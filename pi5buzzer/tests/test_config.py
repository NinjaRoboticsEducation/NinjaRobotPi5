"""Unit tests for pi5buzzer.config.config_manager.BuzzerConfigManager."""

import json
import os

import pytest

from pi5buzzer.config.config_manager import DEFAULT_CONFIG, BuzzerConfigManager


class TestConfigManagerLoad:
    """Test load()."""

    def test_load_defaults_when_no_file(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config = config_manager.load()
        assert config["pin"] == DEFAULT_CONFIG["pin"]
        assert config["volume"] == DEFAULT_CONFIG["volume"]

    def test_load_from_file(self, tmp_config):
        with open(tmp_config, "w", encoding="utf-8") as file_obj:
            json.dump({"pin": 18, "volume": 64}, file_obj)

        config_manager = BuzzerConfigManager(tmp_config)
        config = config_manager.load()
        assert config["pin"] == 18
        assert config["volume"] == 64

    def test_load_merges_with_defaults(self, tmp_config):
        with open(tmp_config, "w", encoding="utf-8") as file_obj:
            json.dump({"pin": 22}, file_obj)

        config_manager = BuzzerConfigManager(tmp_config)
        config = config_manager.load()
        assert config["pin"] == 22
        assert config["volume"] == DEFAULT_CONFIG["volume"]

    def test_load_handles_corrupt_json(self, tmp_config):
        with open(tmp_config, "w", encoding="utf-8") as file_obj:
            file_obj.write("not valid json!!!")

        config_manager = BuzzerConfigManager(tmp_config)
        config = config_manager.load()
        assert config["pin"] == DEFAULT_CONFIG["pin"]

    def test_load_handles_non_dict_json(self, tmp_config):
        with open(tmp_config, "w", encoding="utf-8") as file_obj:
            json.dump([1, 2, 3], file_obj)

        config_manager = BuzzerConfigManager(tmp_config)
        config = config_manager.load()
        assert config["pin"] == DEFAULT_CONFIG["pin"]


class TestConfigManagerSave:
    """Test save()."""

    def test_save_creates_file(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        config_manager.save()
        assert os.path.exists(tmp_config)

    def test_save_writes_correct_content(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        config_manager.set_pin(22)
        config_manager.save()

        with open(tmp_config, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        assert data["pin"] == 22

    def test_save_roundtrip(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        config_manager.set_pin(23)
        config_manager.set_volume(100)
        config_manager.save()

        config_manager_2 = BuzzerConfigManager(tmp_config)
        config = config_manager_2.load()
        assert config["pin"] == 23
        assert config["volume"] == 100


class TestConfigManagerPin:
    """Test pin management."""

    def test_get_pin_default(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        assert config_manager.get_pin() == DEFAULT_CONFIG["pin"]

    def test_set_pin_valid(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        config_manager.set_pin(22)
        assert config_manager.get_pin() == 22

    def test_set_pin_boundary(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        config_manager.set_pin(0)
        assert config_manager.get_pin() == 0
        config_manager.set_pin(27)
        assert config_manager.get_pin() == 27

    def test_set_pin_invalid_low(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        with pytest.raises(ValueError):
            config_manager.set_pin(-1)

    def test_set_pin_invalid_high(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        with pytest.raises(ValueError):
            config_manager.set_pin(28)


class TestConfigManagerVolume:
    """Test volume management."""

    def test_get_volume_default(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        assert config_manager.get_volume() == DEFAULT_CONFIG["volume"]

    def test_set_volume_valid(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        config_manager.set_volume(200)
        assert config_manager.get_volume() == 200

    def test_set_volume_boundaries(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        config_manager.set_volume(0)
        assert config_manager.get_volume() == 0
        config_manager.set_volume(255)
        assert config_manager.get_volume() == 255

    def test_set_volume_invalid(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        with pytest.raises(ValueError):
            config_manager.set_volume(-1)
        with pytest.raises(ValueError):
            config_manager.set_volume(256)


class TestConfigManagerExportImport:
    """Test export/import functionality."""

    def test_export_import_roundtrip(self, tmp_config, tmp_path):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        config_manager.set_pin(22)
        config_manager.set_volume(100)
        config_manager.save()

        export_path = str(tmp_path / "exported.json")
        config_manager.export_config(export_path)

        imported = BuzzerConfigManager(str(tmp_path / "new_config.json"))
        imported.import_config(export_path)
        assert imported.get_pin() == 22
        assert imported.get_volume() == 100

    def test_import_nonexistent_file(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.load()
        with pytest.raises(FileNotFoundError):
            config_manager.import_config("/nonexistent/path.json")


class TestConfigManagerInitConfig:
    """Test init_config()."""

    def test_init_config(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        config_manager.init_config(pin=22)
        assert config_manager.get_pin() == 22
        assert os.path.exists(tmp_config)

    def test_init_config_invalid_pin(self, tmp_config):
        config_manager = BuzzerConfigManager(tmp_config)
        with pytest.raises(ValueError):
            config_manager.init_config(pin=99)
