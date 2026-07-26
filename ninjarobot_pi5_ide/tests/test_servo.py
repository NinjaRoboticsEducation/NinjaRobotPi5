from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ninjarobot_pi5_ide.servo import ServoRuntime

from ninjarobot_pi5_ide import (
    ActionLedger,
    ActionRequest,
    ActionStatus,
    CapabilityRegistry,
    ExecutionEngine,
    ResourceHealth,
    ResourceScheduler,
    RetrySafety,
    ServoDevice,
    ServoMoveAdapter,
    ServoStatusAdapter,
    ServoStopAdapter,
)

ENDPOINTS = (
    "gpio12",
    "gpio13",
    "hat_pwm1",
    "hat_pwm2",
    "hat_pwm3",
    "hat_pwm4",
)


@dataclass
class FakeCalibration:
    pulse_min: int = 1000
    pulse_max: int = 2000
    pulse_center: int = 1500
    angle_min: float = -90.0
    angle_max: float = 90.0
    angle_center: float = 0.0
    speed: int = 80


class FakeServo:
    def __init__(self, calibration: FakeCalibration | None = None) -> None:
        self._calibration = calibration or FakeCalibration()
        self.center_calls = 0

    @property
    def calibration(self) -> FakeCalibration:
        return self._calibration

    def move_to_center(self) -> None:
        self.center_calls += 1


class FakeServoGroup:
    def __init__(self) -> None:
        self.servos = {endpoint: FakeServo() for endpoint in ENDPOINTS}
        self.move_calls: list[tuple[list[float | None], str]] = []
        self.abort_calls = 0
        self.off_calls = 0
        self.close_calls = 0
        self.block_movement = False
        self.move_started = asyncio.Event()
        self.abort_event = asyncio.Event()

    def get_servo(self, pin: int | str) -> FakeServo | None:
        return self.servos.get(str(pin))

    async def move_all_async(
        self,
        targets: list[float | None],
        speed_mode: str = "M",
    ) -> bool:
        self.move_calls.append((targets, speed_mode))
        self.move_started.set()
        if self.block_movement:
            await self.abort_event.wait()
            return False
        return True

    def abort(self) -> None:
        self.abort_calls += 1
        self.abort_event.set()

    def off(self) -> None:
        self.off_calls += 1

    def close(self) -> None:
        self.close_calls += 1


def request(
    action_id: str,
    capability: str,
    arguments: dict[str, Any] | None = None,
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        capability=capability,
        arguments=arguments or {},
        requested_by="test",
        session_id="servo-test",
        idempotency_key=f"key-{action_id}",
    )


def engine_for(
    tmp_path: Path,
    device: ServoDevice,
) -> ExecutionEngine:
    return ExecutionEngine(
        CapabilityRegistry(
            [
                ServoMoveAdapter(device),
                ServoStatusAdapter(device),
                ServoStopAdapter(device),
            ]
        ),
        ActionLedger(tmp_path / "servo.sqlite3"),
        scheduler=ResourceScheduler(max_concurrency=2, max_queue_size=4),
    )


def runtime_factory(
    group: FakeServoGroup,
    calibrated: frozenset[str] = frozenset(ENDPOINTS),
):
    def factory(
        endpoints: tuple[str, ...],
        calibration_file: str,
        i2c_bus: int,
        address: int,
    ) -> ServoRuntime:
        assert endpoints == ENDPOINTS
        assert calibration_file == "/tmp/test-servo.json"
        assert i2c_bus == 1
        assert address == 0x10
        return ServoRuntime(group=group, calibrated_endpoints=calibrated)

    return factory


def test_status_claims_no_motion_and_reports_fixed_topology(tmp_path: Path) -> None:
    async def exercise() -> None:
        group = FakeServoGroup()
        device = ServoDevice(
            calibration_file="/tmp/test-servo.json",
            motion_enabled=False,
            runtime_factory=runtime_factory(group),
            simulated=True,
        )
        engine = engine_for(tmp_path, device)
        result = await engine.execute(request("servo-status-1", "servo.status"))

        assert result.status is ActionStatus.SUCCEEDED
        assert result.retry_safety is RetrySafety.SAFE
        assert result.data == {
            "endpoints": list(ENDPOINTS),
            "calibrated": {endpoint: True for endpoint in ENDPOINTS},
            "motion_enabled": False,
            "group_motion_enabled": False,
            "driver_available": True,
            "simulated": True,
        }
        assert group.move_calls == []
        assert all(servo.center_calls == 0 for servo in group.servos.values())
        health = await engine.health()
        assert health.status is ResourceHealth.READY
        await engine.close()
        assert group.off_calls == 1
        assert group.close_calls == 1

    asyncio.run(exercise())


def test_motion_disabled_fails_before_any_pulse(tmp_path: Path) -> None:
    async def exercise() -> None:
        group = FakeServoGroup()
        device = ServoDevice(
            calibration_file="/tmp/test-servo.json",
            motion_enabled=False,
            runtime_factory=runtime_factory(group),
        )
        engine = engine_for(tmp_path, device)
        result = await engine.execute(
            request(
                "servo-disabled",
                "servo.move",
                {"endpoint": "gpio12", "target_angle": 10},
            )
        )

        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "SERVO_MOTION_DISABLED"
        assert result.error.definitely_not_executed is True
        assert group.servos["gpio12"].center_calls == 0
        assert group.move_calls == []
        await engine.close()

    asyncio.run(exercise())


def test_uncalibrated_endpoint_fails_before_any_pulse(tmp_path: Path) -> None:
    async def exercise() -> None:
        group = FakeServoGroup()
        device = ServoDevice(
            calibration_file="/tmp/test-servo.json",
            motion_enabled=True,
            runtime_factory=runtime_factory(
                group,
                calibrated=frozenset({"gpio13"}),
            ),
        )
        engine = engine_for(tmp_path, device)
        result = await engine.execute(
            request(
                "servo-uncalibrated",
                "servo.move",
                {"endpoint": "gpio12", "target_angle": 10},
            )
        )

        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "SERVO_NOT_CALIBRATED"
        assert group.servos["gpio12"].center_calls == 0
        assert group.move_calls == []
        await engine.close()

    asyncio.run(exercise())


def test_single_endpoint_move_centers_first_and_is_not_retry_safe(tmp_path: Path) -> None:
    async def exercise() -> None:
        group = FakeServoGroup()
        device = ServoDevice(
            calibration_file="/tmp/test-servo.json",
            motion_enabled=True,
            runtime_factory=runtime_factory(group),
            simulated=True,
        )
        engine = engine_for(tmp_path, device)
        result = await engine.execute(
            request(
                "servo-move-1",
                "servo.move",
                {
                    "endpoint": "hat_pwm2",
                    "target_angle": -15,
                    "speed_mode": "S",
                },
            )
        )

        assert result.status is ActionStatus.SUCCEEDED
        assert result.retry_safety is RetrySafety.UNSAFE
        assert result.data == {
            "endpoint": "hat_pwm2",
            "target_angle": -15.0,
            "speed_mode": "S",
            "interrupted": False,
            "simulated": True,
        }
        assert group.servos["hat_pwm2"].center_calls == 1
        expected_targets: list[float | None] = [None, None, None, -15.0, None, None]
        assert group.move_calls == [(expected_targets, "S")]
        await engine.close()

    asyncio.run(exercise())


def test_target_outside_endpoint_calibration_is_rejected(tmp_path: Path) -> None:
    async def exercise() -> None:
        group = FakeServoGroup()
        group.servos["gpio12"] = FakeServo(FakeCalibration(angle_min=-20, angle_max=20))
        device = ServoDevice(
            calibration_file="/tmp/test-servo.json",
            motion_enabled=True,
            runtime_factory=runtime_factory(group),
        )
        engine = engine_for(tmp_path, device)
        result = await engine.execute(
            request(
                "servo-outside-calibration",
                "servo.move",
                {"endpoint": "gpio12", "target_angle": 30},
            )
        )

        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "SERVO_TARGET_OUTSIDE_CALIBRATION"
        assert group.servos["gpio12"].center_calls == 0
        await engine.close()

    asyncio.run(exercise())


def test_emergency_stop_interrupts_without_servo_resource_lock(tmp_path: Path) -> None:
    async def exercise() -> None:
        group = FakeServoGroup()
        group.block_movement = True
        device = ServoDevice(
            calibration_file="/tmp/test-servo.json",
            motion_enabled=True,
            runtime_factory=runtime_factory(group),
            simulated=True,
        )
        engine = engine_for(tmp_path, device)
        moving = asyncio.create_task(
            engine.execute(
                request(
                    "servo-long-move",
                    "servo.move",
                    {"endpoint": "gpio13", "target_angle": 10},
                )
            )
        )
        await group.move_started.wait()
        stopped = await engine.execute(request("servo-stop-1", "servo.stop"))
        moved = await moving

        assert stopped.status is ActionStatus.SUCCEEDED
        assert stopped.retry_safety is RetrySafety.SAFE
        assert stopped.data == {
            "stopped": True,
            "driver_available": True,
            "simulated": True,
        }
        assert moved.status is ActionStatus.SUCCEEDED
        assert moved.data is not None and moved.data["interrupted"] is True
        assert group.abort_calls >= 1
        assert group.off_calls >= 1
        await engine.close()

    asyncio.run(exercise())


def test_cancellation_aborts_and_turns_every_servo_off(tmp_path: Path) -> None:
    async def exercise() -> None:
        group = FakeServoGroup()
        group.block_movement = True
        device = ServoDevice(
            calibration_file="/tmp/test-servo.json",
            motion_enabled=True,
            runtime_factory=runtime_factory(group),
        )
        engine = engine_for(tmp_path, device)
        moving = asyncio.create_task(
            engine.execute(
                request(
                    "servo-cancel-move",
                    "servo.move",
                    {"endpoint": "hat_pwm1", "target_angle": 10},
                )
            )
        )
        await group.move_started.wait()

        cancelled = await engine.cancel("servo-cancel-move")
        returned = await moving

        assert cancelled.status is ActionStatus.CANCELLED
        assert returned == cancelled
        assert group.abort_calls >= 1
        assert group.off_calls >= 1
        await engine.close()

    asyncio.run(exercise())


def test_invalid_arguments_never_center_or_move(tmp_path: Path) -> None:
    async def exercise() -> None:
        group = FakeServoGroup()
        device = ServoDevice(
            calibration_file="/tmp/test-servo.json",
            motion_enabled=True,
            runtime_factory=runtime_factory(group),
        )
        engine = engine_for(tmp_path, device)
        result = await engine.execute(
            request(
                "servo-invalid",
                "servo.move",
                {"endpoint": "gpio18", "target_angle": 10},
            )
        )

        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "INVALID_CAPABILITY_ARGUMENTS"
        assert result.error.definitely_not_executed is True
        assert group.move_calls == []
        assert all(servo.center_calls == 0 for servo in group.servos.values())
        await engine.close()

    asyncio.run(exercise())


def test_unavailable_backend_is_structured_and_stop_remains_callable(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        def unavailable(
            _endpoints: tuple[str, ...],
            _calibration_file: str,
            _i2c_bus: int,
            _address: int,
        ) -> ServoRuntime:
            raise ConnectionError("PWM or DFR0566 unavailable")

        device = ServoDevice(runtime_factory=unavailable)
        engine = engine_for(tmp_path, device)
        status = await engine.execute(request("servo-unavailable", "servo.status"))
        stopped = await engine.execute(request("servo-unavailable-stop", "servo.stop"))

        assert status.status is ActionStatus.SUCCEEDED
        assert status.data is not None
        assert status.data["driver_available"] is False
        assert stopped.status is ActionStatus.SUCCEEDED
        assert stopped.data == {
            "stopped": True,
            "driver_available": False,
            "simulated": False,
        }
        health = await engine.health()
        assert health.status is ResourceHealth.UNAVAILABLE
        await engine.close()

    asyncio.run(exercise())


def test_servo_descriptors_encode_motion_and_emergency_policy() -> None:
    assert ServoMoveAdapter.descriptor.risk.value == "motion"
    assert ServoMoveAdapter.descriptor.confirmation_required is True
    assert ServoMoveAdapter.descriptor.idempotent is False
    assert ServoMoveAdapter.descriptor.resources == (
        "servo_bus",
        "pwm0",
        "pwm1",
        "i2c1",
        "dfr0566",
    )
    assert ServoStopAdapter.descriptor.risk.value == "emergency"
    assert ServoStopAdapter.descriptor.resources == ()
    assert ServoStopAdapter.descriptor.confirmation_required is False
