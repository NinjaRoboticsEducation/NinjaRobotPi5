"""Provider-neutral model protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from .models import ModelRequest, ModelTurn, ProviderCapabilities, ProviderHealth


class LLMProvider(Protocol):
    """Common boundary implemented by all future model providers."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Describe provider features without making a network request."""

    async def generate(self, request: ModelRequest) -> ModelTurn:
        """Generate one bounded, normalized model turn."""

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelTurn]:
        """Stream normalized model events when supported."""

    async def health(self) -> ProviderHealth:
        """Return provider readiness without exposing secrets."""

    async def close(self) -> None:
        """Release provider resources idempotently."""
