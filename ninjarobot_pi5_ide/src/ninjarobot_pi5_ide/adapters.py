"""Hardware-neutral adapter boundary used by the deterministic IDE."""

from __future__ import annotations

from typing import Any, Protocol

from .models import CapabilityDescriptor, ResourceHealth


class CapabilityAdapter(Protocol):
    """One independently managed implementation of one IDE capability."""

    @property
    def descriptor(self) -> CapabilityDescriptor:
        """Describe validation, safety, timing, and resource requirements."""

    async def start(self) -> None:
        """Acquire adapter resources; repeated calls must be safe."""

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run one validated capability invocation."""

    async def health(self) -> ResourceHealth:
        """Return a non-moving, side-effect-free health status."""

    async def close(self) -> None:
        """Release resources; repeated calls must be safe."""
