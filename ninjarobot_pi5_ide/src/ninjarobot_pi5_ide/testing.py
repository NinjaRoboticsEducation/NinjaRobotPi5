"""Deterministic Phase 1 fakes for contract and agent tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from .models import (
    ActionRecord,
    ActionRequest,
    ActionResult,
    ActionStatus,
    CapabilityDescriptor,
    HealthReport,
    ResourceHealth,
    RetrySafety,
)


class FakeClock:
    """Small controllable UTC clock."""

    def __init__(self, current: datetime | None = None) -> None:
        initial = current or datetime(2026, 1, 1, tzinfo=UTC)
        if initial.tzinfo is None:
            raise ValueError("FakeClock requires a timezone-aware datetime")
        self._current = initial

    def now(self) -> datetime:
        """Return the current deterministic time."""
        return self._current

    def advance(self, delta: timedelta) -> None:
        """Move time forward; backwards movement is intentionally forbidden."""
        if delta < timedelta(0):
            raise ValueError("FakeClock cannot move backwards")
        self._current += delta


class DeterministicIDGenerator:
    """Generate stable identifiers for repeatable tests."""

    def __init__(self, prefix: str = "test") -> None:
        if not prefix or not prefix.replace("-", "").isalnum():
            raise ValueError("ID prefix must contain only letters, numbers, and hyphens")
        self._prefix = prefix
        self._next = 1

    def new(self) -> str:
        """Return the next deterministic identifier."""
        result = f"{self._prefix}-{self._next:04d}"
        self._next += 1
        return result


class FakeIDEClient:
    """In-memory IDE client that never imports or operates hardware."""

    def __init__(
        self,
        descriptors: Iterable[CapabilityDescriptor] = (),
        *,
        clock: FakeClock | None = None,
    ) -> None:
        self._descriptors = tuple(descriptors)
        self._clock = clock or FakeClock()
        self.requests: list[ActionRequest] = []
        self.results: dict[str, ActionResult] = {}
        self.closed = False

    async def start(self) -> None:
        """Start the hardware-free fake."""
        self._ensure_open()

    async def capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Return configured fake descriptors."""
        self._ensure_open()
        return self._descriptors

    async def execute(self, request: ActionRequest) -> ActionResult:
        """Record a request and return a clearly simulated success."""
        self._ensure_open()
        self.requests.append(request)
        timestamp = self._clock.now()
        result = ActionResult(
            action_id=request.action_id,
            status=ActionStatus.SUCCEEDED,
            data={"simulated": True, "capability": request.capability},
            started_at=timestamp,
            finished_at=timestamp,
            retry_safety=RetrySafety.SAFE,
        )
        self.results[request.action_id] = result
        return result

    async def action(self, action_id: str) -> ActionRecord | None:
        """The lightweight Phase 1 fake does not simulate durable records."""
        self._ensure_open()
        return None

    async def cancel(self, action_id: str) -> ActionResult:
        """Return a terminal result or report that no live fake action exists."""
        self._ensure_open()
        try:
            return self.results[action_id]
        except KeyError as exc:
            raise KeyError(f"unknown action: {action_id}") from exc

    async def health(self) -> HealthReport:
        """Return a non-hardware fake health report."""
        self._ensure_open()
        return HealthReport(
            status=ResourceHealth.READY,
            components={"fake_ide": ResourceHealth.READY},
            checked_at=self._clock.now(),
            detail="Simulated Phase 1 IDE; no hardware was accessed.",
        )

    async def close(self) -> None:
        """Mark the fake closed; repeated calls are safe."""
        self.closed = True

    def _ensure_open(self) -> None:
        if self.closed:
            raise RuntimeError("FakeIDEClient is closed")
