from __future__ import annotations

import asyncio
import stat
import time
from pathlib import Path
from typing import Any, cast

import pytest
from ninjarobot_pi5_ide.config import BehaviorConfig
from ninjarobot_pi5_ide.errors import IDEError
from ninjarobot_pi5_ide.models import ErrorDetails, RetrySafety

from ninjarobot_pi5_ide import (
    DriveOperation,
    MotionController,
    MotionSafetyError,
    SafetyStateStore,
    ServoDevice,
    SystemSafetyController,
)


class FakeServo:
    def __init__(self) -> None:
        self.simulated = True
        self.start_calls = 0
        self.move_calls: list[tuple[dict[str, float], str]] = []
        self.stop_calls = 0
        self.emergency_calls = 0
        self.move_delay = 0.0

    async def start(self) -> None:
        self.start_calls += 1

    async def move_group(
        self,
        *,
        targets: dict[str, float],
        speed_mode: str,
    ) -> dict[str, Any]:
        self.move_calls.append((targets, speed_mode))
        await asyncio.sleep(self.move_delay)
        return {"interrupted": False}

    async def stop(self) -> dict[str, Any]:
        self.stop_calls += 1
        return {
            "stopped": True,
            "driver_available": True,
            "simulated": True,
        }

    def emergency_stop_sync(self) -> bool:
        self.emergency_calls += 1
        return True


class FakeDistance:
    def __init__(self, readings: list[int | Exception]) -> None:
        self.readings = readings
        self.index = 0
        self.start_calls = 0
        self.close_calls = 0
        self.suspend_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def execute(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        item = self.readings[min(self.index, len(self.readings) - 1)]
        self.index += 1
        if isinstance(item, Exception):
            raise item
        return {
            "distance_mm": item,
            "raw_value": item,
            "sensor_timestamp": time.time(),
        }

    async def close(self) -> None:
        self.close_calls += 1

    async def suspend(self) -> None:
        self.suspend_calls += 1


def out_of_range() -> IDEError:
    return IDEError(
        ErrorDetails(
            code="DEVICE_OUT_OF_RANGE",
            message="No target is in measurable range.",
            technical_detail="raw_value=8191",
            definitely_not_executed=False,
            retry_safety=RetrySafety.SAFE,
            capability="distance.read",
        )
    )


class FakeSuspendable:
    def __init__(self) -> None:
        self.suspend_calls = 0

    async def suspend(self) -> None:
        self.suspend_calls += 1


def behavior_config(tmp_path: Path, **updates: Any) -> BehaviorConfig:
    payload: dict[str, Any] = {
        "user_directory": str(tmp_path / "behaviors"),
        "safety_state_file": str(tmp_path / "safety.json"),
        "distance_poll_interval_seconds": 0.02,
        "watchdog_timeout_seconds": 0.1,
        "system_stopped_display_seconds": 0.0,
    }
    payload.update(updates)
    return BehaviorConfig.model_validate(payload)


def drive_operation(
    *,
    obstacle_policy: str = "front_guarded",
    hold_seconds: float | None = None,
) -> DriveOperation:
    return DriveOperation.model_validate(
        {
            "kind": "drive",
            "targets": {"left_motor": 45.0, "right_motor": -45.0},
            "obstacle_policy": obstacle_policy,
            "hold_seconds": hold_seconds,
        }
    )


def controller(
    tmp_path: Path,
    *,
    readings: list[int | Exception],
    undervoltage: bool = False,
    config_updates: dict[str, Any] | None = None,
    warning_handler: Any | None = None,
) -> tuple[MotionController, FakeServo, FakeDistance, SafetyStateStore]:
    servo = FakeServo()
    distance = FakeDistance(readings)
    config = behavior_config(tmp_path, **(config_updates or {}))
    state = SafetyStateStore(config.safety_state_file)
    motion = MotionController(
        servo=cast(ServoDevice, servo),
        distance=distance,
        config=config,
        state=state,
        undervoltage_provider=lambda: undervoltage,
        warning_handler=warning_handler,
    )
    return motion, servo, distance, state


def test_safety_state_is_private_atomic_and_corruption_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "state" / "safety.json"
    state = SafetyStateStore(path)

    latched = state.latch_motion("front_obstacle")

    assert latched.motion_latched is True
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    state.clear_motion()
    path.write_text("{broken", encoding="utf-8")
    corrupted = state.read()
    assert corrupted.motion_latched is True
    assert corrupted.system_latched is True
    assert corrupted.reason == "invalid_safety_state"


@pytest.mark.parametrize("behavior_name", ["move_forward", "turn_left", "turn_right"])
def test_guarded_motion_starts_immediately_and_stops_after_three_low_readings(
    tmp_path: Path,
    behavior_name: str,
) -> None:
    async def exercise() -> None:
        motion, servo, _distance, state = controller(
            tmp_path / behavior_name,
            readings=[50, 40, 30],
        )

        result = await motion.drive(drive_operation(), behavior_name)

        assert servo.move_calls == [({"gpio12": 45.0, "gpio13": -45.0}, "M")]
        assert result["stop_reason"] == "front_obstacle"
        assert result["warnings"] == []
        assert state.read().motion_latched is True
        assert state.read().system_latched is False
        with pytest.raises(MotionSafetyError, match="motion is latched"):
            await motion.drive(drive_operation(), "move_forward")
        motion.resume(confirmed=True)
        assert state.read().motion_latched is False

    asyncio.run(exercise())


def test_guarded_motion_requires_consecutive_low_readings(tmp_path: Path) -> None:
    async def exercise() -> None:
        motion, _servo, _distance, state = controller(
            tmp_path,
            readings=[50, 40, 51, 50, 40, RuntimeError("missing")],
        )
        task = asyncio.create_task(motion.drive(drive_operation(), "turn_right"))
        while not motion.active:
            await asyncio.sleep(0.001)
        await asyncio.sleep(0.16)

        assert not task.done()
        assert state.read().motion_latched is False
        await motion.stop_motion("operator_stop", latch=False)
        result = await task
        assert result["stop_reason"] == "operator_stop"

    asyncio.run(exercise())


def test_out_of_range_samples_are_silent_clear_space(tmp_path: Path) -> None:
    async def exercise() -> None:
        visible: list[str] = []

        async def show_warning(message: str) -> None:
            visible.append(message)

        motion, servo, _distance, state = controller(
            tmp_path,
            readings=[out_of_range(), 250, out_of_range(), out_of_range()],
            warning_handler=show_warning,
        )
        task = asyncio.create_task(motion.drive(drive_operation(), "move_forward"))
        while not motion.active:
            await asyncio.sleep(0.001)
        await asyncio.sleep(0.06)

        assert servo.move_calls == [({"gpio12": 45.0, "gpio13": -45.0}, "M")]
        assert visible == []
        assert state.read().motion_latched is False
        await motion.stop_motion("operator_stop", latch=False)
        result = await task
        assert result["stop_reason"] == "operator_stop"
        assert result["warnings"] == []

    asyncio.run(exercise())


def test_backward_invalid_readings_warn_but_do_not_stop(tmp_path: Path) -> None:
    async def exercise() -> None:
        visible: list[str] = []

        async def show_warning(message: str) -> None:
            visible.append(message)

        motion, servo, _distance, _state = controller(
            tmp_path,
            readings=[RuntimeError("invalid range")],
            warning_handler=show_warning,
        )
        task = asyncio.create_task(
            motion.drive(
                drive_operation(obstacle_policy="warn_only"),
                "move_backward",
            )
        )
        while not motion.active:
            await asyncio.sleep(0.001)
        await asyncio.sleep(0.06)

        assert not task.done()
        await motion.stop_motion("operator_stop", latch=False)
        result = await task

        assert result["stop_reason"] == "operator_stop"
        assert "front sensor does not protect the rear" in result["warnings"]
        assert "distance reading unavailable; movement continues" in result["warnings"]
        assert visible == ["distance reading unavailable; movement continues"]
        assert servo.stop_calls >= 1

    asyncio.run(exercise())


def test_undervoltage_and_watchdog_are_level_one_motion_stops(tmp_path: Path) -> None:
    async def exercise_undervoltage() -> None:
        motion, _servo, _distance, state = controller(
            tmp_path / "undervoltage",
            readings=[200],
            undervoltage=True,
        )
        result = await motion.drive(drive_operation(), "move_forward")
        assert result["stop_reason"] == "undervoltage"
        assert state.read().motion_latched is True
        assert state.read().system_latched is False

    async def exercise_watchdog() -> None:
        motion, servo, _distance, state = controller(
            tmp_path / "watchdog",
            readings=[200],
        )
        task = asyncio.create_task(motion.drive(drive_operation(), "move_forward"))
        while not motion.active:
            await asyncio.sleep(0.001)
        time.sleep(0.2)
        result = await asyncio.wait_for(task, timeout=1.0)

        assert result["stop_reason"] == "software_watchdog"
        assert servo.emergency_calls == 1
        assert state.read().motion_latched is True
        assert state.read().system_latched is False

    asyncio.run(exercise_undervoltage())
    asyncio.run(exercise_watchdog())


def test_watchdog_receives_heartbeats_during_a_slow_async_servo_ramp(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        motion, servo, _distance, state = controller(
            tmp_path,
            readings=[200],
        )
        servo.move_delay = 0.25
        task = asyncio.create_task(motion.drive(drive_operation(), "move_forward"))
        await asyncio.sleep(0.35)

        assert servo.emergency_calls == 0
        assert state.read().motion_latched is False
        await motion.stop_motion("operator_stop", latch=False)
        result = await task
        assert result["stop_reason"] == "operator_stop"

    asyncio.run(exercise())


def test_missing_readings_do_not_block_motion_start_or_latch(tmp_path: Path) -> None:
    async def exercise() -> None:
        motion, servo, _distance, state = controller(
            tmp_path,
            readings=[RuntimeError("missing")],
        )
        task = asyncio.create_task(motion.drive(drive_operation(), "move_forward"))
        while not motion.active:
            await asyncio.sleep(0.001)
        await asyncio.sleep(0.06)

        assert servo.move_calls == [({"gpio12": 45.0, "gpio13": -45.0}, "M")]
        assert state.read().motion_latched is False

        await motion.stop_motion("operator_stop", latch=False)
        result = await task
        assert result["stop_reason"] == "operator_stop"
        assert state.read().motion_latched is False

    asyncio.run(exercise())


def test_full_stop_suspends_sensors_and_driver_failure_latches_system(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        motion, servo, distance, state = controller(
            tmp_path,
            readings=[200],
        )
        camera = FakeSuspendable()
        microphone = FakeSuspendable()
        calls: list[str] = []

        async def silence() -> None:
            calls.append("silence")

        async def show() -> None:
            calls.append("display")

        system = SystemSafetyController(
            motion=motion,
            state=state,
            silence_buzzer=silence,
            show_stopped=show,
            sensors=(distance, camera, microphone),
            display_hold_seconds=0,
        )

        result = await system.full_stop(
            "driver_failure",
            latch=True,
            fault_detail="DISPLAY_WRITE_FAILED: simulated SPI fault",
        )

        assert result["level"] == 2
        assert result["cleanup_errors"] == []
        assert state.read().system_latched is True
        assert state.read().fault_detail == "DISPLAY_WRITE_FAILED: simulated SPI fault"
        assert servo.stop_calls == 1
        assert distance.suspend_calls == 1
        assert camera.suspend_calls == 1
        assert microphone.suspend_calls == 1
        assert calls == ["silence", "display"]
        with pytest.raises(ValueError, match="explicit confirmation"):
            await system.resume_system(confirmed=False, health_checks={})
        with pytest.raises(
            RuntimeError,
            match=r"camera \(ImportError: missing camera backend\)",
        ):
            await system.resume_system(
                confirmed=True,
                health_checks={
                    "display": lambda: _health(True),
                    "camera": _failed_health,
                },
            )
        resumed = await system.resume_system(
            confirmed=True,
            health_checks={"test": lambda: _health(True)},
        )
        assert resumed.system_latched is False
        assert resumed.motion_latched is False

    asyncio.run(exercise())


async def _health(value: bool) -> bool:
    return value


async def _failed_health() -> bool:
    raise ImportError("missing camera backend")
