"""JSON configuration management for pi5buzzer."""

from __future__ import annotations

import json
import logging
import os
import shutil
from typing import Any, Optional

try:
    from ninja_utils import get_logger

    log = get_logger(__name__)
except ImportError:
    log = logging.getLogger(__name__)


DEFAULT_CONFIG: dict[str, Any] = {
    "pin": 17,
    "volume": 128,
}

_MIN_PIN = 0
_MAX_PIN = 27
_MIN_VOLUME = 0
_MAX_VOLUME = 255


def get_default_config_filepath() -> str:
    """Return the default config file path."""
    return os.path.join(os.getcwd(), "buzzer.json")


class BuzzerConfigManager:
    """Manage `buzzer.json` compatibility for the standalone pi5buzzer package."""

    def __init__(self, config_path: Optional[str] = None):
        self.path = config_path or get_default_config_filepath()
        self._config: dict[str, Any] = dict(DEFAULT_CONFIG)

    @property
    def config(self) -> dict[str, Any]:
        """Return a copy of the current configuration."""
        return dict(self._config)

    def load(self) -> dict[str, Any]:
        """Load configuration from disk, falling back to defaults when needed."""
        if not os.path.exists(self.path):
            log.info("Config file not found: %s. Using defaults.", self.path)
            self._config = dict(DEFAULT_CONFIG)
            return self.config

        try:
            with open(self.path, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Failed to load config from %s: %s", self.path, exc)
            self._config = dict(DEFAULT_CONFIG)
            return self.config

        if not isinstance(data, dict):
            log.warning("Invalid config format. Using defaults.")
            self._config = dict(DEFAULT_CONFIG)
            return self.config

        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        self._config = merged
        log.info("Config loaded from %s", self.path)
        return self.config

    def save(self) -> None:
        """Persist the current configuration to disk."""
        try:
            parent = os.path.dirname(self.path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            with open(self.path, "w", encoding="utf-8") as file_obj:
                json.dump(self._config, file_obj, indent=2)

            log.info("Config saved to %s", self.path)
        except OSError as exc:
            log.error("Failed to save config to %s: %s", self.path, exc)

    def get_pin(self) -> int:
        """Return the configured GPIO pin number."""
        return self._config.get("pin", DEFAULT_CONFIG["pin"])

    def set_pin(self, pin: int) -> None:
        """Set the GPIO pin number."""
        if not (_MIN_PIN <= pin <= _MAX_PIN):
            raise ValueError(f"Pin must be between {_MIN_PIN} and {_MAX_PIN}, got {pin}")

        self._config["pin"] = pin

    def get_volume(self) -> int:
        """Return the configured PWM volume."""
        return self._config.get("volume", DEFAULT_CONFIG["volume"])

    def set_volume(self, volume: int) -> None:
        """Set the PWM volume in the 0..255 range."""
        if not (_MIN_VOLUME <= volume <= _MAX_VOLUME):
            raise ValueError(
                f"Volume must be between {_MIN_VOLUME} and {_MAX_VOLUME}, got {volume}"
            )

        self._config["volume"] = volume

    def export_config(self, path: str) -> None:
        """Export configuration to another JSON file."""
        try:
            self.save()
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(self.path, path)
            log.info("Config exported to %s", path)
        except OSError as exc:
            log.error("Failed to export config: %s", exc)
            raise

    def import_config(self, path: str) -> None:
        """Import configuration from another JSON file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Failed to import config from %s: %s", path, exc)
            raise

        if not isinstance(data, dict):
            raise ValueError("Invalid config format in imported file.")

        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        self._config = merged
        log.info("Config imported from %s", path)

    def init_config(self, pin: int) -> None:
        """Initialize configuration with the given pin and save it."""
        self.set_pin(pin)
        self.save()
        log.info("Buzzer config initialized: pin=%s", pin)
