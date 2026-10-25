from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from ninjarobot_pi5_ide.config import RobotConfig, load_robot_config
from ninjarobot_pi5_ide.config_import import (
    DiscoveredConfig,
    default_robot_config,
    import_pi5_configs,
    robot_config_to_toml,
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
        {
            "audio": {"input_device": "USB PnP Sound Device", "sample_rate": 44_100},
            "wakeword": {
                "model_path": "pi5mic/voiceinput/hey_Ninja.onnx",
                "threshold": 0.62,
                "vad_threshold": 0.25,
                "enable_noise_suppression": True,
                "inference_framework": "onnx",
            },
            "voiceinput": {
                "max_capture_seconds": 12.0,
                "silence_timeout_seconds": 1.5,
                "cooldown_seconds": 2.0,
                "vad_rms_threshold": 240,
            },
        },
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
    assert imported.voice_input.model_resource.startswith("package://")
    assert imported.voice_input.wake_threshold == 0.62
    assert imported.voice_input.wake_vad_threshold == 0.25
    assert imported.voice_input.noise_suppression_enabled is True
    assert imported.voice_input.max_command_seconds == 12.0
    assert imported.voice_input.silence_stop_seconds == 1.5
    assert imported.voice_input.cooldown_seconds == 2.0
    assert imported.voice_input.silence_rms_threshold == 240
    assert len(report) == 8
    assert {item.path: item.path.read_bytes() for item in discovered} == before


def test_saved_config_is_private_valid_and_no_overwrite(tmp_path: Path) -> None:
    destination = tmp_path / "private" / "config.toml"
    config = load_robot_config(EXAMPLE)

    saved = save_robot_config(config, destination, overwrite=False)

    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    assert load_robot_config(saved) == config
    with pytest.raises(FileExistsError, match="already exists"):
        save_robot_config(config, destination, overwrite=False)


def test_current_configuration_round_trip_preserves_phase_8_sections(tmp_path: Path) -> None:
    original = load_robot_config(EXAMPLE)
    destination = tmp_path / "config.toml"
    destination.write_text(robot_config_to_toml(original), encoding="utf-8")

    restored = load_robot_config(destination)

    assert restored == original
    assert restored.voice_input.enabled is False
    assert restored.remote_access.authtoken_env == "NGROK_AUTHTOKEN"
    assert restored.onboarding.qr_border_modules == 4


def test_phase_7_configuration_migrates_with_release_features_disabled(tmp_path: Path) -> None:
    phase_7 = load_robot_config(EXAMPLE).model_dump()
    for section in ("voice_input", "remote_access", "onboarding", "deployment"):
        phase_7.pop(section)
    phase_7_config = RobotConfig.model_validate(phase_7)

    assert phase_7_config.voice_input.enabled is False
    assert phase_7_config.remote_access.enabled is False
    assert phase_7_config.onboarding.enabled is False
    assert phase_7_config.deployment.auto_start_enabled is False


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


def test_import_sunfounder_and_pca9685_servo_configs(tmp_path: Path) -> None:
    sunfounder_servo = tmp_path / "sunfounder_servo.json"
    write_json(
        sunfounder_servo,
        {
            "__backend__": {
                "name": "sunfounder_robot_hat",
                "kwargs": {"bus_id": 1, "address": 20, "frequency_hz": 50},
            },
            "hat_pwm0": {"pulse_center": 1500},
            "hat_pwm1": {"pulse_center": 1500},
            "hat_pwm2": {"pulse_center": 1500},
        },
    )
    imported_sf, _ = import_pi5_configs(
        load_robot_config(EXAMPLE),
        [DiscoveredConfig("pi5servo", sunfounder_servo, True)],
    )
    assert imported_sf.hardware.servos.endpoints == ("hat_pwm0", "hat_pwm1", "hat_pwm2")
    assert imported_sf.behaviors.servo_roles["left_motor"] == "hat_pwm0"
    assert imported_sf.behaviors.servo_roles["right_motor"] == "hat_pwm1"
    assert imported_sf.speech_output.speaker_enable_gpio == 12
    assert imported_sf.hardware.power.enabled is True
    assert imported_sf.hardware.power.fuel_gauge_address == 0x14
    assert imported_sf.hardware.power.charging_gpio == 23

    toml_path = tmp_path / "sunfounder.toml"
    toml_path.write_text(robot_config_to_toml(imported_sf), encoding="utf-8")
    restored_sf = load_robot_config(toml_path)
    assert restored_sf == imported_sf

    pca_servo = tmp_path / "pca9685_servo.json"
    write_json(
        pca_servo,
        {
            "__backend__": {
                "name": "pca9685",
                "kwargs": {"bus_id": 1, "address": 64, "frequency_hz": 50},
            },
            "hat_pwm0": {"pulse_center": 1500},
            "hat_pwm1": {"pulse_center": 1500},
            "hat_pwm15": {"pulse_center": 1500},
        },
    )
    imported_pca, _ = import_pi5_configs(
        load_robot_config(EXAMPLE),
        [DiscoveredConfig("pi5servo", pca_servo, True)],
    )
    assert imported_pca.hardware.servos.endpoints == ("hat_pwm0", "hat_pwm1", "hat_pwm15")
    assert imported_pca.behaviors.servo_roles["left_motor"] == "hat_pwm0"
    assert imported_pca.behaviors.servo_roles["right_motor"] == "hat_pwm1"
    assert imported_pca.speech_output.speaker_enable_gpio is None
    assert imported_pca.hardware.power.enabled is False


def test_import_sunfounder_arbitrary_digital_and_pwm_pins(tmp_path: Path) -> None:
    buzzer = tmp_path / "buzzer.json"
    display = tmp_path / "display.json"
    servo = tmp_path / "servo.json"
    write_json(buzzer, {"pin": 17, "volume": 128})
    write_json(
        display,
        {
            "display_profile": "st7789v_2inch8",
            "dc_pin": 27,
            "rst_pin": 22,
            "backlight_pin": 6,
            "width": 240,
            "height": 320,
            "rotation": 90,
            "brightness": 75,
            "spi_speed_mhz": 32,
        },
    )
    write_json(
        servo,
        {
            "__backend__": {
                "name": "sunfounder_robot_hat",
                "kwargs": {"bus_id": 1, "address": 23, "frequency_hz": 50},
            },
            "hat_pwm10": {"pulse_center": 1500},
            "hat_pwm11": {"pulse_center": 1500},
        },
    )
    imported, _ = import_pi5_configs(
        default_robot_config(),
        [
            DiscoveredConfig("pi5buzzer", buzzer, True),
            DiscoveredConfig("pi5disp", display, True),
            DiscoveredConfig("pi5servo", servo, True),
        ],
    )
    assert imported.hardware.buzzer.gpio == 17
    assert imported.hardware.display.dc_gpio == 27
    assert imported.hardware.display.reset_gpio == 22
    assert imported.hardware.display.backlight_gpio == 6
    assert imported.hardware.servos.endpoints == ("hat_pwm10", "hat_pwm11")
    assert imported.behaviors.servo_roles["left_motor"] == "hat_pwm10"
    assert imported.behaviors.servo_roles["right_motor"] == "hat_pwm11"
    assert imported.hardware.power.fuel_gauge_address == 0x17
