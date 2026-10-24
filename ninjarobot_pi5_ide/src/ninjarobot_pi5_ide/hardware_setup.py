"""IDE-owned handoff to approved standalone hardware setup tools."""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .config_import import default_robot_config, discover_pi5_configs, import_pi5_configs
from .hardware_ownership import DEFAULT_HARDWARE_LOCK, HardwareOwnership


@dataclass(frozen=True)
class HardwareSetupTool:
    component: str
    command: tuple[str, ...]
    configuration: Path
    required: bool
    moves_actuators: bool = False
    captures_media: bool = False


TOOLS: dict[str, HardwareSetupTool] = {
    "buzzer": HardwareSetupTool(
        "pi5buzzer", ("pi5buzzer", "buzzer-tool"), Path("~/.config/pi5buzzer/buzzer.json"), True
    ),
    "display": HardwareSetupTool(
        "pi5disp", ("pi5disp", "display-tool"), Path("~/.config/pi5disp/display.json"), True
    ),
    "distance": HardwareSetupTool(
        "pi5vl53l0x",
        ("pi5vl53l0x", "sensor-tool"),
        Path("~/.config/pi5vl53l0x/vl53l0x.json"),
        True,
    ),
    "servo": HardwareSetupTool(
        "pi5servo",
        ("pi5servo", "servo-tool"),
        Path("~/.config/pi5servo/servo.json"),
        True,
        moves_actuators=True,
    ),
    "camera": HardwareSetupTool(
        "pi5camera",
        ("pi5camera", "camera-tool"),
        Path("~/.config/pi5camera/camera.json"),
        True,
        captures_media=True,
    ),
    "microphone": HardwareSetupTool(
        "pi5mic",
        ("pi5mic", "mic-tool"),
        Path("~/.config/pi5mic/mic.json"),
        False,
        captures_media=True,
    ),
}


def hardware_setup_status(component: str) -> dict[str, object]:
    """Inspect executable and saved configuration without opening a device."""
    tool = _tool(component)
    executable = shutil.which(tool.command[0])
    discovered = next(item for item in discover_pi5_configs() if item.library == tool.component)
    configuration = discovered.path
    valid = False
    summary: dict[str, object] = {}
    problem = "No saved configuration found."
    if (
        configuration.is_file()
        and not configuration.is_symlink()
        and configuration.parent.resolve() == configuration.absolute().parent
    ):
        try:
            if configuration.stat().st_size > 1_048_576:
                raise ValueError("configuration is oversized")
            if not stat.S_ISREG(configuration.stat().st_mode):
                raise ValueError("configuration must be a regular file")
            data = json.loads(configuration.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not data:
                raise ValueError("configuration must contain settings")
            # Reuse the integrated schema for fields that the IDE consumes.
            from .config_import import DiscoveredConfig

            import_pi5_configs(
                default_robot_config(), [DiscoveredConfig(tool.component, configuration, True)]
            )
            fields = {
                "buzzer": ("pin", "volume"),
                "display": ("width", "height", "rotation", "brightness", "dc_pin", "rst_pin"),
                "distance": ("offset_mm",),
                "servo": ("12", "13", "gpio12", "gpio13"),
                "camera": ("camera",),
                "microphone": ("audio", "wakeword", "stt"),
            }[component]
            required = {
                "buzzer": "pin",
                "display": "width",
                "distance": "offset_mm",
                "camera": "camera",
                "microphone": "audio",
            }.get(component)
            if required and required not in data:
                raise ValueError(f"missing {required} settings")
            if component == "buzzer" and type(data["pin"]) is not int:
                raise ValueError("buzzer pin must be an integer")
            if component == "distance" and type(data["offset_mm"]) is not int:
                raise ValueError("distance offset must be an integer")
            if component == "servo":
                from pi5servo.config.config_manager import (  # type: ignore[import-untyped]
                    ConfigManager,
                )

                manager = ConfigManager(configuration)
                if not manager.load():
                    raise ValueError("unable to load servo calibration")
                backend_cfg = manager.get_backend_config()
                backend_name = str(backend_cfg.get("name", "auto") or "auto").lower()
                backend_addr = backend_cfg.get("kwargs", {}).get("address")
                is_hat_backend = backend_name in {
                    "sunfounder_robot_hat",
                    "sunfounder",
                    "robot_hat",
                    "pca9685",
                } or backend_addr in {0x14, 0x40, "0x14", "0x40"}
                all_calibrated = manager.get_all_endpoint_calibrations()

                if is_hat_backend or any(k.startswith("hat_pwm") for k in all_calibrated):
                    required_endpoints = ("hat_pwm0", "hat_pwm1")
                    for ep in required_endpoints:
                        ch_num = ep.removeprefix("hat_pwm")
                        entry = data.get(ep) or data.get(f"pwm{ch_num}") or data.get(f"p{ch_num}")
                        if not isinstance(entry, dict) or "pulse_center" not in entry:
                            raise ValueError("missing saved wheel neutral calibration")
                    if not set(required_endpoints) <= set(all_calibrated):
                        raise ValueError("calibrate both hat_pwm0 and hat_pwm1")
                    selected_calibrations = {
                        ep: cal for ep, cal in all_calibrated.items() if ep.startswith("hat_pwm")
                    }
                else:
                    for pin in (12, 13):
                        entry = data.get(str(pin), data.get(f"gpio{pin}"))
                        if not isinstance(entry, dict) or "pulse_center" not in entry:
                            raise ValueError("missing saved wheel neutral calibration")
                    calibrated = manager.get_all_calibrations()
                    if not {12, 13} <= set(calibrated):
                        raise ValueError("calibrate both GPIO12 and GPIO13")
                    selected_calibrations = {
                        str(pin): cal for pin, cal in calibrated.items() if pin in {12, 13}
                    }

                for calibration in selected_calibrations.values():
                    if (
                        not 500
                        <= calibration.pulse_min
                        < calibration.pulse_center
                        < calibration.pulse_max
                        <= 2500
                    ):
                        raise ValueError("invalid servo pulse calibration")
            if component == "microphone":
                _check_microphone_assets(data)
            # Only reviewed hardware fields are shown, never arbitrary JSON/credentials.
            for key in fields:
                if key in data and isinstance(data[key], (str, int, float, bool)):
                    summary[key] = data[key]
            if component in {"camera", "microphone"}:
                section = data.get("camera" if component == "camera" else "audio")
                if not isinstance(section, dict) or not section:
                    raise ValueError("missing capture profile")
                for key in ("width", "height", "sample_rate", "channels", "input_device"):
                    if key in section:
                        summary[key] = section[key]
            if component == "servo":
                summary = {
                    ep_key: {"pulse_center": cal.pulse_center, "speed": cal.speed}
                    for ep_key, cal in selected_calibrations.items()
                }
            valid = True
            problem = "Settings checked; physical operation has not been tested."
        except (OSError, ValueError, TypeError, KeyError, ImportError):
            problem = (
                "Saved settings are invalid or incomplete. Open the setup tool to repair them."
            )

    return {
        "component": tool.component,
        "executable": executable,
        "tool_available": executable is not None,
        "configuration": str(configuration),
        "configuration_saved": configuration.is_file() and not configuration.is_symlink(),
        "configuration_valid": valid,
        "summary": summary,
        "message": problem,
        "required": tool.required,
        "moves_actuators": tool.moves_actuators,
        "captures_media": tool.captures_media,
    }


def run_hardware_setup(
    component: str,
    *,
    ownership_path: Path = DEFAULT_HARDWARE_LOCK,
    runner: Callable[[Sequence[str]], int] | None = None,
) -> int:
    """Run one allowlisted driver tool while IDE owns the hardware lock."""
    tool = _tool(component)
    executable = shutil.which(tool.command[0])
    if executable is None:
        raise RuntimeError(f"{tool.command[0]} is not installed in PATH")
    command = (executable, *tool.command[1:])
    execute = runner or _run_attached
    ownership = HardwareOwnership(ownership_path)
    ownership.acquire()
    try:
        return execute(command)
    finally:
        ownership.release()


def _run_attached(command: Sequence[str]) -> int:
    return subprocess.run(command, check=False).returncode


def _tool(component: str) -> HardwareSetupTool:
    try:
        return TOOLS[component]
    except KeyError as exc:
        raise ValueError(f"unknown hardware setup component: {component}") from exc


def _check_microphone_assets(data: dict[str, object]) -> None:
    """Check standalone assets in a bounded child, preserving runtime import containment."""
    stt = data.get("stt")
    wake = data.get("wakeword")
    voice = data.get("voiceinput")
    if not isinstance(stt, dict) or stt.get("selected") != "whisper_cpp":
        raise ValueError("select whisper.cpp in the microphone setup tool")
    whisper = stt.get("whisper_cpp")
    if not isinstance(whisper, dict):
        raise ValueError("configure whisper.cpp")
    if (
        not isinstance(wake, dict)
        or not isinstance(voice, dict)
        or voice.get("enabled") is not True
    ):
        raise ValueError("configure Hey Ninja voice input")
    payload = {
        "command": whisper.get("command"),
        "model": whisper.get("model_path"),
        "wake_model": wake.get("model_path"),
    }
    if any(value is not None and not isinstance(value, str) for value in payload.values()):
        raise ValueError("asset paths must be text")
    try:
        result = subprocess.run(
            (sys.executable, "-m", "ninjarobot_pi5_ide.hardware_config_probe"),
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("microphone asset check could not finish") from exc
    if result.returncode:
        raise ValueError("microphone speech or wake model setup is incomplete")


HARDWARE_PROFILE_BACKENDS: dict[str, dict[str, object]] = {
    "dfr0566": {
        "name": "auto",
        "kwargs": {"bus_id": 1, "address": 16, "frequency_hz": 50},
    },
    "sunfounder_robot_hat": {
        "name": "sunfounder_robot_hat",
        "kwargs": {"bus_id": 1, "address": 20, "frequency_hz": 50},
    },
    "pca9685": {
        "name": "pca9685",
        "kwargs": {"bus_id": 1, "address": 64, "frequency_hz": 50},
    },
}


def apply_hardware_profile_preset(profile: str) -> Path:
    """Write the selected Expansion HAT backend preset into ``servo.json``."""
    if profile not in HARDWARE_PROFILE_BACKENDS:
        raise ValueError(f"unsupported hardware profile: {profile}")
    discovered = next(item for item in discover_pi5_configs() if item.library == "pi5servo")
    servo_path = discovered.path.expanduser().resolve()
    servo_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {}
    if servo_path.is_file() and not servo_path.is_symlink():
        try:
            loaded = json.loads(servo_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {}
    data["__backend__"] = dict(HARDWARE_PROFILE_BACKENDS[profile])
    servo_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return servo_path


async def configure_sunfounder_i2s_speaker(config_path: Path) -> str:
    """Enable GPIO12 amplifier, discover I2S sink, and persist in ``config.toml``."""
    from .audio_output import _set_speaker_amplifier, discover_i2s_output_node
    from .config_import import load_effective_config, save_robot_config

    _set_speaker_amplifier(12, True)
    node = await discover_i2s_output_node() or "alsa_output.platform-soc_sound.stereo-fallback"
    resolved_path = config_path.expanduser()
    current = load_effective_config(resolved_path if resolved_path.exists() else None)
    payload = current.model_dump()
    servos_endpoints = tuple(payload["hardware"]["servos"].get("endpoints") or ())
    if "gpio12" in servos_endpoints or "12" in servos_endpoints:
        payload["hardware"]["servos"]["endpoints"] = ("hat_pwm0", "hat_pwm1")
        roles = dict(payload["behaviors"].get("servo_roles") or {})
        roles["left_motor"] = "hat_pwm0"
        roles["right_motor"] = "hat_pwm1"
        payload["behaviors"]["servo_roles"] = roles
    payload["speech_output"]["enabled"] = True
    payload["speech_output"]["output_node"] = node
    payload["speech_output"]["speaker_enable_gpio"] = 12
    from .config import RobotConfig

    updated = RobotConfig.model_validate(payload)
    save_robot_config(updated, resolved_path, overwrite=resolved_path.exists())
    return node
