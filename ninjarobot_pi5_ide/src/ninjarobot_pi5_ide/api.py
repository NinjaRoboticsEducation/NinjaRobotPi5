"""Provider-neutral client protocol for the deterministic IDE layer."""

from __future__ import annotations

from typing import Protocol

from .models import ActionRequest, ActionResult, CapabilityDescriptor, HealthReport


class IDEClient(Protocol):
    """Only control-plane interface exposed to the agent package."""

    async def capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Return currently available capability descriptors."""

    async def execute(self, request: ActionRequest) -> ActionResult:
        """Execute one already-validated action request."""

    async def health(self) -> HealthReport:
        """Return a non-moving health snapshot."""

    async def close(self) -> None:
        """Release client-owned resources safely and idempotently."""
