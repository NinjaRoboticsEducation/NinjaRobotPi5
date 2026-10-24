"""PCA9685 16-channel I2C PWM backend for servo control."""

from __future__ import annotations

import time
from importlib import import_module
from typing import Any

from ..backend_errors import BackendConfigurationError, BackendUnavailableError
from ..endpoint import ServoEndpoint, parse_servo_endpoint

DEFAULT_PCA9685_ADDRESS = 0x40
DEFAULT_PCA9685_BUS_ID = 1
DEFAULT_PCA9685_FREQUENCY_HZ = 50
DEFAULT_REFERENCE_CLOCK_SPEED = 25_000_000
PCA9685_PWM_CHANNELS = range(0, 16)

_REG_MODE1 = 0x00
_REG_LED0_ON_L = 0x06
_REG_PRESCALE = 0xFE
_MODE1_RESTART = 0x80
_MODE1_AI = 0x20
_MODE1_SLEEP = 0x10


class _SMBusPCA9685Channel:
    """16-bit duty_cycle adapter matching adafruit_pca9685 channel interface over smbus2."""

    def __init__(self, controller: _SMBusPCA9685Controller, channel: int) -> None:
        self._controller = controller
        self._channel = channel
        self._duty_cycle = 0

    @property
    def duty_cycle(self) -> int:
        return self._duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, value: int) -> None:
        clamped = max(0, min(0xFFFF, int(value)))
        self._duty_cycle = clamped
        self._controller.set_channel_duty(self._channel, clamped)


class _SMBusPCA9685Controller:
    """Direct smbus2 register driver for NXP PCA9685 16-channel PWM controllers."""

    def __init__(
        self,
        bus: Any,
        *,
        address: int = DEFAULT_PCA9685_ADDRESS,
        reference_clock_speed: int = DEFAULT_REFERENCE_CLOCK_SPEED,
        owns_bus: bool = False,
    ) -> None:
        self._bus = bus
        self._address = int(address)
        self._reference_clock_speed = int(reference_clock_speed)
        self._owns_bus = owns_bus
        self._frequency = DEFAULT_PCA9685_FREQUENCY_HZ
        self.channels = [_SMBusPCA9685Channel(self, ch) for ch in PCA9685_PWM_CHANNELS]
        self._reset()

    def _write_byte(self, register: int, value: int) -> None:
        try:
            self._bus.write_byte_data(self._address, register, value & 0xFF)
        except AttributeError:
            self._bus.write_i2c_block_data(self._address, register, [value & 0xFF])
        except OSError as exc:
            raise BackendUnavailableError(
                f"Failed to write to PCA9685 at address 0x{self._address:02X}: {exc}"
            ) from exc

    def _read_byte(self, register: int) -> int:
        try:
            if hasattr(self._bus, "read_byte_data"):
                return int(self._bus.read_byte_data(self._address, register)) & 0xFF
            return int(self._bus.read_i2c_block_data(self._address, register, 1)[0]) & 0xFF
        except OSError as exc:
            raise BackendUnavailableError(
                f"Failed to read from PCA9685 at address 0x{self._address:02X}: {exc}"
            ) from exc

    def _reset(self) -> None:
        self._write_byte(_REG_MODE1, _MODE1_AI)

    @property
    def frequency(self) -> int:
        return self._frequency

    @frequency.setter
    def frequency(self, frequency_hz: int) -> None:
        if not 24 <= int(frequency_hz) <= 1526:
            raise BackendConfigurationError(
                f"PCA9685 frequency must be in 24..1526Hz, got {frequency_hz}Hz."
            )
        self._frequency = int(frequency_hz)
        prescale = int(round(self._reference_clock_speed / (4096.0 * float(self._frequency))) - 1)
        prescale = max(3, min(255, prescale))
        old_mode = self._read_byte(_REG_MODE1)
        sleep_mode = (old_mode & 0x7F) | _MODE1_SLEEP
        self._write_byte(_REG_MODE1, sleep_mode)
        self._write_byte(_REG_PRESCALE, prescale)
        self._write_byte(_REG_MODE1, old_mode | _MODE1_AI)
        time.sleep(0.005)
        self._write_byte(_REG_MODE1, old_mode | _MODE1_RESTART | _MODE1_AI)

    def set_channel_duty(self, channel: int, duty_cycle_u16: int) -> None:
        reg = _REG_LED0_ON_L + 4 * channel
        if duty_cycle_u16 <= 0:
            payload = [0x00, 0x00, 0x00, 0x10]  # Full OFF
        elif duty_cycle_u16 >= 0xFFFF:
            payload = [0x00, 0x10, 0x00, 0x00]  # Full ON
        else:
            ticks = max(0, min(4095, int(round((duty_cycle_u16 / 65535.0) * 4096.0))))
            payload = [0x00, 0x00, ticks & 0xFF, (ticks >> 8) & 0x0F]
        try:
            self._bus.write_i2c_block_data(self._address, reg, payload)
        except OSError as exc:
            raise BackendUnavailableError(
                f"Failed to update PCA9685 channel {channel} at 0x{self._address:02X}: {exc}"
            ) from exc

    def deinit(self) -> None:
        if self._owns_bus and hasattr(self._bus, "close"):
            self._bus.close()


class PCA9685ServoBackend:
    """Servo backend that offloads pulse generation to a PCA9685 controller."""

    name = "pca9685"

    def __init__(
        self,
        *,
        address: int = DEFAULT_PCA9685_ADDRESS,
        bus_id: int = DEFAULT_PCA9685_BUS_ID,
        frequency_hz: int = DEFAULT_PCA9685_FREQUENCY_HZ,
        reference_clock_speed: int = DEFAULT_REFERENCE_CLOCK_SPEED,
        channel_map: dict[int, int] | None = None,
        i2c_bus: Any | None = None,
        pca9685_cls: type[Any] | None = None,
        smbus_cls: type[Any] | None = None,
    ) -> None:
        if address < 0x03 or address > 0x77:
            raise BackendConfigurationError(f"Invalid I2C address 0x{address:02X}.")
        self._address = int(address)
        self._bus_id = int(bus_id)
        self._frequency_hz = int(frequency_hz)
        self._channel_map = dict(channel_map or {})
        self._current_pulses: dict[int | str, int] = {}
        self._claimed: set[int | str] = set()

        if pca9685_cls is not None:
            kwargs = {
                "address": self._address,
                "reference_clock_speed": int(reference_clock_speed),
            }
            self._controller = pca9685_cls(i2c_bus, **kwargs)
            self._controller.frequency = self._frequency_hz
        elif i2c_bus is not None and (
            hasattr(i2c_bus, "write_i2c_block_data") or hasattr(i2c_bus, "write_byte_data")
        ):
            self._controller = _SMBusPCA9685Controller(
                i2c_bus,
                address=self._address,
                reference_clock_speed=int(reference_clock_speed),
                owns_bus=False,
            )
            self._controller.frequency = self._frequency_hz
        else:
            # Prefer smbus2 on Raspberry Pi 5; fall back to adafruit_pca9685 if requested/installed
            bus_instance = None
            if smbus_cls is not None:
                bus_instance = smbus_cls(self._bus_id)
            else:
                try:
                    smbus_module = import_module("smbus2")
                    bus_instance = smbus_module.SMBus(self._bus_id)
                except Exception:
                    bus_instance = None

            if bus_instance is not None:
                self._controller = _SMBusPCA9685Controller(
                    bus_instance,
                    address=self._address,
                    reference_clock_speed=int(reference_clock_speed),
                    owns_bus=True,
                )
                self._controller.frequency = self._frequency_hz
            else:
                try:
                    board = import_module("board")
                    busio = import_module("busio")
                    pca9685_module = import_module("adafruit_pca9685")
                    pca9685_cls = pca9685_module.PCA9685
                    if i2c_bus is None:
                        i2c_bus = busio.I2C(board.SCL, board.SDA)
                except ImportError as exc:
                    raise BackendUnavailableError(
                        "PCA9685 backend requires 'smbus2' or 'adafruit-circuitpython-pca9685'."
                    ) from exc
                kwargs = {
                    "address": self._address,
                    "reference_clock_speed": int(reference_clock_speed),
                }
                self._controller = pca9685_cls(i2c_bus, **kwargs)
                self._controller.frequency = self._frequency_hz

    def _period_us(self) -> float:
        return 1_000_000.0 / float(self._frequency_hz)

    def _normalize_identifier(self, identifier: int | str | ServoEndpoint) -> int | str:
        endpoint = parse_servo_endpoint(identifier)
        return endpoint.legacy_key

    def _resolve_channel(self, identifier: int | str | ServoEndpoint) -> int:
        endpoint = parse_servo_endpoint(identifier)
        if endpoint.kind == "hat_pwm":
            channel = endpoint.value
        else:
            channel = self._channel_map.get(endpoint.legacy_pin, endpoint.legacy_pin)
        if 0 <= channel <= 15:
            return channel
        raise BackendConfigurationError(
            f"Identifier {identifier} does not map to a valid PCA9685 channel (0..15)."
        )

    def _pulse_to_duty_cycle(self, pulse_width_us: int) -> int:
        pulse_width_us = max(0, pulse_width_us)
        duty = int((pulse_width_us / self._period_us()) * 0xFFFF)
        return max(0, min(0xFFFF, duty))

    def claim(self, identifier: int | str | ServoEndpoint) -> None:
        key = self._normalize_identifier(identifier)
        self._resolve_channel(identifier)
        self._claimed.add(key)
        self._current_pulses.setdefault(key, 0)

    def set_pulse_us(
        self, identifier: int | str | ServoEndpoint, pulse_width_us: int | float
    ) -> None:
        key = self._normalize_identifier(identifier)
        if pulse_width_us <= 0:
            self.off(identifier)
            return
        self.claim(identifier)
        channel = self._resolve_channel(identifier)
        self._controller.channels[channel].duty_cycle = self._pulse_to_duty_cycle(
            int(round(pulse_width_us))
        )
        self._current_pulses[key] = int(round(pulse_width_us))

    def get_pulse_us(self, identifier: int | str | ServoEndpoint) -> int:
        key = self._normalize_identifier(identifier)
        return int(self._current_pulses.get(key, 0))

    def off(self, identifier: int | str | ServoEndpoint) -> None:
        key = self._normalize_identifier(identifier)
        self.claim(identifier)
        channel = self._resolve_channel(identifier)
        self._controller.channels[channel].duty_cycle = 0
        self._current_pulses[key] = 0

    def release(self, identifier: int | str | ServoEndpoint) -> None:
        key = self._normalize_identifier(identifier)
        if key not in self._claimed:
            return
        self.off(identifier)
        self._claimed.discard(key)
        self._current_pulses.pop(key, None)

    def close(self) -> None:
        for identifier in list(self._claimed):
            self.release(identifier)
        if hasattr(self._controller, "deinit"):
            self._controller.deinit()
