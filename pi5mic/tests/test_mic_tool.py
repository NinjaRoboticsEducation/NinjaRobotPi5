"""Tests for the mic-tool menu."""

from __future__ import annotations

from click.testing import CliRunner

from pi5mic.__main__ import cli


def test_mic_tool_can_exit_cleanly() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["mic-tool"], input="7\n")

    assert result.exit_code == 0, result.output
    assert "Run setup wizard" in result.output
    assert "Open voiceinput-tool" in result.output
    assert "Leaving pi5mic mic-tool." in result.output
