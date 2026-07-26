from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from ninjarobot_pi5_ide.testing import DeterministicIDGenerator, FakeClock, FakeIDEClient

from ninjarobot_pi5_ide import ActionRequest


def test_deterministic_helpers_and_fake_ide() -> None:
    clock = FakeClock(datetime(2026, 7, 26, tzinfo=UTC))
    identifiers = DeterministicIDGenerator("action")
    client = FakeIDEClient(clock=clock)
    request = ActionRequest(
        action_id=identifiers.new(),
        capability="system.echo",
        arguments={"message": "hello"},
        requested_by="tester",
        session_id="session-1",
        idempotency_key="key-1",
    )

    result = asyncio.run(client.execute(request))
    clock.advance(timedelta(seconds=1))
    health = asyncio.run(client.health())
    asyncio.run(client.close())
    asyncio.run(client.close())

    assert result.action_id == "action-0001"
    assert result.data == {"simulated": True, "capability": "system.echo"}
    assert health.detail is not None and "no hardware" in health.detail
    assert client.requests == [request]
    assert client.closed is True


def test_fake_clock_and_closed_client_fail_safely() -> None:
    clock = FakeClock()
    with pytest.raises(ValueError, match="cannot move backwards"):
        clock.advance(timedelta(seconds=-1))

    client = FakeIDEClient()
    asyncio.run(client.close())
    with pytest.raises(RuntimeError, match="closed"):
        asyncio.run(client.health())
