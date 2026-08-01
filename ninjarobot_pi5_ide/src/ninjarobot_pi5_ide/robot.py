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
from .errors import describe_hardware_driver_error, is_hardware_driver_error
from .face_renderer import render_emergency_stop
from .hardware_ownership import HardwareOwnership
from .microphone import MicrophoneBackendFactory, MicrophoneDevice
from .models import ResourceHealth
from .safety import (
    MotionController,
    MotionSafetyError,
    SafetySnapshot,
    SafetyStateStore,
    SystemSafetyController,
    UndervoltageProvider,
    raspberry_pi_undervoltage_active,
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
        self.assets = BehaviorAssetRepository(config.behaviors.user_directory)
        self.display = DisplayDevice(
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

    async def run_behavior(self, name: str) -> dict[str, Any]:
        """Load and run one validated expression behavior by safe name."""
        return await self.run_definition(self.assets.load(name))

    async def run_definition(self, definition: BehaviorDefinition) -> dict[str, Any]:
        """Run one already-validated definition through the same safety boundary."""
        if self.system_safety.stopped:
            snapshot = self.safety_state.read()
            raise RuntimeError(
                f"system is stopped ({snapshot.reason or 'local_stop'}); "
                "resume or launch a fresh tool process"
            )
        await self._begin_foreground_behavior()
        try:
            result = await self.behaviors.run(definition)
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
        await self._stop_idle()
        await self.behaviors.stop()
        return await self.system_safety.full_stop("operator_stop", latch=False)

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
                "display": self._display_health,
                "buzzer": self._buzzer_health,
                "servo": self._servo_health,
                "distance": self._distance_health,
                "camera": self._camera_health,
                "microphone": self._microphone_health,
            },
        )
        self._idle_suppressed = False
        await self._start_idle_if_safe()
        return snapshot

    async def close(self) -> None:
        """Release all assembly-owned devices."""
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
        finally:
            self._hardware_ownership.release()

    async def _driver_failure(self, error: Exception) -> None:
        if isinstance(error, MotionSafetyError) or not is_hardware_driver_error(error):
            return
        detail = describe_hardware_driver_error(error)
        LOGGER.error(
            "Hardware driver failure escalated to a persistent Level 2 stop: %s",
            detail,
            exc_info=(type(error), error, error.__traceback__),
        )
        self._idle_suppressed = True
        stopped = await self.system_safety.full_stop(
            "driver_failure",
            latch=True,
            fault_detail=detail,
        )
        cleanup_errors = stopped.get("cleanup_errors")
        if cleanup_errors:
            LOGGER.error("Level 2 cleanup reported errors: %s", cleanup_errors)

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
        await self._stop_idle()

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
        if not task.done():
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

    async def _show_system_stopped(self) -> dict[str, Any]:
        width, height = await self.display.dimensions()
        image = render_emergency_stop(width=width, height=height)
        return await self.display.show_image(
            image,
            source="safety:emergency-stop",
        )

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
