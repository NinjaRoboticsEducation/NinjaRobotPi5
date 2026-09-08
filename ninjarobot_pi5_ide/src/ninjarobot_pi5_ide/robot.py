"""V4-owned robot assembly for coordinated IDE behavior execution."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any, cast

from .behavior_assets import BehaviorAssetRepository
from .behavior_models import (
    BehaviorDefinition,
    BehaviorStage,
    FaceOperation,
    normalize_face_name,
)
from .behavior_runtime import BehaviorRunner, MelodyProvider, load_pi5buzzer_melody
from .buzzer import BuzzerDevice, BuzzerFactory
from .camera import CameraDevice, CameraFactory
from .config import RobotConfig
from .display import DisplayDevice, DisplayFactory
from .distance import SensorFactory, VL53L0XDistanceAdapter
from .errors import IDEError, describe_hardware_driver_error, is_hardware_driver_error
from .face_renderer import render_emergency_stop
from .hardware_ownership import HardwareOwnership
from .microphone import MicrophoneBackendFactory, MicrophoneDevice
from .models import ErrorDetails, HealthReport, ResourceHealth, RetrySafety
from .qr_display import render_pairing_qr
from .safety import (
    MotionController,
    MotionSafetyError,
    SafetySnapshot,
    SafetyStateStore,
    SystemSafetyController,
    UndervoltageProvider,
    raspberry_pi_undervoltage_active,
    stop_guidance,
)
from .servo import ServoDevice, ServoFactory
from .simulation import (
    SimulatedBuzzerDriver,
    SimulatedDisplayDriver,
    SimulatedDistanceSensor,
    SimulatedMicrophoneBackend,
    simulated_servo_runtime,
)

CAMERA_COUNTDOWN_INTERVAL_SECONDS = 1.0
OBSTACLE_WARNING_SECONDS = 2.0
LOGGER = logging.getLogger(__name__)


class RobotAssembly:
    """Share configured device instances across all integrated behavior work."""

    def __init__(
        self,
        *,
        config: RobotConfig,
        display_factory: DisplayFactory | None = None,
        buzzer_factory: BuzzerFactory | None = None,
        servo_factory: ServoFactory | None = None,
        distance_factory: SensorFactory | None = None,
        camera_factory: CameraFactory | None = None,
        microphone_factory: MicrophoneBackendFactory | None = None,
        melody_provider: MelodyProvider = load_pi5buzzer_melody,
        undervoltage_provider: UndervoltageProvider = raspberry_pi_undervoltage_active,
        simulated: bool = False,
    ) -> None:
        display_config = config.hardware.display
        buzzer_config = config.hardware.buzzer
        servo_config = config.hardware.servos
        i2c_config = config.hardware.i2c
        camera_config = config.hardware.camera
        microphone_config = config.hardware.microphone
        self._enabled_devices = {
            "display": display_config.enabled,
            "buzzer": buzzer_config.enabled,
            "servo": servo_config.enabled,
            "distance": True,
            "camera": camera_config.enabled,
            "microphone": microphone_config.enabled,
        }
        self.assets = BehaviorAssetRepository(config.behaviors.user_directory)
        self.display = DisplayDevice(
            enabled=display_config.enabled,
            spi_bus=display_config.spi_bus,
            spi_device=display_config.spi_device,
            dc_gpio=display_config.dc_gpio,
            reset_gpio=display_config.reset_gpio,
            backlight_gpio=display_config.backlight_gpio,
            frequency_hz=display_config.frequency_hz,
            width=display_config.width,
            height=display_config.height,
            rotation=display_config.rotation,
            initial_brightness=display_config.brightness,
            driver_factory=(
                display_factory
                if display_factory is not None
                else SimulatedDisplayDriver
                if simulated
                else None
            ),
            simulated=simulated,
        )
        self.buzzer = BuzzerDevice(
            enabled=buzzer_config.enabled,
            pin=buzzer_config.gpio,
            driver_factory=(
                buzzer_factory
                if buzzer_factory is not None
                else SimulatedBuzzerDriver
                if simulated
                else None
            ),
            simulated=simulated,
        )
        self.servo = ServoDevice(
            enabled=servo_config.enabled,
            endpoints=servo_config.endpoints,
            calibration_file=servo_config.calibration_file,
            i2c_bus=i2c_config.bus,
            dfr0566_address=i2c_config.dfr0566_address,
            motion_enabled=servo_config.motion_enabled,
            group_motion_enabled=servo_config.group_motion_enabled,
            runtime_factory=(
                servo_factory
                if servo_factory is not None
                else simulated_servo_runtime
                if simulated
                else None
            ),
            simulated=simulated,
        )
        self.distance = VL53L0XDistanceAdapter(
            i2c_bus=i2c_config.bus,
            i2c_address=i2c_config.vl53l0x_address,
            sensor_factory=(
                distance_factory
                if distance_factory is not None
                else SimulatedDistanceSensor
                if simulated
                else None
            ),
        )
        self.camera = CameraDevice(
            enabled=camera_config.enabled,
            width=camera_config.width,
            height=camera_config.height,
            warmup_seconds=camera_config.warmup_seconds,
            autofocus_mode=camera_config.autofocus_mode,
            media_directory=camera_config.media_directory,
            camera_factory=camera_factory,
            simulated=simulated,
        )
        self.microphone = MicrophoneDevice(
            enabled=microphone_config.enabled,
            device_selector=microphone_config.device_selector,
            sample_rate_hz=microphone_config.sample_rate_hz,
            channels=microphone_config.channels,
            max_capture_seconds=microphone_config.max_capture_seconds,
            media_directory=microphone_config.media_directory,
            backend_factory=(
                microphone_factory
                if microphone_factory is not None
                else cast(MicrophoneBackendFactory, SimulatedMicrophoneBackend)
                if simulated
                else None
            ),
            simulated=simulated,
        )
        self.safety_state = SafetyStateStore(config.behaviors.safety_state_file)
        self.motion = MotionController(
            servo=self.servo,
            distance=self.distance,
            config=config.behaviors,
            state=self.safety_state,
            undervoltage_provider=undervoltage_provider,
            warning_handler=self._show_motion_warning,
            system_stopped=lambda: self.system_safety.stopped,
        )
        self.behaviors = BehaviorRunner(
            display=self.display,
            buzzer=self.buzzer,
            melody_provider=melody_provider,
        )
        self.system_safety = SystemSafetyController(
            motion=self.motion,
            state=self.safety_state,
            silence_buzzer=self.buzzer.stop,
            show_stopped=self._show_system_stopped,
            sensors=(self.distance, self.camera, self.microphone),
            display_hold_seconds=config.behaviors.system_stopped_display_seconds,
        )
        self.servo.set_motion_guard(self.motion.require_motion_context)
        self.behaviors.set_drive_handler(self.motion.drive)
        self.behaviors.set_failure_handler(self._driver_failure)
        self._liveliness_enabled = False
        self._idle_suppressed = False
        self._ambient_face = "idle"
        self._foreground_behaviors = 0
        self._idle_task: asyncio.Task[None] | None = None
        self._idle_lock = asyncio.Lock()
        self._idle_error: str | None = None
        self._closing = False
        self._closed = False
        self._close_lock = asyncio.Lock()
        self._hardware_ownership = HardwareOwnership()
        if not simulated:
            self._hardware_ownership.acquire()

    async def start(self) -> None:
        """Initialize shared expression hardware without running a behavior."""
        await self.behaviors.start()

    async def start_liveliness(self) -> dict[str, Any]:
        """Run the one-time greeting and then supervise a silent idle face."""
        self._liveliness_enabled = True
        self._idle_suppressed = False
        return await self.run_behavior("greeting")

    async def show_onboarding_qr(self, url: str) -> dict[str, Any]:
        """Render one trusted pairing QR without exposing arbitrary images."""
        if self.system_safety.stopped:
            raise RuntimeError("system is stopped; onboarding QR cannot replace safety state")
        await self._stop_idle()
        width, height = await self.display.dimensions()
        image = render_pairing_qr(url, width=width, height=height)
        return await self.display.show_image(image, source="phase-8-onboarding-qr")

    async def show_onboarding_status(
        self,
        state: str,
    ) -> dict[str, Any]:
        """Show one bounded boot state while Greeting remains disabled."""
        if state not in {"connecting", "error"}:
            raise ValueError("onboarding state must be connecting or error")
        if self.system_safety.stopped:
            raise RuntimeError("system is stopped; onboarding cannot replace safety state")
        await self._stop_idle()
        text = "Connecting…" if state == "connecting" else "Error"
        return await self.display.show_text(
            text=text,
            font_size=32 if state == "connecting" else 48,
            foreground="#FFFFFF",
            background="#00152E" if state == "connecting" else "#8B0018",
        )

    async def prepare_onboarding_greeting(self) -> dict[str, Any]:
        """Clear the QR immediately before the one authorized Greeting attempt."""
        await self._stop_idle()
        return await self.display.clear(color="#000000")

    async def run_behavior(self, name: str) -> dict[str, Any]:
        """Load and run one validated expression behavior by safe name."""
        return await self.run_definition(self.assets.load(name))

    def ensure_action_allowed(self, capability: str) -> None:
        """Keep low-level output and sensing calls behind the system stop gate."""
        if capability in {
            "behavior.stop",
            "servo.stop",
            "buzzer.stop",
            "system.resume",
            "motion.resume",
            "servo.status",
            "camera.status",
            "microphone.status",
            "behavior.list",
            "behavior.preview",
            "behavior.save_user",
        }:
            return
        if self.system_safety.stopped:
            snapshot = self.safety_state.read()
            guidance = stop_guidance(
                snapshot.reason or "operator_stop", fault_detail=snapshot.fault_detail
            )
            raise IDEError(
                ErrorDetails(
                    code="SYSTEM_STOPPED",
                    message=f"{guidance.cause} Recovery: {guidance.recovery_instruction}",
                    technical_detail=snapshot.fault_detail,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability=capability,
                )
            )

    async def move_servo_endpoint(
        self,
        *,
        endpoint: str,
        target_angle: float,
        speed_mode: str,
    ) -> dict[str, Any]:
        """Coordinate a raw endpoint request with motion safety and presentation."""
        self.ensure_action_allowed("servo.move")
        await self._begin_foreground_behavior()
        try:
            return await self.motion.move_endpoint(
                endpoint=endpoint,
                target_angle=target_angle,
                speed_mode=speed_mode,
            )
        except Exception as exc:
            await self._driver_failure(exc)
            raise
        finally:
            await self._end_foreground_behavior()

    async def run_definition(self, definition: BehaviorDefinition) -> dict[str, Any]:
        """Run one already-validated definition through the same safety boundary."""
        requirements = {
            "face": "display",
            "text": "display",
            "tone": "buzzer",
            "melody": "buzzer",
            "drive": "servo",
        }
        disabled = {
            requirements[operation.kind]
            for stage in definition.stages
            for operation in stage.operations
            if operation.kind in requirements
            and not self._enabled_devices[requirements[operation.kind]]
        }
        if disabled:
            raise IDEError(
                ErrorDetails(
                    code="DEVICE_DISABLED",
                    message=f"Behavior requires disabled devices: {', '.join(sorted(disabled))}.",
                    technical_detail=None,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="behavior.run",
                )
            )
        if self.system_safety.stopped:
            snapshot = self.safety_state.read()
            guidance = stop_guidance(
                snapshot.reason or "operator_stop",
                fault_detail=snapshot.fault_detail,
            )
            raise IDEError(
                ErrorDetails(
                    code="SYSTEM_STOPPED",
                    message=f"{guidance.cause} Recovery: {guidance.recovery_instruction}",
                    technical_detail=snapshot.fault_detail,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="behavior.run",
                )
            )
        await self._begin_foreground_behavior()
        try:
            result = await self.behaviors.run(definition)
            interruption = result.get("interruption")
            if (
                result.get("interrupted") is True
                and isinstance(interruption, dict)
                and interruption.get("stop_reason") == "front_obstacle"
            ):
                message = (
                    "An obstacle was detected inside the configured safety distance, so "
                    "the current movement was stopped."
                )
                recovery = (
                    "No safety resume is required. Check and clear the robot's path, then "
                    "issue a new command. The interrupted behavior will not restart "
                    "automatically."
                )
                LOGGER.warning(
                    "Behavior interrupted by obstacle: behavior=%s cause=%s recovery=%s",
                    definition.name,
                    message,
                    recovery,
                )
                await self.behaviors.run(self._obstacle_warning_definition())
                result = {
                    **result,
                    "cause": message,
                    "recovery_instruction": recovery,
                    "user_message": f"{message} {recovery}",
                    "requires_resume": False,
                    "next_state": "idle",
                }
            elif result.get("interrupted") is True and isinstance(interruption, dict):
                persistent_cause = interruption.get("cause")
                persistent_recovery = interruption.get("recovery_instruction")
                if not isinstance(persistent_cause, str) or not isinstance(
                    persistent_recovery, str
                ):
                    guidance = stop_guidance(str(interruption.get("stop_reason") or "unknown"))
                    persistent_cause = guidance.cause
                    persistent_recovery = guidance.recovery_instruction
                LOGGER.error(
                    "Behavior interrupted by persistent safety stop: behavior=%s "
                    "cause=%s recovery=%s",
                    definition.name,
                    persistent_cause,
                    persistent_recovery,
                )
                result = {
                    **result,
                    "cause": persistent_cause,
                    "recovery_instruction": persistent_recovery,
                    "user_message": (f"{persistent_cause} Recovery: {persistent_recovery}"),
                    "requires_resume": True,
                    "next_state": "safety_stopped",
                }
        finally:
            await self._end_foreground_behavior()
        return result

    async def show_agent_face(self, expression: str) -> bool:
        """Loop one silent agent face unless safety or a foreground action has priority."""
        face = normalize_face_name(expression)
        self._ambient_face = face
        await self._stop_idle()
        await self._start_idle_if_safe()
        return (
            not self.system_safety.stopped
            and self._idle_task is not None
            and not self._idle_task.done()
        )

    async def restore_idle_face(self) -> bool:
        """Restore the normal silent idle loop after an agent interaction."""
        return await self.show_agent_face("idle")

    async def show_camera_capture(self) -> bool:
        """Count down clearly, then loop the camera icon during capture."""
        if self.system_safety.stopped:
            return False
        self._ambient_face = "camera"
        await self._stop_idle()
        for count in ("3", "2", "1"):
            if self.system_safety.stopped:
                return False
            await self.display.show_text(
                text=count,
                font_size=128,
                foreground="#FFFFFF",
                background="#00152E",
            )
            await asyncio.sleep(CAMERA_COUNTDOWN_INTERVAL_SECONDS)
        await self._start_idle_if_safe()
        return (
            not self.system_safety.stopped
            and self._idle_task is not None
            and not self._idle_task.done()
        )

    async def health(self) -> dict[str, str]:
        """Return integrated expression component health."""
        health = await self.behaviors.health()
        if self._liveliness_enabled:
            health["idle"] = "degraded" if self._idle_error is not None else "ready"
        return health

    def annotate_health(self, report: HealthReport) -> HealthReport:
        """Explain configured and safety restrictions without touching devices."""
        capabilities = dict(report.capabilities)
        snapshot = self.safety_state.read()
        for name, item in capabilities.items():
            device = name.split(".", 1)[0]
            if not self._enabled_devices.get(device, True):
                item = item.model_copy(
                    update={
                        "status": ResourceHealth.NOT_CONFIGURED,
                        "reason_code": "disabled_in_configuration",
                        "recovery": "This device is disabled. Leave it disabled if intentional; "
                        "otherwise review its configuration and restart after correction.",
                    }
                )
            try:
                self.ensure_action_allowed(name)
            except IDEError:
                item = item.model_copy(
                    update={
                        "execution_blocked": True,
                        "reason_code": "system_stopped",
                        "recovery": "Remove the hazard and correct the fault, then explicitly use "
                        "Resume Robot Movement. Interrupted actions do not restart automatically.",
                    }
                )
            else:
                if snapshot.motion_latched and name in {
                    "servo.move",
                    "behavior.execute_movement",
                    "behavior.run",
                }:
                    item = item.model_copy(
                        update={
                            "execution_blocked": True,
                            "reason_code": "motion_stopped",
                            "recovery": "Correct the fault, then explicitly resume movement. "
                            "A named behavior may still be usable if it contains no movement.",
                        }
                    )
            capabilities[name] = item
        return report.model_copy(update={"capabilities": capabilities})

    def status(self) -> dict[str, Any]:
        """Return non-invasive safety and liveliness supervision state."""
        snapshot = self.safety_state.read()
        idle_running = self._idle_task is not None and not self._idle_task.done()
        if not self._liveliness_enabled:
            liveliness_state = "disabled"
        elif self._idle_error is not None:
            liveliness_state = "degraded"
        elif self._closing:
            liveliness_state = "closing"
        elif self._idle_suppressed or self.system_safety.stopped:
            liveliness_state = "suppressed"
        elif self._foreground_behaviors:
            liveliness_state = "foreground"
        elif idle_running:
            liveliness_state = "running"
        else:
            liveliness_state = "degraded"
        return {
            "safety": asdict(snapshot),
            "recovery_required": snapshot.system_latched,
            "motion_recovery_required": (snapshot.motion_latched and not snapshot.system_latched),
            "liveliness": {
                "enabled": self._liveliness_enabled,
                "state": liveliness_state,
                "idle_error": self._idle_error,
                "idle_task_running": idle_running,
                "ambient_face": self._ambient_face,
                "foreground_behaviors": self._foreground_behaviors,
            },
        }

    async def stop(self) -> dict[str, Any]:
        """Perform a non-latching full stop requested by the operator."""
        self._idle_suppressed = True
        # Dispatch device stop before waiting for expression cancellation. A
        # blocked display must not postpone the request to de-energize motors.
        results = await asyncio.gather(
            self.system_safety.full_stop("operator_stop", latch=False),
            self._stop_idle(),
            self.behaviors.stop(),
            return_exceptions=True,
        )
        result = results[0]
        if isinstance(result, BaseException):
            raise result
        assert isinstance(result, dict)
        result["cleanup_errors"].extend(
            f"{type(error).__name__}: {error}"
            for error in results[1:]
            if isinstance(error, BaseException)
        )
        return result

    async def resume_motion(self, *, confirmed: bool) -> SafetySnapshot:
        """Clear an explicitly confirmed Level 1 latch."""
        snapshot = self.motion.resume(confirmed=confirmed)
        self._idle_suppressed = False
        await self._start_idle_if_safe()
        return snapshot

    async def resume_system(self, *, confirmed: bool) -> SafetySnapshot:
        """Clear Level 2 only after every configured device reports ready."""
        snapshot = await self.system_safety.resume_system(
            confirmed=confirmed,
            health_checks={
                name: probe
                for name, probe in {
                    "display": self._display_health,
                    "buzzer": self._buzzer_health,
                    "servo": self._servo_health,
                    "distance": self._distance_health,
                    "camera": self._camera_health,
                    "microphone": self._microphone_health,
                }.items()
                if self._enabled_devices[name]
            },
        )
        self._idle_suppressed = False
        await self._start_idle_if_safe()
        return snapshot

    async def close(self) -> None:
        """Release all assembly-owned devices."""
        async with self._close_lock:
            if self._closed:
                return
            self._closing = True
            self._idle_suppressed = True
            try:
                await self._stop_idle()
                await self.behaviors.stop()
                await asyncio.gather(
                    self.servo.close(),
                    self.distance.close(),
                    self.camera.close(),
                    self.microphone.close(),
                    return_exceptions=True,
                )
                await self.behaviors.close()
                self._closed = True
            finally:
                self._hardware_ownership.release()

    async def _driver_failure(self, error: Exception) -> str | None:
        if (
            getattr(self, "_closing", False)
            or isinstance(error, MotionSafetyError)
            or not is_hardware_driver_error(error)
        ):
            return None
        detail = describe_hardware_driver_error(error)
        guidance = stop_guidance("driver_failure", fault_detail=detail)
        LOGGER.error(
            "Hardware driver failure escalated to a persistent Level 2 stop: %s recovery=%s",
            detail,
            guidance.recovery_instruction,
            exc_info=(type(error), error, error.__traceback__),
        )
        self._idle_suppressed = True
        await self._stop_idle()
        stopped = await self.system_safety.full_stop(
            "driver_failure",
            latch=True,
            fault_detail=detail,
        )
        cleanup_errors = stopped.get("cleanup_errors")
        if cleanup_errors:
            LOGGER.error("Level 2 cleanup reported errors: %s", cleanup_errors)
        return guidance.recovery_instruction

    async def _start_idle_if_safe(self) -> None:
        if (
            not self._liveliness_enabled
            or self._idle_suppressed
            or self._closing
            or self.system_safety.stopped
            or self._foreground_behaviors
        ):
            return
        snapshot = self.safety_state.read()
        if snapshot.motion_latched or snapshot.system_latched:
            return
        async with self._idle_lock:
            if self._foreground_behaviors:
                return
            if self._idle_task is not None and not self._idle_task.done():
                return
            definition = self._silent_face_definition(self._ambient_face)
            self._idle_error = None
            self._idle_task = asyncio.create_task(
                self._run_idle(definition),
                name=f"ninjarobot-silent-{self._ambient_face}",
            )
        await asyncio.sleep(0)

    async def _begin_foreground_behavior(self) -> None:
        async with self._idle_lock:
            self._foreground_behaviors += 1
        try:
            await self._stop_idle()
        except BaseException:
            async with self._idle_lock:
                self._foreground_behaviors = max(0, self._foreground_behaviors - 1)
            raise

    async def _end_foreground_behavior(self) -> None:
        async with self._idle_lock:
            self._foreground_behaviors = max(0, self._foreground_behaviors - 1)
            if self._foreground_behaviors == 0:
                self._ambient_face = "idle"
        await self._start_idle_if_safe()

    async def _run_idle(self, definition: BehaviorDefinition) -> None:
        current = asyncio.current_task()
        try:
            await self.behaviors.run(definition)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._idle_error = f"{type(exc).__name__}: {exc}"
            LOGGER.error(
                "Idle face supervisor stopped unexpectedly: %s",
                self._idle_error,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            return
        finally:
            async with self._idle_lock:
                if self._idle_task is current:
                    self._idle_task = None

    async def _stop_idle(self) -> None:
        async with self._idle_lock:
            task = self._idle_task
            self._idle_task = None
        if task is None or task is asyncio.current_task():
            return
        if not task.done() and not task.cancelling():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    def _silent_face_definition(self, expression: str) -> BehaviorDefinition:
        if expression == "camera":
            source = FaceOperation(
                kind="face",
                expression="camera",
                background="#00152E",
                foreground="#FFFFFF",
                accent="#00BFFF",
                hold_seconds=None,
            )
        else:
            configured = self.assets.load(expression)
            source = next(
                operation
                for stage in configured.stages
                for operation in stage.operations
                if isinstance(operation, FaceOperation)
            )
        return BehaviorDefinition(
            schema_version=1,
            name=f"agent_{expression}",
            description=f"Loop the embedded {expression} face silently.",
            category="expression",
            stages=(
                BehaviorStage(
                    name=f"silent_{expression}_face",
                    operations=(source.model_copy(update={"hold_seconds": None}),),
                ),
            ),
        )

    def _obstacle_warning_definition(self) -> BehaviorDefinition:
        """Show one bounded scary face without extending the stopped movement."""
        configured = self.assets.load("scary")
        source = next(
            operation
            for stage in configured.stages
            for operation in stage.operations
            if isinstance(operation, FaceOperation)
        )
        return BehaviorDefinition(
            schema_version=1,
            name="obstacle_warning",
            description="Show a bounded silent obstacle warning before returning to Idle.",
            category="expression",
            stages=(
                BehaviorStage(
                    name="scary_obstacle_face",
                    operations=(
                        source.model_copy(update={"hold_seconds": OBSTACLE_WARNING_SECONDS}),
                    ),
                ),
            ),
        )

    async def _show_system_stopped(self) -> dict[str, Any]:
        if not self.display.enabled:
            return {"display_skipped": "disabled by configuration"}
        try:
            width, height = await self.display.dimensions()
            image = render_emergency_stop(width=width, height=height)
            return await self.display.show_image(
                image,
                source="safety:emergency-stop",
            )
        except Exception as icon_error:
            detail = f"{type(icon_error).__name__}: {icon_error}"
            LOGGER.error(
                "Emergency-stop icon failed; attempting the text fallback: %s",
                detail,
                exc_info=(type(icon_error), icon_error, icon_error.__traceback__),
            )
            try:
                result = await self.display.show_text(
                    text="EMERGENCY STOP\nRESUME REQUIRED",
                    font_size=28,
                    foreground="#FFFFFF",
                    background="#8B0018",
                )
            except Exception as fallback_error:
                fallback_detail = f"{type(fallback_error).__name__}: {fallback_error}"
                raise RuntimeError(
                    f"emergency-stop display failed: icon={detail}; text_fallback={fallback_detail}"
                ) from fallback_error
            return {
                **result,
                "fallback": "text",
                "emergency_icon_error": detail,
            }

    async def _show_motion_warning(self, warning: str) -> dict[str, Any]:
        if warning.startswith("distance reading unavailable"):
            message = "SENSOR WARNING\nREADING UNAVAILABLE\nMOVEMENT CONTINUES"
        elif warning.startswith("distance reading stale"):
            message = "SENSOR WARNING\nREADING STALE\nMOVEMENT CONTINUES"
        else:
            message = "POWER WARNING\nSTATUS UNAVAILABLE\nMOVEMENT CONTINUES"
        return await self.display.show_text(
            text=message,
            font_size=18,
            foreground="#FFFFFF",
            background="#604000",
        )

    async def _display_health(self) -> bool:
        snapshot = self.safety_state.read()
        if snapshot.system_latched and (snapshot.fault_detail or "").startswith("DISPLAY_"):
            await self.display.recover()
        else:
            await self.display.start()
        return await self.display.health() is ResourceHealth.READY

    async def _buzzer_health(self) -> bool:
        snapshot = self.safety_state.read()
        if snapshot.system_latched and (snapshot.fault_detail or "").startswith("BUZZER_"):
            await self.buzzer.recover()
        else:
            await self.buzzer.start()
        return await self.buzzer.health() is ResourceHealth.READY

    async def _servo_health(self) -> bool:
        await self.servo.start()
        return await self.servo.health() is ResourceHealth.READY

    async def _distance_health(self) -> bool:
        await self.distance.start()
        return await self.distance.health() is ResourceHealth.READY

    async def _camera_health(self) -> bool:
        await self.camera.start()
        return await self.camera.health() is ResourceHealth.READY

    async def _microphone_health(self) -> bool:
        await self.microphone.start()
        return await self.microphone.health() is ResourceHealth.READY
