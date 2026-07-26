from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ninjarobot_pi5_ide import (
    ActionLedger,
    ActionRequest,
    ActionStatus,
    CapabilityDescriptor,
    CapabilityRegistry,
    ExecutionEngine,
    ResourceHealth,
    ResourceScheduler,
    RetrySafety,
    RiskLevel,
)


class ControlledAdapter:
    def __init__(
        self,
        *,
        idempotent: bool = True,
        timeout: float = 1.0,
        delay: float = 0.0,
    ) -> None:
        self._descriptor = CapabilityDescriptor(
            name="test.execute",
            version="1.0.0",
            description="Controlled execution adapter.",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            risk=RiskLevel.READ_ONLY,
            resources=("shared-test-resource",),
            default_timeout_seconds=timeout,
            idempotent=idempotent,
            cancellable=True,
            confirmation_required=False,
        )
        self.delay = delay
        self.calls = 0
        self.active = 0
        self.maximum_active = 0
        self.entered = asyncio.Event()

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    async def start(self) -> None:
        return None

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        self.entered.set()
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            return {"echo": arguments}
        finally:
            self.active -= 1

    async def health(self) -> ResourceHealth:
        return ResourceHealth.READY

    async def close(self) -> None:
        return None


def request(
    action_id: str,
    *,
    key: str | None = None,
    deadline: datetime | None = None,
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        capability="test.execute",
        arguments={"value": action_id},
        requested_by="test",
        session_id="session-1",
        idempotency_key=key or f"key-{action_id}",
        deadline=deadline,
    )


def engine_for(tmp_path: Path, adapter: ControlledAdapter) -> ExecutionEngine:
    return ExecutionEngine(
        CapabilityRegistry([adapter]),
        ActionLedger(tmp_path / "ledger.sqlite3"),
        scheduler=ResourceScheduler(max_concurrency=2, max_queue_size=2),
    )


def test_success_and_repeated_action_execute_only_once(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = ControlledAdapter()
        engine = engine_for(tmp_path, adapter)
        first = await engine.execute(request("action-1"))
        repeated = await engine.execute(request("action-1"))
        assert first.status is ActionStatus.SUCCEEDED
        assert repeated == first
        assert adapter.calls == 1
        record = await engine.action("action-1")
        assert record is not None and record.result == first
        await engine.close()
        await engine.close()

    asyncio.run(exercise())


def test_concurrent_duplicate_and_resource_race_are_serialized(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = ControlledAdapter(delay=0.02)
        engine = engine_for(tmp_path, adapter)
        duplicate = request("same-action")
        results = await asyncio.gather(
            engine.execute(duplicate),
            engine.execute(duplicate),
            engine.execute(request("other-action")),
        )
        assert all(result.status is ActionStatus.SUCCEEDED for result in results)
        assert adapter.calls == 2
        assert adapter.maximum_active == 1
        await engine.close()

    asyncio.run(exercise())


def test_expired_deadline_and_unknown_capability_never_execute(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = ControlledAdapter()
        engine = engine_for(tmp_path, adapter)
        expired = await engine.execute(
            request("expired", deadline=datetime.now(UTC) - timedelta(seconds=1))
        )
        missing_request = request("missing").model_copy(update={"capability": "missing.capability"})
        missing = await engine.execute(missing_request)
        assert expired.status is ActionStatus.REJECTED
        assert expired.error is not None and expired.error.definitely_not_executed
        assert missing.status is ActionStatus.REJECTED
        assert missing.error is not None and missing.error.code == "CAPABILITY_NOT_FOUND"
        assert adapter.calls == 0
        await engine.close()

    asyncio.run(exercise())


def test_non_idempotent_timeout_records_unknown_outcome(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = ControlledAdapter(idempotent=False, timeout=0.01, delay=0.1)
        engine = engine_for(tmp_path, adapter)
        result = await engine.execute(request("timeout"))
        assert result.status is ActionStatus.FAILED
        assert result.retry_safety is RetrySafety.UNKNOWN
        assert result.error is not None
        assert result.error.code == "ACTION_TIMEOUT_UNKNOWN_OUTCOME"
        assert result.error.definitely_not_executed is False
        await engine.close()

    asyncio.run(exercise())


def test_full_queue_is_rejected_before_second_adapter_execution(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = ControlledAdapter(delay=10)
        engine = ExecutionEngine(
            CapabilityRegistry([adapter]),
            ActionLedger(tmp_path / "full.sqlite3"),
            scheduler=ResourceScheduler(max_concurrency=1, max_queue_size=0),
        )
        first = asyncio.create_task(engine.execute(request("first")))
        await adapter.entered.wait()
        second = await engine.execute(request("second"))
        assert second.status is ActionStatus.REJECTED
        assert second.error is not None
        assert second.error.code == "ACTION_QUEUE_FULL"
        assert second.error.definitely_not_executed is True
        assert adapter.calls == 1
        await engine.cancel("first")
        await first
        await engine.close()

    asyncio.run(exercise())


def test_explicit_cancellation_is_persisted(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = ControlledAdapter(delay=10)
        engine = engine_for(tmp_path, adapter)
        running = asyncio.create_task(engine.execute(request("cancel-me")))
        await adapter.entered.wait()
        cancelled = await engine.cancel("cancel-me")
        returned = await running
        assert cancelled.status is ActionStatus.CANCELLED
        assert returned == cancelled
        record = await engine.action("cancel-me")
        assert record is not None and record.result == cancelled
        await engine.close()

    asyncio.run(exercise())


def test_restart_recovery_distinguishes_accepted_and_running(tmp_path: Path) -> None:
    database = tmp_path / "recovery.sqlite3"
    now = datetime.now(UTC)
    first_ledger = ActionLedger(database)
    first_ledger.reserve(request("accepted"), now)
    first_ledger.reserve(request("running"), now)
    first_ledger.mark_running("running", now)
    first_ledger.close()

    async def exercise() -> None:
        second_ledger = ActionLedger(database)
        engine = ExecutionEngine(
            CapabilityRegistry([ControlledAdapter()]),
            second_ledger,
        )
        await engine.start()
        accepted = await engine.action("accepted")
        running = await engine.action("running")
        assert accepted is not None and accepted.result is not None
        assert accepted.result.retry_safety is RetrySafety.SAFE
        assert accepted.result.error is not None
        assert accepted.result.error.definitely_not_executed is True
        assert running is not None and running.result is not None
        assert running.result.retry_safety is RetrySafety.UNKNOWN
        assert running.result.error is not None
        assert running.result.error.code == "ACTION_OUTCOME_UNKNOWN_AFTER_RESTART"
        await engine.close()

    asyncio.run(exercise())
