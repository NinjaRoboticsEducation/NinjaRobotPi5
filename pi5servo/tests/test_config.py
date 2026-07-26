"""Unit tests for config module."""

import json

import pytest

from pi5servo.config import ConfigManager, get_default_config_path
from pi5servo.core import ServoCalibration


class TestConfigManager:
    """Test ConfigManager class."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config path."""
        return tmp_path / "test_servo.json"

    @pytest.fixture
    def manager(self, temp_config):
        """Create a ConfigManager with temp path."""
        return ConfigManager(temp_config)

    def test_default_path(self):
        """Default path is relative to package."""
        path = get_default_config_path()
        assert path.name == "servo.json"
        assert path.parent.name == "pi5servo"

    def test_init_with_path(self, temp_config):
        """ConfigManager accepts custom path."""
        mgr = ConfigManager(temp_config)
        assert mgr.config_path == temp_config

    def test_exists_false(self, manager):
        """exists() returns False when file doesn't exist."""
        assert manager.exists() is False

    def test_save_creates_file(self, manager):
        """save() creates config file."""
        cal = ServoCalibration(pulse_center=1550, speed=100)
        manager.set_calibration(20, cal)
        assert manager.save() is True
        assert manager.exists() is True

    def test_load_restores_data(self, manager, temp_config):
        """load() restores saved calibrations."""
        # Save data
        cal = ServoCalibration(pulse_center=1550, speed=100)
        manager.set_calibration(20, cal)
        manager.save()

        # Load in new manager
        manager2 = ConfigManager(temp_config)
        assert manager2.load() is True
        loaded_cal = manager2.get_calibration(20)
        assert loaded_cal.pulse_center == 1550
        assert loaded_cal.speed == 100

    def test_get_calibration_default(self, manager):
        """get_calibration returns safe defaults for unknown pins."""
        cal = manager.get_calibration(99)
        # Safe defaults: all pulses set to center (1500) to prevent unexpected movement
        assert cal.pulse_min == 1500
        assert cal.pulse_max == 1500
        assert cal.speed == 80

    def test_set_and_get_calibration(self, manager):
        """set_calibration stores data correctly."""
        cal = ServoCalibration(
            pulse_min=600,
            pulse_max=2400,
            pulse_center=1500,
            angle_min=-85.0,
            angle_max=85.0,
            angle_center=5.0,
            speed=90,
        )
        manager.set_calibration(20, cal)

        loaded = manager.get_calibration(20)
        assert loaded.pulse_min == 600
        assert loaded.pulse_max == 2400
        assert loaded.angle_center == 5.0
        assert loaded.speed == 90

    def test_get_all_calibrations(self, manager):
        """get_all_calibrations returns all stored data."""
        manager.set_calibration(20, ServoCalibration(speed=100))
        manager.set_calibration(21, ServoCalibration(speed=90))

        all_cals = manager.get_all_calibrations()
        assert len(all_cals) == 2
        assert 20 in all_cals
        assert 21 in all_cals

    def test_remove_calibration(self, manager):
        """remove_calibration deletes pin data."""
        manager.set_calibration(20, ServoCalibration())
        assert manager.remove_calibration(20) is True
        assert manager.remove_calibration(20) is False  # Already removed

    def test_clear(self, manager):
        """clear() removes all calibrations."""
        manager.set_calibration(20, ServoCalibration())
        manager.set_calibration(21, ServoCalibration())
        manager.clear()

        all_cals = manager.get_all_calibrations()
        assert len(all_cals) == 0

    def test_load_invalid_json(self, manager, temp_config):
        """load() handles invalid JSON gracefully."""
        temp_config.write_text("not valid json")
        assert manager.load() is False

    def test_load_missing_file(self, manager):
        """load() returns False for missing file."""
        assert manager.load() is False

    def test_speed_field_persisted(self, manager, temp_config):
        """speed field is correctly persisted and loaded."""
        cal = ServoCalibration(speed=42)
        manager.set_calibration(20, cal)
        manager.save()

        # Read raw JSON to verify
        with open(temp_config) as f:
            data = json.load(f)
        assert data["gpio20"]["speed"] == 42

        # Load and verify
        manager.load()
        assert manager.get_calibration(20).speed == 42

    def test_legacy_numeric_config_keys_load_as_gpio_endpoints(self, temp_config):
        """Older numeric config keys are normalized on load."""
        temp_config.write_text(
            json.dumps(
                {
                    "20": {"pulse_center": 1600, "speed": 55},
                    "__backend__": {"name": "auto", "kwargs": {}},
                }
            ),
            encoding="utf-8",
        )

        manager = ConfigManager(temp_config)
        assert manager.load() is True
        assert manager.get_calibration(20).pulse_center == 1600
        assert manager.get_all_endpoint_calibrations()["gpio20"].speed == 55

    def test_explicit_endpoint_config_persisted(self, manager, temp_config):
        """Explicit endpoint identifiers are stored in the new schema."""
        manager.set_calibration("hat_pwm1", ServoCalibration(speed=60))
        manager.save()

        with open(temp_config, encoding="utf-8") as handle:
            data = json.load(handle)

        assert data["hat_pwm1"]["speed"] == 60
        assert 20 not in manager.get_all_calibrations()

    def test_get_all_calibrations_keeps_legacy_gpio_view(self, manager):
        """Legacy int-key view should only expose native GPIO endpoints."""
        manager.set_calibration(20, ServoCalibration(speed=100))
        manager.set_calibration("hat_pwm2", ServoCalibration(speed=90))

        all_cals = manager.get_all_calibrations()
        assert all_cals == {20: manager.get_calibration(20)}

    def test_get_known_endpoints_returns_normalized_ids(self, manager):
        """Configured endpoints should be returned in normalized form."""
        manager.set_calibration(20, ServoCalibration())
        manager.set_calibration("hat_pwm1", ServoCalibration())

        endpoints = manager.get_known_endpoints()
        assert [endpoint.identifier for endpoint in endpoints] == ["gpio20", "hat_pwm1"]

    def test_backend_config_defaults_to_auto(self, manager):
        """Backend config defaults to standalone auto mode."""
        assert manager.get_backend_config() == {"name": "auto", "kwargs": {}}

    def test_backend_config_persisted(self, manager, temp_config):
        """Backend metadata is stored alongside servo calibrations."""
        manager.set_backend_config(
            "pca9685",
            {
                "address": 0x40,
                "channel_map": {12: 0, 13: 1},
            },
        )
        manager.save()

        with open(temp_config, encoding="utf-8") as handle:
            data = json.load(handle)

        assert data["__backend__"]["name"] == "pca9685"
        assert data["__backend__"]["kwargs"]["address"] == 64

        manager2 = ConfigManager(temp_config)
        assert manager2.load() is True
        assert manager2.get_backend_config()["name"] == "pca9685"
        assert manager2.get_backend_config()["kwargs"]["channel_map"] == {"12": 0, "13": 1}
