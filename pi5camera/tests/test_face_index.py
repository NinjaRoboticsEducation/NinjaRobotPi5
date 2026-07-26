"""Tests for pi5camera.storage.face_index."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pi5camera.config.config_manager import CameraConfigManager
from pi5camera.models import FaceBoundingBox
from pi5camera.storage.face_index import FaceIndex


def _make_config(tmp_path: Path) -> dict:
    manager = CameraConfigManager(tmp_path / "camera.json")
    return manager.load()


def _write_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), "white").save(path)


def test_save_and_list_known_faces(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    photo = tmp_path / "test.jpg"
    _write_photo(photo)

    index = FaceIndex(config)
    index.save_known_face(
        name="Alice",
        source_image=photo,
        box=FaceBoundingBox(top=0, right=32, bottom=32, left=0),
        encoding=[0.1, 0.2, 0.3],
    )
    assert index.list_known_faces() == ["Alice"]


def test_remove_known_face(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    photo = tmp_path / "test.jpg"
    _write_photo(photo)

    index = FaceIndex(config)
    index.save_known_face(
        name="Bob",
        source_image=photo,
        box=FaceBoundingBox(top=0, right=32, bottom=32, left=0),
        encoding=[0.4, 0.5, 0.6],
    )
    assert index.remove_known_face("Bob") is True
    assert index.list_known_faces() == []
    assert index.remove_known_face("Bob") is False


def test_load_known_entries_returns_encoding(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    photo = tmp_path / "test.jpg"
    _write_photo(photo)

    index = FaceIndex(config)
    index.save_known_face(
        name="Charlie",
        source_image=photo,
        box=FaceBoundingBox(top=0, right=32, bottom=32, left=0),
        encoding=[0.7, 0.8, 0.9],
    )
    entries = index.load_known_entries()
    assert len(entries) == 1
    assert entries[0]["name"] == "Charlie"
    assert entries[0]["encoding"] == [0.7, 0.8, 0.9]
