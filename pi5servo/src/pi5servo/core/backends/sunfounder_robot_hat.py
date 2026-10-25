"""SunFounder Robot HAT (v5) I2C servo & battery ADC backend for pi5servo."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from importlib import import_module
from typing import Any

from ..backend_errors import BackendConfigurationError, BackendUnavailableError
from ..endpoint import ServoEndpoint, parse_servo_endpoint

SUNFOUNDER_DEFAULT_ADDRESS = 0x14
SUNFOUNDER_FUSION_ADDRESS = 0x17
SUNFOUNDER_ADDRESSES = (SUNFOUNDER_DEFAULT_ADDRESS, SUNFOUNDER_FUSION_ADDRESS)
SUNFOUNDER_DEFAULT_BUS_ID = 1
SUNFOUNDER_DEFAULT_FREQUENCY_HZ = 50
SUNFOUNDER_PWM_CHANNELS = range(0, 12)  # P0 through P11 (0-indexed)
SUNFOUNDER_MCU_CLOCK_HZ = 72_000_000
SUNFOUNDER_PWM_PERIOD = 4095
SUNFOUNDER_ADC_BATTERY_CHANNEL = 4  # A4 internal 20k/10k voltage divider
SUNFOUNDER_MCU_RESET_GPIO = 5


def reset_sunfounder_mcu(reset_gpio: int = SUNFOUNDER_MCU_RESET_GPIO) -> bool:
    """Pulse the SunFounder Robot HAT MCU reset pin (GPIO 5) via lgpio on Pi 5."""
    try:
        lgpio = import_module("lgpio")
    except ImportError:
        return False

    for chip in (4, 0):
        try:
            handle = lgpio.gpiochip_open(chip)
        except Exception:
            continue
        try:
            lgpio.gpio_claim_output(handle, reset_gpio, 0)
            lgpio.gpio_write(handle, reset_gpio, 0)
            time.sleep(0.01)
            lgpio.gpio_write(handle, reset_gpio, 1)
            time.sleep(0.01)
            return True
        except Exception:
            return False
        finally:
            try:
                lgpio.gpiochip_close(handle)
            except Exception:
                pass
    return False


class SunFounderRobotHatBackend:
    """Drive up to 12 servos (P0..P11) and read battery ADC via SunFounder Robot HAT MCU (0x14)."""

    name = "sunfounder_robot_hat"
    _io_lock = threading.RLock()

    def __init__(
        self,
        *,
        bus_id: int = SUNFOUNDER_DEFAULT_BUS_ID,
        address: int = SUNFOUNDER_DEFAULT_ADDRESS,
        frequency_hz: int = SUNFOUNDER_DEFAULT_FREQUENCY_HZ,
        channel_map: dict[int, int] | None = None,
        bus: Any | None = None,
        i2c_bus: Any | None = None,
        bus_factory: Callable[[int], Any] | None = None,
        smbus_cls: type[Any] | None = None,
    ) -> None:
        if address < 0x03 or address > 0x77:
            raise BackendConfigurationError(f"Invalid I2C address 0x{address:02X}.")
        if frequency_hz < 40 or frequency_hz > 300:
            raise BackendConfigurationError(
                f"Invalid servo PWM frequency {frequency_hz}Hz. Expected 40-300Hz."
            )

        self.bus_id = int(bus_id)
        self.address = int(address)
        self.frequency_hz = int(frequency_hz)
        self.period_us = 1_000_000.0 / float(self.frequency_hz)
        self._channel_map = dict(channel_map or {})
        provided_bus = bus if bus is not None else i2c_bus
        self._owns_bus = provided_bus is None
        self._bus = provided_bus or self._open_bus(bus_factory, smbus_cls)
        self._pulses: dict[int, int] = {}
        self._claimed: set[int | str] = set()
        self._closed = False
        self._initialize_timers()

    def _open_bus(
        self,
        bus_factory: Callable[[int], Any] | None,
        smbus_cls: type[Any] | None,
    ) -> Any:
        if bus_factory is not None:
            return bus_factory(self.bus_id)
        if smbus_cls is None:
            try:
                smbus_module = import_module("smbus2")
                smbus_cls = smbus_module.SMBus
            except ImportError as exc:
                raise BackendUnavailableError(
                    "SunFounder Robot HAT backend requires 'smbus2'."
                ) from exc
        try:
            return smbus_cls(self.bus_id)
        except Exception as exc:
            raise BackendUnavailableError(
                f"Unable to open I2C bus {self.bus_id} for SunFounder Robot HAT "
                f"at 0x{self.address:02X}: {exc}"
            ) from exc

    def _write_u16_be(self, register: int, value: int) -> None:
        """Write a 16-bit unsigned integer in Big-Endian [MSB, LSB] format to the AT32F413 MCU."""
        clamped = max(0, min(65535, int(value)))
        msb = (clamped >> 8) & 0xFF
        lsb = clamped & 0xFF
        with self._io_lock:
            try:
                self._bus.write_i2c_block_data(self.address, register, [msb, lsb])
            except OSError as exc:
                raise BackendUnavailableError(
                    f"Failed to write to SunFounder Robot HAT MCU at 0x{self.address:02X}: {exc}"
                ) from exc

    @property
    def _pwm_register_base(self) -> int:
        return 0x60 if self.address == SUNFOUNDER_FUSION_ADDRESS else 0x20

    @property
    def _period_register_base(self) -> int:
        return 0x50 if self.address == SUNFOUNDER_FUSION_ADDRESS else 0x44

    def _write_timer_registers(self, prescaler: int) -> None:
        with self._io_lock:
            for timer_idx in range(3):  # Timers 0, 1, 2 -> Channels P0..P11
                self._write_u16_be(0x40 + timer_idx, prescaler)
                self._write_u16_be(self._period_register_base + timer_idx, SUNFOUNDER_PWM_PERIOD)

    def _initialize_timers(self) -> None:
        """Configure Timers 0, 1, and 2 (covering P0..P11) for 50Hz PWM."""
        prescaler = max(
            1,
            int(round(SUNFOUNDER_MCU_CLOCK_HZ / (self.frequency_hz * (SUNFOUNDER_PWM_PERIOD + 1))))
            - 1,
        )
        try:
            try:
                self._write_timer_registers(prescaler)
                return
            except BackendUnavailableError as first_exc:
                if self.address not in SUNFOUNDER_ADDRESSES:
                    raise
                orig_address = self.address
                alt_address = (
                    SUNFOUNDER_FUSION_ADDRESS
                    if orig_address == SUNFOUNDER_DEFAULT_ADDRESS
                    else SUNFOUNDER_DEFAULT_ADDRESS
                )
                try:
                    self.address = alt_address
                    self._write_timer_registers(prescaler)
                    return
                except BackendUnavailableError:
                    self.address = orig_address
                if reset_sunfounder_mcu():
                    for candidate in (orig_address, alt_address):
                        try:
                            self.address = candidate
                            self._write_timer_registers(prescaler)
                            return
                        except BackendUnavailableError:
                            self.address = orig_address
                raise first_exc
        except Exception as exc:
            if self._owns_bus and hasattr(self._bus, "close"):
                self._bus.close()
            if isinstance(exc, BackendUnavailableError):
                raise
            raise BackendUnavailableError(
                f"Unable to initialize SunFounder Robot HAT MCU at 0x{self.address:02X}: {exc}"
            ) from exc

    def _resolve_channel(self, identifier: int | str | ServoEndpoint) -> int:
        endpoint = parse_servo_endpoint(identifier)
        if endpoint.kind == "hat_pwm":
            channel = endpoint.value
        elif endpoint.legacy_pin in self._channel_map:
            channel = self._channel_map[endpoint.legacy_pin]
        else:
            raise BackendConfigurationError(
                f"SunFounder Robot HAT requires HAT PWM endpoints (pwm0..pwm11 / p0..p11), got {identifier!r}."
            )
        if channel not in SUNFOUNDER_PWM_CHANNELS:
            raise BackendConfigurationError(
                f"SunFounder Robot HAT channel {channel} out of range (expected 0..11)."
            )
        return channel

    def claim(self, identifier: int | str | ServoEndpoint) -> None:
        endpoint = parse_servo_endpoint(identifier)
        channel = self._resolve_channel(endpoint)
        self._claimed.add(endpoint.legacy_key)
        self._pulses.setdefault(channel, 0)

    def set_pulse_us(
        self, identifier: int | str | ServoEndpoint, pulse_width_us: int | float
    ) -> None:
        channel = self._resolve_channel(identifier)
        if pulse_width_us <= 0:
            self.off(identifier)
            return
        self.claim(identifier)
        ticks = int(round((float(pulse_width_us) / self.period_us) * float(SUNFOUNDER_PWM_PERIOD)))
        ticks = max(0, min(SUNFOUNDER_PWM_PERIOD, ticks))
        self._write_u16_be(self._pwm_register_base + channel, ticks)
        self._pulses[channel] = int(round(pulse_width_us))

    def get_pulse_us(self, identifier: int | str | ServoEndpoint) -> int:
        channel = self._resolve_channel(identifier)
        return int(self._pulses.get(channel, 0))

    def off(self, identifier: int | str | ServoEndpoint) -> None:
        self.claim(identifier)
        channel = self._resolve_channel(identifier)
        self._write_u16_be(self._pwm_register_base + channel, 0)
        self._pulses[channel] = 0

    def release(self, identifier: int | str | ServoEndpoint) -> None:
        endpoint = parse_servo_endpoint(identifier)
        claim_key = endpoint.legacy_key
        if claim_key not in self._claimed:
            return
        self.off(endpoint)
        self._claimed.discard(claim_key)
        channel = self._resolve_channel(endpoint)
        self._pulses.pop(channel, None)

    def read_battery_voltage(self) -> float:
        """Thread-safe read of onboard 2S battery voltage (Reg 0x13 on 0x14, Reg 0x18 on 0x17)."""
        if self.address == SUNFOUNDER_FUSION_ADDRESS:
            with self._io_lock:
                try:
                    if hasattr(self._bus, "read_i2c_block_data"):
                        block = self._bus.read_i2c_block_data(self.address, 0x18, 2)
                        msb, lsb = int(block[0]), int(block[1])
                    else:
                        msb = int(self._bus.read_byte_data(self.address, 0x18))
                        lsb = int(self._bus.read_byte_data(self.address, 0x19))
                except OSError as exc:
                    raise BackendUnavailableError(
                        f"Failed to read battery ADC from SunFounder Robot HAT at 0x{self.address:02X}: {exc}"
                    ) from exc
            raw_mv = ((msb & 0xFF) << 8) | (lsb & 0xFF)
            return round(raw_mv / 1000.0, 2)

        channel_reg = (7 - SUNFOUNDER_ADC_BATTERY_CHANNEL) | 0x10  # 0x13
        with self._io_lock:
            self._write_u16_be(channel_reg, 0)
            try:
                msb = int(self._bus.read_byte(self.address))
                lsb = int(self._bus.read_byte(self.address))
            except OSError as exc:
                raise BackendUnavailableError(
                    f"Failed to read battery ADC from SunFounder Robot HAT at 0x{self.address:02X}: {exc}"
                ) from exc
        raw = ((msb & 0xFF) << 8) | (lsb & 0xFF)
        return round((raw / 4095.0) * 3.3 * 3.0, 2)

    def close(self) -> None:
        if self._closed:
            return
        for identifier in list(self._claimed):
            try:
                self.release(identifier)
            except Exception:
                pass
        for ch in list(self._pulses):
            try:
                self._write_u16_be(self._pwm_register_base + ch, 0)
            except Exception:
                pass
        self._pulses.clear()
        self._closed = True
        if self._owns_bus and hasattr(self._bus, "close"):
            self._bus.close()
