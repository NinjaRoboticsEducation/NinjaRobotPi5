"""Optional PCA9685 backend for advanced external PWM control."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ..backend_errors import BackendConfigurationError, BackendUnavailableError
from ..endpoint import parse_servo_endpoint

DEFAULT_PCA9685_ADDRESS = 0x40
DEFAULT_PCA9685_FREQUENCY_HZ = 50
DEFAULT_REFERENCE_CLOCK_SPEED = 25_000_000


class PCA9685ServoBackend:
    """Servo backend that offloads pulse generation to a PCA9685 controller."""

    def __init__(
        self,
        *,
        address: int = DEFAULT_PCA9685_ADDRESS,
        frequency_hz: int = DEFAULT_PCA9685_FREQUENCY_HZ,
        reference_clock_speed: int = DEFAULT_REFERENCE_CLOCK_SPEED,
        channel_map: dict[int, int] | None = None,
        i2c_bus: Any | None = None,
        pca9685_cls: type[Any] | None = None,
    ) -> None:
        if pca9685_cls is None:
            try:
                board = import_module("board")
                busio = import_module("busio")
                pca9685_module = import_module("adafruit_pca9685")
                pca9685_cls = pca9685_module.PCA9685
            except ImportError as exc:
                raise BackendUnavailableError(
                    "PCA9685 backend requires adafruit-blinka and adafruit-circuitpython-pca9685."
                ) from exc

            if i2c_bus is None:
                i2c_bus = busio.I2C(board.SCL, board.SDA)

        kwargs = {
            "address": int(address),
            "reference_clock_speed": int(reference_clock_speed),
        }
        self._controller = pca9685_cls(i2c_bus, **kwargs)
        self._controller.frequency = int(frequency_hz)
        self._frequency_hz = int(frequency_hz)
        self._channel_map = dict(channel_map or {})
        self._current_pulses: dict[int, int] = {}
        self._claimed: set[int] = set()

    def _period_us(self) -> float:
        return 1_000_000.0 / float(self._frequency_hz)

    def _normalize_identifier(self, identifier: int | str) -> int:
        endpoint = parse_servo_endpoint(identifier)
        if endpoint.kind != "gpio":
            raise BackendConfigurationError(
                "PCA9685 routing currently supports native GPIO identifiers only."
            )
        return endpoint.legacy_pin

    def _resolve_channel(self, identifier: int | str) -> int:
        identifier = self._normalize_identifier(identifier)
        channel = self._channel_map.get(identifier, identifier)
        if 0 <= channel <= 15:
            return channel
        raise BackendConfigurationError(
            f"Identifier {identifier} does not map to a valid PCA9685 channel."
        )

    def _pulse_to_duty_cycle(self, pulse_width_us: int) -> int:
        pulse_width_us = max(0, pulse_width_us)
        duty = int((pulse_width_us / self._period_us()) * 0xFFFF)
        return max(0, min(0xFFFF, duty))

    def claim(self, identifier: int | str) -> None:
        identifier = self._normalize_identifier(identifier)
        self._resolve_channel(identifier)
        self._claimed.add(identifier)
        self._current_pulses.setdefault(identifier, 0)

    def set_pulse_us(self, identifier: int | str, pulse_width_us: int) -> None:
        identifier = self._normalize_identifier(identifier)
        if pulse_width_us <= 0:
            self.off(identifier)
            return
        self.claim(identifier)
        channel = self._resolve_channel(identifier)
        self._controller.channels[channel].duty_cycle = self._pulse_to_duty_cycle(
            int(pulse_width_us)
        )
        self._current_pulses[identifier] = int(pulse_width_us)

    def get_pulse_us(self, identifier: int | str) -> int:
        identifier = self._normalize_identifier(identifier)
        return int(self._current_pulses.get(identifier, 0))

    def off(self, identifier: int | str) -> None:
        identifier = self._normalize_identifier(identifier)
        self.claim(identifier)
        channel = self._resolve_channel(identifier)
        self._controller.channels[channel].duty_cycle = 0
        self._current_pulses[identifier] = 0

    def release(self, identifier: int | str) -> None:
        identifier = self._normalize_identifier(identifier)
        if identifier not in self._claimed:
            return
        self.off(identifier)
        self._claimed.discard(identifier)
        self._current_pulses.pop(identifier, None)

    def close(self) -> None:
        for identifier in list(self._claimed):
            self.release(identifier)
        if hasattr(self._controller, "deinit"):
            self._controller.deinit()
