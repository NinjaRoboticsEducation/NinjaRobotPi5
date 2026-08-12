from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
from ninjarobot_pi5_ide.errors import IDEError

from ninjarobot_pi5_ide import RobotIDEClient


class _RobotPresentation:
    def __init__(
        self,
        *,
        countdown_started: bool = True,
        countdown_error: BaseException | None = None,
    ) -> None:
        self.countdown_started = countdown_started
        self.countdown_error = countdown_error
        self.camera_calls = 0
        self.idle_calls = 0

    async def show_camera_capture(self) -> bool:
        self.camera_calls += 1
        if self.countdown_error is not None:
            raise self.countdown_error
        return self.countdown_started

    async def restore_idle_face(self) -> bool:
        self.idle_calls += 1
        return True


class _Identity:
    def __init__(self, *, error: BaseException | None = None) -> None:
        self.error = error
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.block = False
        self.calls = 0

    async def enroll(self, user_id: str) -> dict[str, Any]:
        self.calls += 1
        assert user_id == "local-user"
        if self.error is not None:
            raise self.error
        return {"status": "enrolled"}

    async def identify(self) -> dict[str, Any]:
        self.calls += 1
        self.started.set()
        if self.block:
            await self.release.wait()
        if self.error is not None:
            raise self.error
        return {"status": "unknown"}


def _client(robot: _RobotPresentation, identity: _Identity) -> RobotIDEClient:
    client = RobotIDEClient(
        robot=cast(Any, robot),
        engine=cast(Any, object()),
        identity=cast(Any, identity),
    )
    client._started = True  # type: ignore[attr-defined]
    return client


def test_face_identity_restores_idle_after_success_and_failure() -> None:
    async def exercise() -> None:
        success_robot = _RobotPresentation()
        success = await _client(success_robot, _Identity()).enroll_face_identity("local-user")
        assert success["status"] == "enrolled"
        assert success_robot.idle_calls == 1

        failure_robot = _RobotPresentation()
        failure_client = _client(failure_robot, _Identity(error=RuntimeError("backend failed")))
        with pytest.raises(RuntimeError, match="backend failed"):
            await failure_client.identify_face()
        assert failure_robot.idle_calls == 1

    asyncio.run(exercise())


def test_face_identity_restores_idle_after_cancellation() -> None:
    async def exercise() -> None:
        robot = _RobotPresentation()
        identity = _Identity()
        identity.block = True
        task = asyncio.create_task(_client(robot, identity).identify_face())
        await identity.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert robot.idle_calls == 1

    asyncio.run(exercise())


def test_face_identity_does_not_capture_when_countdown_cannot_start() -> None:
    async def exercise() -> None:
        robot = _RobotPresentation(countdown_started=False)
        identity = _Identity()
        client = _client(robot, identity)
        with pytest.raises(IDEError, match="countdown could not start"):
            await client.enroll_face_identity("local-user")
        assert identity.calls == 0
        assert robot.idle_calls == 1

        failing_robot = _RobotPresentation(countdown_error=RuntimeError("display failed"))
        failing_client = _client(failing_robot, identity)
        with pytest.raises(RuntimeError, match="display failed"):
            await failing_client.enroll_face_identity("local-user")
        assert identity.calls == 0
        assert failing_robot.idle_calls == 1

    asyncio.run(exercise())
