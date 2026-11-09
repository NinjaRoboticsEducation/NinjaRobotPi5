"""Presentation recovery must not clear or bypass motion protection."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from ninjarobot_pi5_ide import RobotAssembly


def test_motion_latch_allows_silent_face_but_system_latch_does_not():
    async def exercise():
        robot = object.__new__(RobotAssembly)
        robot._liveliness_enabled = True
        robot._waiting_presentation = False
        robot._idle_suppressed = False
        robot._closing = False
        robot._foreground_behaviors = 0
        robot._idle_task = None
        robot._idle_lock = asyncio.Lock()
        robot._ambient_face = "idle"
        robot.distance_game = SimpleNamespace(status=lambda: {"state": "idle"})
        robot.system_safety = SimpleNamespace(stopped=False)
        state = SimpleNamespace(motion_latched=True, system_latched=False)
        robot.safety_state = SimpleNamespace(read=lambda: state)
        robot._silent_face_definition = lambda face: face
        robot._run_idle = AsyncMock()
        await robot._start_idle_if_safe()
        robot._run_idle.assert_awaited_once_with("idle")
        assert state.motion_latched
        state.system_latched = True
        robot._run_idle.reset_mock()
        await robot._start_idle_if_safe()
        robot._run_idle.assert_not_awaited()

    asyncio.run(exercise())
