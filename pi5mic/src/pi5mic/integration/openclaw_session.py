"""Helpers for OpenClaw session-id compatibility in pi5mic."""

from __future__ import annotations

import re

DEFAULT_OPENCLAW_SESSION_ID = "voice-local-mic"
LEGACY_OPENCLAW_SESSION_ID = "voice:local-mic"
SAFE_OPENCLAW_SESSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$", re.IGNORECASE)
_INVALID_SESSION_CHARS_RE = re.compile(r"[^a-z0-9._-]+", re.IGNORECASE)
_DUPLICATE_DASH_RE = re.compile(r"-{2,}")


def normalize_openclaw_session_id(value: str | None) -> str:
    """Return a session id that matches the current OpenClaw CLI rules."""
    trimmed = (value or "").strip()
    if not trimmed:
        return DEFAULT_OPENCLAW_SESSION_ID
    if SAFE_OPENCLAW_SESSION_ID_RE.fullmatch(trimmed):
        return trimmed

    normalized = _INVALID_SESSION_CHARS_RE.sub("-", trimmed)
    normalized = _DUPLICATE_DASH_RE.sub("-", normalized)
    normalized = normalized.strip("._-")
    if not normalized:
        return DEFAULT_OPENCLAW_SESSION_ID
    if not normalized[0].isalnum():
        normalized = f"voice-{normalized}"
    return normalized[:128]


def needs_openclaw_session_id_migration(value: str | None) -> bool:
    """Return True when the configured value is empty or not OpenClaw-safe."""
    trimmed = (value or "").strip()
    if not trimmed:
        return True
    return normalize_openclaw_session_id(trimmed) != trimmed
