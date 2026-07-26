"""Tests for the Gemini STT backend."""

from __future__ import annotations

import sys
import types

import pytest

from pi5mic.errors import STTError
from pi5mic.stt.gemini import GeminiBackend, describe_gemini_env_help, resolve_gemini_api_key


def test_gemini_backend_requires_credentials(monkeypatch, tmp_path) -> None:
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"RIFF")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    backend = GeminiBackend()
    with pytest.raises(STTError, match="GOOGLE_API_KEY or GEMINI_API_KEY"):
        backend.transcribe(audio_path)


def test_resolve_gemini_api_key_prefers_google_api_key(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")

    credential_name, api_key = resolve_gemini_api_key()

    assert credential_name == "GOOGLE_API_KEY"
    assert api_key == "google-key"
    assert "export GEMINI_API_KEY" in describe_gemini_env_help()


def test_gemini_backend_transcribes_audio(monkeypatch, tmp_path) -> None:
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"RIFF")
    monkeypatch.setenv("GEMINI_API_KEY", "demo-key")

    captured: dict[str, object] = {}

    class _FakePart:
        @staticmethod
        def from_bytes(*, data, mime_type):
            captured["mime_type"] = mime_type
            captured["bytes"] = data
            return {"mime_type": mime_type, "bytes": data}

    class _FakeModels:
        def generate_content(self, *, model, contents):
            captured["model"] = model
            captured["contents"] = contents
            return types.SimpleNamespace(text="こんにちは")

    class _FakeHttpRetryOptions:
        def __init__(self, *, attempts, initial_delay, max_delay):
            self.attempts = attempts
            self.initial_delay = initial_delay
            self.max_delay = max_delay

    class _FakeHttpOptions:
        def __init__(self, *, timeout, retry_options):
            self.timeout = timeout
            self.retry_options = retry_options

    class _FakeClient:
        def __init__(self, *, api_key=None, http_options=None):
            captured["api_key"] = api_key
            captured["http_options"] = http_options
            self.models = _FakeModels()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    genai_module.Client = _FakeClient
    genai_module.types = types.SimpleNamespace(
        Part=_FakePart,
        HttpOptions=_FakeHttpOptions,
        HttpRetryOptions=_FakeHttpRetryOptions,
    )
    google_module.genai = genai_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)

    backend = GeminiBackend(model="gemini-2.5-flash", timeout_seconds=45, retry_limit=2)
    result = backend.transcribe(audio_path)

    assert result.text == "こんにちは"
    assert result.backend == "gemini"
    assert captured["model"] == "gemini-2.5-flash"
    assert captured["mime_type"] == "audio/wav"
    assert captured["api_key"] == "demo-key"
    assert captured["http_options"].timeout == 45_000
    assert captured["http_options"].retry_options.attempts == 3
