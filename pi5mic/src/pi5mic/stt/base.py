"""Speech-to-text backend abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pi5mic.models import TranscriptionResult


class SpeechToTextBackend(ABC):
    """Abstract speech-to-text interface."""

    @abstractmethod
    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        """Transcribe the given audio file."""
