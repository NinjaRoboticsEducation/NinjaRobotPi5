from __future__ import annotations

from datetime import datetime, timezone

from llmwiki.lint import is_stale, trust_tier


def test_trust_is_derived_from_verification_events() -> None:
    assert trust_tier({}) == "unverified"
    assert trust_tier({"verified": {"by": "agent:test", "at": "2026-01-01T00:00:00Z"}}) == "machine-confirmed"
    assert trust_tier({"verified": [{"by": "human:owner", "at": "2026-01-01T00:00:00Z"}]}) == "human-reviewed"


def test_freshness_uses_absolute_time() -> None:
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    assert is_stale({"stale_after": "2026-08-21T00:00:00Z"}, now)
    assert not is_stale({"stale_after": "2026-08-23T00:00:00Z"}, now)
    assert not is_stale({}, now)
