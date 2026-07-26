"""V4-owned robot assembly for coordinated IDE behavior execution."""

from __future__ import annotations

import asyncio
from typing import Any

from .behavior_assets import BehaviorAssetRepository
from .behavior_models import BehaviorDefinition
from .behavior_runtime import BehaviorRunner, MelodyProvider, load_pi5buzzer_melody
from .buzzer import BuzzerDevice, BuzzerFactory
from .camera import CameraDevice, CameraFactory
from .config import RobotConfig
from .display import DisplayDevice, DisplayFactory
from .distance import SensorFactory, VL53L0XDistanceAdapter
from .face_renderer import render_emergency_stop
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
            driver_factory=display_factory,
            simulated=simulated,
        )
        self.buzzer = BuzzerDevice(
            pin=buzzer_config.gpio,
            driver_factory=buzzer_factory,
            simulated=simulated,
        )
        self.servo = ServoDevice(
            endpoints=servo_config.endpoints,
            calibration_file=servo_config.calibration_file,
            i2c_bus=i2c_config.bus,
            dfr0566_address=i2c_config.dfr0566_address,
            motion_enabled=servo_config.motion_enabled,
            group_motion_enabled=servo_config.group_motion_enabled,
            runtime_factory=servo_factory,
            simulated=simulated,
        )
        self.distance = VL53L0XDistanceAdapter(
            i2c_bus=i2c_config.bus,
            i2c_address=i2c_config.vl53l0x_address,
            sensor_factory=distance_factory,
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
            backend_factory=microphone_factory,
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

    async def start(self) -> None:
        """Initialize shared expression hardware without running a behavior."""
        await self.behaviors.start()

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
        return await self.behaviors.run(definition)

    async def health(self) -> dict[str, str]:
        """Return integrated expression component health."""
        return await self.behaviors.health()

    async def stop(self) -> dict[str, Any]:
        """Perform a non-latching full stop requested by the operator."""
        await self.behaviors.stop()
        return await self.system_safety.full_stop("operator_stop", latch=False)

    def resume_motion(self, *, confirmed: bool) -> SafetySnapshot:
        """Clear an explicitly confirmed Level 1 latch."""
        return self.motion.resume(confirmed=confirmed)

    async def resume_system(self, *, confirmed: bool) -> SafetySnapshot:
        """Clear Level 2 only after every configured device reports ready."""
        return await self.system_safety.resume_system(
            confirmed=confirmed,
            health_checks=(
                self._expression_health,
                self._servo_health,
                self._distance_health,
                self._camera_health,
                self._microphone_health,
            ),
        )

    async def close(self) -> None:
        """Release all assembly-owned devices."""
        await self.behaviors.stop()
        await asyncio.gather(
            self.servo.close(),
            self.distance.close(),
            self.camera.close(),
            self.microphone.close(),
            return_exceptions=True,
        )
        await self.behaviors.close()

    async def _driver_failure(self, error: Exception) -> None:
        if isinstance(error, MotionSafetyError):
            return
        await self.system_safety.full_stop("driver_failure", latch=True)

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

    async def _expression_health(self) -> bool:
        await self.behaviors.start()
        health = await self.behaviors.health()
        return all(value == ResourceHealth.READY.value for value in health.values())

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
