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
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .events import AgentEvent
from .pairing import (
    REMOTE_MARKER_HEADER,
    SESSION_COOKIE_NAME,
    PairingError,
    PairingSessionManager,
)
from .runtime import AgentRuntime
from .shutdown import PoweroffCoordinator
from .web_control import (
    ControllerLeaseManager,
    ControllerLockedError,
    InvalidControllerLeaseError,
    WebRobotController,
)

MAX_WEB_MESSAGE_BYTES = 64 * 1024
_PAIRING_BOOTSTRAP_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NinjaRobot Pairing</title><style>
body{font-family:system-ui,sans-serif;background:#101318;color:#fff;display:grid;
place-items:center;min-height:100vh;margin:0}main{max-width:28rem;padding:2rem;text-align:center}
</style></head><body><main><h1>NinjaRobot Pairing</h1>
<p id="status">Checking this one-time pairing link…</p></main><script>
(async()=>{const output=document.querySelector('#status');
const token=new URLSearchParams(location.hash.slice(1)).get('pair');
history.replaceState(null,'',location.pathname);
if(!token){output.textContent='Scan a fresh QR code shown by NinjaRobot.';return;}
try{const response=await fetch('/pair',{method:'POST',credentials:'same-origin',
headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
if(!response.ok)throw new Error('pairing rejected');location.replace('/');}
catch(_error){output.textContent='This pairing link is invalid, expired, or already used. '
+'Scan a fresh QR code.';}
})();</script></body></html>"""


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
            if _certificate_dns_names(existing) >= _required_dns_names() and _certificate_ip_names(
                existing
            ) >= {"127.0.0.1", "::1"}:
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


def _certificate_ip_names(certificate: x509.Certificate) -> set[str]:
    try:
        extension = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return set()
    return {str(address) for address in extension.value.get_values_for_type(x509.IPAddress)}


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
    pairing: PairingSessionManager | None = None,
    poweroff: PoweroffCoordinator | None = None,
    require_local_pairing: bool = False,
    access_state: WebAccessState | None = None,
    on_authenticated_controller: Callable[[bool, bool], Awaitable[None]] | None = None,
) -> FastAPI:
    """Build the fixed local-network API; arbitrary tool calls are never exposed."""
    static_root = Path(static_directory).resolve()
    app = FastAPI(
        title="NinjaRobotAgent",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def pairing_boundary(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if pairing is None:
            return await call_next(request)
        try:
            scope = pairing.request_scope(
                request.headers.get("host", ""),
                remote_marker=request.headers.get(REMOTE_MARKER_HEADER),
            )
        except PairingError:
            return PlainTextResponse("Invalid request host.", status_code=421)
        if scope == "denied":
            return PlainTextResponse("Unknown request host.", status_code=421)
        if scope == "local" and access_state is not None and not access_state.local_available:
            return PlainTextResponse(
                "Local Web Interface is unavailable while ngrok Remote Access is active.",
                status_code=503,
            )
        if request.url.path == "/pair":
            return await call_next(request)
        if scope == "local" and not require_local_pairing:
            return await call_next(request)
        session = request.cookies.get(SESSION_COOKIE_NAME)
        try:
            authorized = pairing.authorize_controller(
                session,
                origin=request.headers.get("origin"),
                host=request.headers.get("host", ""),
                remote_marker=request.headers.get(REMOTE_MARKER_HEADER),
                require_origin=False,
            )
        except PairingError:
            authorized = False
        if authorized:
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        if request.method == "GET" and request.url.path == "/":
            return HTMLResponse(
                _PAIRING_BOOTSTRAP_HTML,
                headers={
                    "Cache-Control": "no-store",
                    "Content-Security-Policy": (
                        "default-src 'none'; script-src 'unsafe-inline'; "
                        "style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'"
                    ),
                    "Referrer-Policy": "no-referrer",
                },
            )
        return PlainTextResponse("Remote browser pairing required.", status_code=401)

    app.mount("/assets", StaticFiles(directory=static_root), name="assets")

    @app.post("/pair", include_in_schema=False)
    async def pair_browser(request: Request) -> JSONResponse:
        if pairing is None:
            return JSONResponse({"paired": False}, status_code=404)
        raw = await request.body()
        if len(raw) > 2048:
            return JSONResponse({"paired": False}, status_code=413)
        try:
            payload = json.loads(raw)
            token = payload.get("token") if isinstance(payload, dict) else None
            if not isinstance(token, str):
                raise PairingError("pairing token is malformed")
            session = pairing.exchange(
                token,
                origin=request.headers.get("origin"),
                host=request.headers.get("host", ""),
                remote_marker=request.headers.get(REMOTE_MARKER_HEADER),
            )
        except (json.JSONDecodeError, PairingError):
            return JSONResponse({"paired": False}, status_code=401)
        response = JSONResponse({"paired": True})
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session,
            secure=True,
            httponly=True,
            samesite="strict",
            max_age=pairing.session_lifetime_seconds,
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

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
        remote_connection = False
        paired_connection = False
        if pairing is not None:
            try:
                scope = pairing.request_scope(
                    websocket.headers.get("host", ""),
                    remote_marker=websocket.headers.get(REMOTE_MARKER_HEADER),
                )
                if scope == "denied":
                    raise PairingError("unknown request host")
                remote_connection = scope == "remote"
                if (
                    scope == "local"
                    and access_state is not None
                    and not access_state.local_available
                ):
                    raise PairingError("local web interface is disabled")
                try:
                    paired_connection = pairing.authorize_controller(
                        websocket.cookies.get(SESSION_COOKIE_NAME),
                        origin=websocket.headers.get("origin"),
                        host=websocket.headers.get("host", ""),
                        remote_marker=websocket.headers.get(REMOTE_MARKER_HEADER),
                    )
                except PairingError:
                    paired_connection = False
                if (remote_connection or require_local_pairing) and not paired_connection:
                    raise PairingError("browser pairing required")
            except PairingError:
                denial = PlainTextResponse("Remote browser pairing required.", status_code=401)
                send_denial = getattr(websocket, "send_denial_response", None)
                denial_supported = "websocket.http.response" in websocket.scope.get(
                    "extensions", {}
                )
                if send_denial is not None and denial_supported:
                    await send_denial(denial)
                else:
                    await websocket.close(code=4401, reason="Pairing required")
                return
        reconnect_token = websocket.query_params.get("reconnect_token")
        browser_chat_id = websocket.query_params.get("browser_chat_id")
        try:
            lease = await leases.acquire(reconnect_token)
        except ControllerLockedError:
            denial = PlainTextResponse(
                "Another device currently controls NinjaRobot.",
                status_code=423,
            )
            send_denial = getattr(websocket, "send_denial_response", None)
            denial_supported = "websocket.http.response" in websocket.scope.get("extensions", {})
            if send_denial is not None and denial_supported:
                await send_denial(denial)
            else:
                await websocket.close(code=4423, reason="423 Locked")
            return

        await websocket.accept()
        try:
            controller.activate(lease.lease_id, browser_chat_id=browser_chat_id)
        except (ValueError, PermissionError, RuntimeError) as error:
            await leases.release(lease.lease_id)
            await websocket.close(code=4403, reason=str(error)[:120])
            return
        if on_authenticated_controller is not None:
            await on_authenticated_controller(remote_connection, paired_connection)
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
                if kind in {"emergency_stop", "move_stop", "usb_microphone_stop", "speech"}:
                    data = await _dispatch_web_message(
                        controller,
                        lease.lease_id,
                        message,
                        send,
                        poweroff=poweroff,
                        poweroff_authorized=paired_connection,
                    )
                else:
                    async with operation_lock:
                        data = await _dispatch_web_message(
                            controller,
                            lease.lease_id,
                            message,
                            send,
                            poweroff=poweroff,
                            poweroff_authorized=paired_connection,
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
                    "remote": remote_connection,
                    "poweroff_authorized": paired_connection,
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
    *,
    poweroff: PoweroffCoordinator | None = None,
    poweroff_authorized: bool = False,
) -> dict[str, Any]:
    kind = _required_string(message, "type")
    if kind == "guided_checks":
        return await controller.guided_checks(message.get("step", 0))
    if kind == "tasks":
        return await controller.task_action(
            lease_id,
            message.get("operation", "list"),
            message.get("task_id", ""),
            message.get("minutes", 5),
        )
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
    if kind == "voice_enable":
        return await controller.enable_voice_input()
    if kind == "voice_disable":
        return await controller.disable_voice_input()
    if kind == "speech":
        return await controller.speech_control(_required_string(message, "operation"))
    if kind == "voice_status":
        return controller.voice_input_status()
    if kind == "poweroff_prepare":
        if not poweroff_authorized:
            raise PermissionError("power-off requires a paired controller")
        if poweroff is None:
            raise PermissionError("web power-off is unavailable")
        return await poweroff.issue_nonce(lease_id)
    if kind == "poweroff_confirm":
        if not poweroff_authorized:
            raise PermissionError("power-off requires a paired controller")
        if message.get("confirmed") is not True:
            raise PermissionError("power-off requires explicit confirmation")
        if poweroff is None:
            raise PermissionError("web power-off is unavailable")
        return await poweroff.confirm(lease_id, _required_string(message, "nonce"))
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
        return controller.grant_chat_camera(lease_id, confirmed=True)
    if kind == "revoke_chat_camera":
        controller.revoke_chat_camera(lease_id)
        return {"ai_camera_granted": False, "captures_remaining": 0}
    raise ValueError(f"unsupported web request type: {kind}")


class WebAccessState:
    """Track user-visible local access separately from the shared HTTPS backend."""

    def __init__(self) -> None:
        self._local_requested = False
        self._remote_enabled = False
        self._local_fallback = False

    @property
    def mode(self) -> str:
        if self._local_fallback:
            return "local_fallback"
        if self._remote_enabled:
            return "remote"
        if self._local_requested:
            return "local"
        return "none"

    @property
    def local_available(self) -> bool:
        return self._local_requested or self._local_fallback

    @property
    def backend_required(self) -> bool:
        return self._remote_enabled or self.local_available

    def request_local(self) -> bool:
        if self._remote_enabled and not self._local_fallback:
            return False
        self._local_requested = True
        return True

    def stop_local(self) -> None:
        self._local_requested = False
        self._local_fallback = False

    def enable_remote(self) -> None:
        self._remote_enabled = True
        self._local_requested = False
        self._local_fallback = False

    def disable_remote(self) -> None:
        self._remote_enabled = False
        self._local_fallback = False

    def enable_local_fallback(self) -> None:
        self._local_requested = False
        self._local_fallback = True

    def disable_local_fallback(self) -> None:
        self._local_fallback = False

    def reset(self) -> None:
        self._local_requested = False
        self._remote_enabled = False
        self._local_fallback = False


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
        access_state: WebAccessState | None = None,
    ) -> None:
        if not 1 <= port <= 65_535:
            raise ValueError("web port must be from 1 through 65535")
        self._app = app
        self._leases = leases
        self._host = host
        self._port = port
        self._certificate_path = Path(certificate_path).expanduser()
        self._key_path = Path(key_path).expanduser()
        self._access_state = access_state or WebAccessState()
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> dict[str, Any]:
        if not self._access_state.request_local():
            return self.status()
        await self._start_backend()
        return self.status()

    async def start_remote(self) -> dict[str, Any]:
        """Start the shared backend without claiming that the tunnel is ready."""
        await self._start_backend()
        return self.backend_status()

    async def activate_remote(self) -> dict[str, Any]:
        """Withdraw local access only after ngrok reports a usable endpoint."""
        self._access_state.enable_remote()
        await self._start_backend()
        return self.backend_status()

    async def start_local_fallback(self) -> dict[str, Any]:
        self._access_state.enable_local_fallback()
        await self._start_backend()
        return self.status()

    async def stop_local_fallback(self) -> dict[str, Any]:
        self._access_state.disable_local_fallback()
        if not self._access_state.backend_required:
            await self._stop_backend()
        return self.status()

    async def _start_backend(self) -> None:
        if self._task is not None and not self._task.done():
            return
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
                return
            if task.done():
                await task
                raise RuntimeError("web server stopped before it became ready")
            await asyncio.sleep(0.05)
        await self._stop_backend()
        raise RuntimeError("web server did not become ready within five seconds")

    async def stop(self) -> dict[str, Any]:
        self._access_state.stop_local()
        if self._access_state.backend_required:
            return self.status()
        await self._stop_backend()
        return self.status()

    async def stop_remote(self) -> dict[str, Any]:
        self._access_state.disable_remote()
        if not self._access_state.backend_required:
            await self._stop_backend()
        return self.status()

    async def _stop_backend(self) -> None:
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

    def status(self) -> dict[str, Any]:
        backend_running = self._task is not None and not self._task.done()
        running = backend_running and self._access_state.local_available
        display_host = mdns_hostname() if self._host in {"0.0.0.0", "::"} else self._host
        ca_certificate, _ca_key = local_ca_paths(self._certificate_path)
        url = f"https://{display_host}:{self._port}/" if running else None
        return {
            "running": running,
            "ready": running and bool(self._server and self._server.started),
            "host": self._host,
            "port": self._port,
            "url": url,
            "loopback_url": f"https://127.0.0.1:{self._port}/" if running else None,
            "certificate": str(self._certificate_path),
            "local_ca_certificate": (str(ca_certificate) if ca_certificate.is_file() else None),
            "browser_trust_required": ca_certificate.is_file(),
            "next_step": (
                "Open the URL in a browser. If the browser warns about the local "
                "certificate, export and trust the NinjaRobot local CA from the "
                "Interactive Tool. Use Remote Access when mDNS is unavailable."
                if running
                else (
                    "Connect the web interface via the ngrok pairing link or remote access QR code."
                    if self._access_state.mode == "remote"
                    else "Start the web interface from the Interactive Tool."
                )
            ),
        }

    def backend_status(self) -> dict[str, Any]:
        running = self._task is not None and not self._task.done()
        return {
            "running": running,
            "ready": running and bool(self._server and self._server.started),
            "access_mode": self._access_state.mode,
        }

    async def close(self) -> None:
        self._access_state.reset()
        await self._stop_backend()


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
