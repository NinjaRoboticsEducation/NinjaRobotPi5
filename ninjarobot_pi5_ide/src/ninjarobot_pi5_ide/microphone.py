"""Privacy-bounded microphone integration for approved ``pi5mic`` device APIs."""

from __future__ import annotations

import asyncio
import hashlib
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
import types
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.machinery import ModuleSpec
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

MICROPHONE_RESOURCES = ("microphone",)
MICROPHONE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.wav$")
MICROPHONE_CAPTURE_TIMEOUT_SECONDS = 35.0
MICROPHONE_TRANSCRIPTION_TIMEOUT_SECONDS = 90.0
MICROPHONE_ALLOWED_MODULES = frozenset(
    {
        "pi5mic",
        "pi5mic.core",
        "pi5mic.errors",
        "pi5mic.models",
        "pi5mic.core.audio_backend",
        "pi5mic.core.devices",
        "pi5mic.core.recorder",
    }
)
_MICROPHONE_IMPORT_LOCK = threading.Lock()


class MicrophoneDeviceInfo(Protocol):
    """Minimum audio-device information used by the V4 adapter."""

    index: int
    name: str
    max_input_channels: int
    default_samplerate: float | None
    hostapi: int | None


class MicrophoneClip(Protocol):
    """Minimum bounded-recording result returned by ``pi5mic``."""

    path: Path
    duration_seconds: float
    sample_rate: int
    channels: int
    frames: int
    bytes_written: int
    overflowed: bool


class MicrophoneBackend(Protocol):
    """Approved device-facing microphone operations."""

    def list_input_devices(self) -> list[MicrophoneDeviceInfo]: ...

    def resolve_input_settings(
        self,
        *,
        selector: str,
        sample_rate: int,
        channels: int,
    ) -> tuple[int | None, int, MicrophoneDeviceInfo | None, str | None]: ...

    def record_wav(
        self,
        output_path: Path,
        *,
        selector: str,
        sample_rate: int,
        channels: int,
        duration_seconds: float,
    ) -> MicrophoneClip: ...


class SpeechTranscriber(Protocol):
    """Local speech-to-text boundary used by the IDE microphone capability."""

    async def transcribe(self, wav_path: Path, *, language: str) -> str: ...

    def available(self) -> bool: ...


class WhisperCppTranscriber:
    """Run a local ``whisper.cpp`` command without a shell or retained audio."""

    def __init__(
        self,
        *,
        command: str | Path,
        model: str | Path,
        threads: int = 4,
        timeout_seconds: float = 75.0,
    ) -> None:
        if threads < 1 or threads > 8:
            raise ValueError("whisper.cpp threads must be from 1 through 8")
        if timeout_seconds <= 0:
            raise ValueError("whisper.cpp timeout must be positive")
        self._command = Path(command).expanduser().resolve()
        self._model = Path(model).expanduser().resolve()
        self._threads = threads
        self._timeout_seconds = timeout_seconds

    def available(self) -> bool:
        return (
            self._command.is_file() and os.access(self._command, os.X_OK) and self._model.is_file()
        )

    async def transcribe(self, wav_path: Path, *, language: str) -> str:
        if language not in {"auto", "en", "ja"}:
            raise ValueError("language must be auto, en, or ja")
        if not self.available():
            raise RuntimeError("whisper.cpp is unavailable; verify the command and model paths")
        resolved_wav = wav_path.expanduser().resolve()
        if not resolved_wav.is_file():
            raise FileNotFoundError(resolved_wav)
        output_directory = Path(tempfile.mkdtemp(prefix=".ninjarobot-transcript-"))
        output_prefix = output_directory / "transcript"
        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                str(self._command),
                "-m",
                str(self._model),
                "-f",
                str(resolved_wav),
                "-l",
                language,
                "-t",
                str(self._threads),
                "-otxt",
                "-of",
                str(output_prefix),
                "-np",
                "-nt",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            try:
                _stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._timeout_seconds,
                )
            except TimeoutError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                raise RuntimeError("whisper.cpp transcription timed out") from None
            if process.returncode != 0:
                detail = stderr.decode("utf-8", errors="replace")[-1000:].strip()
                raise RuntimeError(f"whisper.cpp exited with status {process.returncode}: {detail}")
            transcript_path = output_prefix.with_suffix(".txt")
            transcript = transcript_path.read_text(encoding="utf-8").strip()
            if not transcript:
                raise RuntimeError("whisper.cpp returned an empty transcript")
            return transcript
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            raise
        finally:
            shutil.rmtree(output_directory, ignore_errors=True)


class SimulatedSpeechTranscriber:
    """Return deterministic text while exercising the full privacy workflow."""

    def available(self) -> bool:
        return True

    async def transcribe(self, wav_path: Path, *, language: str) -> str:
        if not wav_path.is_file():
            raise FileNotFoundError(wav_path)
        return f"Simulated {language} microphone prompt"


MicrophoneBackendFactory = Callable[[], MicrophoneBackend]


@dataclass(slots=True)
class _Pi5MicBindings:
    """Dynamically loaded approved ``pi5mic`` callables."""

    list_input_devices: Callable[[], list[MicrophoneDeviceInfo]]
    resolve_supported_input_settings: Callable[
        ...,
        tuple[int | None, int, MicrophoneDeviceInfo | None, str | None],
    ]
    recorder_settings: Callable[..., Any]
    record_wav: Callable[[Path, Any], MicrophoneClip]


class _ManagedPi5MicBackend:
    """Translate V4 operations into the approved managed-driver functions."""

    def __init__(self, bindings: _Pi5MicBindings) -> None:
        self._bindings = bindings

    def list_input_devices(self) -> list[MicrophoneDeviceInfo]:
        return self._bindings.list_input_devices()

    def resolve_input_settings(
        self,
        *,
        selector: str,
        sample_rate: int,
        channels: int,
    ) -> tuple[int | None, int, MicrophoneDeviceInfo | None, str | None]:
        return self._bindings.resolve_supported_input_settings(
            selector=selector,
            sample_rate=sample_rate,
            channels=channels,
        )

    def record_wav(
        self,
        output_path: Path,
        *,
        selector: str,
        sample_rate: int,
        channels: int,
        duration_seconds: float,
    ) -> MicrophoneClip:
        settings = self._bindings.recorder_settings(
            device=selector,
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=duration_seconds,
        )
        return self._bindings.record_wav(output_path, settings)


class _CaptureCancelledInWorker(Exception):
    """Signal that microphone cleanup completed after task cancellation."""


def _managed_pi5mic_package_directory() -> Path:
    """Locate the managed ``pi5mic`` package without importing its root module."""
    try:
        distribution = importlib.metadata.distribution("pi5mic")
        direct_url_text = distribution.read_text("direct_url.json")
        if direct_url_text is not None:
            direct_url = json.loads(direct_url_text)
            parsed_url = urlparse(direct_url.get("url", ""))
            if parsed_url.scheme == "file":
                project_directory = Path(unquote(parsed_url.path)).resolve()
                package_directory = project_directory / "src" / "pi5mic"
                if (package_directory / "core" / "recorder.py").is_file():
                    return package_directory
    except (
        importlib.metadata.PackageNotFoundError,
        json.JSONDecodeError,
        OSError,
        TypeError,
    ):
        pass

    for parent in Path(__file__).resolve().parents:
        package_directory = parent / "pi5mic" / "src" / "pi5mic"
        if (package_directory / "core" / "recorder.py").is_file():
            return package_directory

    spec = importlib.util.find_spec("pi5mic")
    locations = spec.submodule_search_locations if spec is not None else None
    if locations:
        for location in locations:
            package_directory = Path(location).resolve()
            if (package_directory / "core" / "recorder.py").is_file():
                return package_directory
    raise ImportError("the managed pi5mic device source could not be located")


def _namespace_package(name: str, package_directory: Path) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__package__ = name
    module.__path__ = [str(package_directory)]
    spec = ModuleSpec(name, loader=None, is_package=True)
    spec.submodule_search_locations = [str(package_directory)]
    module.__spec__ = spec
    return module


def _load_module(name: str, path: Path) -> types.ModuleType:
    existing = sys.modules.get(name)
    if existing is not None:
        existing_path = getattr(existing, "__file__", None)
        if existing_path is None or Path(existing_path).resolve() != path.resolve():
            raise ImportError(f"unexpected preloaded module blocks safe microphone loading: {name}")
        return existing

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not create a loader for approved microphone module {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _unexpected_pi5mic_modules() -> list[str]:
    return sorted(
        name
        for name in sys.modules
        if (name == "pi5mic" or name.startswith("pi5mic."))
        and name not in MICROPHONE_ALLOWED_MODULES
    )


def _load_pi5mic_bindings() -> _Pi5MicBindings:
    """Load only approved device modules, bypassing historical package exports."""
    with _MICROPHONE_IMPORT_LOCK:
        unexpected = _unexpected_pi5mic_modules()
        if unexpected:
            raise ImportError(f"unapproved pi5mic modules were already imported: {unexpected}")

        package_directory = _managed_pi5mic_package_directory()
        root_module = sys.modules.get("pi5mic")
        if root_module is None:
            sys.modules["pi5mic"] = _namespace_package("pi5mic", package_directory)
        elif getattr(root_module, "__file__", None) is not None:
            raise ImportError("the pi5mic package root was imported before V4 containment")

        core_directory = package_directory / "core"
        core_module = sys.modules.get("pi5mic.core")
        if core_module is None:
            sys.modules["pi5mic.core"] = _namespace_package(
                "pi5mic.core",
                core_directory,
            )
        elif getattr(core_module, "__file__", None) is not None:
            raise ImportError("the pi5mic.core package exports were imported before containment")

        errors_module = _load_module("pi5mic.errors", package_directory / "errors.py")
        models_module = _load_module("pi5mic.models", package_directory / "models.py")
        _load_module(
            "pi5mic.core.audio_backend",
            core_directory / "audio_backend.py",
        )
        devices_module = _load_module(
            "pi5mic.core.devices",
            core_directory / "devices.py",
        )
        recorder_module = _load_module(
            "pi5mic.core.recorder",
            core_directory / "recorder.py",
        )
        del errors_module

        unexpected = _unexpected_pi5mic_modules()
        if unexpected:
            raise ImportError(f"microphone loading imported unapproved modules: {unexpected}")

        return _Pi5MicBindings(
            list_input_devices=cast(
                Callable[[], list[MicrophoneDeviceInfo]],
                devices_module.list_input_devices,
            ),
            resolve_supported_input_settings=cast(
                Callable[
                    ...,
                    tuple[
                        int | None,
                        int,
                        MicrophoneDeviceInfo | None,
                        str | None,
                    ],
                ],
                devices_module.resolve_supported_input_settings,
            ),
            recorder_settings=cast(
                Callable[..., Any],
                models_module.RecorderSettings,
            ),
            record_wav=cast(
                Callable[[Path, Any], MicrophoneClip],
                recorder_module.record_wav,
            ),
        )


def _load_microphone_backend() -> MicrophoneBackend:
    return _ManagedPi5MicBackend(_load_pi5mic_bindings())


class MicrophoneDevice:
    """Own one serialized microphone service and its private audio boundary."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        device_selector: str = "USB PnP Sound Device",
        sample_rate_hz: int = 16_000,
        channels: int = 1,
        max_capture_seconds: float = 10.0,
        media_directory: str | Path = "~/.local/share/ninjarobot_pi5/microphone",
        backend_factory: MicrophoneBackendFactory | None = None,
        simulated: bool = False,
    ) -> None:
        if not device_selector.strip():
            raise ValueError("microphone device_selector cannot be empty")
        if sample_rate_hz <= 0:
            raise ValueError("microphone sample_rate_hz must be greater than zero")
        if channels != 1:
            raise ValueError("Phase 3.5 microphone capture supports mono audio only")
        if not 1 <= max_capture_seconds <= 30:
            raise ValueError("microphone max_capture_seconds must be from 1 through 30")
        self._enabled = enabled
        self._device_selector = device_selector
        self._sample_rate_hz = sample_rate_hz
        self._channels = channels
        self._max_capture_seconds = float(max_capture_seconds)
        self._media_directory = Path(media_directory).expanduser().resolve()
        self._backend_factory = backend_factory or _load_microphone_backend
        self._simulated = simulated
        self._backend: MicrophoneBackend | None = None
        self._devices: list[MicrophoneDeviceInfo] = []
        self._selected_device: MicrophoneDeviceInfo | None = None
        self._actual_sample_rate_hz: int | None = None
        self._sample_rate_warning: str | None = None
        self._startup_error: str | None = None
        self._start_attempted = False
        self._closed = False
        self._lock = asyncio.Lock()

    @property
    def simulated(self) -> bool:
        """Return whether the service uses deterministic synthetic audio."""
        return self._simulated

    async def start(self) -> None:
        """Check device and PortAudio readiness without recording audio."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("microphone device is closed")
            if self._start_attempted:
                return
            self._start_attempted = True
            if not self._enabled:
                self._startup_error = "microphone is disabled by V4 configuration"
                return
            try:
                await asyncio.to_thread(
                    self._media_directory.mkdir,
                    parents=True,
                    exist_ok=True,
                    mode=0o700,
                )
                await asyncio.to_thread(os.chmod, self._media_directory, 0o700)
                backend = await asyncio.to_thread(self._backend_factory)
                devices, actual_rate, selected, warning = await asyncio.to_thread(
                    self._inspect_backend,
                    backend,
                )
                self._backend = backend
                self._devices = devices
                self._selected_device = selected
                self._actual_sample_rate_hz = actual_rate
                self._sample_rate_warning = warning
                self._startup_error = None
            except Exception as exc:
                self._backend = None
                self._devices = []
                self._selected_device = None
                self._actual_sample_rate_hz = None
                self._sample_rate_warning = None
                self._startup_error = f"{type(exc).__name__}: {exc}"

    async def status(self) -> dict[str, Any]:
        """Return device and retention readiness without recording audio."""
        async with self._lock:
            selected = self._selected_device
            return {
                "enabled": self._enabled,
                "driver_available": self._backend is not None,
                "device_selector": self._device_selector,
                "selected_device": (
                    _device_info_payload(selected) if selected is not None else None
                ),
                "input_devices": [_device_info_payload(device) for device in self._devices],
                "requested_sample_rate_hz": self._sample_rate_hz,
                "actual_sample_rate_hz": self._actual_sample_rate_hz,
                "sample_rate_warning": self._sample_rate_warning,
                "channels": self._channels,
                "max_capture_seconds": self._max_capture_seconds,
                "retain_audio_by_default": False,
                "media_directory": str(self._media_directory),
                "simulated": self._simulated,
            }

    async def capture(
        self,
        *,
        duration_seconds: float,
        retain: bool,
        filename: str | None,
    ) -> dict[str, Any]:
        """Record one bounded clip and wait for worker cleanup on cancellation."""
        async with self._lock:
            backend = self._require_backend()
            if not 0.25 <= duration_seconds <= self._max_capture_seconds:
                raise _invalid_arguments(
                    f"duration_seconds must be from 0.25 through {self._max_capture_seconds:g}"
                )
            destination = self._prepare_destination(retain=retain, filename=filename)
            cancellation = threading.Event()
            task = asyncio.create_task(
                asyncio.to_thread(
                    self._capture_in_worker,
                    backend,
                    duration_seconds,
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
                raise _microphone_error(
                    code="MICROPHONE_CAPTURE_FAILED",
                    message="The microphone could not complete the audio capture.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    capability="microphone.capture",
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.UNKNOWN,
                ) from exc

    async def health(self) -> ResourceHealth:
        """Report microphone readiness without recording audio."""
        async with self._lock:
            if not self._enabled or self._backend is None:
                return ResourceHealth.UNAVAILABLE
            return ResourceHealth.READY

    async def suspend(self) -> None:
        """Release the audio backend while allowing a later start."""
        async with self._lock:
            if self._closed:
                return
            self._backend = None
            self._devices = []
            self._selected_device = None
            self._actual_sample_rate_hz = None
            self._sample_rate_warning = None
            self._startup_error = None
            self._start_attempted = False

    async def close(self) -> None:
        """Prevent new recordings after any in-flight worker has cleaned up."""
        async with self._lock:
            if self._closed:
                return
            self._backend = None
            self._devices = []
            self._selected_device = None
            self._actual_sample_rate_hz = None
            self._closed = True

    def _inspect_backend(
        self,
        backend: MicrophoneBackend,
    ) -> tuple[
        list[MicrophoneDeviceInfo],
        int,
        MicrophoneDeviceInfo | None,
        str | None,
    ]:
        devices = backend.list_input_devices()
        if not devices:
            raise RuntimeError("no audio input devices were discovered")
        _resolved, actual_rate, selected, warning = backend.resolve_input_settings(
            selector=self._device_selector,
            sample_rate=self._sample_rate_hz,
            channels=self._channels,
        )
        return devices, actual_rate, selected, warning

    def _require_backend(self) -> MicrophoneBackend:
        if self._backend is None:
            raise _microphone_error(
                code="MICROPHONE_UNAVAILABLE",
                message="The configured microphone backend is unavailable.",
                technical_detail=self._startup_error,
                capability="microphone.capture",
                definitely_not_executed=True,
                retry_safety=RetrySafety.SAFE,
            )
        return self._backend

    def _prepare_destination(self, *, retain: bool, filename: str | None) -> Path | None:
        if filename is not None and not retain:
            raise _invalid_arguments("--filename requires retain=true")
        if filename is not None and not MICROPHONE_FILENAME_PATTERN.fullmatch(filename):
            raise _invalid_arguments(
                "filename must contain only letters, numbers, underscores, or hyphens "
                "and end with .wav"
            )
        if not retain:
            return None
        selected = filename or (
            f"microphone-{datetime.now(UTC):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.wav"
        )
        destination = (self._media_directory / selected).resolve()
        if destination.parent != self._media_directory:
            raise _invalid_arguments("filename must stay inside the configured media directory")
        if destination.exists():
            raise _microphone_error(
                code="MICROPHONE_OUTPUT_EXISTS",
                message="The requested retained microphone filename already exists.",
                technical_detail=str(destination),
                capability="microphone.capture",
                definitely_not_executed=True,
                retry_safety=RetrySafety.SAFE,
            )
        return destination

    def _capture_in_worker(
        self,
        backend: MicrophoneBackend,
        duration_seconds: float,
        retain: bool,
        destination: Path | None,
        cancellation: threading.Event,
    ) -> dict[str, Any]:
        staging_directory = Path(
            tempfile.mkdtemp(prefix=".capture-", dir=self._media_directory)
        ).resolve()
        staging_path = staging_directory / "capture.wav"
        retained_path: Path | None = None
        try:
            clip = backend.record_wav(
                staging_path,
                selector=self._device_selector,
                sample_rate=self._sample_rate_hz,
                channels=self._channels,
                duration_seconds=duration_seconds,
            )
            captured_path = Path(clip.path).expanduser().resolve()
            if captured_path != staging_path or not captured_path.is_file():
                raise RuntimeError("managed microphone returned an unexpected capture path")
            os.chmod(captured_path, 0o600)
            byte_count = captured_path.stat().st_size
            if byte_count <= 44:
                raise RuntimeError("managed microphone returned an empty WAV recording")
            sha256 = _sha256_file(captured_path)
            if cancellation.is_set():
                raise _CaptureCancelledInWorker
            if retain:
                if destination is None:
                    raise RuntimeError("retained audio capture has no destination")
                os.link(captured_path, destination)
                os.chmod(destination, 0o600)
                retained_path = destination
                if cancellation.is_set():
                    raise _CaptureCancelledInWorker
            return {
                "captured": True,
                "duration_seconds": clip.duration_seconds,
                "requested_sample_rate_hz": self._sample_rate_hz,
                "sample_rate_hz": clip.sample_rate,
                "channels": clip.channels,
                "frames": clip.frames,
                "format": "wav",
                "byte_count": byte_count,
                "overflowed": bool(clip.overflowed),
                "sha256": sha256,
                "retained": retained_path is not None,
                "path": str(retained_path) if retained_path is not None else None,
                "simulated": self._simulated,
            }
        finally:
            if cancellation.is_set() and retained_path is not None:
                retained_path.unlink(missing_ok=True)
            shutil.rmtree(staging_directory, ignore_errors=True)


class MicrophoneStatusAdapter:
    """Expose microphone readiness and device discovery without recording."""

    descriptor = CapabilityDescriptor(
        name="microphone.status",
        version="1.0.0",
        description="Report USB microphone readiness and the privacy-safe capture profile.",
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
                "device_selector": {"type": "string"},
                "selected_device": {"type": ["object", "null"]},
                "input_devices": {"type": "array"},
                "requested_sample_rate_hz": {"type": "integer"},
                "actual_sample_rate_hz": {"type": ["integer", "null"]},
                "sample_rate_warning": {"type": ["string", "null"]},
                "channels": {"type": "integer", "const": 1},
                "max_capture_seconds": {"type": "number"},
                "retain_audio_by_default": {"type": "boolean", "const": False},
                "media_directory": {"type": "string"},
                "simulated": {"type": "boolean"},
            },
            "required": [
                "enabled",
                "driver_available",
                "device_selector",
                "selected_device",
                "input_devices",
                "requested_sample_rate_hz",
                "actual_sample_rate_hz",
                "sample_rate_warning",
                "channels",
                "max_capture_seconds",
                "retain_audio_by_default",
                "media_directory",
                "simulated",
            ],
            "additionalProperties": False,
        },
        risk=RiskLevel.READ_ONLY,
        resources=MICROPHONE_RESOURCES,
        default_timeout_seconds=5.0,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, device: MicrophoneDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise _invalid_arguments(
                f"microphone.status does not accept arguments: {sorted(arguments)}",
                capability="microphone.status",
            )
        return await self._device.status()

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


class MicrophoneCaptureAdapter:
    """Expose one explicitly confirmed and privacy-bounded WAV capture."""

    descriptor = CapabilityDescriptor(
        name="microphone.capture",
        version="1.0.0",
        description="Capture one WAV clip without retaining it unless explicitly requested.",
        input_schema={
            "type": "object",
            "properties": {
                "duration_seconds": {
                    "type": "number",
                    "minimum": 0.25,
                    "maximum": 30,
                    "default": 3.0,
                },
                "retain": {"type": "boolean", "default": False},
                "filename": {
                    "type": "string",
                    "pattern": r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.wav$",
                },
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "captured": {"type": "boolean"},
                "duration_seconds": {"type": "number"},
                "requested_sample_rate_hz": {"type": "integer"},
                "sample_rate_hz": {"type": "integer"},
                "channels": {"type": "integer", "const": 1},
                "frames": {"type": "integer", "minimum": 1},
                "format": {"type": "string", "const": "wav"},
                "byte_count": {"type": "integer", "minimum": 45},
                "overflowed": {"type": "boolean"},
                "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "retained": {"type": "boolean"},
                "path": {"type": ["string", "null"]},
                "simulated": {"type": "boolean"},
            },
            "required": [
                "captured",
                "duration_seconds",
                "requested_sample_rate_hz",
                "sample_rate_hz",
                "channels",
                "frames",
                "format",
                "byte_count",
                "overflowed",
                "sha256",
                "retained",
                "path",
                "simulated",
            ],
            "additionalProperties": False,
        },
        risk=RiskLevel.PRIVACY,
        resources=MICROPHONE_RESOURCES,
        default_timeout_seconds=MICROPHONE_CAPTURE_TIMEOUT_SECONDS,
        idempotent=False,
        cancellable=True,
        confirmation_required=True,
    )

    def __init__(self, device: MicrophoneDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        unexpected = sorted(set(arguments) - {"duration_seconds", "retain", "filename"})
        if unexpected:
            raise _invalid_arguments(
                f"Unexpected argument keys: {unexpected}",
                capability="microphone.capture",
            )
        duration = arguments.get("duration_seconds", 3.0)
        retain = arguments.get("retain", False)
        filename = arguments.get("filename")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise _invalid_arguments(
                "duration_seconds must be a number",
                capability="microphone.capture",
            )
        if not isinstance(retain, bool):
            raise _invalid_arguments(
                "retain must be true or false",
                capability="microphone.capture",
            )
        if filename is not None and not isinstance(filename, str):
            raise _invalid_arguments(
                "filename must be a string",
                capability="microphone.capture",
            )
        return await self._device.capture(
            duration_seconds=float(duration),
            retain=retain,
            filename=filename,
        )

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


class MicrophoneTranscribeAdapter:
    """Capture a temporary WAV and convert it to text with local whisper.cpp."""

    descriptor = CapabilityDescriptor(
        name="microphone.transcribe",
        version="1.0.0",
        description=(
            "Record one bounded USB-microphone clip, transcribe it locally, "
            "and delete the temporary audio."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "duration_seconds": {
                    "type": "number",
                    "minimum": 0.25,
                    "maximum": 10,
                    "default": 5.0,
                },
                "language": {
                    "type": "string",
                    "enum": ["auto", "en", "ja"],
                    "default": "auto",
                },
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "transcript": {"type": "string", "minLength": 1},
                "language": {"type": "string", "enum": ["auto", "en", "ja"]},
                "duration_seconds": {"type": "number"},
                "audio_retained": {"type": "boolean", "const": False},
                "simulated": {"type": "boolean"},
            },
            "required": [
                "transcript",
                "language",
                "duration_seconds",
                "audio_retained",
                "simulated",
            ],
            "additionalProperties": False,
        },
        risk=RiskLevel.PRIVACY,
        resources=MICROPHONE_RESOURCES,
        default_timeout_seconds=MICROPHONE_TRANSCRIPTION_TIMEOUT_SECONDS,
        idempotent=False,
        cancellable=True,
        confirmation_required=True,
    )

    def __init__(
        self,
        device: MicrophoneDevice,
        transcriber: SpeechTranscriber,
    ) -> None:
        self._device = device
        self._transcriber = transcriber

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        unexpected = sorted(set(arguments) - {"duration_seconds", "language"})
        if unexpected:
            raise _invalid_arguments(
                f"Unexpected argument keys: {unexpected}",
                capability="microphone.transcribe",
            )
        duration = arguments.get("duration_seconds", 5.0)
        language = arguments.get("language", "auto")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise _invalid_arguments(
                "duration_seconds must be a number",
                capability="microphone.transcribe",
            )
        if language not in {"auto", "en", "ja"}:
            raise _invalid_arguments(
                "language must be auto, en, or ja",
                capability="microphone.transcribe",
            )
        filename = f"transcribe-{uuid.uuid4().hex}.wav"
        capture: dict[str, Any] | None = None
        try:
            capture = await self._device.capture(
                duration_seconds=float(duration),
                retain=True,
                filename=filename,
            )
            raw_path = capture.get("path")
            if not isinstance(raw_path, str):
                raise RuntimeError("temporary microphone capture returned no path")
            transcript = await self._transcriber.transcribe(
                Path(raw_path),
                language=language,
            )
            return {
                "transcript": transcript,
                "language": language,
                "duration_seconds": float(capture["duration_seconds"]),
                "audio_retained": False,
                "simulated": self._device.simulated,
            }
        except IDEError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise _microphone_error(
                code="MICROPHONE_TRANSCRIPTION_FAILED",
                message="The local microphone transcription could not be completed.",
                technical_detail=f"{type(exc).__name__}: {exc}",
                capability="microphone.transcribe",
                definitely_not_executed=False,
                retry_safety=RetrySafety.UNKNOWN,
            ) from exc
        finally:
            if capture is not None and isinstance(capture.get("path"), str):
                Path(capture["path"]).unlink(missing_ok=True)

    async def health(self) -> ResourceHealth:
        device_health = await self._device.health()
        if device_health is not ResourceHealth.READY or not self._transcriber.available():
            return ResourceHealth.UNAVAILABLE
        return ResourceHealth.READY

    async def close(self) -> None:
        await self._device.close()


def _device_info_payload(device: MicrophoneDeviceInfo) -> dict[str, Any]:
    return {
        "index": device.index,
        "name": device.name,
        "max_input_channels": device.max_input_channels,
        "default_sample_rate_hz": (
            int(device.default_samplerate) if device.default_samplerate is not None else None
        ),
        "hostapi": device.hostapi,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _invalid_arguments(
    detail: str,
    *,
    capability: str = "microphone.capture",
) -> IDEError:
    return _microphone_error(
        code="INVALID_CAPABILITY_ARGUMENTS",
        message="The microphone capability arguments are invalid.",
        technical_detail=detail,
        capability=capability,
        definitely_not_executed=True,
        retry_safety=RetrySafety.SAFE,
    )


def _microphone_error(
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
