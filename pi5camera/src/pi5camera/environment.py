"""Environment and dependency probes for pi5camera.

Simplified from the original 538-line version to a focused probe module.
No more runtime .pth file generation, startup hook code generation, or
custom MetaPathFinder injection.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from typing import Any


def is_raspberry_pi() -> bool:
    """Return whether the current system appears to be a Raspberry Pi."""
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/device-tree/model", "r") as f:
            return "raspberry pi" in f.read().lower()
    except OSError:
        return False


def is_module_available(module_name: str) -> bool:
    """Return whether a Python module can be imported in the current environment."""
    import importlib.util

    return importlib.util.find_spec(module_name) is not None


def check_rpicam_available() -> dict[str, Any]:
    """Check whether ``rpicam-hello`` or ``libcamera-hello`` is available."""
    for cmd in ("rpicam-hello", "libcamera-hello"):
        if shutil.which(cmd):
            try:
                result = subprocess.run(
                    [cmd, "--list-cameras"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                cameras_found = "Available cameras" in result.stdout
                return {
                    "available": cameras_found,
                    "command": cmd,
                    "output": result.stdout.strip()[:500],
                    "help_text": None if cameras_found else "No cameras detected by the system.",
                }
            except (OSError, subprocess.SubprocessError):
                continue
    return {
        "available": False,
        "command": None,
        "output": None,
        "help_text": (
            "Neither rpicam-hello nor libcamera-hello found. "
            "On Raspberry Pi OS, install with: sudo apt install -y rpicam-apps"
        ),
    }


def describe_camera_environment() -> dict[str, Any]:
    """Summarize camera and recognition backend readiness."""
    on_pi = is_raspberry_pi()
    picamera2_ok = is_module_available("picamera2")
    mediapipe_ok = is_module_available("mediapipe")
    cv2_ok = is_module_available("cv2")

    camera_state = "ready" if picamera2_ok else "missing"
    camera_help = None
    if not picamera2_ok and on_pi:
        camera_help = (
            "Picamera2 is not importable. Install with: "
            "sudo apt install -y python3-picamera2 python3-libcamera"
        )
    elif not picamera2_ok:
        camera_help = (
            "Picamera2 is only available on Raspberry Pi. Using stub backend on this machine."
        )

    # Recognition only requires OpenCV. MediaPipe is optional (enhances
    # detection accuracy but has no ARM64 Linux wheel).
    recognition_available = cv2_ok
    if cv2_ok and mediapipe_ok:
        recognition_state = "ready"
        detection_mode = "mediapipe"
    elif cv2_ok:
        recognition_state = "ready"
        detection_mode = "opencv_haar"
    else:
        recognition_state = "missing"
        detection_mode = "none"

    recognition_help = None
    if not cv2_ok:
        recognition_help = (
            "OpenCV is not installed. Install with: pip install opencv-python-headless"
        )
    elif not mediapipe_ok and not on_pi:
        recognition_help = (
            "MediaPipe is not installed (optional, improves accuracy). "
            "Install with: pip install mediapipe"
        )

    return {
        "is_raspberry_pi": on_pi,
        "python_executable": sys.executable,
        "camera_backend_available": picamera2_ok,
        "camera_backend_state": camera_state,
        "camera_backend_help_text": camera_help,
        "recognition_backend_available": recognition_available,
        "recognition_backend_state": recognition_state,
        "recognition_backend_help_text": recognition_help,
        "mediapipe_available": mediapipe_ok,
        "opencv_available": cv2_ok,
        "detection_mode": detection_mode,
    }
