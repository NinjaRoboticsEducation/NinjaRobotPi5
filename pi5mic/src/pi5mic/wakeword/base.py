"""Wake-word detector abstractions for pi5mic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class WakeWordResult:
    """Wake-word processing result."""

    detected: bool
    keyword_index: int | None = None
    keyword: str | None = None
    score: float | None = None


class WakeWordDetector(ABC):
    """Abstract interface for wake-word engines."""

    @abstractmethod
    def process(self, pcm_frame: Sequence[int]) -> WakeWordResult:
        """Process one audio frame and report whether the wake word fired."""

    def reset(self) -> None:
        """Reset any rolling backend state after a completed wake-word cycle."""

    def close(self) -> None:
        """Release any native wake-word backend resources."""
