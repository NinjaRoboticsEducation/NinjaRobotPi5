"""IDE-owned handoff to approved standalone hardware setup tools."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

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
    configuration = tool.configuration.expanduser()
    return {
        "component": tool.component,
        "executable": executable,
        "tool_available": executable is not None,
        "configuration": str(configuration),
        "configuration_saved": configuration.is_file() and not configuration.is_symlink(),
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
