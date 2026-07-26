"""Helpers for locating and validating whisper.cpp assets."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Sequence

from pi5mic.errors import STTError

DEFAULT_COMMAND_CANDIDATES = ("whisper-cli",)
DEFAULT_MODEL_FILE = "ggml-base.bin"


def find_whisper_cpp_command(
    command: str | Path | None = None,
    *,
    candidates: Sequence[str] = DEFAULT_COMMAND_CANDIDATES,
) -> Path | None:
    """Locate a whisper.cpp CLI binary."""
    if command is not None:
        command_path = Path(command)
        if command_path.is_file():
            return command_path.resolve()
        resolved = shutil.which(str(command))
        return Path(resolved).resolve() if resolved else None

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return Path(resolved).resolve()
    return None


def resolve_whisper_cpp_command(command: str | Path | None = None) -> Path:
    """Resolve the configured whisper.cpp command or raise a helpful error."""
    resolved = find_whisper_cpp_command(command)
    if resolved is None:
        raise STTError(
            "Could not find 'whisper-cli'. Set an explicit command path or install whisper.cpp."
        )
    return resolved


def resolve_model_path(model_path: str | Path) -> Path:
    """Resolve a configured model path or raise a helpful error."""
    resolved = Path(model_path).expanduser().resolve()
    if not resolved.is_file():
        raise STTError(f"Whisper model file not found: {resolved}")
    return resolved
