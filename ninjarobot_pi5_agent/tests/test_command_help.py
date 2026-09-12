"""Command guidance must remain useful without granting hardware permissions."""

import asyncio

from ninjarobot_pi5_agent.command_help import help_text, wants_command_help
from ninjarobot_pi5_agent.command_help_tool import CommandHelpProvider
from ninjarobot_pi5_agent.models import ToolCall, ToolExecutionStatus, ToolInvocation
from ninjarobot_pi5_agent.skills import SkillRepository
from ninjarobot_pi5_agent.tools import CancellationToken


def test_audio_help_separates_output_and_capture():
    question = "Can you turn on the audio and voice out your answer?"
    assert wants_command_help(question)
    answer = help_text(question)
    assert "/speech on" in answer and "/speech off" in answer
    assert "does not enable the microphone" in answer
    assert "no setting has been changed" in answer
    assert not wants_command_help("Is there any scheduled task in your memory?")
    assert not wants_command_help("/remind 60 Explain how to use robot functions")
    assert not wants_command_help("Move forward")
    assert "/guide" in help_text()
    assert "No matching command" in help_text("unrecognized-topic-xyz")


def test_command_help_tool_and_skill_have_no_execution_surface(tmp_path):
    async def exercise():
        provider = CommandHelpProvider()
        await provider.start()
        tools = await provider.list_tools()
        skill = SkillRepository(tmp_path / "skills").get(
            "robot-command-help", available_tools={tool.name for tool in tools}
        )
        assert skill.manifest.allowed_tools == ("command_help.search",)
        invocation = ToolInvocation(
            session_id="help",
            call=ToolCall(
                call_id="help", name="command_help.search", arguments={"query": "speech"}
            ),
        )
        result = await provider.call(invocation, CancellationToken())
        assert result.status is ToolExecutionStatus.SUCCEEDED
        assert result.data["executed"] is False
        assert len(result.data["instructions"]) < 12000
        cancellation = CancellationToken()
        cancellation.cancel()
        assert (await provider.call(invocation, cancellation)).definitely_not_executed
        invalid = invocation.model_copy(
            update={
                "call": invocation.call.model_copy(
                    update={"arguments": {"query": "speech", "execute": True}}
                )
            }
        )
        assert (
            await provider.call(invalid, CancellationToken())
        ).status is ToolExecutionStatus.FAILED
        await provider.close()

    asyncio.run(exercise())


def test_ordinary_chat_selects_help_skill_but_task_queries_do_not(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from ninjarobot_pi5_agent.runtime import AgentRuntime

    async def exercise():
        runtime = Mock(spec=AgentRuntime)
        runtime._chat_lock = asyncio.Lock()
        runtime._handle_identity_chat = AsyncMock(return_value=None)
        runtime._handle_behavior_confirmation = AsyncMock(return_value=None)
        runtime._chat_with_task = AsyncMock(return_value=SimpleNamespace(text="Instructions"))
        runtime._memory_capture = None
        runtime._automatic_memory_notices = {}
        runtime._execution_notices = {}
        runtime._pending_confirmation_prompts = set()
        runtime.task_controls = None
        runtime.speech = None
        runtime.skills = SkillRepository(tmp_path / "skills")
        runtime.tools = Mock()
        runtime.tools.list_tools.return_value = await CommandHelpProvider().list_tools()
        await AgentRuntime.chat(runtime, session_id="help", text="How do I enable spoken replies?")
        selected = runtime._chat_with_task.call_args.kwargs["skill"]
        assert selected.manifest.id == "robot-command-help"
        runtime.speech_control.assert_not_called()
        await AgentRuntime.chat(
            runtime, session_id="help", text="Is there any scheduled task in your memory?"
        )
        assert runtime._chat_with_task.call_args.kwargs["skill"] is None

    asyncio.run(exercise())
