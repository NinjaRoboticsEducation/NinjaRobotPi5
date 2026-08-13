"""Nonce-confirmed, narrowly privileged Raspberry Pi shutdown coordination."""

from __future__ import annotations

import asyncio
import logging
import secrets
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .events import AgentEventType, EventBroker
from .release_foundations import ReleaseFeatureState, ReleaseStatusRegistry

NONCE_LIFETIME_SECONDS = 30.0
LOGGER = logging.getLogger(__name__)


class ShutdownRuntime(Protocol):
    async def disable_voice_input(self) -> dict[str, object]: ...


class ShutdownController(Protocol):
    async def emergency_stop(self, lease_id: str) -> dict[str, object]: ...


class PoweroffCoordinator:
    """Consume a short-lived lease nonce, stop hardware, then request teardown."""

    def __init__(
        self,
        *,
        enabled: bool,
        helper_path: str | Path,
        runtime: ShutdownRuntime,
        controller: ShutdownController,
        events: EventBroker,
        release_status: ReleaseStatusRegistry,
        request_service_stop: Callable[[], None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._enabled = enabled
        self._helper_path = Path(helper_path)
        self._runtime = runtime
        self._controller = controller
        self._events = events
        self._release_status = release_status
        self._request_service_stop = request_service_stop
        self._clock = clock
        self._nonces: dict[str, tuple[str, float]] = {}
        self._requested = False
        self._lock = asyncio.Lock()

    @property
    def requested(self) -> bool:
        return self._requested

    async def issue_nonce(self, lease_id: str) -> dict[str, object]:
        """Issue one nonce only to an already validated active controller lease."""
        if not self._enabled:
            raise PermissionError("web power-off is disabled")
        nonce = secrets.token_urlsafe(32)
        async with self._lock:
            self._prune()
            self._nonces = {lease_id: (nonce, self._clock() + NONCE_LIFETIME_SECONDS)}
        return {
            "nonce": nonce,
            "expires_in_seconds": int(NONCE_LIFETIME_SECONDS),
        }

    async def confirm(self, lease_id: str, nonce: str) -> dict[str, object]:
        """Consume the nonce before cleanup so replay cannot re-enter shutdown."""
        if not self._enabled:
            raise PermissionError("web power-off is disabled")
        if not nonce or len(nonce) > 128:
            raise PermissionError("power-off confirmation nonce is invalid")
        async with self._lock:
            self._prune()
            pending = self._nonces.pop(lease_id, None)
            if (
                pending is None
                or self._clock() >= pending[1]
                or not secrets.compare_digest(pending[0], nonce)
            ):
                raise PermissionError("power-off confirmation nonce is invalid or expired")
            if self._requested:
                raise PermissionError("power-off is already in progress")
            self._requested = True
        self._release_status.update(
            "shutdown",
            ReleaseFeatureState.SHUTTING_DOWN,
            detail=None,
        )
        await self._events.publish(
            AgentEventType.SHUTDOWN,
            "Orderly power-off was confirmed; robot hardware is stopping.",
            data={"kind": "poweroff_confirmed"},
        )
        cleanup_failures: list[str] = []
        try:
            await self._controller.emergency_stop(lease_id)
        except Exception:
            LOGGER.exception("Robot emergency stop failed during orderly power-off.")
            cleanup_failures.append("hardware_stop_failed")
        try:
            await self._runtime.disable_voice_input()
        except Exception:
            LOGGER.exception("Voice input cleanup failed during orderly power-off.")
            cleanup_failures.append("voice_stop_failed")
        if cleanup_failures:
            await self._events.publish(
                AgentEventType.ERROR,
                "One or more modules could not stop cleanly; system power-off will continue.",
                data={"kind": "poweroff_cleanup_degraded", "failures": cleanup_failures},
            )
        asyncio.create_task(self._stop_after_response(), name="poweroff-service-stop")
        return {
            "shutdown_accepted": True,
            "cleanup_degraded": bool(cleanup_failures),
        }

    async def invoke_helper(self) -> None:
        """Run only after web, tunnel, SQLite, IDE, and agent cleanup completed."""
        if not self._requested:
            return
        helper = self._helper_path
        if not helper.is_absolute() or helper != Path("/usr/libexec/ninjarobot-poweroff"):
            raise RuntimeError("power-off helper path is not approved")
        if not helper.is_file() or helper.is_symlink():
            raise RuntimeError(
                "power-off helper is unavailable; run `sudo systemctl poweroff` locally"
            )
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                ["/usr/bin/sudo", "-n", str(helper)],
                check=False,
                capture_output=True,
                text=True,
                timeout=15.0,
            )
        except Exception as exc:
            raise RuntimeError(
                "power-off helper failed; run `sudo systemctl poweroff` locally"
            ) from exc
        if completed.returncode != 0:
            raise RuntimeError("power-off helper was denied; run `sudo systemctl poweroff` locally")

    async def _stop_after_response(self) -> None:
        await asyncio.sleep(0.25)
        self._request_service_stop()

    def _prune(self) -> None:
        now = self._clock()
        self._nonces = {lease: record for lease, record in self._nonces.items() if record[1] > now}
