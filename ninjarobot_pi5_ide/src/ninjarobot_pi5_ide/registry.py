"""Deterministic capability registration and adapter lifecycle."""

from __future__ import annotations

from collections.abc import Iterable

from .adapters import CapabilityAdapter
from .models import CapabilityDescriptor, LifecycleState, ResourceHealth


class CapabilityRegistry:
    """Own capability adapters and expose them in a stable order."""

    def __init__(self, adapters: Iterable[CapabilityAdapter] = ()) -> None:
        self._adapters: dict[str, CapabilityAdapter] = {}
        self._state = LifecycleState.CREATED
        for adapter in adapters:
            self.register(adapter)

    @property
    def state(self) -> LifecycleState:
        """Return the current lifecycle state."""
        return self._state

    def register(self, adapter: CapabilityAdapter) -> None:
        """Register one unique capability before startup."""
        if self._state is not LifecycleState.CREATED:
            raise RuntimeError("capabilities can only be registered before startup")
        name = adapter.descriptor.name
        if name in self._adapters:
            raise ValueError(f"capability already registered: {name}")
        self._adapters[name] = adapter

    def descriptors(self) -> tuple[CapabilityDescriptor, ...]:
        """Return descriptors sorted by capability name."""
        return tuple(self._adapters[name].descriptor for name in sorted(self._adapters))

    def get(self, capability: str) -> CapabilityAdapter:
        """Resolve a registered adapter or raise a stable lookup error."""
        try:
            return self._adapters[capability]
        except KeyError as exc:
            raise KeyError(f"unknown capability: {capability}") from exc

    async def start(self) -> None:
        """Start each adapter once and roll back partial startup failures."""
        if self._state is LifecycleState.RUNNING:
            return
        if self._state is not LifecycleState.CREATED:
            raise RuntimeError(f"registry cannot start from state {self._state}")
        self._state = LifecycleState.STARTING
        started: list[CapabilityAdapter] = []
        try:
            for name in sorted(self._adapters):
                adapter = self._adapters[name]
                await adapter.start()
                started.append(adapter)
        except BaseException:
            self._state = LifecycleState.FAILED
            for adapter in reversed(started):
                await adapter.close()
            raise
        self._state = LifecycleState.RUNNING

    async def health(self) -> dict[str, ResourceHealth]:
        """Return health for every registered adapter without running actions."""
        if self._state is not LifecycleState.RUNNING:
            return {name: ResourceHealth.UNAVAILABLE for name in sorted(self._adapters)}
        return {name: await self._adapters[name].health() for name in sorted(self._adapters)}

    async def close(self) -> None:
        """Close every adapter in reverse order and remain idempotent."""
        if self._state is LifecycleState.CLOSED:
            return
        if self._state is LifecycleState.CREATED:
            self._state = LifecycleState.CLOSED
            return
        self._state = LifecycleState.CLOSING
        first_error: BaseException | None = None
        for name in reversed(sorted(self._adapters)):
            try:
                await self._adapters[name].close()
            except BaseException as exc:
                first_error = first_error or exc
        self._state = LifecycleState.CLOSED if first_error is None else LifecycleState.FAILED
        if first_error is not None:
            raise first_error
