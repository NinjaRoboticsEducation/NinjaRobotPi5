"""Regression tests for mic-tool setup flows."""

from __future__ import annotations

import importlib
from pathlib import Path

import click
from click.testing import CliRunner

from pi5mic.__main__ import cli
from pi5mic.errors import DeviceError

mic_tool_module = importlib.import_module("pi5mic.cli.mic_tool")
setup_cmd_module = importlib.import_module("pi5mic.cli.setup_cmd")


def test_mic_tool_setup_warns_instead_of_crashing_when_audio_backend_is_unavailable(
    monkeypatch,
    tmp_path,
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        setup_cmd_module,
        "list_input_devices",
        lambda: (_ for _ in ()).throw(
            DeviceError("PortAudio library not found\nPortAudio is required for microphone access.")
        ),
    )
    monkeypatch.setattr(
        setup_cmd_module,
        "find_whisper_cpp_command",
        lambda command=None: Path("/usr/local/bin/whisper-cli"),
    )
    monkeypatch.setattr(setup_cmd_module, "build_stt_backend", lambda config: object())
    monkeypatch.setattr(
        setup_cmd_module,
        "get_recommended_sample_rate",
        lambda selector, fallback_rate: 16_000,
    )
    monkeypatch.setattr(setup_cmd_module, "recommend_whisper_threads", lambda threads=None: 2)
    monkeypatch.setattr(setup_cmd_module, "is_raspberry_pi", lambda: False)

    inputs = "\n".join(
        [
            "1",
            "standalone",
            "default",
            "16000",
            "whisper_cpp",
            "/usr/local/bin/whisper-cli",
            str(tmp_path / "ggml-base.bin"),
            "2",
            "120",
            "15",
            "n",
            "7",
        ]
    )

    result = runner.invoke(
        cli,
        ["--config-file", str(tmp_path / "mic.json"), "mic-tool"],
        input=inputs,
    )

    assert result.exit_code == 0, result.output
    assert "WARNING: Could not list audio devices yet:" in result.output
    assert "Leaving pi5mic mic-tool." in result.output


def test_mic_tool_returns_to_menu_after_click_exception(monkeypatch) -> None:
    runner = CliRunner()

    @click.command("doctor")
    @click.pass_context
    def _failing_doctor(ctx: click.Context) -> None:
        raise click.ClickException("doctor failed on purpose")

    monkeypatch.setattr(mic_tool_module, "doctor", _failing_doctor)

    result = runner.invoke(cli, ["mic-tool"], input="3\n7\n")

    assert result.exit_code == 0, result.output
    assert "ERROR: doctor failed on purpose" in result.output
    assert "Fix the issue above" in result.output
    assert "Leaving pi5mic mic-tool." in result.output
