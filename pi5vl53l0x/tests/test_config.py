"""Unit tests for the ConfigManager."""

from __future__ import annotations

import json

import pytest

from pi5vl53l0x.config.config_manager import (
    ConfigManager,
    get_default_config_filepath,
    load_config,
    save_config,
)


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config file with test data."""
    config_file = tmp_path / "test_config.json"
    config = {"offset_mm": 15, "custom_key": "value"}
    with open(config_file, "w", encoding="utf-8") as file_handle:
        json.dump(config, file_handle)
    return config_file


@pytest.fixture
def empty_dir(tmp_path):
    """Return a path to a non-existent config file in a temp dir."""
    return tmp_path / "no_config.json"


class TestLoadSave:
    """Tests for load_config and save_config functions."""

    def test_load_existing_config(self, tmp_config) -> None:
        """Should load config from existing JSON file."""
        config = load_config(tmp_config)
        assert config["offset_mm"] == 15
        assert config["custom_key"] == "value"

    def test_load_missing_file(self, empty_dir) -> None:
        """Should return empty dict if file does not exist."""
        config = load_config(empty_dir)
        assert config == {}

    def test_load_corrupt_json(self, tmp_path) -> None:
        """Should return empty dict on corrupt JSON."""
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("not valid json {{{", encoding="utf-8")
        config = load_config(corrupt)
        assert config == {}

    def test_save_creates_file(self, tmp_path) -> None:
        """save_config should create the file."""
        filepath = tmp_path / "new_config.json"
        save_config(filepath, {"offset_mm": 42})
        assert filepath.exists()

        loaded = load_config(filepath)
        assert loaded["offset_mm"] == 42

    def test_save_creates_parent_dirs(self, tmp_path) -> None:
        """save_config should create parent directories."""
        filepath = tmp_path / "sub" / "dir" / "config.json"
        save_config(filepath, {"offset_mm": 99})
        assert filepath.exists()

    def test_save_default_config(self, tmp_path) -> None:
        """save_config with no config should save defaults."""
        filepath = tmp_path / "default.json"
        save_config(filepath)
        loaded = load_config(filepath)
        assert loaded["offset_mm"] == 0

    def test_load_accepts_string_path(self, tmp_config) -> None:
        """load_config should accept string path."""
        config = load_config(str(tmp_config))
        assert config["offset_mm"] == 15


class TestDefaultPath:
    """Tests for default path resolution."""

    def test_default_path_is_project_relative(self) -> None:
        """Default config path should be relative to the module."""
        path = get_default_config_filepath()
        assert path.name == "vl53l0x.json"
        assert "config" in str(path.parent)


class TestConfigManager:
    """Tests for the ConfigManager class."""

    def test_init_loads_config(self, tmp_config) -> None:
        """ConfigManager should load config on init."""
        manager = ConfigManager(tmp_config)
        assert manager.get("offset_mm") == 15

    def test_init_missing_file(self, empty_dir) -> None:
        """ConfigManager should handle missing file gracefully."""
        manager = ConfigManager(empty_dir)
        assert manager.config == {}

    def test_get_with_default(self, empty_dir) -> None:
        """get() should return default for missing keys."""
        manager = ConfigManager(empty_dir)
        assert manager.get("nonexistent", 42) == 42

    def test_set_and_save(self, tmp_path) -> None:
        """set() + save() should persist config."""
        filepath = tmp_path / "mgr_config.json"
        manager = ConfigManager(filepath)
        manager.set("offset_mm", 25)
        manager.save()

        manager2 = ConfigManager(filepath)
        assert manager2.get("offset_mm") == 25

    def test_path_property(self, tmp_config) -> None:
        """path property should return the config file path."""
        manager = ConfigManager(tmp_config)
        assert manager.path == tmp_config

    def test_export_config(self, tmp_config, tmp_path) -> None:
        """export_config should write config to a different file."""
        manager = ConfigManager(tmp_config)
        export_path = tmp_path / "exported.json"
        manager.export_config(export_path)

        exported = load_config(export_path)
        assert exported["offset_mm"] == 15

    def test_import_config(self, tmp_config, tmp_path) -> None:
        """import_config should load config from another file."""
        import_file = tmp_path / "import.json"
        save_config(import_file, {"offset_mm": 77})

        manager = ConfigManager(tmp_config)
        assert manager.get("offset_mm") == 15

        manager.import_config(import_file)
        assert manager.get("offset_mm") == 77

    def test_reload(self, tmp_path) -> None:
        """load() should re-read config from disk."""
        filepath = tmp_path / "reload.json"
        save_config(filepath, {"offset_mm": 10})

        manager = ConfigManager(filepath)
        assert manager.get("offset_mm") == 10

        save_config(filepath, {"offset_mm": 50})

        manager.load()
        assert manager.get("offset_mm") == 50
