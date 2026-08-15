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

from .deployment import read_full_poweroff_status, validate_poweroff_helper
from .events import AgentEventType, EventBroker
from .release_foundations import ReleaseFeatureState, ReleaseStatusRegistry

NONCE_LIFETIME_SECONDS = 30.0
MAX_HELPER_DIAGNOSTIC_CHARACTERS = 500
LOGGER = logging.getLogger(__name__)
HelperProbe = Callable[[Path], tuple[bool, str | None]]


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
        helper_probe: HelperProbe | None = None,
    ) -> None:
        self._enabled = enabled
        self._helper_path = Path(helper_path)
        self._runtime = runtime
        self._controller = controller
        self._events = events
        self._release_status = release_status
        self._request_service_stop = request_service_stop
        self._clock = clock
        self._helper_probe = helper_probe or _probe_poweroff_helper
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
        await self._require_helper_ready()
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
        await self._require_helper_ready()
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
        await self._require_helper_ready(runtime_error=True)
        helper = self._helper_path
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                ["/usr/bin/sudo", "-n", str(helper)],
                check=False,
                capture_output=True,
                text=True,
                timeout=15.0,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "power-off helper timed out; run `sudo systemctl poweroff` locally"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "power-off helper could not execute; run `sudo systemctl poweroff` locally"
            ) from exc
        if completed.returncode != 0:
            detail = _bounded_helper_diagnostic(completed)
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(
                f"power-off helper exited with status {completed.returncode}{suffix}; "
                "run `sudo systemctl poweroff` locally"
            )
        LOGGER.info("Orderly operating-system power-off request was accepted.")

    async def _stop_after_response(self) -> None:
        await asyncio.sleep(0.25)
        self._request_service_stop()

    def _prune(self) -> None:
        now = self._clock()
        self._nonces = {lease: record for lease, record in self._nonces.items() if record[1] > now}

    async def _require_helper_ready(self, *, runtime_error: bool = False) -> None:
        ready, detail = await asyncio.to_thread(self._helper_probe, self._helper_path)
        if ready:
            return
        message = "web power-off is unavailable: " + (
            detail or "deployment helper is not ready; use Startup Agent deployment to repair it"
        )
        if runtime_error:
            raise RuntimeError(message)
        raise PermissionError(message)


def _probe_poweroff_helper(helper: Path) -> tuple[bool, str | None]:
    """Verify the fixed helper and passwordless narrow sudo rule without mutating state."""
    approved = Path("/usr/libexec/ninjarobot-poweroff")
    if not helper.is_absolute() or helper != approved:
        return (
            False,
            "power-off helper path is not approved; use Startup Agent deployment to repair it",
        )
    if not validate_poweroff_helper(helper):
        return (
            False,
            "power-off helper content, ownership, or mode is invalid; use Startup Agent "
            "deployment to repair it",
        )
    try:
        completed = subprocess.run(
            ["/usr/bin/sudo", "-n", "-l", str(helper)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return (
            False,
            "power-off sudo authorization could not be checked; repair Startup Agent deployment",
        )
    if completed.returncode != 0:
        return (
            False,
            "passwordless power-off sudo authorization is missing; repair Startup Agent deployment",
        )
    poweroff = read_full_poweroff_status()
    if not poweroff.available:
        return (
            False,
            "Raspberry Pi EEPROM status is unavailable; repair Startup Agent deployment",
        )
    if poweroff.update_pending:
        if poweroff.pending_configured:
            return (
                False,
                "the full-power-off EEPROM update is pending; reboot once before using Power Off",
            )
        return (
            False,
            "an incompatible EEPROM update is pending; reboot or cancel it, then repair Startup "
            "Agent deployment",
        )
    if not poweroff.configured:
        return (
            False,
            "Raspberry Pi full power-off is not configured; repair Startup Agent deployment",
        )
    return True, None


def _bounded_helper_diagnostic(completed: subprocess.CompletedProcess[str]) -> str:
    """Return one bounded printable line from a fixed helper's process output."""
    output = completed.stderr.strip() or completed.stdout.strip()
    printable = "".join(character if character.isprintable() else " " for character in output)
    normalized = " ".join(printable.split())
    return normalized[:MAX_HELPER_DIAGNOSTIC_CHARACTERS]
