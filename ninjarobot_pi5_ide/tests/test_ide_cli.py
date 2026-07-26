from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from ninjarobot_pi5_ide.cli import main
from ninjarobot_pi5_ide.config import BehaviorConfig, RobotConfig, load_robot_config
from ninjarobot_pi5_ide.config_import import save_robot_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"


def private_config(tmp_path: Path) -> Path:
    config = load_robot_config(EXAMPLE)
    config = config.model_copy(
        update={
            "behaviors": BehaviorConfig(
                user_directory=str(tmp_path / "behaviors"),
                safety_state_file=str(tmp_path / "safety.json"),
                distance_poll_interval_seconds=0.02,
                system_stopped_display_seconds=0.0,
            )
        }
    )
    path = tmp_path / "config.toml"
    save_robot_config(config, path, overwrite=False)
    return path


def invoke(runner: CliRunner, config: Path, *arguments: str, input: str | None = None):
    return runner.invoke(
        main,
        ["--config", str(config), *arguments],
        input=input,
        catch_exceptions=False,
    )


def test_list_show_and_configuration_only_status(tmp_path: Path) -> None:
    runner = CliRunner()
    config = private_config(tmp_path)

    listed = invoke(runner, config, "behavior", "list")
    shown = invoke(runner, config, "behavior", "show", "greeting")
    health = invoke(runner, config, "behavior", "health")
    status = invoke(runner, config, "hardware", "status")

    assert listed.exit_code == 0
    assert "move_forward" in [item["name"] for item in json.loads(listed.output)]
    assert json.loads(shown.output)["stages"][1]["name"] == "greeting_text_and_sound"
    assert json.loads(health.output)["components"]["display"] == "ready"
    status_payload = json.loads(status.output)
    assert status_payload["mode"] == "configuration-only"
    assert status_payload["servo_roles"] == {
        "left_motor": "gpio12",
        "right_motor": "gpio13",
    }
    assert status_payload["safety"]["motion_latched"] is False


def test_simulated_movement_is_bounded_and_uses_approved_targets(
    tmp_path: Path,
) -> None:
    result = invoke(
        CliRunner(),
        private_config(tmp_path),
        "behavior",
        "simulate",
        "move_forward",
        "--duration",
        "0.1",
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    drive = next(
        operation
        for operation in payload["stages"][0]["operations"]
        if operation["kind"] == "drive"
    )
    assert drive["resolved_endpoints"] == {"gpio12": 45.0, "gpio13": -45.0}
    assert drive["stop_reason"] == "movement_duration_complete"
    assert payload["simulated"] is True


def test_real_movement_requires_explicit_confirmation_before_hardware(
    tmp_path: Path,
) -> None:
    result = invoke(
        CliRunner(),
        private_config(tmp_path),
        "behavior",
        "run",
        "move_forward",
        "--real",
    )

    assert result.exit_code == 2
    assert "real movement requires --confirm-motion" in result.output


def test_create_validates_previews_confirms_and_saves_private_asset(
    tmp_path: Path,
) -> None:
    config = private_config(tmp_path)
    source = tmp_path / "custom.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "my_message",
                "description": "Show one private message.",
                "category": "expression",
                "stages": [
                    {
                        "name": "message",
                        "operations": [
                            {
                                "kind": "text",
                                "text": "My robot",
                                "hold_seconds": 0.05,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    created = invoke(
        CliRunner(),
        config,
        "behavior",
        "create",
        "--from-file",
        str(source),
        "--confirm-save",
    )

    assert created.exit_code == 0
    saved = tmp_path / "behaviors" / "my_message.json"
    assert saved.is_file()
    assert "simulation" not in saved.read_text(encoding="utf-8")
    shown = invoke(CliRunner(), config, "behavior", "show", "my_message")
    assert json.loads(shown.output)["description"] == "Show one private message."


def test_validate_and_friendly_path_error(tmp_path: Path) -> None:
    config = private_config(tmp_path)
    invalid = invoke(CliRunner(), config, "behavior", "show", "../../secret")

    assert invalid.exit_code == 1
    assert "behavior name must start" in invalid.output
    assert "Traceback" not in invalid.output


def test_interactive_menu_can_exit_without_hardware(tmp_path: Path) -> None:
    result = invoke(CliRunner(), private_config(tmp_path), input="q\n")

    assert result.exit_code == 0
    assert "Simulation is the default" in result.output


def test_motion_resume_requires_confirmation_and_clears_level_one(
    tmp_path: Path,
) -> None:
    config_path = private_config(tmp_path)
    config = load_robot_config(config_path)
    from ninjarobot_pi5_ide import SafetyStateStore

    SafetyStateStore(config.behaviors.safety_state_file).latch_motion("front_obstacle")

    refused = invoke(CliRunner(), config_path, "motion", "resume")
    resumed = invoke(CliRunner(), config_path, "motion", "resume", "--confirm")

    assert refused.exit_code == 2
    assert json.loads(resumed.output)["motion_latched"] is False


def test_private_config_written_by_cli_serializer_round_trips(tmp_path: Path) -> None:
    config_path = private_config(tmp_path)

    loaded = load_robot_config(config_path)

    assert isinstance(loaded, RobotConfig)
    assert loaded.hardware.servos.endpoints == ("gpio12", "gpio13")
    assert loaded.behaviors.user_directory == str(tmp_path / "behaviors")
