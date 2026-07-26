"""Placeholder for a future `pwm-pio` backend on Raspberry Pi 5."""

from __future__ import annotations

from ..backend_errors import BackendUnavailableError


class PwmPioServoBackend:
    """Placeholder backend for future stable `pwm-pio` integration."""

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        raise BackendUnavailableError(
            "The pwm-pio backend is planned but not implemented in pi5servo yet. "
            "Use `hardware_pwm` for header-connected servos or `pca9685` for an external controller."
        )
