from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ninjarobot_pi5_agent.testing import FakeProvider
from ninjarobot_pi5_ide.testing import FakeIDEClient

from ninjarobot_pi5_agent import (
    AgentLoop,
    AgentLoopConfig,
    AgentLoopError,
    ConversationStore,
    FinishReason,
    IDEToolProvider,
    ModelRequest,
    ModelStreamEvent,
    ModelTurn,
    MotionArmManager,
    PolicyEngine,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthStatus,
    RecoveryPolicy,
    RobotPresentationController,
    StreamEventType,
    ToolCall,
    ToolRegistry,
)
from ninjarobot_pi5_ide import CapabilityDescriptor, RiskLevel


def descriptor(
    *,
    risk: RiskLevel = RiskLevel.READ_ONLY,
    name: str = "distance.read",
    input_schema: dict[str, object] | None = None,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name=name,
        version="1.0.0",
        description="Read forward distance.",
        input_schema=input_schema or {"type": "object", "additionalProperties": False},
        output_schema={"type": "object"},
        risk=risk,
        resources=("i2c1",),
        default_timeout_seconds=2.0,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
    )


class _IDs:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"id-{self.value}"


class _FaceClient:
    def __init__(self) -> None:
        self.faces: list[str] = []
        self.idle_count = 0

    async def show_agent_face(self, expression: str) -> bool:
        self.faces.append(expression)
        return True

    async def restore_idle_face(self) -> bool:
        self.idle_count += 1
        return True


class _ActiveThinkingProvider:
    """Emit private activity often enough to reset the inactivity timeout."""

    def __init__(self, *, activity_count: int = 4, interval: float = 0.02) -> None:
        self.activity_count = activity_count
        self.interval = interval

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
        raise AssertionError("streaming provider should not use generate")

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        for _ in range(self.activity_count):
            await asyncio.sleep(self.interval)
            yield ModelStreamEvent(
                request_id=request.request_id,
                event=StreamEventType.ACTIVITY,
            )
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.DONE,
            turn=ModelTurn(
                request_id=request.request_id,
                text="Thinking completed.",
                finish_reason=FinishReason.STOP,
            ),
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="active-thinking",
            status=ProviderHealthStatus.READY,
            checked_at=datetime(2026, 7, 29, tzinfo=UTC),
        )

    async def close(self) -> None:
        return None


class _DelayedMotionProvider:
    """Return one motion call only after the test revokes its session."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tools=True,
            streaming=False,
            images=False,
            audio=False,
            structured_output=True,
            usage_reporting=False,
            provider_conversation_state=False,
        )

    async def generate(self, request: ModelRequest) -> ModelTurn:
        self.entered.set()
        await self.release.wait()
        return ModelTurn(
            request_id=request.request_id,
            finish_reason=FinishReason.TOOL_CALLS,
            tool_calls=(
                ToolCall(
                    call_id="delayed-motion",
                    name="robot.behavior.execute_movement",
                    arguments={},
                ),
            ),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        del request
        raise AssertionError("non-streaming provider should not use stream")
        yield

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="delayed-motion",
            status=ProviderHealthStatus.READY,
            checked_at=datetime(2026, 7, 29, tzinfo=UTC),
        )

    async def close(self) -> None:
        return None


async def build_loop(
    tmp_path: Path,
    turns: list[ModelTurn],
    *,
    risk: RiskLevel = RiskLevel.READ_ONLY,
    capability_name: str = "distance.read",
    input_schema: dict[str, object] | None = None,
    arm_session: str | None = None,
    config: AgentLoopConfig | None = None,
) -> tuple[AgentLoop, ConversationStore, ToolRegistry, FakeIDEClient]:
    store = ConversationStore(tmp_path / "conversation.sqlite3")
    await store.start()
    ide = FakeIDEClient(
        (
            descriptor(
                risk=risk,
                name=capability_name,
                input_schema=input_schema,
            ),
        )
    )
    registry = ToolRegistry((IDEToolProvider(ide),))
    await registry.start()
    arms = MotionArmManager()
    if arm_session is not None:
        arms.arm(arm_session, confirmed=True)
    loop = AgentLoop(
        provider=FakeProvider(turns),
        tools=registry,
        policy=PolicyEngine(arms),
        recovery=RecoveryPolicy(),
        store=store,
        config=config,
        id_factory=_IDs(),
    )
    return loop, store, registry, ide


async def build_streaming_loop(
    tmp_path: Path,
    provider: _ActiveThinkingProvider,
    *,
    config: AgentLoopConfig,
) -> tuple[AgentLoop, ConversationStore, ToolRegistry]:
    store = ConversationStore(tmp_path / "streaming-conversation.sqlite3")
    await store.start()
    registry = ToolRegistry((IDEToolProvider(FakeIDEClient((descriptor(),))),))
    await registry.start()
    loop = AgentLoop(
        provider=provider,
        tools=registry,
        policy=PolicyEngine(MotionArmManager()),
        recovery=RecoveryPolicy(),
        store=store,
        config=config,
        id_factory=_IDs(),
    )
    return loop, store, registry


def test_agent_loop_private_activity_resets_model_inactivity_timeout(tmp_path) -> None:
    async def exercise() -> None:
        loop, store, registry = await build_streaming_loop(
            tmp_path,
            _ActiveThinkingProvider(),
            config=AgentLoopConfig(
                request_timeout_seconds=0.5,
                model_inactivity_timeout_seconds=0.03,
            ),
        )

        deltas: list[str] = []
        reply = await loop.chat(
            session_id="session-1",
            text="Think carefully",
            on_text_delta=lambda text: _record_delta(deltas, text),
        )

        assert reply.text == "Thinking completed."
        assert deltas == []
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_agent_loop_complete_request_timeout_still_bounds_activity(tmp_path) -> None:
    async def exercise() -> None:
        loop, store, registry = await build_streaming_loop(
            tmp_path,
            _ActiveThinkingProvider(activity_count=100),
            config=AgentLoopConfig(
                request_timeout_seconds=0.05,
                model_inactivity_timeout_seconds=0.03,
            ),
        )

        with pytest.raises(AgentLoopError, match="complete request|agent request exceeded"):
            await loop.chat(
                session_id="session-1",
                text="Never finish",
                on_text_delta=lambda text: _record_delta([], text),
            )
        await registry.close()
        await store.close()

    asyncio.run(exercise())


async def _record_delta(values: list[str], text: str) -> None:
    values.append(text)


def test_agent_loop_executes_tool_once_and_persists_complete_context(tmp_path) -> None:
    async def exercise() -> None:
        turns = [
            ModelTurn(
                request_id="id-2",
                finish_reason=FinishReason.TOOL_CALLS,
                tool_calls=(
                    ToolCall(
                        call_id="call-1",
                        name="robot.distance.read",
                        arguments={},
                    ),
                ),
            ),
            ModelTurn(
                request_id="id-5",
                text="The sensor is ready.",
                finish_reason=FinishReason.STOP,
            ),
        ]
        loop, store, registry, ide = await build_loop(tmp_path, turns)

        reply = await loop.chat(session_id="session-1", text="Check distance")

        assert reply.text == "The sensor is ready."
        assert reply.model_turns == 2
        assert reply.tool_calls == 1
        assert len(ide.requests) == 1
        messages = await store.messages("session-1")
        assert [stored.message.role.value for stored in messages] == [
            "user",
            "assistant",
            "tool",
            "assistant",
        ]
        assert messages[1].message.tool_calls[0].name == "robot.distance.read"
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_agent_loop_strips_emotion_directive_and_restores_idle(tmp_path) -> None:
    async def exercise() -> None:
        store = ConversationStore(tmp_path / "presentation.sqlite3")
        await store.start()
        registry = ToolRegistry((IDEToolProvider(FakeIDEClient((descriptor(),))),))
        await registry.start()
        face_client = _FaceClient()
        loop = AgentLoop(
            provider=FakeProvider(
                (
                    ModelTurn(
                        request_id="id-2",
                        text="[[face:happy]] Hello there.",
                        finish_reason=FinishReason.STOP,
                    ),
                )
            ),
            tools=registry,
            policy=PolicyEngine(MotionArmManager()),
            recovery=RecoveryPolicy(),
            store=store,
            presentation=RobotPresentationController(face_client),
            id_factory=_IDs(),
        )

        reply = await loop.chat(session_id="session-1", text="Hello")

        assert reply.text == "Hello there."
        assert face_client.faces == ["thinking", "happy"]
        assert face_client.idle_count == 1
        messages = await store.messages("session-1")
        assert messages[-1].message.content == "Hello there."
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_agent_loop_policy_denies_unarmed_motion_without_ide_execution(tmp_path) -> None:
    async def exercise() -> None:
        turns = [
            ModelTurn(
                request_id="id-2",
                finish_reason=FinishReason.TOOL_CALLS,
                tool_calls=(
                    ToolCall(
                        call_id="call-1",
                        name="robot.distance.read",
                        arguments={},
                    ),
                ),
            ),
            ModelTurn(
                request_id="id-5",
                text="Motion was not armed, so I did not move.",
                finish_reason=FinishReason.STOP,
            ),
        ]
        loop, store, registry, ide = await build_loop(
            tmp_path,
            turns,
            risk=RiskLevel.MOTION,
        )

        reply = await loop.chat(session_id="session-1", text="Move")

        assert "not armed" in reply.text
        assert ide.requests == []
        tool_message = (await store.messages("session-1"))[2].message.content
        assert "Motion is not armed" in tool_message
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_agent_loop_executes_agent_composed_movement_when_session_is_armed(
    tmp_path,
) -> None:
    async def exercise() -> None:
        definition = {
            "schema_version": 1,
            "name": "agent_cheer",
            "description": "A transient face, tone, and raised-wheel movement.",
            "category": "movement",
            "stages": [
                {
                    "name": "cheer",
                    "operations": [
                        {
                            "kind": "face",
                            "expression": "exciting",
                            "hold_seconds": 0.5,
                        },
                        {
                            "kind": "tone",
                            "frequency_hz": 880,
                            "duration_seconds": 0.25,
                            "volume": 48,
                        },
                        {
                            "kind": "drive",
                            "targets": {
                                "left_motor": 25,
                                "right_motor": -25,
                            },
                            "hold_seconds": 0.5,
                        },
                    ],
                }
            ],
        }
        turns = [
            ModelTurn(
                request_id="id-2",
                finish_reason=FinishReason.TOOL_CALLS,
                tool_calls=(
                    ToolCall(
                        call_id="call-1",
                        name="robot.behavior.execute_movement",
                        arguments=definition,
                    ),
                ),
            ),
            ModelTurn(
                request_id="id-5",
                text="I created and ran an exciting movement.",
                finish_reason=FinishReason.STOP,
            ),
        ]
        loop, store, registry, ide = await build_loop(
            tmp_path,
            turns,
            risk=RiskLevel.MOTION,
            capability_name="behavior.execute_movement",
            input_schema={"type": "object"},
            arm_session="session-1",
        )

        reply = await loop.chat(session_id="session-1", text="Celebrate with movement")

        assert reply.tool_calls == 1
        assert len(ide.requests) == 1
        assert ide.requests[0].capability == "behavior.execute_movement"
        assert ide.requests[0].arguments == definition
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_agent_loop_corrects_explicit_movement_sent_to_expression_tool(
    tmp_path,
) -> None:
    async def exercise() -> None:
        draft = {
            "name": "agent_forward",
            "description": "Move forward briefly with an excited face.",
            "stages": [
                {
                    "face": "exciting",
                    "movement": "move_forward",
                    "duration_seconds": 1.0,
                }
            ],
        }
        turns = [
            ModelTurn(
                request_id="id-2",
                finish_reason=FinishReason.TOOL_CALLS,
                tool_calls=(
                    ToolCall(
                        call_id="call-1",
                        name="robot.behavior.execute_expression",
                        arguments=draft,
                    ),
                ),
            ),
            ModelTurn(
                request_id="id-5",
                text="I moved forward and stopped.",
                finish_reason=FinishReason.STOP,
            ),
        ]
        loop, store, registry, ide = await build_loop(
            tmp_path,
            turns,
            risk=RiskLevel.MOTION,
            capability_name="behavior.execute_movement",
            input_schema={"type": "object"},
            arm_session="session-1",
        )

        reply = await loop.chat(session_id="session-1", text="Move forward")

        assert reply.tool_calls == 1
        assert len(ide.requests) == 1
        assert ide.requests[0].capability == "behavior.execute_movement"
        assert ide.requests[0].arguments == draft
        messages = await store.messages("session-1")
        assert messages[1].message.tool_calls[0].name == "robot.behavior.execute_movement"
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_corrected_movement_call_still_requires_motion_arming(tmp_path) -> None:
    async def exercise() -> None:
        turns = [
            ModelTurn(
                request_id="id-2",
                finish_reason=FinishReason.TOOL_CALLS,
                tool_calls=(
                    ToolCall(
                        call_id="call-1",
                        name="robot.behavior.execute_expression",
                        arguments={
                            "name": "agent_forward",
                            "stages": [{"movement": "move_forward"}],
                        },
                    ),
                ),
            ),
            ModelTurn(
                request_id="id-5",
                text="Motion is not armed, so I did not move.",
                finish_reason=FinishReason.STOP,
            ),
        ]
        loop, store, registry, ide = await build_loop(
            tmp_path,
            turns,
            risk=RiskLevel.MOTION,
            capability_name="behavior.execute_movement",
            input_schema={"type": "object"},
        )

        reply = await loop.chat(session_id="session-1", text="Move forward")

        assert "not armed" in reply.text
        assert ide.requests == []
        messages = await store.messages("session-1")
        assert messages[1].message.tool_calls[0].name == "robot.behavior.execute_movement"
        assert "Motion is not armed" in messages[2].message.content
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_session_cancellation_prevents_a_delayed_model_motion_call(tmp_path) -> None:
    async def exercise() -> None:
        provider = _DelayedMotionProvider()
        store = ConversationStore(tmp_path / "cancelled.sqlite3")
        await store.start()
        ide = FakeIDEClient(
            (
                descriptor(
                    risk=RiskLevel.MOTION,
                    name="behavior.execute_movement",
                    input_schema={"type": "object"},
                ),
            )
        )
        registry = ToolRegistry((IDEToolProvider(ide),))
        await registry.start()
        arms = MotionArmManager()
        arms.arm("cancelled-session", confirmed=True)
        loop = AgentLoop(
            provider=provider,
            tools=registry,
            policy=PolicyEngine(arms),
            recovery=RecoveryPolicy(),
            store=store,
            id_factory=_IDs(),
        )

        chat = asyncio.create_task(
            loop.chat(
                session_id="cancelled-session",
                text="Move after thinking",
            )
        )
        await provider.entered.wait()
        loop.cancel_session("cancelled-session")
        provider.release.set()

        with pytest.raises(asyncio.CancelledError):
            await chat
        assert ide.requests == []
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_agent_loop_requires_explicit_request_confirmation_to_save_behavior(
    tmp_path,
) -> None:
    async def exercise() -> None:
        definition = {
            "schema_version": 1,
            "name": "saved_smile",
            "description": "A confirmed saved expression.",
            "category": "expression",
            "stages": [
                {
                    "name": "smile",
                    "operations": [
                        {
                            "kind": "face",
                            "expression": "happy",
                            "hold_seconds": 1,
                        }
                    ],
                }
            ],
        }

        def turns() -> list[ModelTurn]:
            return [
                ModelTurn(
                    request_id="id-2",
                    finish_reason=FinishReason.TOOL_CALLS,
                    tool_calls=(
                        ToolCall(
                            call_id="save-call",
                            name="robot.behavior.save_user",
                            arguments=definition,
                        ),
                    ),
                ),
                ModelTurn(
                    request_id="id-5",
                    text="The save request was handled.",
                    finish_reason=FinishReason.STOP,
                ),
            ]

        loop, store, registry, ide = await build_loop(
            tmp_path / "unconfirmed",
            turns(),
            risk=RiskLevel.MAINTENANCE,
            capability_name="behavior.save_user",
            input_schema={"type": "object"},
        )
        await loop.chat(session_id="unconfirmed", text="Maybe save this")
        assert ide.requests == []
        await registry.close()
        await store.close()

        loop, store, registry, ide = await build_loop(
            tmp_path / "confirmed",
            turns(),
            risk=RiskLevel.MAINTENANCE,
            capability_name="behavior.save_user",
            input_schema={"type": "object"},
        )
        await loop.chat(
            session_id="confirmed",
            text="Save this behavior",
            confirmed=True,
        )
        assert len(ide.requests) == 1
        assert ide.requests[0].arguments == definition
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_agent_loop_blocks_duplicate_call_identity(tmp_path) -> None:
    async def exercise() -> None:
        duplicate = ToolCall(
            call_id="duplicate-call",
            name="robot.distance.read",
            arguments={},
        )
        turns = [
            ModelTurn(
                request_id="id-2",
                finish_reason=FinishReason.TOOL_CALLS,
                tool_calls=(duplicate, duplicate),
            ),
            ModelTurn(
                request_id="id-6",
                text="Only one action was executed.",
                finish_reason=FinishReason.STOP,
            ),
        ]
        loop, store, registry, ide = await build_loop(tmp_path, turns)

        reply = await loop.chat(session_id="session-1", text="Check twice")

        assert reply.tool_calls == 2
        assert len(ide.requests) == 1
        messages = await store.messages("session-1")
        assert "Duplicate tool call identity was blocked" in messages[3].message.content
        await registry.close()
        await store.close()

    asyncio.run(exercise())


def test_agent_loop_stops_at_model_turn_limit(tmp_path) -> None:
    async def exercise() -> None:
        turns = [
            ModelTurn(
                request_id="id-2",
                finish_reason=FinishReason.TOOL_CALLS,
                tool_calls=(
                    ToolCall(
                        call_id="call-1",
                        name="robot.distance.read",
                        arguments={},
                    ),
                ),
            ),
        ]
        loop, store, registry, _ide = await build_loop(
            tmp_path,
            turns,
            config=AgentLoopConfig(max_model_turns=1),
        )

        with pytest.raises(AgentLoopError, match="model-turn limit"):
            await loop.chat(session_id="session-1", text="Keep checking")
        await registry.close()
        await store.close()

    asyncio.run(exercise())
