"""HTTPS FastAPI controller hosted inside the single-owner agent service."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import shutil
import socket
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
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


def local_ca_paths(certificate_path: str | Path) -> tuple[Path, Path]:
    """Return the public CA certificate and owner-only CA key paths."""
    parent = Path(certificate_path).expanduser().parent
    return parent / "local-ca.pem", parent / "local-ca-key.pem"


def ensure_local_ca_certificate(
    certificate_path: str | Path,
    key_path: str | Path,
) -> tuple[Path, Path]:
    """Create or reuse a local-CA-signed certificate for the mDNS hostname."""
    certificate = Path(certificate_path).expanduser()
    key = Path(key_path).expanduser()
    ca_certificate, ca_key = local_ca_paths(certificate)
    if certificate.is_file() and key.is_file():
        os.chmod(key, 0o600)
        existing = x509.load_pem_x509_certificate(certificate.read_bytes())
        if not ca_certificate.is_file() and not ca_key.is_file():
            if not _is_legacy_managed_certificate(existing):
                return certificate, key
            certificate.unlink()
            key.unlink()
        elif ca_certificate.is_file() and ca_key.is_file():
            ca = x509.load_pem_x509_certificate(ca_certificate.read_bytes())
            if existing.issuer != ca.subject:
                return certificate, key
            if _certificate_dns_names(existing) >= _required_dns_names():
                _ensure_served_certificate_chain(certificate, existing, ca)
                return certificate, key
            certificate.unlink()
            key.unlink()
    if certificate.exists() != key.exists():
        raise RuntimeError("HTTPS certificate and key must either both exist or both be absent")
    certificate.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    key.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    certificate.parent.chmod(0o700)
    key.parent.chmod(0o700)

    if ca_certificate.exists() != ca_key.exists():
        raise RuntimeError("local CA certificate and key must either both exist or both be absent")
    if ca_certificate.is_file():
        authority = x509.load_pem_x509_certificate(ca_certificate.read_bytes())
        authority_key = cast(
            rsa.RSAPrivateKey,
            serialization.load_pem_private_key(ca_key.read_bytes(), password=None),
        )
        os.chmod(ca_key, 0o600)
    else:
        authority_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        authority_subject = x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NinjaRobotPi5"),
                x509.NameAttribute(NameOID.COMMON_NAME, "NinjaRobotPi5 Local CA"),
            ]
        )
        now = datetime.now(UTC)
        authority = (
            x509.CertificateBuilder()
            .subject_name(authority_subject)
            .issuer_name(authority_subject)
            .public_key(authority_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(authority_key, hashes.SHA256())
        )
        _atomic_private_key(ca_key, authority_key)
        _atomic_certificate(ca_certificate, authority, mode=0o644)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    display_name = mdns_hostname()
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NinjaRobotPi5"),
            x509.NameAttribute(NameOID.COMMON_NAME, display_name),
        ]
    )
    now = datetime.now(UTC)
    san_names: list[x509.GeneralName] = [
        *(x509.DNSName(name) for name in sorted(_required_dns_names())),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ]
    built = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(authority.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage((ExtendedKeyUsageOID.SERVER_AUTH,)),
            critical=False,
        )
        .sign(authority_key, hashes.SHA256())
    )
    _atomic_private_key(key, private_key)
    _atomic_certificate_chain(certificate, built, authority, mode=0o644)
    return certificate, key


def ensure_self_signed_certificate(
    certificate_path: str | Path,
    key_path: str | Path,
) -> tuple[Path, Path]:
    """Backward-compatible name for the safer local-CA certificate setup."""
    return ensure_local_ca_certificate(certificate_path, key_path)


def export_local_ca_certificate(
    certificate_path: str | Path,
    key_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Export only the public CA certificate for browser trust onboarding."""
    certificate, _key = ensure_local_ca_certificate(certificate_path, key_path)
    ca_certificate, ca_key = local_ca_paths(certificate)
    if not ca_certificate.is_file() or not ca_key.is_file():
        raise RuntimeError("the configured server certificate is custom; no local CA is available")
    output = Path(output_path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ca_certificate, output)
    os.chmod(output, 0o644)
    return output


def _atomic_private_key(path: Path, private_key: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_certificate(path: Path, certificate: x509.Certificate, *, mode: int) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_certificate_chain(
    path: Path,
    leaf: x509.Certificate,
    authority: x509.Certificate,
    *,
    mode: int,
) -> None:
    """Write the server leaf followed by its local authority for TLS clients."""
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(
            leaf.public_bytes(serialization.Encoding.PEM)
            + authority.public_bytes(serialization.Encoding.PEM)
        )
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _ensure_served_certificate_chain(
    path: Path,
    leaf: x509.Certificate,
    authority: x509.Certificate,
) -> None:
    """Upgrade an existing leaf-only file without replacing its private key."""
    expected = leaf.public_bytes(serialization.Encoding.PEM) + authority.public_bytes(
        serialization.Encoding.PEM
    )
    if path.read_bytes() != expected:
        _atomic_certificate_chain(path, leaf, authority, mode=0o644)


def mdns_hostname() -> str:
    """Return the Bonjour/mDNS hostname browsers should open."""
    hostname = socket.gethostname().rstrip(".")
    return hostname if hostname.endswith(".local") else f"{hostname}.local"


def _required_dns_names() -> set[str]:
    hostname = socket.gethostname().rstrip(".")
    return {"localhost", hostname, mdns_hostname()}


def _certificate_dns_names(certificate: x509.Certificate) -> set[str]:
    try:
        extension = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return set()
    return set(extension.value.get_values_for_type(x509.DNSName))


def _is_legacy_managed_certificate(certificate: x509.Certificate) -> bool:
    organizations = certificate.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
    return certificate.subject == certificate.issuer and any(
        item.value == "NinjaRobotPi5" for item in organizations
    )


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
        await controller.stop_motion(lease_id)
        controller.disarm_chat_motion(lease_id)
        return {"motion_armed": False}
    if kind == "grant_chat_camera":
        if message.get("confirmed") is not True:
            raise PermissionError("AI camera access requires explicit confirmation")
        controller.grant_chat_camera(lease_id, confirmed=True)
        return {"ai_camera_granted": True, "captures_remaining": 1}
    if kind == "revoke_chat_camera":
        controller.revoke_chat_camera(lease_id)
        return {"ai_camera_granted": False, "captures_remaining": 0}
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
            ensure_local_ca_certificate,
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
        display_host = mdns_hostname() if self._host in {"0.0.0.0", "::"} else self._host
        ca_certificate, _ca_key = local_ca_paths(self._certificate_path)
        return {
            "running": running,
            "host": self._host,
            "port": self._port,
            "url": f"https://{display_host}:{self._port}/" if running else None,
            "certificate": str(self._certificate_path),
            "local_ca_certificate": (str(ca_certificate) if ca_certificate.is_file() else None),
            "browser_trust_required": ca_certificate.is_file(),
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
