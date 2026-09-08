from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from ninjarobot_pi5_ide.config import BehaviorConfig
from ninjarobot_pi5_ide.models import ActionRequest, ActionStatus
from ninjarobot_pi5_ide.simulation import SimulatedServoGroup

from ninjarobot_pi5_ide import IDEError, build_robot_ide_client, load_robot_config

EXAMPLE = Path(__file__).resolve().parents[2] / "config/ninjarobot_pi5.toml.example"


def client_for(tmp_path):
    config = load_robot_config(EXAMPLE).model_copy(
        update={
            "behaviors": BehaviorConfig(
                safety_state_file=str(tmp_path / "safety.json"),
                user_directory=str(tmp_path / "behaviors"),
                system_stopped_display_seconds=0,
            )
        }
    )
    return build_robot_ide_client(config, ledger_path=tmp_path / "ledger.sqlite3", simulated=True)


def action(key, capability="servo.move", arguments=None):
    return ActionRequest(
        action_id=key,
        capability=capability,
        arguments=arguments
        if arguments is not None
        else {"endpoint": "gpio12", "target_angle": 10},
        requested_by="test",
        session_id="test",
        idempotency_key=key,
    )


@pytest.mark.parametrize("stop", ["system", "motion", "operator"])
def test_raw_and_behavior_motion_reject_stop_before_driver_write(tmp_path, monkeypatch, stop):
    async def exercise():
        client = client_for(tmp_path)
        await client.start()
        if stop == "system":
            client.robot.safety_state.latch_system("driver_failure")
        elif stop == "motion":
            client.robot.safety_state.latch_motion("undervoltage")
        else:
            await client.robot.stop()

        async def forbidden(*args, **kwargs):
            pytest.fail("stopped motion reached a driver")

        monkeypatch.setattr(SimulatedServoGroup, "move_all_async", forbidden)
        try:
            raw = await client.execute(action("raw"))
            assert raw.status is ActionStatus.FAILED
            assert raw.error.code == ("MOTION_STOPPED" if stop == "motion" else "SYSTEM_STOPPED")
            behavior = await client.execute(
                action("behavior", "behavior.run", {"name": "move_forward"})
            )
            assert behavior.status is ActionStatus.FAILED
            with pytest.raises(IDEError):
                await client.robot.servo.move(endpoint="gpio12", target_angle=10, speed_mode="S")
        finally:
            await client.close()

    asyncio.run(exercise())


def test_direct_move_uses_controller_and_finishes_with_zero_output(tmp_path, monkeypatch):
    async def exercise():
        client = client_for(tmp_path)
        off = []
        original = SimulatedServoGroup.off

        def record(self):
            off.append(True)
            original(self)

        monkeypatch.setattr(SimulatedServoGroup, "off", record)
        try:
            await client.start()
            result = await client.execute(action("raw"))
            assert result.status is ActionStatus.SUCCEEDED
            assert result.data["interrupted"] is False
            assert off
            assert not client.robot.motion.active
            with pytest.raises(IDEError, match="motion controller"):
                await client.robot.servo.move_group(targets={"gpio12": 10}, speed_mode="S")
        finally:
            await client.close()

    asyncio.run(exercise())


def test_other_task_cannot_borrow_active_motion_context(tmp_path, monkeypatch):
    async def exercise():
        client = client_for(tmp_path)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def blocked(self, targets, speed_mode="S"):
            entered.set()
            await release.wait()
            return True

        monkeypatch.setattr(SimulatedServoGroup, "move_all_async", blocked)
        await client.start()
        movement = asyncio.create_task(client.execute(action("raw")))
        await entered.wait()
        try:
            with pytest.raises(IDEError, match="motion controller"):
                await client.robot.servo.move(endpoint="gpio13", target_angle=5, speed_mode="S")
        finally:
            release.set()
            await movement
            await client.close()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "capability,arguments",
    [
        ("display.clear", {}),
        ("display.show_text", {"text": "hello"}),
        ("buzzer.play_tone", {"frequency_hz": 440}),
        ("distance.read", {}),
        ("camera.capture", {}),
        ("microphone.capture", {}),
    ],
)
def test_system_stop_blocks_low_level_output_and_sensor_actions(tmp_path, capability, arguments):
    async def exercise():
        client = client_for(tmp_path)
        try:
            await client.start()
            await client.robot.stop()
            result = await client.execute(action("stopped", capability, arguments))
            assert result.status is ActionStatus.FAILED
            assert result.error.code == "SYSTEM_STOPPED"
            assert result.error.definitely_not_executed
        finally:
            await client.close()

    asyncio.run(exercise())
