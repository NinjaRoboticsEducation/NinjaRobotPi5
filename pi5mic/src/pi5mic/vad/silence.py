"""Simple silence-stop detector for pi5mic."""

from __future__ import annotations

import math

from .base import VoiceActivityDetector, VoiceActivityResult


class SilenceStopDetector(VoiceActivityDetector):
    """Stop after a configurable run of low-volume PCM frames."""

    def __init__(
        self,
        *,
        rms_threshold: float = 200.0,
        stop_after_silent_frames: int = 8,
    ) -> None:
        if rms_threshold < 0:
            raise ValueError("rms_threshold must be >= 0.")
        if stop_after_silent_frames <= 0:
            raise ValueError("stop_after_silent_frames must be > 0.")
        self._rms_threshold = rms_threshold
        self._stop_after_silent_frames = stop_after_silent_frames
        self._consecutive_silence_frames = 0

    def process(self, pcm_frame: bytes) -> VoiceActivityResult:
        """Measure RMS level and update silence counters."""
        if len(pcm_frame) % 2 != 0:
            raise ValueError("PCM frame must contain 16-bit samples.")

        samples_view = memoryview(pcm_frame).cast("h")
        if len(samples_view) == 0:
            rms_level = 0.0
        else:
            squares = sum(int(sample) * int(sample) for sample in samples_view)
            rms_level = math.sqrt(squares / len(samples_view))

        is_silent = rms_level < self._rms_threshold
        if is_silent:
            self._consecutive_silence_frames += 1
        else:
            self._consecutive_silence_frames = 0

        return VoiceActivityResult(
            is_silent=is_silent,
            rms_level=rms_level,
            consecutive_silence_frames=self._consecutive_silence_frames,
            should_stop=self._consecutive_silence_frames >= self._stop_after_silent_frames,
        )

    def reset(self) -> None:
        """Reset the silence counter."""
        self._consecutive_silence_frames = 0
