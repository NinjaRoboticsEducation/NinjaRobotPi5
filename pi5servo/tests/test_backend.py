"""Unit tests for servo pulse backends."""

from __future__ import annotations

import shutil
from unittest.mock import MagicMock

import pytest

from pi5servo.core.backend import (
    BackendConfigurationError,
    BackendUnavailableError,
    MixedServoBackend,
    PigpioServoBackend,
    create_servo_backend,
)
from pi5servo.core.backends.dfr0566 import DFR0566ServoBackend
from pi5servo.core.backends.hardware_pwm import HardwarePWMServoBackend
from pi5servo.core.backends.pca9685 import PCA9685ServoBackend
from pi5servo.core.backends.sunfounder_robot_hat import SunFounderRobotHatBackend


class FakeHardwarePWM:
    """Simple fake for rpi_hardware_pwm.HardwarePWM."""

    def __init__(self, pwm_channel: int, hz: int, chip: int) -> None:
        self.pwm_channel = pwm_channel
        self.hz = hz
        self.chip = chip
        self.chippath = ""
        self.pwm_dir = ""
        self.started_with: list[float] = []
        self.duty_history: list[float] = []
        self.frequency_history: list[int] = []
        self.stop_calls = 0

    def start(self, duty_cycle: float) -> None:
        self.started_with.append(duty_cycle)

    def change_duty_cycle(self, duty_cycle: float) -> None:
        self.duty_history.append(duty_cycle)

    def change_frequency(self, hz: int) -> None:
        self.frequency_history.append(hz)

    def stop(self) -> None:
        self.stop_calls += 1

    def echo(self, message: int, file: str) -> None:
        with open(file, "w", encoding="ascii") as handle:
            handle.write(f"{message}\n")
        if file.endswith("/unexport") and self.pwm_dir:
            shutil.rmtree(self.pwm_dir, ignore_errors=True)


class FakeChannel:
    """Simple PWM channel fake."""

    def __init__(self) -> None:
        self.duty_cycle = 0


class FakePCA9685:
    """Simple fake for adafruit_pca9685.PCA9685."""

    def __init__(self, i2c_bus, **kwargs) -> None:
        self.i2c_bus = i2c_bus
        self.kwargs = kwargs
        self.frequency = 0
        self.channels = [FakeChannel() for _ in range(16)]
        self.deinit_called = False

    def deinit(self) -> None:
        self.deinit_called = True


class FakeSMBus:
    """Simple fake for smbus2.SMBus."""

    def __init__(self, bus_id: int = 1, *, pid: int = 0xDF, vid: int = 0x10) -> None:
        self.bus_id = bus_id
        self.pid = pid
        self.vid = vid
        self.writes: list[tuple[int, int, list[int]]] = []
        self.closed = False

    def write_i2c_block_data(self, address: int, register: int, payload: list[int]) -> None:
        self.writes.append((address, register, list(payload)))

    def read_i2c_block_data(self, address: int, register: int, length: int) -> list[int]:
        if register == 0x01:
            return [self.pid]
        if register == 0x02:
            return [self.vid]
        return [0] * length

    def close(self) -> None:
        self.closed = True


class FakeMixedHardwareBackend:
    """Simple fake for auto-routed native GPIO backend."""

    def __init__(self, *, pins=None, **kwargs) -> None:
        self.pins = list(pins or [])
        self.kwargs = kwargs
        self.pulses: dict[int | str, int] = {}

    def claim(self, identifier: int | str) -> None:
        self.pulses.setdefault(identifier, 0)

    def set_pulse_us(self, identifier: int | str, pulse_width_us: int) -> None:
        self.pulses[identifier] = pulse_width_us

    def get_pulse_us(self, identifier: int | str) -> int:
        return self.pulses.get(identifier, 0)

    def off(self, identifier: int | str) -> None:
        self.pulses[identifier] = 0

    def release(self, identifier: int | str) -> None:
        self.pulses.pop(identifier, None)

    def close(self) -> None:
        return None


class FakeMixedHatBackend(FakeMixedHardwareBackend):
    """Simple fake for auto-routed DFR0566 backend."""


def test_pigpio_backend_pass_through(mock_pigpio) -> None:
    """Pigpio backend should proxy set/get/off calls."""
    backend = PigpioServoBackend(mock_pigpio)

    backend.claim(20)
    backend.set_pulse_us(20, 1500)
    assert backend.get_pulse_us(20) == 1500
    backend.off(20)

    mock_pigpio.set_servo_pulsewidth.assert_any_call(20, 1500)
    mock_pigpio.set_servo_pulsewidth.assert_any_call(20, 0)


def test_hardware_pwm_backend_rejects_unsupported_pin() -> None:
    """Only Pi 5 PWM-capable header pins should be accepted."""
    backend = HardwarePWMServoBackend(pwm_cls=FakeHardwarePWM)

    with pytest.raises(BackendConfigurationError, match="GPIO20"):
        backend.claim(20)


def test_hardware_pwm_backend_sets_pulse_and_off() -> None:
    """Hardware PWM backend should keep long-lived PWM objects per pin."""
    backend = HardwarePWMServoBackend(pwm_cls=FakeHardwarePWM)

    backend.set_pulse_us(12, 1500)
    pwm = backend._pwms[12]
    assert pwm.pwm_channel == 0
    assert pytest.approx(pwm.started_with[-1], rel=0.01) == 7.5
    assert backend.get_pulse_us(12) == 1500

    backend.set_pulse_us(12, 2000)
    assert pytest.approx(pwm.duty_history[-1], rel=0.01) == 10.0
    assert pwm.frequency_history[-1] == 50

    backend.off(12)
    assert pwm.stop_calls == 1
    assert backend.get_pulse_us(12) == 0


def test_hardware_pwm_backend_maps_each_alternate_pin_to_its_pwm_channel() -> None:
    """GPIO12/18 share PWM0 and GPIO13/19 share PWM1."""
    backend = HardwarePWMServoBackend(pwm_cls=FakeHardwarePWM)

    backend.set_pulse_us(18, 1500)
    backend.set_pulse_us(19, 1500)

    assert backend._pwms[18].pwm_channel == 0
    assert backend._pwms[19].pwm_channel == 1


def test_hardware_pwm_backend_rejects_duplicate_alternate_pwm_routes() -> None:
    """One hardware PWM channel cannot drive two selected servo endpoints."""
    with pytest.raises(BackendConfigurationError, match="GPIO12 and GPIO18.*PWM0"):
        HardwarePWMServoBackend(pins=[12, 18], pwm_cls=FakeHardwarePWM)

    backend = HardwarePWMServoBackend(pwm_cls=FakeHardwarePWM)
    backend.claim(12)

    with pytest.raises(BackendConfigurationError, match="GPIO12 and GPIO18.*PWM0"):
        backend.claim(18)


def test_hardware_pwm_backend_claim_retries_after_permission_error(monkeypatch) -> None:
    """A stale sysfs node should be cleaned up and retried once on claim."""

    class FlakyHardwarePWM(FakeHardwarePWM):
        attempts = 0

        def __init__(self, pwm_channel: int, hz: int, chip: int) -> None:
            type(self).attempts += 1
            if type(self).attempts == 1:
                raise PermissionError("Unable to create/write to pwm0")
            super().__init__(pwm_channel, hz, chip)

    backend = HardwarePWMServoBackend(pwm_cls=FlakyHardwarePWM)
    recovered_channels: list[int] = []

    monkeypatch.setattr(backend, "_prepare_channel_for_claim", lambda _channel: None)
    monkeypatch.setattr(
        backend,
        "_best_effort_unexport_channel",
        lambda channel, **_kwargs: recovered_channels.append(channel),
    )

    backend.claim(12)

    assert FlakyHardwarePWM.attempts == 2
    assert recovered_channels == [0]
    assert 12 in backend._pwms


def test_hardware_pwm_backend_claim_preemptively_cleans_unwritable_sysfs_channel(
    monkeypatch,
) -> None:
    """Pre-existing unwritable sysfs nodes should be unexported before claim."""
    backend = HardwarePWMServoBackend(pwm_cls=FakeHardwarePWM)
    recovered_channels: list[int] = []

    monkeypatch.setattr(backend, "_channel_paths", lambda _channel: ("chip", "pwm0", "unexport"))
    monkeypatch.setattr(
        "pi5servo.core.backends.hardware_pwm.os.path.isdir", lambda path: path == "pwm0"
    )
    monkeypatch.setattr(backend, "_controls_writable", lambda _path: False)
    monkeypatch.setattr(
        backend,
        "_best_effort_unexport_channel",
        lambda channel, **_kwargs: recovered_channels.append(channel),
    )

    backend.claim(12)

    assert recovered_channels == [0]
    assert 12 in backend._pwms


def test_hardware_pwm_backend_release_keeps_healthy_sysfs_channel_exported(tmp_path) -> None:
    """Normal release should not force a fresh sysfs export on the next startup."""
    chippath = tmp_path / "pwmchip0"
    chippath.mkdir()
    unexport_path = chippath / "unexport"
    unexport_path.write_text("", encoding="ascii")
    pwm_dir = chippath / "pwm0"
    pwm_dir.mkdir()

    backend = HardwarePWMServoBackend(pwm_cls=FakeHardwarePWM)
    backend.set_pulse_us(12, 1500)
    pwm = backend._pwms[12]
    pwm.chippath = str(chippath)
    pwm.pwm_dir = str(pwm_dir)

    backend.release(12)

    assert unexport_path.read_text(encoding="ascii") == ""
    assert pwm_dir.exists()
    assert 12 not in backend._pwms


def test_pca9685_backend_sets_frequency_and_duty() -> None:
    """PCA9685 backend should convert pulse widths to duty-cycle values."""
    backend = PCA9685ServoBackend(
        pca9685_cls=FakePCA9685,
        i2c_bus=object(),
        channel_map={20: 3},
    )

    assert backend._controller.frequency == 50

    backend.set_pulse_us(20, 1500)
    assert backend.get_pulse_us(20) == 1500
    assert backend._controller.channels[3].duty_cycle > 0

    backend.off(20)
    assert backend._controller.channels[3].duty_cycle == 0

    backend.close()
    assert backend._controller.deinit_called is True


def test_dfr0566_backend_validates_board_and_sets_pulse() -> None:
    """DFR0566 backend should validate identity and convert pulses to duty writes."""
    bus = FakeSMBus()
    backend = DFR0566ServoBackend(i2c_bus=bus, channel_map={20: 1})

    backend.set_pulse_us(20, 1500)
    assert backend.get_pulse_us(20) == 1500
    assert (0x10, 0x03, [0x01]) in bus.writes
    assert (0x10, 0x06, [7, 5]) in bus.writes

    backend.off(20)
    assert (0x10, 0x06, [0, 0]) in bus.writes


def test_dfr0566_backend_rejects_invalid_channel() -> None:
    """DFR0566 backend only supports PWM channels 1..4."""
    backend = DFR0566ServoBackend(i2c_bus=FakeSMBus())

    with pytest.raises(BackendConfigurationError, match="DFR0566 PWM channel"):
        backend.claim(5)


def test_dfr0566_backend_rejects_wrong_device_identity() -> None:
    """Identity mismatch should fail early instead of writing blind PWM traffic."""
    with pytest.raises(BackendUnavailableError, match="not detected"):
        DFR0566ServoBackend(i2c_bus=FakeSMBus(pid=0x00))


def test_create_servo_backend_wraps_pigpio(mock_pigpio) -> None:
    """Passing a pigpio-like `pi` should create the legacy wrapper backend."""
    backend = create_servo_backend(pi=mock_pigpio)

    backend.set_pulse_us(20, 1700)
    mock_pigpio.set_servo_pulsewidth.assert_called_with(20, 1700)


def test_create_servo_backend_accepts_backend_object() -> None:
    """A prebuilt backend object should pass straight through."""
    backend = MagicMock()

    assert create_servo_backend(backend) is backend


def test_create_servo_backend_supports_dfr0566() -> None:
    """Named DFR0566 backend should be created through the shared factory."""
    bus = FakeSMBus()

    backend = create_servo_backend("dfr0566", i2c_bus=bus, channel_map={21: 2})

    backend.set_pulse_us(21, 1600)
    assert backend.get_pulse_us(21) == 1600
    assert (0x10, 0x08, [8, 0]) in bus.writes


def test_mixed_servo_backend_routes_gpio_and_hat_endpoints(monkeypatch) -> None:
    """Auto backend should create a mixed router for GPIO plus DFR0566 endpoints."""
    import pi5servo.core.backend as backend_module

    monkeypatch.setattr(backend_module, "HardwarePWMServoBackend", FakeMixedHardwareBackend)
    monkeypatch.setattr(backend_module, "DFR0566ServoBackend", FakeMixedHatBackend)

    backend = create_servo_backend(
        "auto",
        pins=[12, "hat_pwm1"],
        address=0x10,
        bus_id=1,
    )

    assert isinstance(backend, MixedServoBackend)
    backend.set_pulse_us(12, 1500)
    backend.set_pulse_us("hat_pwm1", 1600)

    gpio_backend, gpio_identifier = backend._routes["gpio12"]
    hat_backend, hat_identifier = backend._routes["hat_pwm1"]

    assert gpio_identifier == 12
    assert hat_identifier == "hat_pwm1"
    assert gpio_backend.pulses[12] == 1500
    assert hat_backend.pulses["hat_pwm1"] == 1600


def test_sunfounder_robot_hat_backend_writes_big_endian_and_reads_battery() -> None:
    """SunFounder backend must send 3-byte Big-Endian [reg, MSB, LSB] packets and read ADC A4."""

    class FakeSunFounderBus(FakeSMBus):
        def __init__(self) -> None:
            super().__init__()
            self._read_queue = [0x0B, 0x1A]  # raw = 0x0B1A = 2842 -> ~6.87V

        def read_byte(self, address: int) -> int:
            assert address == 0x14
            return self._read_queue.pop(0)

    bus = FakeSunFounderBus()
    backend = SunFounderRobotHatBackend(bus=bus)

    # Verify Timer 0, 1, 2 period = 4095 (0x0FFF -> [0x0F, 0xFF]) and prescaler = 351 (0x015F -> [0x01, 0x5F])
    assert (0x14, 0x40, [0x01, 0x5F]) in bus.writes
    assert (0x14, 0x44, [0x0F, 0xFF]) in bus.writes
    assert (0x14, 0x41, [0x01, 0x5F]) in bus.writes
    assert (0x14, 0x45, [0x0F, 0xFF]) in bus.writes
    assert (0x14, 0x42, [0x01, 0x5F]) in bus.writes
    assert (0x14, 0x46, [0x0F, 0xFF]) in bus.writes

    # Set pulse on P0 (hat_pwm0) to 1500us -> ticks = round(1500/20000 * 4095) = 307 (0x0133 -> [0x01, 0x33])
    backend.set_pulse_us("p0", 1500)
    assert backend.get_pulse_us("hat_pwm0") == 1500
    assert (0x14, 0x20, [0x01, 0x33]) in bus.writes

    # Read battery voltage (channel A4 -> reg 0x13)
    voltage = backend.read_battery_voltage()
    assert (0x14, 0x13, [0x00, 0x00]) in bus.writes
    assert voltage == pytest.approx(6.87, abs=0.02)

    backend.off("pwm0")
    assert backend.get_pulse_us("hat_pwm0") == 0
    assert (0x14, 0x20, [0x00, 0x00]) in bus.writes

    with pytest.raises(BackendConfigurationError, match="out of range"):
        backend.claim("hat_pwm12")


def test_pca9685_backend_supports_hat_pwm_and_smbus2() -> None:
    """PCA9685 backend should support hat_pwm0..15 directly over smbus2."""
    bus = FakeSMBus()
    backend = PCA9685ServoBackend(i2c_bus=bus)

    backend.set_pulse_us("hat_pwm0", 1500)
    assert backend.get_pulse_us("pwm0") == 1500
    # Verify LED0_ON_L (0x06) received a 4-byte block write
    led0_writes = [w for w in bus.writes if w[0] == 0x40 and w[1] == 0x06]
    assert led0_writes
    assert led0_writes[-1][2][:2] == [0x00, 0x00]

    backend.off("hat_pwm0")
    assert backend.get_pulse_us("hat_pwm0") == 0
    assert bus.writes[-1] == (0x40, 0x06, [0x00, 0x00, 0x00, 0x10])


def test_auto_backend_selects_sunfounder_and_pca9685_by_address() -> None:
    """Auto backend with hat_pwm endpoints should dispatch by I2C address."""
    bus_sf = FakeSMBus()
    sf_backend = create_servo_backend(
        "auto", pins=["hat_pwm0", "hat_pwm1"], address=0x14, i2c_bus=bus_sf
    )
    assert isinstance(sf_backend, SunFounderRobotHatBackend)

    bus_sf_fusion = FakeSMBus()
    sf_fusion_backend = create_servo_backend(
        "auto", pins=["hat_pwm10", "hat_pwm11"], address=0x17, i2c_bus=bus_sf_fusion
    )
    assert isinstance(sf_fusion_backend, SunFounderRobotHatBackend)
    assert sf_fusion_backend.address == 0x17

    bus_pca = FakeSMBus()
    pca_backend = create_servo_backend(
        "auto", pins=["hat_pwm0", "hat_pwm15"], address=0x40, i2c_bus=bus_pca
    )
    assert isinstance(pca_backend, PCA9685ServoBackend)


def test_sunfounder_fusion_hat_0x17_fallback_and_register_map() -> None:
    """SunFounder backend should auto-fallback from 0x14 to 0x17 and use 0x50/0x60/0x18 registers."""

    class FakeFusionBus(FakeSMBus):
        def write_i2c_block_data(self, address: int, register: int, data: list[int]) -> None:
            if address == 0x14:
                raise OSError(121, "Remote I/O error")
            super().write_i2c_block_data(address, register, data)

        def read_i2c_block_data(self, address: int, register: int, length: int) -> list[int]:
            assert address == 0x17
            assert register == 0x18
            assert length == 2
            return [0x20, 0x26]  # 8230 mV -> 8.23 V

    bus = FakeFusionBus()
    # Initialize with default 0x14; should auto-detect 0x17 when 0x14 raises Errno 121
    backend = SunFounderRobotHatBackend(bus=bus, address=0x14)
    assert backend.address == 0x17

    # Verify Timer 0..2 prescaler (0x40..0x42) and period (0x50..0x52) on 0x17
    assert (0x17, 0x40, [0x01, 0x5F]) in bus.writes
    assert (0x17, 0x50, [0x0F, 0xFF]) in bus.writes

    # Set pulse on P11 (hat_pwm11) -> register 0x60 + 11 = 0x6B
    backend.set_pulse_us("p11", 1500)
    assert backend.get_pulse_us("hat_pwm11") == 1500
    assert (0x17, 0x6B, [0x01, 0x33]) in bus.writes

    assert backend.read_battery_voltage() == pytest.approx(8.23, abs=0.01)

    backend.off("pwm11")
    assert (0x17, 0x6B, [0x00, 0x00]) in bus.writes
