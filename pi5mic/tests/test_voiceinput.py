"""Tests for always-on voice input helpers."""

from __future__ import annotations

import copy
import importlib
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from pi5mic.config.config_manager import DEFAULT_CONFIG
from pi5mic.core.voiceinput import (
    build_voiceinput_runtime_paths,
    normalize_voiceinput_config,
    read_voiceinput_state,
    update_voiceinput_state,
    validate_voiceinput_readiness,
)
from pi5mic.errors import NoSpeechDetectedError, WakeWordError
from pi5mic.models import TranscriptionResult

voiceinput_module = importlib.import_module("pi5mic.core.voiceinput")


def _enabled_voiceinput_config() -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["voiceinput"]["enabled"] = True
    config["wakeword"]["enabled"] = True
    config["wakeword"]["keyword"] = "ninja"
    config["wakeword"]["model_path"] = "/models/ninja.tflite"
    return config


def test_normalize_voiceinput_config_accepts_supported_values() -> None:
    config = _enabled_voiceinput_config()

    normalized = normalize_voiceinput_config(config)

    assert normalized["backend"] == "openwakeword"
    assert normalized["keyword"] == "ninja"
    assert normalized["model_path"] == "/models/ninja.tflite"
    assert normalized["session_strategy"] == "agent_main"


def test_read_voiceinput_state_marks_stale_process_as_stopped(tmp_path) -> None:
    paths = build_voiceinput_runtime_paths(tmp_path / "mic.json")
    update_voiceinput_state(
        paths,
        running=True,
        pid=999_999,
        mode="running",
        listener_state="listening",
    )

    state = read_voiceinput_state(paths)

    assert state["running"] is False
    assert state["mode"] == "stopped"
    assert state["pid"] is None


def test_validate_voiceinput_readiness_requires_model_path(monkeypatch) -> None:
    config = _enabled_voiceinput_config()
    config["wakeword"]["model_path"] = None

    with pytest.raises(WakeWordError, match="model path"):
        validate_voiceinput_readiness(config)


def test_validate_voiceinput_readiness_returns_detector_details(monkeypatch) -> None:
    config = _enabled_voiceinput_config()

    class _FakeDetector:
        frame_length = 1280
        sample_rate = 16_000

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        voiceinput_module,
        "resolve_openwakeword_model_path",
        lambda model_path: Path("/models/ninja.tflite"),
    )
    monkeypatch.setattr(
        voiceinput_module,
        "resolve_openwakeword_inference_framework",
        lambda *, model_path, configured_framework: "tflite",
    )
    monkeypatch.setattr(
        voiceinput_module, "build_wakeword_detector", lambda config: _FakeDetector()
    )

    readiness = validate_voiceinput_readiness(config)

    assert readiness["detector_frame_length"] == 1280
    assert readiness["detector_sample_rate"] == 16_000
    assert readiness["keyword"] == "ninja"
    assert readiness["resolved_inference_framework"] == "tflite"


def test_voiceinput_loop_reopens_stream_around_processing(monkeypatch, tmp_path) -> None:
    config = _enabled_voiceinput_config()
    config["audio"]["sample_rate"] = 16_000
    config["audio"]["channels"] = 1
    config["audio"]["block_size"] = 2
    config["voiceinput"]["max_capture_seconds"] = 0.1
    config["voiceinput"]["silence_timeout_seconds"] = 0.1
    config_path = tmp_path / "mic.json"
    paths = build_voiceinput_runtime_paths(config_path)
    stop_event = Event()
    events: list[str] = []

    class _FakeDetector:
        frame_length = 2
        sample_rate = 16_000

        def __init__(self) -> None:
            self._calls = 0

        def process(self, pcm_frame) -> object:
            del pcm_frame
            self._calls += 1
            return SimpleNamespace(detected=self._calls == 1)

        def reset(self) -> None:
            events.append("detector.reset")

        def close(self) -> None:
            events.append("detector.close")

    class _FakeVad:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def process(self, frame) -> object:
            del frame
            return SimpleNamespace(should_stop=True)

        def reset(self) -> None:
            events.append("vad.reset")

    class _FakeStream:
        _instance_count = 0

        def __init__(self, **kwargs) -> None:
            del kwargs
            type(self)._instance_count += 1
            self._instance_id = type(self)._instance_count

        def __enter__(self):
            events.append(f"stream.enter.{self._instance_id}")
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb
            events.append(f"stream.exit.{self._instance_id}")

        def read(self, frames):
            del frames
            if self._instance_id == 2:
                stop_event.set()
            return (b"\x00\x00\x00\x00", False)

    class _FakeSoundDevice:
        RawInputStream = _FakeStream

    def _fake_process_capture(self, **kwargs) -> None:
        del self, kwargs
        events.append("process_capture")

    monkeypatch.setattr(
        voiceinput_module, "build_wakeword_detector", lambda config: _FakeDetector()
    )
    monkeypatch.setattr(voiceinput_module, "SilenceStopDetector", _FakeVad)
    monkeypatch.setattr(voiceinput_module, "_get_sounddevice", lambda: _FakeSoundDevice())
    monkeypatch.setattr(
        voiceinput_module,
        "resolve_supported_input_settings",
        lambda selector, sample_rate, channels: (
            None,
            sample_rate,
            SimpleNamespace(name="Fake Mic", index=0),
            None,
        ),
    )
    monkeypatch.setattr(voiceinput_module.VoiceInputLoop, "_process_capture", _fake_process_capture)
    monkeypatch.setattr("pi5mic.cli._common.build_stt_backend", lambda config: object())

    loop = voiceinput_module.VoiceInputLoop(
        config=config,
        config_path=config_path,
        state_paths=paths,
        event_logger=lambda message: None,
    )
    loop.run(stop_event)

    assert "process_capture" in events
    assert "stream.enter.1" in events
    assert "stream.exit.1" in events
    assert "stream.enter.2" in events
    assert (
        events.index("stream.exit.1")
        < events.index("process_capture")
        < events.index("stream.enter.2")
    )


def test_process_capture_treats_no_speech_as_recoverable(tmp_path) -> None:
    config = _enabled_voiceinput_config()
    config_path = tmp_path / "mic.json"
    paths = build_voiceinput_runtime_paths(config_path)
    messages: list[str] = []
    listener = voiceinput_module.MicListener(cooldown_seconds=1.0)
    request_id = listener.arm().active_request_id
    del request_id
    request_id = listener.start_listening().active_request_id
    assert request_id is not None

    class _FakeBackend:
        def transcribe(self, audio_path):
            del audio_path
            raise NoSpeechDetectedError("whisper.cpp did not detect spoken text in the audio clip.")

    loop = voiceinput_module.VoiceInputLoop(
        config=config,
        config_path=config_path,
        state_paths=paths,
        event_logger=messages.append,
    )

    loop._process_capture(
        listener=listener,
        request_id=request_id,
        capture_pcm=b"\x00\x00" * 32,
        sample_rate=16_000,
        stt_backend=_FakeBackend(),
        transport=None,
        presence_updater=None,
    )

    assert listener.snapshot().state.value == "cooldown"
    assert any(
        "No spoken command was detected after the wake word" in message for message in messages
    )


def test_process_capture_reports_transcript_to_detail_logger(tmp_path) -> None:
    config = _enabled_voiceinput_config()
    config_path = tmp_path / "mic.json"
    paths = build_voiceinput_runtime_paths(config_path)
    listener = voiceinput_module.MicListener(cooldown_seconds=1.0)
    detail_messages: list[str] = []
    request_id = listener.arm().active_request_id
    del request_id
    request_id = listener.start_listening().active_request_id
    assert request_id is not None

    class _FakeBackend:
        def transcribe(self, audio_path):
            del audio_path
            return TranscriptionResult(
                text="turn on the light",
                backend="whisper_cpp",
                model="ggml-base.bin",
                language="en",
            )

    loop = voiceinput_module.VoiceInputLoop(
        config=config,
        config_path=config_path,
        state_paths=paths,
        event_logger=lambda message: None,
        detail_logger=detail_messages.append,
    )

    loop._process_capture(
        listener=listener,
        request_id=request_id,
        capture_pcm=b"\x00\x00" * 32,
        sample_rate=16_000,
        stt_backend=_FakeBackend(),
        transport=None,
        presence_updater=None,
    )

    assert "Transcript: turn on the light" in detail_messages


def test_process_capture_submits_presence_updates_for_openclaw(tmp_path) -> None:
    config = _enabled_voiceinput_config()
    config_path = tmp_path / "mic.json"
    paths = build_voiceinput_runtime_paths(config_path)
    listener = voiceinput_module.MicListener(cooldown_seconds=1.0)
    detail_messages: list[str] = []
    request_id = listener.arm().active_request_id
    del request_id
    request_id = listener.start_listening().active_request_id
    assert request_id is not None
    presence_events: list[tuple[str, str]] = []

    class _FakeBackend:
        def transcribe(self, audio_path):
            del audio_path
            return TranscriptionResult(
                text="hello there",
                backend="gemini",
                model="gemini-2.5-flash",
                language="en",
            )

    class _FakeTransport:
        def dispatch(self, text):
            assert text == "hello there"
            return SimpleNamespace(reply_text="general kenobi")

    class _FakePresenceUpdater:
        def submit(self, mode: str, *, reason: str) -> None:
            presence_events.append((mode, reason))

    loop = voiceinput_module.VoiceInputLoop(
        config=config,
        config_path=config_path,
        state_paths=paths,
        event_logger=lambda message: None,
        detail_logger=detail_messages.append,
    )

    loop._process_capture(
        listener=listener,
        request_id=request_id,
        capture_pcm=b"\x00\x00" * 32,
        sample_rate=16_000,
        stt_backend=_FakeBackend(),
        transport=_FakeTransport(),
        presence_updater=_FakePresenceUpdater(),
    )

    assert ("thinking", "pi5mic.voiceinput.dispatch") in presence_events
    assert ("idle", "pi5mic.voiceinput.idle") in presence_events
    assert "Transcript: hello there" in detail_messages
    assert "OpenClaw reply: general kenobi" in detail_messages


def test_voiceinput_loop_recovers_after_repeated_overflow(monkeypatch, tmp_path) -> None:
    config = _enabled_voiceinput_config()
    config["audio"]["sample_rate"] = 16_000
    config["audio"]["channels"] = 1
    config["audio"]["block_size"] = 2
    config["voiceinput"]["max_capture_seconds"] = 0.1
    config["voiceinput"]["silence_timeout_seconds"] = 0.1
    config_path = tmp_path / "mic.json"
    paths = build_voiceinput_runtime_paths(config_path)
    stop_event = Event()
    messages: list[str] = []
    events: list[str] = []

    class _FakeDetector:
        frame_length = 2
        sample_rate = 16_000

        def __init__(self) -> None:
            self._calls = 0

        def process(self, pcm_frame) -> object:
            del pcm_frame
            self._calls += 1
            return SimpleNamespace(detected=self._calls == 1)

        def reset(self) -> None:
            events.append("detector.reset")

        def close(self) -> None:
            events.append("detector.close")

    class _FakeVad:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def process(self, frame) -> object:
            del frame
            return SimpleNamespace(should_stop=True)

        def reset(self) -> None:
            events.append("vad.reset")

    class _FakeStream:
        _instance_count = 0

        def __init__(self, **kwargs) -> None:
            del kwargs
            type(self)._instance_count += 1
            self._instance_id = type(self)._instance_count
            self._reads = 0

        def __enter__(self):
            events.append(f"stream.enter.{self._instance_id}")
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb
            events.append(f"stream.exit.{self._instance_id}")

        def read(self, frames):
            del frames
            self._reads += 1
            if self._instance_id == 1:
                return (b"\x00\x00\x00\x00", True)
            return (b"\x00\x00\x00\x00", False)

    class _FakeSoundDevice:
        RawInputStream = _FakeStream

    def _fake_process_capture(self, **kwargs) -> None:
        del self, kwargs
        events.append("process_capture")
        stop_event.set()

    monkeypatch.setattr(
        voiceinput_module, "build_wakeword_detector", lambda config: _FakeDetector()
    )
    monkeypatch.setattr(voiceinput_module, "SilenceStopDetector", _FakeVad)
    monkeypatch.setattr(voiceinput_module, "_get_sounddevice", lambda: _FakeSoundDevice())
    monkeypatch.setattr(
        voiceinput_module,
        "resolve_supported_input_settings",
        lambda selector, sample_rate, channels: (
            None,
            sample_rate,
            SimpleNamespace(name="Fake Mic", index=0),
            None,
        ),
    )
    monkeypatch.setattr(voiceinput_module.VoiceInputLoop, "_process_capture", _fake_process_capture)
    monkeypatch.setattr("pi5mic.cli._common.build_stt_backend", lambda config: object())

    loop = voiceinput_module.VoiceInputLoop(
        config=config,
        config_path=config_path,
        state_paths=paths,
        event_logger=messages.append,
    )
    loop.run(stop_event)

    assert "process_capture" in events
    assert "stream.enter.1" in events
    assert "stream.enter.2" in events
    assert any("recreating the live input stream" in message for message in messages)
    assert any(
        "Voice input recovered and is waiting for the next wake word." in message
        for message in messages
    )


def test_async_presence_updater_disables_after_first_failure() -> None:
    messages: list[str] = []
    calls: list[tuple[str, str]] = []

    class _FailingController:
        def set_mode(self, mode: str, *, reason: str):
            calls.append((mode, reason))
            raise voiceinput_module.IntegrationError("OpenClaw presence update timed out.")

    updater = voiceinput_module._AsyncPresenceUpdater(
        _FailingController(),
        log=messages.append,
    )

    updater.submit("listening", reason="test.listening")
    updater.submit("idle", reason="test.idle")
    updater.shutdown()

    import time

    time.sleep(0.05)

    assert calls == [("listening", "test.listening")]
    assert any("presence 'listening' failed" in message for message in messages)
    assert any(
        "will be skipped for the rest of this listener session" in message for message in messages
    )
