"""Deterministic execution engine for capability adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from .errors import IDEError
from .ledger import ActionLedger
from .models import (
    ActionRecord,
    ActionRequest,
    ActionResult,
    ActionStatus,
    CapabilityDescriptor,
    ErrorDetails,
    HealthReport,
    LifecycleState,
    ResourceHealth,
    RetrySafety,
)
from .registry import CapabilityRegistry
from .scheduler import QueueCapacityError, ResourceScheduler

Clock = Callable[[], datetime]


class ExecutionEngine:
    """Own IDE execution, durable idempotency, resources, and lifecycle."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        ledger: ActionLedger,
        *,
        scheduler: ResourceScheduler | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._registry = registry
        self._ledger = ledger
        self._scheduler = scheduler or ResourceScheduler()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._state = LifecycleState.CREATED
        self._start_lock = asyncio.Lock()
        self._tasks: dict[str, asyncio.Task[ActionResult]] = {}

    @property
    def state(self) -> LifecycleState:
        """Return the engine lifecycle state."""
        return self._state

    async def start(self) -> None:
        """Start once and resolve incomplete records from an earlier process."""
        async with self._start_lock:
            if self._state is LifecycleState.RUNNING:
                return
            if self._state is not LifecycleState.CREATED:
                raise RuntimeError(f"engine cannot start from state {self._state}")
            self._state = LifecycleState.STARTING
            try:
                await self._registry.start()
                await self._scheduler.start()
                self._recover_unfinished_actions()
            except BaseException:
                self._state = LifecycleState.FAILED
                await self._scheduler.close()
                await self._registry.close()
                raise
            self._state = LifecycleState.RUNNING

    async def capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Discover capabilities without opening adapter hardware."""
        if self._state in {LifecycleState.CLOSED, LifecycleState.CLOSING}:
            raise RuntimeError("execution engine is closed")
        return self._registry.descriptors()

    async def execute(self, request: ActionRequest) -> ActionResult:
        """Execute once or return the durable outcome of an earlier request."""
        await self._ensure_running()
        now = self._now()
        record, created = self._ledger.reserve(request, now)
        if not created:
            self._validate_repeated_request(request, record)
            if record.result is not None:
                return record.result
            existing_task = self._tasks.get(record.request.action_id)
            if existing_task is not None:
                return await asyncio.shield(existing_task)
            return self._failed_result(
                record.request,
                code="ACTION_STATE_UNAVAILABLE",
                message="The action exists but its live execution state is unavailable.",
                technical_detail="No in-process task owns a non-terminal ledger record.",
                started_at=record.accepted_at,
                definitely_not_executed=record.status is ActionStatus.ACCEPTED,
                retry_safety=(
                    RetrySafety.SAFE
                    if record.status is ActionStatus.ACCEPTED
                    else RetrySafety.UNKNOWN
                ),
            )

        task = asyncio.create_task(self._execute_reserved(request, now))
        self._tasks[request.action_id] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self._tasks.pop(request.action_id, None)

    async def action(self, action_id: str) -> ActionRecord | None:
        """Return the authoritative ledger record."""
        return self._ledger.get(action_id)

    async def cancel(self, action_id: str) -> ActionResult:
        """Cancel queued or running work without inventing a successful outcome."""
        record = self._ledger.get(action_id)
        if record is None:
            raise KeyError(f"unknown action: {action_id}")
        if record.result is not None:
            return record.result
        task = self._tasks.get(action_id)
        if task is None:
            return self._failed_result(
                record.request,
                code="ACTION_STATE_UNAVAILABLE",
                message="The action cannot be cancelled because no live task owns it.",
                technical_detail="The ledger is non-terminal but the task is absent.",
                started_at=record.accepted_at,
                definitely_not_executed=record.status is ActionStatus.ACCEPTED,
                retry_safety=(
                    RetrySafety.SAFE
                    if record.status is ActionStatus.ACCEPTED
                    else RetrySafety.UNKNOWN
                ),
            )
        task.cancel()
        return await task

    async def health(self) -> HealthReport:
        """Return adapter, scheduler, and ledger health without executing actions."""
        await self._ensure_running()
        components = await self._registry.health()
        components["scheduler"] = ResourceHealth.READY
        components["action_ledger"] = ResourceHealth.READY
        overall = (
            ResourceHealth.UNAVAILABLE
            if ResourceHealth.UNAVAILABLE in components.values()
            else (
                ResourceHealth.DEGRADED
                if ResourceHealth.DEGRADED in components.values()
                else ResourceHealth.READY
            )
        )
        return HealthReport(
            status=overall,
            components=components,
            checked_at=self._now(),
            detail="Health checks do not execute capability actions.",
        )

    async def close(self) -> None:
        """Cancel owned actions, close adapters, and close the ledger once."""
        if self._state is LifecycleState.CLOSED:
            return
        self._state = LifecycleState.CLOSING
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        first_error: BaseException | None = None
        try:
            await self._scheduler.close()
        except BaseException as exc:
            first_error = exc
        try:
            await self._registry.close()
        except BaseException as exc:
            first_error = first_error or exc
        self._ledger.close()
        self._state = LifecycleState.CLOSED if first_error is None else LifecycleState.FAILED
        if first_error is not None:
            raise first_error

    async def _ensure_running(self) -> None:
        if self._state is LifecycleState.CREATED:
            await self.start()
        if self._state is not LifecycleState.RUNNING:
            raise RuntimeError(f"execution engine is not running: {self._state}")

    async def _execute_reserved(
        self,
        request: ActionRequest,
        accepted_at: datetime,
    ) -> ActionResult:
        started_at = accepted_at
        try:
            if request.deadline is not None and request.deadline <= self._now():
                result = self._failed_result(
                    request,
                    code="ACTION_DEADLINE_EXPIRED",
                    message="The action deadline expired before execution.",
                    technical_detail=None,
                    started_at=started_at,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    status=ActionStatus.REJECTED,
                )
                self._ledger.finish(result)
                return result
            try:
                adapter = self._registry.get(request.capability)
            except KeyError as exc:
                result = self._failed_result(
                    request,
                    code="CAPABILITY_NOT_FOUND",
                    message=f"Capability is not registered: {request.capability}",
                    technical_detail=str(exc),
                    started_at=started_at,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    status=ActionStatus.REJECTED,
                )
                self._ledger.finish(result)
                return result

            descriptor = adapter.descriptor

            async def invoke() -> ActionResult:
                nonlocal started_at
                started_at = self._now()
                self._ledger.mark_running(request.action_id, started_at)
                timeout = descriptor.default_timeout_seconds
                if request.deadline is not None:
                    remaining = (request.deadline - started_at).total_seconds()
                    if remaining <= 0:
                        raise TimeoutError("deadline expired immediately before adapter execution")
                    timeout = min(timeout, remaining)
                try:
                    data = await asyncio.wait_for(adapter.execute(request.arguments), timeout)
                except TimeoutError as exc:
                    retry = RetrySafety.SAFE if descriptor.idempotent else RetrySafety.UNKNOWN
                    code = (
                        "ACTION_TIMEOUT"
                        if descriptor.idempotent
                        else "ACTION_TIMEOUT_UNKNOWN_OUTCOME"
                    )
                    return self._failed_result(
                        request,
                        code=code,
                        message=f"Capability did not finish within {timeout:.3f} seconds.",
                        technical_detail=str(exc) or "Adapter execution timed out.",
                        started_at=started_at,
                        definitely_not_executed=False,
                        retry_safety=retry,
                    )
                except IDEError as exc:
                    details = exc.details.model_copy(
                        update={
                            "capability": request.capability,
                            "action_id": request.action_id,
                        }
                    )
                    return ActionResult(
                        action_id=request.action_id,
                        status=ActionStatus.FAILED,
                        error=details,
                        started_at=started_at,
                        finished_at=self._now(),
                        retry_safety=details.retry_safety,
                    )
                except Exception as exc:
                    return self._failed_result(
                        request,
                        code="ADAPTER_EXECUTION_FAILED",
                        message="The capability adapter reported an unexpected failure.",
                        technical_detail=f"{type(exc).__name__}: {exc}",
                        started_at=started_at,
                        definitely_not_executed=False,
                        retry_safety=RetrySafety.UNKNOWN,
                    )
                return ActionResult(
                    action_id=request.action_id,
                    status=ActionStatus.SUCCEEDED,
                    data=data,
                    started_at=started_at,
                    finished_at=self._now(),
                    retry_safety=RetrySafety.SAFE,
                )

            try:
                result = await self._scheduler.run(descriptor.resources, invoke)
            except QueueCapacityError as exc:
                result = self._failed_result(
                    request,
                    code="ACTION_QUEUE_FULL",
                    message="The bounded action queue is full.",
                    technical_detail=str(exc),
                    started_at=started_at,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    status=ActionStatus.REJECTED,
                )
            self._ledger.finish(result)
            return result
        except asyncio.CancelledError:
            record = self._ledger.get(request.action_id)
            definitely_not_executed = record is not None and record.status is ActionStatus.ACCEPTED
            result = self._failed_result(
                request,
                code="ACTION_CANCELLED",
                message="The action was cancelled.",
                technical_detail=None,
                started_at=started_at,
                definitely_not_executed=definitely_not_executed,
                retry_safety=(RetrySafety.SAFE if definitely_not_executed else RetrySafety.UNKNOWN),
                status=ActionStatus.CANCELLED,
            )
            self._ledger.finish(result)
            return result

    def _recover_unfinished_actions(self) -> None:
        for record in self._ledger.unfinished():
            definitely_not_executed = record.status is ActionStatus.ACCEPTED
            result = self._failed_result(
                record.request,
                code=(
                    "ACTION_INTERRUPTED_BEFORE_EXECUTION"
                    if definitely_not_executed
                    else "ACTION_OUTCOME_UNKNOWN_AFTER_RESTART"
                ),
                message=(
                    "The queued action was interrupted before execution."
                    if definitely_not_executed
                    else (
                        "The process restarted while the action was running; "
                        "its outcome is unknown."
                    )
                ),
                technical_detail="Recovered a non-terminal record during IDE startup.",
                started_at=record.updated_at,
                definitely_not_executed=definitely_not_executed,
                retry_safety=(RetrySafety.SAFE if definitely_not_executed else RetrySafety.UNKNOWN),
            )
            self._ledger.finish(result)

    def _validate_repeated_request(
        self,
        request: ActionRequest,
        existing: ActionRecord,
    ) -> None:
        original = existing.request
        same_intent = (
            request.capability == original.capability
            and request.arguments == original.arguments
            and request.requested_by == original.requested_by
            and request.session_id == original.session_id
        )
        if not same_intent:
            raise ValueError("action_id or idempotency_key already belongs to a different request")

    def _failed_result(
        self,
        request: ActionRequest,
        *,
        code: str,
        message: str,
        technical_detail: str | None,
        started_at: datetime,
        definitely_not_executed: bool,
        retry_safety: RetrySafety,
        status: ActionStatus = ActionStatus.FAILED,
    ) -> ActionResult:
        return ActionResult(
            action_id=request.action_id,
            status=status,
            error=ErrorDetails(
                code=code,
                message=message,
                technical_detail=technical_detail,
                definitely_not_executed=definitely_not_executed,
                retry_safety=retry_safety,
                capability=request.capability,
                action_id=request.action_id,
            ),
            started_at=started_at,
            finished_at=self._now(),
            retry_safety=retry_safety,
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("execution engine clock must return timezone-aware datetimes")
        return value
