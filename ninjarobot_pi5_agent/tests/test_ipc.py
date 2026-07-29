from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from ninjarobot_pi5_agent import (
    AgentIPCClient,
    AgentIPCServer,
    AgentLoop,
    AgentRuntime,
    ConversationStore,
    EventBroker,
    FinishReason,
    ModelRequest,
    ModelStreamEvent,
    ModelTurn,
    MotionArmManager,
    PolicyEngine,
    PromptComposer,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthStatus,
    RecoveryPolicy,
    ServiceOwnership,
    SkillRepository,
    StreamEventType,
    ToolRegistry,
)


class _EchoProvider:
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
            text="Hello from NinjaRobot.",
            finish_reason=FinishReason.STOP,
        )

    async def stream(self, request: ModelRequest):
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.TEXT_DELTA,
            text="Hello ",
        )
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.DONE,
            turn=ModelTurn(
                request_id=request.request_id,
                text="Hello from NinjaRobot.",
                finish_reason=FinishReason.STOP,
            ),
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="echo",
            status=ProviderHealthStatus.READY,
            checked_at=datetime(2026, 7, 28, tzinfo=UTC),
        )

    async def close(self) -> None:
        return None


def build_runtime(tmp_path) -> AgentRuntime:
    provider = _EchoProvider()
    tools = ToolRegistry(())
    store = ConversationStore(tmp_path / "conversation.sqlite3")
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
    return AgentRuntime(
        provider=provider,
        tools=tools,
        store=store,
        loop=loop,
        policy=policy,
        motion_arms=arms,
        skills=SkillRepository(tmp_path / "skills"),
        events=events,
    )


def test_ipc_allows_reconnect_stream_history_clear_arm_and_stop(tmp_path) -> None:
    async def exercise() -> None:
        socket_path = tmp_path / "agent.sock"
        server = AgentIPCServer(
            runtime=build_runtime(tmp_path),
            socket_path=socket_path,
            ownership=ServiceOwnership(tmp_path / "agent.lock"),
        )
        await server.start()
        serve_task = asyncio.create_task(server.serve())

        first_client = AgentIPCClient(socket_path)
        streamed = [
            message
            async for message in first_client.stream(
                {
                    "command": "chat",
                    "session_id": "session-1",
                    "text": "Hello",
                }
            )
        ]
        assert streamed[0] == {"type": "delta", "text": "Hello "}
        assert streamed[-1]["data"]["text"] == "Hello from NinjaRobot."

        second_client = AgentIPCClient(socket_path)
        status = await second_client.request({"command": "status"})
        assert status["data"]["started"] is True
        history = await second_client.request({"command": "history", "session_id": "session-1"})
        assert [
            item["message"]["role"]
            for item in history["data"]  # type: ignore[index]
        ] == ["user", "assistant"]

        armed = await second_client.request(
            {
                "command": "arm_motion",
                "session_id": "session-1",
                "confirmed": True,
            }
        )
        assert armed["data"]["motion_armed"] is True
        cleared = await second_client.request({"command": "clear", "session_id": "session-1"})
        assert cleared["data"]["cleared_messages"] == 2

        stopped = await second_client.request({"command": "stop"})
        assert stopped["data"]["service_stopping"] is True
        await serve_task
        await server.close()
        assert not socket_path.exists()

    asyncio.run(exercise())


def test_ipc_client_disconnect_during_error_reporting_is_clean(tmp_path) -> None:
    class DisconnectedWriter:
        def __init__(self) -> None:
            self.closed = False

        def write(self, _data: bytes) -> None:
            return None

        async def drain(self) -> None:
            raise ConnectionResetError("client disconnected")

        def close(self) -> None:
            self.closed = True

        async def wait_closed(self) -> None:
            raise ConnectionResetError("client disconnected")

    async def exercise() -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(b"not-json\n")
        reader.feed_eof()
        writer = DisconnectedWriter()
        server = AgentIPCServer(
            runtime=build_runtime(tmp_path),
            socket_path=tmp_path / "agent.sock",
            ownership=ServiceOwnership(tmp_path / "agent.lock"),
        )

        await server._handle_client(reader, writer)  # type: ignore[arg-type]

        assert writer.closed is True

    asyncio.run(exercise())
