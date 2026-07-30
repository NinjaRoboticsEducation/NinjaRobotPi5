"""Exception wrapper for structured IDE errors."""

from __future__ import annotations

from .models import ErrorDetails

HARDWARE_DRIVER_ERROR_CODES = frozenset(
    {
        "BUZZER_PLAY_FAILED",
        "BUZZER_STOP_FAILED",
        "BUZZER_UNAVAILABLE",
        "CAMERA_CAPTURE_FAILED",
        "CAMERA_UNAVAILABLE",
        "DEVICE_READ_FAILED",
        "DEVICE_UNAVAILABLE",
        "DISPLAY_BRIGHTNESS_FAILED",
        "DISPLAY_CLEAR_FAILED",
        "DISPLAY_UNAVAILABLE",
        "DISPLAY_WRITE_FAILED",
        "MICROPHONE_CAPTURE_FAILED",
        "MICROPHONE_UNAVAILABLE",
        "SERVO_CENTER_FAILED",
        "SERVO_ENDPOINT_UNAVAILABLE",
        "SERVO_MOVE_FAILED",
        "SERVO_STOP_FAILED",
        "SERVO_UNAVAILABLE",
    }
)


class IDEError(Exception):
    """Exception that retains a stable, serializable error contract."""

    def __init__(self, details: ErrorDetails) -> None:
        super().__init__(details.message)
        self.details = details


def is_hardware_driver_error(error: Exception) -> bool:
    """Return whether a structured IDE failure represents a real device fault.

    Hardware adapters wrap device-start, communication, and output failures in
    stable IDE error codes. Validation, policy, configuration, and generated
    behavior mistakes must not escalate into a persistent Level 2 system stop.
    """

    return isinstance(error, IDEError) and str(error.details.code) in HARDWARE_DRIVER_ERROR_CODES


def describe_hardware_driver_error(error: Exception) -> str:
    """Return a bounded, operator-facing description for a device failure."""

    if isinstance(error, IDEError):
        details = error.details
        description = f"{details.code}: {details.message}"
        if details.technical_detail:
            description = f"{description} ({details.technical_detail})"
        return description[:1000]
    return f"{type(error).__name__}: {error}"[:1000]
