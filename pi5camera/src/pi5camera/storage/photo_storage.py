"""Photo storage helpers for pi5camera."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pi5camera.errors import StorageError
from pi5camera.models import microsecond_timestamp


class PhotoStorage:
    """Manage photo output paths and directory layout."""

    def __init__(self, config: dict[str, Any]) -> None:
        paths = config.get("paths", {})
        self.photo_dir = Path(str(paths["photo_dir"])).expanduser().resolve()

    def ensure_layout(self) -> None:
        """Create the photo directory if it does not exist."""
        try:
            self.photo_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Could not create photo directory: {exc}") from exc

    def create_photo_path(self, *, prefix: str = "photo") -> Path:
        """Create a timestamped output path in the configured photo directory."""
        self.ensure_layout()
        return self.photo_dir / f"{prefix}-{microsecond_timestamp()}.jpg"
