"""Bounded asynchronous scheduling with deterministic resource ownership."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar

from .models import LifecycleState

ResultT = TypeVar("ResultT")


class QueueCapacityError(RuntimeError):
    """Raised when an action cannot enter the bounded scheduler."""


class StopInProgressError(RuntimeError):
    """Raised when ordinary work would compete with an emergency stop."""


class ResourceScheduler:
    """Limit queued work and serialize conflicting resource users."""

    def __init__(self, *, max_concurrency: int = 1, max_queue_size: int = 16) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if max_queue_size < 0:
            raise ValueError("max_queue_size must not be negative")
        self._max_concurrency = max_concurrency
        self._capacity = max_concurrency + max_queue_size
        self._slots = asyncio.Semaphore(self._capacity)
        self._workers = asyncio.Semaphore(max_concurrency)
        self._resource_locks: dict[str, asyncio.Lock] = {}
        self._state = LifecycleState.CREATED
        self._operations: dict[asyncio.Task[object], frozenset[str]] = {}
        self._interrupts: dict[asyncio.Task[object], frozenset[str]] = {}

    @property
    def state(self) -> LifecycleState:
        """Return the scheduler lifecycle state."""
        return self._state

    async def start(self) -> None:
        """Start the scheduler without creating background tasks."""
        if self._state is LifecycleState.RUNNING:
            return
        if self._state is not LifecycleState.CREATED:
            raise RuntimeError(f"scheduler cannot start from state {self._state}")
        self._state = LifecycleState.RUNNING

    async def run(
        self,
        resources: Iterable[str],
        operation: Callable[[], Awaitable[ResultT]],
    ) -> ResultT:
        """Run work after reserving bounded capacity and sorted resource locks."""
        if self._state is not LifecycleState.RUNNING:
            raise RuntimeError("scheduler is not running")
        resource_set = frozenset(resources)
        if any(resource_set & held for held in self._interrupts.values()):
            raise StopInProgressError("conflicting resources are being stopped")
        if self._slots.locked():
            raise QueueCapacityError("action queue is full")
        await self._slots.acquire()
        task = asyncio.current_task()
        assert task is not None
        self._operations[task] = resource_set
        try:
            async with self._workers:
                locks = [
                    self._resource_locks.setdefault(name, asyncio.Lock())
                    for name in sorted(resource_set)
                ]
                acquired: list[asyncio.Lock] = []
                try:
                    for lock in locks:
                        await lock.acquire()
                        acquired.append(lock)
                    return await operation()
                finally:
                    for lock in reversed(acquired):
                        lock.release()
        finally:
            self._operations.pop(task, None)
            self._slots.release()

    async def interrupt(
        self,
        resources: Iterable[str],
        operation: Callable[[], Awaitable[ResultT]],
    ) -> ResultT:
        """Dispatch a trusted stop without waiting for ordinary slots or locks.

        Device stop implementations must support concurrent cleanup. Cancellation
        is requested before dispatch, but a stuck ordinary action cannot delay the
        stop. Conflicting new actions are rejected until every stop has returned.
        """
        if self._state is not LifecycleState.RUNNING:
            raise RuntimeError("scheduler is not running")
        task = asyncio.current_task()
        assert task is not None
        resource_set = frozenset(resources)
        self._interrupts[task] = resource_set
        try:
            for owner, held in tuple(self._operations.items()):
                if resource_set & held and not owner.cancelling():
                    owner.cancel()
            return await operation()
        finally:
            self._interrupts.pop(task, None)

    async def close(self) -> None:
        """Prevent new work; already running calls are allowed to finish."""
        if self._state is LifecycleState.CLOSED:
            return
        self._state = LifecycleState.CLOSED
