from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from ninjarobot_pi5_agent.models import ToolExecutionResult, ToolExecutionStatus

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


def build_runtime(
    tmp_path,
    *,
    robot_status: Callable[[], Mapping[str, Any]] | None = None,
) -> AgentRuntime:
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
        robot_status=robot_status,
    )


def test_runtime_status_exposes_startup_safety_and_recovery(tmp_path) -> None:
    async def exercise() -> None:
        safety = {
            "schema_version": 1,
            "motion_latched": True,
            "system_latched": True,
            "reason": "driver_failure",
            "fault_detail": "DISPLAY_UNAVAILABLE: simulated startup failure",
            "updated_at": "2026-08-01T05:46:21Z",
        }
        runtime = build_runtime(
            tmp_path,
            robot_status=lambda: {
                "safety": safety,
                "recovery_required": safety["system_latched"],
            },
        )
        runtime.begin_startup_liveliness()
        await runtime.start()

        starting = await runtime.status()
        assert starting["ready"] is False
        assert starting["operational_state"] == "starting"
        assert starting["startup"]["complete"] is False

        lightweight = runtime.startup_status()
        assert lightweight == {
            key: starting[key]
            for key in (
                "started",
                "ready",
                "operational_state",
                "startup",
                "robot",
                "robot_status_error",
                "recovery",
            )
        }

        failure = RuntimeError("system is stopped (driver_failure)")
        runtime.fail_startup_liveliness(failure)
        degraded = await runtime.status()
        assert degraded["ready"] is False
        assert degraded["operational_state"] == "recovery_required"
        assert degraded["startup"]["liveliness"] == "failed"
        assert degraded["robot"]["safety"] == safety
        assert degraded["recovery"] == {
            "required": True,
            "reason": "driver_failure",
            "detail": "DISPLAY_UNAVAILABLE: simulated startup failure",
            "instructions": (
                "Open `ninjarobot-agent chat`, enter `/resume`, and explicitly confirm "
                "the non-moving health checks. Do not delete the safety state file."
            ),
        }

        safety.update(motion_latched=False, system_latched=False, reason=None, fault_detail=None)
        runtime.complete_startup_recovery()
        recovered = await runtime.status()
        assert recovered["ready"] is True
        assert recovered["operational_state"] == "ready"
        assert recovered["startup"]["liveliness"] == "recovered"
        assert recovered["recovery"]["required"] is False
        await runtime.close()

    asyncio.run(exercise())


def test_runtime_status_failure_is_degraded_instead_of_hiding_status(tmp_path) -> None:
    def unavailable_status() -> Mapping[str, Any]:
        raise OSError("safety state cannot be read")

    async def exercise() -> None:
        runtime = build_runtime(tmp_path, robot_status=unavailable_status)
        await runtime.start()
        status = await runtime.status()
        assert status["started"] is True
        assert status["ready"] is False
        assert status["operational_state"] == "status_degraded"
        assert status["robot"] is None
        assert status["robot_status_error"] == "OSError: safety state cannot be read"
        await runtime.close()

    asyncio.run(exercise())


def test_runtime_status_reports_unexpected_idle_supervisor_loss(tmp_path) -> None:
    async def exercise() -> None:
        runtime = build_runtime(
            tmp_path,
            robot_status=lambda: {
                "safety": {
                    "motion_latched": False,
                    "system_latched": False,
                    "reason": None,
                    "fault_detail": None,
                },
                "liveliness": {
                    "enabled": True,
                    "state": "degraded",
                    "idle_error": "OSError: simulated SPI failure",
                    "idle_task_running": False,
                },
            },
        )
        await runtime.start()

        status = runtime.startup_status()

        assert status["ready"] is False
        assert status["operational_state"] == "liveliness_degraded"
        assert status["robot"]["liveliness"]["idle_error"] == ("OSError: simulated SPI failure")
        await runtime.close()

    asyncio.run(exercise())


def test_startup_status_does_not_probe_model_tools_or_database(tmp_path) -> None:
    async def exercise() -> None:
        runtime = build_runtime(tmp_path)
        runtime.begin_startup_liveliness()
        await runtime.start()
        provider_health = AsyncMock(side_effect=AssertionError("provider health was called"))
        tool_health = AsyncMock(side_effect=AssertionError("tool health was called"))
        sessions = AsyncMock(side_effect=AssertionError("database sessions were read"))
        runtime.provider.health = provider_health  # type: ignore[method-assign]
        runtime.tools.health = tool_health  # type: ignore[method-assign]
        runtime.store.sessions = sessions  # type: ignore[method-assign]

        status = runtime.startup_status()

        assert status["operational_state"] == "starting"
        provider_health.assert_not_called()
        tool_health.assert_not_called()
        sessions.assert_not_called()
        await runtime.close()

    asyncio.run(exercise())


def test_runtime_resume_is_confirmed_health_checked_and_does_not_rearm(tmp_path) -> None:
    async def exercise() -> None:
        runtime = build_runtime(tmp_path)
        runtime.begin_startup_liveliness()
        runtime.fail_startup_liveliness(RuntimeError("startup failed"))
        await runtime.start()
        runtime.arm_motion("local-cli", confirmed=True)
        succeeded = ToolExecutionResult(
            call_id="resume-1",
            tool_name="robot.system.resume",
            status=ToolExecutionStatus.SUCCEEDED,
            data={"system_latched": False, "motion_latched": False},
        )
        execute_tool = AsyncMock(return_value=succeeded)
        runtime.execute_tool = execute_tool

        result = await runtime.resume_system(
            "local-cli",
            confirmed=True,
            requested_by="test-resume",
        )

        assert result is succeeded
        assert runtime.motion_arms.is_armed("local-cli") is False
        assert (await runtime.status())["startup"]["liveliness"] == "recovered"
        execute_tool.assert_awaited_once_with(
            tool_name="robot.system.resume",
            arguments={"confirmed": True},
            session_id="local-cli",
            lease_id=None,
            confirmed=True,
            requested_by="test-resume",
        )

        runtime.arm_motion("local-cli", confirmed=True)
        with pytest.raises(PermissionError, match="explicit confirmation"):
            await runtime.resume_system("local-cli", confirmed=False)
        assert runtime.motion_arms.is_armed("local-cli") is True
        await runtime.close()

    asyncio.run(exercise())


def test_runtime_resume_failure_stays_disarmed_and_reports_health_error(tmp_path) -> None:
    async def exercise() -> None:
        runtime = build_runtime(tmp_path)
        await runtime.start()
        runtime.arm_motion("local-cli", confirmed=True)
        runtime.execute_tool = AsyncMock(
            return_value=ToolExecutionResult(
                call_id="resume-failed",
                tool_name="robot.system.resume",
                status=ToolExecutionStatus.FAILED,
                error="a required robot health check failed",
            )
        )

        with pytest.raises(RuntimeError, match="required robot health check failed"):
            await runtime.resume_system("local-cli", confirmed=True)

        assert runtime.motion_arms.is_armed("local-cli") is False
        await runtime.close()

    asyncio.run(exercise())


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
        startup_status = await second_client.request({"command": "startup_status"})
        assert startup_status["data"]["started"] is True
        assert "provider" not in startup_status["data"]
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
        camera_grant = await second_client.request(
            {
                "command": "grant_camera",
                "session_id": "session-1",
                "confirmed": True,
            }
        )
        assert camera_grant["data"] == {
            "ai_camera_granted": True,
            "authorized_for_next_preview": True,
            "captures_remaining": 1,
            "grant_sequence": 1,
        }
        second_camera_grant = await second_client.request(
            {
                "command": "grant_camera",
                "session_id": "session-1",
                "confirmed": True,
            }
        )
        assert second_camera_grant["data"]["grant_sequence"] == 2
        camera_revoke = await second_client.request(
            {
                "command": "revoke_camera",
                "session_id": "session-1",
            }
        )
        assert camera_revoke["data"]["ai_camera_granted"] is False
        cleared = await second_client.request({"command": "clear", "session_id": "session-1"})
        assert cleared["data"]["cleared_messages"] == 2

        stopped = await second_client.request({"command": "stop"})
        assert stopped["data"]["service_stopping"] is True
        await serve_task
        await server.close()
        assert not socket_path.exists()

    asyncio.run(exercise())


def test_ipc_resume_routes_to_the_confirmed_runtime_boundary(tmp_path) -> None:
    async def exercise() -> None:
        socket_path = tmp_path / "agent.sock"
        runtime = build_runtime(tmp_path)
        resumed = ToolExecutionResult(
            call_id="resume-ipc",
            tool_name="robot.system.resume",
            status=ToolExecutionStatus.SUCCEEDED,
            data={"system_latched": False, "motion_latched": False},
        )
        resume_system = AsyncMock(return_value=resumed)
        runtime.resume_system = resume_system
        server = AgentIPCServer(
            runtime=runtime,
            socket_path=socket_path,
            ownership=ServiceOwnership(tmp_path / "agent.lock"),
        )
        await server.start()
        serve_task = asyncio.create_task(server.serve())
        client = AgentIPCClient(socket_path)

        response = await client.request(
            {
                "command": "resume_system",
                "session_id": "local-cli",
                "confirmed": True,
            }
        )

        assert response["data"]["status"] == "succeeded"
        assert response["data"]["data"]["system_latched"] is False
        resume_system.assert_awaited_once_with(
            "local-cli",
            confirmed=True,
            lease_id=None,
            requested_by="ipc-resume",
        )
        await client.request({"command": "stop"})
        await serve_task
        await server.close()

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
