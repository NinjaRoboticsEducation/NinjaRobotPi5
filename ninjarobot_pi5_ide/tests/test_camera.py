from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from ninjarobot_pi5_ide import (
    ActionLedger,
    ActionRequest,
    ActionStatus,
    CameraCaptureAdapter,
    CameraDevice,
    CameraStatusAdapter,
    CapabilityRegistry,
    ExecutionEngine,
    ResourceHealth,
    ResourceScheduler,
    RetrySafety,
)


class FakeCaptureResult:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.metadata: dict[str, Any] = {"fake": True}


class FakeCapture:
    def __init__(
        self,
        *,
        fail: bool = False,
        delay: float = 0.0,
        started: threading.Event | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self.fail = fail
        self.delay = delay
        self.started = started
        self.release = release
        self.calls = 0
        self.active_calls = 0
        self.max_active_calls = 0
        self._lock = threading.Lock()

    def __call__(
        self,
        config: dict[str, Any],
        *,
        output_path: Path | None = None,
        filename_prefix: str = "photo",
    ) -> FakeCaptureResult:
        del config, filename_prefix
        if output_path is None:
            raise ValueError("fake capture requires an output path")
        with self._lock:
            self.calls += 1
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            if self.started is not None:
                self.started.set()
            if self.release is not None:
                self.release.wait(timeout=2)
            if self.delay:
                time.sleep(self.delay)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"\xff\xd8fake-jpeg-data\xff\xd9")
            if self.fail:
                raise OSError("camera transport failed")
            return FakeCaptureResult(output_path)
        finally:
            with self._lock:
                self.active_calls -= 1


def request(
    action_id: str,
    capability: str,
    arguments: dict[str, Any],
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        capability=capability,
        arguments=arguments,
        requested_by="test",
        session_id="camera-test",
        idempotency_key=f"key-{action_id}",
    )


def engine_for(tmp_path: Path, device: CameraDevice) -> ExecutionEngine:
    return ExecutionEngine(
        CapabilityRegistry(
            [
                CameraCaptureAdapter(device),
                CameraStatusAdapter(device),
            ]
        ),
        ActionLedger(tmp_path / "camera.sqlite3"),
        scheduler=ResourceScheduler(max_concurrency=2, max_queue_size=4),
    )


def test_status_and_default_capture_do_not_retain_media(tmp_path: Path) -> None:
    async def exercise() -> None:
        media = tmp_path / "private-camera"
        capture = FakeCapture()
        device = CameraDevice(
            media_directory=media,
            camera_factory=lambda: capture,
            simulated=True,
        )
        engine = engine_for(tmp_path, device)

        status = await engine.execute(request("camera-status-1", "camera.status", {}))
        result = await engine.execute(
            request("camera-capture-1", "camera.capture", {"retain": False})
        )
        health = await engine.health()

        assert status.status is ActionStatus.SUCCEEDED
        assert status.retry_safety is RetrySafety.SAFE
        assert status.data == {
            "enabled": True,
            "driver_available": True,
            "width": 1280,
            "height": 720,
            "autofocus_mode": "none",
            "retain_media_by_default": False,
            "media_directory": str(media.resolve()),
            "simulated": True,
        }
        assert result.status is ActionStatus.SUCCEEDED
        assert result.retry_safety is RetrySafety.UNSAFE
        assert result.data is not None
        assert result.data["captured"] is True
        assert result.data["retained"] is False
        assert result.data["path"] is None
        assert result.data["simulated"] is True
        assert len(result.data["sha256"]) == 64
        assert health.status is ResourceHealth.READY
        assert list(media.iterdir()) == []
        await engine.close()

    asyncio.run(exercise())


def test_explicit_retention_is_private_and_never_overwrites(tmp_path: Path) -> None:
    async def exercise() -> None:
        media = tmp_path / "private-camera"
        capture = FakeCapture()
        device = CameraDevice(
            media_directory=media,
            camera_factory=lambda: capture,
            simulated=True,
        )
        engine = engine_for(tmp_path, device)
        arguments = {"retain": True, "filename": "phase34-test.jpg"}

        retained = await engine.execute(request("camera-retain-1", "camera.capture", arguments))
        duplicate = await engine.execute(request("camera-retain-2", "camera.capture", arguments))

        assert retained.status is ActionStatus.SUCCEEDED
        assert retained.data is not None
        retained_path = Path(retained.data["path"])
        assert retained_path == media / "phase34-test.jpg"
        assert retained_path.read_bytes() == b"\xff\xd8fake-jpeg-data\xff\xd9"
        assert retained_path.stat().st_mode & 0o777 == 0o600
        assert duplicate.status is ActionStatus.FAILED
        assert duplicate.error is not None
        assert duplicate.error.code == "CAMERA_OUTPUT_EXISTS"
        assert duplicate.error.definitely_not_executed is True
        assert capture.calls == 1
        await engine.close()

    asyncio.run(exercise())


def test_invalid_filename_and_retention_arguments_never_capture(tmp_path: Path) -> None:
    async def exercise() -> None:
        capture = FakeCapture()
        device = CameraDevice(
            media_directory=tmp_path / "media",
            camera_factory=lambda: capture,
            simulated=True,
        )
        engine = engine_for(tmp_path, device)

        traversal = await engine.execute(
            request(
                "camera-traversal",
                "camera.capture",
                {"retain": True, "filename": "../outside.jpg"},
            )
        )
        filename_without_retention = await engine.execute(
            request(
                "camera-no-retain-name",
                "camera.capture",
                {"filename": "unexpected.jpg"},
            )
        )
        wrong_type = await engine.execute(
            request("camera-wrong-type", "camera.capture", {"retain": "yes"})
        )

        for result in (traversal, filename_without_retention, wrong_type):
            assert result.status is ActionStatus.FAILED
            assert result.error is not None
            assert result.error.code == "INVALID_CAPABILITY_ARGUMENTS"
            assert result.error.definitely_not_executed is True
        assert capture.calls == 0
        assert not (tmp_path / "outside.jpg").exists()
        await engine.close()

    asyncio.run(exercise())


def test_capture_failure_removes_staging_media(tmp_path: Path) -> None:
    async def exercise() -> None:
        media = tmp_path / "media"
        device = CameraDevice(
            media_directory=media,
            camera_factory=lambda: FakeCapture(fail=True),
        )
        engine = engine_for(tmp_path, device)
        result = await engine.execute(
            request(
                "camera-failure",
                "camera.capture",
                {"retain": True, "filename": "failed.jpg"},
            )
        )

        assert result.status is ActionStatus.FAILED
        assert result.retry_safety is RetrySafety.UNKNOWN
        assert result.error is not None
        assert result.error.code == "CAMERA_CAPTURE_FAILED"
        assert list(media.iterdir()) == []
        await engine.close()

    asyncio.run(exercise())


def test_cancelled_capture_waits_for_cleanup_and_removes_retained_file(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        media = tmp_path / "media"
        started = threading.Event()
        release = threading.Event()
        capture = FakeCapture(started=started, release=release)
        device = CameraDevice(
            media_directory=media,
            camera_factory=lambda: capture,
            simulated=True,
        )
        adapter = CameraCaptureAdapter(device)
        await adapter.start()
        task = asyncio.create_task(adapter.execute({"retain": True, "filename": "cancelled.jpg"}))
        assert await asyncio.to_thread(started.wait, 1)

        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert list(media.iterdir()) == []
        await adapter.close()

    asyncio.run(exercise())


def test_timed_out_capture_finishes_worker_cleanup_before_returning(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        media = tmp_path / "media"
        capture = FakeCapture(delay=0.05)
        device = CameraDevice(
            media_directory=media,
            camera_factory=lambda: capture,
            simulated=True,
        )
        adapter = CameraCaptureAdapter(device)
        adapter.descriptor = adapter.descriptor.model_copy(update={"default_timeout_seconds": 0.01})
        engine = ExecutionEngine(
            CapabilityRegistry([adapter, CameraStatusAdapter(device)]),
            ActionLedger(tmp_path / "timeout.sqlite3"),
        )
        result = await engine.execute(
            request(
                "camera-timeout",
                "camera.capture",
                {"retain": True, "filename": "timeout.jpg"},
            )
        )

        assert result.status is ActionStatus.FAILED
        assert result.retry_safety is RetrySafety.UNKNOWN
        assert result.error is not None
        assert result.error.code == "ACTION_TIMEOUT_UNKNOWN_OUTCOME"
        assert list(media.iterdir()) == []
        await engine.close()

    asyncio.run(exercise())


def test_camera_resource_serializes_concurrent_captures(tmp_path: Path) -> None:
    async def exercise() -> None:
        capture = FakeCapture(delay=0.03)
        device = CameraDevice(
            media_directory=tmp_path / "media",
            camera_factory=lambda: capture,
            simulated=True,
        )
        engine = engine_for(tmp_path, device)
        await engine.start()

        first, second = await asyncio.gather(
            engine.execute(request("camera-concurrent-1", "camera.capture", {"retain": False})),
            engine.execute(request("camera-concurrent-2", "camera.capture", {"retain": False})),
        )

        assert first.status is ActionStatus.SUCCEEDED
        assert second.status is ActionStatus.SUCCEEDED
        assert capture.max_active_calls == 1
        await engine.close()

    asyncio.run(exercise())


def test_unavailable_and_disabled_camera_are_structured(tmp_path: Path) -> None:
    async def exercise() -> None:
        def unavailable() -> FakeCapture:
            raise ImportError("Picamera2 unavailable")

        unavailable_engine = engine_for(
            tmp_path,
            CameraDevice(
                media_directory=tmp_path / "unavailable",
                camera_factory=unavailable,
            ),
        )
        unavailable_result = await unavailable_engine.execute(
            request("camera-unavailable", "camera.capture", {})
        )
        assert unavailable_result.status is ActionStatus.FAILED
        assert unavailable_result.error is not None
        assert unavailable_result.error.code == "CAMERA_UNAVAILABLE"
        assert unavailable_result.error.definitely_not_executed is True
        assert (await unavailable_engine.health()).status is ResourceHealth.UNAVAILABLE
        await unavailable_engine.close()

        disabled_engine = engine_for(
            tmp_path,
            CameraDevice(
                enabled=False,
                media_directory=tmp_path / "disabled",
                camera_factory=lambda: FakeCapture(),
            ),
        )
        status = await disabled_engine.execute(
            request("camera-disabled-status", "camera.status", {})
        )
        assert status.status is ActionStatus.SUCCEEDED
        assert status.data is not None
        assert status.data["enabled"] is False
        assert status.data["driver_available"] is False
        assert (await disabled_engine.health()).status is ResourceHealth.UNAVAILABLE
        await disabled_engine.close()

    asyncio.run(exercise())
