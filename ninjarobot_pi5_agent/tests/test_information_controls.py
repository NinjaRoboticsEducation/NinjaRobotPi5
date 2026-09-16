"""Public controls exercised with fake model, temporary data and no hardware."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from ninjarobot_pi5_agent.information_controls import information_action
from ninjarobot_pi5_agent.information_tools import InformationProvider
from ninjarobot_pi5_agent.secrets import SecretStore
from ninjarobot_pi5_agent.task_service import TaskService
from ninjarobot_pi5_agent.testing import FakeProvider
from ninjarobot_pi5_agent.tools import CancellationToken

from ninjarobot_pi5_agent import (
    AgentLoop,
    AgentRuntime,
    ConversationStore,
    EventBroker,
    MemoryStore,
    MotionArmManager,
    PolicyEngine,
    PromptComposer,
    RecoveryPolicy,
    SkillRepository,
    ToolRegistry,
)


async def runtime_for(tmp_path: Path) -> AgentRuntime:
    store = ConversationStore(tmp_path / "agent.db")
    memory = MemoryStore(store.path)
    provider = FakeProvider(())
    events = EventBroker()
    arms = MotionArmManager()
    policy = PolicyEngine(arms)

    async def no_notify(task):
        pytest.fail("information work must not create reminder delivery")

    tasks = TaskService(store.path, no_notify)
    information = InformationProvider(
        store.path,
        SecretStore(tmp_path / "secrets.env"),
        tasks,
        lambda session: runtime.task_scope(session),
        lambda **kwargs: runtime.execute_tool(**kwargs),
    )
    tools = ToolRegistry((information,))
    loop = AgentLoop(
        provider=provider,
        tools=tools,
        policy=policy,
        recovery=RecoveryPolicy(),
        store=store,
        prompts=PromptComposer(),
        events=events,
    )
    runtime = AgentRuntime(
        provider=provider,
        tools=tools,
        store=store,
        loop=loop,
        policy=policy,
        motion_arms=arms,
        skills=SkillRepository(tmp_path / "skills"),
        events=events,
        memory=memory,
        tasks=tasks,
        information=information,
    )
    await runtime.start()
    await memory.create_profile("Owner")
    return runtime


def test_direct_chat_review_and_model_cannot_confirm(tmp_path: Path) -> None:
    async def run() -> None:
        runtime = await runtime_for(tmp_path)
        try:
            assert "notes.confirm" not in {t.name for t in runtime.tools.list_tools()}
            assert "calendar.confirm" not in {t.name for t in runtime.tools.list_tools()}
            reply = await runtime.chat(
                session_id="one",
                text=(
                    '/info notes.create {"arguments":{"content":{"title":"Checklist",'
                    '"items":[{"text":"Pack charger"}]}}}'
                ),
            )
            preview = json.loads(reply.text)
            assert preview["executed"] is False
            args = {
                "preview_id": preview["record_id"],
                "review_hash": preview["payload"]["review_hash"],
            }
            with pytest.raises(PermissionError):
                await information_action(
                    runtime, "one", {"operation": "notes.confirm", "arguments": args}
                )
            with pytest.raises(ValueError):
                await information_action(
                    runtime,
                    "two",
                    {"operation": "notes.confirm", "arguments": args, "confirmed": True},
                )
            saved = await information_action(
                runtime, "one", {"operation": "notes.confirm", "arguments": args, "confirmed": True}
            )
            assert saved["payload"]["title"] == "Checklist"
            briefing = await information_action(
                runtime,
                "one",
                {
                    "operation": "briefing.build",
                    "arguments": {"timezone": "Asia/Tokyo", "note_ids": [saved["record_id"]]},
                },
            )
            assert "Pack charger" in briefing["text"]
            assert briefing["saved"] is False
            assert all(s["state"] == "available" for s in briefing["sections"])
            assert await runtime.tasks.list("user:local-user")
        finally:
            await runtime.close()

    asyncio.run(run())


def test_private_user_switch_withholds_delayed_result(tmp_path: Path) -> None:
    async def run() -> None:
        runtime = await runtime_for(tmp_path)
        try:
            info = runtime.information
            assert info is not None and runtime.memory is not None
            member = await runtime.memory.create_profile("Member")
            entered = asyncio.Event()
            release = asyncio.Event()

            async def delayed(user, **kwargs):
                entered.set()
                await release.wait()
                return {"notes": [{"title": "private"}]}

            info.notes.list = delayed
            worker = asyncio.create_task(info.action("one", "notes.list", {}, CancellationToken()))
            await entered.wait()
            runtime._active_users["one"] = member.user_id
            release.set()
            with pytest.raises(ValueError, match="active user changed"):
                await worker
        finally:
            await runtime.close()

    asyncio.run(run())


def test_large_note_pages_preserve_exact_review_without_chat_overflow(tmp_path: Path) -> None:
    async def run() -> None:
        runtime = await runtime_for(tmp_path)
        try:
            preview = await information_action(
                runtime,
                "one",
                {
                    "operation": "notes.create",
                    "arguments": {"content": {"title": "Long", "body": "x" * 16000}},
                },
            )
            assert preview["pages"] >= 2
            chunks = []
            for page in range(1, preview["pages"] + 1):
                reply = await runtime.chat(
                    session_id="one",
                    text="/info notes.preview "
                    + json.dumps({"arguments": {"record_id": preview["record_id"], "page": page}}),
                )
                value = json.loads(reply.text)
                chunks.append(value["content_chunk"])
                assert len(reply.text) < 20000
            full = json.loads("".join(chunks))
            assert full["payload"]["change"]["content"]["body"] == "x" * 16000
            assert full["payload"]["review_hash"] == preview["review_hash"]
        finally:
            await runtime.close()

    asyncio.run(run())


def test_chat_briefing_keeps_local_text_during_calendar_outage(tmp_path: Path) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    async def run() -> None:
        runtime = await runtime_for(tmp_path)
        try:
            runtime.speech = SimpleNamespace(
                enabled=True,
                speak=AsyncMock(return_value={"status": "played", "played": True}),
                close=AsyncMock(),
            )
            reply = await runtime.chat(
                session_id="one",
                text='/info briefing.build {"arguments":{"timezone":"Asia/Tokyo",'
                '"connection_id":"disconnected-test-calendar"}}',
            )
            assert "Local reminders" in reply.text
            assert "calendar: unavailable" in reply.text
            assert "not a full schedule" in reply.text
            spoken = runtime.speech.speak.call_args.args[0]
            assert len(spoken) < 500 and "source coverage" in spoken
            assert not (await runtime.information.notes.list("local-user"))["notes"]
        finally:
            await runtime.close()

    asyncio.run(run())


def test_calendar_setup_owner_binding_and_profile_credential_cleanup(tmp_path: Path) -> None:
    from ninjarobot_pi5_agent.calendar_google import READ_SCOPE

    async def run():
        runtime = await runtime_for(tmp_path)
        try:
            member = await runtime.memory.create_profile("Member")
            runtime._active_users["setup"] = member.user_id
            args = {
                "calendar_id": "test@example.org",
                "account_label": "Synthetic account",
                "credential": {
                    "client_id": "fake",
                    "client_secret": "fake",
                    "refresh_token": "fake",
                    "scope": READ_SCOPE,
                },
                "expected_user_id": "local-user",
            }
            with pytest.raises(ValueError, match="active user changed"):
                await information_action(
                    runtime,
                    "setup",
                    {"operation": "calendar.connect", "confirmed": True, "arguments": args},
                )
            args["expected_user_id"] = member.user_id
            connection = await information_action(
                runtime,
                "setup",
                {"operation": "calendar.connect", "confirmed": True, "arguments": args},
            )
            assert connection["write_enabled"] is False
            info = runtime.information
            record = await info.store.action(
                member.user_id, "get", record_id=connection["connection_id"]
            )
            reference = record["payload"]["secret_ref"]
            assert info.secrets.contains(reference)
            runtime._active_users["setup"] = "local-user"
            await runtime.delete_memory_profile(member.user_id)
            assert not info.secrets.contains(reference)
            with pytest.raises(ValueError, match="no longer exists"):
                await info.store.action(
                    member.user_id, "get", record_id=connection["connection_id"]
                )
        finally:
            await runtime.close()

    asyncio.run(run())


def test_calendar_reconnect_preserves_id_and_replaces_private_grant(tmp_path):
    from ninjarobot_pi5_agent.calendar_google import READ_SCOPE, WRITE_SCOPE

    async def run():
        runtime = await runtime_for(tmp_path)
        try:
            args = dict(
                calendar_id="test@example.org",
                account_label="Test",
                credential=dict(
                    client_id="fake", client_secret="fake", refresh_token="fake", scope=READ_SCOPE
                ),
                expected_user_id="local-user",
            )

            async def connect():
                return await information_action(
                    runtime,
                    "setup",
                    dict(operation="calendar.connect", confirmed=True, arguments=args),
                )

            first = await connect()
            record = await runtime.information.store.action(
                "local-user", "get", record_id=first["connection_id"]
            )
            args["write"] = True
            args["credential"]["scope"] = WRITE_SCOPE
            second = await connect()
            assert first["connection_id"] == second["connection_id"]
            assert second["reconnected"] and second["write_enabled"]
            assert not runtime.information.secrets.contains(record["payload"]["secret_ref"])
            page = await runtime.information.store.action(
                "local-user", "list", kind="calendar_connection"
            )
            assert len(page["records"]) == 1
            assert page["records"][0]["revision"] == 2
            args["credential"]["scope"] = READ_SCOPE
            with pytest.raises(ValueError, match="scope"):
                await connect()
        finally:
            await runtime.close()

    asyncio.run(run())
