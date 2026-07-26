"""Tests for bounded WAV recording."""

from __future__ import annotations

import builtins
import wave

import pytest

from pi5mic.core import recorder as recorder_module
from pi5mic.errors import RecordingError
from pi5mic.models import RecorderSettings


class _FakeRawInputStream:
    def __init__(self, *, samplerate, blocksize, device, channels, dtype) -> None:
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.device = device
        self.channels = channels
        self.dtype = dtype
        self._reads = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, frames):
        self._reads += 1
        return (b"\x00\x01" * frames * self.channels, self._reads == 1)


class _FakeSoundDevice:
    def check_input_settings(self, *, device=None, channels=None, dtype=None, samplerate=None):
        if samplerate == 8_000:
            raise ValueError("Invalid sample rate [PaErrorCode -9997]")

    RawInputStream = _FakeRawInputStream


def test_record_wav_writes_valid_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recorder_module, "_get_sounddevice", lambda: _FakeSoundDevice())
    monkeypatch.setattr(
        recorder_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (1, 8_000, None, None),
    )

    settings = RecorderSettings(
        device=1, sample_rate=8_000, channels=1, block_size=400, duration_seconds=0.1
    )
    clip = recorder_module.record_wav(tmp_path / "clip.wav", settings)

    assert clip.path.exists()
    assert clip.frames == 800
    assert clip.overflowed is True

    with wave.open(str(clip.path), "rb") as wav_file:
        assert wav_file.getframerate() == 8_000
        assert wav_file.getnchannels() == 1
        assert wav_file.getnframes() == 800


def test_record_temp_wav_uses_temp_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recorder_module, "_get_sounddevice", lambda: _FakeSoundDevice())
    monkeypatch.setattr(
        recorder_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (None, 8_000, None, None),
    )

    clip = recorder_module.record_temp_wav(
        RecorderSettings(sample_rate=8_000, duration_seconds=0.05),
        directory=tmp_path,
        prefix="capture-",
    )

    assert clip.path.parent == tmp_path
    assert clip.path.name.startswith("capture-")
    assert clip.path.suffix == ".wav"


def test_record_wav_falls_back_to_supported_sample_rate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recorder_module, "_get_sounddevice", lambda: _FakeSoundDevice())
    monkeypatch.setattr(
        recorder_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (0, 48_000, None, "Using 48000 Hz instead."),
    )

    settings = RecorderSettings(
        device=1, sample_rate=8_000, channels=1, block_size=400, duration_seconds=0.1
    )
    clip = recorder_module.record_wav(tmp_path / "clip.wav", settings)

    assert clip.sample_rate == 48_000


def test_recorder_settings_validate_sample_width() -> None:
    with pytest.raises(ValueError, match="16-bit PCM"):
        RecorderSettings(sample_width_bytes=1).validate()


def test_recording_backend_reports_missing_portaudio(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sounddevice":
            raise OSError("PortAudio library not found")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RecordingError, match="PortAudio library not found"):
        recorder_module._get_sounddevice()
