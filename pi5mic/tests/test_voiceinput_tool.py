"""Tests for the always-on voiceinput-tool CLI."""

from __future__ import annotations

import importlib

from click.testing import CliRunner

from pi5mic.__main__ import cli

voiceinput_tool_module = importlib.import_module("pi5mic.cli.voiceinput_tool")


def test_voiceinput_tool_menu_can_exit_cleanly() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["voiceinput-tool"], input="6\n")

    assert result.exit_code == 0, result.output
    assert "Start background listener" in result.output
    assert "Leaving pi5mic voiceinput-tool." in result.output


def test_voiceinput_tool_foreground_uses_manual_runner(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "voiceinput": {
    "enabled": true
  },
  "wakeword": {
    "enabled": true,
    "keyword": "ninja"
  }
}
""".strip(),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        voiceinput_tool_module,
        "_ensure_voiceinput_enabled",
        lambda config: {
            "keyword": "ninja",
            "silence_timeout_seconds": 3.0,
            "max_capture_seconds": 10.0,
        },
    )

    def _fake_run_loop(*, manager_path, config, paths, echo_logs):
        captured["manager_path"] = manager_path
        captured["config"] = config
        captured["paths"] = paths
        captured["echo_logs"] = echo_logs

    monkeypatch.setattr(voiceinput_tool_module, "_run_voiceinput_loop", _fake_run_loop)

    result = runner.invoke(
        cli,
        ["--config-file", str(config_path), "voiceinput-tool", "foreground"],
    )

    assert result.exit_code == 0, result.output
    assert "Starting voice input in the foreground." in result.output
    assert captured["manager_path"] == config_path
    assert captured["echo_logs"] is True


def test_voiceinput_tool_start_reports_success_when_state_turns_running(
    monkeypatch,
    tmp_path,
) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "voiceinput": {
    "enabled": true
  },
  "wakeword": {
    "enabled": true,
    "keyword": "ninja"
  }
}
""".strip(),
        encoding="utf-8",
    )

    class _FakeProcess:
        pid = 321

        def poll(self):
            return None

    state_sequence = iter(
        [
            {"running": False, "pid": None, "mode": "stopped"},
            {"running": True, "pid": 321, "mode": "running"},
        ]
    )

    monkeypatch.setattr(
        voiceinput_tool_module,
        "_ensure_voiceinput_enabled",
        lambda config: {
            "backend": "openwakeword",
            "keyword": "ninja",
            "session_strategy": "agent_main",
        },
    )
    monkeypatch.setattr(
        voiceinput_tool_module.subprocess,
        "Popen",
        lambda *args, **kwargs: _FakeProcess(),
    )
    monkeypatch.setattr(
        voiceinput_tool_module,
        "read_voiceinput_state",
        lambda paths: next(state_sequence),
    )
    monkeypatch.setattr(voiceinput_tool_module.time, "sleep", lambda seconds: None)

    result = runner.invoke(
        cli,
        ["--config-file", str(config_path), "voiceinput-tool", "start"],
    )

    assert result.exit_code == 0, result.output
    assert "Started the always-on voice input listener in the background." in result.output


def test_voiceinput_tool_stop_handles_not_running_state(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        voiceinput_tool_module,
        "read_voiceinput_state",
        lambda paths: {"running": False, "pid": None, "mode": "stopped"},
    )

    result = runner.invoke(
        cli,
        ["--config-file", str(config_path), "voiceinput-tool", "stop"],
    )

    assert result.exit_code == 0, result.output
    assert "Voice input is not running right now." in result.output
