from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from ninjarobot_pi5_ide.config import BehaviorConfig
from ninjarobot_pi5_ide.face_renderer import render_face

from ninjarobot_pi5_ide import (
    BehaviorDefinition,
    BehaviorRunner,
    BuzzerDevice,
    DisplayDevice,
    RobotAssembly,
    load_robot_config,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"


class FakeDisplayDriver:
    def __init__(self, *, fail_write: bool = False) -> None:
        self.width = 320
        self.height = 240
        self.fail_write = fail_write
        self.frames: list[Any] = []
        self.brightness: list[int] = []
        self.closed = 0

    def display(self, image: Any) -> None:
        if self.fail_write:
            raise OSError("simulated SPI failure")
        self.frames.append(image.copy())

    def clear(self, _color: tuple[int, int, int]) -> None:
        return

    def set_brightness(self, percent: int) -> None:
        self.brightness.append(percent)

    def health_check(self) -> bool:
        return True

    def close(self) -> None:
        self.closed += 1


class FakeBuzzerDriver:
    def __init__(self) -> None:
        self._initialized = False
        self._volume = 0
        self.play_calls: list[tuple[int, float, int]] = []
        self.off_calls = 0

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value: int) -> None:
        self._volume = value

    def initialize(self) -> None:
        self._initialized = True

    def play_sound(self, frequency: int, duration: float) -> None:
        self.play_calls.append((frequency, duration, self._volume))

    def off(self) -> None:
        self.off_calls += 1
        self._initialized = False


def expression_definition(*, hold_seconds: float = 0.05) -> BehaviorDefinition:
    return BehaviorDefinition.model_validate(
        {
            "schema_version": 1,
            "name": "runtime_test",
            "description": "Exercise concurrent expression execution.",
            "category": "expression",
            "stages": [
                {
                    "name": "face",
                    "operations": [
                        {
                            "kind": "face",
                            "expression": "happy",
                            "hold_seconds": hold_seconds,
                        }
                    ],
                },
                {
                    "name": "text_and_sound",
                    "operations": [
                        {
                            "kind": "text",
                            "text": "Hello",
                            "hold_seconds": hold_seconds,
                        },
                        {
                            "kind": "melody",
                            "melody": "happy",
                            "volume": 32,
                        },
                    ],
                },
            ],
        }
    )


def build_runner(
    *,
    display_driver: FakeDisplayDriver | None = None,
    buzzer_driver: FakeBuzzerDriver | None = None,
) -> tuple[BehaviorRunner, FakeDisplayDriver, FakeBuzzerDriver]:
    display_driver = display_driver or FakeDisplayDriver()
    buzzer_driver = buzzer_driver or FakeBuzzerDriver()
    display = DisplayDevice(
        driver_factory=lambda **_settings: display_driver,
        simulated=True,
    )
    buzzer = BuzzerDevice(
        driver_factory=lambda _pin, _volume: buzzer_driver,
        simulated=True,
    )
    runner = BehaviorRunner(
        display=display,
        buzzer=buzzer,
        melody_provider=lambda _name: ((440, 0.01), (None, 0.01), (660, 0.01)),
    )
    return runner, display_driver, buzzer_driver


@pytest.mark.parametrize(
    "expression",
    ["idle", "happy", "thinking", "success", "warning", "error"],
)
def test_face_renderer_produces_exact_rgb_frame(expression: str) -> None:
    image = render_face(
        expression,  # type: ignore[arg-type]
        width=320,
        height=240,
        background="#000020",
        foreground="#FFFFFF",
        accent="#00BFFF",
    )

    assert image.mode == "RGB"
    assert image.size == (320, 240)
    assert image.getbbox() is not None


def test_expression_stages_run_in_order_and_stage_operations_overlap() -> None:
    async def exercise() -> None:
        runner, display, buzzer = build_runner()

        result = await runner.run(expression_definition())

        assert [stage["name"] for stage in result["stages"]] == [
            "face",
            "text_and_sound",
        ]
        assert len(display.frames) >= 3
        assert display.frames[0].size == (320, 240)
        assert buzzer.play_calls == [(440, 0.01, 32), (660, 0.01, 32)]
        assert result["simulated"] is True
        await runner.close()
        assert display.closed == 1
        assert buzzer.off_calls >= 1

    asyncio.run(exercise())


def test_face_animation_updates_until_cancelled() -> None:
    async def exercise() -> None:
        runner, display, _buzzer = build_runner()
        definition = expression_definition(hold_seconds=10.0)
        task = asyncio.create_task(runner.run(definition))
        for _ in range(200):
            if len(display.frames) >= 3:
                break
            await asyncio.sleep(0.005)

        assert len(display.frames) >= 3
        assert display.frames[0].tobytes() != display.frames[1].tobytes()
        await runner.stop()
        assert task.cancelled()
        await runner.close()

    asyncio.run(exercise())


def test_stop_cancels_active_expression_and_silences_buzzer() -> None:
    async def exercise() -> None:
        runner, display, buzzer = build_runner()
        await runner.start()
        task = asyncio.create_task(runner.run(expression_definition(hold_seconds=10.0)))
        for _ in range(100):
            if display.frames:
                break
            await asyncio.sleep(0.001)

        result = await runner.stop()

        assert result == {"stopped": True}
        assert task.cancelled()
        assert buzzer.off_calls >= 1
        await runner.close()

    asyncio.run(exercise())


def test_device_failure_cancels_stage_and_silences_buzzer() -> None:
    async def exercise() -> None:
        runner, _display, buzzer = build_runner(display_driver=FakeDisplayDriver(fail_write=True))
        await runner.start()

        with pytest.raises(Exception, match="display could not write"):
            await runner.run(expression_definition())

        assert buzzer.off_calls >= 1
        await runner.close()

    asyncio.run(exercise())


def test_robot_assembly_shares_expression_devices_and_blocks_unsafe_motion_start(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        display = FakeDisplayDriver()
        buzzer = FakeBuzzerDriver()
        config = load_robot_config(EXAMPLE)
        config = config.model_copy(
            update={
                "behaviors": BehaviorConfig(
                    user_directory=str(tmp_path / "behaviors"),
                    safety_state_file=str(tmp_path / "safety.json"),
                    clear_reading_timeout_seconds=1.0,
                    system_stopped_display_seconds=0.0,
                )
            }
        )
        robot = RobotAssembly(
            config=config,
            display_factory=lambda **_settings: display,
            buzzer_factory=lambda _pin, _volume: buzzer,
            melody_provider=lambda _name: ((440, 0.01),),
            simulated=True,
        )
        await robot.start()

        health = await robot.health()
        result = await robot.run_behavior("thinking")

        assert health == {"display": "ready", "buzzer": "ready"}
        assert result["name"] == "thinking"
        with pytest.raises(Exception, match="motion is disabled"):
            await robot.run_behavior("move_forward")
        await robot.close()

    asyncio.run(exercise())


def test_robot_liveliness_runs_greeting_then_supervises_silent_idle(tmp_path: Path) -> None:
    async def exercise() -> None:
        display = FakeDisplayDriver()
        buzzer = FakeBuzzerDriver()
        config = load_robot_config(EXAMPLE)
        config = config.model_copy(
            update={
                "behaviors": BehaviorConfig(
                    user_directory=str(tmp_path / "behaviors"),
                    safety_state_file=str(tmp_path / "safety.json"),
                    system_stopped_display_seconds=0.0,
                )
            }
        )
        robot = RobotAssembly(
            config=config,
            display_factory=lambda **_settings: display,
            buzzer_factory=lambda _pin, _volume: buzzer,
            melody_provider=lambda _name: ((440, 0.01),),
            simulated=True,
        )
        idle = BehaviorDefinition.model_validate(
            {
                "schema_version": 1,
                "name": "idle",
                "description": "Test idle face.",
                "category": "expression",
                "stages": [
                    {
                        "name": "idle_face",
                        "operations": [
                            {
                                "kind": "face",
                                "expression": "idle",
                                "hold_seconds": 0.05,
                            },
                            {"kind": "melody", "melody": "idle", "volume": 20},
                        ],
                    }
                ],
            }
        )
        greeting = expression_definition(hold_seconds=0.05).model_copy(update={"name": "greeting"})
        robot.assets = _LifecycleAssets(greeting=greeting, idle=idle)  # type: ignore[assignment]
        await robot.start()

        result = await robot.start_liveliness()
        assert result["name"] == "greeting"
        greeting_sound_count = len(buzzer.play_calls)
        frame_count = len(display.frames)
        await asyncio.sleep(0.22)

        assert len(display.frames) > frame_count
        assert len(buzzer.play_calls) == greeting_sound_count

        thinking = idle.model_copy(
            update={
                "name": "thinking",
                "stages": (
                    idle.stages[0].model_copy(
                        update={
                            "operations": (
                                idle.stages[0]
                                .operations[0]
                                .model_copy(update={"expression": "thinking"}),
                            )
                        }
                    ),
                ),
            }
        )
        robot.assets._definitions["thinking"] = thinking  # type: ignore[attr-defined]
        assert await robot.show_agent_face("thinking") is True
        await asyncio.sleep(0)
        assert robot._idle_task is not None  # type: ignore[attr-defined]
        assert robot._idle_task.get_name() == "ninjarobot-silent-thinking"  # type: ignore[attr-defined]

        await robot.run_definition(expression_definition(hold_seconds=0.05))
        frame_count = len(display.frames)
        await asyncio.sleep(0.12)
        assert len(display.frames) > frame_count
        assert robot._idle_task is not None  # type: ignore[attr-defined]
        assert robot._idle_task.get_name() == "ninjarobot-silent-thinking"  # type: ignore[attr-defined]

        assert await robot.restore_idle_face() is True
        await asyncio.sleep(0)
        assert robot._idle_task is not None  # type: ignore[attr-defined]
        assert robot._idle_task.get_name() == "ninjarobot-silent-idle"  # type: ignore[attr-defined]

        await robot.stop()
        frame_count = len(display.frames)
        await asyncio.sleep(0.12)
        assert len(display.frames) == frame_count
        await robot.close()

    asyncio.run(exercise())


class _LifecycleAssets:
    def __init__(
        self,
        *,
        greeting: BehaviorDefinition,
        idle: BehaviorDefinition,
    ) -> None:
        self._definitions = {"greeting": greeting, "idle": idle}

    def load(self, name: str) -> BehaviorDefinition:
        return self._definitions[name]
