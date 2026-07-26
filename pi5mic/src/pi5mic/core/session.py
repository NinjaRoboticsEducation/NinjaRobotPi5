"""State snapshots for the pi5mic listener."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ListenerState(str, Enum):
    """High-level listener states used by `MicListener`."""

    IDLE = "idle"
    ARMED = "armed"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    DISPATCHING = "dispatching"
    WAITING_FOR_REPLY = "waiting_for_reply"
    COOLDOWN = "cooldown"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ListenerSnapshot:
    """Immutable listener state snapshot."""

    state: ListenerState
    active_request_id: str | None
    cooldown_remaining_seconds: float
    last_error: str | None
