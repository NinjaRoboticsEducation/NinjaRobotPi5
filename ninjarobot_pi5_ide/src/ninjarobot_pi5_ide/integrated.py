"""Integrated RobotAssembly capability client for the single-owner agent service."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

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
from .engine import ExecutionEngine
from .errors import IDEError
from .ledger import ActionLedger
from .microphone import (
    MicrophoneCaptureAdapter,
    MicrophoneStatusAdapter,
    MicrophoneTranscribeAdapter,
    SimulatedSpeechTranscriber,
    WhisperCppTranscriber,
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
from .servo import ServoMoveAdapter, ServoStatusAdapter, ServoStopAdapter


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
        return await self._robot.run_definition(definition)

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

    def __init__(self, robot: RobotAssembly, engine: ExecutionEngine) -> None:
        self.robot = robot
        self._engine = engine
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

    async def action(self, action_id: str) -> ActionRecord | None:
        return await self._engine.action(action_id)

    async def cancel(self, action_id: str) -> ActionResult:
        return await self._engine.cancel(action_id)

    async def health(self) -> HealthReport:
        return await self._engine.health()

    def status(self) -> dict[str, Any]:
        """Return non-invasive robot state for agent readiness reporting."""
        return self.robot.status()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._engine.close()
        await self.robot.close()


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
        ServoMoveAdapter(robot.servo),
        ServoStopAdapter(robot.servo),
        CameraStatusAdapter(robot.camera),
        CameraCaptureAdapter(robot.camera),
        CameraPreviewAdapter(robot.camera),
        MicrophoneStatusAdapter(robot.microphone),
        MicrophoneCaptureAdapter(robot.microphone),
        MicrophoneTranscribeAdapter(robot.microphone, transcriber),
    ):
        registry.register(adapter)
    engine = ExecutionEngine(registry, ActionLedger(ledger_path))
    return RobotIDEClient(robot, engine)
