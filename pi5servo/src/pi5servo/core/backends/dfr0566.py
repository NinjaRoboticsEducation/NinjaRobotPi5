"""DFRobot DFR0566 PWM backend for servo channels 1..4 over I2C."""

from __future__ import annotations

import time
from importlib import import_module
from typing import Any

from ..backend_errors import BackendConfigurationError, BackendUnavailableError
from ..endpoint import parse_servo_endpoint

DEFAULT_DFR0566_ADDRESS = 0x10
DEFAULT_DFR0566_BUS_ID = 1
DEFAULT_DFR0566_FREQUENCY_HZ = 50
DFR0566_PWM_CHANNELS = range(1, 5)

_REG_PID = 0x01
_REG_VID = 0x02
_REG_PWM_CONTROL = 0x03
_REG_PWM_FREQ = 0x04
_REG_PWM_DUTY1 = 0x06

_EXPECTED_PID = 0xDF
_EXPECTED_VID = 0x10
_COMMAND_SETTLE_SECONDS = 0.01


class DFR0566ServoBackend:
    """Servo backend that drives the DFR0566 HAT PWM channels over I2C."""

    def __init__(
        self,
        *,
        address: int = DEFAULT_DFR0566_ADDRESS,
        bus_id: int = DEFAULT_DFR0566_BUS_ID,
        frequency_hz: int = DEFAULT_DFR0566_FREQUENCY_HZ,
        channel_map: dict[int, int] | None = None,
        i2c_bus: Any | None = None,
        smbus_cls: type[Any] | None = None,
    ) -> None:
        self._address = int(address)
        self._bus_id = int(bus_id)
        self._frequency_hz = int(frequency_hz)
        self._channel_map = dict(channel_map or {})
        self._claimed: set[int | str] = set()
        self._current_pulses: dict[int | str, int] = {}
        self._pwm_enabled = False
        self._owns_bus = i2c_bus is None

        if i2c_bus is None:
            if smbus_cls is None:
                try:
                    smbus_module = import_module("smbus2")
                    smbus_cls = smbus_module.SMBus
                except ImportError as exc:
                    raise BackendUnavailableError(
                        "DFR0566 backend requires smbus2. Install the `pi` extra."
                    ) from exc
            i2c_bus = smbus_cls(self._bus_id)

        self._bus = i2c_bus
        self._begin()

    def _begin(self) -> None:
        pid = self._read_bytes(_REG_PID, 1)[0]
        vid = self._read_bytes(_REG_VID, 1)[0]
        if pid != _EXPECTED_PID or vid != _EXPECTED_VID:
            raise BackendUnavailableError(
                "DFR0566 board was not detected at the requested address."
            )
        self._write_pwm_enable(False)
        self._write_frequency(self._frequency_hz)
        self._write_all_duty(0.0)

    def _resolve_channel(self, identifier: int | str) -> int:
        endpoint = parse_servo_endpoint(identifier)
        if endpoint.kind == "hat_pwm":
            channel = endpoint.value
        else:
            channel = self._channel_map.get(endpoint.legacy_pin, endpoint.legacy_pin)
        if channel in DFR0566_PWM_CHANNELS:
            return channel
        raise BackendConfigurationError(
            f"Identifier {identifier} does not map to a valid DFR0566 PWM channel (1..4)."
        )

    def _write_bytes(self, register: int, payload: list[int]) -> None:
        try:
            self._bus.write_i2c_block_data(self._address, register, payload)
        except OSError as exc:
            raise BackendUnavailableError(
                f"Failed to write to DFR0566 at address 0x{self._address:02x}."
            ) from exc

    def _read_bytes(self, register: int, length: int) -> list[int]:
        try:
            return list(self._bus.read_i2c_block_data(self._address, register, length))
        except OSError as exc:
            raise BackendUnavailableError(
                f"Failed to read from DFR0566 at address 0x{self._address:02x}."
            ) from exc

    def _write_pwm_enable(self, enabled: bool) -> None:
        self._write_bytes(_REG_PWM_CONTROL, [0x01 if enabled else 0x00])
        self._pwm_enabled = enabled
        time.sleep(_COMMAND_SETTLE_SECONDS)

    def _write_frequency(self, frequency_hz: int) -> None:
        if not 1 <= frequency_hz <= 1000:
            raise BackendConfigurationError("DFR0566 frequency must be in the range 1..1000Hz.")
        was_enabled = self._pwm_enabled
        if was_enabled:
            self._write_pwm_enable(False)
        self._write_bytes(_REG_PWM_FREQ, [(frequency_hz >> 8) & 0xFF, frequency_hz & 0xFF])
        time.sleep(_COMMAND_SETTLE_SECONDS)
        if was_enabled:
            self._write_pwm_enable(True)

    def _write_channel_duty(self, channel: int, duty_percent: float) -> None:
        duty_percent = max(0.0, min(100.0, duty_percent))
        duty_tenths = int(round(duty_percent * 10))
        register = _REG_PWM_DUTY1 + (channel - 1) * 2
        self._write_bytes(register, [duty_tenths // 10, duty_tenths % 10])

    def _write_all_duty(self, duty_percent: float) -> None:
        for channel in DFR0566_PWM_CHANNELS:
            self._write_channel_duty(channel, duty_percent)

    def _period_us(self) -> float:
        return 1_000_000.0 / float(self._frequency_hz)

    def _pulse_to_duty_cycle(self, pulse_width_us: int) -> float:
        pulse_width_us = max(0, pulse_width_us)
        return (pulse_width_us / self._period_us()) * 100.0

    def claim(self, identifier: int | str) -> None:
        endpoint = parse_servo_endpoint(identifier)
        claim_key = endpoint.legacy_key
        self._resolve_channel(identifier)
        self._claimed.add(claim_key)
        self._current_pulses.setdefault(claim_key, 0)

    def set_pulse_us(self, identifier: int | str, pulse_width_us: int) -> None:
        if pulse_width_us <= 0:
            self.off(identifier)
            return

        self.claim(identifier)
        if not self._pwm_enabled:
            self._write_pwm_enable(True)

        channel = self._resolve_channel(identifier)
        self._write_channel_duty(channel, self._pulse_to_duty_cycle(int(pulse_width_us)))
        self._current_pulses[parse_servo_endpoint(identifier).legacy_key] = int(pulse_width_us)

    def get_pulse_us(self, identifier: int | str) -> int:
        return int(self._current_pulses.get(parse_servo_endpoint(identifier).legacy_key, 0))

    def off(self, identifier: int | str) -> None:
        self.claim(identifier)
        channel = self._resolve_channel(identifier)
        self._write_channel_duty(channel, 0.0)
        self._current_pulses[parse_servo_endpoint(identifier).legacy_key] = 0

    def release(self, identifier: int | str) -> None:
        claim_key = parse_servo_endpoint(identifier).legacy_key
        if claim_key not in self._claimed:
            return
        self.off(identifier)
        self._claimed.discard(claim_key)
        self._current_pulses.pop(claim_key, None)

    def close(self) -> None:
        for identifier in list(self._claimed):
            self.release(identifier)
        if self._pwm_enabled:
            self._write_pwm_enable(False)
        if self._owns_bus and hasattr(self._bus, "close"):
            self._bus.close()
