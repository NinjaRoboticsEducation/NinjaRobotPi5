from __future__ import annotations

import asyncio

import pytest
from ninjarobot_pi5_agent.onboarding import guided_check
from ninjarobot_pi5_agent.runtime import AgentRuntime
from ninjarobot_pi5_agent.web_app import _dispatch_web_message
from ninjarobot_pi5_agent.web_control import WebRobotController


def test_guide_skip_return_and_web_share_diagnostics_without_actions() -> None:
    async def exercise():
        calls = []

        def diagnose():
            calls.append("diagnostics")
            return {"ok": True, "execution_mode": "simulation"}

        # Deliberately no model, hardware, store or deployment object to call.
        runtime = object.__new__(AgentRuntime)
        runtime._guide_diagnostics = diagnose
        controller = WebRobotController(runtime)

        async def forbidden_send(message):
            pytest.fail("guide attempted an unsolicited event")

        for step in (4, 2, 0, 1, 0):
            result = await _dispatch_web_message(
                controller, "test-lease", {"type": "guided_checks", "step": step}, forbidden_send
            )
            assert result["step"] == step
            assert result == guided_check(
                step,
                diagnose if step != 0 else lambda: {"ok": True, "execution_mode": "simulation"},
            )
        assert calls == ["diagnostics", "diagnostics"]

    asyncio.run(exercise())


@pytest.mark.parametrize("step", [True, -1, 5, "0", None, 1.5])
def test_guide_rejects_invalid_step_before_diagnostics(step) -> None:
    def forbidden():
        pytest.fail("invalid step must not inspect the environment")

    with pytest.raises(ValueError, match="guide step"):
        guided_check(step, forbidden)
