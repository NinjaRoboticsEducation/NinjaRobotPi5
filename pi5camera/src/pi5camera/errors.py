"""Shared exceptions for pi5camera."""

from __future__ import annotations


class CameraError(Exception):
    """Base exception for pi5camera failures."""


class ConfigError(CameraError):
    """Raised when the camera config is invalid or unreadable."""


class CaptureError(CameraError):
    """Raised when still-image capture fails."""


class RecognitionError(CameraError):
    """Raised when face-recognition processing fails."""


class EnrollmentError(CameraError):
    """Raised when known-face enrollment fails."""


class StorageError(CameraError):
    """Raised when camera files or indexes cannot be saved or loaded."""


class BackendNotAvailableError(CameraError):
    """Raised when a required backend (camera or recognition) is not importable."""
