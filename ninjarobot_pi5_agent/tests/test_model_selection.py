from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from ninjarobot_pi5_agent.cloud_common import CloudUnavailableError
from ninjarobot_pi5_agent.secrets import SecretStore

from ninjarobot_pi5_agent import (
    AgentLoop,
    AgentRuntime,
    BenchmarkMetrics,
    BenchmarkRegistry,
    BenchmarkReport,
    BenchmarkThresholds,
    ConversationStore,
    EventBroker,
    FinishReason,
    MemoryKind,
    MemoryStore,
    MessageRole,
    ModelCatalogEntry,
    ModelManager,
    ModelMessage,
    ModelRequest,
    ModelSelectionError,
    ModelStreamEvent,
    ModelTurn,
    MotionArmManager,
    PolicyEngine,
    PromptComposer,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderRegistration,
    RecoveryPolicy,
    SkillRepository,
    StreamEventType,
    ToolRegistry,
)


class _Provider:
    def __init__(self, model: str) -> None:
        self.model = model
        self.closed = False
        self.requests: list[ModelRequest] = []

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tools=True,
            streaming=True,
            images=False,
            audio=False,
            structured_output=True,
            usage_reporting=False,
            provider_conversation_state=False,
        )

    async def generate(self, request: ModelRequest) -> ModelTurn:
        self.requests.append(request)
        return ModelTurn(
            request_id=request.request_id,
            text=self.model,
            finish_reason=FinishReason.STOP,
        )

    async def stream(self, request: ModelRequest):
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.DONE,
            turn=await self.generate(request),
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="ollama",
            status=ProviderHealthStatus.READY,
            checked_at=datetime(2026, 7, 29, tzinfo=UTC),
            detail=f"{self.model} is ready",
        )

    async def close(self) -> None:
        self.closed = True


class _BlockingProvider(_Provider):
    def __init__(self, model: str) -> None:
        super().__init__(model)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def stream(self, request: ModelRequest):
        self.entered.set()
        await self.release.wait()
        async for event in super().stream(request):
            yield event


class _FailingCloudProvider(_Provider):
    async def generate(self, request: ModelRequest) -> ModelTurn:
        raise CloudUnavailableError("provider unavailable")

    async def stream(self, request: ModelRequest):
        raise CloudUnavailableError("provider unavailable")
        yield


def test_secret_store_can_report_and_remove_file_backed_secret(tmp_path) -> None:
    store = SecretStore(tmp_path / "secrets.env")

    assert store.contains("OPENAI_API_KEY") is False
    assert store.delete("OPENAI_API_KEY") is False

    store.set("OPENAI_API_KEY", "test-secret")
    assert store.contains("OPENAI_API_KEY") is True
    assert store.delete("OPENAI_API_KEY") is True
    assert store.contains("OPENAI_API_KEY") is False
    assert not store.path.exists()


def test_model_fallback_is_opt_in_and_never_persists_an_automatic_switch(
    tmp_path,
) -> None:
    async def exercise() -> None:
        persisted: list[tuple[str, str]] = []

        async def catalog() -> tuple[ModelCatalogEntry, ...]:
            return ()

        manager = ModelManager(
            active_provider_id="openai",
            active_model="primary",
            active_provider=_FailingCloudProvider("primary"),
            registrations=(
                ProviderRegistration(
                    provider_id="openai",
                    factory=_FailingCloudProvider,
                    catalog=catalog,
                    default_model="primary",
                ),
                ProviderRegistration(
                    provider_id="ollama",
                    factory=_Provider,
                    catalog=catalog,
                    default_model="fallback",
                ),
            ),
            benchmarks=BenchmarkRegistry(tmp_path / "reports"),
            selection_writer=lambda provider, model: persisted.append((provider, model)),
            fallback_provider_ids=("ollama",),
        )
        request = ModelRequest(
            request_id="fallback-request",
            session_id="fallback-session",
            messages=(ModelMessage(role=MessageRole.USER, content="Hello"),),
            allow_provider_fallback=True,
        )

        turn = await manager.generate(request)

        assert turn.text == "fallback"
        assert manager.provider_id == "openai"
        assert persisted == []
        with pytest.raises(CloudUnavailableError):
            await manager.generate(request.model_copy(update={"allow_provider_fallback": False}))
        await manager.close()

    asyncio.run(exercise())


def test_model_fallback_error_retains_safe_provider_failure_detail(tmp_path) -> None:
    async def exercise() -> None:
        async def catalog() -> tuple[ModelCatalogEntry, ...]:
            return ()

        manager = ModelManager(
            active_provider_id="gemini",
            active_model="gemini-3.6-flash",
            active_provider=_FailingCloudProvider("gemini"),
            registrations=(
                ProviderRegistration(
                    provider_id="gemini",
                    factory=_FailingCloudProvider,
                    catalog=catalog,
                    default_model="gemini-3.6-flash",
                ),
            ),
            benchmarks=BenchmarkRegistry(tmp_path / "reports"),
            selection_writer=lambda _provider, _model: None,
        )
        request = ModelRequest(
            request_id="failure-request",
            session_id="failure-session",
            messages=(ModelMessage(role=MessageRole.USER, content="Hello"),),
            allow_provider_fallback=True,
        )
        with pytest.raises(
            ModelSelectionError,
            match="model providers failed before tool execution: gemini: provider unavailable",
        ):
            await manager.generate(request)
        await manager.close()

    asyncio.run(exercise())


def test_model_manager_lists_acceptance_and_switches_after_persistence(tmp_path) -> None:
    async def exercise() -> None:
        BenchmarkReport(
            model="small:2b",
            measured_at=datetime(2026, 7, 29, tzinfo=UTC),
            thresholds=BenchmarkThresholds(),
            metrics=BenchmarkMetrics(),
            accepted=True,
            failures=(),
        ).save(tmp_path / "reports" / "small.json")
        original = _Provider("qwen3:4b")
        created: list[_Provider] = []
        persisted: list[tuple[str, str]] = []

        def factory(model: str) -> _Provider:
            provider = _Provider(model)
            created.append(provider)
            return provider

        async def catalog() -> tuple[ModelCatalogEntry, ...]:
            return (
                ModelCatalogEntry(provider="ollama", name="qwen3:4b"),
                ModelCatalogEntry(provider="ollama", name="small:2b"),
            )

        manager = ModelManager(
            active_provider_id="ollama",
            active_model="qwen3:4b",
            active_provider=original,
            registrations=(
                ProviderRegistration(
                    provider_id="ollama",
                    factory=factory,
                    catalog=catalog,
                ),
            ),
            benchmarks=BenchmarkRegistry(tmp_path / "reports"),
            selection_writer=lambda provider, model: persisted.append((provider, model)),
        )

        models = await manager.catalog()
        assert [model.current for model in models] == [True, False]
        assert [model.accepted for model in models] == [False, True]

        selected = await manager.select("ollama", "small:2b")

        assert selected.current is True
        assert selected.accepted is True
        assert manager.selection() == {
            "provider": "ollama",
            "model": "small:2b",
            "accepted": True,
        }
        assert persisted == [("ollama", "small:2b")]
        assert original.closed is True
        assert created[0].closed is False
        await manager.close()
        assert created[0].closed is True

    asyncio.run(exercise())


def test_runtime_allows_confirmed_motion_arm_but_refuses_model_switch_while_busy(
    tmp_path,
) -> None:
    async def exercise() -> None:
        active = _BlockingProvider("qwen3:4b")

        async def catalog() -> tuple[ModelCatalogEntry, ...]:
            return (
                ModelCatalogEntry(provider="ollama", name="qwen3:4b"),
                ModelCatalogEntry(provider="ollama", name="small:2b"),
            )

        manager = ModelManager(
            active_provider_id="ollama",
            active_model="qwen3:4b",
            active_provider=active,
            registrations=(
                ProviderRegistration(
                    provider_id="ollama",
                    factory=_Provider,
                    catalog=catalog,
                ),
            ),
            benchmarks=BenchmarkRegistry(tmp_path / "reports"),
            selection_writer=lambda _provider, _model: None,
        )
        tools = ToolRegistry(())
        store = ConversationStore(tmp_path / "conversation.sqlite3")
        arms = MotionArmManager()
        policy = PolicyEngine(arms)
        events = EventBroker()
        loop = AgentLoop(
            provider=manager,
            tools=tools,
            policy=policy,
            recovery=RecoveryPolicy(),
            store=store,
            prompts=PromptComposer(),
            events=events,
        )
        runtime = AgentRuntime(
            provider=manager,
            model_manager=manager,
            tools=tools,
            store=store,
            loop=loop,
            policy=policy,
            motion_arms=arms,
            skills=SkillRepository(tmp_path / "skills"),
            events=events,
        )
        await runtime.start()

        with pytest.raises(PermissionError, match="explicit confirmation"):
            runtime.arm_motion("session-1", confirmed=False)
        runtime.arm_motion("session-1", confirmed=True)
        assert arms.is_armed("session-1") is True

        chat = asyncio.create_task(
            runtime.chat(
                session_id="session-1",
                text="Hello",
                on_text_delta=lambda _text: asyncio.sleep(0),
            )
        )
        await active.entered.wait()
        with pytest.raises(RuntimeError, match="agent is busy"):
            await runtime.select_model("ollama", "small:2b")
        active.release.set()
        await chat

        selected = await runtime.select_model("ollama", "small:2b")
        assert selected.name == "small:2b"
        await runtime.close()

    asyncio.run(exercise())


def test_model_switch_preserves_session_history_and_long_term_memory_context(tmp_path) -> None:
    async def exercise() -> None:
        database = tmp_path / "conversation.sqlite3"
        memory = MemoryStore(database)
        await memory.start()
        owner = await memory.create_profile("Owner")
        await memory.update_personalization(
            owner.user_id,
            preferred_robot_name="Pocky",
            preferred_form_of_address="Master",
        )
        await memory.add_memory(
            owner.user_id,
            MemoryKind.SUCCESSFUL_BEHAVIOR,
            'Confirmed successful behavior: "Exciting one step forward".',
        )
        await memory.close()

        original = _Provider("qwen")
        created: list[_Provider] = []

        def factory(model: str) -> _Provider:
            provider = _Provider(model)
            created.append(provider)
            return provider

        async def catalog() -> tuple[ModelCatalogEntry, ...]:
            return (
                ModelCatalogEntry(provider="ollama", name="qwen"),
                ModelCatalogEntry(provider="ollama", name="gemma"),
            )

        manager = ModelManager(
            active_provider_id="ollama",
            active_model="qwen",
            active_provider=original,
            registrations=(
                ProviderRegistration(
                    provider_id="ollama",
                    factory=factory,
                    catalog=catalog,
                ),
            ),
            benchmarks=BenchmarkRegistry(tmp_path / "reports"),
            selection_writer=lambda _provider, _model: None,
        )
        tools = ToolRegistry(())
        store = ConversationStore(database)
        arms = MotionArmManager()
        policy = PolicyEngine(arms)
        events = EventBroker()
        loop = AgentLoop(
            provider=manager,
            tools=tools,
            policy=policy,
            recovery=RecoveryPolicy(),
            store=store,
            prompts=PromptComposer(),
            events=events,
        )
        runtime = AgentRuntime(
            provider=manager,
            model_manager=manager,
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

        await runtime.chat(session_id="local-cli", text="What do you remember?")
        await runtime.chat(session_id="web-browser", text="What is your name?")
        await runtime.select_model("ollama", "gemma")
        await runtime.chat(session_id="local-cli", text="Do you still remember?")

        remembered = 'Confirmed successful behavior: "Exciting one step forward".'
        assert any(remembered in message.content for message in original.requests[0].messages)
        assert any(
            "Current robot name: Pocky." in message.content
            for message in original.requests[0].messages
        )
        assert any(
            "Preferred form of address: Master." in message.content
            for message in original.requests[0].messages
        )
        assert any(
            "Current robot name: Pocky." in message.content
            for message in original.requests[1].messages
        )
        assert any(
            "Preferred form of address: Master." in message.content
            for message in original.requests[1].messages
        )
        assert any(remembered in message.content for message in created[0].requests[0].messages)
        assert any(
            "Current robot name: Pocky." in message.content
            for message in created[0].requests[0].messages
        )
        assert any(
            "Preferred form of address: Master." in message.content
            for message in created[0].requests[0].messages
        )
        assert any(
            message.role is MessageRole.ASSISTANT and message.content == "qwen"
            for message in created[0].requests[0].messages
        )
        persisted_owner = await memory.owner()
        assert persisted_owner is not None
        assert persisted_owner.user_id == owner.user_id
        assert persisted_owner.preferred_robot_name == "Pocky"
        assert len(await memory.memories(owner.user_id, kind=MemoryKind.SUCCESSFUL_BEHAVIOR)) == 1
        await runtime.close()

    asyncio.run(exercise())
