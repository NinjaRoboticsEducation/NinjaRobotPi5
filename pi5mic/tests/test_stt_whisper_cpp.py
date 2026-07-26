"""Tests for the whisper.cpp STT backend."""

from __future__ import annotations

import json
import wave
from types import SimpleNamespace

import pytest

from pi5mic.errors import NoSpeechDetectedError, STTError
from pi5mic.install import whisper_cpp as install_module
from pi5mic.stt.whisper_cpp import (
    WhisperCppBackend,
    describe_whisper_runtime,
    recommend_whisper_threads,
)


def test_find_whisper_cpp_command_uses_which(monkeypatch, tmp_path) -> None:
    command_path = tmp_path / "whisper-cli"
    command_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(install_module.shutil, "which", lambda name: str(command_path))

    assert install_module.find_whisper_cpp_command() == command_path.resolve()


def test_resolve_model_path_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(STTError, match="Whisper model file not found"):
        install_module.resolve_model_path(tmp_path / "missing.bin")


def test_whisper_cpp_backend_transcribes_from_json_output(monkeypatch, tmp_path) -> None:
    command_path = tmp_path / "whisper-cli"
    model_path = tmp_path / "ggml-base.bin"
    audio_path = tmp_path / "clip.wav"
    command_path.write_text("", encoding="utf-8")
    model_path.write_text("", encoding="utf-8")
    audio_path.write_bytes(b"RIFF")

    def fake_run(command, **kwargs):
        del kwargs
        output_prefix = command[command.index("-of") + 1]
        with open(f"{output_prefix}.json", "w", encoding="utf-8") as handle:
            json.dump({"text": "hello world", "language": "en"}, handle)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("pi5mic.stt.whisper_cpp.subprocess.run", fake_run)

    backend = WhisperCppBackend(command=command_path, model_path=model_path)
    result = backend.transcribe(audio_path)

    assert result.text == "hello world"
    assert result.backend == "whisper_cpp"
    assert result.model == "ggml-base.bin"
    assert result.language == "en"


def test_whisper_cpp_backend_joins_segment_text(monkeypatch, tmp_path) -> None:
    command_path = tmp_path / "whisper-cli"
    model_path = tmp_path / "ggml-base.bin"
    audio_path = tmp_path / "clip.wav"
    command_path.write_text("", encoding="utf-8")
    model_path.write_text("", encoding="utf-8")
    audio_path.write_bytes(b"RIFF")

    def fake_run(command, **kwargs):
        del kwargs
        output_prefix = command[command.index("-of") + 1]
        with open(f"{output_prefix}.json", "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "segments": [
                        {"text": "hello"},
                        {"text": "world"},
                    ]
                },
                handle,
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("pi5mic.stt.whisper_cpp.subprocess.run", fake_run)

    backend = WhisperCppBackend(command=command_path, model_path=model_path)
    result = backend.transcribe(audio_path)

    assert result.text == "hello world"


def test_whisper_cpp_backend_raises_when_json_missing(monkeypatch, tmp_path) -> None:
    command_path = tmp_path / "whisper-cli"
    model_path = tmp_path / "ggml-base.bin"
    audio_path = tmp_path / "clip.wav"
    command_path.write_text("", encoding="utf-8")
    model_path.write_text("", encoding="utf-8")
    audio_path.write_bytes(b"RIFF")

    monkeypatch.setattr(
        "pi5mic.stt.whisper_cpp.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    backend = WhisperCppBackend(command=command_path, model_path=model_path)
    with pytest.raises(STTError, match="without producing a JSON transcript"):
        backend.transcribe(audio_path)


def test_whisper_cpp_backend_reports_no_speech_for_empty_transcription(
    monkeypatch, tmp_path
) -> None:
    command_path = tmp_path / "whisper-cli"
    model_path = tmp_path / "ggml-base.bin"
    audio_path = tmp_path / "clip.wav"
    command_path.write_text("", encoding="utf-8")
    model_path.write_text("", encoding="utf-8")
    audio_path.write_bytes(b"RIFF")

    def fake_run(command, **kwargs):
        del kwargs
        output_prefix = command[command.index("-of") + 1]
        with open(f"{output_prefix}.json", "w", encoding="utf-8") as handle:
            json.dump({"result": {"language": "en"}, "transcription": []}, handle)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("pi5mic.stt.whisper_cpp.subprocess.run", fake_run)

    backend = WhisperCppBackend(command=command_path, model_path=model_path)
    with pytest.raises(NoSpeechDetectedError, match="did not detect spoken text"):
        backend.transcribe(audio_path)


def test_recommend_whisper_threads_uses_safe_raspberry_pi_default(monkeypatch) -> None:
    monkeypatch.setattr("pi5mic.stt.whisper_cpp.is_raspberry_pi", lambda: True)
    monkeypatch.setattr("pi5mic.stt.whisper_cpp.os.cpu_count", lambda: 4)

    assert recommend_whisper_threads() == 2
    assert "safe Raspberry Pi default" in describe_whisper_runtime(None)


def test_whisper_cpp_backend_normalizes_wav_before_transcribing(monkeypatch, tmp_path) -> None:
    command_path = tmp_path / "whisper-cli"
    model_path = tmp_path / "ggml-base.bin"
    audio_path = tmp_path / "clip.wav"
    command_path.write_text("", encoding="utf-8")
    model_path.write_text("", encoding="utf-8")

    with wave.open(str(audio_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44_100)
        handle.writeframes(b"\x00\x00" * 44_100)

    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        del kwargs
        captured["command"] = command
        prepared_audio = command[command.index("-f") + 1]
        with wave.open(prepared_audio, "rb") as handle:
            captured["sample_rate"] = handle.getframerate()
            captured["channels"] = handle.getnchannels()
        output_prefix = command[command.index("-of") + 1]
        with open(f"{output_prefix}.json", "w", encoding="utf-8") as handle:
            json.dump({"text": "hello world", "language": "en"}, handle)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("pi5mic.stt.whisper_cpp.subprocess.run", fake_run)

    backend = WhisperCppBackend(command=command_path, model_path=model_path, threads=2)
    result = backend.transcribe(audio_path)

    assert result.text == "hello world"
    assert captured["sample_rate"] == 16_000
    assert captured["channels"] == 1
    assert "-np" in captured["command"]
