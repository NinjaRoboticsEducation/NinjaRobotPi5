from __future__ import annotations

import asyncio
import sys
import threading
import time
import wave
from pathlib import Path

import pytest
from ninjarobot_pi5_ide.microphone import (
    MicrophoneClip,
    MicrophoneDeviceInfo,
)

from ninjarobot_pi5_ide import (
    ActionLedger,
    ActionRequest,
    ActionStatus,
    CapabilityRegistry,
    ExecutionEngine,
    MicrophoneCaptureAdapter,
    MicrophoneDevice,
    MicrophoneStatusAdapter,
    MicrophoneTranscribeAdapter,
    ResourceHealth,
    ResourceScheduler,
    RetrySafety,
    SimulatedSpeechTranscriber,
)
from ninjarobot_pi5_ide import microphone as microphone_module


class FakeDeviceInfo:
    index = 0
    name = "USB PnP Sound Device: Audio (hw:0,0)"
    max_input_channels = 1
    default_samplerate = 44_100.0
    hostapi = 0


class FakeClip:
    def __init__(
        self,
        path: Path,
        duration_seconds: float,
        sample_rate: int,
    ) -> None:
        self.path = path
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate
        self.channels = 1
        self.frames = max(1, round(duration_seconds * sample_rate))
        self.bytes_written = path.stat().st_size
        self.overflowed = False


class FakeBackend:
    def __init__(
        self,
        *,
        fail: bool = False,
        delay: float = 0.0,
        started: threading.Event | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self.device = FakeDeviceInfo()
        self.fail = fail
        self.delay = delay
        self.started = started
        self.release = release
        self.record_calls = 0
        self.active_calls = 0
        self.max_active_calls = 0
        self._lock = threading.Lock()

    def list_input_devices(self) -> list[MicrophoneDeviceInfo]:
        return [self.device]

    def resolve_input_settings(
        self,
        *,
        selector: str,
        sample_rate: int,
        channels: int,
    ) -> tuple[int, int, MicrophoneDeviceInfo, str | None]:
        assert selector == "USB PnP Sound Device"
        assert channels == 1
        warning = (
            f"Configured sample rate {sample_rate} Hz is not supported; using 44100 Hz instead."
            if sample_rate != 44_100
            else None
        )
        return self.device.index, 44_100, self.device, warning

    def record_wav(
        self,
        output_path: Path,
        *,
        selector: str,
        sample_rate: int,
        channels: int,
        duration_seconds: float,
    ) -> MicrophoneClip:
        assert selector == "USB PnP Sound Device"
        assert sample_rate == 16_000
        assert channels == 1
        with self._lock:
            self.record_calls += 1
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            if self.started is not None:
                self.started.set()
            if self.release is not None:
                self.release.wait(timeout=2)
            if self.delay:
                time.sleep(self.delay)
            frame_count = max(1, round(duration_seconds * 44_100))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(44_100)
                wav_file.writeframes(b"\x01\x00" * frame_count)
            if self.fail:
                raise OSError("microphone transport failed")
            return FakeClip(output_path, duration_seconds, 44_100)
        finally:
            with self._lock:
                self.active_calls -= 1


def test_microphone_can_restart_after_emergency_suspend(tmp_path: Path) -> None:
    async def exercise() -> None:
        backends: list[FakeBackend] = []

        def factory() -> FakeBackend:
            backend = FakeBackend()
            backends.append(backend)
            return backend

        device = MicrophoneDevice(
            media_directory=tmp_path / "microphone",
            backend_factory=factory,
        )
        await device.start()
        assert await device.health() is ResourceHealth.READY

        await device.suspend()
        assert await device.health() is ResourceHealth.UNAVAILABLE

        await device.start()
        assert await device.health() is ResourceHealth.READY
        assert len(backends) == 2
        await device.close()

    asyncio.run(exercise())


def request(
    action_id: str,
    capability: str,
    arguments: dict[str, object],
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        capability=capability,
        arguments=arguments,
        requested_by="test",
        session_id="microphone-test",
        idempotency_key=f"key-{action_id}",
    )


def device_for(tmp_path: Path, backend: FakeBackend) -> MicrophoneDevice:
    return MicrophoneDevice(
        media_directory=tmp_path / "private-microphone",
        backend_factory=lambda: backend,
        simulated=True,
    )


def engine_for(tmp_path: Path, device: MicrophoneDevice) -> ExecutionEngine:
    return ExecutionEngine(
        CapabilityRegistry(
            [
                MicrophoneCaptureAdapter(device),
                MicrophoneStatusAdapter(device),
                MicrophoneTranscribeAdapter(device, SimulatedSpeechTranscriber()),
            ]
        ),
        ActionLedger(tmp_path / "microphone.sqlite3"),
        scheduler=ResourceScheduler(max_concurrency=2, max_queue_size=4),
    )


def test_transcription_deletes_its_temporary_audio(tmp_path: Path) -> None:
    async def exercise() -> None:
        backend = FakeBackend()
        media = tmp_path / "private-microphone"
        engine = engine_for(tmp_path, device_for(tmp_path, backend))

        result = await engine.execute(
            request(
                "microphone-transcribe-1",
                "microphone.transcribe",
                {"duration_seconds": 0.25, "language": "en"},
            )
        )

        assert result.status is ActionStatus.SUCCEEDED
        assert result.data is not None
        assert result.data["transcript"] == "Simulated en microphone prompt"
        assert result.data["audio_retained"] is False
        assert list(media.glob("transcribe-*.wav")) == []
        await engine.close()

    asyncio.run(exercise())


def test_device_only_loader_never_imports_historical_or_voice_modules() -> None:
    bindings = microphone_module._load_pi5mic_bindings()

    imported = {name for name in sys.modules if name == "pi5mic" or name.startswith("pi5mic.")}
    assert imported == microphone_module.MICROPHONE_ALLOWED_MODULES
    assert getattr(sys.modules["pi5mic"], "__file__", None) is None
    assert callable(bindings.list_input_devices)
    assert callable(bindings.record_wav)


def test_status_discovers_device_without_recording(tmp_path: Path) -> None:
    async def exercise() -> None:
        backend = FakeBackend()
        engine = engine_for(tmp_path, device_for(tmp_path, backend))

        result = await engine.execute(request("microphone-status-1", "microphone.status", {}))
        health = await engine.health()

        assert result.status is ActionStatus.SUCCEEDED
        assert result.retry_safety is RetrySafety.SAFE
        assert result.data is not None
        assert result.data["driver_available"] is True
        assert result.data["device_selector"] == "USB PnP Sound Device"
        assert result.data["selected_device"]["name"].startswith("USB PnP")
        assert len(result.data["input_devices"]) == 1
        assert result.data["requested_sample_rate_hz"] == 16_000
        assert result.data["actual_sample_rate_hz"] == 44_100
        assert "using 44100 Hz" in result.data["sample_rate_warning"]
        assert result.data["retain_audio_by_default"] is False
        assert result.data["simulated"] is True
        assert backend.record_calls == 0
        assert health.status is ResourceHealth.READY
        await engine.close()

    asyncio.run(exercise())


def test_default_capture_does_not_retain_audio_and_replay_is_durable(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        backend = FakeBackend()
        media = tmp_path / "private-microphone"
        engine = engine_for(tmp_path, device_for(tmp_path, backend))
        action = request(
            "microphone-capture-1",
            "microphone.capture",
            {"duration_seconds": 0.25, "retain": False},
        )

        first = await engine.execute(action)
        repeated = await engine.execute(action)

        assert first.status is ActionStatus.SUCCEEDED
        assert first.retry_safety is RetrySafety.UNSAFE
        assert first.data is not None
        assert first.data["captured"] is True
        assert first.data["sample_rate_hz"] == 44_100
        assert first.data["channels"] == 1
        assert first.data["format"] == "wav"
        assert first.data["retained"] is False
        assert first.data["path"] is None
        assert len(first.data["sha256"]) == 64
        assert repeated == first
        assert backend.record_calls == 1
        assert list(media.iterdir()) == []
        await engine.close()

    asyncio.run(exercise())


def test_explicit_retention_is_private_and_never_overwrites(tmp_path: Path) -> None:
    async def exercise() -> None:
        backend = FakeBackend()
        media = tmp_path / "private-microphone"
        engine = engine_for(tmp_path, device_for(tmp_path, backend))
        arguments = {
            "duration_seconds": 0.25,
            "retain": True,
            "filename": "phase35-test.wav",
        }

        retained = await engine.execute(
            request("microphone-retain-1", "microphone.capture", arguments)
        )
        duplicate = await engine.execute(
            request("microphone-retain-2", "microphone.capture", arguments)
        )

        assert retained.status is ActionStatus.SUCCEEDED
        assert retained.data is not None
        retained_path = Path(retained.data["path"])
        assert retained_path == media / "phase35-test.wav"
        assert retained_path.stat().st_mode & 0o777 == 0o600
        with wave.open(str(retained_path), "rb") as wav_file:
            assert wav_file.getnchannels() == 1
            assert wav_file.getframerate() == 44_100
        assert duplicate.status is ActionStatus.FAILED
        assert duplicate.error is not None
        assert duplicate.error.code == "MICROPHONE_OUTPUT_EXISTS"
        assert duplicate.error.definitely_not_executed is True
        assert backend.record_calls == 1
        await engine.close()

    asyncio.run(exercise())


def test_invalid_arguments_never_record(tmp_path: Path) -> None:
    async def exercise() -> None:
        backend = FakeBackend()
        engine = engine_for(tmp_path, device_for(tmp_path, backend))
        cases = (
            {"duration_seconds": 0.1},
            {"duration_seconds": 11.0},
            {"retain": False, "filename": "unexpected.wav"},
            {"retain": True, "filename": "../outside.wav"},
            {"retain": "yes"},
            {"duration_seconds": True},
            {"mystery": 1},
        )

        for index, arguments in enumerate(cases):
            result = await engine.execute(
                request(
                    f"microphone-invalid-{index}",
                    "microphone.capture",
                    arguments,
                )
            )
            assert result.status is ActionStatus.FAILED
            assert result.error is not None
            assert result.error.code == "INVALID_CAPABILITY_ARGUMENTS"
            assert result.error.definitely_not_executed is True
        assert backend.record_calls == 0
        assert not (tmp_path / "outside.wav").exists()
        await engine.close()

    asyncio.run(exercise())


def test_recording_failure_removes_staging_audio(tmp_path: Path) -> None:
    async def exercise() -> None:
        media = tmp_path / "private-microphone"
        engine = engine_for(
            tmp_path,
            device_for(tmp_path, FakeBackend(fail=True)),
        )

        result = await engine.execute(
            request(
                "microphone-failure",
                "microphone.capture",
                {
                    "duration_seconds": 0.25,
                    "retain": True,
                    "filename": "failed.wav",
                },
            )
        )

        assert result.status is ActionStatus.FAILED
        assert result.retry_safety is RetrySafety.UNKNOWN
        assert result.error is not None
        assert result.error.code == "MICROPHONE_CAPTURE_FAILED"
        assert list(media.iterdir()) == []
        await engine.close()

    asyncio.run(exercise())


def test_cancelled_recording_waits_for_cleanup(tmp_path: Path) -> None:
    async def exercise() -> None:
        media = tmp_path / "private-microphone"
        started = threading.Event()
        release = threading.Event()
        backend = FakeBackend(started=started, release=release)
        adapter = MicrophoneCaptureAdapter(device_for(tmp_path, backend))
        await adapter.start()
        task = asyncio.create_task(
            adapter.execute(
                {
                    "duration_seconds": 0.25,
                    "retain": True,
                    "filename": "cancelled.wav",
                }
            )
        )
        assert await asyncio.to_thread(started.wait, 1)

        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert list(media.iterdir()) == []
        await adapter.close()

    asyncio.run(exercise())


def test_timed_out_recording_finishes_cleanup_before_returning(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        media = tmp_path / "private-microphone"
        adapter = MicrophoneCaptureAdapter(device_for(tmp_path, FakeBackend(delay=0.05)))
        adapter.descriptor = adapter.descriptor.model_copy(update={"default_timeout_seconds": 0.01})
        engine = ExecutionEngine(
            CapabilityRegistry([adapter]),
            ActionLedger(tmp_path / "timeout.sqlite3"),
        )

        result = await engine.execute(
            request(
                "microphone-timeout",
                "microphone.capture",
                {
                    "duration_seconds": 0.25,
                    "retain": True,
                    "filename": "timeout.wav",
                },
            )
        )

        assert result.status is ActionStatus.FAILED
        assert result.retry_safety is RetrySafety.UNKNOWN
        assert result.error is not None
        assert result.error.code == "ACTION_TIMEOUT_UNKNOWN_OUTCOME"
        assert list(media.iterdir()) == []
        await engine.close()

    asyncio.run(exercise())


def test_microphone_resource_serializes_concurrent_recordings(tmp_path: Path) -> None:
    async def exercise() -> None:
        backend = FakeBackend(delay=0.03)
        engine = engine_for(tmp_path, device_for(tmp_path, backend))
        await engine.start()

        first, second = await asyncio.gather(
            engine.execute(
                request(
                    "microphone-concurrent-1",
                    "microphone.capture",
                    {"duration_seconds": 0.25},
                )
            ),
            engine.execute(
                request(
                    "microphone-concurrent-2",
                    "microphone.capture",
                    {"duration_seconds": 0.25},
                )
            ),
        )

        assert first.status is ActionStatus.SUCCEEDED
        assert second.status is ActionStatus.SUCCEEDED
        assert backend.max_active_calls == 1
        await engine.close()

    asyncio.run(exercise())


def test_unavailable_and_disabled_microphone_are_structured(tmp_path: Path) -> None:
    async def exercise() -> None:
        def unavailable() -> FakeBackend:
            raise ImportError("PortAudio unavailable")

        unavailable_engine = engine_for(
            tmp_path,
            MicrophoneDevice(
                media_directory=tmp_path / "unavailable",
                backend_factory=unavailable,
            ),
        )
        unavailable_result = await unavailable_engine.execute(
            request(
                "microphone-unavailable",
                "microphone.capture",
                {"duration_seconds": 0.25},
            )
        )
        assert unavailable_result.status is ActionStatus.FAILED
        assert unavailable_result.error is not None
        assert unavailable_result.error.code == "MICROPHONE_UNAVAILABLE"
        assert unavailable_result.error.definitely_not_executed is True
        assert (await unavailable_engine.health()).status is ResourceHealth.UNAVAILABLE
        await unavailable_engine.close()

        disabled_engine = engine_for(
            tmp_path,
            MicrophoneDevice(
                enabled=False,
                media_directory=tmp_path / "disabled",
                backend_factory=lambda: FakeBackend(),
            ),
        )
        status = await disabled_engine.execute(
            request("microphone-disabled-status", "microphone.status", {})
        )
        assert status.status is ActionStatus.SUCCEEDED
        assert status.data is not None
        assert status.data["enabled"] is False
        assert status.data["driver_available"] is False
        assert (await disabled_engine.health()).status is ResourceHealth.UNAVAILABLE
        await disabled_engine.close()

    asyncio.run(exercise())
