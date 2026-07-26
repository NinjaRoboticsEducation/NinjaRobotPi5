"""Bounded asynchronous scheduling with deterministic resource ownership."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar

from .models import LifecycleState

ResultT = TypeVar("ResultT")


class QueueCapacityError(RuntimeError):
    """Raised when an action cannot enter the bounded scheduler."""


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
        if self._slots.locked():
            raise QueueCapacityError("action queue is full")
        await self._slots.acquire()
        try:
            async with self._workers:
                locks = [
                    self._resource_locks.setdefault(name, asyncio.Lock())
                    for name in sorted(set(resources))
                ]
                for lock in locks:
                    await lock.acquire()
                try:
                    return await operation()
                finally:
                    for lock in reversed(locks):
                        lock.release()
        finally:
            self._slots.release()

    async def close(self) -> None:
        """Prevent new work; already running calls are allowed to finish."""
        if self._state is LifecycleState.CLOSED:
            return
        self._state = LifecycleState.CLOSED
