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
    assert config.hardware.servos.calibration_file == "~/.config/pi5servo/servo.json"
    assert config.hardware.servos.motion_enabled is False
    assert config.hardware.servos.group_motion_enabled is False
    assert config.hardware.display.dc_gpio == 4
    assert config.hardware.display.reset_gpio == 5
    assert config.hardware.display.backlight_gpio == 6
    assert config.hardware.display.rotation == 90
    assert config.hardware.display.brightness == 75
    assert config.hardware.i2c.dfr0566_address == 0x10
    assert config.hardware.i2c.vl53l0x_address == 0x29
    assert config.hardware.camera.width == 1280
    assert config.hardware.camera.height == 720
    assert config.hardware.camera.warmup_seconds == 1.0
    assert config.hardware.camera.autofocus_mode == "none"
    assert config.hardware.camera.media_directory == "~/.local/share/ninjarobot_pi5/camera"
    assert config.hardware.camera.retain_media_by_default is False
    assert config.hardware.microphone.device_selector == "USB PnP Sound Device"
    assert config.hardware.microphone.sample_rate_hz == 16_000
    assert config.hardware.microphone.channels == 1
    assert config.hardware.microphone.max_capture_seconds == 10.0
    assert config.hardware.microphone.media_directory == "~/.local/share/ninjarobot_pi5/microphone"
    assert config.hardware.microphone.retain_audio_by_default is False
    assert config.behaviors.servo_roles == {
        "left_motor": "gpio12",
        "right_motor": "gpio13",
    }
    assert config.behaviors.obstacle_threshold_mm == 50
    assert config.behaviors.obstacle_consecutive_readings == 3
    assert config.behaviors.stop_on_invalid_distance is False
    assert config.agent.request_timeout_seconds == 600.0
    assert config.agent.model_inactivity_timeout_seconds == 120.0
    assert config.agent.fallback_providers == ()
    assert config.providers["ollama"].api_key_env is None
    assert config.providers["openai"].api_key_env == "OPENAI_API_KEY"
    assert config.providers["gemini"].api_key_env == "GEMINI_API_KEY"
    assert config.providers["anthropic"].api_key_env == "ANTHROPIC_API_KEY"


def test_configuration_path_expands_home_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    config_directory = tmp_path / ".config" / "ninjarobot_pi5"
    config_directory.mkdir(parents=True)
    config_path = config_directory / "config.toml"
    config_path.write_bytes(EXAMPLE.read_bytes())

    config = load_robot_config("~/.config/ninjarobot_pi5/config.toml")

    assert config.schema_version == 1


def test_configuration_migrates_legacy_agent_timeout() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["agent"].pop("request_timeout_seconds")
    payload["agent"].pop("model_inactivity_timeout_seconds")
    payload["agent"]["turn_timeout_seconds"] = 90.0

    config = RobotConfig.model_validate(payload)

    assert config.agent.request_timeout_seconds == 600.0
    assert config.agent.model_inactivity_timeout_seconds == 120.0


def test_configuration_rejects_unknown_fields_and_gpio_conflicts() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["display"]["mystery_pin"] = 99

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RobotConfig.model_validate(payload)

    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["buzzer"]["gpio"] = 4
    with pytest.raises(ValidationError, match="buzzer GPIO must not overlap"):
        RobotConfig.model_validate(payload)


def test_configuration_allows_supported_servo_topology_customization() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["servos"]["endpoints"] = ("gpio13", "gpio12", "hat_pwm1")
    payload["behaviors"]["servo_roles"] = {
        "left_motor": "gpio13",
        "right_motor": "gpio12",
    }

    config = RobotConfig.model_validate(payload)

    assert config.hardware.servos.endpoints == ("gpio13", "gpio12", "hat_pwm1")


@pytest.mark.parametrize(
    ("endpoints", "message"),
    [
        ((), "must not be empty"),
        (("gpio12", "gpio12"), "must not contain duplicates"),
        (("gpio12", "gpio99"), "unsupported servo endpoints"),
    ],
)
def test_configuration_rejects_invalid_servo_topology(
    endpoints: tuple[str, ...],
    message: str,
) -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["servos"]["endpoints"] = endpoints
    with pytest.raises(ValidationError, match=message):
        RobotConfig.model_validate(payload)


def test_configuration_permits_explicit_group_motion_gate() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["servos"]["group_motion_enabled"] = True

    config = RobotConfig.model_validate(payload)

    assert config.hardware.servos.group_motion_enabled is True


def test_configuration_rejects_behavior_roles_outside_servo_topology() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["behaviors"]["servo_roles"]["right_motor"] = "hat_pwm1"

    with pytest.raises(ValidationError, match="require configured endpoints"):
        RobotConfig.model_validate(payload)


def test_configuration_bounds_obstacle_policy() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["behaviors"]["obstacle_threshold_mm"] = 49

    with pytest.raises(ValidationError, match="greater than or equal to 50"):
        RobotConfig.model_validate(payload)

    payload = load_robot_config(EXAMPLE).model_dump()
    payload["behaviors"]["stop_on_invalid_distance"] = True
    with pytest.raises(ValidationError, match="Input should be False"):
        RobotConfig.model_validate(payload)


def test_configuration_keeps_default_camera_retention_disabled() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["camera"]["retain_media_by_default"] = True
    with pytest.raises(ValidationError, match="Input should be False"):
        RobotConfig.model_validate(payload)

    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["camera"]["autofocus_mode"] = "tracking"
    with pytest.raises(ValidationError, match="Input should be"):
        RobotConfig.model_validate(payload)


def test_configuration_bounds_microphone_capture_and_retention() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["microphone"]["retain_audio_by_default"] = True
    with pytest.raises(ValidationError, match="Input should be False"):
        RobotConfig.model_validate(payload)

    payload = load_robot_config(EXAMPLE).model_dump()
    payload["hardware"]["microphone"]["max_capture_seconds"] = 60.0
    with pytest.raises(ValidationError, match="less than or equal to 30"):
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


def test_cloud_oauth_configuration_rejects_unsupported_or_incomplete_login() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["providers"]["openai"]["auth_method"] = "oauth"
    with pytest.raises(ValidationError, match="does not support ChatGPT web login"):
        RobotConfig.model_validate(payload)

    payload = load_robot_config(EXAMPLE).model_dump()
    payload["providers"]["gemini"]["auth_method"] = "oauth"
    with pytest.raises(ValidationError, match="requires project_id"):
        RobotConfig.model_validate(payload)

    payload["providers"]["gemini"]["project_id"] = "robot-cloud-project"
    config = RobotConfig.model_validate(payload)
    assert config.providers["gemini"].auth_method == "oauth"


def test_fallback_providers_must_be_enabled_and_exclude_the_primary() -> None:
    payload = load_robot_config(EXAMPLE).model_dump()
    payload["agent"]["fallback_providers"] = ("openai", "gemini")
    config = RobotConfig.model_validate(payload)
    assert config.agent.fallback_providers == ("openai", "gemini")

    payload["agent"]["fallback_providers"] = ("ollama",)
    with pytest.raises(ValidationError, match="must not include the default"):
        RobotConfig.model_validate(payload)
