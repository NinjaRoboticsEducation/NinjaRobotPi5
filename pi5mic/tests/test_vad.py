"""Tests for silence-based voice activity detection."""

from __future__ import annotations

import pytest

from pi5mic.vad.silence import SilenceStopDetector


def test_silence_detector_stops_after_configured_silent_frames() -> None:
    detector = SilenceStopDetector(rms_threshold=100.0, stop_after_silent_frames=2)

    first = detector.process(b"\x00\x00" * 8)
    second = detector.process(b"\x00\x00" * 8)

    assert first.is_silent is True
    assert first.should_stop is False
    assert second.consecutive_silence_frames == 2
    assert second.should_stop is True


def test_silence_detector_resets_after_loud_frame() -> None:
    detector = SilenceStopDetector(rms_threshold=100.0, stop_after_silent_frames=3)

    detector.process(b"\x00\x00" * 8)
    loud = detector.process((1000).to_bytes(2, "little", signed=True) * 8)

    assert loud.is_silent is False
    assert loud.consecutive_silence_frames == 0
    assert loud.should_stop is False


def test_silence_detector_rejects_odd_byte_count() -> None:
    detector = SilenceStopDetector()

    with pytest.raises(ValueError, match="16-bit"):
        detector.process(b"\x00")
