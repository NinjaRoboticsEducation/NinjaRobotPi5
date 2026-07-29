from __future__ import annotations

import asyncio
import os
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from ninjarobot_pi5_agent.events import EventBroker
from ninjarobot_pi5_agent.models import (
    ProviderHealth,
    ProviderHealthStatus,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from ninjarobot_pi5_agent.runtime import AgentRuntime
from ninjarobot_pi5_agent.web_app import (
    create_web_app,
    ensure_self_signed_certificate,
    local_ca_paths,
)
from ninjarobot_pi5_agent.web_control import (
    ControllerLeaseManager,
    ControllerLockedError,
    WebRobotController,
)
from starlette.testclient import TestClient, WebSocketDenialResponse


class _FakeRuntime:
    def __init__(self) -> None:
        self.events = EventBroker()

    async def provider_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="test",
            status=ProviderHealthStatus.READY,
            checked_at=datetime.now(UTC),
        )

    async def status(self) -> dict[str, Any]:
        return {
            "started": True,
            "provider": (await self.provider_health()).model_dump(mode="json"),
            "tool_providers": [],
            "tools": [],
            "session_count": 0,
        }

    async def history(self, _session_id: str) -> list[dict[str, Any]]:
        return []


class _FakeController:
    def __init__(self) -> None:
        self.activated: list[str] = []
        self.revoked: list[tuple[str, str]] = []

    def activate(self, lease_id: str) -> None:
        self.activated.append(lease_id)

    def chat_session(self, lease_id: str) -> str:
        return f"web-chat-{lease_id.removeprefix('lease-')}"

    async def lease_revoked(self, lease_id: str, reason: str) -> None:
        self.revoked.append((lease_id, reason))


class _RacingRuntime:
    def __init__(self) -> None:
        self.first_servo_stop_started = asyncio.Event()
        self.release_first_servo_stop = asyncio.Event()
        self.servo_stop_calls = 0
        self.behavior_cancelled = False

    async def execute_tool(self, **arguments: Any) -> ToolExecutionResult:
        tool_name = arguments["tool_name"]
        if tool_name == "robot.servo.stop":
            self.servo_stop_calls += 1
            if self.servo_stop_calls == 1:
                self.first_servo_stop_started.set()
                await self.release_first_servo_stop.wait()
        elif tool_name == "robot.behavior.run":
            cancellation = arguments["cancellation"]
            await cancellation.wait()
            self.behavior_cancelled = cancellation.cancelled
        return ToolExecutionResult(
            call_id=f"call-{self.servo_stop_calls + 1}",
            tool_name=tool_name,
            status=ToolExecutionStatus.SUCCEEDED,
            data={"ok": True},
        )

    def arm_motion(self, *_args: Any, **_kwargs: Any) -> None:
        return

    def disarm_motion(self, *_args: Any, **_kwargs: Any) -> None:
        return


def test_pointer_release_cannot_race_a_pending_movement_start() -> None:
    async def exercise() -> None:
        runtime = _RacingRuntime()
        controller = WebRobotController(cast(AgentRuntime, runtime))

        start = asyncio.create_task(controller.start_movement("lease-test", "forward"))
        await runtime.first_servo_stop_started.wait()
        stop = asyncio.create_task(controller.stop_motion("lease-test"))
        runtime.release_first_servo_stop.set()

        await start
        await stop
        assert runtime.behavior_cancelled is True
        assert runtime.servo_stop_calls == 2

    asyncio.run(exercise())


def test_controller_lease_is_exclusive_and_reconnectable() -> None:
    async def exercise() -> None:
        revoked: list[tuple[str, str]] = []

        async def on_revoke(lease_id: str, reason: str) -> None:
            revoked.append((lease_id, reason))

        manager = ControllerLeaseManager(on_revoke=on_revoke)
        first = await manager.acquire()
        with pytest.raises(ControllerLockedError):
            await manager.acquire()

        await manager.disconnect(first.lease_id)
        with pytest.raises(ControllerLockedError):
            await manager.acquire("wrong-token")
        reclaimed = await manager.acquire(first.reconnect_token)

        assert reclaimed.lease_id == first.lease_id
        await manager.release(first.lease_id)
        assert revoked == [(first.lease_id, "controller_release")]
        await manager.close()

    asyncio.run(exercise())


def test_missed_heartbeat_revokes_the_controller_lease() -> None:
    async def exercise() -> None:
        revoked = asyncio.Event()
        evidence: list[tuple[str, str]] = []

        async def on_revoke(lease_id: str, reason: str) -> None:
            evidence.append((lease_id, reason))
            revoked.set()

        manager = ControllerLeaseManager(
            on_revoke=on_revoke,
            heartbeat_seconds=0.01,
            heartbeat_timeout_seconds=0.03,
            reconnect_grace_seconds=0.02,
        )
        await manager.start()
        lease = await manager.acquire()
        await asyncio.wait_for(revoked.wait(), timeout=0.5)

        assert evidence == [(lease.lease_id, "heartbeat_timeout")]
        assert (await manager.status())["lease_active"] is False
        await manager.close()

    asyncio.run(exercise())


def test_second_websocket_receives_http_423_locked() -> None:
    runtime = _FakeRuntime()
    controller = _FakeController()
    leases = ControllerLeaseManager(on_revoke=controller.lease_revoked)
    static = Path(__file__).resolve().parents[1] / "src" / "ninjarobot_pi5_agent" / "web_static"
    app = create_web_app(
        runtime=cast(AgentRuntime, runtime),
        controller=cast(WebRobotController, controller),
        leases=leases,
        static_directory=static,
    )

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as first:
            lease = first.receive_json()
            assert lease["type"] == "lease"
            system_status = first.receive_json()
            assert system_status["type"] == "system_status"
            history = first.receive_json()
            assert history == {"type": "conversation_history", "data": []}
            with pytest.raises(WebSocketDenialResponse) as exc_info:
                with client.websocket_connect("/ws"):
                    pass
            assert exc_info.value.status_code == 423
            first.send_json(
                {
                    "type": "heartbeat",
                    "request_id": "heartbeat-1",
                    "lease_id": lease["lease_id"],
                }
            )
            response = first.receive_json()
            assert response == {
                "type": "heartbeat",
                "request_id": "heartbeat-1",
                "ok": True,
            }


def test_local_ca_certificate_is_reused_named_and_private(tmp_path: Path) -> None:
    certificate = tmp_path / "tls" / "cert.pem"
    key = tmp_path / "tls" / "key.pem"

    first = ensure_self_signed_certificate(certificate, key)
    first_bytes = certificate.read_bytes()
    second = ensure_self_signed_certificate(certificate, key)

    assert first == second == (certificate, key)
    assert certificate.read_bytes() == first_bytes
    assert certificate.read_text(encoding="ascii").startswith("-----BEGIN CERTIFICATE-----")
    assert certificate.read_bytes().count(b"-----BEGIN CERTIFICATE-----") == 2
    assert key.read_text(encoding="ascii").startswith("-----BEGIN PRIVATE KEY-----")
    assert os.stat(key).st_mode & 0o777 == 0o600
    ca_certificate, ca_key = local_ca_paths(certificate)
    server = x509.load_pem_x509_certificate(certificate.read_bytes())
    authority = x509.load_pem_x509_certificate(ca_certificate.read_bytes())
    names = set(
        server.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value.get_values_for_type(x509.DNSName)
    )
    hostname = socket.gethostname().rstrip(".")
    assert server.issuer == authority.subject
    assert {hostname, f"{hostname}.local", "localhost"} <= names
    assert authority.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is True
    assert os.stat(ca_key).st_mode & 0o777 == 0o600


def test_existing_leaf_only_certificate_is_upgraded_without_replacing_key(
    tmp_path: Path,
) -> None:
    certificate = tmp_path / "tls" / "cert.pem"
    key = tmp_path / "tls" / "key.pem"
    ensure_self_signed_certificate(certificate, key)
    leaf = x509.load_pem_x509_certificate(certificate.read_bytes())
    original_key = key.read_bytes()
    certificate.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))

    ensure_self_signed_certificate(certificate, key)

    assert key.read_bytes() == original_key
    assert certificate.read_bytes().count(b"-----BEGIN CERTIFICATE-----") == 2


def test_mobile_interface_has_safari_chrome_safety_and_input_only_speech() -> None:
    static = Path(__file__).resolve().parents[1] / "src" / "ninjarobot_pi5_agent" / "web_static"
    html = (static / "index.html").read_text(encoding="utf-8")
    css = (static / "styles.css").read_text(encoding="utf-8")
    javascript = (static / "app.js").read_text(encoding="utf-8")
    recognition_handler = javascript.split("recognition.onresult =", maxsplit=1)[1].split(
        "recognition.onerror =",
        maxsplit=1,
    )[0]

    assert 'id="activityDrawer"' in html
    assert 'class="orientation-blocker"' in html
    assert 'rel="manifest"' in html
    assert 'id="startControllerButton"' in html
    assert "maximum-scale=1, user-scalable=no" in html
    assert "Agent Controller" not in html
    assert "AI motion disarmed" not in html
    assert "DIRECT CONTROL" not in html
    assert 'aria-pressed="false"' in html
    assert "-webkit-user-select: none" in css
    assert "-webkit-touch-callout: none" in css
    assert "overscroll-behavior: none" in css
    assert "max(44px, calc(env(safe-area-inset-bottom) + 38px))" in css
    assert "grid-template-rows: auto minmax(0, 1fr) auto auto" in css
    assert "height: 100%" in css
    assert "grid-template-rows: repeat(3, minmax(0, 1fr))" in css
    assert "clamp(43px, 12.5vh, 66px)" not in css
    assert "event.preventDefault()" in javascript
    assert "elements.chatInput.focus()" in recognition_handler
    assert "submitChat(" not in recognition_handler
    assert 'elements.webMic.querySelector("strong")' in javascript
    assert 'elements.webMic.querySelector("span")' not in javascript
    assert "state.recognitionActive" in javascript
    assert "recognition.stop()" in javascript
    assert "requestFullscreen" in javascript
    assert "webkitRequestFullscreen" in javascript
    assert 'window.matchMedia("(display-mode: standalone)")' in javascript
    assert "startController()" in javascript
    assert "motionBadge" not in javascript
    assert "certificate-status" in javascript
    assert (static / "manifest.webmanifest").is_file()
