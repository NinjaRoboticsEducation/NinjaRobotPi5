"""Pending-recognition record management for pi5camera."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

from pi5camera.errors import StorageError
from pi5camera.models import FaceBoundingBox


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PendingRecordManager:
    """Lifecycle management for pending-recognition records."""

    def __init__(self, config: dict[str, Any]) -> None:
        paths = config.get("paths", {})
        recognition = config.get("recognition", {})
        self.data_dir = Path(str(paths["data_dir"])).expanduser().resolve()
        self.pending_dir = self.data_dir / "pending"
        self.pending_ttl_seconds = int(recognition.get("pending_ttl_seconds", 86_400))
        self.save_unknown_crops = bool(recognition.get("save_unknown_crops", True))

    def ensure_layout(self) -> None:
        """Create the pending records directory."""
        try:
            self.pending_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Could not create pending directory: {exc}") from exc

    def purge_expired(self) -> None:
        """Delete expired pending-recognition records."""
        self.ensure_layout()
        if not self.pending_dir.exists():
            return
        for record_dir in self.pending_dir.iterdir():
            if not record_dir.is_dir():
                continue
            record_path = record_dir / "record.json"
            try:
                with record_path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (OSError, json.JSONDecodeError):
                shutil.rmtree(record_dir, ignore_errors=True)
                continue
            expires_at = str(payload.get("expires_at", "")).strip()
            if not expires_at:
                continue
            try:
                expiry = datetime.fromisoformat(expires_at)
            except ValueError:
                shutil.rmtree(record_dir, ignore_errors=True)
                continue
            if _utc_now() >= expiry:
                shutil.rmtree(record_dir, ignore_errors=True)

    def _save_crop(self, source_image: Path, box: FaceBoundingBox, destination: Path) -> Path:
        """Crop a face from *source_image* and save it to *destination*."""
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source_image) as image:
                cropped = image.crop(box.as_crop_box())
                cropped.save(destination)
        except OSError as exc:
            raise StorageError(f"Could not save pending face crop '{destination}': {exc}") from exc
        return destination

    def save_pending_recognition(
        self,
        *,
        photo_path: Path,
        photo_metadata: dict[str, Any],
        unknown_faces: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Persist unknown-face context for later enrollment."""
        self.ensure_layout()
        self.purge_expired()

        recognition_id = uuid4().hex
        record_dir = self.pending_dir / recognition_id
        record_dir.mkdir(parents=True, exist_ok=True)

        stored_faces: list[dict[str, Any]] = []
        for face in unknown_faces:
            face_id = str(face["face_id"])
            crop_path = None
            if self.save_unknown_crops:
                crop_destination = record_dir / f"{face_id}.jpg"
                crop_path = str(
                    self._save_crop(
                        photo_path,
                        FaceBoundingBox.from_dict(face["bounding_box"]),
                        crop_destination,
                    )
                )
            stored_face = dict(face)
            stored_face["crop_path"] = crop_path
            stored_faces.append(stored_face)

        now = _utc_now()
        payload = {
            "recognition_id": recognition_id,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.pending_ttl_seconds)).isoformat(),
            "photo_path": str(photo_path),
            "photo_metadata": dict(photo_metadata),
            "faces": stored_faces,
        }
        record_path = record_dir / "record.json"
        try:
            with record_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            raise StorageError(
                f"Could not write pending recognition '{record_path}': {exc}"
            ) from exc
        return payload

    def load_pending_record(self, recognition_id: str) -> dict[str, Any]:
        """Load a pending-recognition record by id."""
        self.purge_expired()
        record_path = self.pending_dir / recognition_id / "record.json"
        if not record_path.exists():
            raise StorageError(f"Unknown pending recognition '{recognition_id}'.")
        try:
            with record_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(
                f"Could not read pending recognition '{record_path}': {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise StorageError(f"Pending recognition '{record_path}' must be a JSON object.")
        return payload

    def save_pending_record(self, recognition_id: str, payload: dict[str, Any]) -> None:
        """Update an existing pending-recognition record."""
        record_path = self.pending_dir / recognition_id / "record.json"
        try:
            with record_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            raise StorageError(
                f"Could not update pending recognition '{record_path}': {exc}"
            ) from exc

    def remove_pending_record(self, recognition_id: str) -> None:
        """Delete a pending-recognition record directory."""
        shutil.rmtree(self.pending_dir / recognition_id, ignore_errors=True)
