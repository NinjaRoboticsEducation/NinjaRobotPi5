"""IDE-owned face enrollment and explicit recognition workflows."""

from __future__ import annotations

import asyncio
import importlib
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Protocol

from .camera import CameraDevice


class FaceIdentityBackend(Protocol):
    """Narrow seam around the existing pi5camera recognition API."""

    def enroll(self, config: dict[str, Any], image_path: Path, identity: str) -> dict[str, Any]: ...

    def recognize(self, config: dict[str, Any], image_path: Path) -> dict[str, Any]: ...

    def delete(self, config: dict[str, Any], identity: str) -> bool: ...


class Pi5CameraFaceIdentityBackend:
    """Lazy adapter that keeps pi5camera dependencies behind the IDE."""

    def enroll(
        self,
        config: dict[str, Any],
        image_path: Path,
        identity: str,
    ) -> dict[str, Any]:
        pi5camera = importlib.import_module("pi5camera")
        enroll_pending_face = pi5camera.enroll_pending_face
        recognize_faces = pi5camera.recognize_faces

        result = recognize_faces(config, image_path=image_path)
        if int(result.get("face_count", 0)) != 1:
            self._discard_pending(config, result.get("recognition_id"))
            return {
                "status": "no_face" if not result.get("face_count") else "multiple_faces",
                "face_count": int(result.get("face_count", 0)),
            }
        faces = result.get("faces", [])
        face = faces[0] if isinstance(faces, list) and faces else {}
        known_identity = face.get("name") if face.get("status") == "known" else None
        if isinstance(known_identity, str) and known_identity != identity:
            self._discard_pending(config, result.get("recognition_id"))
            return {
                "status": "already_known",
                "face_count": 1,
                "identity": known_identity,
            }
        recognition_id = result.get("recognition_id")
        face_id = face.get("face_id")
        if not isinstance(recognition_id, str) or not isinstance(face_id, str):
            self._discard_pending(config, recognition_id)
            return {"status": "failed", "face_count": 1}
        enrolled = enroll_pending_face(
            config,
            recognition_id=recognition_id,
            face_id=face_id,
            name=identity,
        )
        return {
            "status": "enrolled",
            "face_count": 1,
            "identity": identity,
            "profile_image_path": enrolled["saved_image_path"],
            "refreshed": known_identity == identity,
        }

    def recognize(self, config: dict[str, Any], image_path: Path) -> dict[str, Any]:
        recognize_faces = importlib.import_module("pi5camera").recognize_faces

        result = recognize_faces(config, image_path=image_path)
        face_count = int(result.get("face_count", 0))
        recognition_id = result.get("recognition_id")
        self._discard_pending(config, recognition_id)
        if face_count == 0:
            return {"status": "no_face", "face_count": 0}
        if face_count != 1:
            return {"status": "multiple_faces", "face_count": face_count}
        faces = result.get("faces", [])
        face = faces[0] if isinstance(faces, list) and faces else {}
        identity = face.get("name") if face.get("status") == "known" else None
        if not isinstance(identity, str):
            return {"status": "unknown", "face_count": 1}
        return {
            "status": "recognized",
            "face_count": 1,
            "identity": identity,
            "match_distance": face.get("match_distance"),
        }

    def delete(self, config: dict[str, Any], identity: str) -> bool:
        FaceStore = importlib.import_module("pi5camera").FaceStore

        return bool(FaceStore(config).remove_known_face(identity))

    @staticmethod
    def _discard_pending(config: dict[str, Any], recognition_id: object) -> None:
        if not isinstance(recognition_id, str) or not recognition_id:
            return
        pending_module = importlib.import_module("pi5camera.storage.pending_records")
        pending_module.PendingRecordManager(config).remove_pending_record(recognition_id)


class FaceIdentityDevice:
    """Serialize identity photos with the existing camera device and erase full frames."""

    def __init__(
        self,
        camera: CameraDevice,
        *,
        data_directory: str | Path,
        backend: FaceIdentityBackend | None = None,
    ) -> None:
        self._camera = camera
        self._data_directory = Path(data_directory).expanduser().resolve()
        self._backend = backend or Pi5CameraFaceIdentityBackend()
        self._lock = asyncio.Lock()

    async def enroll(self, user_id: str) -> dict[str, Any]:
        """Enroll exactly one face under an opaque profile identifier."""
        identity = _face_identity(user_id)
        async with self._lock:
            return await self._with_temporary_capture(
                lambda path: self._backend.enroll(self._config(), path, identity)
            )

    async def identify(self) -> dict[str, Any]:
        """Explicitly identify exactly one known face without switching any session."""
        async with self._lock:
            return await self._with_temporary_capture(
                lambda path: self._backend.recognize(self._config(), path)
            )

    async def delete(self, user_id: str) -> bool:
        """Delete IDE-owned face data for a deterministically selected profile."""
        async with self._lock:
            removed = await asyncio.to_thread(
                self._backend.delete,
                self._config(),
                _face_identity(user_id),
            )
            await asyncio.to_thread(self._secure_data_tree)
            return removed

    async def _with_temporary_capture(self, operation: Any) -> dict[str, Any]:
        self._data_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        capture = await self._camera.capture(
            retain=True,
            filename=f"identity-{uuid.uuid4().hex}.jpg",
        )
        raw_path = Path(str(capture["path"])).expanduser().resolve()
        task = asyncio.create_task(asyncio.to_thread(operation, raw_path))
        try:
            try:
                result = await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await asyncio.shield(task)
                except BaseException:
                    pass
                raise
            await asyncio.to_thread(self._secure_data_tree)
            return {
                **result,
                "backend": "pi5camera",
                "raw_photo_retained": False,
            }
        finally:
            raw_path.unlink(missing_ok=True)

    def _config(self) -> dict[str, Any]:
        return {
            "recognition": {
                "backend": "mediapipe_opencv",
                "tolerance": 0.6,
                "save_unknown_crops": False,
                "pending_ttl_seconds": 300,
            },
            "paths": {
                "photo_dir": str(self._data_directory / "temporary"),
                "data_dir": str(self._data_directory),
            },
            "retention": {
                "keep_photo_captures": False,
                "keep_pending_crops": False,
            },
        }

    def _secure_data_tree(self) -> None:
        if not self._data_directory.exists():
            return
        os.chmod(self._data_directory, 0o700)
        for path in self._data_directory.rglob("*"):
            try:
                os.chmod(path, 0o700 if path.is_dir() else 0o600)
            except FileNotFoundError:
                continue

    async def close(self) -> None:
        """Remove incomplete temporary identity data; camera ownership stays with RobotAssembly."""
        temporary = self._data_directory / "temporary"
        await asyncio.to_thread(shutil.rmtree, temporary, True)


def _face_identity(user_id: str) -> str:
    if (
        not user_id
        or len(user_id) > 128
        or any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-"
            for character in user_id
        )
    ):
        raise ValueError("user_id is not valid for face enrollment")
    return f"face-{user_id}"
