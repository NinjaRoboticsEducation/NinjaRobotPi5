"""Bounded, typed runtime events shared by CLI and web clients."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from .models import AgentContractModel, Identifier


class AgentEventType(StrEnum):
    """Stable event categories rendered by every user interface."""

    SERVICE = "service"
    CHAT = "chat"
    TOOL = "tool"
    STATUS = "status"
    WARNING = "warning"
    ERROR = "error"
    RECOVERY = "recovery"
    LOG = "log"


class AgentEvent(AgentContractModel):
    """One redaction-safe event emitted by the single-owner service."""

    event_id: Identifier
    event_type: AgentEventType
    created_at: datetime
    message: str
    session_id: Identifier | None = None
    correlation_id: Identifier | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class EventBroker:
    """Fan out bounded events without allowing a slow client to block the robot."""

    def __init__(self, *, history_limit: int = 500, subscriber_limit: int = 100) -> None:
        if history_limit < 1:
            raise ValueError("history_limit must be positive")
        if subscriber_limit < 1:
            raise ValueError("subscriber_limit must be positive")
        self._history: deque[AgentEvent] = deque(maxlen=history_limit)
        self._subscriber_limit = subscriber_limit
        self._subscribers: set[asyncio.Queue[AgentEvent]] = set()
        self._lock = asyncio.Lock()
        self._next_id = 1

    async def publish(
        self,
        event_type: AgentEventType,
        message: str,
        *,
        session_id: str | None = None,
        correlation_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> AgentEvent:
        """Store and broadcast one event, dropping only stale client backlog."""
        async with self._lock:
            event = AgentEvent(
                event_id=f"event-{self._next_id:08d}",
                event_type=event_type,
                created_at=datetime.now(UTC),
                message=message,
                session_id=session_id,
                correlation_id=correlation_id,
                data=data or {},
            )
            self._next_id += 1
            self._history.append(event)
            for queue in self._subscribers:
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(event)
            return event

    async def subscribe(self) -> asyncio.Queue[AgentEvent]:
        """Create one bounded subscriber queue."""
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=self._subscriber_limit)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[AgentEvent]) -> None:
        """Remove a queue idempotently."""
        async with self._lock:
            self._subscribers.discard(queue)

    async def history(self) -> tuple[AgentEvent, ...]:
        """Return a stable snapshot of retained events."""
        async with self._lock:
            return tuple(self._history)
