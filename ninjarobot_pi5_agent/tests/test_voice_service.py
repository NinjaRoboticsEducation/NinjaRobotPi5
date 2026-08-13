"""Agent-side voice identity, event, persistence, and lifecycle tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from ninjarobot_pi5_agent.events import EventBroker
from ninjarobot_pi5_agent.release_foundations import ReleaseStatusRegistry
from ninjarobot_pi5_agent.voice_service import (
    VOICE_SESSION_ID,
    VoiceInputService,
    persist_voice_input_enabled,
)
from ninjarobot_pi5_ide.voice_input import VoiceInputState, VoiceInputStatus

from ninjarobot_pi5_ide import load_robot_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"


class FakeIDE:
    def __init__(self) -> None:
        self.transcript_handler = None
        self.status_handler = None
        self.started = False
        self.stopped = False
        self.start_error: Exception | None = None

    def bind_voice_handlers(self, *, transcript_handler, status_handler) -> None:
        self.transcript_handler = transcript_handler
        self.status_handler = status_handler

    async def start_voice_input(self) -> dict[str, object]:
        self.started = True
        if self.start_error is not None:
            raise self.start_error
        return {"enabled": True, "state": "listening"}

    async def stop_voice_input(self) -> dict[str, object]:
        self.stopped = True
        return {"enabled": False, "state": "disabled"}

    def voice_input_status(self) -> dict[str, object]:
        return {"enabled": self.started and not self.stopped, "state": "listening"}


class FakeRuntime:
    def __init__(self) -> None:
        self.chats: list[tuple[str, str]] = []
        self.disarms: list[str | None] = []

    async def chat(self, *, session_id: str, text: str, **_kwargs):
        self.chats.append((session_id, text))
        return SimpleNamespace(text="Voice reply")

    def disarm_voice_motion(self, *, lease_id: str | None = None) -> None:
        self.disarms.append(lease_id)


def build_service(*, configured_enabled: bool = False):
    ide = FakeIDE()
    runtime = FakeRuntime()
    events = EventBroker()
    release = ReleaseStatusRegistry.disabled()
    persisted: list[bool] = []

    async def persist(enabled: bool) -> None:
        persisted.append(enabled)

    service = VoiceInputService(
        ide=ide,  # type: ignore[arg-type]
        runtime=runtime,  # type: ignore[arg-type]
        events=events,
        release_status=release,
        configured_enabled=configured_enabled,
        persist_enabled=persist,
    )
    return service, ide, runtime, events, release, persisted


def test_voice_transcript_uses_independent_owner_session_and_publishes_reply() -> None:
    async def scenario() -> None:
        service, _ide, runtime, events, _release, _persisted = build_service()

        await service.handle_transcript("move safely", "en")

        assert runtime.chats == [(VOICE_SESSION_ID, "move safely")]
        history = await events.history()
        assert [event.data["kind"] for event in history] == [
            "voice_transcript",
            "voice_reply",
        ]
        assert history[0].data["transcript"] == "move safely"
        assert history[1].data["text"] == "Voice reply"

    asyncio.run(scenario())


def test_explicit_enable_disable_persists_and_clears_voice_motion() -> None:
    async def scenario() -> None:
        service, ide, runtime, _events, release, persisted = build_service()

        await service.enable()
        await service.disable()

        assert ide.started is True
        assert ide.stopped is True
        assert runtime.disarms == [None]
        assert persisted == [True, False]
        assert release.status()["voice"]["state"] == "disabled"

    asyncio.run(scenario())


def test_start_configured_does_not_persist_again() -> None:
    async def scenario() -> None:
        service, ide, _runtime, _events, _release, persisted = build_service(
            configured_enabled=True
        )

        await service.start_configured()

        assert ide.started is True
        assert persisted == []

    asyncio.run(scenario())


def test_failed_explicit_enable_rolls_back_persistence_and_motion() -> None:
    async def scenario() -> None:
        service, ide, runtime, events, release, persisted = build_service()
        ide.start_error = RuntimeError("microphone unavailable")

        with pytest.raises(RuntimeError, match="microphone unavailable"):
            await service.enable()

        assert ide.stopped is True
        assert persisted == [False]
        assert runtime.disarms == [None]
        voice_status = release.status()["voice"]
        assert voice_status["enabled"] is False
        assert voice_status["state"] == "disabled"
        assert (await events.history())[-1].data["code"] == "listener_start_failed"

    asyncio.run(scenario())


def test_failed_status_is_safe_and_includes_manual_fallback_guidance() -> None:
    async def scenario() -> None:
        service, _ide, _runtime, events, release, _persisted = build_service()
        status = VoiceInputStatus(
            enabled=True,
            state=VoiceInputState.FAILED,
            language="ja",
            last_error_code="microphone_unavailable",
        )

        await service.handle_status(status)

        assert release.status()["voice"]["state"] == "failed"
        event = (await events.history())[-1]
        assert "Manual terminal and web chat remain available" in event.message
        assert event.data["error_code"] == "microphone_unavailable"
        assert "token" not in event.model_dump_json()

    asyncio.run(scenario())


def test_voice_enable_persistence_changes_only_validated_switch(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_bytes(EXAMPLE.read_bytes())
    before = load_robot_config(config_path)

    asyncio.run(persist_voice_input_enabled(config_path, True))
    enabled = load_robot_config(config_path)
    asyncio.run(persist_voice_input_enabled(config_path, False))
    disabled = load_robot_config(config_path)

    assert enabled.voice_input.enabled is True
    assert disabled.voice_input.enabled is False
    assert enabled.hardware == before.hardware
    assert enabled.providers == before.providers
