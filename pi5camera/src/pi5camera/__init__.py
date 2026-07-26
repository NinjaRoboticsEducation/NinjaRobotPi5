"""Public package exports for pi5camera.

The package keeps all hardware and image-processing imports lazy so
lightweight commands such as ``uv run pi5camera --help`` do not depend
on Pillow, OpenCV, MediaPipe, or Picamera2 loading successfully at
startup.
"""

from __future__ import annotations

from pi5camera.config.config_manager import (  # noqa: F401
    CONFIG_FILE_NAME,
    DEFAULT_CONFIG,
    CameraConfigManager,
    get_default_config_filepath,
)


def __getattr__(name: str):  # noqa: C901
    """Lazily resolve heavy symbols on first access."""
    if name == "capture_photo":
        from pi5camera.core.capture import capture_photo

        return capture_photo
    if name == "enroll_face_from_image":
        from pi5camera.core.enrollment import enroll_face_from_image

        return enroll_face_from_image
    if name == "enroll_pending_face":
        from pi5camera.core.enrollment import enroll_pending_face

        return enroll_pending_face
    if name == "recognize_faces":
        from pi5camera.core.recognition import recognize_faces

        return recognize_faces
    if name == "FaceStore":
        from pi5camera.storage.face_index import FaceIndex

        return FaceIndex
    raise AttributeError(f"module 'pi5camera' has no attribute {name!r}")
