"""Tests for pi5camera.storage.photo_storage."""

from __future__ import annotations

from pathlib import Path

from pi5camera.config.config_manager import CameraConfigManager
from pi5camera.storage.photo_storage import PhotoStorage


def test_create_photo_path_uses_microsecond_timestamps(tmp_path: Path) -> None:
    manager = CameraConfigManager(tmp_path / "camera.json")
    config = manager.load()

    storage = PhotoStorage(config)
    path_a = storage.create_photo_path(prefix="snap")
    path_b = storage.create_photo_path(prefix="snap")

    assert path_a.parent == (tmp_path / "photo").resolve()
    assert path_a.suffix == ".jpg"
    assert path_a.name.startswith("snap-")
    # Microsecond timestamps should produce different file names.
    assert path_a != path_b


def test_ensure_layout_creates_directory(tmp_path: Path) -> None:
    manager = CameraConfigManager(tmp_path / "camera.json")
    config = manager.load()

    storage = PhotoStorage(config)
    storage.ensure_layout()
    assert storage.photo_dir.is_dir()
