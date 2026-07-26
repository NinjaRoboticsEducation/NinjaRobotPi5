"""Tests for pi5camera.storage.pending_records."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pi5camera.config.config_manager import CameraConfigManager
from pi5camera.errors import StorageError
from pi5camera.storage.pending_records import PendingRecordManager


def _make_config(tmp_path: Path) -> dict:
    manager = CameraConfigManager(tmp_path / "camera.json")
    return manager.load()


def _write_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), "white").save(path)


def test_save_and_load_pending_record(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    photo = tmp_path / "incoming.jpg"
    _write_photo(photo)

    manager = PendingRecordManager(config)
    result = manager.save_pending_recognition(
        photo_path=photo,
        photo_metadata={"test": True},
        unknown_faces=[
            {
                "face_id": "face-1",
                "index": 1,
                "bounding_box": {"top": 0, "right": 32, "bottom": 32, "left": 0},
                "encoding": [0.1, 0.2, 0.3],
            }
        ],
    )

    assert result["recognition_id"]
    loaded = manager.load_pending_record(result["recognition_id"])
    assert loaded["faces"][0]["face_id"] == "face-1"


def test_remove_pending_record(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    photo = tmp_path / "incoming.jpg"
    _write_photo(photo)

    manager = PendingRecordManager(config)
    result = manager.save_pending_recognition(
        photo_path=photo,
        photo_metadata={},
        unknown_faces=[
            {
                "face_id": "face-1",
                "index": 1,
                "bounding_box": {"top": 0, "right": 32, "bottom": 32, "left": 0},
                "encoding": [0.1],
            }
        ],
    )
    manager.remove_pending_record(result["recognition_id"])

    with pytest.raises(StorageError, match="Unknown pending recognition"):
        manager.load_pending_record(result["recognition_id"])
