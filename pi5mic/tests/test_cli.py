"""CLI tests for pi5mic."""

from __future__ import annotations

import importlib
from pathlib import Path

from click.testing import CliRunner

from pi5mic.__main__ import cli
from pi5mic.errors import IntegrationError
from pi5mic.integration.openclaw_setup import (
    OpenClawAutoConfig,
    OpenClawReplyTarget,
    OpenClawVoiceReadyReport,
)
from pi5mic.models import AudioDeviceInfo, DispatchResult, RecordedClip, TranscriptionResult

status_module = importlib.import_module("pi5mic.cli.status")
setup_cmd_module = importlib.import_module("pi5mic.cli.setup_cmd")
run_cmd_module = importlib.import_module("pi5mic.cli.run_cmd")


def test_devices_command_lists_input_devices(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        "pi5mic.__main__.list_input_devices",
        lambda: [
            AudioDeviceInfo(
                index=1, name="USB Mic", max_input_channels=1, default_samplerate=16_000
            )
        ],
    )
    monkeypatch.setattr("pi5mic.__main__.get_default_input_device", lambda: 1)

    result = runner.invoke(cli, ["devices"])

    assert result.exit_code == 0, result.output
    assert "USB Mic" in result.output
    assert "(default)" in result.output


def test_record_command_uses_config_defaults(monkeypatch, tmp_path) -> None:
    runner = CliRunner()

    recorded: dict[str, object] = {}

    def fake_record_wav(output, settings):
        recorded["output"] = output
        recorded["settings"] = settings
        return RecordedClip(
            path=Path(output),
            duration_seconds=settings.duration_seconds,
            sample_rate=settings.sample_rate,
            channels=settings.channels,
            frames=160,
            bytes_written=320,
            overflowed=False,
        )

    monkeypatch.setattr("pi5mic.__main__.record_wav", fake_record_wav)

    result = runner.invoke(
        cli,
        [
            "--config-file",
            str(tmp_path / "mic.json"),
            "record",
            "--output",
            str(tmp_path / "clip.wav"),
        ],
    )

    assert result.exit_code == 0, result.output
    settings = recorded["settings"]
    assert settings.sample_rate == 16_000
    assert settings.duration_seconds == 5.0
    assert "Recorded WAV to" in result.output


def test_config_show_works_with_default_file(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert '"profile": "standalone"' in result.output
    assert "Config file:" in result.output


def test_status_command_reports_device_count(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        status_module,
        "list_input_devices",
        lambda: [
            AudioDeviceInfo(
                index=1, name="USB Mic", max_input_channels=1, default_samplerate=16_000
            ),
            AudioDeviceInfo(
                index=2, name="Desk Mic", max_input_channels=2, default_samplerate=48_000
            ),
        ],
    )
    monkeypatch.setattr(status_module, "get_default_input_device", lambda: 2)

    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0, result.output
    assert "Input devices:    2" in result.output
    assert "Default device:   2" in result.output


def test_status_command_shows_openclaw_reply_target(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "profile": "openclaw",
  "integration": {
    "delivery_mode": "local_plus_explicit_channel_target",
    "openclaw": {
      "command": "/usr/local/bin/openclaw",
      "gateway_url": "ws://127.0.0.1:18789",
      "agent_id": "main",
      "session_key": "voice-local-mic",
      "reply_channel": "telegram",
      "reply_to": "-1001234567890:topic:42",
      "reply_account": "default"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(status_module, "list_input_devices", lambda: [])
    monkeypatch.setattr(status_module, "get_default_input_device", lambda: None)

    result = runner.invoke(cli, ["--config-file", str(config_path), "status"])

    assert result.exit_code == 0, result.output
    assert "Delivery mode:    local + explicit channel target" in result.output
    assert "Reply target:     telegram:-1001234567890:topic:42 (account default)" in result.output


def test_setup_command_saves_interactive_choices(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        setup_cmd_module,
        "list_input_devices",
        lambda: [
            AudioDeviceInfo(
                index=1, name="USB Mic", max_input_channels=1, default_samplerate=16_000
            )
        ],
    )
    monkeypatch.setattr(
        setup_cmd_module,
        "find_whisper_cpp_command",
        lambda command=None: Path("/usr/local/bin/whisper-cli"),
    )
    monkeypatch.setattr(
        setup_cmd_module,
        "build_stt_backend",
        lambda config: object(),
    )
    monkeypatch.setattr(
        setup_cmd_module,
        "get_recommended_sample_rate",
        lambda selector, fallback_rate: 16_000,
    )
    monkeypatch.setattr(setup_cmd_module, "recommend_whisper_threads", lambda threads=None: 2)
    monkeypatch.setattr(setup_cmd_module, "is_raspberry_pi", lambda: False)

    inputs = "\n".join(
        [
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
        ]
    )

    result = runner.invoke(
        cli,
        ["--config-file", str(tmp_path / "mic.json"), "setup"],
        input=inputs,
    )

    assert result.exit_code == 0, result.output
    saved = (tmp_path / "mic.json").read_text(encoding="utf-8")
    assert "/usr/local/bin/whisper-cli" in saved
    assert str(tmp_path / "ggml-base.bin") in saved
    assert '"threads": 2' in saved


def test_setup_command_clears_placeholder_openwakeword_model_path(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        setup_cmd_module,
        "list_input_devices",
        lambda: [
            AudioDeviceInfo(
                index=1, name="USB Mic", max_input_channels=1, default_samplerate=16_000
            )
        ],
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
            "standalone",
            "default",
            "16000",
            "whisper_cpp",
            "/usr/local/bin/whisper-cli",
            str(tmp_path / "ggml-base.bin"),
            "2",
            "120",
            "12",
            "y",
            "ninja",
            ".tflite",
            "0.5",
            "0",
            "n",
            "auto",
            "3",
            "10",
            "1.5",
            "200",
        ]
    )

    result = runner.invoke(
        cli,
        ["--config-file", str(tmp_path / "mic.json"), "setup"],
        input=inputs,
    )

    assert result.exit_code == 0, result.output
    saved = (tmp_path / "mic.json").read_text(encoding="utf-8")
    assert '"model_path": null' in saved
    assert "only points to `.tflite` or `.onnx`" in result.output


def test_setup_command_auto_discovers_openclaw_and_repairs_pairing(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    discovered = OpenClawAutoConfig(
        command=tmp_path / "openclaw",
        config_path=tmp_path / "openclaw.json",
        gateway_url="ws://127.0.0.1:18789",
        agent_id="main",
        session_key="voice-local-mic",
        gateway_mode="local",
        gateway_bind="loopback",
        plugin_enabled=True,
        plugin_allowlisted=True,
        plugin_install_found=True,
        telegram_enabled=True,
        telegram_accounts=("default",),
        telegram_default_account="default",
        telegram_reply_target=OpenClawReplyTarget(
            channel="telegram",
            target="-1001234567890:topic:42",
            account_id="default",
            source_session_key="agent:main:telegram:direct:12345",
            updated_at=1_700_000_000_000,
            source="gateway sessions.list",
        ),
    )
    probe_calls = {"count": 0}

    monkeypatch.setattr(
        setup_cmd_module,
        "list_input_devices",
        lambda: [
            AudioDeviceInfo(
                index=1, name="USB Mic", max_input_channels=1, default_samplerate=16_000
            )
        ],
    )
    monkeypatch.setattr(
        setup_cmd_module,
        "get_recommended_sample_rate",
        lambda selector, fallback_rate: 16_000,
    )
    monkeypatch.setattr(setup_cmd_module, "is_raspberry_pi", lambda: False)
    monkeypatch.setattr(setup_cmd_module, "build_stt_backend", lambda config: object())
    monkeypatch.setattr(
        setup_cmd_module,
        "discover_openclaw_auto_config",
        lambda **kwargs: discovered,
    )

    def _probe(**kwargs):
        probe_calls["count"] += 1
        if probe_calls["count"] == 1:
            raise IntegrationError(
                "OpenClaw presence update failed: gateway connect failed: Error: pairing required"
            )
        return OpenClawVoiceReadyReport(
            ok_lines=("OpenClaw gateway responded.", "NinjaClawBot presence method responded."),
        )

    monkeypatch.setattr(setup_cmd_module, "probe_openclaw_voice_ready", _probe)
    monkeypatch.setattr(
        setup_cmd_module,
        "approve_latest_openclaw_pairing",
        lambda command: "Approved the latest OpenClaw device request.",
    )

    inputs = "\n".join(
        [
            "openclaw",
            "default",
            "16000",
            "gemini",
            "gemini-2.5-flash",
            "60",
            "2",
            "12",
            "n",
            "y",
            "y",
        ]
    )

    result = runner.invoke(
        cli,
        ["--config-file", str(tmp_path / "mic.json"), "setup"],
        input=inputs,
    )

    assert result.exit_code == 0, result.output
    saved = (tmp_path / "mic.json").read_text(encoding="utf-8")
    assert str(discovered.command) in saved
    assert discovered.gateway_url in saved
    assert discovered.agent_id in saved
    assert discovered.session_key in saved
    assert '"delivery_mode": "local_plus_explicit_channel_target"' in saved
    assert '"reply_channel": "telegram"' in saved
    assert '"reply_to": "-1001234567890:topic:42"' in saved
    assert "Approve the newest local OpenClaw device request now?" in result.output
    assert "Approved the latest OpenClaw device request." in result.output
    assert "OpenClaw voice handoff is ready." in result.output


def test_transcribe_command_uses_backend_builder(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"RIFF")

    class _FakeBackend:
        def transcribe(self, audio_path):
            return type(
                "Result",
                (),
                {
                    "text": "hello",
                    "backend": "whisper_cpp",
                    "model": "ggml-base.bin",
                    "language": "en",
                },
            )()

    monkeypatch.setattr(
        "pi5mic.__main__.build_stt_backend", lambda config, backend_name=None: _FakeBackend()
    )

    result = runner.invoke(
        cli,
        ["--config-file", str(tmp_path / "mic.json"), "transcribe", str(audio_path)],
    )

    assert result.exit_code == 0, result.output
    assert "hello" in result.output
    assert "Backend: whisper_cpp" in result.output


def test_run_command_reports_transcript_and_reply(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"RIFF")

    monkeypatch.setattr(
        run_cmd_module,
        "_run_cycle",
        lambda **kwargs: (
            TranscriptionResult(
                text="hello ninja",
                backend="whisper_cpp",
                model="ggml-base.bin",
                language="en",
            ),
            DispatchResult(transcript="hello ninja", reply_text="Hello back"),
            audio_path,
            False,
        ),
    )

    result = runner.invoke(
        cli,
        [
            "--config-file",
            str(tmp_path / "mic.json"),
            "run",
            "--once",
            "--audio-file",
            str(audio_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "hello ninja" in result.output
    assert "Hello back" in result.output


def test_run_command_shows_openclaw_delivery_mode(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"RIFF")
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "profile": "openclaw",
  "stt": {
    "selected": "whisper_cpp"
  },
  "integration": {
    "delivery_mode": "local_plus_explicit_channel_target",
    "openclaw": {
      "command": "/usr/local/bin/openclaw",
      "gateway_url": "ws://127.0.0.1:18789",
      "agent_id": "main",
      "session_key": "voice-local-mic",
      "reply_channel": "telegram",
      "reply_to": "-1001234567890:topic:42",
      "reply_account": "default"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        run_cmd_module,
        "_run_cycle",
        lambda **kwargs: (
            TranscriptionResult(
                text="hello ninja",
                backend="whisper_cpp",
                model="ggml-base.bin",
                language="en",
            ),
            DispatchResult(transcript="hello ninja", reply_text="Hello back"),
            audio_path,
            False,
        ),
    )

    result = runner.invoke(
        cli,
        [
            "--config-file",
            str(config_path),
            "run",
            "--once",
            "--audio-file",
            str(audio_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (
        "Delivery: local + explicit channel target (telegram:-1001234567890:topic:42 (account default))"
        in result.output
    )
