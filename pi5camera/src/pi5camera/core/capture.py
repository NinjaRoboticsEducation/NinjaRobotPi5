"""One-shot still capture helpers for pi5camera."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pi5camera.core.camera_backend import build_camera_backend
from pi5camera.errors import CaptureError
from pi5camera.models import CaptureResult, microsecond_timestamp
from pi5camera.storage.photo_storage import PhotoStorage


def build_output_path(
    config: dict[str, Any],
    *,
    output_path: Path | None = None,
    filename_prefix: str = "photo",
) -> Path:
    """Build the output path for a captured still image."""
    if output_path is not None:
        resolved = output_path.expanduser().resolve()
        if resolved.suffix:
            return resolved
        timestamp = microsecond_timestamp()
        return resolved / f"{filename_prefix}-{timestamp}.jpg"

    storage = PhotoStorage(config)
    return storage.create_photo_path(prefix=filename_prefix)


def capture_photo(
    config: dict[str, Any],
    *,
    output_path: Path | None = None,
    filename_prefix: str = "photo",
) -> CaptureResult:
    """Capture one still photo and return the saved file path plus metadata."""
    destination = build_output_path(
        config, output_path=output_path, filename_prefix=filename_prefix
    )
    try:
        with build_camera_backend(config) as backend:
            return backend.capture(destination)
    except CaptureError:
        raise
    except OSError as exc:
        raise CaptureError(
            f"Could not create the output photo path '{destination}': {exc}"
        ) from exc
