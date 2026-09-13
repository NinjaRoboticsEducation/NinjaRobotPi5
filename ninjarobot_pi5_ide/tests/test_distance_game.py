from __future__ import annotations

import asyncio
import math
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from ninjarobot_pi5_ide.config import BehaviorConfig, DistanceGameConfig
from ninjarobot_pi5_ide.distance_game import GameRequest, SampleFilter, next_band
from pydantic import ValidationError

from ninjarobot_pi5_ide import (
    ActionRequest,
    ActionStatus,
    build_robot_ide_client,
    load_robot_config,
)

ROOT = Path(__file__).resolve().parents[2]


def client_for(tmp_path, *, enabled=True):
    base = load_robot_config(ROOT / "config/ninjarobot_pi5.toml.example")
    config = base.model_copy(
        update={
            "distance_game": DistanceGameConfig(enabled=enabled),
            "behaviors": BehaviorConfig(
                user_directory=str(tmp_path / "behaviors"),
                safety_state_file=str(tmp_path / "safety.json"),
                system_stopped_display_seconds=0.0,
            ),
        }
    )
    return build_robot_ide_client(config, ledger_path=tmp_path / "ledger.sqlite3", simulated=True)


def request(name, identity="1", arguments=None):
    return ActionRequest(
        action_id=identity,
        capability=name,
        arguments=arguments or {},
        requested_by="test",
        session_id="test",
        idempotency_key=identity,
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {"duration_seconds": True},
        {"duration_seconds": 4},
        {"duration_seconds": 61},
        {"duration_seconds": "5"},
        {"mode": "other"},
        {"volume": 128},
    ],
)
def test_game_strict_inputs(arguments):
    with pytest.raises(ValidationError):
        GameRequest.model_validate(arguments)


@pytest.mark.parametrize(
    "value,previous,expected",
    [
        (49, None, None),
        (50, None, "near"),
        (150, None, "middle"),
        (300, None, "far"),
        (600, None, "far"),
        (601, None, None),
        (160, "near", "near"),
        (169, "near", "near"),
        (170, "near", "middle"),
        (290, "far", "far"),
        (279, "far", "middle"),
        (math.nan, None, None),
    ],
)
def test_bands(value, previous, expected):
    assert next_band(value, previous) == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"sensor_timestamp": math.nan},
        {"sensor_timestamp": 101.0},
        {"sensor_timestamp": 99.0},
        {"distance_mm": True},
        {"raw_value": 8191},
        {"distance_mm": 0},
        {"distance_mm": 601},
    ],
)
def test_bad_samples_clear_history(changes):
    samples = SampleFilter()
    original = dict(distance_mm=100, raw_value=100, sensor_timestamp=100.0)
    assert (
        samples.accept(original, started=1, completed=1.1, wall_started=100, wall_completed=100.1)
        == "near"
    )
    assert (
        samples.accept(
            original | changes, started=1.2, completed=1.3, wall_started=100.2, wall_completed=100.3
        )
        is None
    )
    assert not samples.values and samples.band is None


def test_cached_read_clock_jump_and_read_latency():
    sample = dict(distance_mm=200, raw_value=200, sensor_timestamp=100.1)
    for completed, wall_completed in [(1.3, 100.3), (1.1, 100.25)]:
        assert (
            SampleFilter().accept(
                sample,
                started=1,
                completed=completed,
                wall_started=100,
                wall_completed=wall_completed,
            )
            is None
        )
    samples = SampleFilter()
    assert (
        samples.accept(sample, started=1, completed=1.1, wall_started=100, wall_completed=100.1)
        == "middle"
    )
    assert (
        samples.accept(sample, started=1.2, completed=1.3, wall_started=100.2, wall_completed=100.3)
        is None
    )


def test_game_stop_and_status_bypass_busy_worker_and_do_not_move(tmp_path):
    async def exercise():
        client = client_for(tmp_path)
        await client.start()
        robot = client.robot
        robot.servo.move = AsyncMock(side_effect=AssertionError("game must not move wheels"))
        entered = asyncio.Event()

        async def loop(*_):
            entered.set()
            await asyncio.Event().wait()

        robot.distance_game._loop = loop
        running = asyncio.create_task(client.execute(request("game.distance.run")))
        await asyncio.wait_for(entered.wait(), 1)
        status = await asyncio.wait_for(client.execute(request("game.distance.status", "s")), 0.5)
        assert status.data["state"] == "running"
        duplicate = await client.execute(request("game.distance.run", "d"))
        assert duplicate.status is ActionStatus.REJECTED
        stopped = await asyncio.wait_for(client.execute(request("game.distance.stop", "x")), 0.5)
        assert stopped.status is ActionStatus.SUCCEEDED
        assert (await running).data["state"] == "cancelled"
        assert robot._foreground_behaviors == 0
        robot.servo.move.assert_not_awaited()
        assert (
            await client.execute(request("game.distance.stop", "y"))
        ).status is ActionStatus.SUCCEEDED
        await client.close()

    asyncio.run(exercise())


def test_incoming_output_cancels_game_before_waiting_for_locks(tmp_path):
    async def exercise():
        client = client_for(tmp_path)
        await client.start()
        game = client.robot.distance_game
        entered, ended = asyncio.Event(), asyncio.Event()

        async def loop(*_):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                ended.set()

        game._loop = loop
        run = asyncio.create_task(client.execute(request("game.distance.run")))
        await asyncio.wait_for(entered.wait(), 1)
        original = client.robot.display.clear

        async def clear(**kwargs):
            assert ended.is_set()
            return await original(**kwargs)

        client.robot.display.clear = clear
        result = await asyncio.wait_for(client.execute(request("display.clear", "c")), 1)
        assert result.status is ActionStatus.SUCCEEDED
        assert (await run).data["reason"] == "incoming_action"
        await client.close()

    asyncio.run(exercise())


def test_disabled_game_is_additive_and_never_reads_sensor(tmp_path):
    async def exercise():
        client = client_for(tmp_path, enabled=False)
        await client.start()
        client.robot.distance.execute = AsyncMock(side_effect=AssertionError("unexpected read"))
        result = await client.execute(request("game.distance.run"))
        assert result.status is ActionStatus.REJECTED
        client.robot.distance.execute.assert_not_awaited()
        await client.close()

    asyncio.run(exercise())


def test_loop_enforces_pulse_volume_duration_and_silence_bounds():
    from types import SimpleNamespace

    from ninjarobot_pi5_ide.distance_game import DistanceGame

    async def exercise():
        now = [0.0]
        pulses = []

        async def sleep(seconds):
            now[0] += seconds
            await asyncio.sleep(0)

        async def read(_):
            return dict(distance_mm=100, raw_value=100, sensor_timestamp=1000 + now[0])

        async def play(**kwargs):
            pulses.append((now[0], kwargs))
            now[0] += 0.11
            return {}

        robot = SimpleNamespace(
            ensure_action_allowed=lambda _: None,
            distance=SimpleNamespace(execute=read),
            buzzer=SimpleNamespace(play=play, stop=AsyncMock()),
            display=SimpleNamespace(show_text=AsyncMock()),
        )
        game = DistanceGame(
            robot,
            enabled=True,
            volume=16,
            clock=lambda: now[0],
            wall_clock=lambda: 1000 + now[0],
            sleep=sleep,
        )
        game._state.update(valid_samples=0, invalid_samples=0, tone_seconds=0.0)
        await game._loop(GameRequest(duration_seconds=60), 0.0)
        assert 59.9 <= now[0] <= 60.01
        assert 1 < len(pulses) <= 166
        assert all(
            pulse[1] == dict(frequency_hz=880, duration_seconds=0.06, volume=16) for pulse in pulses
        )
        assert all(b[0] - a[0] >= 1 / 3 for a, b in zip(pulses, pulses[1:]))
        assert game._state["tone_seconds"] <= 10
        assert robot.display.show_text.await_count == 1

        # Out-of-area input clears feedback and finishes after two seconds.
        async def invalid(_):
            return dict(distance_mm=8191, raw_value=8191, sensor_timestamp=1000 + now[0])

        robot.distance.execute = invalid
        started = now[0]
        before = len(pulses)
        await game._loop(GameRequest(duration_seconds=5), started)
        assert len(pulses) == before
        assert game._state["reason"] == "readings_unavailable"
        assert now[0] - started < 2.3
        assert robot.buzzer.stop.await_count >= 10

    asyncio.run(exercise())


def test_emergency_is_not_delayed_by_game_admission_or_fault(tmp_path):
    async def exercise():
        client = client_for(tmp_path)
        await client.start()
        game = client.robot.distance_game
        game._state.update(state="faulted", reason="test")
        result = await client.execute(request("behavior.stop", "emergency"))
        assert result.status is ActionStatus.SUCCEEDED
        assert client.robot.system_safety.stopped
        # Clear test-only fault so test teardown does not mask its assertion.
        game._state["state"] = "idle"
        await client.close()

    asyncio.run(exercise())


def test_unknown_and_stopped_requests_do_not_preempt_game(tmp_path):
    async def exercise():
        client = client_for(tmp_path)
        await client.start()
        game = client.robot.distance_game
        game.stop = AsyncMock(return_value=game.status())
        result = await client.execute(request("unknown.capability"))
        assert result.status is ActionStatus.REJECTED
        game.stop.assert_not_awaited()
        client.robot.safety_state.latch_system("operator_stop")
        result = await client.execute(request("servo.move", "denied"))
        assert result.error.code == "SYSTEM_STOPPED"
        game.stop.assert_not_awaited()
        await client.close()

    asyncio.run(exercise())


def test_unavailable_game_does_not_block_existing_outputs(tmp_path):
    from ninjarobot_pi5_ide.models import ResourceHealth

    async def exercise():
        client = client_for(tmp_path)
        await client.start()
        client.robot.distance.health = AsyncMock(return_value=ResourceHealth.UNAVAILABLE)
        client.robot.buzzer.stop = AsyncMock()
        result = await client.execute(request("game.distance.run"))
        assert result.data["state"] == "unavailable"
        client.robot.buzzer.stop.assert_not_awaited()
        assert (
            await client.execute(request("display.clear", "clear"))
        ).status is ActionStatus.SUCCEEDED
        await client.close()

    asyncio.run(exercise())


def test_only_full_successful_recovery_clears_game_fault(tmp_path):
    async def exercise():
        client = client_for(tmp_path)
        await client.start()
        game = client.robot.distance_game
        game._state.update(state="faulted", reason="test")
        await client.robot.resume_motion(confirmed=True)
        assert game.status()["state"] == "faulted"
        original = client.robot.system_safety.resume_system
        client.robot.system_safety.resume_system = AsyncMock(
            side_effect=RuntimeError("health failed")
        )
        with pytest.raises(RuntimeError):
            await client.robot.resume_system(confirmed=True)
        assert game.status()["state"] == "faulted"
        client.robot.system_safety.resume_system = original
        await client.robot.resume_system(confirmed=True)
        assert game.status()["state"] == "idle"
        await client.close()

    asyncio.run(exercise())


def test_failed_silence_blocks_conflicting_actions_and_reports_fault(tmp_path):
    async def exercise():
        client = client_for(tmp_path)
        await client.start()
        game = client.robot.distance_game
        entered = asyncio.Event()

        async def loop(*_):
            entered.set()
            await asyncio.Event().wait()

        game._loop = loop
        running = asyncio.create_task(client.execute(request("game.distance.run")))
        await asyncio.wait_for(entered.wait(), 1)
        original = client.robot.buzzer.stop
        client.robot.buzzer.stop = AsyncMock(side_effect=RuntimeError("stop failed"))
        stopped = await client.execute(request("game.distance.stop", "stop"))
        assert stopped.status is ActionStatus.FAILED
        assert (await running).status is ActionStatus.FAILED
        assert game.status()["state"] == "faulted"
        client.robot.servo.move = AsyncMock(side_effect=AssertionError("unsafe movement"))
        result = await client.execute(
            request("servo.move", "move", {"endpoint": "gpio12", "target_angle": 90})
        )
        assert result.status is ActionStatus.REJECTED
        client.robot.servo.move.assert_not_awaited()
        assert client.robot._foreground_behaviors == 0
        client.robot.buzzer.stop = original
        await client.robot.resume_system(confirmed=True)
        await client.close()

    asyncio.run(exercise())
