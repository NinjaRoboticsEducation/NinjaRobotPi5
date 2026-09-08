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
