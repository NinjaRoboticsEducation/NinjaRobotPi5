"""Read-only Pi5 configuration discovery and safe V4 config writing."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import RobotConfig, load_robot_config

DEFAULT_USER_CONFIG = Path("~/.config/ninjarobot_pi5/config.toml").expanduser()


@dataclass(frozen=True)
class DiscoveredConfig:
    """One standalone Pi5 configuration candidate."""

    library: str
    path: Path
    exists: bool


def default_robot_config() -> RobotConfig:
    """Return safe project defaults when no TOML file has been created."""
    return RobotConfig.model_validate(
        {
            "schema_version": 1,
            "providers": {
                "ollama": {
                    "kind": "ollama",
                    "model": "configured-by-user",
                    "enabled": True,
                }
            },
        }
    )


def load_effective_config(path: str | Path | None) -> RobotConfig:
    """Load an explicit config, user config, root example, or safe defaults."""
    if path is not None:
        return load_robot_config(path)
    if DEFAULT_USER_CONFIG.exists():
        return load_robot_config(DEFAULT_USER_CONFIG)
    root_example = Path.cwd() / "config" / "ninjarobot_pi5.toml.example"
    if root_example.exists():
        return load_robot_config(root_example)
    return default_robot_config()


def discover_pi5_configs(cwd: Path | None = None) -> list[DiscoveredConfig]:
    """List known standalone config locations without importing a driver."""
    current = (cwd or Path.cwd()).resolve()
    home = Path.home()
    candidates: dict[str, tuple[Path, ...]] = {
        "pi5buzzer": (
            home / ".config/pi5buzzer/buzzer.json",
            current / "buzzer.json",
        ),
        "pi5disp": (home / ".config/pi5disp/display.json",),
        "pi5servo": (
            home / ".config/pi5servo/servo.json",
            current / "servo.json",
        ),
        "pi5vl53l0x": (
            home / ".config/pi5vl53l0x/vl53l0x.json",
            current / "vl53l0x.json",
        ),
        "pi5camera": (
            home / ".config/pi5camera/camera.json",
            current / "camera.json",
        ),
        "pi5mic": (
            home / ".config/pi5mic/mic.json",
            current / "mic.json",
        ),
    }
    discovered: list[DiscoveredConfig] = []
    for library, paths in candidates.items():
        existing = next((path for path in paths if path.is_file()), None)
        selected = existing or paths[0]
        discovered.append(
            DiscoveredConfig(
                library=library,
                path=selected,
                exists=existing is not None,
            )
        )
    return discovered


def import_pi5_configs(
    base: RobotConfig,
    discovered: list[DiscoveredConfig],
) -> tuple[RobotConfig, list[str]]:
    """Import only hardware fields V4 understands; never rewrite source files."""
    payload = base.model_dump(mode="python")
    imported: list[str] = []
    for item in discovered:
        if not item.exists:
            continue
        data = _read_json_object(item.path)
        if item.library == "pi5buzzer":
            pin = data.get("pin")
            if isinstance(pin, int) and not isinstance(pin, bool):
                payload["hardware"]["buzzer"]["gpio"] = pin
                imported.append(f"pi5buzzer gpio from {item.path}")
        elif item.library == "pi5disp":
            mapping = {
                "dc_pin": "dc_gpio",
                "rst_pin": "reset_gpio",
                "backlight_pin": "backlight_gpio",
                "width": "width",
                "height": "height",
                "rotation": "rotation",
                "brightness": "brightness",
            }
            for source, target in mapping.items():
                if source in data:
                    payload["hardware"]["display"][target] = data[source]
            speed = data.get("spi_speed_mhz")
            if isinstance(speed, int) and not isinstance(speed, bool):
                payload["hardware"]["display"]["frequency_hz"] = speed * 1_000_000
            imported.append(f"pi5disp wiring from {item.path}")
        elif item.library == "pi5servo":
            payload["hardware"]["servos"]["calibration_file"] = str(item.path)
            imported.append(f"pi5servo calibration path from {item.path}")
        elif item.library == "pi5camera":
            camera = data.get("camera")
            if isinstance(camera, dict):
                for key in ("width", "height", "warmup_seconds", "autofocus_mode"):
                    if key in camera:
                        payload["hardware"]["camera"][key] = camera[key]
                imported.append(f"pi5camera capture profile from {item.path}")
        elif item.library == "pi5mic":
            audio = data.get("audio")
            if isinstance(audio, dict):
                selector = audio.get("input_device")
                if isinstance(selector, str) and selector.strip():
                    payload["hardware"]["microphone"]["device_selector"] = selector
                if "sample_rate" in audio:
                    payload["hardware"]["microphone"]["sample_rate_hz"] = audio["sample_rate"]
                if "channels" in audio:
                    payload["hardware"]["microphone"]["channels"] = audio["channels"]
                imported.append(f"pi5mic audio profile from {item.path}")
        elif item.library == "pi5vl53l0x":
            imported.append(
                f"pi5vl53l0x found at {item.path}; its calibration remains driver-owned"
            )
    return RobotConfig.model_validate(payload), imported


def save_robot_config(
    config: RobotConfig,
    destination: str | Path,
    *,
    overwrite: bool,
) -> Path:
    """Atomically save owner-private TOML without silently replacing a file."""
    target = Path(destination).expanduser()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.parent.is_symlink():
        raise ValueError("configuration directory must not be a symbolic link")
    target.parent.chmod(0o700)
    if target.exists() and not overwrite:
        raise FileExistsError(f"configuration already exists: {target}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".config-",
        suffix=".tmp",
        dir=target.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(robot_config_to_toml(config))
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, target)
        else:
            try:
                os.link(temporary, target)
            except FileExistsError as exc:
                raise FileExistsError(f"configuration already exists: {target}") from exc
            temporary.unlink()
        target.chmod(0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


def robot_config_to_toml(config: RobotConfig) -> str:
    """Serialize the strict, fixed V4 schema to readable TOML."""
    hardware = config.hardware
    behavior = config.behaviors
    lines = [
        f"schema_version = {config.schema_version}",
        "",
        "[hardware.buzzer]",
        f"enabled = {_toml(config.hardware.buzzer.enabled)}",
        f"gpio = {hardware.buzzer.gpio}",
        "",
        "[hardware.servos]",
        f"enabled = {_toml(hardware.servos.enabled)}",
        f"endpoints = {_toml(list(hardware.servos.endpoints))}",
        f"calibration_file = {_toml(hardware.servos.calibration_file)}",
        f"motion_enabled = {_toml(hardware.servos.motion_enabled)}",
        f"group_motion_enabled = {_toml(hardware.servos.group_motion_enabled)}",
        "",
        "[hardware.display]",
        f"enabled = {_toml(hardware.display.enabled)}",
        f"model = {_toml(hardware.display.model)}",
        f"width = {hardware.display.width}",
        f"height = {hardware.display.height}",
        f"spi_bus = {hardware.display.spi_bus}",
        f"spi_device = {hardware.display.spi_device}",
        f"frequency_hz = {hardware.display.frequency_hz}",
        f"dc_gpio = {hardware.display.dc_gpio}",
        f"reset_gpio = {hardware.display.reset_gpio}",
        f"backlight_gpio = {hardware.display.backlight_gpio}",
        f"rotation = {hardware.display.rotation}",
        f"brightness = {hardware.display.brightness}",
        "",
        "[hardware.i2c]",
        f"bus = {hardware.i2c.bus}",
        f"dfr0566_address = {hardware.i2c.dfr0566_address}",
        f"vl53l0x_address = {hardware.i2c.vl53l0x_address}",
        "",
        "[hardware.camera]",
        f"enabled = {_toml(hardware.camera.enabled)}",
        f"width = {hardware.camera.width}",
        f"height = {hardware.camera.height}",
        f"warmup_seconds = {hardware.camera.warmup_seconds}",
        f"autofocus_mode = {_toml(hardware.camera.autofocus_mode)}",
        f"media_directory = {_toml(hardware.camera.media_directory)}",
        f"retain_media_by_default = {_toml(hardware.camera.retain_media_by_default)}",
        "",
        "[hardware.microphone]",
        f"enabled = {_toml(hardware.microphone.enabled)}",
        f"device_selector = {_toml(hardware.microphone.device_selector)}",
        f"sample_rate_hz = {hardware.microphone.sample_rate_hz}",
        f"channels = {hardware.microphone.channels}",
        f"max_capture_seconds = {hardware.microphone.max_capture_seconds}",
        f"media_directory = {_toml(hardware.microphone.media_directory)}",
        f"retain_audio_by_default = {_toml(hardware.microphone.retain_audio_by_default)}",
        "",
        "[behaviors]",
        f"user_directory = {_toml(behavior.user_directory)}",
        f"safety_state_file = {_toml(behavior.safety_state_file)}",
        f"left_motor_role = {_toml(behavior.left_motor_role)}",
        f"right_motor_role = {_toml(behavior.right_motor_role)}",
        f"obstacle_threshold_mm = {behavior.obstacle_threshold_mm}",
        f"obstacle_consecutive_readings = {behavior.obstacle_consecutive_readings}",
        f"distance_poll_interval_seconds = {behavior.distance_poll_interval_seconds}",
        f"watchdog_timeout_seconds = {behavior.watchdog_timeout_seconds}",
        f"system_stopped_display_seconds = {behavior.system_stopped_display_seconds}",
        f"stop_on_invalid_distance = {_toml(behavior.stop_on_invalid_distance)}",
        "",
        "[behaviors.servo_roles]",
    ]
    lines.extend(f"{name} = {_toml(endpoint)}" for name, endpoint in behavior.servo_roles.items())
    lines.extend(
        [
            "",
            "[agent]",
            f"default_provider = {_toml(config.agent.default_provider)}",
            f"max_model_turns = {config.agent.max_model_turns}",
            f"max_tool_calls = {config.agent.max_tool_calls}",
            f"request_timeout_seconds = {config.agent.request_timeout_seconds}",
            f"model_inactivity_timeout_seconds = {config.agent.model_inactivity_timeout_seconds}",
        ]
    )
    for name, provider in config.providers.items():
        lines.extend(
            [
                "",
                f"[providers.{json.dumps(name)}]",
                f"kind = {_toml(provider.kind)}",
                f"model = {_toml(provider.model)}",
                f"enabled = {_toml(provider.enabled)}",
            ]
        )
        if provider.base_url is not None:
            lines.append(f"base_url = {_toml(provider.base_url)}")
        if provider.api_key_env is not None:
            lines.append(f"api_key_env = {_toml(provider.api_key_env)}")
    return "\n".join(lines) + "\n"


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to import {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"unable to import {path}: root must be a JSON object")
    return payload


def _toml(value: str | bool | list[str]) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(item) for item in value) + "]"
    return json.dumps(value)
