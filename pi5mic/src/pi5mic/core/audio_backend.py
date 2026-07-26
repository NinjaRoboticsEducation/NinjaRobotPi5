"""Shared audio-backend import helpers for pi5mic."""

from __future__ import annotations

from typing import Callable


def _portaudio_help_text() -> str:
    return (
        "PortAudio is required for microphone access. On Raspberry Pi / Debian, install it with:\n"
        "  sudo apt update\n"
        "  sudo apt install -y libportaudio2 portaudio19-dev"
    )


def load_sounddevice(*, purpose: str, error_factory: Callable[[str], Exception]):
    """Import `sounddevice` and translate common setup failures into friendly errors."""
    try:
        import sounddevice as sd
    except ImportError as exc:  # pragma: no cover - exercised indirectly in CLI
        raise error_factory(
            f"The 'sounddevice' package is required for {purpose}. "
            "Reinstall the pi5mic environment with `uv sync --extra dev` if needed."
        ) from exc
    except OSError as exc:  # pragma: no cover - hardware/system dependency path
        details = str(exc).strip()
        if "PortAudio library not found" in details:
            raise error_factory(f"{details}\n{_portaudio_help_text()}") from exc
        raise error_factory(
            f"Could not initialize the audio backend for {purpose}: {details}"
        ) from exc
    return sd
