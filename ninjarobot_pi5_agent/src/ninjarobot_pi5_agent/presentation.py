"""Safe conversational face selection through the IDE-owned robot assembly."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Protocol

EMOTION_FACES = frozenset(
    {
        "angry",
        "confusing",
        "cry",
        "curious",
        "error",
        "exciting",
        "happy",
        "laughing",
        "sad",
        "scary",
        "shy",
        "sleepy",
        "success",
        "surprising",
        "warning",
    }
)
PRESENTATION_DIRECTIVE = re.compile(r"^\[\[face:([a-z_]{1,32})\]\][ \t]*")
DIRECTIVE_PREFIX = "[[face:"
TextHandler = Callable[[str], Awaitable[None]]


class AgentFaceClient(Protocol):
    """The narrow IDE presentation boundary used by the agent."""

    async def show_agent_face(self, expression: str) -> bool:
        """Request a silent ambient face."""

    async def restore_idle_face(self) -> bool:
        """Restore the normal silent idle face."""


class PresentationController(Protocol):
    """Conversation lifecycle presentation surface."""

    async def thinking(self) -> None:
        """Show private reasoning in progress."""

    async def responding(self, face: str | None = None) -> None:
        """Show response streaming with an optional approved emotion."""

    async def action_started(self, tool_name: str) -> None:
        """Show that a tool action is being executed."""

    async def action_finished(self, tool_name: str) -> None:
        """Return to thinking after a tool action."""

    async def idle(self) -> None:
        """Restore the normal idle loop."""


class NullPresentationController:
    """No-output controller used by tests and non-robot integrations."""

    async def thinking(self) -> None:
        return None

    async def responding(self, face: str | None = None) -> None:
        return None

    async def action_started(self, tool_name: str) -> None:
        return None

    async def action_finished(self, tool_name: str) -> None:
        return None

    async def idle(self) -> None:
        return None


class RobotPresentationController:
    """Map agent lifecycle states to silent faces through the IDE only."""

    def __init__(self, client: AgentFaceClient) -> None:
        self._client = client

    async def thinking(self) -> None:
        await self._client.show_agent_face("thinking")

    async def responding(self, face: str | None = None) -> None:
        await self._client.show_agent_face(face or "speaking")

    async def action_started(self, tool_name: str) -> None:
        await self._client.show_agent_face("curious")

    async def action_finished(self, tool_name: str) -> None:
        await self._client.show_agent_face("thinking")

    async def idle(self) -> None:
        await self._client.restore_idle_face()


def extract_presentation_directive(text: str) -> tuple[str | None, str]:
    """Remove one bounded leading face directive and return only allowlisted emotion."""
    match = PRESENTATION_DIRECTIVE.match(text)
    if match is None:
        return None, text
    face = match.group(1)
    return (face if face in EMOTION_FACES else None), text[match.end() :]


class StreamingPresentationFilter:
    """Buffer only the possible directive prefix and never stream it to users."""

    def __init__(
        self,
        *,
        on_visible_text: TextHandler,
        on_response_started: Callable[[str | None], Awaitable[None]],
    ) -> None:
        self._on_visible_text = on_visible_text
        self._on_response_started = on_response_started
        self._buffer = ""
        self._started = False

    async def feed(self, text: str) -> None:
        if not text:
            return
        if self._started:
            await self._on_visible_text(text)
            return
        self._buffer += text
        if DIRECTIVE_PREFIX.startswith(self._buffer):
            return
        if self._buffer.startswith(DIRECTIVE_PREFIX) and "]]" not in self._buffer:
            if len(self._buffer) <= 48 and "\n" not in self._buffer:
                return
        face, visible = extract_presentation_directive(self._buffer)
        await self._start(face)
        if visible:
            await self._on_visible_text(visible)
        self._buffer = ""

    async def finish(self) -> None:
        if self._started:
            return
        face, visible = extract_presentation_directive(self._buffer)
        await self._start(face)
        if visible:
            await self._on_visible_text(visible)
        self._buffer = ""

    async def _start(self, face: str | None) -> None:
        if self._started:
            return
        self._started = True
        await self._on_response_started(face)
