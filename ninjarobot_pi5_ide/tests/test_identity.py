from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest

from ninjarobot_pi5_ide import CameraDevice, FaceIdentityDevice


class _CaptureResult:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.metadata: dict[str, Any] = {}


class _Capture:
    def __call__(
        self,
        config: dict[str, Any],
        *,
        output_path: Path | None = None,
        filename_prefix: str = "photo",
    ) -> _CaptureResult:
        del config, filename_prefix
        assert output_path is not None
        output_path.write_bytes(b"\xff\xd8identity-test\xff\xd9")
        return _CaptureResult(output_path)


class _FaceBackend:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def enroll(
        self,
        config: dict[str, Any],
        image_path: Path,
        identity: str,
    ) -> dict[str, Any]:
        assert image_path.is_file()
        destination = Path(config["paths"]["data_dir"]) / "known_faces" / identity / "face.jpg"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"cropped-face")
        return {
            "status": "enrolled",
            "face_count": 1,
            "identity": identity,
            "profile_image_path": str(destination),
        }

    def recognize(self, config: dict[str, Any], image_path: Path) -> dict[str, Any]:
        del config
        assert image_path.is_file()
        return {
            "status": "recognized",
            "face_count": 1,
            "identity": "face-local-user",
            "match_distance": 0.1,
        }

    def delete(self, config: dict[str, Any], identity: str) -> bool:
        del config
        self.deleted.append(identity)
        return True


class _BlockingFaceBackend(_FaceBackend):
    def __init__(self, started: threading.Event, release: threading.Event) -> None:
        super().__init__()
        self._started = started
        self._release = release

    def recognize(self, config: dict[str, Any], image_path: Path) -> dict[str, Any]:
        del config
        self._started.set()
        assert self._release.wait(timeout=2)
        assert image_path.is_file()
        return {"status": "unknown", "face_count": 1}


def test_identity_uses_temporary_full_frames_and_secures_profile_data(tmp_path: Path) -> None:
    async def exercise() -> None:
        camera_directory = tmp_path / "camera"
        face_directory = tmp_path / "faces"
        camera = CameraDevice(
            media_directory=camera_directory,
            camera_factory=_Capture,
            simulated=True,
        )
        backend = _FaceBackend()
        identity = FaceIdentityDevice(
            camera,
            data_directory=face_directory,
            backend=backend,
        )
        await camera.start()

        enrolled = await identity.enroll("local-user")
        assert enrolled["status"] == "enrolled"
        assert enrolled["raw_photo_retained"] is False
        assert list(camera_directory.glob("identity-*.jpg")) == []
        profile_path = Path(enrolled["profile_image_path"])
        assert profile_path.read_bytes() == b"cropped-face"
        assert profile_path.stat().st_mode & 0o777 == 0o600
        assert profile_path.parent.stat().st_mode & 0o777 == 0o700

        recognized = await identity.identify()
        assert recognized["identity"] == "face-local-user"
        assert list(camera_directory.glob("identity-*.jpg")) == []
        assert await identity.delete("local-user")
        assert backend.deleted == ["face-local-user"]
        await identity.close()
        await camera.close()

    asyncio.run(exercise())


def test_cancelled_identity_waits_for_worker_before_deleting_full_frame(tmp_path: Path) -> None:
    async def exercise() -> None:
        started = threading.Event()
        release = threading.Event()
        camera_directory = tmp_path / "camera"
        camera = CameraDevice(
            media_directory=camera_directory,
            camera_factory=_Capture,
            simulated=True,
        )
        identity = FaceIdentityDevice(
            camera,
            data_directory=tmp_path / "faces",
            backend=_BlockingFaceBackend(started, release),
        )
        await camera.start()
        task = asyncio.create_task(identity.identify())
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done()
        assert len(list(camera_directory.glob("identity-*.jpg"))) == 1
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert list(camera_directory.glob("identity-*.jpg")) == []
        await identity.close()
        await camera.close()

    asyncio.run(exercise())
