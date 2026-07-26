from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ninjarobot_pi5_ide import (
    ActionLedger,
    ActionRequest,
    ActionResult,
    ActionStatus,
    CapabilityDescriptor,
    CapabilityRegistry,
    LifecycleState,
    QueueCapacityError,
    ResourceHealth,
    ResourceScheduler,
    RetrySafety,
    RiskLevel,
)


class StubAdapter:
    def __init__(self, name: str = "distance.read") -> None:
        self._descriptor = CapabilityDescriptor(
            name=name,
            version="1.0.0",
            description="Test adapter.",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            risk=RiskLevel.READ_ONLY,
            resources=("i2c-1",),
            default_timeout_seconds=1.0,
            idempotent=True,
            cancellable=True,
            confirmation_required=False,
        )
        self.started = 0
        self.closed = 0

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    async def start(self) -> None:
        self.started += 1

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return dict(arguments)

    async def health(self) -> ResourceHealth:
        return ResourceHealth.READY

    async def close(self) -> None:
        self.closed += 1


def make_request(
    action_id: str = "action-1",
    idempotency_key: str = "key-1",
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        capability="distance.read",
        arguments={},
        requested_by="test",
        session_id="session-1",
        idempotency_key=idempotency_key,
    )


def test_registry_discovery_lifecycle_and_duplicates() -> None:
    adapter = StubAdapter()
    registry = CapabilityRegistry([adapter])
    assert registry.descriptors() == (adapter.descriptor,)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(StubAdapter())

    async def exercise() -> None:
        await registry.start()
        await registry.start()
        assert registry.state is LifecycleState.RUNNING
        assert registry.get("distance.read") is adapter
        assert await registry.health() == {"distance.read": ResourceHealth.READY}
        await registry.close()
        await registry.close()

    asyncio.run(exercise())
    assert adapter.started == 1
    assert adapter.closed == 1


def test_registry_rolls_back_partial_startup() -> None:
    first = StubAdapter("a.first")
    second = StubAdapter("b.second")

    async def fail() -> None:
        raise RuntimeError("startup failed")

    second.start = fail  # type: ignore[method-assign]
    registry = CapabilityRegistry([second, first])
    with pytest.raises(RuntimeError, match="startup failed"):
        asyncio.run(registry.start())
    assert registry.state is LifecycleState.FAILED
    assert first.closed == 1


def test_sqlite_ledger_round_trip_and_atomic_duplicate(tmp_path: Path) -> None:
    ledger = ActionLedger(tmp_path / "actions.sqlite3")
    now = datetime(2026, 7, 26, tzinfo=UTC)
    request = make_request()
    accepted, created = ledger.reserve(request, now)
    repeated, repeated_created = ledger.reserve(request, now)
    assert created is True
    assert repeated_created is False
    assert repeated == accepted

    running = ledger.mark_running(request.action_id, now)
    assert running.status is ActionStatus.RUNNING
    result = ActionResult(
        action_id=request.action_id,
        status=ActionStatus.SUCCEEDED,
        data={"distance_mm": 123},
        started_at=now,
        finished_at=now,
        retry_safety=RetrySafety.SAFE,
    )
    finished = ledger.finish(result)
    assert finished.result == result
    assert ledger.get(request.action_id) == finished
    assert ledger.list() == (finished,)
    ledger.close()


def test_ledger_rejects_crossed_action_and_idempotency_conflicts(tmp_path: Path) -> None:
    ledger = ActionLedger(tmp_path / "conflicts.sqlite3")
    now = datetime(2026, 7, 26, tzinfo=UTC)
    ledger.reserve(make_request("action-a", "key-a"), now)
    ledger.reserve(make_request("action-b", "key-b"), now)
    with pytest.raises(ValueError, match="belong to different actions"):
        ledger.reserve(make_request("action-a", "key-b"), now)
    ledger.close()


def test_scheduler_serializes_shared_resources_and_bounds_queue() -> None:
    async def exercise() -> None:
        scheduler = ResourceScheduler(max_concurrency=1, max_queue_size=0)
        await scheduler.start()
        entered = asyncio.Event()
        release = asyncio.Event()

        async def blocking() -> str:
            entered.set()
            await release.wait()
            return "first"

        first = asyncio.create_task(scheduler.run(["i2c-1"], blocking))
        await entered.wait()
        with pytest.raises(QueueCapacityError, match="queue is full"):
            await scheduler.run(["i2c-1"], lambda: asyncio.sleep(0))
        release.set()
        assert await first == "first"
        await scheduler.close()
        with pytest.raises(RuntimeError, match="not running"):
            await scheduler.run([], lambda: asyncio.sleep(0))

    asyncio.run(exercise())
