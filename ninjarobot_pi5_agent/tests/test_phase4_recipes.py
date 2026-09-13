"""Recipe persistence, policy, cancellation and actual provider calls in isolation."""

from __future__ import annotations

import asyncio
import json

import pytest
from ninjarobot_pi5_agent.command_help_tool import CommandHelpProvider
from ninjarobot_pi5_agent.recipe_controls import recipe_action
from ninjarobot_pi5_agent.recipes import Recipe, RecipeStore, resolve_arguments
from ninjarobot_pi5_agent.system_time_tool import SystemTimeProvider
from ninjarobot_pi5_agent.task_models import TaskStatus
from ninjarobot_pi5_agent.task_service import TaskService
from ninjarobot_pi5_agent.testing import FakeProvider
from ninjarobot_pi5_agent.tools import CancellationToken

from ninjarobot_pi5_agent import (
    AgentLoop,
    AgentRuntime,
    ConversationStore,
    EventBroker,
    MotionArmManager,
    PolicyEngine,
    PromptComposer,
    RecoveryPolicy,
    SkillRepository,
    ToolRegistry,
)


def draft():
    return {
        "id": "clock-help",
        "name": "Clock and help",
        "purpose": "Read current time and instructions",
        "steps": [
            {"tool": "system.time.get", "expected": "Current clock"},
            {
                "tool": "command_help.search",
                "arguments": {"query": "speech"},
                "expected": "Spoken reply instructions",
            },
        ],
    }


async def make_runtime(tmp_path, callback=None):
    class Clock(SystemTimeProvider):
        async def call(self, invocation, cancellation):
            if callback:
                await callback()
            return await super().call(invocation, cancellation)

    provider = FakeProvider(())
    tools = ToolRegistry((Clock(), CommandHelpProvider()))
    store = ConversationStore(tmp_path / "agent.sqlite3")
    arms = MotionArmManager()
    policy = PolicyEngine(arms)
    events = EventBroker()
    loop = AgentLoop(
        provider=provider,
        tools=tools,
        policy=policy,
        recovery=RecoveryPolicy(),
        store=store,
        prompts=PromptComposer(),
        events=events,
    )

    async def forbidden_notify(task):
        pytest.fail("recipe must not notify or move hardware")

    tasks = TaskService(store.path, forbidden_notify)
    runtime = AgentRuntime(
        provider=provider,
        tools=tools,
        store=store,
        loop=loop,
        policy=policy,
        motion_arms=arms,
        skills=SkillRepository(tmp_path / "skills"),
        events=events,
        tasks=tasks,
    )
    await runtime.start()
    return runtime


async def save(runtime, recipe=None, version=0):
    value = recipe or draft()
    preview = await recipe_action(runtime, "one", {"operation": "preview", "recipe": value})
    return await recipe_action(
        runtime,
        "one",
        {
            "operation": "save",
            "recipe": value,
            "review_hash": preview["review_hash"],
            "version": version,
        },
    )


def test_save_review_ownership_versions_policy_and_receipts(tmp_path):
    async def exercise():
        runtime = await make_runtime(tmp_path)
        try:
            value = draft()
            preview = await recipe_action(runtime, "one", {"operation": "preview", "recipe": value})
            assert await runtime.tasks.list("session:one") == ()
            changed = {**value, "purpose": "Changed after review"}
            with pytest.raises(ValueError, match="review_hash"):
                await recipe_action(
                    runtime,
                    "one",
                    {"operation": "save", "recipe": changed, "review_hash": preview["review_hash"]},
                )
            assert (await save(runtime))["version"] == 1
            assert await runtime.tasks.list("session:one") == ()
            with pytest.raises(KeyError):
                await recipe_action(
                    runtime, "two", {"operation": "show", "recipe_id": "clock-help"}
                )
            with pytest.raises(ValueError, match="concurrently"):
                await save(runtime)
            assert (await save(runtime, changed, 1))["version"] == 2
            await recipe_action(
                runtime,
                "one",
                {
                    "operation": "rollback",
                    "recipe_id": "clock-help",
                    "version": 1,
                    "confirmed": True,
                },
            )
            assert (
                await recipe_action(
                    runtime, "one", {"operation": "show", "recipe_id": "clock-help"}
                )
            )["version"] == 1
            result = await recipe_action(
                runtime,
                "one",
                {"operation": "run", "recipe_id": "clock-help", "version": 1, "confirmed": True},
            )
            assert result["status"] == "completed"
            assert [r["tool"] for r in result["results"]] == [
                "system.time.get",
                "command_help.search",
            ]
            receipts = await runtime.tasks.list("session:one")
            assert receipts[0].status is TaskStatus.COMPLETED
            assert [s.description for s in receipts[0].steps[1:]] == [
                "system.time.get",
                "command_help.search",
            ]
            await recipe_action(runtime, "one", {"operation": "disable", "recipe_id": "clock-help"})
            with pytest.raises(ValueError, match="disabled"):
                await recipe_action(
                    runtime,
                    "one",
                    {
                        "operation": "run",
                        "recipe_id": "clock-help",
                        "version": 1,
                        "confirmed": True,
                    },
                )
            with pytest.raises(PermissionError):
                await recipe_action(
                    runtime, "one", {"operation": "delete", "recipe_id": "clock-help"}
                )
        finally:
            await runtime.close()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "interrupt", ["cancel", "disable", "delete", "changed_contract", "timeout"]
)
def test_interrupt_stops_later_steps(tmp_path, interrupt):
    async def exercise():
        token = CancellationToken()

        async def callback():
            if interrupt == "cancel":
                token.cancel()
            elif interrupt in {"disable", "delete"}:
                await recipe_action(
                    runtime,
                    "one",
                    {"operation": interrupt, "recipe_id": "clock-help", "confirmed": True},
                )
            elif interrupt == "changed_contract":
                runtime.tools._definitions["command_help.search"] = runtime.tools.get(
                    "command_help.search"
                ).model_copy(update={"version": "2.0.0"})
            else:
                await asyncio.sleep(2)

        runtime = await make_runtime(tmp_path, callback)
        try:
            value = draft()
            value["max_seconds"] = 1
            await save(runtime, value)
            result = await recipe_action(
                runtime,
                "one",
                {"operation": "run", "recipe_id": "clock-help", "version": 1, "confirmed": True},
                token,
            )
            assert result["status"] in {"cancelled", "failed"}
            assert not any(r.get("tool") == "command_help.search" for r in result["results"])
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_references_and_forbidden_effects():
    value = draft()
    value["steps"][0]["result_fields"] = ["date"]
    value["steps"][1]["arguments"] = {"query": {"$result": [0, "date"]}}
    recipe = Recipe.model_validate_json(json.dumps(value))
    assert resolve_arguments(recipe, recipe.steps[1], {}, [{"date": "2026-09-13"}]) == {
        "query": "2026-09-13"
    }
    for ref in ([1, "date"], [0, "__dict__"], [-1, "date"], [True, "date"]):
        value["steps"][1]["arguments"]["query"]["$result"] = ref
        with pytest.raises(ValueError):
            Recipe.model_validate_json(json.dumps(value))
    value = draft()
    for tool in ("robot.servo.move", "calendar.write", "tasks.reminder.preview", "shell.run"):
        value["steps"][0]["tool"] = tool
        with pytest.raises(ValueError):
            Recipe.model_validate_json(json.dumps(value))


def test_restart_does_not_resume_and_deletion_is_owned(tmp_path):
    async def exercise():
        runtime = await make_runtime(tmp_path)
        await save(runtime)
        task = await runtime.tasks.begin_request(
            scope="session:one", user_id=None, session_id="one", title="Interrupted recipe"
        )
        await runtime.close()
        runtime = await make_runtime(tmp_path)
        try:
            assert (await runtime.tasks.list("session:one"))[0].status is TaskStatus.UNCERTAIN
            store = RecipeStore(runtime.store.path)
            with pytest.raises(KeyError):
                await store.action("session:two", None, "delete", recipe_id="clock-help")
            await store.action("session:one", None, "delete", recipe_id="clock-help")
            assert (await store.action("session:one", None, "list"))["recipes"] == []
            assert (await runtime.tasks.list("session:one"))[0].task_id == task.task_id
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_shutdown_cancels_owned_run_before_closing_receipts(tmp_path):
    async def exercise():
        entered = asyncio.Event()

        async def wait():
            entered.set()
            await asyncio.sleep(30)

        runtime = await make_runtime(tmp_path, wait)
        await save(runtime)
        run = asyncio.create_task(
            recipe_action(
                runtime,
                "one",
                {"operation": "run", "recipe_id": "clock-help", "version": 1, "confirmed": True},
            )
        )
        await entered.wait()
        await asyncio.wait_for(runtime.close(), timeout=2)
        assert run.done()
        assert not runtime._recipe_workers
        runtime = await make_runtime(tmp_path)
        try:
            task = (await runtime.tasks.list("session:one"))[0]
            assert task.status in {TaskStatus.CANCELLED, TaskStatus.UNCERTAIN}
            assert all(step.description != "command_help.search" for step in task.steps)
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_policy_denial_and_outer_budget_prevent_execution(tmp_path, monkeypatch):
    from types import SimpleNamespace

    async def exercise():
        calls = []

        async def callback():
            calls.append("clock")

        runtime = await make_runtime(tmp_path, callback)
        try:
            await save(runtime)
            monkeypatch.setattr(
                runtime.loop,
                "execution_limits",
                lambda: {"tool_attempts_including_retries": 1, "request_seconds": 5},
            )
            request = {
                "operation": "run",
                "recipe_id": "clock-help",
                "version": 1,
                "confirmed": True,
            }
            with pytest.raises(ValueError, match="budget"):
                await recipe_action(runtime, "one", request)
            assert await runtime.tasks.list("session:one") == ()
            monkeypatch.setattr(
                runtime.loop,
                "execution_limits",
                lambda: {"tool_attempts_including_retries": 5, "request_seconds": 5},
            )
            monkeypatch.setattr(
                runtime.policy,
                "evaluate",
                lambda *a, **kw: SimpleNamespace(allowed=False, reason="denied test policy"),
            )
            result = await recipe_action(runtime, "one", request)
            assert result["status"] == "failed"
            assert calls == []
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_deleting_profile_cascades_recipe_versions(tmp_path):
    from ninjarobot_pi5_agent.memory_store import MemoryStore
    from ninjarobot_pi5_agent.recipes import review

    async def exercise():
        memory = MemoryStore(tmp_path / "agent.sqlite3")
        await memory.start()
        try:
            await memory.create_profile("Owner")
            member = await memory.create_profile("Member")
            store = RecipeStore(memory.path)
            recipe = Recipe.model_validate_json(json.dumps(draft()))
            definitions = (
                *await SystemTimeProvider().list_tools(),
                *await CommandHelpProvider().list_tools(),
            )
            preview = review(recipe, definitions)
            await store.action(f"user:{member.user_id}", member.user_id, "save", preview=preview)
            await memory.delete_profile(member.user_id)
            assert (await store.action(f"user:{member.user_id}", member.user_id, "list"))[
                "recipes"
            ] == []
            with memory._lock:
                assert (
                    memory._require_connection()
                    .execute("SELECT COUNT(*) FROM task_recipe_versions")
                    .fetchone()[0]
                    == 0
                )
        finally:
            await memory.close()

    asyncio.run(exercise())
