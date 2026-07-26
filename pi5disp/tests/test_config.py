"""Unit tests for the ConfigManager."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pi5disp.config.config_manager import (
    CONFIG_ENV_VAR,
    DEFAULT_CONFIG,
    DISPLAY_PROFILES,
    ConfigManager,
)


class TestConfigManager:
    """Tests for the ConfigManager class."""

    def setup_method(self) -> None:
        self.config_path = "test_display.json"
        self.manager = ConfigManager(self.config_path)
        if os.path.exists(self.manager.config_path):
            os.remove(self.manager.config_path)

    def teardown_method(self) -> None:
        if os.path.exists(self.manager.config_path):
            os.remove(self.manager.config_path)
        export_path = "exported_display.json"
        if os.path.exists(export_path):
            os.remove(export_path)

    def test_load_defaults_when_no_file(self) -> None:
        """Should load default config if file does not exist."""
        config = self.manager.load()
        assert config == DEFAULT_CONFIG

    def test_default_path_uses_xdg_config_home(self, monkeypatch, tmp_path: Path) -> None:
        """Default configuration should live in writable user runtime state."""
        monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        manager = ConfigManager()
        manager.init_config(interactive=False)

        assert Path(manager.config_path) == tmp_path / "pi5disp" / "display.json"
        assert Path(manager.config_path).is_file()

    def test_environment_override_selects_explicit_path(self, monkeypatch, tmp_path: Path) -> None:
        """PI5DISP_CONFIG should override the normal per-user location."""
        override = tmp_path / "robot" / "screen.json"
        monkeypatch.setenv(CONFIG_ENV_VAR, str(override))

        manager = ConfigManager()
        manager.init_config(interactive=False)

        assert Path(manager.config_path) == override
        assert override.is_file()

    def test_save_and_load(self) -> None:
        """Should save and reload configuration."""
        self.manager.load()
        self.manager.set("rotation", 180)
        reloaded = self.manager.load()
        assert reloaded["rotation"] == 180

    def test_get(self) -> None:
        """Should read a config value."""
        self.manager.load()
        assert self.manager.get("dc_pin") == DEFAULT_CONFIG["dc_pin"]

    def test_set(self) -> None:
        """Should update and persist a config value."""
        self.manager.load()
        self.manager.set("brightness", 75)
        assert self.manager.get("brightness") == 75

    def test_export_config(self) -> None:
        """Should export config to another file."""
        self.manager.load()
        export_path = "exported_display.json"
        self.manager.export_config(export_path)
        assert os.path.exists(export_path)

        with open(export_path, "r", encoding="utf-8") as file_handle:
            exported = json.load(file_handle)
        assert exported["display_profile"] == DEFAULT_CONFIG["display_profile"]

    def test_import_config(self) -> None:
        """Should import config from another file."""
        export_path = "exported_display.json"
        with open(export_path, "w", encoding="utf-8") as file_handle:
            json.dump({"display_profile": "waveshare_2inch", "rotation": 270}, file_handle)

        imported = self.manager.import_config(export_path)
        assert imported["display_profile"] == "waveshare_2inch"
        assert imported["rotation"] == 270

    def test_import_nonexistent(self) -> None:
        """Import should raise if source file does not exist."""
        try:
            self.manager.import_config("missing.json")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("Expected FileNotFoundError")

    def test_init_config_non_interactive(self) -> None:
        """Non-interactive init should save defaults."""
        config = self.manager.init_config(interactive=False)
        assert config == DEFAULT_CONFIG
        assert os.path.exists(self.manager.config_path)

    def test_display_profiles_valid(self) -> None:
        """Display profile metadata should contain required keys."""
        for profile in DISPLAY_PROFILES.values():
            assert "name" in profile
            assert "width" in profile
            assert "height" in profile
            assert "speed_hz" in profile

    def test_load_corrupted_json(self) -> None:
        """Corrupted JSON should fall back to defaults."""
        with open(self.manager.config_path, "w", encoding="utf-8") as file_handle:
            file_handle.write("{broken json")
        config = self.manager.load()
        assert config == DEFAULT_CONFIG
