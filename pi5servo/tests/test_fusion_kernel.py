"""Filesystem-backed simulated kernel: no device access."""

import pytest

from pi5servo.core.backend_errors import BackendConfigurationError, BackendUnavailableError
from pi5servo.core.backends.fusion_hat_plus import DRIVER_VERSION, FusionHatPlusBackend


@pytest.fixture
def kernel(tmp_path):
    root = tmp_path / "hat"
    root.mkdir()
    (root / "version").write_text(DRIVER_VERSION)
    for channel in range(12):
        directory = root / "pwm" / f"pwm{channel}"
        directory.mkdir(parents=True)
        for name in ("period", "duty_cycle", "enable"):
            (directory / name).write_text("0")
    battery = tmp_path / "voltage_now"
    battery.write_text("7494000")
    lock = tmp_path / "lock"
    lock.touch()
    return {"sysfs_root": root, "battery_path": battery, "lock_path": lock}


def test_twelve_channels_are_independent_and_lock_excludes_other_session(kernel):
    backend = FusionHatPlusBackend(**kernel)
    with pytest.raises(BackendUnavailableError, match="owned"):
        FusionHatPlusBackend(**kernel)
    for channel in range(12):
        backend.set_pulse_us(f"hat_pwm{channel}", 1500 + channel)
    for channel in range(12):
        value = (kernel["sysfs_root"] / "pwm" / f"pwm{channel}" / "duty_cycle").read_text()
        assert int(value) == 1500 + channel
    assert backend.read_battery_voltage() == 7.494
    backend.off("hat_pwm5")
    assert backend.get_pulse_us("hat_pwm5") == 0
    assert backend.get_pulse_us("hat_pwm6") == 1506
    backend.close()
    replacement = FusionHatPlusBackend(**kernel)
    replacement.close()


def test_invalid_channels_and_missing_driver_never_start_output(kernel):
    backend = FusionHatPlusBackend(**kernel)
    for endpoint in ("hat_pwm12", "gpio0", 0):
        with pytest.raises(BackendConfigurationError):
            backend.set_pulse_us(endpoint, 1500)
    backend.close()
    (kernel["sysfs_root"] / "version").write_text("1.1.0")
    with pytest.raises(BackendUnavailableError, match="reviewed"):
        FusionHatPlusBackend(**kernel)


def test_close_attempts_all_claimed_channels_and_releases_lock(kernel, monkeypatch):
    backend = FusionHatPlusBackend(**kernel)
    backend.claim("hat_pwm0")
    backend.claim("hat_pwm1")
    original = backend._write
    calls = []

    def write(channel, attribute, value):
        calls.append(channel)
        if channel == 0:
            raise BackendUnavailableError("injected stop failure")
        original(channel, attribute, value)

    monkeypatch.setattr(backend, "_write", write)
    with pytest.raises(BackendUnavailableError, match="remove actuator power"):
        backend.close()
    assert sorted(calls) == [0, 1]
    assert backend._lock is None


def test_invalid_calibration_does_not_replace_file(tmp_path):
    from pi5servo.config.config_manager import ConfigManager
    from pi5servo.core.servo import ServoCalibration

    path = tmp_path / "servo.json"
    manager = ConfigManager(path)
    manager.set_backend_config("fusion_hat_plus", {})
    manager.set_calibration("hat_pwm0", ServoCalibration(pulse_min=800, pulse_max=2200))
    assert manager.save()
    before = path.read_bytes()
    manager.set_calibration("hat_pwm1", ServoCalibration(pulse_min=1500, pulse_center=1500))
    with pytest.raises(ValueError, match="hat_pwm1"):
        manager.save()
    assert path.read_bytes() == before
