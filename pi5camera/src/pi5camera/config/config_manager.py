"""Configuration management for pi5camera."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pi5camera.errors import ConfigError
from pi5camera.models import deep_copy_dict

CONFIG_FILE_NAME = "camera.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "camera": {
        "backend": "picamera2",
        "width": 1280,
        "height": 720,
        "warmup_seconds": 1.0,
        "use_preview": False,
        "autofocus_mode": "continuous",
    },
    "recognition": {
        "backend": "mediapipe_opencv",
        "tolerance": 0.6,
        "save_unknown_crops": True,
        "pending_ttl_seconds": 86_400,
    },
    "paths": {
        "photo_dir": None,
        "data_dir": None,
    },
    "retention": {
        "keep_photo_captures": True,
        "keep_pending_crops": True,
    },
}


def get_default_config_filepath() -> Path:
    """Return the default ``camera.json`` path relative to cwd."""
    return Path.cwd() / CONFIG_FILE_NAME


def _merge_config(
    defaults: dict[str, Any],
    overrides: dict[str, Any],
    *,
    path: str,
) -> dict[str, Any]:
    """Deep-merge *overrides* into *defaults* with validation."""
    merged = deep_copy_dict(defaults)
    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], dict):
            if value is None:
                # Keep the default dict rather than nullifying the section.
                continue
            if not isinstance(value, dict):
                raise ConfigError(
                    f"Expected '{path}.{key}' to be an object, got {type(value).__name__}."
                )
            merged[key] = _merge_config(merged[key], value, path=f"{path}.{key}")
            continue
        merged[key] = value
    return merged


def _normalize_absolute_dir(raw_value: Any, fallback: Path) -> str:
    """Resolve a directory value to an absolute string path."""
    if raw_value in (None, ""):
        return str(fallback)
    return str(Path(str(raw_value)).expanduser().resolve())


def _apply_runtime_defaults(config: dict[str, Any], active_root: Path) -> dict[str, Any]:
    """Fill in root-aware path defaults."""
    paths = config.get("paths")
    if not isinstance(paths, dict):
        raise ConfigError("Config key 'paths' must be an object.")
    paths["photo_dir"] = _normalize_absolute_dir(paths.get("photo_dir"), active_root / "photo")
    paths["data_dir"] = _normalize_absolute_dir(paths.get("data_dir"), active_root / "camera_data")
    return config


class CameraConfigManager:
    """Manage ``camera.json`` loading, saving, export, and import."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._path = (
            (get_default_config_filepath() if config_path is None else Path(config_path))
            .expanduser()
            .resolve()
        )
        self._config = deep_copy_dict(DEFAULT_CONFIG)

    @property
    def path(self) -> Path:
        """Return the config file path."""
        return self._path

    @property
    def active_root(self) -> Path:
        """Return the active project root derived from the config path."""
        return self._path.parent.resolve()

    @property
    def default_photo_dir(self) -> Path:
        """Return the root-aware default photo directory."""
        return self.active_root / "photo"

    @property
    def default_data_dir(self) -> Path:
        """Return the root-aware default camera data directory."""
        return self.active_root / "camera_data"

    @property
    def config(self) -> dict[str, Any]:
        """Return a deep copy of the active config."""
        return deep_copy_dict(self._config)

    def load(self) -> dict[str, Any]:
        """Load config from disk or return defaults when the file is missing."""
        if not self._path.exists():
            self._config = _apply_runtime_defaults(
                deep_copy_dict(DEFAULT_CONFIG),
                self.active_root,
            )
            return self.config

        try:
            with self._path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Config file '{self._path}' is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Could not read config file '{self._path}': {exc}") from exc

        if not isinstance(data, dict):
            raise ConfigError(f"Config file '{self._path}' must contain a JSON object.")

        self._config = _apply_runtime_defaults(
            _merge_config(DEFAULT_CONFIG, data, path="config"),
            self.active_root,
        )
        return self.config

    def replace(self, config: dict[str, Any]) -> dict[str, Any]:
        """Replace the active config after validating its structure."""
        if not isinstance(config, dict):
            raise ConfigError("Config replacement payload must be a JSON object.")
        self._config = _apply_runtime_defaults(
            _merge_config(DEFAULT_CONFIG, config, path="config"),
            self.active_root,
        )
        return self.config

    def save(self) -> None:
        """Write the current config to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as handle:
                json.dump(self._config, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            raise ConfigError(f"Could not write config file '{self._path}': {exc}") from exc

    def export_config(self, export_path: Path | str) -> Path:
        """Export the current config to a different path."""
        destination = Path(export_path).expanduser().resolve()
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", encoding="utf-8") as handle:
                json.dump(self._config, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            raise ConfigError(f"Could not export config to '{destination}': {exc}") from exc
        return destination

    def import_config(self, import_path: Path | str) -> dict[str, Any]:
        """Import config from another JSON file."""
        source = Path(import_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"Config file not found: {source}")

        try:
            with source.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Imported config '{source}' is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Could not read imported config '{source}': {exc}") from exc

        if not isinstance(data, dict):
            raise ConfigError(f"Imported config '{source}' must contain a JSON object.")

        self._config = _apply_runtime_defaults(
            _merge_config(DEFAULT_CONFIG, data, path="config"),
            self.active_root,
        )
        return self.config
