from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from ninjarobot_pi5_ide.config import BehaviorConfig
from ninjarobot_pi5_ide.models import ResourceHealth

from ninjarobot_pi5_ide import IDEError, RobotAssembly, load_robot_config

EXAMPLE = Path(__file__).resolve().parents[2] / "config/ninjarobot_pi5.toml.example"


def test_disabled_devices_never_initialize_and_do_not_block_resume(tmp_path: Path) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("disabled device factory called")

    async def exercise() -> None:
        base = load_robot_config(EXAMPLE)
        hardware = base.hardware.model_copy(
            update={
                name: getattr(base.hardware, name).model_copy(update={"enabled": False})
                for name in ("servos", "display", "buzzer", "camera", "microphone")
            }
        )
        config = base.model_copy(
            update={
                "hardware": hardware,
                "behaviors": BehaviorConfig(
                    user_directory=str(tmp_path / "behaviors"),
                    safety_state_file=str(tmp_path / "safety.json"),
                    system_stopped_display_seconds=0,
                ),
            }
        )
        robot = RobotAssembly(
            config=config,
            simulated=True,
            display_factory=forbidden,
            buzzer_factory=forbidden,
            servo_factory=forbidden,
            camera_factory=forbidden,
            microphone_factory=forbidden,
        )
        try:
            await robot.start()
            await robot.servo.start()
            for device in (robot.display, robot.buzzer, robot.servo):
                assert await device.health() is ResourceHealth.UNAVAILABLE
            with pytest.raises(IDEError, match="disabled"):
                await robot.display.clear(color="#000000")
            with pytest.raises(IDEError, match="disabled"):
                await robot.buzzer.play(frequency_hz=440, duration_seconds=0.05, volume=32)
            with pytest.raises(IDEError, match="disabled"):
                await robot.servo.move(endpoint="gpio12", target_angle=10, speed_mode="S")
            with pytest.raises(IDEError, match="disabled"):
                await robot.display.recover()
            with pytest.raises(IDEError, match="disabled"):
                await robot.buzzer.recover()
            with pytest.raises(IDEError, match="disabled"):
                await robot.run_behavior("greeting")
            assert not robot.safety_state.read().system_latched
            await robot.stop()
            await robot.resume_system(confirmed=True)
            assert not robot.system_safety.stopped
        finally:
            await robot.close()

    asyncio.run(exercise())
