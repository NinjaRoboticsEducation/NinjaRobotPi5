"""Camera backend helpers for pi5camera.

Provides a ``CameraBackend`` protocol, a ``Picamera2StillBackend`` for
Raspberry Pi hardware, and a ``StubCameraBackend`` for macOS
development and test automation.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Protocol

from pi5camera.errors import BackendNotAvailableError, CaptureError
from pi5camera.models import CaptureResult

SYSTEM_CAMERA_PYTHON = Path("/usr/bin/python3")
SYSTEM_CAMERA_TIMEOUT_SECONDS = 20.0
SYSTEM_CAMERA_RESULT_PREFIX = "PI5CAMERA_RESULT="
SYSTEM_CAMERA_BRIDGE = f"""
import json
import sys
from pathlib import Path

from pi5camera.core.camera_backend import Picamera2StillBackend

payload = json.load(sys.stdin)
with Picamera2StillBackend(
    width=payload["width"],
    height=payload["height"],
    warmup_seconds=payload["warmup_seconds"],
    use_preview=False,
    autofocus_mode=payload["autofocus_mode"],
) as backend:
    result = backend.capture(Path(payload["output_path"]))
print({SYSTEM_CAMERA_RESULT_PREFIX!r} + json.dumps(result.metadata))
"""


class CameraBackend(Protocol):
    """Protocol for camera capture backends."""

    def capture(self, output_path: Path) -> CaptureResult:
        """Capture one still image to the given path."""
        ...

    def close(self) -> None:
        """Release camera resources."""
        ...

    def __enter__(self) -> "CameraBackend": ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[type-arg]
        ...


class StubCameraBackend:
    """Generates a placeholder JPEG for macOS development and testing."""

    def __init__(self, *, width: int = 1280, height: int = 720) -> None:
        self._width = width
        self._height = height

    def capture(self, output_path: Path) -> CaptureResult:
        """Generate a solid-colour placeholder image."""
        from PIL import Image

        output_path = output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (self._width, self._height), color=(40, 40, 40))
        image.save(str(output_path), "JPEG")
        return CaptureResult(path=output_path, metadata={"stub": True})

    def close(self) -> None:
        """No-op for stub backend."""

    def __enter__(self) -> "StubCameraBackend":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[type-arg]
        self.close()


class Picamera2StillBackend:
    """Wrapper around Picamera2 still capture with context manager support."""

    def __init__(
        self,
        *,
        width: int,
        height: int,
        warmup_seconds: float,
        use_preview: bool,
        autofocus_mode: str,
    ) -> None:
        picam2_module = _import_picamera2_module()
        self._picam2 = picam2_module.Picamera2()
        self._width = int(width)
        self._height = int(height)
        self._warmup_seconds = max(0.0, float(warmup_seconds))
        self._use_preview = bool(use_preview)
        self._autofocus_mode = autofocus_mode

    def capture(self, output_path: Path) -> CaptureResult:
        """Capture one still image to the given path."""
        output_path = output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        config = self._picam2.create_still_configuration(main={"size": (self._width, self._height)})
        self._picam2.configure(config)
        if self._use_preview:
            try:
                preview_mod = _import_picamera2_module().Preview
                self._picam2.start_preview(preview_mod.NULL)
            except Exception:
                pass

        self._picam2.start()
        try:
            _apply_autofocus(self._picam2, self._autofocus_mode)
            if self._warmup_seconds > 0:
                time.sleep(self._warmup_seconds)
            metadata = self._picam2.capture_file(str(output_path))
        except Exception as exc:
            raise CaptureError(f"Camera capture failed: {exc}") from exc
        finally:
            try:
                self._picam2.stop()
            except Exception:
                pass

        return CaptureResult(path=output_path, metadata=dict(metadata or {}))

    def close(self) -> None:
        """Close camera resources."""
        try:
            self._picam2.close()
        except Exception:
            pass

    def __enter__(self) -> "Picamera2StillBackend":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[type-arg]
        self.close()


class SystemPythonPicamera2Backend:
    """Use Raspberry Pi OS Picamera2 bindings from an isolated project venv.

    Raspberry Pi OS intentionally ships Picamera2 and libcamera as apt-managed
    Python packages.  A normal ``uv`` virtual environment cannot import those
    packages, so this bounded bridge delegates only the still capture to the
    system interpreter while keeping the CLI and its writable state in the
    project environment.
    """

    def __init__(
        self,
        *,
        width: int,
        height: int,
        warmup_seconds: float,
        use_preview: bool,
        autofocus_mode: str,
    ) -> None:
        del use_preview  # A subprocess cannot safely own a GUI preview window.
        self._width = int(width)
        self._height = int(height)
        self._warmup_seconds = max(0.0, float(warmup_seconds))
        self._autofocus_mode = autofocus_mode
        self._source_root = Path(__file__).resolve().parents[2]
        self._environment = os.environ.copy()
        self._environment.pop("PYTHONHOME", None)
        self._environment.pop("VIRTUAL_ENV", None)
        self._environment["PYTHONPATH"] = str(self._source_root)
        self._probe()

    def _probe(self) -> None:
        if not SYSTEM_CAMERA_PYTHON.is_file():
            raise BackendNotAvailableError(
                "Raspberry Pi OS camera Python is missing at /usr/bin/python3."
            )
        completed = _run_system_camera(
            [
                str(SYSTEM_CAMERA_PYTHON),
                "-s",
                "-c",
                "import libcamera, picamera2; "
                "from pi5camera.core.camera_backend import Picamera2StillBackend",
            ],
            environment=self._environment,
            timeout=5.0,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise BackendNotAvailableError(
                "Raspberry Pi OS Picamera2 bridge is unavailable"
                + (f": {detail[-1000:]}" if detail else ".")
            )

    def capture(self, output_path: Path) -> CaptureResult:
        output_path = output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "width": self._width,
                "height": self._height,
                "warmup_seconds": self._warmup_seconds,
                "autofocus_mode": self._autofocus_mode,
                "output_path": str(output_path),
            }
        )
        completed = _run_system_camera(
            [str(SYSTEM_CAMERA_PYTHON), "-s", "-c", SYSTEM_CAMERA_BRIDGE],
            environment=self._environment,
            timeout=SYSTEM_CAMERA_TIMEOUT_SECONDS,
            input_text=payload,
        )
        if completed.returncode != 0 or not output_path.is_file():
            detail = (completed.stderr or completed.stdout).strip()
            raise CaptureError(
                "Raspberry Pi OS camera capture failed" + (f": {detail[-1000:]}" if detail else ".")
            )
        metadata: dict[str, Any] = {"system_python_bridge": True}
        for line in completed.stdout.splitlines():
            if line.startswith(SYSTEM_CAMERA_RESULT_PREFIX):
                try:
                    decoded = json.loads(line.removeprefix(SYSTEM_CAMERA_RESULT_PREFIX))
                    if isinstance(decoded, dict):
                        metadata.update(decoded)
                except json.JSONDecodeError:
                    pass
        return CaptureResult(path=output_path, metadata=metadata)

    def close(self) -> None:
        """Each bridged capture owns and closes its camera subprocess."""

    def __enter__(self) -> "SystemPythonPicamera2Backend":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[type-arg]
        self.close()


def _run_system_camera(
    command: list[str],
    *,
    environment: dict[str, str],
    timeout: float,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            input=input_text,
            timeout=timeout,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackendNotAvailableError(
            f"Raspberry Pi OS camera bridge could not run: {exc}"
        ) from exc


def _import_picamera2_module() -> Any:
    """Lazily import picamera2, raising a clear error if unavailable."""
    import importlib

    try:
        return importlib.import_module("picamera2")
    except ImportError as exc:
        raise BackendNotAvailableError(
            "Picamera2 could not be imported. "
            "On Raspberry Pi OS install it with: sudo apt install -y python3-picamera2 python3-libcamera. "
            "On macOS, set camera.backend to 'stub' in camera.json for development."
        ) from exc


def _apply_autofocus(picam2: Any, autofocus_mode: str) -> None:
    """Attempt to set the autofocus mode. Best-effort, silently ignored if unsupported."""
    import importlib

    normalized = str(autofocus_mode).strip().lower()
    if normalized in {"", "none"}:
        return
    try:
        controls_module = importlib.import_module("libcamera.controls")
    except ImportError:
        return
    mode_map = {
        "manual": getattr(controls_module.AfModeEnum, "Manual", None),
        "auto": getattr(controls_module.AfModeEnum, "Auto", None),
        "continuous": getattr(controls_module.AfModeEnum, "Continuous", None),
    }
    mode_value = mode_map.get(normalized)
    if mode_value is None:
        return
    try:
        picam2.set_controls({"AfMode": mode_value})
    except Exception:
        pass


def build_camera_backend(config: dict[str, Any]) -> CameraBackend:
    """Build the configured still-camera backend."""
    camera_config = config.get("camera", {})
    backend_name = str(camera_config.get("backend", "picamera2")).lower()

    width = int(camera_config.get("width", 1280))
    height = int(camera_config.get("height", 720))

    if backend_name == "stub":
        return StubCameraBackend(width=width, height=height)

    arguments = {
        "width": width,
        "height": height,
        "warmup_seconds": float(camera_config.get("warmup_seconds", 1.0)),
        "use_preview": bool(camera_config.get("use_preview", False)),
        "autofocus_mode": str(camera_config.get("autofocus_mode", "continuous")),
    }
    try:
        return Picamera2StillBackend(**arguments)
    except BackendNotAvailableError as direct_error:
        try:
            return SystemPythonPicamera2Backend(**arguments)
        except BackendNotAvailableError as bridge_error:
            raise BackendNotAvailableError(
                f"{direct_error} Raspberry Pi OS bridge check also failed: {bridge_error}"
            ) from bridge_error
