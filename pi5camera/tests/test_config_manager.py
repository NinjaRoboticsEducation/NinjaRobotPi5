"""Tests for pi5camera.config.config_manager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pi5camera.config.config_manager import CameraConfigManager
from pi5camera.core.capture import build_output_path
from pi5camera.errors import ConfigError


def test_config_defaults_are_root_aware(tmp_path: Path) -> None:
    config_path = tmp_path / "workspace" / "camera.json"
    manager = CameraConfigManager(config_path)
    config = manager.load()

    assert manager.active_root == config_path.parent.resolve()
    assert Path(config["paths"]["photo_dir"]) == config_path.parent.resolve() / "photo"
    assert Path(config["paths"]["data_dir"]) == config_path.parent.resolve() / "camera_data"


def test_build_output_path_supports_directory_and_file_overrides(tmp_path: Path) -> None:
    manager = CameraConfigManager(tmp_path / "camera.json")
    config = manager.load()

    directory_override = build_output_path(
        config,
        output_path=tmp_path / "exports",
        filename_prefix="snapshot",
    )
    file_override = build_output_path(
        config,
        output_path=tmp_path / "exports" / "named-photo.jpg",
    )

    assert directory_override.parent == (tmp_path / "exports").resolve()
    assert directory_override.name.startswith("snapshot-")
    assert directory_override.suffix == ".jpg"
    assert file_override == (tmp_path / "exports" / "named-photo.jpg").resolve()


def test_load_saves_and_reloads_config(tmp_path: Path) -> None:
    config_path = tmp_path / "camera.json"
    manager = CameraConfigManager(config_path)
    config = manager.load()
    config["camera"]["width"] = 1920
    manager.replace(config)
    manager.save()

    manager2 = CameraConfigManager(config_path)
    config2 = manager2.load()
    assert config2["camera"]["width"] == 1920


def test_null_section_does_not_corrupt_config(tmp_path: Path) -> None:
    config_path = tmp_path / "camera.json"
    config_path.write_text(json.dumps({"paths": None}), encoding="utf-8")

    manager = CameraConfigManager(config_path)
    config = manager.load()
    assert isinstance(config["paths"], dict)
    assert config["paths"]["photo_dir"] is not None


def test_invalid_json_raises_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "camera.json"
    config_path.write_text("{invalid", encoding="utf-8")

    manager = CameraConfigManager(config_path)
    with pytest.raises(ConfigError, match="not valid JSON"):
        manager.load()


def test_non_object_config_raises_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "camera.json"
    config_path.write_text("[]", encoding="utf-8")

    manager = CameraConfigManager(config_path)
    with pytest.raises(ConfigError, match="must contain a JSON object"):
        manager.load()
