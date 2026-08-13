from __future__ import annotations

import asyncio
from typing import Any

from ninjarobot_pi5_agent.events import AgentEventType, EventBroker
from ninjarobot_pi5_agent.onboarding import OnboardingCoordinator
from ninjarobot_pi5_agent.pairing import PairingSessionManager
from ninjarobot_pi5_agent.release_foundations import ReleaseStatusRegistry


class _IDE:
    def __init__(self, *, fail_qr: bool = False, fail_greeting: bool = False) -> None:
        self.fail_qr = fail_qr
        self.fail_greeting = fail_greeting
        self.urls: list[str] = []
        self.statuses: list[str] = []
        self.clear_calls = 0
        self.greeting_calls = 0

    async def show_onboarding_qr(self, url: str) -> dict[str, Any]:
        if self.fail_qr:
            raise RuntimeError("display write failed")
        self.urls.append(url)
        return {"displayed": True}

    async def show_onboarding_status(self, state: str) -> dict[str, Any]:
        self.statuses.append(state)
        return {"state": state}

    async def prepare_onboarding_greeting(self) -> dict[str, Any]:
        self.clear_calls += 1
        return {"cleared": True}

    async def start_liveliness(self) -> dict[str, Any]:
        self.greeting_calls += 1
        await asyncio.sleep(0)
        if self.fail_greeting:
            raise RuntimeError("greeting failed")
        return {"name": "greeting"}


class _Runtime:
    def __init__(self) -> None:
        self.completed = 0
        self.failed: list[str] = []
        self.disarmed = 0

    def complete_startup_liveliness(self) -> None:
        self.completed += 1

    def fail_startup_liveliness(self, error: BaseException) -> None:
        self.failed.append(str(error))

    def disarm_voice_motion(self, *, lease_id: str | None = None) -> None:
        self.disarmed += 1

    async def stop_and_disarm_motion(
        self,
        session_id: str,
        *,
        lease_id: str | None = None,
        requested_by: str = "local-controller",
        include_voice: bool = False,
    ) -> object:
        self.disarmed += 1
        return {"stopped": True}


class _Remote:
    def __init__(self, pairing: PairingSessionManager) -> None:
        self.pairing = pairing
        self.public_url: str | None = None
        self.state = "connecting"

    def status(self) -> dict[str, object]:
        return {"public_url": self.public_url, "state": self.state}

    def pairing_url(self) -> str:
        return self.pairing.pairing_url()


def _pairing() -> PairingSessionManager:
    return PairingSessionManager(
        pairing_secret=b"p" * 32,
        session_secret=b"s" * 32,
        remote_header_secret="r" * 43,
        pairing_lifetime_seconds=60,
        session_lifetime_seconds=300,
    )


def _status() -> ReleaseStatusRegistry:
    return ReleaseStatusRegistry(
        voice_enabled=False,
        remote_access_enabled=True,
        onboarding_enabled=True,
        shutdown_enabled=False,
    )


async def _wait_until(predicate: Any) -> None:
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0.001)
    raise AssertionError("asynchronous onboarding condition was not reached")


async def _coordinator(
    *,
    ide: _IDE | None = None,
    refresh_interval_seconds: float | None = None,
) -> tuple[OnboardingCoordinator, _IDE, _Runtime, _Remote, EventBroker]:
    pairing = _pairing()
    events = EventBroker()
    selected_ide = ide or _IDE()
    runtime = _Runtime()
    remote = _Remote(pairing)
    coordinator = OnboardingCoordinator(
        enabled=True,
        local_origin="https://127.0.0.1:8443",
        ide=selected_ide,
        runtime=runtime,
        pairing=pairing,
        events=events,
        release_status=_status(),
        remote=remote,
        refresh_interval_seconds=refresh_interval_seconds,
    )
    return coordinator, selected_ide, runtime, remote, events


def test_remote_failure_selects_local_qr_then_recovery_replaces_it() -> None:
    async def exercise() -> None:
        coordinator, ide, _runtime, remote, events = await _coordinator()
        await coordinator.start(remote_enabled=True)
        assert ide.statuses == ["connecting"]

        remote.state = "degraded"
        await events.publish(
            AgentEventType.REMOTE_ACCESS,
            "remote failed",
            data={"kind": "remote_error", "code": "network_unavailable"},
        )
        await _wait_until(lambda: bool(ide.urls))
        assert ide.urls[-1].startswith("https://127.0.0.1:8443/#pair=")

        remote.public_url = "https://robot.example"
        remote.state = "waiting_for_connection"
        remote.pairing.set_remote_url(remote.public_url)
        await events.publish(
            AgentEventType.REMOTE_ACCESS,
            "remote ready",
            data={"kind": "remote_ready"},
        )
        await _wait_until(lambda: ide.urls[-1].startswith("https://robot.example/"))
        assert ide.urls[-1].startswith("https://robot.example/#pair=")
        await coordinator.close()

    asyncio.run(exercise())


def test_simultaneous_paired_connections_run_greeting_and_idle_once() -> None:
    async def exercise() -> None:
        coordinator, ide, runtime, _remote, events = await _coordinator()
        await coordinator.start(remote_enabled=False)

        await asyncio.gather(*(coordinator.controller_connected(paired=True) for _ in range(12)))
        await coordinator.controller_connected(paired=True)

        assert ide.clear_calls == 1
        assert ide.greeting_calls == 1
        assert runtime.completed == 1
        assert runtime.failed == []
        assert runtime.disarmed == 1
        assert [event.data.get("kind") for event in await events.history()].count(
            "onboarding_complete"
        ) == 1
        await coordinator.close()

    asyncio.run(exercise())


def test_waiting_qr_rotates_before_expiry_without_replaying_greeting() -> None:
    async def exercise() -> None:
        coordinator, ide, runtime, _remote, _events = await _coordinator(
            refresh_interval_seconds=0.01
        )
        await coordinator.start(remote_enabled=False)
        first = ide.urls[-1]
        await asyncio.sleep(0.025)
        assert len(ide.urls) >= 2
        assert ide.urls[-1] != first
        assert runtime.completed == 0
        assert ide.greeting_calls == 0
        await coordinator.close()

    asyncio.run(exercise())


def test_unpaired_connection_never_runs_greeting() -> None:
    async def exercise() -> None:
        coordinator, ide, runtime, _remote, _events = await _coordinator()
        await coordinator.start(remote_enabled=False)
        await coordinator.controller_connected(paired=False)
        assert ide.greeting_calls == 0
        assert runtime.completed == 0
        await coordinator.close()

    asyncio.run(exercise())


def test_qr_or_greeting_failure_is_terminal_disarmed_and_shows_error() -> None:
    async def exercise() -> None:
        qr_coordinator, qr_ide, qr_runtime, _remote, _events = await _coordinator(
            ide=_IDE(fail_qr=True)
        )
        await asyncio.wait_for(qr_coordinator.start(remote_enabled=False), timeout=1.0)
        await qr_coordinator.controller_connected(paired=True)
        assert qr_ide.greeting_calls == 0
        assert qr_ide.statuses == ["error"]
        assert qr_runtime.disarmed == 2
        assert qr_runtime.failed == ["display write failed"]
        await asyncio.wait_for(qr_coordinator.close(), timeout=1.0)

        greeting_coordinator, greeting_ide, greeting_runtime, _remote, _events = await _coordinator(
            ide=_IDE(fail_greeting=True)
        )
        await asyncio.wait_for(greeting_coordinator.start(remote_enabled=False), timeout=1.0)
        await asyncio.wait_for(greeting_coordinator.controller_connected(paired=True), timeout=1.0)
        assert greeting_ide.greeting_calls == 1
        assert greeting_ide.statuses == ["error"]
        assert greeting_runtime.completed == 0
        assert greeting_runtime.failed == ["greeting failed"]
        assert greeting_runtime.disarmed == 3
        await asyncio.wait_for(greeting_coordinator.close(), timeout=1.0)

    asyncio.run(exercise())
