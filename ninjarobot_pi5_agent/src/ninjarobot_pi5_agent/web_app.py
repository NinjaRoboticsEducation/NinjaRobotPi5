"""HTTPS FastAPI controller hosted inside the single-owner agent service."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .events import AgentEvent
from .runtime import AgentRuntime
from .web_control import (
    ControllerLeaseManager,
    ControllerLockedError,
    InvalidControllerLeaseError,
    WebRobotController,
)

MAX_WEB_MESSAGE_BYTES = 64 * 1024


def ensure_self_signed_certificate(
    certificate_path: str | Path,
    key_path: str | Path,
) -> tuple[Path, Path]:
    """Create a private, reusable localhost/LAN certificate when absent."""
    certificate = Path(certificate_path).expanduser()
    key = Path(key_path).expanduser()
    if certificate.is_file() and key.is_file():
        os.chmod(key, 0o600)
        return certificate, key
    if certificate.exists() != key.exists():
        raise RuntimeError("HTTPS certificate and key must either both exist or both be absent")
    certificate.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    key.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    certificate.parent.chmod(0o700)
    key.parent.chmod(0o700)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    hostname = socket.gethostname()
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NinjaRobotPi5"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ]
    )
    now = datetime.now(UTC)
    san_names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName(hostname),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ]
    built = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .sign(private_key, hashes.SHA256())
    )
    key_tmp = key.with_name(f".{key.name}.tmp")
    certificate_tmp = certificate.with_name(f".{certificate.name}.tmp")
    try:
        key_tmp.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        os.chmod(key_tmp, 0o600)
        certificate_tmp.write_bytes(built.public_bytes(serialization.Encoding.PEM))
        os.chmod(certificate_tmp, 0o600)
        os.replace(key_tmp, key)
        os.replace(certificate_tmp, certificate)
    finally:
        key_tmp.unlink(missing_ok=True)
        certificate_tmp.unlink(missing_ok=True)
    return certificate, key


def create_web_app(
    *,
    runtime: AgentRuntime,
    controller: WebRobotController,
    leases: ControllerLeaseManager,
    static_directory: str | Path,
) -> FastAPI:
    """Build the fixed local-network API; arbitrary tool calls are never exposed."""
    static_root = Path(static_directory).resolve()
    app = FastAPI(
        title="NinjaRobotAgent",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.mount("/assets", StaticFiles(directory=static_root), name="assets")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(static_root / "index.html")

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, Any]:
        return {
            "service": "ready",
            "controller": await leases.status(),
            "provider": (await runtime.provider_health()).model_dump(mode="json"),
        }

    @app.websocket("/ws")
    async def websocket_controller(websocket: WebSocket) -> None:
        reconnect_token = websocket.query_params.get("reconnect_token")
        try:
            lease = await leases.acquire(reconnect_token)
        except ControllerLockedError:
            denial = PlainTextResponse(
                "Another device currently controls NinjaRobot.",
                status_code=423,
            )
            send_denial = getattr(websocket, "send_denial_response", None)
            if send_denial is not None:
                await send_denial(denial)
            else:
                await websocket.close(code=4423, reason="423 Locked")
            return

        await websocket.accept()
        controller.activate(lease.lease_id)
        send_lock = asyncio.Lock()
        operation_lock = asyncio.Lock()
        client_tasks: set[asyncio.Task[None]] = set()
        event_queue = await runtime.events.subscribe()

        async def send(payload: dict[str, Any]) -> None:
            async with send_lock:
                await websocket.send_json(payload)

        async def send_event(event: AgentEvent) -> None:
            await send(
                {
                    "type": "event",
                    "event": event.model_dump(mode="json"),
                }
            )

        async def forward_events() -> None:
            while True:
                await send_event(await event_queue.get())

        async def run_request(message: dict[str, Any]) -> None:
            request_id = _request_id(message)
            try:
                kind = _required_string(message, "type")
                if kind in {"emergency_stop", "move_stop", "usb_microphone_stop"}:
                    data = await _dispatch_web_message(
                        controller,
                        lease.lease_id,
                        message,
                        send,
                    )
                else:
                    async with operation_lock:
                        data = await _dispatch_web_message(
                            controller,
                            lease.lease_id,
                            message,
                            send,
                        )
                await send({"type": "result", "request_id": request_id, "data": data})
            except (ValueError, PermissionError, RuntimeError) as exc:
                await send(
                    {
                        "type": "error",
                        "request_id": request_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        event_task = asyncio.create_task(forward_events(), name="web-event-forwarder")
        try:
            await send(
                {
                    "type": "lease",
                    "lease_id": lease.lease_id,
                    "reconnect_token": lease.reconnect_token,
                    "heartbeat_seconds": lease.heartbeat_seconds,
                    "session_id": controller.chat_session(lease.lease_id),
                }
            )
            await send(
                {
                    "type": "system_status",
                    "data": await runtime.status(),
                }
            )
            await send(
                {
                    "type": "conversation_history",
                    "data": await runtime.history(controller.chat_session(lease.lease_id)),
                }
            )
            for event in await runtime.events.history():
                await send_event(event)
            while True:
                raw = await websocket.receive_text()
                if len(raw.encode("utf-8")) > MAX_WEB_MESSAGE_BYTES:
                    raise ValueError("web message exceeds the 64 KiB limit")
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise ValueError("web message must be a JSON object")
                message_lease = _required_string(message, "lease_id")
                if message_lease != lease.lease_id:
                    raise InvalidControllerLeaseError("controller lease does not match")
                await leases.validate(message_lease)
                if message.get("type") == "heartbeat":
                    await leases.heartbeat(message_lease)
                    await send(
                        {
                            "type": "heartbeat",
                            "request_id": _request_id(message),
                            "ok": True,
                        }
                    )
                    continue
                if message.get("type") == "release":
                    await send(
                        {
                            "type": "result",
                            "request_id": _request_id(message),
                            "data": {"released": True},
                        }
                    )
                    await leases.release(message_lease)
                    return
                task = asyncio.create_task(
                    run_request(message),
                    name=f"web-request-{_request_id(message)}",
                )
                client_tasks.add(task)
                task.add_done_callback(client_tasks.discard)
        except (WebSocketDisconnect, InvalidControllerLeaseError):
            pass
        finally:
            for task in client_tasks:
                task.cancel()
            await asyncio.gather(*client_tasks, return_exceptions=True)
            event_task.cancel()
            await asyncio.gather(event_task, return_exceptions=True)
            await runtime.events.unsubscribe(event_queue)
            await leases.disconnect(lease.lease_id)

    return app


async def _dispatch_web_message(
    controller: WebRobotController,
    lease_id: str,
    message: dict[str, Any],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> dict[str, Any]:
    kind = _required_string(message, "type")
    if kind == "move_start":
        return await controller.start_movement(
            lease_id,
            _required_string(message, "direction"),
        )
    if kind == "move_stop":
        return await controller.stop_motion(lease_id)
    if kind == "behavior":
        return await controller.run_behavior(
            lease_id,
            _required_string(message, "name"),
        )
    if kind == "emergency_stop":
        return await controller.emergency_stop(lease_id)
    if kind == "resume":
        if message.get("confirmed") is not True:
            raise PermissionError("resume requires explicit confirmation")
        return await controller.resume(lease_id)
    if kind == "camera":
        return await controller.camera_preview(lease_id)
    if kind == "usb_microphone":
        duration = message.get("duration_seconds", 5.0)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ValueError("duration_seconds must be a number")
        language = message.get("language", "auto")
        if not isinstance(language, str):
            raise ValueError("language must be text")
        return await controller.transcribe(
            lease_id,
            duration_seconds=float(duration),
            language=language,
        )
    if kind == "usb_microphone_stop":
        return await controller.stop_transcription(lease_id)
    if kind == "chat":
        text = _required_string(message, "text")

        async def send_delta(delta: str) -> None:
            await send(
                {
                    "type": "chat_delta",
                    "request_id": _request_id(message),
                    "text": delta,
                }
            )

        reply = await controller.chat(lease_id, text, on_text_delta=send_delta)
        return reply.model_dump(mode="json")
    if kind == "arm_chat_motion":
        if message.get("confirmed") is not True:
            raise PermissionError("AI motion arming requires explicit confirmation")
        controller.arm_chat_motion(lease_id, confirmed=True)
        return {"motion_armed": True}
    if kind == "disarm_chat_motion":
        controller.disarm_chat_motion(lease_id)
        return {"motion_armed": False}
    raise ValueError(f"unsupported web request type: {kind}")


class WebServerManager:
    """Start and stop one uvicorn HTTPS server inside the agent owner process."""

    def __init__(
        self,
        *,
        app: FastAPI,
        leases: ControllerLeaseManager,
        host: str,
        port: int,
        certificate_path: str | Path,
        key_path: str | Path,
    ) -> None:
        if not 1 <= port <= 65_535:
            raise ValueError("web port must be from 1 through 65535")
        self._app = app
        self._leases = leases
        self._host = host
        self._port = port
        self._certificate_path = Path(certificate_path).expanduser()
        self._key_path = Path(key_path).expanduser()
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> dict[str, Any]:
        if self._task is not None and not self._task.done():
            return self.status()
        certificate, key = await asyncio.to_thread(
            ensure_self_signed_certificate,
            self._certificate_path,
            self._key_path,
        )
        await self._leases.start()
        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            ssl_certfile=str(certificate),
            ssl_keyfile=str(key),
            access_log=False,
            log_level="warning",
        )
        server = _EmbeddedUvicornServer(config)
        task = asyncio.create_task(server.serve(), name="ninjarobot-web-server")
        self._server = server
        self._task = task
        for _ in range(100):
            if server.started:
                return self.status()
            if task.done():
                await task
                raise RuntimeError("web server stopped before it became ready")
            await asyncio.sleep(0.05)
        await self.stop()
        raise RuntimeError("web server did not become ready within five seconds")

    async def stop(self) -> dict[str, Any]:
        server = self._server
        task = self._task
        self._server = None
        self._task = None
        if server is not None:
            server.should_exit = True
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=10.0)
            except TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        await self._leases.close()
        return self.status()

    def status(self) -> dict[str, Any]:
        running = self._task is not None and not self._task.done()
        display_host = socket.gethostname() if self._host in {"0.0.0.0", "::"} else self._host
        return {
            "running": running,
            "host": self._host,
            "port": self._port,
            "url": f"https://{display_host}:{self._port}/" if running else None,
            "certificate": str(self._certificate_path),
        }

    async def close(self) -> None:
        await self.stop()


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be non-empty text")
    return value.strip()


def _request_id(payload: dict[str, Any]) -> str:
    value = payload.get("request_id")
    if not isinstance(value, str) or not value:
        raise ValueError("request_id must be non-empty text")
    return value


class _EmbeddedUvicornServer(uvicorn.Server):
    """Let the owning agent service retain all process signal handlers."""

    def install_signal_handlers(self) -> None:
        return
