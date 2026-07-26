"""Privacy-bounded still-camera integration for the managed ``pi5camera`` library."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import unquote, urlparse

from .errors import IDEError
from .models import (
    CapabilityDescriptor,
    ErrorDetails,
    ResourceHealth,
    RetrySafety,
    RiskLevel,
)

CAMERA_RESOURCES = ("camera",)
CAMERA_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.jpg$")
CAMERA_CAPTURE_TIMEOUT_SECONDS = 20.0
SYSTEM_CAMERA_PYTHON = Path("/usr/bin/python3")
SYSTEM_CAMERA_PROBE_TIMEOUT_SECONDS = 5.0
SYSTEM_CAMERA_CAPTURE_TIMEOUT_SECONDS = 18.0
SYSTEM_CAMERA_RESULT_PREFIX = "NINJAROBOT_CAMERA_RESULT="
SYSTEM_CAMERA_BRIDGE = f"""
import json
import sys
from pathlib import Path

from pi5camera.core.capture import capture_photo

payload = json.load(sys.stdin)
result = capture_photo(
    payload["config"],
    output_path=Path(payload["output_path"]),
    filename_prefix=payload["filename_prefix"],
)
print({SYSTEM_CAMERA_RESULT_PREFIX!r} + json.dumps({{"path": str(result.path)}}))
"""


class CameraCaptureResult(Protocol):
    """Minimum result surface returned by ``pi5camera.capture_photo``."""

    path: Path
    metadata: dict[str, Any]


class CameraCapture(Protocol):
    """Managed-driver still-capture callable."""

    def __call__(
        self,
        config: dict[str, Any],
        *,
        output_path: Path | None = None,
        filename_prefix: str = "photo",
    ) -> CameraCaptureResult: ...


CameraFactory = Callable[[], CameraCapture]


class _CaptureCancelledInWorker(Exception):
    """Signal that cleanup completed after cancellation reached a worker thread."""


@dataclass(slots=True)
class _BridgeCaptureResult:
    """Minimal managed-driver result returned across the interpreter boundary."""

    path: Path
    metadata: dict[str, Any]


def _managed_pi5camera_source_root() -> Path:
    """Locate the managed ``pi5camera`` source used by this workspace."""
    try:
        distribution = importlib.metadata.distribution("pi5camera")
        direct_url_text = distribution.read_text("direct_url.json")
        if direct_url_text is not None:
            direct_url = json.loads(direct_url_text)
            parsed_url = urlparse(direct_url.get("url", ""))
            if parsed_url.scheme == "file":
                project_directory = Path(unquote(parsed_url.path)).resolve()
                source_root = project_directory / "src"
                if (source_root / "pi5camera" / "core" / "capture.py").is_file():
                    return source_root
    except (
        importlib.metadata.PackageNotFoundError,
        json.JSONDecodeError,
        OSError,
        TypeError,
    ):
        pass

    for parent in Path(__file__).resolve().parents:
        source_root = parent / "pi5camera" / "src"
        if (source_root / "pi5camera" / "core" / "capture.py").is_file():
            return source_root

    spec = importlib.util.find_spec("pi5camera")
    locations = spec.submodule_search_locations if spec is not None else None
    if not locations:
        raise ImportError("the managed pi5camera package is not installed")
    for location in locations:
        source_root = Path(location).resolve().parent
        if (
            source_root.name == "src"
            and (source_root / "pi5camera" / "core" / "capture.py").is_file()
        ):
            return source_root
    raise ImportError("the managed pi5camera project source could not be located outside .venv")


def _system_camera_environment(source_root: Path) -> dict[str, str]:
    """Build a bounded environment for the Raspberry Pi OS camera interpreter."""
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("VIRTUAL_ENV", None)
    environment["PYTHONPATH"] = str(source_root)
    return environment


class _SystemPythonCameraCapture:
    """Run managed ``pi5camera`` capture with Raspberry Pi OS camera bindings."""

    def __init__(self, python: Path, source_root: Path) -> None:
        self._python = python
        self._source_root = source_root
        self._environment = _system_camera_environment(source_root)

    @classmethod
    def create(cls) -> _SystemPythonCameraCapture:
        """Create and probe the bridge without opening the physical camera."""
        if not SYSTEM_CAMERA_PYTHON.is_file():
            raise ImportError(f"Raspberry Pi OS camera Python is missing: {SYSTEM_CAMERA_PYTHON}")
        capture = cls(SYSTEM_CAMERA_PYTHON, _managed_pi5camera_source_root())
        capture._probe()
        return capture

    def _probe(self) -> None:
        command = [
            str(self._python),
            "-s",
            "-c",
            "import libcamera, picamera2; from pi5camera.core.capture import capture_photo",
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=SYSTEM_CAMERA_PROBE_TIMEOUT_SECONDS,
                env=self._environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ImportError(f"could not probe Raspberry Pi OS camera Python: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise ImportError(
                "Raspberry Pi OS camera imports failed" + (f": {detail[-1000:]}" if detail else "")
            )

    def __call__(
        self,
        config: dict[str, Any],
        *,
        output_path: Path | None = None,
        filename_prefix: str = "photo",
    ) -> CameraCaptureResult:
        if output_path is None:
            raise ValueError("system camera bridge requires an explicit output path")
        payload = json.dumps(
            {
                "config": config,
                "output_path": str(output_path),
                "filename_prefix": filename_prefix,
            }
        )
        try:
            result = subprocess.run(
                [str(self._python), "-s", "-c", SYSTEM_CAMERA_BRIDGE],
                check=False,
                capture_output=True,
                text=True,
                input=payload,
                timeout=SYSTEM_CAMERA_CAPTURE_TIMEOUT_SECONDS,
                env=self._environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Raspberry Pi OS camera capture exceeded 18 seconds") from exc
        except OSError as exc:
            raise RuntimeError(f"could not start Raspberry Pi OS camera capture: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(
                "Raspberry Pi OS camera capture failed" + (f": {detail[-1000:]}" if detail else "")
            )
        result_line = next(
            (
                line
                for line in reversed(result.stdout.splitlines())
                if line.startswith(SYSTEM_CAMERA_RESULT_PREFIX)
            ),
            None,
        )
        if result_line is None:
            raise RuntimeError("Raspberry Pi OS camera bridge returned no result")
        try:
            result_payload = json.loads(result_line.removeprefix(SYSTEM_CAMERA_RESULT_PREFIX))
            captured_path = Path(result_payload["path"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Raspberry Pi OS camera bridge returned an invalid result") from exc
        return _BridgeCaptureResult(path=captured_path, metadata={})


def _load_in_process_camera_capture() -> CameraCapture:
    """Load Picamera2 and the managed driver in the current interpreter."""
    importlib.import_module("picamera2")
    module = importlib.import_module("pi5camera.core.capture")
    return cast(CameraCapture, module.capture_photo)


def _load_camera_capture() -> CameraCapture:
    """Load camera capture locally or bridge to Raspberry Pi OS Python."""
    try:
        return _load_in_process_camera_capture()
    except (ImportError, OSError) as current_error:
        try:
            return cast(CameraCapture, _SystemPythonCameraCapture.create())
        except (ImportError, OSError) as system_error:
            raise ImportError(
                f"camera imports failed in {sys.executable}: {current_error}; "
                f"the {SYSTEM_CAMERA_PYTHON} bridge also failed: {system_error}. "
                "Run ./scripts/bootstrap-rpi-camera-workspace.sh."
            ) from system_error


class CameraDevice:
    """Own one serialized still-camera service and its private media boundary."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        width: int = 1280,
        height: int = 720,
        warmup_seconds: float = 1.0,
        autofocus_mode: str = "none",
        media_directory: str | Path = "~/.local/share/ninjarobot_pi5/camera",
        camera_factory: CameraFactory | None = None,
        simulated: bool = False,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("camera width and height must be greater than zero")
        if not 0 <= warmup_seconds <= 10:
            raise ValueError("camera warmup_seconds must be between 0 and 10")
        if autofocus_mode not in {"none", "manual", "auto", "continuous"}:
            raise ValueError("camera autofocus_mode must be none, manual, auto, or continuous")
        self._enabled = enabled
        self._width = width
        self._height = height
        self._warmup_seconds = float(warmup_seconds)
        self._autofocus_mode = autofocus_mode
        self._media_directory = Path(media_directory).expanduser().resolve()
        self._camera_factory = camera_factory or _load_camera_capture
        self._simulated = simulated
        self._capture: CameraCapture | None = None
        self._startup_error: str | None = None
        self._start_attempted = False
        self._closed = False
        self._lock = asyncio.Lock()

    @property
    def simulated(self) -> bool:
        """Return whether this service uses a deterministic fake."""
        return self._simulated

    async def start(self) -> None:
        """Check dependencies and the private directory without taking a photograph."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("camera device is closed")
            if self._start_attempted:
                return
            self._start_attempted = True
            if not self._enabled:
                self._startup_error = "camera is disabled by V4 configuration"
                return
            try:
                await asyncio.to_thread(
                    self._media_directory.mkdir,
                    parents=True,
                    exist_ok=True,
                    mode=0o700,
                )
                self._capture = await asyncio.to_thread(self._camera_factory)
                self._startup_error = None
            except Exception as exc:
                self._capture = None
                self._startup_error = f"{type(exc).__name__}: {exc}"

    async def status(self) -> dict[str, Any]:
        """Return configuration and readiness without opening the CSI camera."""
        async with self._lock:
            return {
                "enabled": self._enabled,
                "driver_available": self._capture is not None,
                "width": self._width,
                "height": self._height,
                "autofocus_mode": self._autofocus_mode,
                "retain_media_by_default": False,
                "media_directory": str(self._media_directory),
                "simulated": self._simulated,
            }

    async def capture(
        self,
        *,
        retain: bool,
        filename: str | None,
    ) -> dict[str, Any]:
        """Capture once, waiting for worker cleanup if the action is cancelled."""
        async with self._lock:
            capture = self._require_capture()
            destination = self._prepare_destination(retain=retain, filename=filename)
            cancellation = threading.Event()
            task = asyncio.create_task(
                asyncio.to_thread(
                    self._capture_in_worker,
                    capture,
                    retain,
                    destination,
                    cancellation,
                )
            )
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                cancellation.set()
                try:
                    await asyncio.shield(task)
                except BaseException:
                    pass
                raise
            except IDEError:
                raise
            except Exception as exc:
                raise _camera_error(
                    code="CAMERA_CAPTURE_FAILED",
                    message="The camera could not complete the still-image capture.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    capability="camera.capture",
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.UNKNOWN,
                ) from exc

    async def health(self) -> ResourceHealth:
        """Report dependency readiness without taking or retaining a photograph."""
        async with self._lock:
            if not self._enabled or self._capture is None:
                return ResourceHealth.UNAVAILABLE
            return ResourceHealth.READY

    async def close(self) -> None:
        """Prevent new captures after any in-flight worker has cleaned up."""
        async with self._lock:
            if self._closed:
                return
            self._capture = None
            self._closed = True

    def _require_capture(self) -> CameraCapture:
        if self._capture is None:
            raise _camera_error(
                code="CAMERA_UNAVAILABLE",
                message="The configured camera backend is unavailable.",
                technical_detail=self._startup_error,
                capability="camera.capture",
                definitely_not_executed=True,
                retry_safety=RetrySafety.SAFE,
            )
        return self._capture

    def _prepare_destination(self, *, retain: bool, filename: str | None) -> Path | None:
        if filename is not None and not retain:
            raise _invalid_arguments("--filename requires retain=true")
        if filename is not None and not CAMERA_FILENAME_PATTERN.fullmatch(filename):
            raise _invalid_arguments(
                "filename must contain only letters, numbers, underscores, or hyphens "
                "and end with .jpg"
            )
        if not retain:
            return None
        selected = filename or (
            f"camera-{datetime.now(UTC):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.jpg"
        )
        destination = (self._media_directory / selected).resolve()
        if destination.parent != self._media_directory:
            raise _invalid_arguments("filename must stay inside the configured media directory")
        if destination.exists():
            raise _camera_error(
                code="CAMERA_OUTPUT_EXISTS",
                message="The requested retained camera filename already exists.",
                technical_detail=str(destination),
                capability="camera.capture",
                definitely_not_executed=True,
                retry_safety=RetrySafety.SAFE,
            )
        return destination

    def _capture_in_worker(
        self,
        capture: CameraCapture,
        retain: bool,
        destination: Path | None,
        cancellation: threading.Event,
    ) -> dict[str, Any]:
        staging_directory = Path(
            tempfile.mkdtemp(prefix=".capture-", dir=self._media_directory)
        ).resolve()
        staging_path = staging_directory / "capture.jpg"
        retained_path: Path | None = None
        try:
            config = {
                "camera": {
                    "backend": "stub" if self._simulated else "picamera2",
                    "width": self._width,
                    "height": self._height,
                    "warmup_seconds": self._warmup_seconds,
                    "use_preview": False,
                    "autofocus_mode": self._autofocus_mode,
                },
                "paths": {
                    "photo_dir": str(staging_directory),
                    "data_dir": str(staging_directory),
                },
                "retention": {
                    "keep_photo_captures": True,
                    "keep_pending_crops": False,
                },
            }
            result = capture(config, output_path=staging_path)
            captured_path = Path(result.path).expanduser().resolve()
            if captured_path != staging_path or not captured_path.is_file():
                raise RuntimeError("managed camera returned an unexpected capture path")
            os.chmod(captured_path, 0o600)
            byte_count = captured_path.stat().st_size
            sha256 = _sha256_file(captured_path)
            if cancellation.is_set():
                raise _CaptureCancelledInWorker
            if retain:
                if destination is None:
                    raise RuntimeError("retained capture has no destination")
                os.link(captured_path, destination)
                os.chmod(destination, 0o600)
                retained_path = destination
                if cancellation.is_set():
                    raise _CaptureCancelledInWorker
            return {
                "captured": True,
                "width": self._width,
                "height": self._height,
                "format": "jpeg",
                "byte_count": byte_count,
                "sha256": sha256,
                "retained": retained_path is not None,
                "path": str(retained_path) if retained_path is not None else None,
                "simulated": self._simulated,
            }
        finally:
            if cancellation.is_set() and retained_path is not None:
                retained_path.unlink(missing_ok=True)
            shutil.rmtree(staging_directory, ignore_errors=True)


class CameraStatusAdapter:
    """Expose camera configuration and import readiness without capture."""

    descriptor = CapabilityDescriptor(
        name="camera.status",
        version="1.0.0",
        description="Report camera readiness and the privacy-safe still-capture profile.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "driver_available": {"type": "boolean"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "autofocus_mode": {"type": "string"},
                "retain_media_by_default": {"type": "boolean"},
                "media_directory": {"type": "string"},
                "simulated": {"type": "boolean"},
            },
            "required": [
                "enabled",
                "driver_available",
                "width",
                "height",
                "autofocus_mode",
                "retain_media_by_default",
                "media_directory",
                "simulated",
            ],
            "additionalProperties": False,
        },
        risk=RiskLevel.READ_ONLY,
        resources=CAMERA_RESOURCES,
        default_timeout_seconds=5.0,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, device: CameraDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise _invalid_arguments(
                f"camera.status does not accept arguments: {sorted(arguments)}",
                capability="camera.status",
            )
        return await self._device.status()

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


class CameraCaptureAdapter:
    """Expose one explicitly confirmed and privacy-bounded still capture."""

    descriptor = CapabilityDescriptor(
        name="camera.capture",
        version="1.0.0",
        description="Capture one still image without retaining it unless explicitly requested.",
        input_schema={
            "type": "object",
            "properties": {
                "retain": {"type": "boolean", "default": False},
                "filename": {
                    "type": "string",
                    "pattern": r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.jpg$",
                },
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "captured": {"type": "boolean"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "format": {"type": "string", "const": "jpeg"},
                "byte_count": {"type": "integer", "minimum": 1},
                "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "retained": {"type": "boolean"},
                "path": {"type": ["string", "null"]},
                "simulated": {"type": "boolean"},
            },
            "required": [
                "captured",
                "width",
                "height",
                "format",
                "byte_count",
                "sha256",
                "retained",
                "path",
                "simulated",
            ],
            "additionalProperties": False,
        },
        risk=RiskLevel.PRIVACY,
        resources=CAMERA_RESOURCES,
        default_timeout_seconds=CAMERA_CAPTURE_TIMEOUT_SECONDS,
        idempotent=False,
        cancellable=True,
        confirmation_required=True,
    )

    def __init__(self, device: CameraDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        unexpected = sorted(set(arguments) - {"retain", "filename"})
        if unexpected:
            raise _invalid_arguments(
                f"Unexpected argument keys: {unexpected}",
                capability="camera.capture",
            )
        retain = arguments.get("retain", False)
        filename = arguments.get("filename")
        if not isinstance(retain, bool):
            raise _invalid_arguments(
                "retain must be true or false",
                capability="camera.capture",
            )
        if filename is not None and not isinstance(filename, str):
            raise _invalid_arguments(
                "filename must be a string",
                capability="camera.capture",
            )
        return await self._device.capture(retain=retain, filename=filename)

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _invalid_arguments(
    detail: str,
    *,
    capability: str = "camera.capture",
) -> IDEError:
    return _camera_error(
        code="INVALID_CAPABILITY_ARGUMENTS",
        message="The camera capability arguments are invalid.",
        technical_detail=detail,
        capability=capability,
        definitely_not_executed=True,
        retry_safety=RetrySafety.SAFE,
    )


def _camera_error(
    *,
    code: str,
    message: str,
    technical_detail: str | None,
    capability: str,
    definitely_not_executed: bool,
    retry_safety: RetrySafety,
) -> IDEError:
    return IDEError(
        ErrorDetails(
            code=code,
            message=message,
            technical_detail=technical_detail,
            definitely_not_executed=definitely_not_executed,
            retry_safety=retry_safety,
            capability=capability,
        )
    )
