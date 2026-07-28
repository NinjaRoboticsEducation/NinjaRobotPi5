"""Deterministic fake model provider for Phase 1 and later scenario tests."""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime

from .models import (
    ModelRequest,
    ModelStreamEvent,
    ModelTurn,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthStatus,
    StreamEventType,
)


class FakeProvider:
    """Return scripted model turns without network or model access."""

    def __init__(
        self,
        turns: Iterable[ModelTurn],
        *,
        provider_name: str = "fake",
    ) -> None:
        self._turns = deque(turns)
        self._provider_name = provider_name
        self.requests: list[ModelRequest] = []
        self.closed = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Advertise deterministic Phase 1 fake features."""
        return ProviderCapabilities(
            native_tools=True,
            streaming=False,
            images=False,
            audio=False,
            structured_output=True,
            usage_reporting=True,
            provider_conversation_state=False,
        )

    async def generate(self, request: ModelRequest) -> ModelTurn:
        """Return the next scripted turn and record the request."""
        self._ensure_open()
        self.requests.append(request)
        if not self._turns:
            raise RuntimeError("FakeProvider has no scripted turns remaining")
        turn = self._turns.popleft()
        if turn.request_id != request.request_id:
            raise ValueError("scripted turn request_id does not match the request")
        return turn

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        """Yield the same single scripted turn used by generate."""
        turn = await self.generate(request)
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.DONE,
            turn=turn,
        )

    async def health(self) -> ProviderHealth:
        """Return deterministic fake-provider readiness."""
        self._ensure_open()
        return ProviderHealth(
            provider=self._provider_name,
            status=ProviderHealthStatus.READY,
            checked_at=datetime(2026, 1, 1, tzinfo=UTC),
            detail="Simulated provider; no model or network was accessed.",
        )

    async def close(self) -> None:
        """Mark the provider closed; repeated calls are safe."""
        self.closed = True

    def _ensure_open(self) -> None:
        if self.closed:
            raise RuntimeError("FakeProvider is closed")
