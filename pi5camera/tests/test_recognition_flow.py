"""Tests for the recognition and enrollment workflows."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pi5camera.config.config_manager import CameraConfigManager
from pi5camera.core.enrollment import enroll_pending_face
from pi5camera.core.recognition import recognize_faces
from pi5camera.errors import RecognitionError
from pi5camera.models import EncodedFace, FaceBoundingBox
from pi5camera.storage.face_index import FaceIndex


class FakeBackend:
    def __init__(self, faces: list[EncodedFace]) -> None:
        self._faces = faces

    def detect_and_encode(self, image_path: Path) -> list[EncodedFace]:
        return list(self._faces)


def _make_config(tmp_path: Path) -> dict:
    manager = CameraConfigManager(tmp_path / "camera.json")
    config = manager.load()
    config["camera"]["backend"] = "stub"
    return config


def _write_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), "white").save(path)


def test_recognize_faces_creates_pending_record_for_unknown_face(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _make_config(tmp_path)
    photo_path = tmp_path / "incoming" / "unknown.jpg"
    _write_photo(photo_path)

    encoded_face = EncodedFace(
        bounding_box=FaceBoundingBox(top=8, right=32, bottom=32, left=8),
        encoding=[0.1, 0.2, 0.3],
    )
    monkeypatch.setattr(
        "pi5camera.core.recognition.build_recognition_backend",
        lambda config: FakeBackend([encoded_face]),
    )

    result = recognize_faces(config, image_path=photo_path)

    assert result["needs_enrollment"] is True
    assert result["unknown_count"] == 1
    assert result["recognized_names"] == []
    assert result["recognition_id"] is not None
    assert result["faces"][0]["status"] == "unknown"
    assert result["faces"][0]["face_id"] == "face-1"


def test_recognize_faces_returns_saved_name_for_known_face(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _make_config(tmp_path)
    index = FaceIndex(config)
    index.ensure_layout()

    known_photo = tmp_path / "known.jpg"
    input_photo = tmp_path / "input.jpg"
    _write_photo(known_photo)
    _write_photo(input_photo)

    box = FaceBoundingBox(top=8, right=32, bottom=32, left=8)
    encoding = [0.4, 0.5, 0.6]
    index.save_known_face(
        name="Alice",
        source_image=known_photo,
        box=box,
        encoding=encoding,
    )

    monkeypatch.setattr(
        "pi5camera.core.recognition.build_recognition_backend",
        lambda config: FakeBackend([EncodedFace(bounding_box=box, encoding=encoding)]),
    )

    result = recognize_faces(config, image_path=input_photo)

    assert result["needs_enrollment"] is False
    assert result["recognized_names"] == ["Alice"]
    assert result["faces"][0]["status"] == "known"
    assert result["faces"][0]["name"] == "Alice"
    assert result["recognition_id"] is None


def test_enroll_pending_face_saves_name_and_clears_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _make_config(tmp_path)
    photo_path = tmp_path / "incoming" / "pending.jpg"
    _write_photo(photo_path)

    encoded_face = EncodedFace(
        bounding_box=FaceBoundingBox(top=10, right=30, bottom=30, left=10),
        encoding=[0.7, 0.8, 0.9],
    )
    monkeypatch.setattr(
        "pi5camera.core.recognition.build_recognition_backend",
        lambda config: FakeBackend([encoded_face]),
    )

    recognition_result = recognize_faces(config, image_path=photo_path)
    enrollment_result = enroll_pending_face(
        config,
        recognition_id=recognition_result["recognition_id"],
        face_id="face-1",
        name="Bob",
    )

    assert enrollment_result["name"] == "Bob"
    assert enrollment_result["pending_remaining"] == 0

    index = FaceIndex(config)
    assert index.list_known_faces() == ["Bob"]


def test_recognize_faces_fails_before_capture_when_backend_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _make_config(tmp_path)

    monkeypatch.setattr(
        "pi5camera.core.recognition.build_recognition_backend",
        lambda config: (_ for _ in ()).throw(RecognitionError("backend unavailable")),
    )
    monkeypatch.setattr(
        "pi5camera.core.recognition.capture_photo",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("capture should not run")),
    )

    try:
        recognize_faces(config)
    except RecognitionError as exc:
        assert "backend unavailable" in str(exc)
    else:
        raise AssertionError("recognize_faces should have raised RecognitionError")
