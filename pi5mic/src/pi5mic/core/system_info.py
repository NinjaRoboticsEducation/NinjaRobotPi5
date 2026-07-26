"""Host and Raspberry Pi diagnostics helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_RPI_MODEL_PATHS = (
    Path("/sys/firmware/devicetree/base/model"),
    Path("/proc/device-tree/model"),
)

_THROTTLED_FLAGS: tuple[tuple[int, str], ...] = (
    (0x1, "undervoltage detected"),
    (0x2, "Arm frequency capped"),
    (0x4, "currently throttled"),
    (0x8, "soft temperature limit active"),
    (0x10000, "undervoltage has occurred"),
    (0x20000, "Arm frequency capping has occurred"),
    (0x40000, "throttling has occurred"),
    (0x80000, "soft temperature limit has occurred"),
)


def read_raspberry_pi_model() -> str | None:
    """Return the Raspberry Pi model string when available."""
    for candidate in _RPI_MODEL_PATHS:
        try:
            raw = candidate.read_bytes()
        except OSError:
            continue
        text = raw.decode("utf-8", errors="ignore").replace("\x00", "").strip()
        if text:
            return text
    return None


def is_raspberry_pi() -> bool:
    """Return True when running on Raspberry Pi hardware."""
    model = read_raspberry_pi_model()
    return bool(model and "raspberry pi" in model.lower())


def read_linux_mem_available_mb() -> int | None:
    """Return MemAvailable in MiB on Linux when readable."""
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return None

    try:
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1]) // 1024
    except (OSError, ValueError):
        return None
    return None


def parse_vcgencmd_throttled(raw_output: str) -> tuple[str | None, list[str]]:
    """Parse `vcgencmd get_throttled` output into a hex string and issue list."""
    stripped = raw_output.strip()
    if "=" not in stripped:
        return None, []

    _, _, value = stripped.partition("=")
    try:
        throttled_value = int(value, 16)
    except ValueError:
        return None, []

    issues = [label for bit, label in _THROTTLED_FLAGS if throttled_value & bit]
    return value, issues


def read_raspberry_pi_throttled_state() -> tuple[str | None, list[str]]:
    """Return the current Raspberry Pi throttled hex value and decoded issues."""
    if not is_raspberry_pi():
        return None, []

    command = shutil.which("vcgencmd")
    if command is None:
        return None, []

    try:
        result = subprocess.run(
            [command, "get_throttled"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None, []

    if result.returncode != 0:
        return None, []
    return parse_vcgencmd_throttled(result.stdout)


def read_raspberry_pi_temperature_celsius() -> float | None:
    """Return the current SoC temperature on Raspberry Pi when available."""
    if not is_raspberry_pi():
        return None

    command = shutil.which("vcgencmd")
    if command is None:
        return None

    try:
        result = subprocess.run(
            [command, "measure_temp"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    output = result.stdout.strip()
    if "=" not in output:
        return None

    _, _, value = output.partition("=")
    value = value.replace("'C", "").strip()
    try:
        return float(value)
    except ValueError:
        return None
