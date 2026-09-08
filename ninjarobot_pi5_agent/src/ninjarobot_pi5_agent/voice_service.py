"""Agent bridge for IDE-owned voice input, owner identity, events, and config."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

from ninjarobot_pi5_ide.voice_input import VoiceInputState, VoiceInputStatus

from ninjarobot_pi5_ide import RobotIDEClient, load_robot_config, save_robot_config

from .agent_loop import AgentReply, TextDeltaHandler
from .events import CURRENT_LIFECYCLE, AgentEventType, EventBroker, LifecycleTrace, log_lifecycle
from .release_foundations import ReleaseFeatureState, ReleaseStatusRegistry
from .tools import CancellationToken

VOICE_SESSION_ID = "voice-owner"
PersistVoiceSetting = Callable[[bool], Awaitable[None]]


class VoiceRuntime(Protocol):
    """Minimal runtime boundary used to avoid a reverse hardware dependency."""

    async def chat(
        self,
        *,
        session_id: str,
        text: str,
        skill_id: str | None = None,
        lease_id: str | None = None,
        confirmed: bool = False,
        cancellation: CancellationToken | None = None,
        on_text_delta: TextDeltaHandler | None = None,
    ) -> AgentReply: ...

    def disarm_voice_motion(self, *, lease_id: str | None = None) -> None: ...


class VoiceInputService:
    """Dispatch voice transcripts through the same chat/policy/memory path."""

    def __init__(
        self,
        *,
        ide: RobotIDEClient,
        runtime: VoiceRuntime,
        events: EventBroker,
        release_status: ReleaseStatusRegistry,
        configured_enabled: bool,
        persist_enabled: PersistVoiceSetting,
    ) -> None:
        self._ide = ide
        self._runtime = runtime
        self._events = events
        self._release_status = release_status
        self._configured_enabled = configured_enabled
        self._persist_enabled = persist_enabled
        self._dispatch_lock = asyncio.Lock()
        self._closed = False
        self._last_reported: tuple[str, str | None] | None = None
        self._voice_trace: LifecycleTrace | None = None
        ide.bind_voice_handlers(
            transcript_handler=self.handle_transcript,
            status_handler=self.handle_status,
        )

    async def start_configured(self) -> dict[str, object]:
        """Honor only the explicit persisted enable flag from validated config."""
        if not self._configured_enabled:
            return self.status()
        return await self.enable(persist=False)

    async def enable(self, *, persist: bool = True) -> dict[str, object]:
        """Start the listener and optionally persist the explicit operator action."""
        if self._closed:
            raise RuntimeError("voice input service is closed")
        self._release_status.set_enabled("voice", True)
        try:
            status = await self._ide.start_voice_input()
            if status.get("state") != VoiceInputState.LISTENING.value:
                raise RuntimeError("voice listener did not report ready")
        except Exception:
            try:
                await self._ide.stop_voice_input()
            except Exception:
                pass
            self._runtime.disarm_voice_motion()
            self._release_status.set_enabled("voice", False)
            if persist:
                try:
                    await self._persist_enabled(False)
                except Exception:
                    pass
            await self._events.publish(
                AgentEventType.ERROR,
                "Voice input could not start. Check the USB microphone, wake model, "
                "and local transcription setup, then disable and re-enable voice input.",
                session_id=VOICE_SESSION_ID,
                data={"kind": "voice_error", "code": "listener_start_failed"},
            )
            raise
        if persist:
            await self._persist_enabled(True)
        await self._events.publish(
            AgentEventType.VOICE,
            "Always-on voice input was enabled; say Hey Ninja before a command.",
            session_id=VOICE_SESSION_ID,
            data={"kind": "voice_enabled"},
        )
        return status

    async def disable(self, *, persist: bool = True) -> dict[str, object]:
        """Stop listening, clear voice motion, and persist when user-requested."""
        status = await self._ide.stop_voice_input()
        self._runtime.disarm_voice_motion()
        self._release_status.set_enabled("voice", False)
        if persist:
            await self._persist_enabled(False)
        await self._events.publish(
            AgentEventType.VOICE,
            "Always-on voice input was disabled and voice motion authorization was cleared.",
            session_id=VOICE_SESSION_ID,
            data={"kind": "voice_disabled"},
        )
        return status

    def status(self) -> dict[str, object]:
        """Return listener state without probing audio or exposing transcript text."""
        return self._ide.voice_input_status()

    async def handle_transcript(self, transcript: str, language: str) -> None:
        """Send one finalized transcript exactly once through AgentRuntime.chat."""
        async with self._dispatch_lock:
            trace_token = CURRENT_LIFECYCLE.set(
                self._voice_trace or LifecycleTrace.create(VOICE_SESSION_ID)
            )
            try:
                await self._events.publish(
                    AgentEventType.VOICE,
                    "Voice command transcribed.",
                    session_id=VOICE_SESSION_ID,
                    data={
                        "kind": "voice_transcript",
                        "transcript": transcript,
                        "language": language,
                    },
                )
                reply = await self._runtime.chat(
                    session_id=VOICE_SESSION_ID,
                    text=transcript,
                )
                reply_text = str(getattr(reply, "text", ""))
                await self._events.publish(
                    AgentEventType.VOICE,
                    "Voice command completed.",
                    session_id=VOICE_SESSION_ID,
                    data={
                        "kind": "voice_reply",
                        "text": reply_text,
                        "language": language,
                    },
                )
            finally:
                CURRENT_LIFECYCLE.reset(trace_token)
                self._voice_trace = None

    async def handle_status(self, status: VoiceInputStatus) -> None:
        """Normalize IDE state and publish changes without raw exception text."""
        if status.state is VoiceInputState.DISABLED:
            self._release_status.set_enabled("voice", False)
        else:
            current = self._release_status.status().get("voice")
            if not isinstance(current, dict) or current.get("enabled") is not True:
                self._release_status.set_enabled("voice", True)
            self._release_status.update(
                "voice",
                _release_state(status.state),
                detail=status.last_error_code,
            )
        marker = (status.state.value, status.last_error_code)
        if marker == self._last_reported:
            return
        self._last_reported = marker
        if status.state is VoiceInputState.RECORDING:
            self._voice_trace = LifecycleTrace.create(VOICE_SESSION_ID)
            token = CURRENT_LIFECYCLE.set(self._voice_trace)
            try:
                log_lifecycle("listening", reason="voice_capture")
            finally:
                CURRENT_LIFECYCLE.reset(token)
        elif (
            status.state in {VoiceInputState.FAILED, VoiceInputState.DISABLED} and self._voice_trace
        ):
            token = CURRENT_LIFECYCLE.set(self._voice_trace)
            try:
                failed = status.state is VoiceInputState.FAILED
                log_lifecycle(
                    "error" if failed else "interrupted",
                    outcome="failed" if failed else "cancelled",
                    reason="request_failed" if failed else "cancelled",
                )
            finally:
                CURRENT_LIFECYCLE.reset(token)
                self._voice_trace = None
        await self._events.publish(
            AgentEventType.VOICE,
            _voice_status_message(status),
            session_id=VOICE_SESSION_ID,
            data={
                "kind": "voice_status",
                "state": status.state.value,
                "language": status.language,
                "error_code": status.last_error_code,
            },
            retain=status.state
            not in {
                VoiceInputState.LISTENING,
                VoiceInputState.RECORDING,
                VoiceInputState.COOLDOWN,
            },
        )

    async def close(self) -> None:
        """Release voice ownership without rewriting the persisted preference."""
        if self._closed:
            return
        self._closed = True
        await self._ide.stop_voice_input()
        self._runtime.disarm_voice_motion()
        self._release_status.set_enabled("voice", False)


async def persist_voice_input_enabled(config_path: str | Path, enabled: bool) -> None:
    """Atomically persist only the validated voice enable switch."""
    await asyncio.to_thread(_persist_voice_input_enabled, config_path, enabled)


def _persist_voice_input_enabled(config_path: str | Path, enabled: bool) -> None:
    config = load_robot_config(config_path)
    payload = config.model_dump(mode="python")
    payload["voice_input"]["enabled"] = enabled
    validated = type(config).model_validate(payload)
    save_robot_config(validated, config_path, overwrite=True)


def _release_state(state: VoiceInputState) -> ReleaseFeatureState:
    mapping = {
        VoiceInputState.DISABLED: ReleaseFeatureState.DISABLED,
        VoiceInputState.STARTING: ReleaseFeatureState.STARTING,
        VoiceInputState.LISTENING: ReleaseFeatureState.LISTENING,
        VoiceInputState.DETECTED: ReleaseFeatureState.DETECTED,
        VoiceInputState.RECORDING: ReleaseFeatureState.RECORDING,
        VoiceInputState.TRANSCRIBING: ReleaseFeatureState.TRANSCRIBING,
        VoiceInputState.DISPATCHING: ReleaseFeatureState.DISPATCHING,
        VoiceInputState.COOLDOWN: ReleaseFeatureState.COOLDOWN,
        VoiceInputState.PAUSED: ReleaseFeatureState.IDLE,
        VoiceInputState.DEGRADED: ReleaseFeatureState.DEGRADED,
        VoiceInputState.FAILED: ReleaseFeatureState.FAILED,
        VoiceInputState.STOPPING: ReleaseFeatureState.STOPPING,
        VoiceInputState.STOPPED: ReleaseFeatureState.STOPPED,
    }
    return mapping[state]


def _voice_status_message(status: VoiceInputStatus) -> str:
    if status.state in {VoiceInputState.DEGRADED, VoiceInputState.FAILED}:
        return (
            "Voice input encountered an error. Manual terminal and web chat remain available; "
            "check microphone/model/transcription status, then re-enable voice input."
        )
    messages = {
        VoiceInputState.DISABLED: "Voice input is disabled.",
        VoiceInputState.STARTING: "Voice input is starting.",
        VoiceInputState.LISTENING: "Voice input is listening for Hey Ninja.",
        VoiceInputState.DETECTED: "Hey Ninja was detected.",
        VoiceInputState.RECORDING: "Voice input is recording a bounded command.",
        VoiceInputState.TRANSCRIBING: "Voice input is transcribing locally.",
        VoiceInputState.DISPATCHING: "Voice input is dispatching the transcript.",
        VoiceInputState.COOLDOWN: "Voice input is cooling down before re-arming.",
        VoiceInputState.PAUSED: "Voice input paused for an explicit microphone operation.",
        VoiceInputState.STOPPING: "Voice input is stopping.",
        VoiceInputState.STOPPED: "Voice input stopped.",
    }
    return messages[status.state]
