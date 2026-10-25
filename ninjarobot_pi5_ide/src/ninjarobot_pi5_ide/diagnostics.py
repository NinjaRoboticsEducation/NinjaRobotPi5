"""Read-only environment checks; never import drivers or open devices."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import HardwareConfig, RobotConfig

_DEFAULT_FIND_SPEC = importlib.util.find_spec


def _find_system_camera_spec(name: str) -> str | None:
    """Check Raspberry Pi OS /usr/bin/python3 for system camera packages used by camera.py."""
    if name not in {"picamera2", "libcamera"}:
        return None
    if importlib.util.find_spec is not _DEFAULT_FIND_SPEC:
        return None
    system_python = Path("/usr/bin/python3")
    if not system_python.is_file():
        return None
    try:
        completed = subprocess.run(
            [
                str(system_python),
                "-s",
                "-c",
                f"import importlib.util; s = importlib.util.find_spec({name!r}); "
                "print(s.origin or '' if s else '')",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    origin = completed.stdout.strip()
    return origin or None


def diagnose_environment(
    *, profile: str = "hardware", config: RobotConfig | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Inspect the interpreter actually running this call, without repairing it."""
    if profile not in {"hardware", "development"}:
        raise ValueError("profile must be hardware or development")
    checks: list[dict[str, str]] = []
    repair = (
        "From the checkout run uv sync --frozen --extra hardware; then run commands "
        "with .venv/bin/python or uv run --frozen --no-sync to preserve hardware extras."
        if profile == "hardware"
        else "Run ./install.sh --profile development; use .venv-dev/bin/python."
    )

    def check(name: str, passed: bool, detail: str, remedy: str = repair) -> None:
        checks.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail,
                "remedy": "" if passed else remedy,
            }
        )

    check("python", (3, 11) <= sys.version_info[:2] < (3, 14), platform.python_version())
    modules = {"ninjarobot_pi5_ide", "ninjarobot_pi5_agent"}
    if profile == "development":
        modules.update({"pytest", "ruff", "mypy"})
    else:
        check(
            "platform",
            platform.system() == "Linux" and platform.machine() == "aarch64",
            f"{platform.system()} {platform.machine()}",
            "Hardware operation requires 64-bit Raspberry Pi 5 OS; use development on other hosts.",
        )
        hardware = config.hardware if config else HardwareConfig()
        modules.update({"pi5vl53l0x", "smbus2"})
        if hardware.display.enabled:
            modules.update({"pi5disp", "spidev", "lgpio"})
        if hardware.buzzer.enabled:
            modules.update({"pi5buzzer", "lgpio"})
        if hardware.servos.enabled:
            modules.update({"pi5servo", "rpi_hardware_pwm", "adafruit_pca9685"})
        if hardware.camera.enabled:
            modules.update({"pi5camera", "picamera2", "libcamera"})
        if hardware.microphone.enabled:
            modules.update({"pi5mic", "sounddevice"})
        if config and config.voice_input.enabled:
            modules.update({"openwakeword", "onnxruntime"})
        if config and config.remote_access.enabled:
            modules.add("pyngrok")
    for name in sorted(modules):
        try:
            spec = importlib.util.find_spec(name)
            origin = None if spec is None else spec.origin
        except (ImportError, ValueError, OSError):
            origin = None
        if origin is None and name in {"picamera2", "libcamera"}:
            origin = _find_system_camera_spec(name)
        found = origin is not None
        if found and root is not None and name.startswith("pi5"):
            expected = (root / name / "src" / name).resolve()
            found = Path(str(origin)).resolve().is_relative_to(expected)
        remedy = repair
        if name in {"picamera2", "libcamera"}:
            remedy = (
                "Use ./install.sh --check to inspect OS camera prerequisites; after review, "
                "use scripts/bootstrap-rpi-camera-workspace.sh to repair the camera bridge."
            )
        check(
            name, found, str(origin) if origin else "Not discoverable in this interpreter", remedy
        )
    if profile == "hardware":
        for name in ("aplay", "arecord"):
            location = shutil.which(name)
            check(
                name,
                location is not None,
                location or "OS audio command missing",
                "Review ./install.sh --check for required OS audio packages.",
            )
    return {
        "profile": profile,
        "python": sys.executable,
        "environment": sys.prefix,
        "configuration": "provided" if config else "default device requirements",
        "ok": all(item["status"] == "pass" for item in checks),
        "checks": checks,
        "limitations": (
            "Package discovery does not prove imports, native-library compatibility, Pi model, "
            "wiring, permissions, calibration or physical device health. No hardware was opened."
        ),
    }
