"""Multi-servo group controller with abort support."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable

# Optional ninja_utils integration (fallback to standard logging)
try:
    from ninja_utils import get_module_logger

    logger = get_module_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

from ..motion import EASING_FUNCTIONS, calculate_duration, ease_in_out_cubic
from ..parser import ParsedCommand, ServoTarget, parse_command, resolve_special_angle
from .backend import ServoPulseBackend, create_servo_backend, is_servo_backend
from .endpoint import ServoEndpoint, parse_servo_endpoint
from .servo import Servo, ServoCalibration

# Step interval for motion interpolation (10ms = 100Hz for smoother motion)
STEP_INTERVAL = 0.01


class ServoGroup:
    """Multi-servo controller with synchronized movement and abort support."""

    def __init__(
        self,
        pi: Any | None,
        pins: list[int | str | ServoEndpoint],
        calibrations: dict[int | str, ServoCalibration] | None = None,
        *,
        backend: str | ServoPulseBackend | None = None,
        backend_kwargs: dict[str, Any] | None = None,
        owns_backend: bool | None = None,
    ) -> None:
        """Initialize a ServoGroup.

        Args:
            pi: Legacy pigpio-like instance, a backend object, or None for Pi 5 standalone mode.
            pins: List of GPIO pins or backend identifiers.
            calibrations: Optional dict mapping pin to ServoCalibration.
            backend: Optional backend name or backend object.
            backend_kwargs: Optional backend-specific keyword arguments.
            owns_backend: Override backend ownership for advanced use cases.
        """
        self._pi = pi
        self._endpoints = [parse_servo_endpoint(pin) for pin in pins]
        self._pins = [endpoint.legacy_key for endpoint in self._endpoints]
        self._abort_event = threading.Event()
        self._async_abort_event = asyncio.Event()
        self._backend, self._owns_backend = self._resolve_backend(
            pi,
            self._pins,
            backend,
            backend_kwargs or {},
            owns_backend,
        )

        self._servos: dict[int | str, Servo] = {}
        calibrations = calibrations or {}
        try:
            for pin in self._pins:
                endpoint = parse_servo_endpoint(pin)
                cal = calibrations.get(pin)
                if cal is None:
                    cal = calibrations.get(endpoint.identifier)
                self._servos[pin] = Servo(
                    pi,
                    pin,
                    cal,
                    backend=self._backend,
                    owns_backend=False,
                )
        except Exception:
            for servo in list(self._servos.values()):
                try:
                    servo.close()
                except Exception:
                    pass
            self._servos.clear()
            if self._owns_backend:
                try:
                    self._backend.close()
                except Exception:
                    pass
            raise

    @staticmethod
    def _resolve_backend(
        pi: Any | None,
        pins: list[int | str | ServoEndpoint],
        backend: str | ServoPulseBackend | None,
        backend_kwargs: dict[str, Any],
        owns_backend: bool | None,
    ) -> tuple[ServoPulseBackend, bool]:
        if backend is None and is_servo_backend(pi):
            return pi, bool(owns_backend) if owns_backend is not None else False

        if backend is not None and not isinstance(backend, str):
            return backend, bool(owns_backend) if owns_backend is not None else False

        created_backend = create_servo_backend(
            backend,
            pi=pi,
            pins=pins,
            **backend_kwargs,
        )
        if owns_backend is not None:
            return created_backend, owns_backend
        return created_backend, pi is None or backend is not None

    @property
    def pins(self) -> list[int | str]:
        """List of GPIO pins or endpoint identifiers."""
        return list(self._pins)

    @property
    def servos(self) -> dict[int | str, Servo]:
        """Dictionary of pin or endpoint identifier -> Servo."""
        return self._servos

    @property
    def backend(self) -> ServoPulseBackend:
        """Shared pulse backend for this group."""
        return self._backend

    def get_servo(self, pin: int | str | ServoEndpoint) -> Servo | None:
        """Get a Servo by pin number or endpoint identifier."""
        endpoint = parse_servo_endpoint(pin)
        return self._servos.get(endpoint.legacy_key)

    def update_calibration(
        self, pin: int | str | ServoEndpoint, calibration: ServoCalibration
    ) -> None:
        """Update calibration for a specific servo."""
        servo = self.get_servo(pin)
        if servo is not None:
            servo.calibration = calibration

    def abort(self) -> None:
        """Signal abort for any running movement."""
        logger.info("Abort signal received")
        self._abort_event.set()
        self._async_abort_event.set()

    def _reset_abort(self) -> None:
        """Reset abort events for new movement."""
        self._abort_event.clear()
        self._async_abort_event.clear()

    def _is_aborted(self) -> bool:
        """Check if abort was signaled."""
        return self._abort_event.is_set()

    def _abortable_sleep(self, duration: float) -> bool:
        """Sleep that can be interrupted by abort."""
        if self._abort_event.wait(timeout=duration):
            logger.info("Sleep aborted after partial wait")
            return False
        return True

    async def _abortable_sleep_async(self, duration: float) -> bool:
        """Async sleep that can be interrupted by abort."""
        try:
            await asyncio.wait_for(self._async_abort_event.wait(), timeout=duration)
            logger.info("Async sleep aborted")
            return False
        except asyncio.TimeoutError:
            return True

    def move_all_sync(
        self,
        targets: list[float | None],
        speed_mode: str | list[str] = "M",
        easing: str | Callable[[float], float] = "ease_in_out_cubic",
        force: bool = False,
    ) -> bool:
        """Move all servos to target angles with per-servo speed control."""
        self._reset_abort()

        easing_fn = (
            EASING_FUNCTIONS.get(easing, ease_in_out_cubic) if isinstance(easing, str) else easing
        )
        speed_modes = [speed_mode] * len(self._pins) if isinstance(speed_mode, str) else speed_mode

        movements: list[tuple[Servo, float, float, float]] = []
        max_duration = 0.0

        for i, pin in enumerate(self._pins):
            if i >= len(targets) or targets[i] is None:
                continue

            servo = self._servos[pin]
            target = targets[i]

            current = servo.last_angle
            if current is None:
                current = servo.get_angle()
            if current is None:
                current = servo.calibration.angle_center

            distance = abs(target - current)
            if distance < 0.1 and not force:
                logger.debug(
                    "Skip GPIO%s: target=%.1f° current=%.1f° distance=%.3f° (< 0.1° threshold)",
                    pin,
                    target,
                    current,
                    distance,
                )
                continue

            servo_speed_mode = speed_modes[i] if i < len(speed_modes) else "M"
            duration = calculate_duration(distance, servo.speed_limit, servo_speed_mode)
            max_duration = max(max_duration, duration)
            movements.append((servo, current, target, duration))

        if not movements:
            logger.debug("No movement required")
            return True

        logger.info("Moving %s servos, max_duration=%.2fs", len(movements), max_duration)
        start_time = time.monotonic()

        while True:
            if self._is_aborted():
                logger.info("Movement aborted")
                return False

            elapsed = time.monotonic() - start_time
            if elapsed >= max_duration:
                break

            for servo, start, end, duration in movements:
                if duration <= 0:
                    servo.set_angle(end)
                    continue

                t = min(1.0, elapsed / duration)
                eased_t = easing_fn(t)
                angle = start + (end - start) * eased_t
                servo.set_angle(angle)

            if not self._abortable_sleep(STEP_INTERVAL):
                return False

        for servo, start, end, duration in movements:
            del start, duration
            servo.set_angle(end)

        logger.debug("Movement completed successfully")
        return True

    async def move_all_async(
        self,
        targets: list[float | None],
        speed_mode: str | list[str] = "M",
        easing: str | Callable[[float], float] = "ease_in_out_cubic",
    ) -> bool:
        """Async version of move_all_sync with per-servo speed control."""
        self._reset_abort()

        easing_fn = (
            EASING_FUNCTIONS.get(easing, ease_in_out_cubic) if isinstance(easing, str) else easing
        )
        speed_modes = [speed_mode] * len(self._pins) if isinstance(speed_mode, str) else speed_mode

        movements: list[tuple[Servo, float, float, float]] = []
        max_duration = 0.0

        for i, pin in enumerate(self._pins):
            if i >= len(targets) or targets[i] is None:
                continue

            servo = self._servos[pin]
            target = targets[i]

            current = servo.last_angle
            if current is None:
                current = servo.get_angle()
            if current is None:
                current = servo.calibration.angle_center

            distance = abs(target - current)
            if distance < 0.1:
                continue

            servo_speed_mode = speed_modes[i] if i < len(speed_modes) else "M"
            duration = calculate_duration(distance, servo.speed_limit, servo_speed_mode)
            max_duration = max(max_duration, duration)
            movements.append((servo, current, target, duration))

        if not movements:
            return True

        start_time = time.monotonic()

        while True:
            if self._async_abort_event.is_set():
                return False

            elapsed = time.monotonic() - start_time
            if elapsed >= max_duration:
                break

            for servo, start, end, duration in movements:
                if duration <= 0:
                    servo.set_angle(end)
                    continue

                t = min(1.0, elapsed / duration)
                eased_t = easing_fn(t)
                angle = start + (end - start) * eased_t
                servo.set_angle(angle)

            if not await self._abortable_sleep_async(STEP_INTERVAL):
                return False

        for servo, start, end, duration in movements:
            del start, duration
            servo.set_angle(end)

        return True

    def execute_command(
        self,
        command: str,
        easing: str | Callable[[float], float] = "ease_in_out_cubic",
        *,
        force: bool = False,
    ) -> bool:
        """Execute a movement-tool format command string."""
        parsed = parse_command(command)
        return self._execute_parsed(parsed, easing, force=force)

    async def execute_command_async(
        self,
        command: str,
        easing: str | Callable[[float], float] = "ease_in_out_cubic",
    ) -> bool:
        """Async version of execute_command."""
        parsed = parse_command(command)
        return await self._execute_parsed_async(parsed, easing)

    def _execute_parsed(
        self,
        parsed: ParsedCommand,
        easing: str | Callable[[float], float],
        *,
        force: bool = False,
    ) -> bool:
        """Execute a parsed command with per-target speed support."""
        targets, speed_modes = self._resolve_targets(parsed.targets, parsed.speed_mode)
        return self.move_all_sync(targets, speed_modes, easing, force=force)

    async def _execute_parsed_async(
        self,
        parsed: ParsedCommand,
        easing: str | Callable[[float], float],
    ) -> bool:
        """Async execution of a parsed command."""
        targets, speed_modes = self._resolve_targets(parsed.targets, parsed.speed_mode)
        return await self.move_all_async(targets, speed_modes, easing)

    def _resolve_targets(
        self,
        targets: list[ServoTarget],
        global_speed: str = "M",
    ) -> tuple[list[float | None], list[str]]:
        """Convert ServoTargets to angle and speed lists indexed by pin order."""
        result: list[float | None] = [None] * len(self._pins)
        speeds: list[str] = [global_speed] * len(self._pins)

        for target in targets:
            if target.pin not in self._servos:
                logger.warning("Unknown pin in command: %s", target.pin)
                continue

            pin_index = self._pins.index(target.pin)
            servo = self._servos[target.pin]

            if target.angle is not None:
                result[pin_index] = target.angle
            elif target.special:
                cal_dict = {
                    "angle_center": servo.calibration.angle_center,
                    "angle_min": servo.calibration.angle_min,
                    "angle_max": servo.calibration.angle_max,
                }
                result[pin_index] = resolve_special_angle(target.special, cal_dict)

            if target.speed:
                speeds[pin_index] = target.speed

        return result, speeds

    def initialize(self) -> None:
        """Initialize all servos (Actuator interface)."""
        logger.info("ServoGroup initialized with pins: %s", self._pins)

    def execute(self, command: str) -> dict[str, Any]:
        """Execute a command (Actuator interface)."""
        try:
            success = self.execute_command(command)
            return {
                "success": success,
                "message": "Completed" if success else "Aborted",
            }
        except ValueError as exc:
            return {"success": False, "message": str(exc)}

    def off(self) -> None:
        """Turn off all servos."""
        for servo in self._servos.values():
            servo.off()
        logger.info("All servos turned off")

    def refresh_all(self) -> None:
        """Re-send PWM to all servos with known positions."""
        count = 0
        for servo in self._servos.values():
            if servo.refresh():
                count += 1
        if count > 0:
            logger.info("Refreshed PWM on %s servos", count)

    def ensure_all_active(self) -> None:
        """Check and restore PWM on all servos if needed."""
        restored = 0
        for servo in self._servos.values():
            current_pulse = servo.get_pulse()
            if current_pulse == 0 and servo.last_angle is not None:
                servo.refresh()
                restored += 1
        if restored > 0:
            logger.info("Restored PWM on %s limp servos", restored)

    def center_all(self) -> None:
        """Move all servos to their calibrated center position."""
        for servo in self._servos.values():
            servo.move_to_center()

    def move_all_angles_sync(
        self,
        target_angles: list[float | None],
        move_sec: float = 0.5,
        step_n: int = 40,
    ) -> bool:
        """Legacy wrapper for ninja_core compatibility."""
        del step_n
        if move_sec <= 0.2:
            speed_mode = "F"
        elif move_sec <= 0.5:
            speed_mode = "M"
        else:
            speed_mode = "S"

        return self.move_all_sync(target_angles, speed_mode=speed_mode)

    def move_all_angles(self, target_angles: list[float | None]) -> None:
        """Legacy compatibility: instant movement without interpolation."""
        for i, pin in enumerate(self._pins):
            if i < len(target_angles) and target_angles[i] is not None:
                self._servos[pin].set_angle(target_angles[i])

    def get_all_angles(self) -> list[float]:
        """Legacy compatibility: get all angles as ordered list."""
        return [self._servos[pin].last_angle or 0.0 for pin in self._pins]

    @property
    def servo(self) -> list[Servo]:
        """Legacy compatibility: list access ordered by pin."""
        return [self._servos[pin] for pin in self._pins]

    def close(self) -> None:
        """Release the group's backend resources."""
        if self._owns_backend:
            self._backend.close()
            return

        for pin in self._pins:
            self._backend.release(pin)

    def __enter__(self) -> ServoGroup:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        self.close()
