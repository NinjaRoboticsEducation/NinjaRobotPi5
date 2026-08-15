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
from ninjarobot_pi5_agent.pairing import PairingSessionManager
from ninjarobot_pi5_agent.runtime import AgentRuntime
from ninjarobot_pi5_agent.shutdown import PoweroffCoordinator
from ninjarobot_pi5_agent.web_app import (
    WebAccessState,
    _dispatch_web_message,
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
        self.history_sessions: list[str] = []

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

    async def history(self, session_id: str) -> list[dict[str, Any]]:
        self.history_sessions.append(session_id)
        return []


class _FakeController:
    def __init__(self) -> None:
        self.activated: list[str] = []
        self.revoked: list[tuple[str, str]] = []
        self.sessions: dict[str, str] = {}

    def activate(self, lease_id: str, *, browser_chat_id: str | None = None) -> None:
        self.activated.append(lease_id)
        if browser_chat_id is not None:
            self.sessions[lease_id] = f"web-chat-{browser_chat_id}"

    def chat_session(self, lease_id: str) -> str:
        return self.sessions.get(lease_id, f"web-chat-{lease_id.removeprefix('lease-')}")

    async def lease_revoked(self, lease_id: str, reason: str) -> None:
        self.revoked.append((lease_id, reason))


class _FakePoweroff:
    def __init__(self) -> None:
        self.prepared: list[str] = []
        self.confirmed: list[tuple[str, str]] = []

    async def issue_nonce(self, lease_id: str) -> dict[str, object]:
        self.prepared.append(lease_id)
        return {"nonce": "nonce-for-active-controller", "expires_in_seconds": 30}

    async def confirm(self, lease_id: str, nonce: str) -> dict[str, object]:
        self.confirmed.append((lease_id, nonce))
        return {"shutdown_accepted": True}


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


class _ResumeRuntime:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.disarmed: list[str] = []
        self.armed: list[tuple[str, str | None]] = []
        self.resume_calls: list[dict[str, Any]] = []

    def disarm_motion(self, session_id: str) -> None:
        self.disarmed.append(session_id)

    def disarm_voice_motion(self, *, lease_id: str | None = None) -> None:
        self.disarmed.append(f"voice:{lease_id}")

    def arm_motion(
        self,
        session_id: str,
        *,
        confirmed: bool,
        lease_id: str | None = None,
    ) -> None:
        assert confirmed is True
        self.armed.append((session_id, lease_id))

    async def resume_system(self, session_id: str, **arguments: Any) -> ToolExecutionResult:
        self.resume_calls.append({"session_id": session_id, **arguments})
        if self.fail:
            raise RuntimeError("system resume failed: camera health check failed")
        return ToolExecutionResult(
            call_id="resume-web",
            tool_name="robot.system.resume",
            status=ToolExecutionStatus.SUCCEEDED,
            data={"system_latched": False, "motion_latched": False},
        )


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


def test_web_resume_disarms_ai_and_reactivates_direct_control_only_after_success() -> None:
    async def exercise() -> None:
        runtime = _ResumeRuntime()
        controller = WebRobotController(cast(AgentRuntime, runtime))

        result = await controller.resume("lease-test")

        assert result["status"] == "succeeded"
        assert runtime.disarmed == ["web-chat-test", "voice:lease-test"]
        assert runtime.resume_calls == [
            {
                "session_id": "web-control-test",
                "lease_id": "lease-test",
                "confirmed": True,
                "requested_by": "web-controller",
            }
        ]
        assert runtime.armed == [("web-control-test", "lease-test")]

    asyncio.run(exercise())


def test_failed_web_resume_keeps_direct_control_inactive() -> None:
    async def exercise() -> None:
        runtime = _ResumeRuntime(fail=True)
        controller = WebRobotController(cast(AgentRuntime, runtime))

        with pytest.raises(RuntimeError, match="camera health check failed"):
            await controller.resume("lease-test")

        assert runtime.disarmed == ["web-chat-test", "voice:lease-test"]
        assert runtime.armed == []

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


def test_browser_chat_identity_is_stable_across_independent_controller_leases() -> None:
    runtime = _RacingRuntime()
    controller = WebRobotController(cast(AgentRuntime, runtime))
    browser_id = "persistent-browser-identity-0001"

    controller.activate("lease-first", browser_chat_id=browser_id)
    first = controller.chat_session("lease-first")
    controller.activate("lease-second", browser_chat_id=browser_id)
    second = controller.chat_session("lease-second")
    controller.activate("lease-third", browser_chat_id="another-browser-identity-02")
    third = controller.chat_session("lease-third")

    assert first == second
    assert first.startswith("web-chat-")
    assert third != first
    with pytest.raises(ValueError, match="16-128 URL-safe"):
        controller.activate("lease-invalid", browser_chat_id="bad id")


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
        with client.websocket_connect("/ws?browser_chat_id=persistent-browser-0001") as first:
            lease = first.receive_json()
            assert lease["type"] == "lease"
            system_status = first.receive_json()
            assert system_status["type"] == "system_status"
            history = first.receive_json()
            assert history == {"type": "conversation_history", "data": []}
            assert lease["session_id"] == "web-chat-persistent-browser-0001"
            assert runtime.history_sessions == ["web-chat-persistent-browser-0001"]
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


def test_web_poweroff_requires_pairing_second_confirmation_and_active_lease_nonce() -> None:
    runtime = _FakeRuntime()
    controller = _FakeController()
    poweroff = _FakePoweroff()
    leases = ControllerLeaseManager(on_revoke=controller.lease_revoked)
    static = Path(__file__).resolve().parents[1] / "src" / "ninjarobot_pi5_agent" / "web_static"
    app = create_web_app(
        runtime=cast(AgentRuntime, runtime),
        controller=cast(WebRobotController, controller),
        leases=leases,
        static_directory=static,
        poweroff=cast(PoweroffCoordinator, poweroff),
    )

    with TestClient(app) as client:
        with client.websocket_connect("/ws?browser_chat_id=poweroff-browser") as websocket:
            lease = websocket.receive_json()
            assert websocket.receive_json()["type"] == "system_status"
            assert websocket.receive_json()["type"] == "conversation_history"
            websocket.send_json(
                {
                    "type": "poweroff_prepare",
                    "request_id": "prepare-1",
                    "lease_id": lease["lease_id"],
                }
            )
            prepared = websocket.receive_json()
            assert prepared["type"] == "error"
            assert "paired controller" in prepared["error"]

    async def exercise_paired_dispatch() -> None:
        async def send(_payload: dict[str, Any]) -> None:
            return

        nonce = await _dispatch_web_message(
            cast(WebRobotController, controller),
            lease["lease_id"],
            {"type": "poweroff_prepare"},
            send,
            poweroff=cast(PoweroffCoordinator, poweroff),
            poweroff_authorized=True,
        )
        with pytest.raises(PermissionError, match="explicit confirmation"):
            await _dispatch_web_message(
                cast(WebRobotController, controller),
                lease["lease_id"],
                {"type": "poweroff_confirm", "nonce": nonce["nonce"]},
                send,
                poweroff=cast(PoweroffCoordinator, poweroff),
                poweroff_authorized=True,
            )
        confirmed = await _dispatch_web_message(
            cast(WebRobotController, controller),
            lease["lease_id"],
            {
                "type": "poweroff_confirm",
                "nonce": nonce["nonce"],
                "confirmed": True,
            },
            send,
            poweroff=cast(PoweroffCoordinator, poweroff),
            poweroff_authorized=True,
        )
        assert confirmed == {"shutdown_accepted": True}

    asyncio.run(exercise_paired_dispatch())
    assert poweroff.prepared == [lease["lease_id"]]
    assert poweroff.confirmed == [(lease["lease_id"], "nonce-for-active-controller")]


def test_remote_http_and_websocket_require_one_use_pairing_cookie() -> None:
    runtime = _FakeRuntime()
    controller = _FakeController()
    leases = ControllerLeaseManager(on_revoke=controller.lease_revoked)
    pairing = PairingSessionManager(
        pairing_secret=b"p" * 32,
        session_secret=b"s" * 32,
        remote_header_secret="r" * 43,
        pairing_lifetime_seconds=60,
        session_lifetime_seconds=300,
    )
    pairing.set_remote_url("https://robot.example")
    token = pairing.pairing_url().split("#pair=", maxsplit=1)[1]
    static = Path(__file__).resolve().parents[1] / "src" / "ninjarobot_pi5_agent" / "web_static"
    app = create_web_app(
        runtime=cast(AgentRuntime, runtime),
        controller=cast(WebRobotController, controller),
        leases=leases,
        static_directory=static,
        pairing=pairing,
    )

    remote_headers = {"x-ninjarobot-remote": "r" * 43}
    with TestClient(app, base_url="https://robot.example") as client:
        bootstrap = client.get("/", headers=remote_headers)
        assert bootstrap.status_code == 200
        assert "NinjaRobot Pairing" in bootstrap.text
        assert client.get("/assets/app.js", headers=remote_headers).status_code == 401
        with pytest.raises(WebSocketDenialResponse) as denial:
            with client.websocket_connect(
                "/ws",
                headers={"origin": "https://robot.example", **remote_headers},
            ):
                pass
        assert denial.value.status_code == 401
        wrong_origin = client.post(
            "/pair",
            json={"token": token},
            headers={"origin": "https://attacker.example", **remote_headers},
        )
        assert wrong_origin.status_code == 401
        exchanged = client.post(
            "/pair",
            json={"token": token},
            headers={"origin": "https://robot.example", **remote_headers},
        )
        assert exchanged.status_code == 200
        cookie = exchanged.headers["set-cookie"]
        assert "Secure" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Path=/" in cookie
        assert "NINJA ROBOT PI5" in client.get("/", headers=remote_headers).text

        with client.websocket_connect(
            "/ws?browser_chat_id=paired-browser",
            headers={
                "origin": "https://robot.example",
                "host": "robot.example",
                "cookie": f"ninjarobot_session={client.cookies['ninjarobot_session']}",
                **remote_headers,
            },
        ) as websocket:
            assert websocket.receive_json()["type"] == "lease"

    with TestClient(app, base_url="https://robot.example") as replay_client:
        replay = replay_client.post(
            "/pair",
            json={"token": token},
            headers={"origin": "https://robot.example", **remote_headers},
        )
        assert replay.status_code == 401


def test_remote_pairing_gate_denies_unknown_public_host_and_preserves_lan() -> None:
    runtime = _FakeRuntime()
    controller = _FakeController()
    leases = ControllerLeaseManager(on_revoke=controller.lease_revoked)
    pairing = PairingSessionManager(
        pairing_secret=b"p" * 32,
        session_secret=b"s" * 32,
        remote_header_secret="r" * 43,
        pairing_lifetime_seconds=60,
        session_lifetime_seconds=300,
    )
    pairing.set_remote_url("https://robot.example")
    static = Path(__file__).resolve().parents[1] / "src" / "ninjarobot_pi5_agent" / "web_static"
    app = create_web_app(
        runtime=cast(AgentRuntime, runtime),
        controller=cast(WebRobotController, controller),
        leases=leases,
        static_directory=static,
        pairing=pairing,
    )

    with TestClient(app, base_url="https://attacker.example") as unknown:
        assert (
            unknown.get(
                "/",
                headers={"x-ninjarobot-remote": "r" * 43},
            ).status_code
            == 421
        )
    with TestClient(app, base_url="https://192.168.1.20:8443") as local:
        assert local.get("/").status_code == 200
        assert local.get("/assets/app.js").status_code == 200


def test_remote_access_mode_blocks_direct_local_http_until_fallback() -> None:
    runtime = _FakeRuntime()
    controller = _FakeController()
    leases = ControllerLeaseManager(on_revoke=controller.lease_revoked)
    pairing = PairingSessionManager(
        pairing_secret=b"p" * 32,
        session_secret=b"s" * 32,
        remote_header_secret="r" * 43,
        pairing_lifetime_seconds=60,
        session_lifetime_seconds=300,
    )
    access = WebAccessState()
    access.enable_remote()
    static = Path(__file__).resolve().parents[1] / "src" / "ninjarobot_pi5_agent" / "web_static"
    app = create_web_app(
        runtime=cast(AgentRuntime, runtime),
        controller=cast(WebRobotController, controller),
        leases=leases,
        static_directory=static,
        pairing=pairing,
        access_state=access,
    )

    with TestClient(app, base_url="https://ninjarobotpi5.local:8443") as client:
        blocked = client.get("/")
        assert blocked.status_code == 503
        assert "ngrok Remote Access" in blocked.text

        access.enable_local_fallback()
        assert client.get("/").status_code == 200


def test_web_access_state_does_not_silently_restore_local_after_remote_stop() -> None:
    access = WebAccessState()

    assert access.request_local() is True
    assert access.mode == "local"
    access.enable_remote()
    assert access.mode == "remote"
    assert access.local_available is False
    assert access.request_local() is False

    access.disable_remote()
    assert access.mode == "none"
    assert access.local_available is False

    access.enable_remote()
    access.enable_local_fallback()
    assert access.mode == "local_fallback"
    assert access.local_available is True


def test_onboarding_requires_local_pairing_before_websocket_acceptance() -> None:
    runtime = _FakeRuntime()
    controller = _FakeController()
    leases = ControllerLeaseManager(on_revoke=controller.lease_revoked)
    pairing = PairingSessionManager(
        pairing_secret=b"p" * 32,
        session_secret=b"s" * 32,
        remote_header_secret="r" * 43,
        pairing_lifetime_seconds=60,
        session_lifetime_seconds=300,
    )
    pairing.set_local_url("https://127.0.0.1:8443")
    token = pairing.pairing_url().split("#pair=", maxsplit=1)[1]
    connected: list[tuple[bool, bool]] = []

    async def authenticated(remote: bool, paired: bool) -> None:
        connected.append((remote, paired))

    static = Path(__file__).resolve().parents[1] / "src" / "ninjarobot_pi5_agent" / "web_static"
    app = create_web_app(
        runtime=cast(AgentRuntime, runtime),
        controller=cast(WebRobotController, controller),
        leases=leases,
        static_directory=static,
        pairing=pairing,
        require_local_pairing=True,
        on_authenticated_controller=authenticated,
    )

    with TestClient(app, base_url="https://127.0.0.1:8443") as client:
        assert "NinjaRobot Pairing" in client.get("/").text
        assert client.get("/assets/app.js").status_code == 401
        with pytest.raises(WebSocketDenialResponse) as denial:
            with client.websocket_connect(
                "/ws",
                headers={"origin": "https://127.0.0.1:8443"},
            ):
                pass
        assert denial.value.status_code == 401
        exchanged = client.post(
            "/pair",
            json={"token": token},
            headers={"origin": "https://127.0.0.1:8443"},
        )
        assert exchanged.status_code == 200
        assert "NINJA ROBOT PI5" in client.get("/").text
        with client.websocket_connect(
            "/ws?browser_chat_id=paired-local-browser",
            headers={
                "origin": "https://127.0.0.1:8443",
                "host": "127.0.0.1:8443",
                "cookie": f"ninjarobot_session={client.cookies['ninjarobot_session']}",
            },
        ) as websocket:
            lease = websocket.receive_json()
            assert lease["poweroff_authorized"] is True
            assert lease["remote"] is False

    assert connected == [(False, True)]


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
    addresses = {
        str(address)
        for address in server.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value.get_values_for_type(x509.IPAddress)
    }
    hostname = socket.gethostname().rstrip(".")
    assert server.issuer == authority.subject
    assert {hostname, f"{hostname}.local", "localhost"} <= names
    assert {"127.0.0.1", "::1"} <= addresses
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
    english = (static / "i18n" / "en.json").read_text(encoding="utf-8")
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
    assert 'localStorage.getItem("ninjarobotBrowserChatId")' in javascript
    assert "browser_chat_id: state.browserChatId" in javascript
    assert "recognition.stop()" in javascript
    assert "requestFullscreen" in javascript
    assert "webkitRequestFullscreen" in javascript
    assert 'window.matchMedia("(display-mode: standalone)")' in javascript
    assert 'id="usbMicButton"' in html
    assert html.index('id="usbMicButton"') < html.index('id="robotMenu"')
    assert html.index('id="usbRecordButton"') < html.index('id="robotMenu"')
    assert 'id="connectionBadge" class="badge badge-wait" data-i18n=' not in html
    assert 'connectionKey: "connection.offline"' in javascript
    assert "renderConnection();" in javascript
    assert '"voice_enable"' in javascript
    assert '"voice_disable"' in javascript
    assert 'event.data?.kind === "voice_transcript"' in javascript
    assert 'event.data?.kind === "voice_reply"' in javascript
    assert "startController()" in javascript
    assert "motionBadge" not in javascript
    assert "certificate-status" in english
    assert 'if (text === "/resume")' in javascript
    assert 'send("resume", { confirmed: true })' in javascript
    assert 'id="armAiCameraButton"' in html
    assert 'if (text === "/camera")' in javascript
    assert 'send("grant_chat_camera", { confirmed: true })' in javascript
    assert "data.grant_sequence" in javascript
    assert "use /camera again after it succeeds" in english
    assert 'event.event_type === "media"' in javascript
    assert "showCameraPreview(event.data.jpeg_base64)" in javascript
    assert "AI motion remains disarmed" in english
    assert "updateAiMotion(false)" in javascript
    assert 'id="menuButton"' in html
    assert 'id="robotMenu"' in html
    assert 'role="alertdialog"' in html
    assert 'send("poweroff_prepare")' in javascript
    assert 'send("poweroff_confirm", { confirmed: true, nonce })' in javascript
    assert "trapDialogFocus" in javascript
    assert 'localStorage.setItem("ninjarobotLocale"' in javascript
    assert (static / "manifest.webmanifest").is_file()
