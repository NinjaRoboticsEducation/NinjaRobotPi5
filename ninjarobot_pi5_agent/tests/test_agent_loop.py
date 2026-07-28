from __future__ import annotations

import asyncio
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
    ModelTurn,
    MotionArmManager,
    PolicyEngine,
    RecoveryPolicy,
    ToolCall,
    ToolRegistry,
)
from ninjarobot_pi5_ide import CapabilityDescriptor, RiskLevel


def descriptor(*, risk: RiskLevel = RiskLevel.READ_ONLY) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name="distance.read",
        version="1.0.0",
        description="Read forward distance.",
        input_schema={"type": "object", "additionalProperties": False},
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


async def build_loop(
    tmp_path: Path,
    turns: list[ModelTurn],
    *,
    risk: RiskLevel = RiskLevel.READ_ONLY,
    config: AgentLoopConfig | None = None,
) -> tuple[AgentLoop, ConversationStore, ToolRegistry, FakeIDEClient]:
    store = ConversationStore(tmp_path / "conversation.sqlite3")
    await store.start()
    ide = FakeIDEClient((descriptor(risk=risk),))
    registry = ToolRegistry((IDEToolProvider(ide),))
    await registry.start()
    loop = AgentLoop(
        provider=FakeProvider(turns),
        tools=registry,
        policy=PolicyEngine(MotionArmManager()),
        recovery=RecoveryPolicy(),
        store=store,
        config=config,
        id_factory=_IDs(),
    )
    return loop, store, registry, ide


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
