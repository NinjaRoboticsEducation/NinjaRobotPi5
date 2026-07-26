"""Known-face enrollment workflows for pi5camera."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pi5camera.errors import EnrollmentError, RecognitionError
from pi5camera.models import EncodedFace, FaceBoundingBox
from pi5camera.recognition.mediapipe_opencv_backend import build_recognition_backend
from pi5camera.storage.face_index import FaceIndex
from pi5camera.storage.pending_records import PendingRecordManager


def enroll_pending_face(
    config: dict[str, Any],
    *,
    recognition_id: str,
    face_id: str,
    name: str,
) -> dict[str, Any]:
    """Promote a pending-recognition face to a known identity."""
    if not name.strip():
        raise EnrollmentError("Name must not be empty.")

    pending = PendingRecordManager(config)
    try:
        record = pending.load_pending_record(recognition_id)
    except Exception as exc:
        raise EnrollmentError(
            f"Could not load pending recognition '{recognition_id}': {exc}"
        ) from exc

    faces = record.get("faces", [])
    target_face = None
    for face in faces:
        if str(face.get("face_id")) == face_id:
            target_face = face
            break

    if target_face is None:
        raise EnrollmentError(
            f"Face '{face_id}' not found in pending recognition '{recognition_id}'."
        )

    encoding = target_face.get("encoding", [])
    if not encoding:
        raise EnrollmentError(f"Face '{face_id}' has no encoding data.")

    box = FaceBoundingBox.from_dict(target_face["bounding_box"])
    photo_path = Path(str(record["photo_path"])).expanduser().resolve()

    index = FaceIndex(config)
    saved_path = index.save_known_face(
        name=name,
        source_image=photo_path,
        box=box,
        encoding=encoding,
        crop_path=target_face.get("crop_path"),
    )

    # Remove enrolled face from pending record.
    remaining = [f for f in faces if str(f.get("face_id")) != face_id]
    if remaining:
        record["faces"] = remaining
        pending.save_pending_record(recognition_id, record)
    else:
        pending.remove_pending_record(recognition_id)

    return {
        "name": name.strip(),
        "face_id": face_id,
        "saved_image_path": str(saved_path),
        "pending_remaining": len(remaining),
    }


def enroll_face_from_image(
    config: dict[str, Any],
    *,
    name: str,
    image_path: Path,
) -> dict[str, Any]:
    """Enroll a known face directly from an image file."""
    if not name.strip():
        raise EnrollmentError("Name must not be empty.")

    resolved = Path(image_path).expanduser().resolve()
    if not resolved.exists():
        raise EnrollmentError(f"Image file does not exist: {resolved}")

    try:
        backend = build_recognition_backend(config)
        detected: list[EncodedFace] = backend.detect_and_encode(resolved)
    except RecognitionError:
        raise
    except Exception as exc:
        raise EnrollmentError(f"Face detection failed during enrollment: {exc}") from exc

    if not detected:
        raise EnrollmentError(f"No faces detected in '{resolved}'.")

    face = detected[0]
    index = FaceIndex(config)
    saved_path = index.save_known_face(
        name=name,
        source_image=resolved,
        box=face.bounding_box,
        encoding=face.encoding,
    )

    return {
        "name": name.strip(),
        "face_id": "face-1",
        "saved_image_path": str(saved_path),
        "pending_remaining": 0,
    }
