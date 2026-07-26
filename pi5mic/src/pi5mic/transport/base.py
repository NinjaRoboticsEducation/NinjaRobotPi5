"""Text transport abstractions for pi5mic."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pi5mic.models import DispatchResult


class TextTransport(ABC):
    """Abstract destination for recognized transcript text."""

    @abstractmethod
    def dispatch(self, text: str) -> DispatchResult:
        """Dispatch text to the configured downstream integration."""
