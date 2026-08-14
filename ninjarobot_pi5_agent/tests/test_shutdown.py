from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from ninjarobot_pi5_agent.events import EventBroker
from ninjarobot_pi5_agent.release_foundations import ReleaseStatusRegistry
from ninjarobot_pi5_agent.shutdown import PoweroffCoordinator


class _Runtime:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    async def disable_voice_input(self) -> dict[str, object]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("voice cleanup failed")
        return {"enabled": False}


class _Controller:
    def __init__(self, *, fail: bool = False) -> None:
        self.leases: list[str] = []
        self.fail = fail

    async def emergency_stop(self, lease_id: str) -> dict[str, object]:
        self.leases.append(lease_id)
        if self.fail:
            raise RuntimeError("hardware cleanup failed")
        return {"stopped": True}


def _release_status(*, enabled: bool = True) -> ReleaseStatusRegistry:
    return ReleaseStatusRegistry(
        voice_enabled=False,
        remote_access_enabled=False,
        onboarding_enabled=False,
        shutdown_enabled=enabled,
    )


def test_poweroff_nonce_is_lease_bound_one_use_and_requests_orderly_stop() -> None:
    async def exercise() -> None:
        now = [10.0]
        stopped = asyncio.Event()
        runtime = _Runtime()
        controller = _Controller()
        events = EventBroker()
        status = _release_status()
        coordinator = PoweroffCoordinator(
            enabled=True,
            helper_path="/usr/libexec/ninjarobot-poweroff",
            runtime=runtime,
            controller=controller,
            events=events,
            release_status=status,
            request_service_stop=stopped.set,
            clock=lambda: now[0],
            helper_probe=lambda _path: (True, None),
        )

        issued = await coordinator.issue_nonce("lease-owner")
        with pytest.raises(PermissionError, match="invalid or expired"):
            await coordinator.confirm("lease-other", str(issued["nonce"]))
        result = await coordinator.confirm("lease-owner", str(issued["nonce"]))
        with pytest.raises(PermissionError, match="invalid or expired"):
            await coordinator.confirm("lease-owner", str(issued["nonce"]))
        await asyncio.wait_for(stopped.wait(), timeout=1.0)

        assert result == {"shutdown_accepted": True, "cleanup_degraded": False}
        assert controller.leases == ["lease-owner"]
        assert runtime.calls == 1
        assert coordinator.requested is True
        assert status.status()["shutdown"]["state"] == "shutting_down"
        assert [event.data["kind"] for event in await events.history()] == ["poweroff_confirmed"]

    asyncio.run(exercise())


def test_poweroff_nonce_expires_and_disabled_coordinator_rejects_requests() -> None:
    async def exercise() -> None:
        now = [5.0]
        disabled = PoweroffCoordinator(
            enabled=False,
            helper_path="/usr/libexec/ninjarobot-poweroff",
            runtime=_Runtime(),
            controller=_Controller(),
            events=EventBroker(),
            release_status=_release_status(enabled=False),
            request_service_stop=lambda: None,
            clock=lambda: now[0],
            helper_probe=lambda _path: (True, None),
        )
        with pytest.raises(PermissionError, match="disabled"):
            await disabled.issue_nonce("lease-owner")

        enabled = PoweroffCoordinator(
            enabled=True,
            helper_path="/usr/libexec/ninjarobot-poweroff",
            runtime=_Runtime(),
            controller=_Controller(),
            events=EventBroker(),
            release_status=_release_status(),
            request_service_stop=lambda: None,
            clock=lambda: now[0],
            helper_probe=lambda _path: (True, None),
        )
        issued = await enabled.issue_nonce("lease-owner")
        now[0] += 31.0
        with pytest.raises(PermissionError, match="invalid or expired"):
            await enabled.confirm("lease-owner", str(issued["nonce"]))

    asyncio.run(exercise())


def test_poweroff_continues_after_bounded_module_cleanup_failures() -> None:
    async def exercise() -> None:
        stopped = asyncio.Event()
        events = EventBroker()
        coordinator = PoweroffCoordinator(
            enabled=True,
            helper_path="/usr/libexec/ninjarobot-poweroff",
            runtime=_Runtime(fail=True),
            controller=_Controller(fail=True),
            events=events,
            release_status=_release_status(),
            request_service_stop=stopped.set,
            helper_probe=lambda _path: (True, None),
        )
        issued = await coordinator.issue_nonce("lease-owner")

        result = await coordinator.confirm("lease-owner", str(issued["nonce"]))
        await asyncio.wait_for(stopped.wait(), timeout=1.0)

        assert result == {"shutdown_accepted": True, "cleanup_degraded": True}
        history = await events.history()
        assert history[-1].data == {
            "kind": "poweroff_cleanup_degraded",
            "failures": ["hardware_stop_failed", "voice_stop_failed"],
        }

    asyncio.run(exercise())


def test_poweroff_helper_uses_only_fixed_argv_after_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exercise() -> None:
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append((arguments, kwargs))
            return subprocess.CompletedProcess(arguments, 0, "", "")

        monkeypatch.setattr(Path, "is_file", lambda path: str(path) == approved)
        monkeypatch.setattr(Path, "is_symlink", lambda _path: False)
        monkeypatch.setattr("ninjarobot_pi5_agent.shutdown.subprocess.run", run)
        coordinator = PoweroffCoordinator(
            enabled=True,
            helper_path=approved,
            runtime=_Runtime(),
            controller=_Controller(),
            events=EventBroker(),
            release_status=_release_status(),
            request_service_stop=lambda: None,
            helper_probe=lambda _path: (True, None),
        )
        issued = await coordinator.issue_nonce("lease-owner")
        await coordinator.confirm("lease-owner", str(issued["nonce"]))
        await coordinator.invoke_helper()

        assert calls == [
            (
                ["/usr/bin/sudo", "-n", approved],
                {
                    "check": False,
                    "capture_output": True,
                    "text": True,
                    "timeout": 15.0,
                },
            )
        ]

    approved = "/usr/libexec/ninjarobot-poweroff"
    asyncio.run(exercise())


def test_poweroff_rejects_before_nonce_when_privileged_installation_is_missing() -> None:
    async def exercise() -> None:
        stopped = asyncio.Event()
        coordinator = PoweroffCoordinator(
            enabled=True,
            helper_path="/usr/libexec/ninjarobot-poweroff",
            runtime=_Runtime(),
            controller=_Controller(),
            events=EventBroker(),
            release_status=_release_status(),
            request_service_stop=stopped.set,
            helper_probe=lambda _path: (False, "power-off helper file is missing"),
        )

        with pytest.raises(PermissionError, match="install or repair"):
            await coordinator.issue_nonce("lease-owner")

        assert coordinator.requested is False
        assert stopped.is_set() is False

    asyncio.run(exercise())


def test_all_web_locales_have_identical_keys_and_cover_markup_and_script() -> None:
    static = Path(__file__).resolve().parents[1] / "src" / "ninjarobot_pi5_agent" / "web_static"
    locales = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((static / "i18n").glob("*.json"))
    }
    assert set(locales) == {"en", "ja", "zh-TW", "zh-CN"}
    english_keys = set(locales["en"])
    assert all(set(messages) == english_keys for messages in locales.values())
    assert all(
        all(str(value).strip() for value in messages.values()) for messages in locales.values()
    )

    html = (static / "index.html").read_text(encoding="utf-8")
    javascript = (static / "app.js").read_text(encoding="utf-8")
    markup_keys = set(re.findall(r'data-i18n(?:-placeholder|-aria|-alt)?="([A-Za-z0-9.]+)"', html))
    script_keys = set(re.findall(r'\bt\("([A-Za-z0-9.]+)"', javascript))
    assert markup_keys | script_keys <= english_keys
