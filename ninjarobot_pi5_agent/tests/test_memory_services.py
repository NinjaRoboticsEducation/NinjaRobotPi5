from __future__ import annotations

import asyncio
from pathlib import Path

from ninjarobot_pi5_agent.runtime import (
    _catalog_behavior_name,
    _parse_behavior_confirmation,
)
from ninjarobot_pi5_agent.testing import FakeProvider

from ninjarobot_pi5_agent import (
    AgentLoop,
    AgentRuntime,
    CancellationToken,
    ConversationStore,
    EventBroker,
    FinishReason,
    MemoryCaptureService,
    MemoryKind,
    MemoryMCPProvider,
    MemoryRetrievalService,
    MemoryStore,
    MessageRole,
    ModelMessage,
    ModelTurn,
    MotionArmManager,
    PolicyEngine,
    PromptComposer,
    RecoveryPolicy,
    SkillRepository,
    ToolCall,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
    ToolRegistry,
    ToolTrust,
)
from ninjarobot_pi5_ide import RetrySafety, RiskLevel


def _invocation(
    name: str,
    arguments: dict,
    *,
    session_id: str = "session-1",
) -> ToolInvocation:
    return ToolInvocation(
        call=ToolCall(call_id="call-1", name=name, arguments=arguments),
        session_id=session_id,
    )


def _result(name: str, status: ToolExecutionStatus) -> ToolExecutionResult:
    return ToolExecutionResult(
        call_id="call-1",
        tool_name=name,
        status=status,
        data={"completed": status is ToolExecutionStatus.SUCCEEDED},
        error=None if status is ToolExecutionStatus.SUCCEEDED else "driver unavailable",
        action_id="action-1",
        definitely_not_executed=False,
        retry_safety=RetrySafety.UNKNOWN,
    )


def test_capture_policy_records_failures_and_confirms_new_successes(tmp_path: Path) -> None:
    async def exercise() -> None:
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()
        owner = await store.create_profile("Owner")
        capture = MemoryCaptureService(store)
        movement = _invocation(
            "robot.behavior.execute_movement",
            {"name": "wave", "description": "Wave", "stages": []},
        )
        successful = await capture.observe_tool_result(
            owner.user_id,
            movement,
            _result(movement.call.name, ToolExecutionStatus.SUCCEEDED),
        )
        assert successful.confirmation_needed
        pending = await store.take_pending_behavior_confirmation(owner.user_id, "session-1")
        assert pending is not None
        assert pending.request["name"] == "wave"

        failed = _invocation("robot.servo.move", {"endpoint": "gpio12", "angle": 45})
        await capture.observe_tool_result(
            owner.user_id,
            failed,
            _result(failed.call.name, ToolExecutionStatus.FAILED),
        )
        memories = await store.memories(owner.user_id, kind=MemoryKind.FAILED_BEHAVIOR)
        assert len(memories) == 1
        assert memories[0].payload["request"]["angle"] == 45
        assert memories[0].expires_at is not None
        await store.close()

    asyncio.run(exercise())


def test_automatic_preferences_recipes_and_bounded_retrieval(tmp_path: Path) -> None:
    async def exercise() -> None:
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()
        owner = await store.create_profile("Owner")
        capture = MemoryCaptureService(store)
        preference = await capture.capture_inferred_preference(
            owner.user_id,
            "I prefer blue face animations.",
            session_id="session-1",
        )
        assert preference is not None
        duplicate = await capture.capture_inferred_preference(
            owner.user_id,
            "I prefer blue face animations.",
            session_id="session-1",
        )
        assert duplicate is None
        behavior = _invocation("robot.behavior.run", {"behavior_id": "greeting"})
        outcome = await capture.observe_tool_result(
            owner.user_id,
            behavior,
            _result(behavior.call.name, ToolExecutionStatus.SUCCEEDED),
        )
        assert outcome.automatically_saved_kind is MemoryKind.TASK_RECIPE

        retrieval = MemoryRetrievalService(store)
        context = await retrieval.context(owner.user_id, "blue greeting")
        assert "Active user: Owner" in context
        assert "blue face animations" in context
        assert "greeting" in context
        assert "Current robot name: NinjaAgent" in context
        assert len(context) <= (await store.settings()).retrieval_character_budget

        successful = await store.add_memory(
            owner.user_id,
            MemoryKind.SUCCESSFUL_BEHAVIOR,
            'Confirmed successful behavior: "Exciting one step forward".',
        )
        generic_context = await retrieval.context(owner.user_id, "What do you remember?")
        assert successful.content in generic_context
        second_interface_context = await retrieval.context(
            owner.user_id,
            "Tell me about yourself",
        )
        assert successful.content in second_interface_context
        await store.close()

    asyncio.run(exercise())


def test_explicit_chat_rename_updates_canonical_robot_name_only(tmp_path: Path) -> None:
    async def exercise() -> None:
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()
        owner = await store.create_profile("Owner")
        capture = MemoryCaptureService(store)

        renamed = await capture.capture_inferred_preference(
            owner.user_id,
            "I want to change your name. Please rename yourself to Ninja.",
            session_id="session-1",
        )
        assert renamed is not None
        assert (await store.profile(owner.user_id)).preferred_robot_name == "Ninja"
        context = await MemoryRetrievalService(store).context(owner.user_id, "your name")
        assert "Current robot name: Ninja." in context

        ignored = await capture.capture_inferred_preference(
            owner.user_id,
            "Can I change your name to Pocky?",
            session_id="session-1",
        )
        assert ignored is None
        assert (await store.profile(owner.user_id)).preferred_robot_name == "Ninja"
        await store.close()

    asyncio.run(exercise())


def test_memory_mcp_is_read_only_and_bound_to_session_user(tmp_path: Path) -> None:
    async def exercise() -> None:
        database = tmp_path / "memory.sqlite3"
        conversations = ConversationStore(database)
        store = MemoryStore(database)
        await conversations.start()
        await store.start()
        owner = await store.create_profile("Owner")
        member = await store.create_profile("Member")
        await conversations.create_session("owner-session", user_id=owner.user_id)
        await conversations.create_session("member-session", user_id=member.user_id)
        await store.add_memory(owner.user_id, MemoryKind.PREFERENCE, "Owner likes red")
        await store.add_memory(member.user_id, MemoryKind.PREFERENCE, "Member likes blue")
        provider = MemoryMCPProvider(MemoryRetrievalService(store), conversations)
        await provider.start()
        definitions = await provider.list_tools()
        assert {definition.name for definition in definitions} == {
            "memory.profile.get",
            "memory.search",
            "memory.behavior.successful",
            "memory.behavior.failed",
        }
        assert all(definition.risk is RiskLevel.READ_ONLY for definition in definitions)
        assert all(definition.trust is ToolTrust.TRUSTED for definition in definitions)
        result = await provider.call(
            _invocation(
                "memory.search",
                {"query": "likes", "limit": 6},
                session_id="member-session",
            ),
            CancellationToken(),
        )
        assert result.status is ToolExecutionStatus.SUCCEEDED
        assert result.data is not None
        assert [item["content"] for item in result.data["items"]] == ["Member likes blue"]
        await provider.close()
        await store.close()
        await conversations.close()

    asyncio.run(exercise())


class _BehaviorToolProvider:
    provider_id = "behavior-test"

    def __init__(self) -> None:
        self.requests: list[ToolInvocation] = []

    async def start(self) -> None:
        return None

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        return (
            ToolDefinition(
                name="robot.behavior.execute_expression",
                version="1.0.0",
                description="Execute test expression.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                risk=RiskLevel.LOW,
                default_timeout_seconds=2.0,
                idempotent=False,
                cancellable=True,
                confirmation_required=False,
                source=self.provider_id,
            ),
            ToolDefinition(
                name="robot.behavior.save_user",
                version="1.0.0",
                description="Save test expression.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                risk=RiskLevel.MAINTENANCE,
                default_timeout_seconds=2.0,
                idempotent=False,
                cancellable=False,
                confirmation_required=True,
                source=self.provider_id,
            ),
        )

    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult:
        del cancellation
        self.requests.append(invocation)
        if invocation.call.name == "robot.behavior.save_user":
            return ToolExecutionResult(
                call_id=invocation.call.call_id,
                tool_name=invocation.call.name,
                status=ToolExecutionStatus.SUCCEEDED,
                data={"saved": True, "name": invocation.call.arguments["name"]},
                action_id="action-save",
                definitely_not_executed=False,
                retry_safety=RetrySafety.UNKNOWN,
            )
        return ToolExecutionResult(
            call_id=invocation.call.call_id,
            tool_name=invocation.call.name,
            status=ToolExecutionStatus.SUCCEEDED,
            data={
                "completed": True,
                "compiled_definition": {
                    "schema_version": 1,
                    "name": "birthday",
                    "description": "Celebrate",
                    "category": "expression",
                    "stages": [
                        {
                            "name": "celebrate",
                            "operations": [
                                {
                                    "kind": "face",
                                    "expression": "happy",
                                    "hold_seconds": 1.0,
                                }
                            ],
                        }
                    ],
                },
            },
            action_id="action-expression",
            definitely_not_executed=False,
            retry_safety=RetrySafety.UNKNOWN,
        )

    async def health(self):
        raise NotImplementedError

    async def close(self) -> None:
        return None


def test_runtime_prompts_then_saves_confirmed_successful_behavior(tmp_path: Path) -> None:
    async def exercise() -> None:
        next_id = iter(f"id-{index}" for index in range(1, 20))
        provider = FakeProvider(
            (
                ModelTurn(
                    request_id="id-2",
                    text="",
                    finish_reason=FinishReason.TOOL_CALLS,
                    tool_calls=(
                        ToolCall(
                            call_id="behavior-call",
                            name="robot.behavior.execute_expression",
                            arguments={"name": "birthday", "description": "Celebrate"},
                        ),
                    ),
                ),
                ModelTurn(
                    request_id="id-5",
                    text="The birthday expression completed.",
                    finish_reason=FinishReason.STOP,
                ),
            )
        )
        behavior_tools = _BehaviorToolProvider()
        tools = ToolRegistry((behavior_tools,))
        database = tmp_path / "memory.sqlite3"
        store = ConversationStore(database)
        memory = MemoryStore(database)
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
            id_factory=lambda: next(next_id),
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
        )
        await runtime.start()
        await runtime.chat(session_id="chat", text="hello")
        await runtime.chat(session_id="chat", text="Owner")
        reply = await runtime.chat(session_id="chat", text="Celebrate my birthday")
        assert "Do you want to record this new behavior in long-term memory" in reply.text
        saved = await runtime.chat(
            session_id="chat",
            text='Yes, and please record and name this behavior "Exciting one step forward"',
        )
        assert "Memory saved: successful behavior" in saved.text
        assert 'IDE catalog entry saved as "exciting_one_step_forward"' in saved.text
        owner = await memory.owner()
        assert owner is not None
        memories = await memory.memories(
            owner.user_id,
            kind=MemoryKind.SUCCESSFUL_BEHAVIOR,
        )
        assert len(memories) == 1
        assert memories[0].payload["request"]["name"] == "birthday"
        assert memories[0].payload["display_name"] == "Exciting one step forward"
        assert memories[0].payload["catalog_name"] == "exciting_one_step_forward"
        assert [request.call.name for request in behavior_tools.requests] == [
            "robot.behavior.execute_expression",
            "robot.behavior.save_user",
        ]
        assert behavior_tools.requests[-1].call.arguments["name"] == ("exciting_one_step_forward")
        transcript = await runtime.history("chat")
        assert any(
            item["message"]
            == ModelMessage(
                role=MessageRole.ASSISTANT,
                content=saved.text,
            ).model_dump(mode="json")
            for item in transcript
        )
        await runtime.close()

    asyncio.run(exercise())


def test_behavior_confirmation_parser_is_bounded_and_supports_names() -> None:
    assert _parse_behavior_confirmation("Yes") == (True, None)
    assert _parse_behavior_confirmation('Yes, name it "Happy dance"') == (
        True,
        "Happy dance",
    )
    assert _parse_behavior_confirmation("はい、名前を「楽しいダンス」にしてください") == (
        True,
        "楽しいダンス",
    )
    assert _parse_behavior_confirmation("No, do not save it") == (False, None)
    assert _parse_behavior_confirmation("yesterday") is None
    assert _catalog_behavior_name("Exciting one step forward", "attempt-1") == (
        "exciting_one_step_forward"
    )
    assert _catalog_behavior_name("楽しいダンス", "attempt-123") == ("saved_behavior_attempt123")
