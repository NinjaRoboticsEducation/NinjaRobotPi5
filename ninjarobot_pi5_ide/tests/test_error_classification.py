from __future__ import annotations

import asyncio
from typing import Any, cast

from ninjarobot_pi5_ide.errors import is_hardware_driver_error

from ninjarobot_pi5_ide import ErrorDetails, IDEError, RetrySafety, RobotAssembly


def ide_error(code: str) -> IDEError:
    return IDEError(
        ErrorDetails(
            code=code,
            message=f"{code} test failure",
            technical_detail="controlled regression test",
            definitely_not_executed=True,
            retry_safety=RetrySafety.SAFE,
            capability="display.show_text",
        )
    )


class SafetyRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, str | None]] = []

    async def full_stop(
        self,
        reason: str,
        *,
        latch: bool,
        fault_detail: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((reason, latch, fault_detail))
        return {"reason": reason, "latched": latch}


def test_only_explicit_hardware_error_codes_are_driver_failures() -> None:
    assert is_hardware_driver_error(ide_error("DISPLAY_WRITE_FAILED")) is True
    assert is_hardware_driver_error(ide_error("SERVO_MOVE_FAILED")) is True
    assert is_hardware_driver_error(ide_error("INVALID_CAPABILITY_ARGUMENTS")) is False
    assert is_hardware_driver_error(ide_error("BEHAVIOR_DRAFT_INVALID")) is False
    assert is_hardware_driver_error(ValueError("generated text is too long")) is False


def test_robot_latches_only_for_a_real_driver_failure() -> None:
    async def exercise() -> None:
        robot = cast(Any, object.__new__(RobotAssembly))
        recorder = SafetyRecorder()
        robot.system_safety = recorder
        robot._idle_suppressed = False

        await robot._driver_failure(ide_error("INVALID_CAPABILITY_ARGUMENTS"))
        assert recorder.calls == []
        assert robot._idle_suppressed is False

        await robot._driver_failure(ide_error("DISPLAY_WRITE_FAILED"))
        assert recorder.calls == [
            (
                "driver_failure",
                True,
                "DISPLAY_WRITE_FAILED: DISPLAY_WRITE_FAILED test failure "
                "(controlled regression test)",
            )
        ]
        assert robot._idle_suppressed is True

    asyncio.run(exercise())
