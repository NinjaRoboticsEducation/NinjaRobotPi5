"""Configuration management for pi5mic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pi5mic.errors import ConfigError
from pi5mic.integration.openclaw_session import (
    DEFAULT_OPENCLAW_SESSION_ID,
    normalize_openclaw_session_id,
)
from pi5mic.models import deep_copy_dict

CONFIG_FILE_NAME = "mic.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "profile": "standalone",
    "audio": {
        "input_device": None,
        "sample_rate": 16_000,
        "channels": 1,
        "sample_width_bytes": 2,
        "block_size": 1_024,
        "max_clip_seconds": 12.0,
        "silence_timeout_seconds": 1.2,
    },
    "wakeword": {
        "enabled": False,
        "backend": "openwakeword",
        "keyword": "ninja",
        "model_path": None,
        "threshold": 0.5,
        "vad_threshold": 0.0,
        "enable_noise_suppression": False,
        "inference_framework": "auto",
    },
    "voiceinput": {
        "enabled": False,
        "silence_timeout_seconds": 3.0,
        "max_capture_seconds": 10.0,
        "cooldown_seconds": 1.5,
        "vad_rms_threshold": 200.0,
        "session_strategy": "agent_main",
    },
    "stt": {
        "selected": "whisper_cpp",
        "whisper_cpp": {
            "command": None,
            "model_path": None,
            "language": "auto",
            "translate_to_english": False,
            "threads": None,
            "timeout_seconds": 120,
        },
        "gemini": {
            "model": "gemini-2.5-flash",
            "timeout_seconds": 60,
            "retry_limit": 2,
        },
    },
    "integration": {
        "presence_enabled": True,
        "delivery_mode": "local_only",
        "openclaw": {
            "command": None,
            "gateway_url": "ws://127.0.0.1:18789",
            "agent_id": "main",
            "session_key": DEFAULT_OPENCLAW_SESSION_ID,
            "session_strategy": "dedicated_mic",
            "request_timeout_seconds": 180,
            "presence_timeout_seconds": 3,
            "reply_channel": None,
            "reply_to": None,
            "reply_account": None,
        },
    },
    "retention": {
        "keep_temp_audio": False,
        "max_age_seconds": 0,
    },
}


def get_default_config_filepath() -> Path:
    """Return the default `mic.json` path."""
    return Path.cwd() / CONFIG_FILE_NAME


def _merge_config(
    defaults: dict[str, Any], overrides: dict[str, Any], *, path: str
) -> dict[str, Any]:
    merged = deep_copy_dict(defaults)

    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], dict):
            if value is None:
                merged[key] = None
                continue
            if not isinstance(value, dict):
                raise ConfigError(f"Expected '{path}.{key}' to be an object.")
            merged[key] = _merge_config(merged[key], value, path=f"{path}.{key}")
            continue
        merged[key] = value

    return merged


def _apply_runtime_migrations(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy config values that are known to break current runtimes."""
    integration = config.get("integration")
    if isinstance(integration, dict):
        openclaw = integration.get("openclaw")
        if isinstance(openclaw, dict):
            openclaw["session_key"] = normalize_openclaw_session_id(openclaw.get("session_key"))

    wakeword = config.get("wakeword")
    if isinstance(wakeword, dict):
        legacy_backend = str(wakeword.get("backend", "") or "").strip().lower()
        if legacy_backend in {"", "porcupine"}:
            wakeword["backend"] = "openwakeword"
        if not wakeword.get("model_path"):
            legacy_keyword_path = str(wakeword.get("keyword_path", "") or "").strip()
            wakeword["model_path"] = (
                legacy_keyword_path
                if legacy_keyword_path.lower().endswith((".onnx", ".tflite"))
                else None
            )
        wakeword.setdefault("threshold", 0.5)
        wakeword.setdefault("vad_threshold", 0.0)
        wakeword.setdefault("enable_noise_suppression", False)
        wakeword.setdefault("inference_framework", "auto")
        wakeword.pop("keyword_path", None)
        wakeword.pop("access_key_env_var", None)

    return config


class MicConfigManager:
    """Manage `mic.json` loading, saving, export, and import."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._path = get_default_config_filepath() if config_path is None else Path(config_path)
        self._config = deep_copy_dict(DEFAULT_CONFIG)

    @property
    def path(self) -> Path:
        """The config file path."""
        return self._path

    @property
    def config(self) -> dict[str, Any]:
        """Return a copy of the current config."""
        return deep_copy_dict(self._config)

    def load(self) -> dict[str, Any]:
        """Load config from disk, or defaults if the file is missing."""
        if not self._path.exists():
            self._config = deep_copy_dict(DEFAULT_CONFIG)
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

        self._config = _apply_runtime_migrations(_merge_config(DEFAULT_CONFIG, data, path="config"))
        return self.config

    def save(self) -> None:
        """Write the current config to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as handle:
                json.dump(self._config, handle, indent=2)
        except OSError as exc:
            raise ConfigError(f"Could not write config file '{self._path}': {exc}") from exc

    def replace(self, config: dict[str, Any]) -> dict[str, Any]:
        """Replace the active config after validating its structure."""
        if not isinstance(config, dict):
            raise ConfigError("Config replacement payload must be a JSON object.")
        self._config = _apply_runtime_migrations(
            _merge_config(DEFAULT_CONFIG, config, path="config")
        )
        return self.config

    def export_config(self, export_path: Path | str) -> Path:
        """Export the current config to a different path."""
        destination = Path(export_path)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", encoding="utf-8") as handle:
                json.dump(self._config, handle, indent=2)
        except OSError as exc:
            raise ConfigError(f"Could not export config to '{destination}': {exc}") from exc
        return destination

    def import_config(self, import_path: Path | str) -> dict[str, Any]:
        """Import config from another JSON file."""
        source = Path(import_path)
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

        self.replace(data)
        return self.config
