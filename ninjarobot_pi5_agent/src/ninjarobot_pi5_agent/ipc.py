"""Owner-only Unix-socket protocol for reconnectable local interfaces."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .runtime import AgentRuntime
from .service import ServiceOwnership
from .tools import CancellationToken
from .web_app import WebServerManager

MAX_REQUEST_BYTES = 1_048_576


class AgentIPCError(RuntimeError):
    """Raised when the local service protocol is unavailable or malformed."""


class AgentIPCServer:
    """Serve one runtime to any number of short-lived local CLI connections."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        socket_path: str | Path,
        ownership: ServiceOwnership,
        web: WebServerManager | None = None,
    ) -> None:
        self._runtime = runtime
        self._socket_path = Path(socket_path).expanduser()
        self._ownership = ownership
        self._web = web
        self._server: asyncio.AbstractServer | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        """Acquire ownership, start runtime, and bind an owner-only socket."""
        self._ownership.acquire()
        try:
            await self._runtime.start()
            self._socket_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._socket_path.parent.chmod(0o700)
            try:
                self._socket_path.unlink()
            except FileNotFoundError:
                pass
            self._server = await asyncio.start_unix_server(
                self._handle_client,
                path=self._socket_path,
            )
            os.chmod(self._socket_path, 0o600)
        except BaseException:
            await self._runtime.close()
            self._ownership.release()
            raise

    async def serve(self) -> None:
        """Wait until a local stop request is acknowledged."""
        if self._server is None:
            raise RuntimeError("IPC server is not started")
        await self._stop.wait()

    def request_stop(self) -> None:
        """Request orderly shutdown from a local signal handler."""
        self._stop.set()

    async def close(self) -> None:
        """Stop accepting clients and release every owned resource."""
        server = self._server
        self._server = None
        if server is not None:
            server.close()
            await server.wait_closed()
        if self._web is not None:
            await self._web.close()
        await self._runtime.close()
        self._ownership.release()
        try:
            self._socket_path.unlink()
        except FileNotFoundError:
            pass

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        cancellation = CancellationToken()
        try:
            raw = await reader.readline()
            if not raw or len(raw) > MAX_REQUEST_BYTES:
                raise AgentIPCError("request is empty or too large")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise AgentIPCError("request must be a JSON object")
            await self._dispatch(payload, writer, cancellation)
        except (BrokenPipeError, ConnectionResetError):
            cancellation.cancel()
        except (AgentIPCError, ValueError, KeyError, PermissionError) as exc:
            await _write_error_if_connected(
                writer,
                f"{type(exc).__name__}: {exc}",
            )
        except Exception as exc:
            await _write_error_if_connected(
                writer,
                f"{type(exc).__name__}: {exc}",
            )
        finally:
            cancellation.cancel()
            writer.close()
            try:
                await writer.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass

    async def _dispatch(
        self,
        payload: dict[str, Any],
        writer: asyncio.StreamWriter,
        cancellation: CancellationToken,
    ) -> None:
        command = payload.get("command")
        if command == "chat":

            async def send_delta(text: str) -> None:
                await _write_message(writer, {"type": "delta", "text": text})

            reply = await self._runtime.chat(
                session_id=_required_text(payload, "session_id"),
                text=_required_text(payload, "text"),
                skill_id=_optional_text(payload, "skill_id"),
                lease_id=_optional_text(payload, "lease_id"),
                confirmed=payload.get("confirmed") is True,
                cancellation=cancellation,
                on_text_delta=send_delta,
            )
            await _write_message(
                writer,
                {"type": "result", "data": reply.model_dump(mode="json")},
            )
            return
        if command == "status":
            await _write_message(
                writer,
                {"type": "result", "data": await self._runtime.status()},
            )
            return
        if command == "models":
            await _write_message(
                writer,
                {
                    "type": "result",
                    "data": [
                        model.model_dump(mode="json") for model in await self._runtime.list_models()
                    ],
                },
            )
            return
        if command == "model_current":
            await _write_message(
                writer,
                {"type": "result", "data": self._runtime.current_model()},
            )
            return
        if command == "model_select":
            selected = await self._runtime.select_model(
                _required_text(payload, "provider"),
                _required_text(payload, "model"),
            )
            await _write_message(
                writer,
                {"type": "result", "data": selected.model_dump(mode="json")},
            )
            return
        if command == "sessions":
            await _write_message(
                writer,
                {"type": "result", "data": await self._runtime.sessions()},
            )
            return
        if command == "history":
            await _write_message(
                writer,
                {
                    "type": "result",
                    "data": await self._runtime.history(_required_text(payload, "session_id")),
                },
            )
            return
        if command == "clear":
            count = await self._runtime.clear(_required_text(payload, "session_id"))
            await _write_message(
                writer,
                {"type": "result", "data": {"cleared_messages": count}},
            )
            return
        if command == "arm_motion":
            self._runtime.arm_motion(
                _required_text(payload, "session_id"),
                confirmed=payload.get("confirmed") is True,
                lease_id=_optional_text(payload, "lease_id"),
            )
            await _write_message(
                writer,
                {"type": "result", "data": {"motion_armed": True}},
            )
            return
        if command == "disarm_motion":
            session_id = _required_text(payload, "session_id")
            await self._runtime.stop_and_disarm_motion(
                session_id,
                lease_id=_optional_text(payload, "lease_id"),
                requested_by="ipc-disarm",
            )
            await _write_message(
                writer,
                {"type": "result", "data": {"motion_armed": False}},
            )
            return
        if command == "resume_system":
            result = await self._runtime.resume_system(
                _required_text(payload, "session_id"),
                confirmed=payload.get("confirmed") is True,
                lease_id=_optional_text(payload, "lease_id"),
                requested_by="ipc-resume",
            )
            await _write_message(
                writer,
                {"type": "result", "data": result.model_dump(mode="json")},
            )
            return
        if command == "grant_camera":
            session_id = _required_text(payload, "session_id")
            self._runtime.grant_camera(
                session_id,
                confirmed=payload.get("confirmed") is True,
                lease_id=_optional_text(payload, "lease_id"),
            )
            await _write_message(
                writer,
                {
                    "type": "result",
                    "data": {"ai_camera_granted": True, "captures_remaining": 1},
                },
            )
            return
        if command == "revoke_camera":
            self._runtime.revoke_camera(_required_text(payload, "session_id"))
            await _write_message(
                writer,
                {
                    "type": "result",
                    "data": {"ai_camera_granted": False, "captures_remaining": 0},
                },
            )
            return
        if command == "web_start":
            if self._web is None:
                raise AgentIPCError("web interface is not configured")
            await _write_message(
                writer,
                {"type": "result", "data": await self._web.start()},
            )
            return
        if command == "web_status":
            if self._web is None:
                raise AgentIPCError("web interface is not configured")
            await _write_message(
                writer,
                {"type": "result", "data": self._web.status()},
            )
            return
        if command == "web_stop":
            if self._web is None:
                raise AgentIPCError("web interface is not configured")
            await _write_message(
                writer,
                {"type": "result", "data": await self._web.stop()},
            )
            return
        if command == "stop":
            await _write_message(
                writer,
                {"type": "result", "data": {"service_stopping": True}},
            )
            self._stop.set()
            return
        raise AgentIPCError(f"unknown command: {command}")


class AgentIPCClient:
    """Reconnect to an already-running local agent service."""

    def __init__(self, socket_path: str | Path) -> None:
        self._socket_path = Path(socket_path).expanduser()

    async def stream(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Yield streamed protocol messages until the server closes."""
        try:
            reader, writer = await asyncio.open_unix_connection(self._socket_path)
        except (FileNotFoundError, ConnectionRefusedError, OSError) as exc:
            raise AgentIPCError("agent service is not running") from exc
        try:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
            if len(encoded) > MAX_REQUEST_BYTES:
                raise AgentIPCError("request is too large")
            writer.write(encoded)
            await writer.drain()
            while raw := await reader.readline():
                decoded = json.loads(raw)
                if not isinstance(decoded, dict):
                    raise AgentIPCError("service response was not an object")
                yield decoded
        finally:
            writer.close()
            await writer.wait_closed()

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the single terminal result or raise its sanitized error."""
        terminal: dict[str, Any] | None = None
        async for message in self.stream(payload):
            if message.get("type") == "error":
                raise AgentIPCError(str(message.get("error", "unknown service error")))
            if message.get("type") == "result":
                terminal = message
        if terminal is None:
            raise AgentIPCError("agent service returned no result")
        data = terminal.get("data")
        if not isinstance(data, dict) and not isinstance(data, list):
            raise AgentIPCError("agent service result is malformed")
        return {"data": data}


async def _write_message(
    writer: asyncio.StreamWriter,
    payload: dict[str, Any],
) -> None:
    writer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
    await writer.drain()


async def _write_error_if_connected(
    writer: asyncio.StreamWriter,
    error: str,
) -> None:
    """Best-effort error reporting when the requesting client may already be gone."""
    try:
        await _write_message(writer, {"type": "error", "error": error})
    except (BrokenPipeError, ConnectionResetError):
        return


def _required_text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise AgentIPCError(f"{name} must be non-empty text")
    return value


def _optional_text(payload: dict[str, Any], name: str) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AgentIPCError(f"{name} must be non-empty text when provided")
    return value
