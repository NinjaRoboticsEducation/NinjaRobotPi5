"""Single-owner agent service lifecycle shared by all interfaces."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import TextIO

from ninjarobot_pi5_ide import IDEClient

from .events import AgentEventType, EventBroker
from .persistence import ConversationStore
from .providers import LLMProvider


class ServiceAlreadyRunningError(RuntimeError):
    """Raised when another process already owns the robot service."""


class ServiceOwnership:
    """Advisory file lock with a human-readable owner record."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()
        self._handle: TextIO | None = None

    @property
    def path(self) -> Path:
        return self._path

    def acquire(self) -> None:
        """Acquire the service lock without waiting."""
        if self._handle is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self._path.parent, 0o700)
        handle = self._path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.seek(0)
            owner = handle.read().strip()
            handle.close()
            detail = f": {owner}" if owner else ""
            raise ServiceAlreadyRunningError(f"agent service is already running{detail}") from exc
        handle.seek(0)
        handle.truncate()
        json.dump(
            {
                "pid": os.getpid(),
                "started_at": datetime.now(UTC).isoformat(),
            },
            handle,
            sort_keys=True,
        )
        handle.flush()
        os.fsync(handle.fileno())
        os.chmod(self._path, 0o600)
        self._handle = handle

    def release(self) -> None:
        """Release safely and leave no stale owner record."""
        handle = self._handle
        if handle is None:
            return
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
        self._handle = None
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass


class AgentService:
    """Own the provider, IDE boundary, persistence, and event stream once."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        ide: IDEClient,
        store: ConversationStore,
        ownership: ServiceOwnership,
        events: EventBroker | None = None,
    ) -> None:
        self.provider = provider
        self.ide = ide
        self.store = store
        self.ownership = ownership
        self.events = events or EventBroker()
        self._started = False
        self._close_lock = asyncio.Lock()

    @property
    def started(self) -> bool:
        return self._started

    async def start(self) -> None:
        """Start dependencies transactionally and publish readiness."""
        if self._started:
            return
        self.ownership.acquire()
        store_started = False
        ide_started = False
        try:
            await self.store.start()
            store_started = True
            pruned = await self.store.prune()
            await self.ide.start()
            ide_started = True
            provider_health = await self.provider.health()
            self._started = True
            await self.events.publish(
                AgentEventType.SERVICE,
                "Agent service started.",
                data={
                    "provider": provider_health.provider,
                    "provider_status": provider_health.status.value,
                    "pruned_messages": pruned,
                },
            )
        except Exception:
            if ide_started:
                await self.ide.close()
            if store_started:
                await self.store.close()
            self.ownership.release()
            raise

    async def close(self) -> None:
        """Close every owned resource once, even after partial failures."""
        async with self._close_lock:
            if not self._started and not self.ownership.path.exists():
                return
            errors: list[str] = []
            for name, close in (
                ("provider", self.provider.close),
                ("ide", self.ide.close),
                ("store", self.store.close),
            ):
                try:
                    await close()
                except Exception as exc:  # pragma: no cover - defensive aggregation
                    errors.append(f"{name}: {type(exc).__name__}: {exc}")
            self._started = False
            self.ownership.release()
            await self.events.publish(
                AgentEventType.SERVICE,
                "Agent service stopped.",
                data={"cleanup_errors": errors},
            )

    async def __aenter__(self) -> AgentService:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
