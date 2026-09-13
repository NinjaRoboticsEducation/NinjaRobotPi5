"""Controller and skill checks without a model, live service or hardware."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from ninjarobot_pi5_agent.agent_cli import build_parser
from ninjarobot_pi5_agent.command_help import help_text
from ninjarobot_pi5_agent.runtime import AgentRuntime
from ninjarobot_pi5_agent.skills import SkillRepository
from ninjarobot_pi5_agent.web_app import _dispatch_web_message


def test_game_cli_and_version_one_skill(tmp_path):
    args = build_parser().parse_args(["game", "start", "--seconds", "5"])
    assert args.operation == "start" and args.seconds == 5
    skill = SkillRepository(tmp_path / "skills").get("distance-game")
    assert skill.manifest.schema_version == 1
    assert set(skill.manifest.allowed_tools) == {
        "robot.game.distance.run",
        "robot.game.distance.stop",
        "robot.game.distance.status",
    }
    assert "/game" in help_text("distance game")
    assert "wheels stay still" in help_text("game")


def test_game_chat_commands_bypass_model_chat():
    async def exercise():
        runtime = Mock(spec=AgentRuntime)
        runtime.game_control = AsyncMock(return_value={"data": {"state": "cancelled"}})
        runtime._identity_reply = AsyncMock()
        runtime._chat_with_task = AsyncMock()
        await AgentRuntime.chat(runtime, session_id="test", text="/game stop")
        runtime.game_control.assert_awaited_once_with(
            "test", "stop", 30, lease_id=None, cancellation=None
        )
        runtime._chat_with_task.assert_not_awaited()
        with pytest.raises(ValueError):
            await AgentRuntime.chat(runtime, session_id="test", text="/game stop 10")

    asyncio.run(exercise())


def test_web_routes_game_to_shared_runtime_with_bound_session():
    from ninjarobot_pi5_agent.web_control import WebRobotController

    async def exercise():
        controller = SimpleNamespace(game_control=AsyncMock(return_value={"state": "idle"}))
        send = AsyncMock()
        await _dispatch_web_message(
            controller, "lease", {"type": "game", "operation": "stop"}, send
        )
        controller.game_control.assert_awaited_once_with("lease", "stop", 30)
        runtime = SimpleNamespace(game_control=AsyncMock(return_value={}))
        controller = SimpleNamespace(
            _runtime=runtime, chat_session=lambda lease: "trusted-" + lease
        )
        await WebRobotController.game_control(controller, "lease", "start", 5)
        runtime.game_control.assert_awaited_once_with("trusted-lease", "start", 5, lease_id="lease")

    asyncio.run(exercise())


def test_game_direct_control_checks_types_before_tools():
    async def exercise():
        runtime = Mock(spec=AgentRuntime)
        runtime.tasks = None
        runtime.execute_tool = AsyncMock()
        for duration in (True, "5", 4, 61):
            with pytest.raises(ValueError):
                await AgentRuntime.game_control(runtime, "test", "start", duration)
        with pytest.raises(ValueError):
            await AgentRuntime.game_control(runtime, "test", "unexpected")
        runtime.execute_tool.assert_not_awaited()

    asyncio.run(exercise())
