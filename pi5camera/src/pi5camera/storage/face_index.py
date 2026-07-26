"""Known-face index management for pi5camera."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from pi5camera.errors import StorageError
from pi5camera.models import FaceBoundingBox, microsecond_timestamp


def _slugify_name(name: str) -> str:
    """Convert a display name to a safe directory slug."""
    raw = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name.strip())
    return raw.strip("_") or "person"


class FaceIndex:
    """CRUD operations for the known-face encoding index."""

    def __init__(self, config: dict[str, Any]) -> None:
        paths = config.get("paths", {})
        self.data_dir = Path(str(paths["data_dir"])).expanduser().resolve()
        self.known_faces_dir = self.data_dir / "known_faces"
        self.index_dir = self.data_dir / "index"
        self.index_path = self.index_dir / "encodings.json"

    def ensure_layout(self) -> None:
        """Create the index and known-faces directories."""
        try:
            self.known_faces_dir.mkdir(parents=True, exist_ok=True)
            self.index_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Could not create face index directories: {exc}") from exc

    def _load_index(self) -> dict[str, Any]:
        self.ensure_layout()
        if not self.index_path.exists():
            return {"version": 1, "entries": []}
        try:
            with self.index_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Could not read face index '{self.index_path}': {exc}") from exc
        if not isinstance(data, dict):
            raise StorageError(f"Face index '{self.index_path}' must contain a JSON object.")
        entries = data.get("entries")
        if not isinstance(entries, list):
            raise StorageError(f"Face index '{self.index_path}' is missing a valid entries list.")
        return data

    def _save_index(self, payload: dict[str, Any]) -> None:
        try:
            self.index_dir.mkdir(parents=True, exist_ok=True)
            with self.index_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            raise StorageError(f"Could not write face index '{self.index_path}': {exc}") from exc

    def list_known_faces(self) -> list[str]:
        """Return all known saved identity names."""
        index = self._load_index()
        names = {str(entry.get("name", "")).strip() for entry in index["entries"]}
        return sorted(name for name in names if name)

    def load_known_entries(self) -> list[dict[str, Any]]:
        """Return all stored known-face entries."""
        return list(self._load_index()["entries"])

    def remove_known_face(self, name: str) -> bool:
        """Remove all stored data for a known identity."""
        normalized = name.strip()
        if not normalized:
            return False

        index = self._load_index()
        before_count = len(index["entries"])
        index["entries"] = [
            entry for entry in index["entries"] if str(entry.get("name", "")).strip() != normalized
        ]
        if len(index["entries"]) == before_count:
            return False

        self._save_index(index)
        person_dir = self.known_faces_dir / _slugify_name(normalized)
        if person_dir.exists():
            shutil.rmtree(person_dir, ignore_errors=True)
        return True

    def _save_crop(self, source_image: Path, box: FaceBoundingBox, destination: Path) -> Path:
        """Crop a face from an image and save it."""
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source_image) as image:
                cropped = image.crop(box.as_crop_box())
                cropped.save(destination)
        except OSError as exc:
            raise StorageError(f"Could not save face crop '{destination}': {exc}") from exc
        return destination

    def save_known_face(
        self,
        *,
        name: str,
        source_image: Path,
        box: FaceBoundingBox,
        encoding: list[float],
        crop_path: str | None = None,
    ) -> Path:
        """Save an enrolled face crop and append it to the known index."""
        normalized_name = name.strip()
        if not normalized_name:
            raise StorageError("Known face name must not be empty.")

        self.ensure_layout()
        person_dir = self.known_faces_dir / _slugify_name(normalized_name)
        destination = person_dir / f"{microsecond_timestamp()}.jpg"

        if crop_path:
            crop_source = Path(crop_path).expanduser().resolve()
            try:
                person_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(crop_source, destination)
            except OSError as exc:
                raise StorageError(
                    f"Could not copy saved face image to '{destination}': {exc}"
                ) from exc
        else:
            self._save_crop(source_image, box, destination)

        index = self._load_index()
        index["entries"].append(
            {
                "name": normalized_name,
                "encoding": [float(value) for value in encoding],
                "image_path": str(destination),
                "saved_at": datetime.now(UTC).isoformat(),
            }
        )
        self._save_index(index)
        return destination

    def rebuild_index(self) -> dict[str, Any]:
        """Force-reload the index from disk. Returns the fresh index data."""
        return self._load_index()
