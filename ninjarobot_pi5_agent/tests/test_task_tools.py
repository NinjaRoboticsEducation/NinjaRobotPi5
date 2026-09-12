from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from ninjarobot_pi5_agent.models import ToolCall, ToolExecutionStatus, ToolInvocation
from ninjarobot_pi5_agent.persistence import ConversationStore
from ninjarobot_pi5_agent.task_service import TaskService
from ninjarobot_pi5_agent.task_tools import TaskToolProvider
from ninjarobot_pi5_agent.tools import CancellationToken


def test_model_can_preview_but_cannot_confirm_or_choose_another_scope(tmp_path):
    async def exercise():
        store = ConversationStore(tmp_path / "agent.sqlite3")
        await store.start()
        delivered = []

        async def notify(task):
            delivered.append(task.task_id)
            return True, "Inbox saved"

        async def scope(session):
            return f"session:{session}", None

        tasks = TaskService(store.path, notify)
        await tasks.start(background=False)
        provider = TaskToolProvider(tasks, scope)
        await provider.start()
        try:
            definitions = await provider.list_tools()
            assert {tool.name for tool in definitions} == {"tasks.list", "tasks.reminder.preview"}
            arguments = {
                "title": "Tea",
                "timezone": "Asia/Tokyo",
                "due_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            }
            invocation = ToolInvocation(
                session_id="first",
                call=ToolCall(
                    call_id="preview",
                    name="tasks.reminder.preview",
                    arguments=arguments,
                ),
            )
            result = await provider.call(invocation, CancellationToken())
            assert result.status is ToolExecutionStatus.FAILED  # mismatched zone and offset
            assert await tasks.list("session:first") == ()
            arguments["timezone"] = "UTC"
            invocation = invocation.model_copy(
                update={"call": invocation.call.model_copy(update={"arguments": arguments})}
            )
            result = await provider.call(invocation, CancellationToken())
            assert result.status is ToolExecutionStatus.SUCCEEDED
            assert result.data["task"]["status"] == "draft"
            assert "Not scheduled yet" in result.data["review"]
            assert await tasks.list("session:second") == ()
            assert not await tasks.tick()
            assert delivered == []
            invalid = invocation.model_copy(
                update={
                    "call": invocation.call.model_copy(
                        update={"arguments": {**arguments, "scope": "session:second"}}
                    )
                }
            )
            assert (
                await provider.call(invalid, CancellationToken())
            ).status is ToolExecutionStatus.FAILED
            cancelled = CancellationToken()
            cancelled.cancel()
            assert (
                await provider.call(invocation, cancelled)
            ).status is ToolExecutionStatus.CANCELLED
            assert len(await tasks.list("session:first")) == 1
        finally:
            await provider.close()
            await tasks.close()
            await store.close()

    asyncio.run(exercise())


def test_task_pages_are_owned_compact_and_complete(tmp_path):
    import json

    from ninjarobot_pi5_agent.models import MessageRole, ModelMessage
    from ninjarobot_pi5_agent.tool_messages import tool_message_content

    async def exercise():
        store = ConversationStore(tmp_path / "pages.sqlite3")
        await store.start()

        async def notify(task):
            return True, "saved"

        async def scope(session):
            return f"session:{session}", None

        tasks = TaskService(store.path, notify)
        await tasks.start(background=False)
        provider = TaskToolProvider(tasks, scope)
        try:
            owned = set()
            for index in range(45):
                task = await tasks.preview(
                    scope="session:first",
                    user_id=None,
                    session_id="first",
                    title=f"{index}: 日本語 中文 " + "x" * 140,
                    due_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    timezone="UTC",
                )
                owned.add(task.task_id)
            other = await tasks.preview(
                scope="session:second",
                user_id=None,
                session_id="second",
                title="Private",
                due_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                timezone="UTC",
            )
            after = ""
            seen = []
            while True:
                result = await provider.call(
                    ToolInvocation(
                        session_id="first",
                        call=ToolCall(
                            call_id="page",
                            name="tasks.list",
                            arguments={"limit": 20, "after": after, "kind": "reminder"},
                        ),
                    ),
                    CancellationToken(),
                )
                content = tool_message_content(result)
                ModelMessage(
                    role=MessageRole.TOOL, content=content, name="tasks.list", tool_call_id="page"
                )
                page = json.loads(content)["data"]
                assert page["total"] == 45
                assert "record_json" not in content and "owner_scope" not in content
                assert "steps" not in content and "limits" not in content
                assert other.task_id not in content
                seen.extend(item["task_id"] for item in page["tasks"])
                assert all(item["title"] for item in page["tasks"])
                if not page["has_more"]:
                    assert page["next_after"] is None
                    break
                after = page["next_after"]
            assert len(seen) == len(set(seen)) == 45
            assert set(seen) == owned
            scheduled = await tasks.model_page("session:first", status="scheduled")
            assert scheduled["tasks"] == []  # drafts are not scheduled
            assert scheduled["total"] == 0
            empty = await tasks.model_page("session:unknown")
            assert empty["tasks"] == [] and not empty["has_more"]
        finally:
            await tasks.close()
            await store.close()

    asyncio.run(exercise())


def test_oversized_tool_data_preserves_execution_outcome():
    import json

    from ninjarobot_pi5_agent.models import MessageRole, ModelMessage, ToolExecutionResult
    from ninjarobot_pi5_agent.tool_messages import tool_message_content

    for status in ToolExecutionStatus:
        result = ToolExecutionResult(
            call_id="large",
            tool_name="example.read",
            status=status,
            data={"records": "日本語" * 20000},
            error=None if status is ToolExecutionStatus.SUCCEEDED else "Failure detail",
        )
        content = tool_message_content(result)
        ModelMessage(
            role=MessageRole.TOOL, content=content, name="example.read", tool_call_id="large"
        )
        record = json.loads(content)
        assert record["data"]["omitted"] is True
        assert record["status"] == status.value
        assert record["error"] == result.error
        assert record["definitely_not_executed"] == result.definitely_not_executed
        assert record["retry_safety"] == result.retry_safety.value
        assert result.data["records"] == "日本語" * 20000


def test_interrupted_tool_history_is_closed_without_replaying_or_rewriting():
    from ninjarobot_pi5_agent.models import MessageRole, ModelMessage
    from ninjarobot_pi5_agent.tool_messages import repair_tool_history

    call = ModelMessage(
        role=MessageRole.ASSISTANT,
        content="",
        tool_calls=(ToolCall(call_id="interrupted", name="robot.example", arguments={}),),
    )
    user = ModelMessage(role=MessageRole.USER, content="What happened?")
    original = (call, user)
    repaired = repair_tool_history(original)
    assert original == (call, user)
    assert repaired[1].tool_call_id == "interrupted"
    assert "may have executed" in repaired[1].content
    assert "Do not repeat" in repaired[1].content
    assert repaired[2] == user
    assert repair_tool_history(repaired) == repaired
    normal_result = ModelMessage(
        role=MessageRole.TOOL,
        tool_call_id="interrupted",
        name="robot.example",
        content='{"status":"succeeded"}',
    )
    assert repair_tool_history((call, normal_result, user)) == (call, normal_result, user)
    assert repair_tool_history((normal_result, user))[0].role is MessageRole.ASSISTANT
