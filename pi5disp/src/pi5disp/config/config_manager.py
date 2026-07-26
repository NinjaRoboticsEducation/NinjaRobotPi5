"""Configuration manager for pi5disp display settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_ENV_VAR = "PI5DISP_CONFIG"

DISPLAY_PROFILES = {
    "st7789v_2inch8": {
        "name": "ST7789V 2.8-inch IPS TFT 240×320",
        "width": 240,
        "height": 320,
        "x_offset": 0,
        "y_offset": 0,
        "speed_hz": 32_000_000,
    },
    "waveshare_2inch": {
        "name": "Waveshare 2.0-inch IPS LCD 240×320",
        "width": 240,
        "height": 320,
        "x_offset": 0,
        "y_offset": 0,
        "speed_hz": 32_000_000,
    },
}

DEFAULT_PINS = {
    "dc_pin": 14,
    "rst_pin": 15,
    "backlight_pin": 16,
}

DEFAULT_CONFIG = {
    "display_profile": "st7789v_2inch8",
    "dc_pin": DEFAULT_PINS["dc_pin"],
    "rst_pin": DEFAULT_PINS["rst_pin"],
    "backlight_pin": DEFAULT_PINS["backlight_pin"],
    "width": 240,
    "height": 320,
    "rotation": 90,
    "brightness": 100,
    "spi_speed_mhz": 32,
}


def get_default_config_path() -> Path:
    """Return the writable per-user display configuration path."""
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser().absolute()

    config_home = os.environ.get("XDG_CONFIG_HOME")
    base_dir = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return (base_dir / "pi5disp" / "display.json").absolute()


def _prompt_int(label: str, default: int, minimum: int, maximum: int) -> int:
    """Prompt for an integer value with a default and range."""
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("  Please enter a valid integer.")
            continue
        if minimum <= value <= maximum:
            return value
        print(f"  Value must be between {minimum} and {maximum}.")


def _prompt_choice(label: str, default: int, choices: list[int]) -> int:
    """Prompt for one choice from a known list."""
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("  Please enter a valid integer.")
            continue
        if value in choices:
            return value
        print(f"  Please choose one of: {', '.join(str(choice) for choice in choices)}.")


class ConfigManager:
    """Manages display configuration persistence via display.json."""

    def __init__(self, config_file: str | os.PathLike[str] | None = None) -> None:
        path = (
            Path(config_file).expanduser() if config_file is not None else get_default_config_path()
        )
        if not path.is_absolute():
            path = Path.cwd() / path
        self._config_path = str(path.absolute())
        self._config: dict[str, Any] = {}

    @property
    def config_path(self) -> str:
        """Path to the configuration file."""
        return self._config_path

    def load(self) -> dict[str, Any]:
        """Load configuration from display.json."""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r", encoding="utf-8") as file_handle:
                    self._config = json.load(file_handle)
            except (json.JSONDecodeError, OSError):
                self._config = DEFAULT_CONFIG.copy()
        else:
            self._config = DEFAULT_CONFIG.copy()
        return self._config

    def save(self) -> None:
        """Save current configuration to display.json."""
        Path(self._config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as file_handle:
            json.dump(self._config, file_handle, indent=4)
            file_handle.write("\n")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        if not self._config:
            self.load()
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save."""
        if not self._config:
            self.load()
        self._config[key] = value
        self.save()

    def export_config(self, export_path: str) -> None:
        """Export configuration to another file."""
        if not self._config:
            self.load()
        with open(export_path, "w", encoding="utf-8") as file_handle:
            json.dump(self._config, file_handle, indent=4)
            file_handle.write("\n")

    def import_config(self, import_path: str) -> dict[str, Any]:
        """Import configuration from another file and save it locally."""
        with open(import_path, "r", encoding="utf-8") as file_handle:
            self._config = json.load(file_handle)
        self.save()
        return self._config

    def init_config(self, interactive: bool = True) -> dict[str, Any]:
        """Initialize display configuration."""
        if not interactive:
            self._config = DEFAULT_CONFIG.copy()
            self.save()
            return self._config

        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║               pi5disp — Display Initialization               ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()

        print("Select your display module:")
        profiles = list(DISPLAY_PROFILES.items())
        for index, (_key, profile) in enumerate(profiles, 1):
            print(f"  {index}. {profile['name']}")

        choice = _prompt_int("Choice", 1, 1, len(profiles))
        profile_key = profiles[choice - 1][0]
        profile = DISPLAY_PROFILES[profile_key]

        print()
        print("--- Pin Configuration (BCM GPIO numbers) ---")
        print()
        dc_pin = _prompt_int("  DC pin", DEFAULT_PINS["dc_pin"], 0, 27)
        rst_pin = _prompt_int("  RST pin", DEFAULT_PINS["rst_pin"], 0, 27)
        blk_pin = _prompt_int("  BLK pin", DEFAULT_PINS["backlight_pin"], 0, 27)

        print()
        print("--- Display Settings ---")
        print()
        rotation = _prompt_choice("  Rotation (0/90/180/270)", 90, [0, 90, 180, 270])
        brightness = _prompt_int("  Brightness (0-100%)", 100, 0, 100)

        self._config = {
            "display_profile": profile_key,
            "dc_pin": dc_pin,
            "rst_pin": rst_pin,
            "backlight_pin": blk_pin,
            "width": profile["width"],
            "height": profile["height"],
            "rotation": rotation,
            "brightness": brightness,
            "spi_speed_mhz": profile["speed_hz"] // 1_000_000,
        }
        self.save()

        print()
        print(f"✅ Configuration saved to {os.path.basename(self._config_path)}")
        print()
        print(f"  Display:    {profile['name']}")
        print(f"  Resolution: {profile['width']} × {profile['height']}")
        print(f"  Pins:       DC={dc_pin}, RST={rst_pin}, BLK={blk_pin}")
        print(f"  Rotation:   {rotation}°")
        print(f"  Brightness: {brightness}%")
        print()

        return self._config
