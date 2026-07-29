from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

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
    ModelCatalogEntry,
    ModelManager,
    ModelRequest,
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


def test_runtime_refuses_model_switch_and_motion_arm_while_unaccepted_or_busy(
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

        with pytest.raises(PermissionError, match="accepted benchmark"):
            runtime.arm_motion("session-1", confirmed=True)

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
