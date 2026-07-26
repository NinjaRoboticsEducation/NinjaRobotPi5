"""Single servo control with calibration support and pluggable backends.

This module provides the Servo class which handles:
- hardware-backed pulse output through a backend abstraction
- angle-to-pulse conversion with calibration
- per-servo speed limits (0-100)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .backend import ServoPulseBackend, create_servo_backend, is_servo_backend
from .endpoint import ServoEndpoint, parse_servo_endpoint

# Default pulse width constants (microseconds)
# SAFE DEFAULTS: All set to center (1500) to prevent unexpected movement
# on uncalibrated servos. Users MUST calibrate before use.
PULSE_MIN = 1500
PULSE_MAX = 1500
PULSE_CENTER = 1500

# Default angle range
ANGLE_MIN = -90.0
ANGLE_MAX = 90.0
ANGLE_CENTER = 0.0

# Default speed limit (0-100%)
DEFAULT_SPEED_LIMIT = 80


@dataclass
class ServoCalibration:
    """Calibration data for a single servo."""

    pulse_min: int = PULSE_MIN
    pulse_max: int = PULSE_MAX
    pulse_center: int = PULSE_CENTER
    angle_min: float = ANGLE_MIN
    angle_max: float = ANGLE_MAX
    angle_center: float = ANGLE_CENTER
    speed: int = DEFAULT_SPEED_LIMIT


class Servo:
    """Single servo controller with calibration."""

    def __init__(
        self,
        pi: Any | None,
        pin: int | str | ServoEndpoint,
        calibration: ServoCalibration | None = None,
        *,
        backend: str | ServoPulseBackend | None = None,
        backend_kwargs: dict[str, Any] | None = None,
        owns_backend: bool | None = None,
    ) -> None:
        """Initialize a Servo.

        Args:
            pi: Legacy pigpio-like instance, a backend object, or None for Pi 5 standalone mode.
            pin: GPIO pin number, explicit endpoint identifier, or backend identifier.
            calibration: Optional ServoCalibration, uses defaults if None.
            backend: Optional backend name or backend object. Defaults to pigpio compatibility
                when ``pi`` is provided, otherwise the Pi 5 auto backend.
            backend_kwargs: Optional backend-specific keyword arguments.
            owns_backend: Override backend ownership for advanced use cases.
        """
        self._pi = pi
        self._endpoint = parse_servo_endpoint(pin)
        self._pin = self._endpoint.legacy_key
        self._calibration = calibration or ServoCalibration()
        self._last_angle: float | None = None

        self._backend, self._owns_backend = self._resolve_backend(
            pi,
            self._pin,
            backend,
            backend_kwargs or {},
            owns_backend,
        )
        self._backend.claim(self._pin)

    @staticmethod
    def _resolve_backend(
        pi: Any | None,
        pin: int | str | ServoEndpoint,
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
            pins=[pin],
            **backend_kwargs,
        )
        if owns_backend is not None:
            return created_backend, owns_backend
        return created_backend, pi is None or backend is not None

    @property
    def pin(self) -> int | str:
        """GPIO pin number or endpoint identifier."""
        return self._pin

    @property
    def endpoint(self) -> ServoEndpoint:
        """Normalized endpoint metadata."""
        return self._endpoint

    @property
    def calibration(self) -> ServoCalibration:
        """Current calibration data."""
        return self._calibration

    @calibration.setter
    def calibration(self, value: ServoCalibration) -> None:
        """Update calibration."""
        self._calibration = value

    @property
    def backend(self) -> ServoPulseBackend:
        """Active pulse backend."""
        return self._backend

    @property
    def speed_limit(self) -> int:
        """Per-servo speed limit (0-100)."""
        return self._calibration.speed

    @speed_limit.setter
    def speed_limit(self, value: int) -> None:
        """Set per-servo speed limit (clamped to 0-100)."""
        self._calibration.speed = max(0, min(100, int(value)))

    @property
    def last_angle(self) -> float | None:
        """Last known angle, or None if not set."""
        return self._last_angle

    def angle_to_pulse(self, angle: float) -> int:
        """Convert angle in degrees to pulse width in microseconds."""
        cal = self._calibration
        angle = max(cal.angle_min, min(cal.angle_max, angle))

        if angle >= cal.angle_center:
            divisor = cal.angle_max - cal.angle_center
            if divisor == 0:
                pulse = cal.pulse_center
            else:
                t = (angle - cal.angle_center) / divisor
                pulse = cal.pulse_center + t * (cal.pulse_max - cal.pulse_center)
        else:
            divisor = cal.angle_center - cal.angle_min
            if divisor == 0:
                pulse = cal.pulse_center
            else:
                t = (angle - cal.angle_min) / divisor
                pulse = cal.pulse_min + t * (cal.pulse_center - cal.pulse_min)

        return int(pulse)

    def pulse_to_angle(self, pulse: int) -> float:
        """Convert pulse width in microseconds to angle in degrees."""
        cal = self._calibration
        pulse = max(cal.pulse_min, min(cal.pulse_max, pulse))

        if pulse >= cal.pulse_center:
            divisor = cal.pulse_max - cal.pulse_center
            if divisor == 0:
                angle = cal.angle_center
            else:
                t = (pulse - cal.pulse_center) / divisor
                angle = cal.angle_center + t * (cal.angle_max - cal.angle_center)
        else:
            divisor = cal.pulse_center - cal.pulse_min
            if divisor == 0:
                angle = cal.angle_center
            else:
                t = (pulse - cal.pulse_min) / divisor
                angle = cal.angle_min + t * (cal.angle_center - cal.angle_min)

        return angle

    def get_pulse(self) -> int:
        """Get the current pulse width from the active backend."""
        try:
            return int(self._backend.get_pulse_us(self._pin))
        except Exception:
            return 0

    def get_angle(self) -> float | None:
        """Get current angle if servo is active."""
        pulse = self.get_pulse()
        if pulse == 0:
            return None
        return self.pulse_to_angle(pulse)

    def set_pulse(self, pulse: int) -> None:
        """Set servo to a specific pulse width."""
        pulse = int(pulse)
        self._backend.set_pulse_us(self._pin, pulse)
        if pulse > 0:
            self._last_angle = self.pulse_to_angle(pulse)

    def set_angle(self, angle: float) -> None:
        """Set servo to a specific angle."""
        pulse = self.angle_to_pulse(angle)
        self.set_pulse(pulse)
        self._last_angle = angle

    def move_to_center(self) -> None:
        """Move servo to calibrated center position."""
        self.set_angle(self._calibration.angle_center)

    def move_to_min(self) -> None:
        """Move servo to calibrated minimum position."""
        self.set_angle(self._calibration.angle_min)

    def move_to_max(self) -> None:
        """Move servo to calibrated maximum position."""
        self.set_angle(self._calibration.angle_max)

    def off(self) -> None:
        """Turn off servo PWM signal."""
        self._backend.off(self._pin)

    def refresh(self) -> bool:
        """Re-send the last known PWM to ensure the signal is active."""
        if self._last_angle is not None:
            self.set_pulse(self.angle_to_pulse(self._last_angle))
            return True
        return False

    def ensure_active(self) -> bool:
        """Check if PWM is active and refresh if needed."""
        current_pulse = self.get_pulse()
        if current_pulse == 0 and self._last_angle is not None:
            self.refresh()
            return True
        return current_pulse > 0

    def close(self) -> None:
        """Release this servo output from the backend."""
        if self._owns_backend:
            self._backend.close()
        else:
            self._backend.release(self._pin)

    def __enter__(self) -> Servo:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        self.close()
