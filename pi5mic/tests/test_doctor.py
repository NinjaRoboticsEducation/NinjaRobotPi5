"""Tests for pi5mic doctor and install commands."""

from __future__ import annotations

import importlib
from pathlib import Path

from click.testing import CliRunner

from pi5mic.__main__ import cli
from pi5mic.errors import IntegrationError
from pi5mic.integration.openclaw_setup import OpenClawAutoConfig, OpenClawVoiceReadyReport

doctor_module = importlib.import_module("pi5mic.cli.doctor")
install_cmd_module = importlib.import_module("pi5mic.cli.install_cmd")


def test_doctor_passes_for_valid_whisper_configuration(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "stt": {
    "selected": "whisper_cpp",
    "whisper_cpp": {
      "command": "/usr/local/bin/whisper-cli",
      "model_path": "/models/ggml-base.bin"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor_module, "list_input_devices", lambda: [object()])
    monkeypatch.setattr(
        doctor_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (0, 16_000, None, None),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_whisper_cpp_command",
        lambda command: Path("/usr/local/bin/whisper-cli"),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_model_path",
        lambda model_path: Path("/models/ggml-base.bin"),
    )
    monkeypatch.setattr(doctor_module, "is_raspberry_pi", lambda: False)

    result = runner.invoke(cli, ["--config-file", str(config_path), "doctor"])

    assert result.exit_code == 0, result.output
    assert "pi5mic doctor passed" in result.output


def test_doctor_reports_sample_rate_warning(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "audio": {
    "input_device": 0,
    "sample_rate": 16000,
    "channels": 1
  },
  "stt": {
    "selected": "whisper_cpp",
    "whisper_cpp": {
      "command": "/usr/local/bin/whisper-cli",
      "model_path": "/models/ggml-base.bin"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor_module, "list_input_devices", lambda: [object()])
    monkeypatch.setattr(
        doctor_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (
            0,
            48_000,
            type("DeviceInfo", (), {"name": "USB Mic", "index": 0})(),
            "Configured sample rate 16000 Hz is not supported by USB Mic [0]. Using 48000 Hz instead.",
        ),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_whisper_cpp_command",
        lambda command: Path("/usr/local/bin/whisper-cli"),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_model_path",
        lambda model_path: Path("/models/ggml-base.bin"),
    )
    monkeypatch.setattr(doctor_module, "is_raspberry_pi", lambda: False)

    result = runner.invoke(cli, ["--config-file", str(config_path), "doctor"])

    assert result.exit_code == 0, result.output
    assert "Warnings:" in result.output
    assert "Using 48000 Hz instead" in result.output


def test_doctor_reports_actionable_gemini_credential_failure(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "stt": {
    "selected": "gemini",
    "gemini": {
      "model": "gemini-2.5-flash"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor_module, "list_input_devices", lambda: [object()])
    monkeypatch.setattr(
        doctor_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (0, 44_100, None, None),
    )
    monkeypatch.setattr(doctor_module, "is_raspberry_pi", lambda: False)
    monkeypatch.setattr(doctor_module.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        doctor_module,
        "resolve_gemini_api_key",
        lambda: (_ for _ in ()).throw(
            doctor_module.STTError(
                "Gemini credentials are not configured in the environment. "
                "Set GOOGLE_API_KEY or GEMINI_API_KEY before using the Gemini backend."
            )
        ),
    )

    result = runner.invoke(cli, ["--config-file", str(config_path), "doctor"])

    assert result.exit_code != 0
    assert "GOOGLE_API_KEY or GEMINI_API_KEY" in result.output
    assert "export GEMINI_API_KEY" in result.output


def test_doctor_reports_always_on_voiceinput_readiness(monkeypatch, tmp_path) -> None:
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
  },
  "stt": {
    "selected": "whisper_cpp",
    "whisper_cpp": {
      "command": "/usr/local/bin/whisper-cli",
      "model_path": "/models/ggml-base.bin"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor_module, "list_input_devices", lambda: [object()])
    monkeypatch.setattr(
        doctor_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (0, 16_000, None, None),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_whisper_cpp_command",
        lambda command: Path("/usr/local/bin/whisper-cli"),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_model_path",
        lambda model_path: Path("/models/ggml-base.bin"),
    )
    monkeypatch.setattr(doctor_module, "is_raspberry_pi", lambda: False)
    monkeypatch.setattr(
        doctor_module,
        "validate_voiceinput_readiness",
        lambda config: {
            "backend": "openwakeword",
            "keyword": "ninja",
            "model_path": Path("/models/ninja.tflite"),
            "resolved_inference_framework": "tflite",
            "threshold": 0.5,
            "wakeword_vad_threshold": 0.0,
            "enable_noise_suppression": False,
            "silence_timeout_seconds": 3.0,
            "max_capture_seconds": 10.0,
            "cooldown_seconds": 1.5,
            "detector_sample_rate": 16_000,
            "detector_frame_length": 1280,
        },
    )
    monkeypatch.setattr(
        doctor_module,
        "build_voiceinput_runtime_paths",
        lambda config_path: type(
            "Paths",
            (),
            {"state_file": tmp_path / "voice-state.json", "log_file": tmp_path / "voice.log"},
        )(),
    )
    monkeypatch.setattr(
        doctor_module,
        "read_voiceinput_state",
        lambda paths: {"running": False, "mode": "stopped", "last_error": None},
    )

    result = runner.invoke(cli, ["--config-file", str(config_path), "doctor"])

    assert result.exit_code == 0, result.output
    assert "INFO always-on voice input: enabled" in result.output
    assert "OK   wake-word detector: openwakeword @ 16000 Hz" in result.output
    assert "OK   wake model:        /models/ninja.tflite" in result.output
    assert "INFO voice input service: stopped" in result.output


def test_doctor_handles_missing_google_parent_package_gracefully(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "stt": {
    "selected": "gemini",
    "gemini": {
      "model": "gemini-2.5-flash"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor_module, "list_input_devices", lambda: [object()])
    monkeypatch.setattr(
        doctor_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (0, 44_100, None, None),
    )
    monkeypatch.setattr(doctor_module, "is_raspberry_pi", lambda: False)

    def _raise_module_not_found(name):
        raise ModuleNotFoundError("No module named 'google'")

    monkeypatch.setattr(doctor_module.importlib.util, "find_spec", _raise_module_not_found)

    result = runner.invoke(cli, ["--config-file", str(config_path), "doctor"])

    assert result.exit_code != 0
    assert "google-genai" in result.output
    assert "uv sync --extra dev" in result.output


def test_doctor_reports_raspberry_pi_throttle_warning(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "stt": {
    "selected": "whisper_cpp",
    "whisper_cpp": {
      "command": "/usr/local/bin/whisper-cli",
      "model_path": "/models/ggml-base.bin"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor_module, "list_input_devices", lambda: [object()])
    monkeypatch.setattr(
        doctor_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (0, 44_100, None, None),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_whisper_cpp_command",
        lambda command: Path("/usr/local/bin/whisper-cli"),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_model_path",
        lambda model_path: Path("/models/ggml-base.bin"),
    )
    monkeypatch.setattr(doctor_module, "is_raspberry_pi", lambda: True)
    monkeypatch.setattr(
        doctor_module,
        "read_raspberry_pi_model",
        lambda: "Raspberry Pi 5 Model B Rev 1.0",
    )
    monkeypatch.setattr(doctor_module, "read_raspberry_pi_temperature_celsius", lambda: 76.5)
    monkeypatch.setattr(
        doctor_module,
        "read_raspberry_pi_throttled_state",
        lambda: ("0x50005", ["undervoltage has occurred", "throttling has occurred"]),
    )
    monkeypatch.setattr(doctor_module, "read_linux_mem_available_mb", lambda: 900)

    result = runner.invoke(cli, ["--config-file", str(config_path), "doctor"])

    assert result.exit_code == 0, result.output
    assert "Raspberry Pi throttled state: 0x50005" in result.output
    assert "undervoltage has occurred" in result.output
    assert "Only about 900 MiB of memory is currently available" in result.output


def test_doctor_reports_actionable_openclaw_pairing_failure(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "profile": "openclaw",
  "audio": {
    "input_device": 0,
    "sample_rate": 44100,
    "channels": 1
  },
  "stt": {
    "selected": "whisper_cpp",
    "whisper_cpp": {
      "command": "/usr/local/bin/whisper-cli",
      "model_path": "/models/ggml-base.bin"
    }
  },
  "integration": {
    "presence_enabled": true,
    "delivery_mode": "local_only",
    "openclaw": {
      "command": "/usr/local/bin/openclaw",
      "gateway_url": "ws://127.0.0.1:18789",
      "agent_id": "main",
      "session_key": "voice-local-mic"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor_module, "list_input_devices", lambda: [object()])
    monkeypatch.setattr(
        doctor_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (0, 44_100, None, None),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_whisper_cpp_command",
        lambda command: Path("/usr/local/bin/whisper-cli"),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_model_path",
        lambda model_path: Path("/models/ggml-base.bin"),
    )
    monkeypatch.setattr(doctor_module, "is_raspberry_pi", lambda: False)
    monkeypatch.setattr(
        doctor_module,
        "build_openclaw_transport",
        lambda config: type("Transport", (), {"command": Path("/usr/local/bin/openclaw")})(),
    )
    monkeypatch.setattr(
        doctor_module,
        "discover_openclaw_auto_config",
        lambda **kwargs: OpenClawAutoConfig(
            command=Path("/usr/local/bin/openclaw"),
            config_path=tmp_path / "openclaw.json",
            gateway_url="ws://127.0.0.1:18789",
            agent_id="main",
            session_key="voice-local-mic",
            gateway_mode="local",
            gateway_bind="loopback",
            plugin_enabled=True,
            plugin_allowlisted=True,
            plugin_install_found=True,
            telegram_enabled=False,
            telegram_accounts=(),
            telegram_default_account=None,
            telegram_reply_target=None,
        ),
    )
    monkeypatch.setattr(
        doctor_module,
        "probe_openclaw_voice_ready",
        lambda **kwargs: (_ for _ in ()).throw(
            IntegrationError(
                "OpenClaw presence update failed: gateway connect failed: Error: pairing required"
            )
        ),
    )

    result = runner.invoke(cli, ["--config-file", str(config_path), "doctor"])

    assert result.exit_code != 0
    assert "pairing required" in result.output
    assert "openclaw devices approve --latest" in result.output


def test_doctor_fails_when_telegram_delivery_is_configured_but_openclaw_telegram_is_disabled(
    monkeypatch, tmp_path
) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "profile": "openclaw",
  "audio": {
    "input_device": 0,
    "sample_rate": 44100,
    "channels": 1
  },
  "stt": {
    "selected": "whisper_cpp",
    "whisper_cpp": {
      "command": "/usr/local/bin/whisper-cli",
      "model_path": "/models/ggml-base.bin"
    }
  },
  "integration": {
    "presence_enabled": true,
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
    monkeypatch.setattr(doctor_module, "list_input_devices", lambda: [object()])
    monkeypatch.setattr(
        doctor_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (0, 44_100, None, None),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_whisper_cpp_command",
        lambda command: Path("/usr/local/bin/whisper-cli"),
    )
    monkeypatch.setattr(
        doctor_module,
        "resolve_model_path",
        lambda model_path: Path("/models/ggml-base.bin"),
    )
    monkeypatch.setattr(doctor_module, "is_raspberry_pi", lambda: False)
    monkeypatch.setattr(
        doctor_module,
        "build_openclaw_transport",
        lambda config: type("Transport", (), {"command": Path("/usr/local/bin/openclaw")})(),
    )
    monkeypatch.setattr(
        doctor_module,
        "discover_openclaw_auto_config",
        lambda **kwargs: OpenClawAutoConfig(
            command=Path("/usr/local/bin/openclaw"),
            config_path=tmp_path / "openclaw.json",
            gateway_url="ws://127.0.0.1:18789",
            agent_id="main",
            session_key="voice-local-mic",
            gateway_mode="local",
            gateway_bind="loopback",
            plugin_enabled=True,
            plugin_allowlisted=True,
            plugin_install_found=True,
            telegram_enabled=False,
            telegram_accounts=(),
            telegram_default_account=None,
            telegram_reply_target=None,
        ),
    )
    monkeypatch.setattr(
        doctor_module,
        "probe_openclaw_voice_ready",
        lambda **kwargs: OpenClawVoiceReadyReport(
            ok_lines=("OpenClaw gateway responded.", "NinjaClawBot presence method responded."),
        ),
    )

    result = runner.invoke(cli, ["--config-file", str(config_path), "doctor"])

    assert result.exit_code != 0
    assert "configured to mirror replies to Telegram" in result.output


def test_doctor_warns_when_openclaw_presence_probe_times_out(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "profile": "openclaw",
  "audio": {
    "input_device": 0,
    "sample_rate": 44100,
    "channels": 1
  },
  "stt": {
    "selected": "gemini",
    "gemini": {
      "model": "gemini-2.5-flash"
    }
  },
  "integration": {
    "presence_enabled": true,
    "delivery_mode": "local_only",
    "openclaw": {
      "command": "/usr/local/bin/openclaw",
      "gateway_url": "ws://127.0.0.1:18789",
      "agent_id": "main",
      "session_key": "voice-local-mic"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor_module, "list_input_devices", lambda: [object()])
    monkeypatch.setattr(
        doctor_module,
        "resolve_supported_input_settings",
        lambda **kwargs: (0, 44_100, None, None),
    )
    monkeypatch.setattr(doctor_module, "is_raspberry_pi", lambda: False)
    monkeypatch.setattr(doctor_module.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        doctor_module,
        "resolve_gemini_api_key",
        lambda: ("GEMINI_API_KEY", "test-key"),
    )
    monkeypatch.setattr(
        doctor_module,
        "build_openclaw_transport",
        lambda config: type("Transport", (), {"command": Path("/usr/local/bin/openclaw")})(),
    )
    monkeypatch.setattr(
        doctor_module,
        "discover_openclaw_auto_config",
        lambda **kwargs: OpenClawAutoConfig(
            command=Path("/usr/local/bin/openclaw"),
            config_path=tmp_path / "openclaw.json",
            gateway_url="ws://127.0.0.1:18789",
            agent_id="main",
            session_key="voice-local-mic",
            gateway_mode="local",
            gateway_bind="loopback",
            plugin_enabled=True,
            plugin_allowlisted=True,
            plugin_install_found=True,
            telegram_enabled=False,
            telegram_accounts=(),
            telegram_default_account=None,
            telegram_reply_target=None,
        ),
    )
    monkeypatch.setattr(
        doctor_module,
        "probe_openclaw_voice_ready",
        lambda **kwargs: OpenClawVoiceReadyReport(
            ok_lines=("OpenClaw gateway responded.",),
            warnings=(
                "OpenClaw presence updates are not ready right now. Voice handoff can still work, but robot presence changes will be skipped until the plugin bridge responds again.",
                "OpenClaw presence update timed out.",
            ),
        ),
    )

    result = runner.invoke(cli, ["--config-file", str(config_path), "doctor"])

    assert result.exit_code == 0, result.output
    assert "Warnings:" in result.output
    assert "presence update timed out" in result.output.lower()


def test_install_whispercpp_saves_detected_paths(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "mic.json"
    model_path = tmp_path / "ggml-base.bin"
    model_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        install_cmd_module,
        "find_whisper_cpp_command",
        lambda command=None: Path("/usr/local/bin/whisper-cli"),
    )
    monkeypatch.setattr(
        install_cmd_module,
        "resolve_model_path",
        lambda model_path: Path(model_path),
    )

    result = runner.invoke(
        cli,
        [
            "--config-file",
            str(config_path),
            "install",
            "whispercpp",
            "--model-path",
            str(model_path),
        ],
    )

    assert result.exit_code == 0, result.output
    saved = config_path.read_text(encoding="utf-8")
    assert "/usr/local/bin/whisper-cli" in saved
    assert str(model_path) in saved
