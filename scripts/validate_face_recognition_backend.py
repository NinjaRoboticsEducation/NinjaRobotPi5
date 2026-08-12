#!/usr/bin/env python3
"""Validate the non-hardware OpenCV API required by pi5camera recognition."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


def validate_backend() -> dict[str, str]:
    """Return diagnostic details or raise with an actionable compatibility error."""
    cv2: Any = importlib.import_module("cv2")
    version = str(getattr(cv2, "__version__", "unknown"))
    package_path = str(getattr(cv2, "__file__", "unknown"))
    classifier_type = getattr(cv2, "CascadeClassifier", None)
    data = getattr(cv2, "data", None)
    cascade_directory = getattr(data, "haarcascades", None)
    if classifier_type is None or not isinstance(cascade_directory, str):
        raise RuntimeError(
            "Incompatible OpenCV installation. NinjaRobot face recognition requires "
            "opencv-python-headless>=4.8,<5 and no competing OpenCV wheel. Run "
            "'uv sync --frozen --extra hardware', then restart the agent service. "
            f"Detected cv2 {version} at {package_path}."
        )
    cascade_path = Path(cascade_directory) / "haarcascade_frontalface_alt2.xml"
    classifier = classifier_type(str(cascade_path))
    if not cascade_path.is_file() or classifier.empty():
        raise RuntimeError(
            "OpenCV loaded, but its frontal-face Haar cascade is unavailable. Run "
            "'uv sync --frozen --extra hardware', then restart the agent service. "
            f"Expected {cascade_path}."
        )
    return {
        "opencv_version": version,
        "opencv_path": package_path,
        "cascade_path": str(cascade_path),
        "status": "ready",
    }


def main() -> int:
    try:
        details = validate_backend()
    except (ImportError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "PASS: face-recognition backend is ready "
        f"(OpenCV {details['opencv_version']}, {details['cascade_path']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
