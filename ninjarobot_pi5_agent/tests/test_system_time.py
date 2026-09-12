"""Fresh host time reaches model context and read-only controls without OS writes."""

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from ninjarobot_pi5_agent.models import ToolCall, ToolExecutionStatus, ToolInvocation
from ninjarobot_pi5_agent.prompts import PromptComposer
from ninjarobot_pi5_agent.runtime import AgentRuntime
from ninjarobot_pi5_agent.system_time_tool import SystemTimeProvider
from ninjarobot_pi5_agent.task_models import exact_due_time
from ninjarobot_pi5_agent.tools import CancellationToken

from ninjarobot_pi5_agent import system_time


def test_snapshot_tracks_clock_and_os_timezone_changes(monkeypatch, tmp_path):
    # Real timezone rules, synthetic dates. Never change the host timezone/clock.
    localtime = tmp_path / "localtime"
    localtime.symlink_to("/usr/share/zoneinfo/Asia/Tokyo")
    monkeypatch.setattr(system_time, "Path", lambda _: localtime)
    now = [datetime(2026, 9, 12, 15, 1, tzinfo=UTC)]
    monkeypatch.setattr(system_time, "datetime", SimpleNamespace(now=lambda _: now[0]))
    monkeypatch.setenv("TZ", "America/New_York")
    first = system_time.system_time_snapshot()
    assert first["local"] == "2026-09-13T00:01:00+09:00"
    assert first["timezone"] == "Asia/Tokyo"
    assert first["date"] == "2026-09-13"
    now[0] = datetime(2026, 9, 13, 0, 2, tzinfo=UTC)
    localtime.unlink()
    localtime.symlink_to("/usr/share/zoneinfo/America/New_York")
    second = system_time.system_time_snapshot()
    assert second["local"] == "2026-09-12T20:02:00-04:00"
    assert second["timezone"] == "America/New_York"
    assert second["utc"] != first["utc"]
    localtime.unlink()
    missing = system_time.system_time_snapshot()
    assert missing["timezone"] is None
    assert missing["local"] == missing["utc"]
    assert "unavailable" in missing["timezone_status"]


def test_prompt_refreshes_time_without_mutating_or_trusting_cached_state(monkeypatch):
    values = iter([{"utc": "first"}, {"utc": "second"}])
    monkeypatch.setattr("ninjarobot_pi5_agent.prompts.system_time_snapshot", lambda: next(values))
    composer = PromptComposer()
    state = {"system_time": {"utc": "stale"}, "execution_mode": "simulation"}
    first = composer.compose(runtime_state=state, conversation=())
    second = composer.compose(runtime_state=state, conversation=())
    assert '"utc": "first"' in first[2].content
    assert '"utc": "second"' in second[2].content
    assert state["system_time"] == {"utc": "stale"}
    assert "does not grant task confirmation" in second[2].content


def test_clock_tool_is_fresh_cancellable_and_rejects_mutation_arguments(monkeypatch):
    async def exercise():
        clock = Mock(side_effect=[{"utc": "first"}, {"utc": "second"}])
        monkeypatch.setattr("ninjarobot_pi5_agent.system_time_tool.system_time_snapshot", clock)
        provider = SystemTimeProvider()
        invocation = ToolInvocation(
            session_id="clock", call=ToolCall(call_id="now", name="system.time.get", arguments={})
        )
        for value in ("first", "second"):
            result = await provider.call(invocation, CancellationToken())
            assert result.data == {"utc": value}
            assert result.status is ToolExecutionStatus.SUCCEEDED
        bad = invocation.model_copy(
            update={
                "call": invocation.call.model_copy(update={"arguments": {"set_time": "tomorrow"}})
            }
        )
        assert (await provider.call(bad, CancellationToken())).definitely_not_executed
        token = CancellationToken()
        token.cancel()
        assert (await provider.call(invocation, token)).status is ToolExecutionStatus.CANCELLED
        assert clock.call_count == 2

    asyncio.run(exercise())


def test_time_command_reads_without_model_or_scheduler(monkeypatch):
    async def exercise():
        runtime = Mock(spec=AgentRuntime)
        runtime._identity_reply = AsyncMock(return_value="clock reply")
        monkeypatch.setattr(
            system_time,
            "system_time_snapshot",
            lambda: {
                "local": "2026-09-12T19:00:00+09:00",
                "utc": "2026-09-12T10:00:00+00:00",
                "timezone": "Asia/Tokyo",
            },
        )
        await AgentRuntime.chat(runtime, session_id="clock", text="/time")
        notice = runtime._identity_reply.call_args.args[1]
        assert "19:00:00+09:00" in notice and "Asia/Tokyo" in notice
        runtime._chat_with_task.assert_not_called()
        runtime._identity_reply.assert_awaited_once()

    asyncio.run(exercise())


def test_fresh_clock_reminder_offset_matches_existing_scheduler(monkeypatch, tmp_path):
    localtime = tmp_path / "localtime"
    localtime.symlink_to("/usr/share/zoneinfo/Asia/Tokyo")
    monkeypatch.setattr(system_time, "Path", lambda _: localtime)
    now = datetime(2026, 9, 12, 14, 59, tzinfo=UTC)
    monkeypatch.setattr(system_time, "datetime", SimpleNamespace(now=lambda _: now))
    clock = system_time.system_time_snapshot()
    due = exact_due_time("2026-09-13T00:01:00+09:00", clock["timezone"], now)
    assert (due - now).total_seconds() == 120
    assert len(json.dumps(clock)) < 1500


def test_dst_offset_is_recomputed_from_current_instant(monkeypatch, tmp_path):
    localtime = tmp_path / "localtime"
    localtime.symlink_to("/usr/share/zoneinfo/America/New_York")
    monkeypatch.setattr(system_time, "Path", lambda _: localtime)
    moments = iter(
        [
            datetime(2026, 11, 1, 5, 59, tzinfo=UTC),
            datetime(2026, 11, 1, 6, 1, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(system_time, "datetime", SimpleNamespace(now=lambda _: next(moments)))
    before = system_time.system_time_snapshot()
    after = system_time.system_time_snapshot()
    assert before["local"] == "2026-11-01T01:59:00-04:00"
    assert after["local"] == "2026-11-01T01:01:00-05:00"
    assert after["unix_seconds"] - before["unix_seconds"] == 120
