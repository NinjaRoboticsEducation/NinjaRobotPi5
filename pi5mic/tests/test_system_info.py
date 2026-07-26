"""Tests for Raspberry Pi diagnostics helpers."""

from __future__ import annotations

from pi5mic.core.system_info import parse_vcgencmd_throttled


def test_parse_vcgencmd_throttled_reports_historic_issues() -> None:
    raw_hex, issues = parse_vcgencmd_throttled("throttled=0x50005")

    assert raw_hex == "0x50005"
    assert "undervoltage detected" in issues
    assert "undervoltage has occurred" in issues
    assert "throttling has occurred" in issues
