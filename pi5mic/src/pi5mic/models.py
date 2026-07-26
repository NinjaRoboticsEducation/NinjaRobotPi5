"""Data models for pi5mic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AudioDeviceInfo:
    """A discovered audio input device."""

    index: int
    name: str
    max_input_channels: int
    default_samplerate: float | None
    hostapi: int | None = None


@dataclass(frozen=True, slots=True)
class RecorderSettings:
    """Settings for bounded WAV capture."""

    device: int | str | None = None
    sample_rate: int = 16_000
    channels: int = 1
    sample_width_bytes: int = 2
    block_size: int = 1_024
    duration_seconds: float = 5.0

    def validate(self) -> None:
        """Validate the current recorder settings."""
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than 0.")
        if self.channels <= 0:
            raise ValueError("channels must be greater than 0.")
        if self.sample_width_bytes != 2:
            raise ValueError("Phase 1 recorder only supports 16-bit PCM (sample_width_bytes=2).")
        if self.block_size <= 0:
            raise ValueError("block_size must be greater than 0.")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be greater than 0.")


@dataclass(frozen=True, slots=True)
class RecordedClip:
    """Metadata about a recorded WAV clip."""

    path: Path
    duration_seconds: float
    sample_rate: int
    channels: int
    frames: int
    bytes_written: int
    overflowed: bool = False


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """A normalized speech-to-text result."""

    text: str
    backend: str
    model: str
    language: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """A normalized downstream-dispatch result."""

    transcript: str
    reply_text: str | None = None
    raw: dict[str, Any] | None = None


def deep_copy_dict(value: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-ish copy for nested JSON-like dictionaries."""
    copied: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            copied[key] = deep_copy_dict(item)
        elif isinstance(item, list):
            copied[key] = list(item)
        else:
            copied[key] = item
    return copied
