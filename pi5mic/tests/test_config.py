"""Tests for pi5mic configuration management."""

from __future__ import annotations

import json

import pytest

from pi5mic.config.config_manager import (
    DEFAULT_CONFIG,
    MicConfigManager,
    get_default_config_filepath,
)
from pi5mic.errors import ConfigError


def test_default_config_path_uses_cwd(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert get_default_config_filepath() == tmp_path / "mic.json"


def test_load_returns_defaults_when_file_is_missing(tmp_path) -> None:
    manager = MicConfigManager(tmp_path / "mic.json")

    config = manager.load()

    assert config["profile"] == DEFAULT_CONFIG["profile"]
    assert config["audio"]["sample_rate"] == DEFAULT_CONFIG["audio"]["sample_rate"]
    assert config["stt"]["selected"] == "whisper_cpp"
    assert config["wakeword"]["backend"] == "openwakeword"
    assert config["voiceinput"]["enabled"] is False
    assert config["voiceinput"]["session_strategy"] == "agent_main"
    assert config["integration"]["openclaw"]["gateway_url"] == "ws://127.0.0.1:18789"
    assert config["integration"]["openclaw"]["session_key"] == "voice-local-mic"


def test_save_roundtrip_preserves_nested_values(tmp_path) -> None:
    config_path = tmp_path / "mic.json"
    manager = MicConfigManager(config_path)
    config = manager.load()
    config["profile"] = "openclaw"
    config["audio"]["input_device"] = "USB Microphone"
    config["stt"]["gemini"]["retry_limit"] = 4
    manager.replace(config)
    manager.save()

    loaded = MicConfigManager(config_path).load()

    assert loaded["profile"] == "openclaw"
    assert loaded["audio"]["input_device"] == "USB Microphone"
    assert loaded["stt"]["gemini"]["retry_limit"] == 4
    assert loaded["integration"]["openclaw"]["session_key"] == "voice-local-mic"


def test_load_migrates_legacy_openclaw_session_id(tmp_path) -> None:
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "profile": "openclaw",
  "integration": {
    "openclaw": {
      "session_key": "voice:local-mic"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    loaded = MicConfigManager(config_path).load()

    assert loaded["integration"]["openclaw"]["session_key"] == "voice-local-mic"


def test_load_migrates_legacy_porcupine_wakeword_config(tmp_path) -> None:
    config_path = tmp_path / "mic.json"
    config_path.write_text(
        """
{
  "wakeword": {
    "enabled": true,
    "backend": "porcupine",
    "keyword": "ninja",
    "keyword_path": "/tmp/ninja.tflite",
    "access_key_env_var": "PICOVOICE_ACCESS_KEY"
  }
}
""".strip(),
        encoding="utf-8",
    )

    loaded = MicConfigManager(config_path).load()

    assert loaded["wakeword"]["backend"] == "openwakeword"
    assert loaded["wakeword"]["model_path"] == "/tmp/ninja.tflite"
    assert "keyword_path" not in loaded["wakeword"]
    assert "access_key_env_var" not in loaded["wakeword"]


def test_load_rejects_invalid_json(tmp_path) -> None:
    config_path = tmp_path / "mic.json"
    config_path.write_text("{oops", encoding="utf-8")

    manager = MicConfigManager(config_path)
    with pytest.raises(ConfigError, match="not valid JSON"):
        manager.load()


def test_load_rejects_non_object_json(tmp_path) -> None:
    config_path = tmp_path / "mic.json"
    config_path.write_text("[]", encoding="utf-8")

    manager = MicConfigManager(config_path)
    with pytest.raises(ConfigError, match="must contain a JSON object"):
        manager.load()


def test_import_export_roundtrip(tmp_path) -> None:
    source_path = tmp_path / "source.json"
    export_path = tmp_path / "export.json"
    imported_path = tmp_path / "imported.json"

    manager = MicConfigManager(source_path)
    config = manager.load()
    config["audio"]["sample_rate"] = 22_050
    manager.replace(config)
    manager.save()

    manager.export_config(export_path)
    imported = MicConfigManager(imported_path)
    imported.import_config(export_path)
    imported.save()

    with imported_path.open(encoding="utf-8") as handle:
        saved = json.load(handle)

    assert saved["audio"]["sample_rate"] == 22_050
