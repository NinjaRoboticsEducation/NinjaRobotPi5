from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from ninjarobot_pi5_ide.config import load_robot_config
from ninjarobot_pi5_ide.config_import import (
    DiscoveredConfig,
    default_robot_config,
    import_pi5_configs,
    save_robot_config,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"


def test_new_private_config_includes_local_and_cloud_provider_choices() -> None:
    config = default_robot_config()

    assert set(config.providers) == {"ollama", "openai", "gemini", "anthropic"}
    assert config.agent.default_provider == "ollama"


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_import_reads_supported_fields_and_never_rewrites_sources(tmp_path: Path) -> None:
    buzzer = tmp_path / "buzzer.json"
    display = tmp_path / "display.json"
    servo = tmp_path / "servo.json"
    camera = tmp_path / "camera.json"
    microphone = tmp_path / "mic.json"
    distance = tmp_path / "vl53l0x.json"
    write_json(buzzer, {"pin": 27, "volume": 64})
    write_json(
        display,
        {
            "dc_pin": 4,
            "rst_pin": 5,
            "backlight_pin": 6,
            "width": 240,
            "height": 320,
            "rotation": 90,
            "brightness": 75,
            "spi_speed_mhz": 32,
        },
    )
    write_json(servo, {"gpio12": {}, "gpio13": {}})
    write_json(camera, {"camera": {"width": 640, "height": 480}})
    write_json(
        microphone,
        {"audio": {"input_device": "USB PnP Sound Device", "sample_rate": 44_100}},
    )
    write_json(distance, {"offset_mm": 2})
    discovered = [
        DiscoveredConfig("pi5buzzer", buzzer, True),
        DiscoveredConfig("pi5disp", display, True),
        DiscoveredConfig("pi5servo", servo, True),
        DiscoveredConfig("pi5camera", camera, True),
        DiscoveredConfig("pi5mic", microphone, True),
        DiscoveredConfig("pi5vl53l0x", distance, True),
    ]
    before = {item.path: item.path.read_bytes() for item in discovered}

    imported, report = import_pi5_configs(load_robot_config(EXAMPLE), discovered)

    assert imported.hardware.buzzer.gpio == 27
    assert imported.hardware.display.dc_gpio == 4
    assert imported.hardware.servos.calibration_file == str(servo)
    assert imported.hardware.camera.width == 640
    assert imported.hardware.microphone.sample_rate_hz == 44_100
    assert len(report) == 6
    assert {item.path: item.path.read_bytes() for item in discovered} == before


def test_saved_config_is_private_valid_and_no_overwrite(tmp_path: Path) -> None:
    destination = tmp_path / "private" / "config.toml"
    config = load_robot_config(EXAMPLE)

    saved = save_robot_config(config, destination, overwrite=False)

    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    assert load_robot_config(saved) == config
    with pytest.raises(FileExistsError, match="already exists"):
        save_robot_config(config, destination, overwrite=False)


def test_import_rejects_invalid_json_without_changing_destination(tmp_path: Path) -> None:
    invalid = tmp_path / "buzzer.json"
    invalid.write_text("{bad", encoding="utf-8")
    destination = tmp_path / "config.toml"

    with pytest.raises(ValueError, match="unable to import"):
        import_pi5_configs(
            load_robot_config(EXAMPLE),
            [DiscoveredConfig("pi5buzzer", invalid, True)],
        )

    assert not destination.exists()
