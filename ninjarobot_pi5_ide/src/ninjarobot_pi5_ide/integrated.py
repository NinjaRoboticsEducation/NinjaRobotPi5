"""Integrated RobotAssembly capability client for the single-owner agent service."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Awaitable, Callable

from .audio_output import AudioOutput
from .behavior_drafts import BehaviorDraftCompiler, BehaviorDraftError
from .behavior_models import (
    BehaviorDefinition,
)
from .buzzer import BuzzerStopAdapter, BuzzerToneAdapter
from .camera import CameraCaptureAdapter, CameraPreviewAdapter, CameraStatusAdapter
from .config import RobotConfig
from .display import (
    DisplayBrightnessAdapter,
    DisplayClearAdapter,
    DisplayShowTextAdapter,
)
from .distance import VL53L0XDistanceAdapter
from .engine import ExecutionEngine
from .errors import IDEError
from .identity import FaceIdentityDevice
from .ledger import ActionLedger
from .microphone import (
    ManagedVoiceAudioSource,
    MicrophoneCaptureAdapter,
    MicrophoneStatusAdapter,
    MicrophoneTranscribeAdapter,
    SimulatedSpeechTranscriber,
    WhisperCppTranscriber,
    build_managed_wake_detector,
)
from .models import (
    ActionRecord,
    ActionRequest,
    ActionResult,
    CapabilityDescriptor,
    ErrorDetails,
    HealthReport,
    ResourceHealth,
    RetrySafety,
    RiskLevel,
)
from .registry import CapabilityRegistry
from .robot import RobotAssembly
from .safety import MotionController, SafetyStateStore
from .servo import ServoDevice, ServoMoveAdapter, ServoStatusAdapter, ServoStopAdapter
from .voice_input import (
    TranscriptHandler,
    VoiceInputController,
    VoiceInputError,
    VoiceStatusHandler,
    WakeWordDetector,
)


class _SpeechPriorityAdapter:
    """Keep existing explicit device actions ahead of optional spoken output."""

    def __init__(self, adapter: Any, robot: RobotAssembly) -> None:
        self._adapter = adapter
        self._robot = robot
        self.descriptor = adapter.descriptor

    async def start(self) -> None:
        await self._adapter.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        audio = self._robot.audio
        if audio is None:
            result: dict[str, Any] = await self._adapter.execute(arguments)
            return result
        async with audio.foreground():
            result = await self._adapter.execute(arguments)
            return result

    async def health(self) -> ResourceHealth:
        result: ResourceHealth = await self._adapter.health()
        return result

    async def close(self) -> None:
        await self._adapter.close()


class _InlineBehaviorAdapter:
    """Execute one transient, schema-validated behavior definition."""

    def __init__(
        self,
        robot: RobotAssembly,
        *,
        motion: bool,
        servo_roles: tuple[str, ...],
    ) -> None:
        self._robot = robot
        self._servo_roles = frozenset(servo_roles)
        self._motion = motion
        self._compiler = BehaviorDraftCompiler(
            assets=robot.assets,
            servo_roles=servo_roles,
        )
        capability = "behavior.execute_movement" if motion else "behavior.execute_expression"
        description = (
            "Execute one transient validated movement that may combine approved "
            "faces, text, tones, melodies, and logical servo roles. Operations in "
            "one stage start together; stages run in order. Use this tool for every "
            "request containing physical or servo movement. Example arguments: "
            '{"name":"short_forward","description":"Move briefly","stages":'
            '[{"face":"exciting","movement":"move_forward",'
            '"duration_seconds":1},{"movement":"stop","duration_seconds":0.1}]}.'
            if motion
            else "Execute one transient validated expression combining approved "
            "faces, text, tones, and melodies. Operations in one stage start "
            "together; stages run in order. Drive operations are forbidden; never "
            "use this tool for servo movement. Example arguments: "
            '{"name":"happy_tone","description":"Smile and beep","stages":'
            '[{"face":"happy","tone":{"frequency_hz":880,'
            '"duration_seconds":0.2},"duration_seconds":1}]}.'
        )
        input_schema = self._compiler.input_schema(motion=motion)
        self.descriptor = CapabilityDescriptor(
            name=capability,
            version="1.0.0",
            description=description,
            input_schema=input_schema,
            output_schema={"type": "object"},
            risk=RiskLevel.MOTION if motion else RiskLevel.LOW,
            resources=(
                ("display", "buzzer", "servo_bus", "distance_sensor")
                if motion
                else ("display", "buzzer")
            ),
            default_timeout_seconds=300.0,
            idempotent=False,
            cancellable=True,
            confirmation_required=motion,
        )

    async def start(self) -> None:
        await self._robot.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            definition = self._compiler.compile(arguments, motion=self._motion)
        except BehaviorDraftError as exc:
            raise IDEError(
                ErrorDetails(
                    code="BEHAVIOR_DRAFT_INVALID",
                    message=(
                        f"Behavior draft was invalid and no hardware action ran: {exc}. "
                        "Correct the named field and submit a new tool call."
                    ),
                    technical_detail=str(exc),
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability=self.descriptor.name,
                )
            ) from exc
        result = await self._robot.run_definition(definition)
        return {
            **result,
            # Retain the exact definition that passed IDE validation and ran. The
            # agent uses this only after a user confirms that the successful
            # behavior should become a persistent catalog entry.
            "compiled_definition": definition.model_dump(mode="json", exclude_none=False),
        }

    async def health(self) -> ResourceHealth:
        health = await self._robot.health()
        return (
            ResourceHealth.READY
            if health and all(value == "ready" for value in health.values())
            else ResourceHealth.DEGRADED
        )

    async def close(self) -> None:
        return


class _BehaviorPreviewAdapter:
    """Compile a compact behavior draft without starting or touching hardware."""

    def __init__(self, robot: RobotAssembly, *, servo_roles: tuple[str, ...]) -> None:
        self._compiler = BehaviorDraftCompiler(
            assets=robot.assets,
            servo_roles=servo_roles,
        )
        input_schema = deepcopy(self._compiler.input_schema(motion=True))
        input_schema["description"] = (
            "Compile one finite expression or movement draft without executing it."
        )
        input_schema["properties"]["category"] = {
            "type": "string",
            "enum": ["expression", "movement"],
        }
        required = list(input_schema["required"])
        if "category" not in required:
            required.append("category")
        input_schema["required"] = required
        self.descriptor = CapabilityDescriptor(
            name="behavior.preview",
            version="1.0.0",
            description=(
                "Validate and translate one compact robot behavior into the canonical "
                "IDE format without running display, buzzer, or servo hardware."
            ),
            input_schema=input_schema,
            output_schema={"type": "object"},
            risk=RiskLevel.READ_ONLY,
            resources=("behavior_catalog",),
            default_timeout_seconds=2.0,
            idempotent=True,
            cancellable=False,
            confirmation_required=False,
        )

    async def start(self) -> None:
        return

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        category = arguments.get("category")
        if category not in {"expression", "movement"}:
            raise ValueError("behavior preview category must be expression or movement")
        try:
            definition = self._compiler.compile(
                arguments,
                motion=category == "movement",
            )
        except BehaviorDraftError as exc:
            raise IDEError(
                ErrorDetails(
                    code="BEHAVIOR_DRAFT_INVALID",
                    message=f"Behavior draft is invalid and no hardware action ran: {exc}.",
                    technical_detail=str(exc),
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability=self.descriptor.name,
                )
            ) from exc
        return {
            "valid": True,
            "definition": definition.model_dump(mode="json"),
            "contains_motion": definition.contains_motion,
            "required_resources": list(definition.required_resources),
        }

    async def health(self) -> ResourceHealth:
        return ResourceHealth.READY

    async def close(self) -> None:
        return


class _BehaviorSaveAdapter:
    """Persist one validated user behavior without overwriting existing assets."""

    descriptor = CapabilityDescriptor(
        name="behavior.save_user",
        version="1.0.0",
        description=(
            "Save one validated AI-created behavior in the confined user behavior "
            "directory. Call only after the user explicitly asks to save and the "
            "current request carries confirmation. Existing or bundled behaviors "
            "are never overwritten."
        ),
        input_schema=BehaviorDefinition.model_json_schema(),
        output_schema={"type": "object"},
        risk=RiskLevel.MAINTENANCE,
        resources=(),
        default_timeout_seconds=5.0,
        idempotent=False,
        cancellable=False,
        confirmation_required=True,
    )

    def __init__(self, robot: RobotAssembly) -> None:
        self._robot = robot

    async def start(self) -> None:
        await self._robot.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        definition = BehaviorDefinition.model_validate(arguments)
        path = self._robot.assets.save_user(definition, overwrite=False)
        return {
            "saved": True,
            "name": definition.name,
            "category": definition.category,
            "path": str(path),
        }

    async def health(self) -> ResourceHealth:
        return ResourceHealth.READY

    async def close(self) -> None:
        return


class _BehaviorListAdapter:
    descriptor = CapabilityDescriptor(
        name="behavior.list",
        version="1.0.0",
        description="List validated built-in and user-created robot behaviors.",
        input_schema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["all", "expression", "movement"],
                    "default": "all",
                }
            },
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        risk=RiskLevel.READ_ONLY,
        resources=("behavior_catalog",),
        default_timeout_seconds=2.0,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, robot: RobotAssembly) -> None:
        self._robot = robot

    async def start(self) -> None:
        await self._robot.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        category = arguments.get("category", "all")
        if category not in {"all", "expression", "movement"}:
            raise ValueError("category must be all, expression, or movement")
        return {
            "behaviors": [
                definition.model_dump(mode="json")
                for definition in self._robot.assets.list(category)
            ]
        }

    async def health(self) -> ResourceHealth:
        return ResourceHealth.READY

    async def close(self) -> None:
        return


class _BehaviorRunAdapter:
    descriptor = CapabilityDescriptor(
        name="behavior.run",
        version="1.0.0",
        description=(
            "Run one validated robot behavior. Motion behaviors remain protected "
            "by the IDE obstacle guard and emergency stop."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "pattern": r"^[a-z][a-z0-9_]{0,63}$",
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        risk=RiskLevel.MOTION,
        resources=("display", "buzzer", "servo_bus", "distance_sensor"),
        default_timeout_seconds=300.0,
        idempotent=False,
        cancellable=True,
        confirmation_required=True,
    )

    def __init__(self, robot: RobotAssembly) -> None:
        self._robot = robot

    async def start(self) -> None:
        await self._robot.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        name = arguments.get("name")
        if not isinstance(name, str):
            raise ValueError("behavior name must be text")
        return await self._robot.run_behavior(name)

    async def health(self) -> ResourceHealth:
        health = await self._robot.health()
        return (
            ResourceHealth.READY
            if health and all(value == "ready" for value in health.values())
            else ResourceHealth.DEGRADED
        )

    async def close(self) -> None:
        return


class _BehaviorStopAdapter:
    descriptor = CapabilityDescriptor(
        name="behavior.stop",
        version="1.0.0",
        description="Immediately perform the existing Level 2 full robot stop.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        risk=RiskLevel.EMERGENCY,
        resources=("display", "buzzer", "servo_bus", "distance_sensor", "sensors"),
        default_timeout_seconds=5.0,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, robot: RobotAssembly) -> None:
        self._robot = robot

    async def start(self) -> None:
        await self._robot.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise ValueError("behavior.stop accepts no arguments")
        return await self._robot.stop()

    async def health(self) -> ResourceHealth:
        return ResourceHealth.READY

    async def close(self) -> None:
        return


class _ResumeAdapter:
    def __init__(self, robot: RobotAssembly, *, system: bool) -> None:
        self._robot = robot
        self._system = system
        name = "system.resume" if system else "motion.resume"
        description = (
            "Resume all modules after a confirmed Level 2 system stop."
            if system
            else "Clear a confirmed Level 1 motion stop."
        )
        self.descriptor = CapabilityDescriptor(
            name=name,
            version="1.0.0",
            description=description,
            input_schema={
                "type": "object",
                "properties": {"confirmed": {"type": "boolean"}},
                "required": ["confirmed"],
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
            risk=RiskLevel.MAINTENANCE,
            resources=("safety_state", "sensors", "servo_bus"),
            default_timeout_seconds=10.0,
            idempotent=True,
            cancellable=False,
            confirmation_required=True,
        )

    async def start(self) -> None:
        await self._robot.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        confirmed = arguments.get("confirmed")
        if confirmed is not True:
            raise PermissionError("resume requires confirmed=true")
        snapshot = (
            await self._robot.resume_system(confirmed=True)
            if self._system
            else await self._robot.resume_motion(confirmed=True)
        )
        return asdict(snapshot)

    async def health(self) -> ResourceHealth:
        return ResourceHealth.READY

    async def close(self) -> None:
        return


class RobotIDEClient:
    """Delegate IDE contracts while ensuring RobotAssembly closes last."""

    def __init__(
        self,
        robot: RobotAssembly,
        engine: ExecutionEngine,
        identity: FaceIdentityDevice,
        voice_input: VoiceInputController | None = None,
    ) -> None:
        self.robot = robot
        self._engine = engine
        self._identity = identity
        self._voice_input = voice_input
        self._started = False
        self._closed = False

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("robot IDE client is closed")
        if self._started:
            return
        await self.robot.start()
        try:
            await self._engine.start()
        except BaseException:
            await self.robot.close()
            raise
        self._started = True

    async def capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        return await self._engine.capabilities()

    async def execute(self, request: ActionRequest) -> ActionResult:
        return await self._engine.execute(request)

    async def start_liveliness(self) -> dict[str, Any]:
        """Run the service-start greeting through the IDE-owned assembly."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self.robot.start_liveliness()

    async def show_onboarding_qr(self, url: str) -> dict[str, Any]:
        """Display a validated pairing QR through the IDE-owned presentation path."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self.robot.show_onboarding_qr(url)

    async def show_onboarding_status(self, state: str) -> dict[str, Any]:
        """Display one bounded onboarding status, never arbitrary agent text."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        if state not in {"connecting", "error"}:
            raise ValueError("onboarding state must be connecting or error")
        return await self.robot.show_onboarding_status(state)

    async def prepare_onboarding_greeting(self) -> dict[str, Any]:
        """Clear onboarding presentation before Greeting runs exactly once."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self.robot.prepare_onboarding_greeting()

    def bind_voice_handlers(
        self,
        *,
        transcript_handler: TranscriptHandler,
        status_handler: VoiceStatusHandler,
    ) -> None:
        """Connect IDE voice events to the agent after both layers exist."""
        if self._voice_input is None:
            raise VoiceInputError("listener_unavailable")
        self._voice_input.bind_handlers(
            transcript_handler=transcript_handler,
            status_handler=status_handler,
        )

    async def speech_health(self) -> dict[str, Any]:
        if self.robot.audio is None:
            return {"ready": False, "reason": "speech_not_configured"}
        generation = self.robot.audio.generation
        return {**await self.robot.audio.health(), "generation": generation}

    async def speech_outputs(self) -> list[dict[str, str]]:
        if self.robot.audio is None:
            return []
        return await self.robot.audio.outputs()

    async def play_speech(self, audio: bytes, *, generation: int | None = None) -> dict[str, Any]:
        if not self._started or self._closed or self.robot.audio is None:
            raise RuntimeError("speech_not_available")
        return await self.robot.audio.play(audio, generation=generation)

    async def stop_speech(self) -> None:
        if self.robot.audio is not None:
            await self.robot.audio.stop()

    async def start_voice_input(self) -> dict[str, object]:
        """Activate the single IDE-owned microphone listener."""
        if self._voice_input is None:
            raise VoiceInputError("listener_unavailable")
        return await self._voice_input.start()

    async def stop_voice_input(self) -> dict[str, object]:
        """Stop listening and release raw microphone ownership."""
        if self._voice_input is None:
            return {"enabled": False, "state": "disabled"}
        return await self._voice_input.stop()

    def voice_input_status(self) -> dict[str, object]:
        """Return privacy-safe listener status without probing hardware."""
        if self._voice_input is None:
            return {"enabled": False, "state": "disabled"}
        return self._voice_input.status()

    async def show_agent_face(self, expression: str) -> bool:
        """Request an ambient face without exposing display hardware to the agent."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self.robot.show_agent_face(expression)

    async def restore_idle_face(self) -> bool:
        """Restore the IDE-owned silent idle presentation."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self.robot.restore_idle_face()

    async def show_camera_capture(self) -> bool:
        """Show the IDE-owned countdown and camera-capture animation."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self.robot.show_camera_capture()

    async def enroll_face_identity(self, user_id: str) -> dict[str, Any]:
        """Run an IDE-owned countdown and deterministic face enrollment."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self._run_face_identity(lambda: self._identity.enroll(user_id))

    async def identify_face(self) -> dict[str, Any]:
        """Run an IDE-owned countdown and explicit face recognition."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self._run_face_identity(self._identity.identify)

    async def _run_face_identity(
        self,
        operation: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Run one visible identity operation and always restore silent Idle."""
        result: dict[str, Any] | None = None
        operation_error: BaseException | None = None
        try:
            if not await self.robot.show_camera_capture():
                raise IDEError(
                    ErrorDetails(
                        code="IDENTITY_PRESENTATION_STOPPED",
                        message=(
                            "Face capture countdown could not start because robot presentation "
                            "is stopped. Resume the system, then retry the profile workflow."
                        ),
                        definitely_not_executed=True,
                        retry_safety=RetrySafety.SAFE,
                    )
                )
            result = await operation()
        except BaseException as error:
            operation_error = error

        restore_task = asyncio.create_task(self.robot.restore_idle_face())
        try:
            try:
                await asyncio.shield(restore_task)
            except asyncio.CancelledError:
                try:
                    await asyncio.shield(restore_task)
                except BaseException:
                    pass
                raise
        except BaseException as restore_error:
            if operation_error is None:
                raise
            operation_error.add_note(
                "The IDE also failed to restore the Idle presentation: "
                f"{type(restore_error).__name__}: {restore_error}"
            )

        if operation_error is not None:
            raise operation_error
        if result is None:
            raise IDEError(
                ErrorDetails(
                    code="IDENTITY_RESULT_MISSING",
                    message="Face identity operation returned no result; no profile was changed.",
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.UNKNOWN,
                )
            )
        return result

    async def delete_face_identity(self, user_id: str) -> bool:
        """Remove face data selected by the deterministic management interface."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self._identity.delete(user_id)

    async def prepare_face_identity_reset(self) -> str:
        """Quarantine all IDE-owned identity data before a database reset."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self._identity.prepare_reset()

    async def commit_face_identity_reset(self, token: str) -> bool:
        """Permanently erase identity data after the database reset commits."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        return await self._identity.commit_reset(token)

    async def rollback_face_identity_reset(self, token: str) -> None:
        """Restore identity data when the database reset does not commit."""
        if not self._started:
            raise RuntimeError("robot IDE client is not started")
        await self._identity.rollback_reset(token)

    async def action(self, action_id: str) -> ActionRecord | None:
        return await self._engine.action(action_id)

    async def cancel(self, action_id: str) -> ActionResult:
        return await self._engine.cancel(action_id)

    async def health(self) -> HealthReport:
        return self.robot.annotate_health(await self._engine.health())

    def status(self) -> dict[str, Any]:
        """Return non-invasive robot state for agent readiness reporting."""
        return self.robot.status()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        operations: list[Callable[[], Awaitable[object]]] = []
        if self._voice_input is not None:
            operations.append(self._voice_input.stop)
        operations.extend((self._identity.close, self._engine.close, self.robot.close))
        first_error: BaseException | None = None
        for operation in operations:
            try:
                await operation()
            except BaseException as exc:
                first_error = first_error or exc
        if first_error is not None:
            raise first_error


def build_guarded_servo_engine(config: RobotConfig, *, ledger_path: str | Path) -> ExecutionEngine:
    """Keep retained real servo commands inside the IDE owner and motion guard.

    Only servo and distance devices are initialized; this maintenance route does
    not start camera, microphone, greetings, web services or the Agent runtime.
    """
    settings = config.hardware.servos
    i2c = config.hardware.i2c
    servo = ServoDevice(
        enabled=settings.enabled,
        endpoints=settings.endpoints,
        calibration_file=settings.calibration_file,
        i2c_bus=i2c.bus,
        dfr0566_address=i2c.dfr0566_address,
        motion_enabled=settings.motion_enabled,
        group_motion_enabled=settings.group_motion_enabled,
    )
    distance = VL53L0XDistanceAdapter(i2c_bus=i2c.bus, i2c_address=i2c.vl53l0x_address)
    motion = MotionController(
        servo=servo,
        distance=distance,
        config=config.behaviors,
        state=SafetyStateStore(config.behaviors.safety_state_file),
    )
    servo.set_motion_guard(motion.require_motion_context)
    registry = CapabilityRegistry(
        [
            ServoMoveAdapter(servo, move_handler=motion.move_endpoint),
            ServoStatusAdapter(servo),
            ServoStopAdapter(servo),
            distance,
        ]
    )
    return ExecutionEngine(registry, ActionLedger(ledger_path), owns_hardware=True)


def build_robot_ide_client(
    config: RobotConfig,
    *,
    ledger_path: str | Path,
    simulated: bool,
    whisper_command: str | Path = "~/whisper.cpp/build/bin/whisper-cli",
    whisper_model: str | Path = "~/whisper.cpp/models/ggml-base.bin",
    whisper_threads: int = 4,
) -> RobotIDEClient:
    """Build the one integrated IDE client used by the agent service."""
    robot = RobotAssembly(config=config, simulated=simulated)
    transcriber = (
        SimulatedSpeechTranscriber()
        if simulated
        else WhisperCppTranscriber(
            command=whisper_command,
            model=whisper_model,
            threads=whisper_threads,
        )
    )
    registry = CapabilityRegistry()
    for adapter in (
        _BehaviorListAdapter(robot),
        _BehaviorPreviewAdapter(
            robot,
            servo_roles=tuple(config.behaviors.servo_roles),
        ),
        _BehaviorRunAdapter(robot),
        _InlineBehaviorAdapter(
            robot,
            motion=False,
            servo_roles=tuple(config.behaviors.servo_roles),
        ),
        _InlineBehaviorAdapter(
            robot,
            motion=True,
            servo_roles=tuple(config.behaviors.servo_roles),
        ),
        _BehaviorSaveAdapter(robot),
        _BehaviorStopAdapter(robot),
        _ResumeAdapter(robot, system=False),
        _ResumeAdapter(robot, system=True),
        robot.distance,
        DisplayShowTextAdapter(robot.display),
        DisplayClearAdapter(robot.display),
        DisplayBrightnessAdapter(robot.display),
        BuzzerToneAdapter(robot.buzzer),
        BuzzerStopAdapter(robot.buzzer),
        ServoStatusAdapter(robot.servo),
        ServoMoveAdapter(robot.servo, move_handler=robot.move_servo_endpoint),
        ServoStopAdapter(robot.servo),
        CameraStatusAdapter(robot.camera),
        CameraCaptureAdapter(robot.camera),
        CameraPreviewAdapter(robot.camera),
        MicrophoneStatusAdapter(robot.microphone),
        MicrophoneCaptureAdapter(robot.microphone),
        MicrophoneTranscribeAdapter(robot.microphone, transcriber),
    ):
        priority = adapter.descriptor.name in {
            "behavior.run",
            "behavior.execute_expression",
            "behavior.execute_movement",
            "display.show_text",
            "display.clear",
            "display.set_brightness",
            "buzzer.play_tone",
            "camera.capture",
            "camera.preview",
            "microphone.capture",
            "microphone.transcribe",
        }
        registry.register(_SpeechPriorityAdapter(adapter, robot) if priority else adapter)
    engine = ExecutionEngine(
        registry,
        ActionLedger(ledger_path),
        execution_guard=lambda request: robot.ensure_action_allowed(request.capability),
    )
    identity = FaceIdentityDevice(
        robot.camera,
        data_directory=config.memory.face_data_directory,
    )
    voice_config = config.voice_input
    voice_assets = Path(__file__).with_name("assets")
    model_path = voice_assets / "hey_Ninja.onnx"

    def detector_factory() -> WakeWordDetector:
        if simulated:
            raise VoiceInputError("simulation_voice_unavailable")
        return build_managed_wake_detector(
            model_path=model_path,
            threshold=voice_config.wake_threshold,
            vad_threshold=(voice_config.wake_vad_threshold if voice_config.vad_enabled else 0.0),
            enable_noise_suppression=voice_config.noise_suppression_enabled,
            inference_framework=voice_config.inference_framework,
            runtime_asset_directory=voice_assets / "openwakeword",
        )

    def source_factory() -> ManagedVoiceAudioSource:
        if simulated:
            raise VoiceInputError("simulation_voice_unavailable")
        microphone = config.hardware.microphone
        return ManagedVoiceAudioSource(
            selector=microphone.device_selector,
            requested_sample_rate=microphone.sample_rate_hz,
            channels=microphone.channels,
        )

    voice_input = VoiceInputController(
        detector_factory=detector_factory,
        audio_source_factory=source_factory,
        transcriber=transcriber,
        max_command_seconds=voice_config.max_command_seconds,
        silence_stop_seconds=voice_config.silence_stop_seconds,
        cooldown_seconds=voice_config.cooldown_seconds,
        vad_enabled=voice_config.vad_enabled,
        silence_rms_threshold=voice_config.silence_rms_threshold,
        language=voice_config.language,
        retry_limit=voice_config.retry_limit,
        startup_timeout_seconds=voice_config.startup_timeout_seconds,
    )
    robot.audio = AudioOutput(
        config.speech_output,
        voice=voice_input,
        microphone=robot.microphone,
        permitted=lambda: not robot.system_safety.stopped and not robot._closing,
        scene=robot.speech_scene,
        simulated=simulated,
    )
    robot.microphone.set_voice_coordinator(voice_input)
    return RobotIDEClient(robot, engine, identity, voice_input)
