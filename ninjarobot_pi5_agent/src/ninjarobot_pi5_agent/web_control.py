"""Exclusive browser lease and fixed, policy-checked robot controls."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .agent_loop import AgentReply, TextDeltaHandler
from .events import AgentEventType
from .models import ToolExecutionResult, ToolExecutionStatus
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
    generation: int = 0


@dataclass(slots=True)
class _ActiveLease:
    lease_id: str
    reconnect_token: str
    connected: bool
    expires_at: float
    generation: int = 0
    quiesced: bool = False


LeaseRevokedHandler = Callable[[str, str], Awaitable[None]]


class ControllerLeaseManager:
    """Serialize handoff while keeping the small state lock free of device I/O."""

    def __init__(
        self,
        *,
        on_revoke: LeaseRevokedHandler,
        heartbeat_seconds: float = 5.0,
        heartbeat_timeout_seconds: float = 15.0,
        reconnect_grace_seconds: float = 10.0,
        on_available: LeaseRevokedHandler | None = None,
        on_fault: LeaseRevokedHandler | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if heartbeat_seconds <= 0 or heartbeat_timeout_seconds <= heartbeat_seconds:
            raise ValueError("invalid heartbeat interval/timeout")
        if reconnect_grace_seconds <= 0:
            raise ValueError("reconnect grace must be positive")
        self._on_revoke = on_revoke
        self._on_fault = on_fault
        self._on_available = on_available
        self._heartbeat_seconds = heartbeat_seconds
        self._heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._reconnect_grace_seconds = reconnect_grace_seconds
        self._clock = clock
        self._active: _ActiveLease | None = None
        self._lock = asyncio.Lock()
        self._transition = asyncio.Lock()
        self._watchdog: asyncio.Task[None] | None = None
        self._generation = 0
        self._closed = False
        self._fault = False
        self._detach: Callable[[], Awaitable[None]] | None = None

    async def start(self) -> None:
        if self._watchdog is None:
            self._watchdog = asyncio.create_task(
                self._watch(), name="browser-controller-lease-watchdog"
            )

    async def acquire(self, reconnect_token: str | None = None) -> ControllerLease:
        async with self._transition:
            if self._closed or self._fault:
                raise ControllerLockedError(
                    "controller cleanup unavailable; local recovery required"
                )
            await self._expire()
            if self._fault:
                raise ControllerLockedError("controller cleanup failed; local recovery required")
            async with self._lock:
                active = self._active
                now = self._clock()
                if active is not None:
                    if (
                        active.connected
                        or reconnect_token is None
                        or not secrets.compare_digest(reconnect_token, active.reconnect_token)
                    ):
                        raise ControllerLockedError("another browser currently controls NinjaRobot")
                    active.connected = True
                    active.quiesced = False
                    active.expires_at = now + self._heartbeat_timeout_seconds
                else:
                    active = _ActiveLease(
                        f"lease-{secrets.token_hex(16)}",
                        secrets.token_urlsafe(32),
                        True,
                        now + self._heartbeat_timeout_seconds,
                    )
                    self._active = active
                self._generation += 1
                active.generation = self._generation
                self._detach = None
                return self._public(active)

    async def attach(self, lease: ControllerLease, detach: Callable[[], Awaitable[None]]) -> None:
        async with self._lock:
            active = self._require_locked(lease.lease_id, lease.generation)
            if not active.connected:
                raise InvalidControllerLeaseError("controller disconnected during setup")
            self._detach = detach

    async def heartbeat(self, lease_id: str, generation: int | None = None) -> None:
        async with self._lock:
            active = self._require_locked(lease_id, generation)
            if not active.connected or self._clock() >= active.expires_at:
                raise InvalidControllerLeaseError("controller is disconnected or expired")
            active.expires_at = self._clock() + self._heartbeat_timeout_seconds

    async def validate(self, lease_id: str, generation: int | None = None) -> None:
        async with self._lock:
            active = self._require_locked(lease_id, generation)
            if not active.connected or self._clock() >= active.expires_at or self._fault:
                raise InvalidControllerLeaseError("controller lease is not active")

    async def disconnect(self, lease_id: str, generation: int | None = None) -> None:
        async with self._transition:
            active = self._active
            if (
                active is None
                or active.lease_id != lease_id
                or (generation is not None and active.generation != generation)
            ):
                return
            async with self._lock:
                active.connected = False
                active.expires_at = min(
                    active.expires_at, self._clock() + self._reconnect_grace_seconds
                )
            await self._quiesce(active, "disconnect")

    async def release(
        self, lease_id: str, *, reason: str = "controller_release", generation: int | None = None
    ) -> None:
        async with self._transition:
            active = self._active
            if (
                active is not None
                and active.lease_id == lease_id
                and (generation is None or generation == active.generation)
            ):
                await self._finish(active, reason)

    async def _quiesce(self, active: _ActiveLease, reason: str) -> None:
        if active.quiesced:
            return
        active.connected = False
        detach, self._detach = self._detach, None
        # Start policy revocation/device stop alongside transport cancellation.
        operations = [self._on_revoke(active.lease_id, reason)]
        if detach is not None:
            operations.append(detach())

        async def bounded(operation: Awaitable[None]) -> None:
            async with asyncio.timeout(5):
                await operation

        results = await asyncio.gather(*(bounded(op) for op in operations), return_exceptions=True)
        active.quiesced = True
        if any(isinstance(result, BaseException) for result in results):
            self._fault = True
            if self._on_fault is not None:
                try:
                    await bounded(self._on_fault(active.lease_id, "cleanup_failed"))
                except Exception:
                    pass  # Remain fail-closed even if hardware fault reporting fails.

    async def _finish(self, active: _ActiveLease, reason: str) -> None:
        await self._quiesce(active, reason)
        if self._fault:
            return  # Fail closed; never advertise safe availability after failed cleanup.
        async with self._lock:
            self._active = None
        if not self._closed and self._on_available is not None:
            try:
                await self._on_available(active.lease_id, reason)
            except Exception:
                # Presentation failure must not stop the lease watchdog/server.
                pass

    async def _expire(self) -> None:
        active = self._active
        if active is not None and self._clock() >= active.expires_at:
            await self._finish(active, "heartbeat_timeout")

    async def current_lease_id(self) -> str | None:
        """Internal lifecycle identity; never expose reconnect credentials in status."""
        async with self._lock:
            return self._active.lease_id if self._active is not None else None

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "controller_connected": bool(self._active and self._active.connected),
                "lease_active": self._active is not None,
                "cleanup_failed": self._fault,
            }

    async def close(self) -> None:
        self._closed = True
        task, self._watchdog = self._watchdog, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        async with self._transition:
            if self._active is not None:
                await self._finish(self._active, "web_server_shutdown")

    async def _watch(self) -> None:
        while True:
            await asyncio.sleep(min(1.0, self._heartbeat_seconds))
            async with self._transition:
                await self._expire()

    def _require_locked(self, lease_id: str, generation: int | None = None) -> _ActiveLease:
        active = self._active
        if (
            active is None
            or not secrets.compare_digest(active.lease_id, lease_id)
            or (generation is not None and generation != active.generation)
        ):
            raise InvalidControllerLeaseError("request has no active controller lease")
        return active

    def _public(self, active: _ActiveLease) -> ControllerLease:
        return ControllerLease(
            active.lease_id, active.reconnect_token, self._heartbeat_seconds, active.generation
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

    async def game_control(
        self,
        lease_id: str,
        operation: str,
        duration_seconds: int = 30,
    ) -> dict[str, Any]:
        return await self._runtime.game_control(
            self.chat_session(lease_id),
            operation,
            duration_seconds,
            lease_id=lease_id,
        )

    async def speech_control(self, operation: str) -> dict[str, Any]:
        return await self._runtime.speech_control(operation)

    async def guided_checks(self, step: int = 0) -> dict[str, Any]:
        """Share the interactive CLI's optional read-only guide."""
        return await self._runtime.guided_checks(step)

    async def task_action(
        self, lease_id: str, operation: str, task_id: str, minutes: int
    ) -> dict[str, Any]:
        return await self._runtime.task_action(
            self.chat_session(lease_id), operation, task_id, minutes
        )

    def __init__(self, runtime: AgentRuntime) -> None:
        self._runtime = runtime
        self._chat_sessions: dict[str, str] = {}
        self._voice_owner: str | None = None
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
        return self._chat_sessions.get(
            lease_id,
            f"web-chat-{lease_id.removeprefix('lease-')}",
        )

    def activate(self, lease_id: str, *, browser_chat_id: str | None = None) -> None:
        if browser_chat_id is not None:
            self._chat_sessions[lease_id] = _browser_chat_session(browser_chat_id)
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
                self._execute_movement(
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

    async def _execute_movement(self, **arguments: Any) -> ToolExecutionResult:
        """Report background admission/device failures instead of hiding them."""
        try:
            result = await self._runtime.execute_tool(**arguments)
        except Exception as exc:
            await self._runtime.events.publish(
                AgentEventType.ERROR,
                f"Movement failed: {type(exc).__name__}: {exc}"[:1000],
                session_id=arguments["session_id"],
                data={"kind": "web_movement_failed"},
            )
            raise
        if result.status not in {ToolExecutionStatus.SUCCEEDED, ToolExecutionStatus.CANCELLED}:
            await self._runtime.events.publish(
                AgentEventType.ERROR,
                f"Movement did not start or complete: {result.error or result.status.value}"[:1000],
                session_id=arguments["session_id"],
                data={"kind": "web_movement_failed"},
            )
        return result

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

    async def list_user_behaviors(self, lease_id: str) -> dict[str, Any]:
        result = await self._runtime.execute_tool(
            tool_name="robot.behavior.list",
            arguments={"source": "user"},
            session_id=self.control_session(lease_id),
            lease_id=lease_id,
            requested_by="web-controller",
        )
        if result.status != ToolExecutionStatus.SUCCEEDED:
            return {"behaviors": []}
        data = result.data if isinstance(result.data, dict) else {}
        raw_list = data.get("behaviors", [])
        behaviors: list[dict[str, Any]] = []
        if isinstance(raw_list, list):
            for item in raw_list:
                if isinstance(item, dict) and "name" in item:
                    behaviors.append(
                        {
                            "name": str(item["name"]),
                            "description": str(item.get("description", "")),
                            "contains_motion": bool(item.get("contains_motion", False)),
                        }
                    )
        return {"behaviors": behaviors}

    async def run_user_behavior(self, lease_id: str, name: str) -> dict[str, Any]:
        if not isinstance(name, str) or not name or any(c in name for c in "/\\.\x00"):
            raise ValueError(f"invalid behavior name: {name}")
        behaviors = await self.list_user_behaviors(lease_id)
        user_names = {item["name"] for item in behaviors.get("behaviors", [])}
        if name not in user_names:
            raise ValueError(f"unknown or deleted user behavior: {name}")
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
        self._runtime.disarm_motion(self.control_session(lease_id))
        self._runtime.disarm_motion(self.chat_session(lease_id))
        self._runtime.disarm_voice_motion(lease_id=lease_id)
        self._runtime.revoke_camera(self.chat_session(lease_id))
        # A previous start/release request may be waiting for device cleanup.
        # Revoke admission first and dispatch stop without joining that queue.
        async with self._movement_lock:
            pending = self._movement
            self._movement = None
        if pending is not None:
            pending[1].cancel()
        result = await self._runtime.execute_tool(
            tool_name="robot.behavior.stop",
            arguments={},
            session_id=self.control_session(lease_id),
            lease_id=lease_id,
            requested_by="web-controller",
        )
        return result.model_dump(mode="json")

    async def resume(self, lease_id: str) -> dict[str, Any]:
        self._runtime.disarm_motion(self.chat_session(lease_id))
        self._runtime.disarm_voice_motion(lease_id=lease_id)
        result = await self._runtime.resume_system(
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

    async def enable_voice_input(self, lease_id: str | None = None) -> dict[str, object]:
        """Enable the global listener from the authenticated active controller."""
        if not self._runtime.voice_input_status().get("enabled"):
            self._voice_owner = lease_id
        return await self._runtime.enable_voice_input(lease_id=lease_id)

    async def disable_voice_input(self) -> dict[str, object]:
        """Disable the listener and revoke its motion authorization."""
        return await self._runtime.disable_voice_input()

    def voice_input_status(self) -> dict[str, object]:
        """Return privacy-safe listener state."""
        return self._runtime.voice_input_status()

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
            include_voice=True,
        )

    def disarm_chat_motion(self, lease_id: str) -> None:
        self._runtime.disarm_motion(self.chat_session(lease_id))
        self._runtime.disarm_voice_motion(lease_id=lease_id)

    def grant_chat_camera(
        self,
        lease_id: str,
        *,
        confirmed: bool,
    ) -> dict[str, bool | int | None]:
        """Grant one fresh temporary AI photo to the active browser chat."""
        return self._runtime.grant_camera(
            self.chat_session(lease_id),
            confirmed=confirmed,
            lease_id=lease_id,
        )

    def revoke_chat_camera(self, lease_id: str) -> None:
        """Revoke the browser chat's pending camera grant."""
        self._runtime.revoke_camera(self.chat_session(lease_id))

    def revoke_permissions(self, lease_id: str) -> None:
        """Deny policy grants before any display/device cleanup awaits."""
        self._runtime.disarm_motion(self.control_session(lease_id))
        self._runtime.disarm_motion(self.chat_session(lease_id))
        self._runtime.disarm_voice_motion(lease_id=lease_id)
        self._runtime.revoke_camera(self.chat_session(lease_id))

    async def lease_revoked(self, lease_id: str, reason: str) -> None:
        self.revoke_permissions(lease_id)

        async def stop_servos() -> None:
            result = await self._runtime.execute_tool(
                tool_name="robot.servo.stop",
                arguments={},
                session_id=self.control_session(lease_id),
                lease_id=lease_id,
                requested_by=f"web-lease-{reason}",
            )
            if result.status is not ToolExecutionStatus.SUCCEEDED:
                raise RuntimeError("controller servo stop could not be confirmed")

        async def stop_voice() -> None:
            if self._voice_owner == lease_id:
                self._voice_owner = None
                await self._runtime.release_browser_voice(lease_id)

        try:
            results = await asyncio.gather(
                stop_servos(),
                self._cancel_movement(),
                self.stop_transcription(lease_id),
                stop_voice(),
                return_exceptions=True,
            )
            if any(isinstance(result, BaseException) for result in results):
                raise RuntimeError("controller activity cleanup failed")
        finally:
            self._chat_sessions.pop(lease_id, None)

    async def _cancel_movement(self) -> None:
        async with self._movement_lock:
            pending = self._movement
            self._movement = None
        if pending is not None:
            _owner, token, task = pending
            token.cancel()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @staticmethod
    def _consume_background_result(task: asyncio.Task[Any]) -> None:
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            return


def _browser_chat_session(browser_chat_id: str) -> str:
    normalized = browser_chat_id.strip()
    if not 16 <= len(normalized) <= 128 or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for character in normalized
    ):
        raise ValueError("browser_chat_id must be 16-128 URL-safe characters")
    digest = hashlib.sha256(normalized.encode("ascii")).hexdigest()[:32]
    return f"web-chat-{digest}"
