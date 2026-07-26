"""Shared dataclasses and helpers for pi5camera."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def deep_copy_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of nested config-style data."""
    return deepcopy(data)


def microsecond_timestamp() -> str:
    """Return a UTC timestamp with microsecond resolution for unique filenames."""
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


@dataclass(slots=True)
class FaceBoundingBox:
    """A face bounding box in (top, right, bottom, left) format."""

    top: int
    right: int
    bottom: int
    left: int

    def as_crop_box(self) -> tuple[int, int, int, int]:
        """Return a Pillow-friendly crop box (left, top, right, bottom)."""
        return (self.left, self.top, self.right, self.bottom)

    def to_dict(self) -> dict[str, int]:
        """Serialize the bounding box."""
        return {
            "top": int(self.top),
            "right": int(self.right),
            "bottom": int(self.bottom),
            "left": int(self.left),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FaceBoundingBox":
        """Build a bounding box from plain data."""
        return cls(
            top=int(payload["top"]),
            right=int(payload["right"]),
            bottom=int(payload["bottom"]),
            left=int(payload["left"]),
        )


@dataclass(slots=True)
class FaceResult:
    """A normalized face-recognition result."""

    face_id: str
    index: int
    bounding_box: FaceBoundingBox
    status: str
    name: str | None = None
    match_distance: float | None = None
    crop_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the face result."""
        return {
            "face_id": self.face_id,
            "index": self.index,
            "bounding_box": self.bounding_box.to_dict(),
            "status": self.status,
            "name": self.name,
            "match_distance": self.match_distance,
            "crop_path": self.crop_path,
        }


@dataclass(slots=True)
class EncodedFace:
    """A face detection paired with its numeric embedding."""

    bounding_box: FaceBoundingBox
    encoding: list[float]


@dataclass(slots=True)
class CaptureResult:
    """A captured photo plus optional camera metadata."""

    path: Path
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the capture result."""
        return {
            "path": str(self.path),
            "metadata": deep_copy_dict(self.metadata),
        }
