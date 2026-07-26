"""Shared CLI helpers for pi5camera."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pi5camera.config.config_manager import CameraConfigManager
from pi5camera.environment import describe_camera_environment
from pi5camera.errors import ConfigError


def load_manager(config_file: Path | str | None) -> CameraConfigManager:
    """Create and load a config manager for the given path."""
    manager = CameraConfigManager(config_file)
    manager.load()
    return manager


def describe_camera_stack(config: dict[str, Any]) -> dict[str, Any]:
    """Summarize camera and recognition backend readiness."""
    camera_config = config.get("camera")
    recognition_config = config.get("recognition")
    paths = config.get("paths")
    if not isinstance(camera_config, dict):
        raise ConfigError("Config key 'camera' must be an object.")
    if not isinstance(recognition_config, dict):
        raise ConfigError("Config key 'recognition' must be an object.")
    if not isinstance(paths, dict):
        raise ConfigError("Config key 'paths' must be an object.")

    env = describe_camera_environment()
    return {
        "photo_dir": str(paths["photo_dir"]),
        "data_dir": str(paths["data_dir"]),
        "camera_backend": str(camera_config.get("backend", "picamera2")),
        "camera_backend_available": env["camera_backend_available"],
        "camera_backend_state": env["camera_backend_state"],
        "camera_backend_help_text": env["camera_backend_help_text"],
        "python_executable": env["python_executable"],
        "is_raspberry_pi": env["is_raspberry_pi"],
        "recognition_backend": str(recognition_config.get("backend", "mediapipe_opencv")),
        "recognition_backend_available": env["recognition_backend_available"],
        "recognition_backend_state": env["recognition_backend_state"],
        "recognition_backend_help_text": env["recognition_backend_help_text"],
        "detection_mode": env["detection_mode"],
        "resolution": {
            "width": int(camera_config.get("width", 1280)),
            "height": int(camera_config.get("height", 720)),
        },
        "warmup_seconds": float(camera_config.get("warmup_seconds", 1.0)),
    }
