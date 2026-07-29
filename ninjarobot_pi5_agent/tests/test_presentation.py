from __future__ import annotations

import asyncio

from ninjarobot_pi5_agent import (
    EMOTION_FACES,
    RobotPresentationController,
    StreamingPresentationFilter,
    extract_presentation_directive,
)


class _FaceClient:
    def __init__(self) -> None:
        self.faces: list[str] = []
        self.idle_count = 0
        self.camera_count = 0

    async def show_agent_face(self, expression: str) -> bool:
        self.faces.append(expression)
        return True

    async def restore_idle_face(self) -> bool:
        self.idle_count += 1
        return True

    async def show_camera_capture(self) -> bool:
        self.camera_count += 1
        return True


def test_directive_parser_strips_only_bounded_leading_directive() -> None:
    assert extract_presentation_directive("[[face:happy]] Hello") == ("happy", "Hello")
    assert extract_presentation_directive("[[face:execute_shell]] No") == (None, "No")
    assert extract_presentation_directive("Hello [[face:happy]]") == (
        None,
        "Hello [[face:happy]]",
    )
    assert "thinking" not in EMOTION_FACES


def test_streaming_filter_hides_split_directive_and_selects_emotion() -> None:
    async def exercise() -> None:
        visible: list[str] = []
        faces: list[str | None] = []

        async def record_text(text: str) -> None:
            visible.append(text)

        async def record_face(face: str | None) -> None:
            faces.append(face)

        stream = StreamingPresentationFilter(
            on_visible_text=record_text,
            on_response_started=record_face,
        )
        for chunk in ("[[fa", "ce:happy", "]] ", "Hello", " robot"):
            await stream.feed(chunk)
        await stream.finish()

        assert faces == ["happy"]
        assert "".join(visible) == "Hello robot"

    asyncio.run(exercise())


def test_robot_presentation_maps_lifecycle_to_ide_faces() -> None:
    async def exercise() -> None:
        client = _FaceClient()
        presentation = RobotPresentationController(client)

        await presentation.thinking()
        await presentation.responding()
        await presentation.responding("success")
        await presentation.action_started("robot.behavior.run")
        await presentation.action_started("robot.camera.preview")
        await presentation.action_finished("robot.behavior.run")
        await presentation.idle()

        assert client.faces == [
            "thinking",
            "speaking",
            "success",
            "curious",
            "thinking",
        ]
        assert client.idle_count == 1
        assert client.camera_count == 1

    asyncio.run(exercise())
