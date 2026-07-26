"""Face-recognition workflow for pi5camera."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from pi5camera.core.capture import capture_photo
from pi5camera.errors import RecognitionError
from pi5camera.models import CaptureResult, EncodedFace, FaceResult
from pi5camera.recognition.mediapipe_opencv_backend import build_recognition_backend
from pi5camera.storage.face_index import FaceIndex
from pi5camera.storage.pending_records import PendingRecordManager


def _euclidean_distance(encoding_a: list[float], encoding_b: list[float]) -> float:
    """Compute Euclidean distance between two face embeddings."""
    if len(encoding_a) != len(encoding_b):
        return float("inf")
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(encoding_a, encoding_b)))


def _best_known_match(
    encoding: list[float],
    known_entries: list[dict[str, Any]],
    tolerance: float,
) -> tuple[str | None, float | None]:
    """Find the best matching known face within tolerance."""
    best_name: str | None = None
    best_distance: float | None = None

    for entry in known_entries:
        known_encoding = entry.get("encoding", [])
        if not known_encoding:
            continue
        distance = _euclidean_distance(encoding, known_encoding)
        if distance <= tolerance and (best_distance is None or distance < best_distance):
            best_name = str(entry.get("name", ""))
            best_distance = distance

    return best_name, best_distance


def recognize_faces(
    config: dict[str, Any],
    *,
    image_path: Path | None = None,
) -> dict[str, Any]:
    """Run one face-recognition cycle.

    If *image_path* is ``None`` a photo is captured first.
    """
    recognition_config = config.get("recognition", {})
    tolerance = float(recognition_config.get("tolerance", 0.6))

    # Build the backend first — fail fast before capturing.
    try:
        backend = build_recognition_backend(config)
    except Exception as exc:
        raise RecognitionError(f"Recognition backend unavailable: {exc}") from exc

    # Capture or load photo.
    if image_path is None:
        result: CaptureResult = capture_photo(config, filename_prefix="recognize")
        photo_path = result.path
        photo_metadata = result.metadata
    else:
        photo_path = Path(image_path).expanduser().resolve()
        if not photo_path.exists():
            raise RecognitionError(f"Image file does not exist: {photo_path}")
        photo_metadata: dict[str, Any] = {}

    # Detect and encode.
    try:
        detected: list[EncodedFace] = backend.detect_and_encode(photo_path)
    except RecognitionError:
        raise
    except Exception as exc:
        raise RecognitionError(f"Face detection failed: {exc}") from exc

    # Load known faces for comparison.
    index = FaceIndex(config)
    known_entries = index.load_known_entries()

    face_results: list[FaceResult] = []
    unknown_faces: list[dict[str, Any]] = []
    recognized_names: list[str] = []

    for i, encoded_face in enumerate(detected, start=1):
        face_id = f"face-{i}"
        name, distance = _best_known_match(encoded_face.encoding, known_entries, tolerance)

        if name:
            face_results.append(
                FaceResult(
                    face_id=face_id,
                    index=i,
                    bounding_box=encoded_face.bounding_box,
                    status="known",
                    name=name,
                    match_distance=distance,
                )
            )
            recognized_names.append(name)
        else:
            face_results.append(
                FaceResult(
                    face_id=face_id,
                    index=i,
                    bounding_box=encoded_face.bounding_box,
                    status="unknown",
                )
            )
            unknown_faces.append(
                {
                    "face_id": face_id,
                    "index": i,
                    "bounding_box": encoded_face.bounding_box.to_dict(),
                    "encoding": encoded_face.encoding,
                }
            )

    # Save pending record if there are unknown faces.
    recognition_id: str | None = None
    if unknown_faces:
        pending_manager = PendingRecordManager(config)
        pending_data = pending_manager.save_pending_recognition(
            photo_path=photo_path,
            photo_metadata=photo_metadata,
            unknown_faces=unknown_faces,
        )
        recognition_id = pending_data["recognition_id"]

        # Update face results with crop paths.
        face_id_to_crop = {face["face_id"]: face.get("crop_path") for face in pending_data["faces"]}
        for face_result in face_results:
            if face_result.status == "unknown":
                face_result.crop_path = face_id_to_crop.get(face_result.face_id)

    return {
        "photo_path": str(photo_path),
        "face_count": len(face_results),
        "recognized_names": recognized_names,
        "needs_enrollment": bool(unknown_faces),
        "unknown_count": len(unknown_faces),
        "recognition_id": recognition_id,
        "faces": [face.to_dict() for face in face_results],
    }
