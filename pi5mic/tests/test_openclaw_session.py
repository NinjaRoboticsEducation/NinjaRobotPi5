"""Tests for OpenClaw session-id normalization."""

from __future__ import annotations

from pi5mic.integration.openclaw_session import (
    DEFAULT_OPENCLAW_SESSION_ID,
    needs_openclaw_session_id_migration,
    normalize_openclaw_session_id,
)


def test_normalize_openclaw_session_id_migrates_legacy_value() -> None:
    assert normalize_openclaw_session_id("voice:local-mic") == "voice-local-mic"


def test_normalize_openclaw_session_id_keeps_safe_value() -> None:
    assert normalize_openclaw_session_id("voice-local-mic") == "voice-local-mic"


def test_normalize_openclaw_session_id_falls_back_when_empty() -> None:
    assert normalize_openclaw_session_id("") == DEFAULT_OPENCLAW_SESSION_ID


def test_needs_openclaw_session_id_migration_detects_legacy_value() -> None:
    assert needs_openclaw_session_id_migration("voice:local-mic") is True
    assert needs_openclaw_session_id_migration("voice-local-mic") is False
