"""Guided setup registers through fake IPC; never opens Google or starts hardware."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from ninjarobot_pi5_agent import agent_cli


@pytest.mark.parametrize("explicit", [False, True])
def test_calendar_cli_registers_discovered_or_explicit_calendar(monkeypatch, explicit):
    from ninjarobot_pi5_agent import calendar_oauth

    requests = []

    class Client:
        def __init__(self, *args):
            pass

        async def request(self, payload):
            requests.append(payload)
            return {"data": {"owner_user_id": "owner"}}

    async def service_request(arguments, payload):
        requests.append(payload)
        return 0

    credential = dict(client_id="fake", client_secret="fake", refresh_token="fake", scope="fake")
    if not explicit:
        credential.update(calendar_id="primary@example.org", account_label="Primary")
    auth = AsyncMock(return_value=credential)
    monkeypatch.setattr(calendar_oauth, "authorize", auth)
    monkeypatch.setattr(agent_cli, "AgentIPCClient", Client)
    monkeypatch.setattr(agent_cli, "_service_request", service_request)
    args = ["calendar-connect", "--write"]
    if explicit:
        args += ["--calendar-id", "selected@example.org", "--account-label", "Selected"]
    assert asyncio.run(agent_cli._run(agent_cli.build_parser().parse_args(args))) == 0
    sent = requests[-1]["data"]["arguments"]
    assert sent["expected_user_id"] == "owner"
    assert sent["calendar_id"] == ("selected@example.org" if explicit else "primary@example.org")
    assert sent["write"] is True
    assert auth.call_args.kwargs["discover_primary"] is not explicit
    assert "calendar_id" not in sent["credential"]


def test_stopped_agent_does_not_start_oauth(monkeypatch):
    from ninjarobot_pi5_agent import calendar_oauth

    class Client:
        def __init__(self, *args):
            pass

        async def request(self, payload):
            raise OSError("offline")

    auth = AsyncMock()
    monkeypatch.setattr(calendar_oauth, "authorize", auth)
    monkeypatch.setattr(agent_cli, "AgentIPCClient", Client)
    with pytest.raises(ValueError, match="Start the NinjaRobot Agent"):
        asyncio.run(agent_cli._run(agent_cli.build_parser().parse_args(["calendar-connect"])))
    auth.assert_not_awaited()


@pytest.mark.parametrize(
    "flags,expected_write", [([], True), (["--read-only"], False), (["--write"], True)]
)
def test_compatibility_wrapper_selects_explicit_mode(monkeypatch, flags, expected_write):
    import runpy
    from pathlib import Path
    from unittest.mock import Mock

    entry = Path(__file__).resolve().parents[2] / "scripts/authorize_google_calendar.py"
    module = runpy.run_path(str(entry))
    execute = Mock()
    monkeypatch.setattr("os.execv", execute)
    monkeypatch.setattr("sys.argv", [str(entry), *flags])
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    module["main"]()
    arguments = execute.call_args.args[1]
    assert ("--write" in arguments) is expected_write
    assert "--read-only" not in arguments
    assert arguments[1] == "calendar-connect"
