"""Serialized QR-to-Greeting startup coordination for the public release."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from .events import AgentEvent, AgentEventType, EventBroker
from .pairing import PairingError, PairingSessionManager
from .release_foundations import ReleaseFeatureState, ReleaseStatusRegistry

LOGGER = logging.getLogger(__name__)


class OnboardingIDE(Protocol):
    async def show_onboarding_qr(self, url: str) -> dict[str, Any]: ...

    async def show_onboarding_status(self, state: str) -> dict[str, Any]: ...

    async def prepare_onboarding_greeting(self) -> dict[str, Any]: ...

    async def start_liveliness(self) -> dict[str, Any]: ...

    async def restore_idle_face(self) -> object: ...


class OnboardingRuntime(Protocol):
    def complete_startup_liveliness(self) -> None: ...

    def fail_startup_liveliness(self, error: BaseException) -> None: ...

    def disarm_voice_motion(self, *, lease_id: str | None = None) -> None: ...

    async def stop_and_disarm_motion(
        self,
        session_id: str,
        *,
        lease_id: str | None = None,
        requested_by: str = "local-controller",
        include_voice: bool = False,
    ) -> object: ...


class RemoteOnboardingSource(Protocol):
    def status(self) -> dict[str, object]: ...

    def pairing_url(self) -> str: ...


class OnboardingCoordinator:
    """Display the current pairing endpoint and run Greeting at most once."""

    def __init__(
        self,
        *,
        enabled: bool,
        local_origin: str,
        ide: OnboardingIDE,
        runtime: OnboardingRuntime,
        pairing: PairingSessionManager,
        events: EventBroker,
        release_status: ReleaseStatusRegistry,
        remote: RemoteOnboardingSource,
        start_local_fallback: Callable[[], Awaitable[dict[str, Any]]] | None = None,
        activate_remote_access: Callable[[], Awaitable[dict[str, Any]]] | None = None,
        refresh_interval_seconds: float | None = None,
    ) -> None:
        self._enabled = enabled
        self._local_origin = local_origin
        self._ide = ide
        self._runtime = runtime
        self._pairing = pairing
        self._events = events
        self._release_status = release_status
        self._remote = remote
        self._start_local_fallback = start_local_fallback
        self._activate_remote_access = activate_remote_access
        self._refresh_interval = (
            refresh_interval_seconds
            if refresh_interval_seconds is not None
            else max(15.0, pairing.pairing_lifetime_seconds * 0.75)
        )
        if self._refresh_interval <= 0:
            raise ValueError("onboarding refresh interval must be positive")
        self._event_task: asyncio.Task[None] | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._event_queue: asyncio.Queue[AgentEvent] | None = None
        self._presentation_lock = asyncio.Lock()
        self._greeting_lock = asyncio.Lock()
        self._greeting_attempted = False
        self._terminal_failure = False
        self._closed = False
        self._displayed_scope: str | None = None
        self._post_startup_pairing_scope: str | None = None

    async def start(self, *, remote_enabled: bool) -> None:
        """Begin display supervision before remote startup can publish an event."""
        if not self._enabled:
            return
        self._release_status.update("onboarding", ReleaseFeatureState.STARTING)
        self._event_queue = await self._events.subscribe()
        self._event_task = asyncio.create_task(
            self._monitor_remote_events(),
            name="ninjarobot-onboarding-events",
        )
        self._refresh_task = asyncio.create_task(
            self._refresh_loop(),
            name="ninjarobot-onboarding-refresh",
        )
        if remote_enabled:
            try:
                await self._ide.show_onboarding_status("connecting")
            except Exception as exc:
                await self._fail("onboarding_status_failed", exc)
        else:
            await self._show_local_pairing()

    async def remote_start_completed(self) -> None:
        """Resolve initial remote success/failure even if an event raced startup."""
        if not self._enabled or self._terminal_failure or self._greeting_attempted:
            return
        status = self._remote.status()
        if status.get("public_url"):
            if await self._activate_remote():
                await self._show_remote_pairing()
        elif status.get("state") in {"degraded", "failed", "unavailable", "disabled"}:
            if await self._enable_local_fallback():
                await self._show_local_pairing()

    async def controller_connected(self, *, paired: bool, remote: bool = False) -> None:
        """Attempt Greeting once for the first authenticated controller."""
        if not self._enabled or not paired or self._terminal_failure:
            return
        connection_scope = "remote" if remote else "local"
        if self._post_startup_pairing_scope == connection_scope:
            async with self._presentation_lock:
                self._post_startup_pairing_scope = None
                self._displayed_scope = None
                try:
                    await self._ide.restore_idle_face()
                except Exception as exc:
                    await self._fail("pairing_idle_restore_failed", exc)
                    return
            await self._events.publish(
                AgentEventType.ONBOARDING,
                "The additional browser paired; the QR was cleared and Idle restored.",
                data={"kind": "pairing_qr_completed", "scope": connection_scope},
            )
            return
        async with self._greeting_lock:
            if self._greeting_attempted or self._terminal_failure:
                return
            self._greeting_attempted = True
            self._release_status.update("onboarding", ReleaseFeatureState.CONNECTED)
            self._runtime.disarm_voice_motion()
            try:
                await self._ide.prepare_onboarding_greeting()
                await self._ide.start_liveliness()
            except Exception as exc:
                await self._fail("startup_greeting_failed", exc)
                return
            self._runtime.complete_startup_liveliness()
            self._release_status.update("onboarding", ReleaseFeatureState.READY)
            await self._events.publish(
                AgentEventType.ONBOARDING,
                "The first authenticated controller connected; Greeting completed "
                "and Idle is active.",
                data={"kind": "onboarding_complete"},
            )

    async def show_remote_access(self) -> dict[str, object]:
        """Display a fresh non-revoking remote pairing QR after startup."""
        if not self._enabled or self._terminal_failure:
            raise RuntimeError("remote QR display is unavailable")
        status = self._remote.status()
        public_url = status.get("public_url")
        if not isinstance(public_url, str) or not public_url:
            raise RuntimeError("ngrok Remote Access is not ready")
        pairing_url = self._pairing.rotate(invalidate_sessions=False)
        self._post_startup_pairing_scope = "remote"
        self._displayed_scope = None
        await self._show_pairing(pairing_url, scope="remote")
        if self._terminal_failure or self._displayed_scope != "remote":
            raise RuntimeError("ngrok pairing QR could not be displayed")
        return {
            "displayed": True,
            "scope": "remote",
            "public_url": public_url,
            "existing_browser_sessions_revoked": False,
            "next_step": "Scan the QR code; the display returns to Idle after pairing.",
        }

    async def close(self) -> None:
        self._closed = True
        tasks = [task for task in (self._event_task, self._refresh_task) if task is not None]
        self._event_task = None
        self._refresh_task = None
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        queue = self._event_queue
        self._event_queue = None
        if queue is not None:
            await self._events.unsubscribe(queue)

    async def _monitor_remote_events(self) -> None:
        queue = self._event_queue
        if queue is None:
            return
        while True:
            event = await queue.get()
            if event.event_type is not AgentEventType.REMOTE_ACCESS:
                continue
            kind = event.data.get("kind")
            if kind == "remote_ready":
                if await self._activate_remote():
                    if self._greeting_attempted:
                        self._post_startup_pairing_scope = "remote"
                    await self._show_remote_pairing()
            elif kind == "remote_error":
                if await self._enable_local_fallback():
                    if self._greeting_attempted:
                        self._post_startup_pairing_scope = "local"
                    await self._show_local_pairing()

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self._refresh_interval)
            await self._refresh_pairing()

    async def _show_remote_pairing(self) -> None:
        try:
            pairing_url = self._remote.pairing_url()
        except (PairingError, RuntimeError):
            return
        await self._show_pairing(pairing_url, scope="remote")

    async def _show_local_pairing(self) -> None:
        if (
            self._closed
            or self._terminal_failure
            or (self._greeting_attempted and self._post_startup_pairing_scope != "local")
        ):
            return
        try:
            self._pairing.set_local_url(self._local_origin)
            pairing_url = self._pairing.pairing_url()
        except (PairingError, ValueError) as exc:
            await self._fail("local_pairing_failed", exc)
            return
        await self._show_pairing(pairing_url, scope="local")

    async def _refresh_pairing(self) -> None:
        if (
            self._closed
            or self._terminal_failure
            or (self._greeting_attempted and self._post_startup_pairing_scope is None)
            or self._displayed_scope is None
        ):
            return
        try:
            pairing_url = self._pairing.rotate(invalidate_sessions=False)
        except PairingError as exc:
            await self._fail("pairing_refresh_failed", exc)
            return
        await self._show_pairing(pairing_url, scope=self._displayed_scope)

    async def _show_pairing(self, pairing_url: str, *, scope: str) -> None:
        async with self._presentation_lock:
            if (
                self._closed
                or self._terminal_failure
                or (self._greeting_attempted and self._post_startup_pairing_scope is None)
            ):
                return
            try:
                await self._ide.show_onboarding_qr(pairing_url)
            except Exception as exc:
                await self._fail("onboarding_qr_failed", exc)
                return
            self._displayed_scope = scope
            self._release_status.update(
                "onboarding",
                ReleaseFeatureState.PAIRING,
                detail=None,
            )
            await self._events.publish(
                AgentEventType.ONBOARDING,
                "A physical-presence browser pairing QR is ready.",
                data={"kind": "pairing_qr_ready", "scope": scope},
            )

    async def _show_remote_unavailable(self) -> None:
        self._displayed_scope = None
        self._post_startup_pairing_scope = None
        self._release_status.update(
            "onboarding",
            ReleaseFeatureState.DEGRADED,
            detail="remote_access_unavailable",
        )
        try:
            await self._ide.show_onboarding_status("error")
        except Exception as exc:
            await self._fail("onboarding_status_failed", exc)

    async def _enable_local_fallback(self) -> bool:
        if self._start_local_fallback is None:
            return True
        try:
            await self._start_local_fallback()
        except Exception as exc:
            await self._fail("local_fallback_start_failed", exc)
            return False
        return True

    async def _activate_remote(self) -> bool:
        if self._activate_remote_access is None:
            return True
        try:
            await self._activate_remote_access()
        except Exception as exc:
            await self._fail("remote_access_activation_failed", exc)
            return False
        return True

    async def _fail(self, code: str, error: BaseException) -> None:
        if self._terminal_failure:
            return
        self._terminal_failure = True
        self._release_status.update(
            "onboarding",
            ReleaseFeatureState.FAILED,
            detail=code,
        )
        self._runtime.fail_startup_liveliness(error)
        self._runtime.disarm_voice_motion()
        try:
            await self._runtime.stop_and_disarm_motion(
                "onboarding-recovery",
                requested_by="onboarding-recovery",
                include_voice=True,
            )
        except Exception:
            LOGGER.exception("Onboarding recovery could not confirm servo stop.")
        LOGGER.exception("Onboarding failed: %s", code, exc_info=error)
        await self._events.publish(
            AgentEventType.ERROR,
            "Boot onboarding failed; motion remains disarmed and local recovery is required.",
            data={"kind": "onboarding_error", "code": code},
        )
        try:
            await self._ide.show_onboarding_status("error")
        except Exception:
            LOGGER.exception("The display could not show the onboarding Error state.")
