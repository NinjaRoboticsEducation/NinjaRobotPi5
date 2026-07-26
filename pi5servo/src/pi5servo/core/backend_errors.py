"""Shared error types for servo pulse backends."""


class BackendError(RuntimeError):
    """Base error for servo backend failures."""


class BackendUnavailableError(BackendError):
    """Raised when a requested backend cannot be used on the current system."""


class BackendConfigurationError(BackendError):
    """Raised when backend configuration is invalid for the requested pins."""
