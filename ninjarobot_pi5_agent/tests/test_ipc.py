from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from ninjarobot_pi5_agent.models import ToolExecutionResult, ToolExecutionStatus
from ninjarobot_pi5_agent.pairing import PairingError
from ninjarobot_pi5_agent.release_foundations import (
    ReleaseFeatureState,
    ReleaseStatusRegistry,
)

from ninjarobot_pi5_agent import (
    AgentIPCClient,
    AgentIPCError,
    AgentIPCServer,
    AgentLoop,
    AgentRuntime,
    ConversationStore,
    EventBroker,
    FinishReason,
    MemoryKind,
    MemorySettings,
    MemoryStore,
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


class _FakeRemoteAccess:
    def __init__(self) -> None:
        self.active = False
        self.rotations = 0
        self.closed = False

    async def activate(self) -> dict[str, object]:
        self.active = True
        return self.status()

    async def deactivate(self) -> dict[str, object]:
        self.active = False
        return self.status()

    def status(self) -> dict[str, object]:
        return {
            "enabled": self.active,
            "state": "waiting_for_connection" if self.active else "disabled",
        }

    def pairing_url(self) -> str:
        return "https://robot.example/#pair=local-owner-only"

    async def rotate_pairing(self) -> dict[str, object]:
        self.rotations += 1
        return {"pairing_url": self.pairing_url(), "sessions_revoked": True}

    async def close(self) -> None:
        self.closed = True


def build_runtime(
    tmp_path,
    *,
    robot_status: Callable[[], Mapping[str, Any]] | None = None,
    with_memory: bool = False,
    release_status: Callable[[], Mapping[str, Any]] | None = None,
) -> AgentRuntime:
    async def enroll_identity(user_id: str) -> dict[str, Any]:
        return {
            "status": "enrolled",
            "identity": f"face-{user_id}",
            "profile_image_path": str(tmp_path / f"{user_id}.jpg"),
            "backend": "test",
            "raw_photo_retained": False,
        }

    async def prepare_identity_reset() -> str:
        return "ipc-reset-token"

    async def commit_identity_reset(token: str) -> bool:
        assert token == "ipc-reset-token"
        return True

    async def rollback_identity_reset(token: str) -> None:
        assert token == "ipc-reset-token"

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
        memory=MemoryStore(tmp_path / "conversation.sqlite3") if with_memory else None,
        enroll_identity=enroll_identity if with_memory else None,
        prepare_identity_reset=prepare_identity_reset if with_memory else None,
        commit_identity_reset=commit_identity_reset if with_memory else None,
        rollback_identity_reset=rollback_identity_reset if with_memory else None,
        initial_memory_settings=MemorySettings() if with_memory else None,
        release_status=release_status,
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
        assert starting["release"]["voice"]["state"] == "disabled"
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


def test_local_reminder_chat_controls_work_without_a_model(tmp_path) -> None:
    from datetime import timedelta
    from unittest.mock import AsyncMock

    from ninjarobot_pi5_agent.task_controls import TaskControls
    from ninjarobot_pi5_agent.task_models import TaskStatus
    from ninjarobot_pi5_agent.task_service import TaskService

    async def exercise():
        runtime = build_runtime(tmp_path)
        now = [datetime.now(UTC)]
        tasks = TaskService(runtime.store.path, runtime.notify_task, clock=lambda: now[0])
        runtime.tasks = tasks
        runtime.task_controls = TaskControls(tasks, runtime.task_scope)
        runtime.loop.chat = AsyncMock(side_effect=AssertionError("local controls called the model"))
        await runtime.start()
        try:
            reply = await runtime.chat(session_id="reminder-user", text="/remind 60 Tea")
            assert "Not scheduled yet" in reply.text
            assert reply.model_turns == 0
            task = (await tasks.list("session:reminder-user"))[0]
            reply = await runtime.chat(
                session_id="other-user", text=f"/tasks confirm {task.task_id}"
            )
            assert "not found" in reply.text
            reply = await runtime.chat(
                session_id="reminder-user", text=f"/tasks confirm {task.task_id}"
            )
            assert "queued" in reply.text
            now[0] += timedelta(seconds=61)
            await tasks.tick()
            assert (await tasks.list("session:reminder-user"))[0].status is TaskStatus.COMPLETED
            reply = await runtime.chat(session_id="reminder-user", text="/tasks")
            assert "Reading by the user is not confirmed" in reply.text
            assert runtime.loop.chat.await_count == 0
        finally:
            await runtime.close()
        assert not tasks.status()["running"]

    asyncio.run(exercise())


def test_task_progress_and_cancel_do_not_wait_for_busy_chat(tmp_path) -> None:
    from ninjarobot_pi5_agent.task_controls import TaskControls
    from ninjarobot_pi5_agent.task_models import TaskStatus
    from ninjarobot_pi5_agent.task_service import TaskService

    async def exercise():
        runtime = build_runtime(tmp_path)
        entered = asyncio.Event()

        async def blocked(request):
            entered.set()
            await asyncio.Event().wait()

        runtime.provider.generate = blocked
        tasks = TaskService(runtime.store.path, runtime.notify_task)
        runtime.tasks = tasks
        runtime.task_controls = TaskControls(
            tasks, runtime.task_scope, runtime._cancel_request_task
        )
        await runtime.start()
        request = asyncio.create_task(runtime.chat(session_id="busy", text="Explain robots"))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            async with asyncio.timeout(2):
                progress = await runtime.task_action("busy")
                task = progress["tasks"][0]
                assert task["status"] == "running"
                assert task["kind"] == "request"
                await runtime.task_action("busy", "cancel", task["task_id"])
                with pytest.raises(asyncio.CancelledError):
                    await request
            assert (await tasks.list("session:busy"))[0].status is TaskStatus.CANCELLED
        finally:
            request.cancel()
            await asyncio.gather(request, return_exceptions=True)
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


def test_startup_status_waits_until_onboarding_qr_is_presented(tmp_path) -> None:
    async def exercise() -> None:
        release = ReleaseStatusRegistry(
            voice_enabled=False,
            remote_access_enabled=True,
            onboarding_enabled=True,
            shutdown_enabled=False,
        )
        runtime = build_runtime(tmp_path, release_status=release.status)
        runtime.begin_startup_liveliness()
        await runtime.start()

        release.update("onboarding", ReleaseFeatureState.STARTING)
        starting = runtime.startup_status()
        assert starting["ready"] is False
        assert starting["operational_state"] == "starting"

        release.update("onboarding", ReleaseFeatureState.PAIRING)
        pairing = runtime.startup_status()
        assert pairing["ready"] is True
        assert pairing["operational_state"] == "onboarding"
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
        connected = 0

        async def local_controller_connected() -> None:
            nonlocal connected
            connected += 1

        server = AgentIPCServer(
            runtime=build_runtime(tmp_path),
            socket_path=socket_path,
            ownership=ServiceOwnership(tmp_path / "agent.lock"),
            on_local_controller=local_controller_connected,
        )
        await server.start()
        serve_task = asyncio.create_task(server.serve())

        first_client = AgentIPCClient(socket_path)
        guide = await first_client.request({"command": "guided_checks", "step": 1})
        assert guide["data"]["title"] == "Stop and resume"
        assert connected == 0
        acknowledged = await first_client.request({"command": "controller_connected"})
        assert acknowledged["data"] == {"controller_connected": True}
        assert connected == 1
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


def test_ipc_remote_management_is_local_owner_only_and_lifecycle_bounded(tmp_path) -> None:
    async def exercise() -> None:
        socket_path = tmp_path / "remote-agent.sock"
        runtime = build_runtime(tmp_path)
        remote = _FakeRemoteAccess()
        show_remote_access = AsyncMock(
            return_value={
                "displayed": True,
                "existing_browser_sessions_revoked": False,
            }
        )
        server = AgentIPCServer(
            runtime=runtime,
            socket_path=socket_path,
            ownership=ServiceOwnership(tmp_path / "remote-agent.lock"),
            remote_access=remote,  # type: ignore[arg-type]
            show_remote_access=show_remote_access,
        )
        await server.start()
        serve_task = asyncio.create_task(server.serve())
        client = AgentIPCClient(socket_path)

        activated = await client.request({"command": "remote_activate"})
        assert activated["data"]["enabled"] is True
        status = await client.request({"command": "remote_status"})
        assert status["data"]["state"] == "waiting_for_connection"
        pairing = await client.request({"command": "remote_pairing_url"})
        assert pairing["data"]["pairing_url"].startswith("https://")
        displayed = await client.request({"command": "remote_show_qr"})
        assert displayed["data"]["displayed"] is True
        assert displayed["data"]["existing_browser_sessions_revoked"] is False
        show_remote_access.assert_awaited_once_with()
        rotated = await client.request({"command": "remote_rotate_pairing"})
        assert rotated["data"]["sessions_revoked"] is True
        assert remote.rotations == 1
        deactivated = await client.request({"command": "remote_deactivate"})
        assert deactivated["data"]["enabled"] is False

        await client.request({"command": "stop"})
        await serve_task
        await server.close()
        assert remote.closed is True

    asyncio.run(exercise())


def test_ipc_pairing_url_explains_that_the_tunnel_is_not_ready(tmp_path) -> None:
    class UnavailablePairingRemote(_FakeRemoteAccess):
        def pairing_url(self) -> str:
            raise PairingError("no current pairing code is available")

    async def exercise() -> None:
        socket_path = tmp_path / "remote-unavailable.sock"
        runtime = build_runtime(tmp_path)
        server = AgentIPCServer(
            runtime=runtime,
            socket_path=socket_path,
            ownership=ServiceOwnership(tmp_path / "remote-unavailable.lock"),
            remote_access=UnavailablePairingRemote(),  # type: ignore[arg-type]
        )
        await server.start()
        serve_task = asyncio.create_task(server.serve())
        client = AgentIPCClient(socket_path)

        result = await client.request({"command": "remote_pairing_url"})

        assert result["data"] == {
            "pairing_url": None,
            "pairing_available": False,
            "detail": "tunnel_not_ready",
            "next_step": "Check Remote Access status and activate a healthy tunnel first.",
        }
        await client.request({"command": "stop"})
        await serve_task
        await server.close()

    asyncio.run(exercise())


def test_ipc_memory_management_is_confirmed_and_category_bounded(tmp_path) -> None:
    async def exercise() -> None:
        socket_path = tmp_path / "memory-agent.sock"
        runtime = build_runtime(tmp_path, with_memory=True)
        server = AgentIPCServer(
            runtime=runtime,
            socket_path=socket_path,
            ownership=ServiceOwnership(tmp_path / "memory-agent.lock"),
        )
        await server.start()
        serve_task = asyncio.create_task(server.serve())
        client = AgentIPCClient(socket_path)
        await client.request({"command": "chat", "session_id": "session-1", "text": "hello"})
        await client.request({"command": "chat", "session_id": "session-1", "text": "Owner"})
        assert runtime.memory is not None
        member = await runtime.memory.create_profile("Member")
        item = await runtime.memory.add_memory(
            member.user_id,
            MemoryKind.SUCCESSFUL_BEHAVIOR,
            "Confirmed wave",
        )

        profiles = await client.request({"command": "memory_profiles"})
        assert [profile["display_name"] for profile in profiles["data"]] == ["Owner", "Member"]
        listed = await client.request(
            {
                "command": "memory_list",
                "user_id": member.user_id,
                "kind": "successful_behavior",
                "limit": 20,
            }
        )
        assert listed["data"][0]["memory_id"] == item.memory_id
        with pytest.raises(AgentIPCError, match="confirmed=true"):
            await client.request(
                {
                    "command": "memory_delete",
                    "user_id": member.user_id,
                    "memory_id": item.memory_id,
                }
            )
        deleted = await client.request(
            {
                "command": "memory_delete",
                "user_id": member.user_id,
                "memory_id": item.memory_id,
                "confirmed": True,
            }
        )
        assert deleted["data"]["deleted"] is True
        settings = await client.request(
            {
                "command": "memory_update_settings",
                "conversation_retention_days": 21,
                "failed_behavior_retention_days": 120,
            }
        )
        assert settings["data"]["settings"]["conversation_retention_days"] == 21
        registered = await client.request(
            {
                "command": "memory_register_face",
                "user_id": member.user_id,
                "confirmed": True,
            }
        )
        assert registered["data"]["face_registered"] is True
        with pytest.raises(AgentIPCError, match="confirmed=true"):
            await client.request({"command": "memory_reset_all"})
        reset = await client.request({"command": "memory_reset_all", "confirmed": True})
        assert reset["data"]["reset"] is True
        assert reset["data"]["deleted"]["users"] == 2
        assert await runtime.memory.profiles() == ()
        assert (await runtime.memory.settings()).conversation_retention_days == 7
        await client.request({"command": "stop"})
        await serve_task
        await server.close()

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


def test_ipc_client_close_reset_does_not_replace_valid_result(tmp_path, monkeypatch) -> None:
    class ResultReader:
        def __init__(self) -> None:
            self.responses = [b'{"type":"result","data":{"ready":true}}\n', b""]

        async def readline(self) -> bytes:
            return self.responses.pop(0)

    class ResetOnCloseWriter:
        def write(self, _data: bytes) -> None:
            return None

        async def drain(self) -> None:
            return None

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            raise ConnectionResetError("peer closed after response")

    monkeypatch.setattr(
        asyncio,
        "open_unix_connection",
        AsyncMock(return_value=(ResultReader(), ResetOnCloseWriter())),
    )

    async def exercise() -> None:
        response = await AgentIPCClient(tmp_path / "agent.sock").request(
            {"command": "startup_status"}
        )
        assert response == {"data": {"ready": True}}

    asyncio.run(exercise())


def test_ipc_client_read_reset_becomes_controlled_agent_error(tmp_path, monkeypatch) -> None:
    class ResetReader:
        async def readline(self) -> bytes:
            raise ConnectionResetError("service exited")

    class CleanWriter:
        def write(self, _data: bytes) -> None:
            return None

        async def drain(self) -> None:
            return None

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    monkeypatch.setattr(
        asyncio,
        "open_unix_connection",
        AsyncMock(return_value=(ResetReader(), CleanWriter())),
    )

    async def exercise() -> None:
        with pytest.raises(
            AgentIPCError,
            match="agent service connection closed unexpectedly",
        ):
            await AgentIPCClient(tmp_path / "agent.sock").request({"command": "startup_status"})

    asyncio.run(exercise())


def test_runtime_cleanup_attempts_every_resource_after_failure(tmp_path):
    async def exercise():
        runtime = build_runtime(tmp_path, with_memory=True)
        await runtime.start()
        runtime.tasks = AsyncMock()
        runtime.tasks.close.side_effect = RuntimeError("synthetic task close failure")
        for resource in (runtime.tools, runtime.provider, runtime.memory, runtime.store):
            resource.close = AsyncMock(wraps=resource.close)
        with pytest.raises(RuntimeError, match="synthetic task close failure"):
            await runtime.close()
        for resource in (runtime.tools, runtime.provider, runtime.memory, runtime.store):
            resource.close.assert_awaited_once()
        await runtime.close()
        runtime.tasks.close.assert_awaited_once()

    asyncio.run(exercise())


def test_reviewed_reminder_uses_valid_nonmoving_ide_draft(tmp_path):
    from datetime import timedelta
    from unittest.mock import Mock

    from ninjarobot_pi5_agent.models import ToolDefinition
    from ninjarobot_pi5_agent.task_models import LocalTask
    from ninjarobot_pi5_ide.behavior_assets import BehaviorAssetRepository
    from ninjarobot_pi5_ide.behavior_drafts import BehaviorDraftCompiler

    from ninjarobot_pi5_ide import RiskLevel

    async def exercise():
        runtime = build_runtime(tmp_path)
        compiler = BehaviorDraftCompiler(
            assets=BehaviorAssetRepository(tmp_path / "behaviors"), servo_roles=()
        )
        definition = ToolDefinition(
            name="robot.behavior.execute_expression",
            version="1",
            description="Expression",
            input_schema=compiler.input_schema(motion=False),
            output_schema={"type": "object"},
            risk=RiskLevel.LOW,
            default_timeout_seconds=10,
            idempotent=False,
            cancellable=True,
            confirmation_required=True,
        )
        runtime.tools.get = Mock(return_value=definition)
        runtime.tools.call = AsyncMock(
            return_value=ToolExecutionResult(
                call_id="notification",
                tool_name=definition.name,
                status=ToolExecutionStatus.SUCCEEDED,
                data={"completed": True},
                action_id="ide-notification",
            )
        )
        now = datetime.now(UTC)
        task = LocalTask(
            task_id="task-" + "a" * 32,
            owner_scope="session:test",
            source_session_id="test",
            title="Practice",
            created_at=now,
            updated_at=now,
            due_at=now + timedelta(minutes=1),
            timezone="UTC",
            notification="display_buzzer",
        )
        assert not (await runtime.notify_task(task))[0]
        runtime.tools.call.assert_not_awaited()
        task = task.model_copy(update={"approved_at": now})
        success, evidence = await runtime.notify_task(task)
        assert success and "ide-notification" in evidence
        invocation = runtime.tools.call.await_args.args[0]
        compiled = compiler.compile(invocation.call.arguments, motion=False)
        kinds = {op.kind for stage in compiled.stages for op in stage.operations}
        assert kinds == {"text", "tone"}
        runtime.tools.call.return_value = runtime.tools.call.return_value.model_copy(
            update={"data": {"completed": False, "interrupted": True}}
        )
        with pytest.raises(RuntimeError, match="interrupted"):
            await runtime.notify_task(task)

    asyncio.run(exercise())
