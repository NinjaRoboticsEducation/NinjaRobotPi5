"""Remote tunnel lifecycle, recovery, persistence, and redaction tests."""

from __future__ import annotations

import asyncio
import os
import sys
from collections import deque
from pathlib import Path
from types import ModuleType, SimpleNamespace

from ninjarobot_pi5_agent.events import EventBroker
from ninjarobot_pi5_agent.pairing import PairingSessionManager
from ninjarobot_pi5_agent.release_foundations import ReleaseStatusRegistry
from ninjarobot_pi5_agent.remote_access import (
    PyngrokTunnelBackend,
    RemoteAccessError,
    RemoteAccessService,
    _ensure_private_ngrok_config,
    install_ngrok_binary,
    persist_remote_access_enabled,
)
from ninjarobot_pi5_agent.secrets import SecretStore

from ninjarobot_pi5_ide import RemoteAccessConfig, load_robot_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"
REMOTE_MARKER = "r" * 43


class FakeBackend:
    def __init__(self, results: list[str | Exception]) -> None:
        self.results = deque(results)
        self.connect_calls = 0
        self.health = True
        self.closed: list[str | None] = []

    async def connect(self) -> str:
        self.connect_calls += 1
        result = self.results.popleft() if self.results else "https://robot.example"
        if isinstance(result, Exception):
            raise result
        return result

    async def healthy(self, public_url: str) -> bool:
        assert public_url.startswith("https://")
        return self.health

    async def close(self, public_url: str | None) -> None:
        self.closed.append(public_url)


def pairing() -> PairingSessionManager:
    return PairingSessionManager(
        pairing_secret=b"p" * 32,
        session_secret=b"s" * 32,
        remote_header_secret=REMOTE_MARKER,
        pairing_lifetime_seconds=60,
        session_lifetime_seconds=300,
    )


def fast_config(*, enabled: bool = False) -> RemoteAccessConfig:
    return RemoteAccessConfig(enabled=enabled).model_copy(
        update={
            "health_interval_seconds": 0.01,
            "retry_initial_seconds": 0.01,
            "retry_max_seconds": 0.02,
            "connect_timeout_seconds": 0.1,
            "retry_limit": 1,
        }
    )


def build_service(backend: FakeBackend, *, enabled: bool = False):
    events = EventBroker()
    release = ReleaseStatusRegistry(
        voice_enabled=False,
        remote_access_enabled=enabled,
        onboarding_enabled=False,
        shutdown_enabled=False,
    )
    persisted: list[bool] = []
    web_starts = 0
    access_transitions: list[str] = []

    async def start_web() -> dict[str, object]:
        nonlocal web_starts
        web_starts += 1
        return {"running": True}

    async def persist(value: bool) -> None:
        persisted.append(value)

    async def remote_ready() -> dict[str, object]:
        access_transitions.append("remote")
        return {"access_mode": "remote"}

    async def remote_unavailable() -> dict[str, object]:
        access_transitions.append("local_fallback")
        return {"access_mode": "local_fallback"}

    service = RemoteAccessService(
        backend=backend,
        pairing=pairing(),
        events=events,
        release_status=release,
        config=fast_config(enabled=enabled),
        start_web=start_web,
        persist_enabled=persist,
        remote_ready=remote_ready,
        remote_unavailable=remote_unavailable,
    )
    return service, events, release, persisted, lambda: web_starts, access_transitions


def test_activate_waits_for_web_issues_pairing_and_closes_exact_tunnel() -> None:
    async def scenario() -> None:
        backend = FakeBackend(["https://robot.example"])
        service, events, release, persisted, web_starts, transitions = build_service(backend)

        status = await service.activate()

        assert web_starts() == 1
        assert persisted == [True]
        assert status["public_url"] == "https://robot.example"
        assert "#pair=" in service.pairing_url()
        assert release.status()["remote_access"]["state"] == "waiting_for_connection"
        assert transitions == ["remote"]
        assert all("#pair=" not in event.model_dump_json() for event in await events.history())

        await service.deactivate()
        assert backend.closed[-1] == "https://robot.example"
        assert persisted == [True, False]
        assert service.status()["public_url"] is None

    asyncio.run(scenario())


def test_failure_is_sanitized_and_background_recovery_keeps_local_service_alive() -> None:
    async def scenario() -> None:
        raw = "secret-provider-response-body"
        backend = FakeBackend(
            [
                RuntimeError(raw),
                "https://recovered.example",
            ]
        )
        service, events, _release, _persisted, _web_starts, transitions = build_service(backend)

        first = await service.activate()
        assert first["detail"] == "tunnel_unavailable"
        for _ in range(100):
            if service.status()["public_url"] == "https://recovered.example":
                break
            await asyncio.sleep(0.01)

        assert service.status()["public_url"] == "https://recovered.example"
        assert transitions[:2] == ["local_fallback", "remote"]
        serialized = " ".join(event.model_dump_json() for event in await events.history())
        assert raw not in serialized
        assert "local agent and web control remain ready" in serialized
        await service.deactivate()

    asyncio.run(scenario())


def test_private_ngrok_config_contains_no_token_and_rejects_unsafe_mode(
    tmp_path: Path,
) -> None:
    config = tmp_path / "private" / "ngrok.yml"
    _ensure_private_ngrok_config(config)

    assert config.read_text(encoding="utf-8") == (
        'version: "2"\nupdate_check: false\nweb_addr: 127.0.0.1:4041\n'
    )
    assert os.stat(config).st_mode & 0o777 == 0o600
    assert "token" not in config.read_text(encoding="utf-8").casefold()

    config.chmod(0o644)
    try:
        _ensure_private_ngrok_config(config)
    except RemoteAccessError as exc:
        assert exc.code == "config_path_unsafe"
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("public ngrok config permissions were accepted")

    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    try:
        _ensure_private_ngrok_config(linked / "ngrok.yml")
    except RemoteAccessError as exc:
        assert exc.code == "config_path_unsafe"
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("symbolic-link ngrok config directory was accepted")


def test_pyngrok_backend_requires_installed_binary_and_preserves_upstream_tls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / "bin" / "ngrok"
    executable.parent.mkdir()
    executable.write_bytes(b"fake executable")
    executable.chmod(0o700)
    ca = tmp_path / "local-ca.pem"
    ca.write_text("fake CA", encoding="utf-8")
    private_config = tmp_path / "ngrok.yml"
    settings = RemoteAccessConfig().model_copy(
        update={
            "executable": str(executable),
            "config_file": str(private_config),
        }
    )
    secrets = SecretStore(tmp_path / "secrets.env")
    token = "private-ngrok-token"
    secrets.set("NGROK_AUTHTOKEN", token)
    captured: dict[str, object] = {}

    class FakeConfig:
        def __init__(self, **kwargs) -> None:
            captured["config"] = kwargs
            self.ngrok_path = kwargs["ngrok_path"]

    class FakeNgrok:
        @staticmethod
        def connect(**kwargs):
            captured["connect"] = kwargs
            return SimpleNamespace(public_url="https://robot.example")

        @staticmethod
        def disconnect(public_url: str, **kwargs) -> None:
            captured["disconnect"] = (public_url, kwargs)

        @staticmethod
        def kill(**kwargs) -> None:
            captured["kill"] = kwargs

    module = ModuleType("pyngrok")
    module.conf = SimpleNamespace(PyngrokConfig=FakeConfig)
    module.ngrok = FakeNgrok
    monkeypatch.setitem(sys.modules, "pyngrok", module)
    backend = PyngrokTunnelBackend(
        config=settings,
        secrets=secrets,
        local_ca_certificate=ca,
        remote_header_secret=REMOTE_MARKER,
    )

    public_url = asyncio.run(backend.connect())
    asyncio.run(backend.close(public_url))

    config_arguments = captured["config"]
    connect_arguments = captured["connect"]
    assert config_arguments["auth_token"] is None
    assert connect_arguments["addr"] == "https://127.0.0.1:8443"
    assert connect_arguments["bind_tls"] is True
    assert connect_arguments["upstream_tls_verify"] is True
    assert connect_arguments["upstream_tls_verify_cas"] == str(ca)
    assert "request_header_remove" not in connect_arguments
    assert "request_header_add" not in connect_arguments
    assert connect_arguments["traffic_policy"] == {
        "on_http_request": [
            {
                "actions": [
                    {
                        "type": "remove-headers",
                        "config": {"headers": ["x-ninjarobot-remote"]},
                    },
                    {
                        "type": "add-headers",
                        "config": {"headers": {"x-ninjarobot-remote": REMOTE_MARKER}},
                    },
                ]
            }
        ]
    }
    assert token not in private_config.read_text(encoding="utf-8")
    assert captured["disconnect"][0] == "https://robot.example"
    assert "pyngrok_config" in captured["kill"]


def test_permanent_configuration_failure_does_not_retry_forever() -> None:
    async def scenario() -> None:
        backend = FakeBackend([RemoteAccessError("configuration_invalid")])
        service, _events, _release, _persisted, _web_starts, _transitions = build_service(backend)

        status = await service.activate()
        await asyncio.sleep(0.05)

        assert status["state"] == "failed"
        assert status["detail"] == "configuration_invalid"
        assert backend.connect_calls == 1
        await service.deactivate()

    asyncio.run(scenario())


def test_ngrok_installer_reuses_valid_v3_binary(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "bin" / "ngrok"
    destination.parent.mkdir()
    destination.write_text("#!/bin/sh\necho 'ngrok version 3.39.11'\n", encoding="utf-8")
    destination.chmod(0o700)

    def unexpected_install(*_args, **_kwargs) -> None:
        raise AssertionError("a valid installed ngrok binary was replaced")

    from pyngrok import installer

    monkeypatch.setattr(installer, "install_ngrok", unexpected_install)

    assert install_ngrok_binary(destination) == destination


def test_ngrok_installer_replaces_invalid_binary_atomically(
    tmp_path: Path,
    monkeypatch,
) -> None:
    destination = tmp_path / "bin" / "ngrok"
    destination.parent.mkdir()
    destination.write_text("invalid", encoding="utf-8")
    destination.chmod(0o700)

    def install(path: str, *, ngrok_version: str) -> None:
        assert ngrok_version == "3"
        installed = Path(path)
        installed.write_text("#!/bin/sh\necho 'ngrok version 3.40.0'\n", encoding="utf-8")
        installed.chmod(0o700)

    from pyngrok import installer

    monkeypatch.setattr(installer, "install_ngrok", install)

    assert install_ngrok_binary(destination) == destination
    assert "3.40.0" in destination.read_text(encoding="utf-8")


def test_remote_enable_persistence_changes_only_validated_switch(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_bytes(EXAMPLE.read_bytes())
    before = load_robot_config(config_path)

    asyncio.run(persist_remote_access_enabled(config_path, True))
    enabled = load_robot_config(config_path)
    asyncio.run(persist_remote_access_enabled(config_path, False))
    disabled = load_robot_config(config_path)

    assert enabled.remote_access.enabled is True
    assert enabled.onboarding.enabled is True
    assert disabled.remote_access.enabled is False
    assert disabled.onboarding.enabled is False
    assert enabled.hardware == before.hardware
    assert enabled.providers == before.providers
