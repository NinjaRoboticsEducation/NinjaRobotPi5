from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from ninjarobot_pi5_agent.service_main import _complete_startup_liveliness


def test_startup_liveliness_success_marks_runtime_ready() -> None:
    async def exercise() -> None:
        ide = SimpleNamespace(start_liveliness=AsyncMock(return_value={"status": "succeeded"}))
        runtime = SimpleNamespace(
            complete_startup_liveliness=Mock(),
            fail_startup_liveliness=Mock(),
        )
        events = SimpleNamespace(publish=AsyncMock())

        await _complete_startup_liveliness(ide=ide, runtime=runtime, events=events)

        runtime.complete_startup_liveliness.assert_called_once_with()
        runtime.fail_startup_liveliness.assert_not_called()
        events.publish.assert_awaited_once()

    asyncio.run(exercise())


def test_startup_liveliness_failure_is_logged_and_reported(caplog) -> None:
    async def exercise() -> None:
        failure = RuntimeError("DISPLAY_UNAVAILABLE: display initialization failed")
        ide = SimpleNamespace(start_liveliness=AsyncMock(side_effect=failure))
        runtime = SimpleNamespace(
            complete_startup_liveliness=Mock(),
            fail_startup_liveliness=Mock(),
        )
        events = SimpleNamespace(publish=AsyncMock())

        with caplog.at_level(logging.ERROR):
            await _complete_startup_liveliness(ide=ide, runtime=runtime, events=events)

        runtime.fail_startup_liveliness.assert_called_once_with(failure)
        runtime.complete_startup_liveliness.assert_not_called()
        events.publish.assert_awaited_once()
        assert "DISPLAY_UNAVAILABLE: display initialization failed" in caplog.text

    asyncio.run(exercise())


def test_startup_event_failure_does_not_change_success(caplog) -> None:
    async def exercise() -> None:
        ide = SimpleNamespace(start_liveliness=AsyncMock(return_value={"status": "succeeded"}))
        runtime = SimpleNamespace(
            complete_startup_liveliness=Mock(),
            fail_startup_liveliness=Mock(),
        )
        events = SimpleNamespace(publish=AsyncMock(side_effect=RuntimeError("event failure")))

        with caplog.at_level(logging.ERROR):
            await _complete_startup_liveliness(ide=ide, runtime=runtime, events=events)

        runtime.complete_startup_liveliness.assert_called_once_with()
        runtime.fail_startup_liveliness.assert_not_called()
        assert "Failed to publish the startup completion event" in caplog.text

    asyncio.run(exercise())
