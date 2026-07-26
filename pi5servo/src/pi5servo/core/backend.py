"""Servo pulse backend abstractions for Raspberry Pi 5."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .backend_errors import (
    BackendConfigurationError,
    BackendError,
    BackendUnavailableError,
)
from .backends.dfr0566 import DFR0566ServoBackend
from .backends.hardware_pwm import HardwarePWMServoBackend
from .backends.pca9685 import PCA9685ServoBackend
from .backends.pwm_pio import PwmPioServoBackend
from .endpoint import ServoEndpoint, parse_servo_endpoint

HARDWARE_PWM_BACKEND_KWARGS = {"pin_channel_map", "frequency_hz", "chip", "pwm_cls"}
DFR0566_BACKEND_KWARGS = {
    "address",
    "bus_id",
    "frequency_hz",
    "channel_map",
    "i2c_bus",
    "smbus_cls",
}
PCA9685_BACKEND_KWARGS = {
    "address",
    "frequency_hz",
    "reference_clock_speed",
    "channel_map",
    "i2c_bus",
    "pca9685_cls",
}
PIGPIO_BACKEND_KWARGS = {"owns_pi"}
PWM_PIO_BACKEND_KWARGS: set[str] = set()


@runtime_checkable
class ServoPulseBackend(Protocol):
    """Interface for long-lived servo pulse generators."""

    def claim(self, identifier: int | str | ServoEndpoint) -> None:
        """Claim a servo output once for long-lived use."""

    def set_pulse_us(self, identifier: int | str | ServoEndpoint, pulse_width_us: int) -> None:
        """Set the output pulse width in microseconds."""

    def get_pulse_us(self, identifier: int | str | ServoEndpoint) -> int:
        """Return the last known pulse width in microseconds."""

    def off(self, identifier: int | str | ServoEndpoint) -> None:
        """Turn the servo output off for one identifier."""

    def release(self, identifier: int | str | ServoEndpoint) -> None:
        """Release one claimed output."""

    def close(self) -> None:
        """Release all claimed outputs."""


class PigpioServoBackend:
    """Thin compatibility wrapper around a pigpio-like servo API."""

    def __init__(self, pi: Any, *, owns_pi: bool = False) -> None:
        self._pi = pi
        self._owns_pi = owns_pi
        self._claimed: set[int] = set()
        self._closed = False

    @staticmethod
    def _normalize_identifier(identifier: int | str | ServoEndpoint) -> int:
        endpoint = parse_servo_endpoint(identifier)
        if endpoint.kind != "gpio":
            raise BackendConfigurationError("pigpio backend only supports native GPIO endpoints.")
        return endpoint.legacy_pin

    def claim(self, identifier: int | str | ServoEndpoint) -> None:
        identifier = self._normalize_identifier(identifier)
        self._claimed.add(identifier)

    def set_pulse_us(self, identifier: int | str | ServoEndpoint, pulse_width_us: int) -> None:
        identifier = self._normalize_identifier(identifier)
        self.claim(identifier)
        self._pi.set_servo_pulsewidth(identifier, pulse_width_us)

    def get_pulse_us(self, identifier: int | str | ServoEndpoint) -> int:
        identifier = self._normalize_identifier(identifier)
        try:
            return int(self._pi.get_servo_pulsewidth(identifier))
        except Exception:
            return 0

    def off(self, identifier: int | str | ServoEndpoint) -> None:
        identifier = self._normalize_identifier(identifier)
        self._pi.set_servo_pulsewidth(identifier, 0)

    def release(self, identifier: int | str | ServoEndpoint) -> None:
        identifier = self._normalize_identifier(identifier)
        if identifier in self._claimed:
            self.off(identifier)
            self._claimed.discard(identifier)

    def close(self) -> None:
        if self._closed:
            return
        for identifier in list(self._claimed):
            self.release(identifier)
        if self._owns_pi and hasattr(self._pi, "stop"):
            self._pi.stop()
        self._closed = True


def is_servo_backend(candidate: Any | None) -> bool:
    """Return True when a value looks like a servo pulse backend.

    Pigpio-like objects expose ``set_servo_pulsewidth`` / ``get_servo_pulsewidth`` and should
    stay on the legacy compatibility path even if they are mocks.
    """
    if candidate is None or isinstance(candidate, str):
        return False

    if callable(getattr(candidate, "set_servo_pulsewidth", None)):
        return False

    required = (
        "claim",
        "set_pulse_us",
        "get_pulse_us",
        "off",
        "release",
        "close",
    )
    return all(callable(getattr(candidate, name, None)) for name in required)


def _filter_backend_kwargs(kwargs: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    """Keep only kwargs accepted by a specific backend constructor."""
    return {key: value for key, value in kwargs.items() if key in allowed}


class MixedServoBackend:
    """Route servo endpoints to multiple backend instances."""

    def __init__(
        self,
        routes: dict[str, tuple[ServoPulseBackend, int | str]],
        *,
        owned_backends: list[ServoPulseBackend],
    ) -> None:
        self._routes = dict(routes)
        self._owned_backends = list(dict.fromkeys(owned_backends))

    def _resolve_route(
        self, identifier: int | str | ServoEndpoint
    ) -> tuple[ServoPulseBackend, int | str]:
        endpoint = parse_servo_endpoint(identifier)
        try:
            return self._routes[endpoint.identifier]
        except KeyError as exc:
            raise BackendConfigurationError(
                f"No backend route configured for servo endpoint {endpoint.identifier}."
            ) from exc

    def claim(self, identifier: int | str | ServoEndpoint) -> None:
        backend, backend_identifier = self._resolve_route(identifier)
        backend.claim(backend_identifier)

    def set_pulse_us(self, identifier: int | str | ServoEndpoint, pulse_width_us: int) -> None:
        backend, backend_identifier = self._resolve_route(identifier)
        backend.set_pulse_us(backend_identifier, pulse_width_us)

    def get_pulse_us(self, identifier: int | str | ServoEndpoint) -> int:
        backend, backend_identifier = self._resolve_route(identifier)
        return backend.get_pulse_us(backend_identifier)

    def off(self, identifier: int | str | ServoEndpoint) -> None:
        backend, backend_identifier = self._resolve_route(identifier)
        backend.off(backend_identifier)

    def release(self, identifier: int | str | ServoEndpoint) -> None:
        backend, backend_identifier = self._resolve_route(identifier)
        backend.release(backend_identifier)

    def close(self) -> None:
        for backend in self._owned_backends:
            backend.close()


def _create_auto_backend(
    pins: list[int | str | ServoEndpoint],
    kwargs: dict[str, Any],
) -> ServoPulseBackend:
    normalized_pins = [parse_servo_endpoint(pin) for pin in pins]
    gpio_endpoints = [endpoint for endpoint in normalized_pins if endpoint.kind == "gpio"]
    hat_endpoints = [endpoint for endpoint in normalized_pins if endpoint.kind == "hat_pwm"]

    if gpio_endpoints and hat_endpoints:
        gpio_backend = HardwarePWMServoBackend(
            pins=[endpoint.legacy_pin for endpoint in gpio_endpoints],
            **_filter_backend_kwargs(kwargs, HARDWARE_PWM_BACKEND_KWARGS),
        )
        hat_backend = DFR0566ServoBackend(**_filter_backend_kwargs(kwargs, DFR0566_BACKEND_KWARGS))
        routes: dict[str, tuple[ServoPulseBackend, int | str]] = {
            endpoint.identifier: (gpio_backend, endpoint.legacy_pin) for endpoint in gpio_endpoints
        }
        routes.update(
            {endpoint.identifier: (hat_backend, endpoint.identifier) for endpoint in hat_endpoints}
        )
        return MixedServoBackend(routes, owned_backends=[gpio_backend, hat_backend])

    if hat_endpoints:
        return DFR0566ServoBackend(**_filter_backend_kwargs(kwargs, DFR0566_BACKEND_KWARGS))

    return HardwarePWMServoBackend(
        pins=[endpoint.legacy_pin for endpoint in gpio_endpoints],
        **_filter_backend_kwargs(kwargs, HARDWARE_PWM_BACKEND_KWARGS),
    )


def create_servo_backend(
    backend: str | ServoPulseBackend | None = None,
    *,
    pi: Any | None = None,
    pins: list[int | str | ServoEndpoint] | None = None,
    **kwargs: Any,
) -> ServoPulseBackend:
    """Create a servo backend from a name, a backend object, or a pigpio-like pi."""
    if backend is not None and not isinstance(backend, str):
        return backend

    backend_name = (backend or ("pigpio" if pi is not None else "auto")).lower()
    pins = list(pins or [])

    if backend_name in {"pigpio", "legacy"}:
        if pi is None:
            raise BackendConfigurationError("pigpio backend requires a `pi` instance.")
        return PigpioServoBackend(
            pi,
            owns_pi=_filter_backend_kwargs(kwargs, PIGPIO_BACKEND_KWARGS).get("owns_pi", False),
        )

    if backend_name in {"auto", "hardware_pwm", "rp1_hardware_pwm"}:
        if backend_name == "auto":
            return _create_auto_backend(pins, kwargs)
        return HardwarePWMServoBackend(
            pins=pins,
            **_filter_backend_kwargs(kwargs, HARDWARE_PWM_BACKEND_KWARGS),
        )

    if backend_name == "pwm_pio":
        return PwmPioServoBackend(
            pins=pins,
            **_filter_backend_kwargs(kwargs, PWM_PIO_BACKEND_KWARGS),
        )

    if backend_name == "pca9685":
        return PCA9685ServoBackend(**_filter_backend_kwargs(kwargs, PCA9685_BACKEND_KWARGS))

    if backend_name == "dfr0566":
        return DFR0566ServoBackend(**_filter_backend_kwargs(kwargs, DFR0566_BACKEND_KWARGS))

    raise BackendConfigurationError(f"Unknown servo backend: {backend_name}")


__all__ = [
    "BackendConfigurationError",
    "BackendError",
    "BackendUnavailableError",
    "MixedServoBackend",
    "PigpioServoBackend",
    "ServoPulseBackend",
    "create_servo_backend",
    "is_servo_backend",
]
