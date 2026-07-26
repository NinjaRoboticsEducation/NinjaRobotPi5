"""Bounded WAV recording helpers for pi5mic."""

from __future__ import annotations

import math
import tempfile
import wave
from pathlib import Path

from pi5mic.core.audio_backend import load_sounddevice
from pi5mic.errors import RecordingError
from pi5mic.models import RecordedClip, RecorderSettings

from .devices import resolve_supported_input_settings


def _get_sounddevice():
    return load_sounddevice(
        purpose="WAV recording",
        error_factory=RecordingError,
    )


def record_wav(output_path: Path | str, settings: RecorderSettings) -> RecordedClip:
    """Record a bounded PCM WAV clip to `output_path`."""
    settings.validate()

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sd = _get_sounddevice()
    try:
        resolved_device, actual_sample_rate, _device_info, _warning = (
            resolve_supported_input_settings(
                selector=settings.device,
                sample_rate=settings.sample_rate,
                channels=settings.channels,
            )
        )
    except Exception as exc:
        raise RecordingError(str(exc)) from exc

    total_frames = math.ceil(settings.duration_seconds * actual_sample_rate)
    overflowed = False

    try:
        with sd.RawInputStream(
            samplerate=actual_sample_rate,
            blocksize=settings.block_size,
            device=resolved_device,
            channels=settings.channels,
            dtype="int16",
        ) as stream:
            with wave.open(str(path), "wb") as wav_file:
                wav_file.setnchannels(settings.channels)
                wav_file.setsampwidth(settings.sample_width_bytes)
                wav_file.setframerate(actual_sample_rate)

                remaining_frames = total_frames
                while remaining_frames > 0:
                    chunk_frames = min(settings.block_size, remaining_frames)
                    data, chunk_overflowed = stream.read(chunk_frames)
                    overflowed = overflowed or bool(chunk_overflowed)
                    wav_file.writeframes(data)
                    remaining_frames -= chunk_frames
    except Exception as exc:
        raise RecordingError(f"Could not record WAV audio: {exc}") from exc

    bytes_written = path.stat().st_size if path.exists() else 0
    return RecordedClip(
        path=path,
        duration_seconds=settings.duration_seconds,
        sample_rate=actual_sample_rate,
        channels=settings.channels,
        frames=total_frames,
        bytes_written=bytes_written,
        overflowed=overflowed,
    )


def record_temp_wav(
    settings: RecorderSettings,
    *,
    directory: Path | str | None = None,
    prefix: str = "pi5mic-",
) -> RecordedClip:
    """Record a bounded WAV clip into a temporary file."""
    temp_dir = None if directory is None else Path(directory)
    with tempfile.NamedTemporaryFile(
        prefix=prefix,
        suffix=".wav",
        dir=temp_dir,
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
    return record_wav(temp_path, settings)
