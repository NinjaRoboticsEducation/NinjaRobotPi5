"""Voice activity detection abstractions for pi5mic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VoiceActivityResult:
    """Silence detector result for one audio frame."""

    is_silent: bool
    rms_level: float
    consecutive_silence_frames: int
    should_stop: bool


class VoiceActivityDetector(ABC):
    """Abstract interface for local voice-activity checks."""

    @abstractmethod
    def process(self, pcm_frame: bytes) -> VoiceActivityResult:
        """Process one frame of PCM audio."""

    def reset(self) -> None:
        """Reset any internal silence counters."""
