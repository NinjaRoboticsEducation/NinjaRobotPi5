"""Exclusive browser lease and fixed, policy-checked robot controls."""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .agent_loop import AgentReply, TextDeltaHandler
from .runtime import AgentRuntime
from .tools import CancellationToken


class ControllerLockedError(RuntimeError):
    """Raised when another browser currently owns the controller lease."""


class InvalidControllerLeaseError(PermissionError):
    """Raised when a request does not carry the active controller lease."""


@dataclass(frozen=True, slots=True)
class ControllerLease:
    """Public lease material returned only to its owning browser."""

    lease_id: str
    reconnect_token: str
    heartbeat_seconds: float


@dataclass(slots=True)
class _ActiveLease:
    lease_id: str
    reconnect_token: str
    connected: bool
    expires_at: float


LeaseRevokedHandler = Callable[[str, str], Awaitable[None]]


class ControllerLeaseManager:
    """Grant one controller lease and revoke it on missed heartbeats."""

    def __init__(
        self,
        *,
        on_revoke: LeaseRevokedHandler,
        heartbeat_seconds: float = 5.0,
        heartbeat_timeout_seconds: float = 15.0,
        reconnect_grace_seconds: float = 10.0,
    ) -> None:
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be positive")
        if heartbeat_timeout_seconds <= heartbeat_seconds:
            raise ValueError("heartbeat timeout must exceed the heartbeat interval")
        if reconnect_grace_seconds <= 0:
            raise ValueError("reconnect grace must be positive")
        self._on_revoke = on_revoke
        self._heartbeat_seconds = heartbeat_seconds
        self._heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._reconnect_grace_seconds = reconnect_grace_seconds
        self._active: _ActiveLease | None = None
        self._lock = asyncio.Lock()
        self._watchdog: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._watchdog is None:
            self._watchdog = asyncio.create_task(
                self._watch(),
                name="browser-controller-lease-watchdog",
            )

    async def acquire(self, reconnect_token: str | None = None) -> ControllerLease:
        now = time.monotonic()
        expired: _ActiveLease | None = None
        async with self._lock:
            active = self._active
            if active is not None and now >= active.expires_at:
                expired = active
                self._active = None
                active = None
            if active is not None:
                if (
                    not active.connected
                    and reconnect_token is not None
                    and secrets.compare_digest(reconnect_token, active.reconnect_token)
                ):
                    active.connected = True
                    active.expires_at = now + self._heartbeat_timeout_seconds
                    lease = self._public(active)
                else:
                    raise ControllerLockedError("another browser currently controls NinjaRobot")
            else:
                active = _ActiveLease(
                    lease_id=f"lease-{secrets.token_hex(16)}",
                    reconnect_token=secrets.token_urlsafe(32),
                    connected=True,
                    expires_at=now + self._heartbeat_timeout_seconds,
                )
                self._active = active
                lease = self._public(active)
        if expired is not None:
            await self._on_revoke(expired.lease_id, "heartbeat_timeout")
        return lease

    async def heartbeat(self, lease_id: str) -> None:
        async with self._lock:
            active = self._require_locked(lease_id)
            if not active.connected:
                raise InvalidControllerLeaseError("controller is disconnected")
            active.expires_at = time.monotonic() + self._heartbeat_timeout_seconds

    async def validate(self, lease_id: str) -> None:
        async with self._lock:
            active = self._require_locked(lease_id)
            if not active.connected or time.monotonic() >= active.expires_at:
                raise InvalidControllerLeaseError("controller lease is not active")

    async def disconnect(self, lease_id: str) -> None:
        async with self._lock:
            active = self._active
            if active is None or active.lease_id != lease_id:
                return
            active.connected = False
            active.expires_at = min(
                active.expires_at,
                time.monotonic() + self._reconnect_grace_seconds,
            )

    async def release(self, lease_id: str, *, reason: str = "controller_release") -> None:
        active: _ActiveLease | None = None
        async with self._lock:
            if self._active is not None and self._active.lease_id == lease_id:
                active = self._active
                self._active = None
        if active is not None:
            await self._on_revoke(active.lease_id, reason)

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            active = self._active
            return {
                "controller_connected": bool(active and active.connected),
                "lease_active": active is not None,
            }

    async def close(self) -> None:
        task = self._watchdog
        self._watchdog = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        active: _ActiveLease | None
        async with self._lock:
            active = self._active
            self._active = None
        if active is not None:
            await self._on_revoke(active.lease_id, "web_server_shutdown")

    async def _watch(self) -> None:
        try:
            while True:
                await asyncio.sleep(min(1.0, self._heartbeat_seconds))
                expired: _ActiveLease | None = None
                async with self._lock:
                    if self._active is not None and time.monotonic() >= self._active.expires_at:
                        expired = self._active
                        self._active = None
                if expired is not None:
                    await self._on_revoke(expired.lease_id, "heartbeat_timeout")
        except asyncio.CancelledError:
            raise

    def _require_locked(self, lease_id: str) -> _ActiveLease:
        active = self._active
        if active is None or not secrets.compare_digest(active.lease_id, lease_id):
            raise InvalidControllerLeaseError("request has no active controller lease")
        return active

    def _public(self, active: _ActiveLease) -> ControllerLease:
        return ControllerLease(
            lease_id=active.lease_id,
            reconnect_token=active.reconnect_token,
            heartbeat_seconds=self._heartbeat_seconds,
        )


class WebRobotController:
    """Translate a fixed browser protocol into IDE tools and agent chat."""

    MOVEMENTS = {
        "forward": "move_forward",
        "backward": "move_backward",
        "left": "turn_left",
        "right": "turn_right",
    }
    SPECIAL_BEHAVIORS = {"greeting", "celebrate"}

    def __init__(self, runtime: AgentRuntime) -> None:
        self._runtime = runtime
        self._movement: (
            tuple[
                str,
                CancellationToken,
                asyncio.Task[Any],
            ]
            | None
        ) = None
        self._movement_lock = asyncio.Lock()
        self._motion_command_lock = asyncio.Lock()
        self._microphone: (
            tuple[
                str,
                CancellationToken,
                asyncio.Task[Any],
            ]
            | None
        ) = None
        self._microphone_lock = asyncio.Lock()

    def control_session(self, lease_id: str) -> str:
        return f"web-control-{lease_id.removeprefix('lease-')}"

    def chat_session(self, lease_id: str) -> str:
        return f"web-chat-{lease_id.removeprefix('lease-')}"

    def activate(self, lease_id: str) -> None:
        self._runtime.arm_motion(
            self.control_session(lease_id),
            confirmed=True,
            lease_id=lease_id,
        )

    async def start_movement(self, lease_id: str, direction: str) -> dict[str, Any]:
        try:
            behavior = self.MOVEMENTS[direction]
        except KeyError as exc:
            raise ValueError(f"unknown movement direction: {direction}") from exc
        async with self._motion_command_lock:
            await self._stop_motion_unlocked(lease_id)
            token = CancellationToken()
            task = asyncio.create_task(
                self._runtime.execute_tool(
                    tool_name="robot.behavior.run",
                    arguments={"name": behavior},
                    session_id=self.control_session(lease_id),
                    lease_id=lease_id,
                    requested_by="web-controller",
                    cancellation=token,
                ),
                name=f"web-movement-{direction}",
            )
            async with self._movement_lock:
                self._movement = (lease_id, token, task)
            task.add_done_callback(self._consume_background_result)
        return {"started": True, "direction": direction}

    async def stop_motion(self, lease_id: str) -> dict[str, Any]:
        async with self._motion_command_lock:
            return await self._stop_motion_unlocked(lease_id)

    async def _stop_motion_unlocked(self, lease_id: str) -> dict[str, Any]:
        pending: tuple[str, CancellationToken, asyncio.Task[Any]] | None
        async with self._movement_lock:
            pending = self._movement
            self._movement = None
        if pending is not None:
            _owner, token, task = pending
            token.cancel()
            await asyncio.gather(task, return_exceptions=True)
        result = await self._runtime.execute_tool(
            tool_name="robot.servo.stop",
            arguments={},
            session_id=self.control_session(lease_id),
            lease_id=lease_id,
            requested_by="web-controller",
        )
        return result.model_dump(mode="json")

    async def run_behavior(self, lease_id: str, name: str) -> dict[str, Any]:
        if name not in self.SPECIAL_BEHAVIORS:
            raise ValueError(f"unsupported web behavior: {name}")
        await self.stop_motion(lease_id)
        result = await self._runtime.execute_tool(
            tool_name="robot.behavior.run",
            arguments={"name": name},
            session_id=self.control_session(lease_id),
            lease_id=lease_id,
            requested_by="web-controller",
        )
        return result.model_dump(mode="json")

    async def emergency_stop(self, lease_id: str) -> dict[str, Any]:
        async with self._motion_command_lock:
            await self._cancel_movement()
            result = await self._runtime.execute_tool(
                tool_name="robot.behavior.stop",
                arguments={},
                session_id=self.control_session(lease_id),
                lease_id=lease_id,
                requested_by="web-controller",
            )
        self._runtime.disarm_motion(self.control_session(lease_id))
        self._runtime.disarm_motion(self.chat_session(lease_id))
        return result.model_dump(mode="json")

    async def resume(self, lease_id: str) -> dict[str, Any]:
        result = await self._runtime.execute_tool(
            tool_name="robot.system.resume",
            arguments={},
            session_id=self.control_session(lease_id),
            lease_id=lease_id,
            confirmed=True,
            requested_by="web-controller",
        )
        self.activate(lease_id)
        return result.model_dump(mode="json")

    async def camera_preview(self, lease_id: str) -> dict[str, Any]:
        result = await self._runtime.execute_tool(
            tool_name="robot.camera.preview",
            arguments={},
            session_id=self.control_session(lease_id),
            lease_id=lease_id,
            confirmed=True,
            requested_by="web-controller",
        )
        if result.data is None:
            raise RuntimeError(result.error or "camera preview failed")
        return result.data

    async def transcribe(
        self,
        lease_id: str,
        *,
        duration_seconds: float,
        language: str,
    ) -> dict[str, Any]:
        token = CancellationToken()
        task = asyncio.create_task(
            self._runtime.execute_tool(
                tool_name="robot.microphone.transcribe",
                arguments={
                    "duration_seconds": duration_seconds,
                    "language": language,
                },
                session_id=self.control_session(lease_id),
                lease_id=lease_id,
                confirmed=True,
                requested_by="web-controller",
                cancellation=token,
            ),
            name="web-usb-microphone",
        )
        async with self._microphone_lock:
            if self._microphone is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise RuntimeError("USB microphone recording is already active")
            self._microphone = (lease_id, token, task)
        try:
            result = await task
            if result.status.value == "cancelled":
                return {
                    "cancelled": True,
                    "transcript": "",
                    "language": language,
                    "duration_seconds": duration_seconds,
                    "audio_retained": False,
                }
            if result.data is None:
                raise RuntimeError(result.error or "microphone transcription failed")
            return result.data
        finally:
            async with self._microphone_lock:
                if self._microphone is not None and self._microphone[2] is task:
                    self._microphone = None

    async def stop_transcription(self, lease_id: str) -> dict[str, Any]:
        async with self._microphone_lock:
            pending = self._microphone
        if pending is None:
            return {"stopped": False, "reason": "no active USB microphone recording"}
        owner, token, task = pending
        if owner != lease_id:
            raise InvalidControllerLeaseError("USB microphone belongs to another lease")
        token.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return {"stopped": True}

    async def chat(
        self,
        lease_id: str,
        text: str,
        *,
        on_text_delta: TextDeltaHandler | None = None,
    ) -> AgentReply:
        return await self._runtime.chat(
            session_id=self.chat_session(lease_id),
            text=text,
            lease_id=lease_id,
            on_text_delta=on_text_delta,
        )

    def arm_chat_motion(self, lease_id: str, *, confirmed: bool) -> None:
        self._runtime.arm_motion(
            self.chat_session(lease_id),
            confirmed=confirmed,
            lease_id=lease_id,
        )

    def disarm_chat_motion(self, lease_id: str) -> None:
        self._runtime.disarm_motion(self.chat_session(lease_id))

    async def lease_revoked(self, lease_id: str, reason: str) -> None:
        try:
            async with self._motion_command_lock:
                await self._cancel_movement()
                await self._runtime.execute_tool(
                    tool_name="robot.servo.stop",
                    arguments={},
                    session_id=self.control_session(lease_id),
                    lease_id=lease_id,
                    requested_by=f"web-lease-{reason}",
                )
        finally:
            try:
                await self.stop_transcription(lease_id)
            finally:
                self._runtime.disarm_motion(self.control_session(lease_id))
                self._runtime.disarm_motion(self.chat_session(lease_id))

    async def _cancel_movement(self) -> None:
        async with self._movement_lock:
            pending = self._movement
            self._movement = None
        if pending is not None:
            _owner, token, task = pending
            token.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @staticmethod
    def _consume_background_result(task: asyncio.Task[Any]) -> None:
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            return
