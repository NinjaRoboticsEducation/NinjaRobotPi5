from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ninjarobot_pi5_ide import RobotConfig, load_robot_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"


def test_example_configuration_matches_confirmed_wiring() -> None:
    config = load_robot_config(EXAMPLE)

    assert config.hardware.buzzer.gpio == 27
    assert config.hardware.servos.endpoints == ("gpio12", "gpio13")
    assert config.hardware.display.dc_gpio == 4
    assert config.hardware.display.reset_gpio == 5
    assert config.hardware.display.backlight_gpio == 6
    assert config.hardware.display.rotation == 90
    assert config.hardware.display.brightness == 75
    assert config.hardware.i2c.dfr0566_address == 0x10
    assert config.hardware.i2c.vl53l0x_address == 0x29
    assert config.hardware.camera.retain_media_by_default is False
    assert config.hardware.microphone.sample_rate_hz == 16_000
    assert config.hardware.microphone.retain_audio_by_default is False
    assert config.providers["ollama"].api_key_env is None


def test_configuration_rejects_unknown_fields_and_gpio_conflicts() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["display"]["mystery_pin"] = 99

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RobotConfig.model_validate(payload)

    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["buzzer"]["gpio"] = 4
    with pytest.raises(ValidationError, match="buzzer GPIO must not overlap"):
        RobotConfig.model_validate(payload)


def test_configuration_rejects_disabled_default_provider() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["providers"]["ollama"]["enabled"] = False

    with pytest.raises(ValidationError, match="default_provider must be enabled"):
        RobotConfig.model_validate(payload)


def test_enabled_cloud_provider_requires_environment_secret_reference() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["providers"]["cloud"] = {
        "kind": "openai",
        "model": "configured-by-user",
        "enabled": True,
    }

    with pytest.raises(ValidationError, match="require api_key_env"):
        RobotConfig.model_validate(payload)
