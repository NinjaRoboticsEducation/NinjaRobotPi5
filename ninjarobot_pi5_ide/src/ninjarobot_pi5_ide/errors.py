"""Exception wrapper for structured IDE errors."""

from __future__ import annotations

from .models import ErrorDetails


class IDEError(Exception):
    """Exception that retains a stable, serializable error contract."""

    def __init__(self, details: ErrorDetails) -> None:
        super().__init__(details.message)
        self.details = details
