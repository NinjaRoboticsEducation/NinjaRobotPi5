"""Editable terminal input for NinjaRobot chat."""

from __future__ import annotations

import sys
from typing import Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.application.current import get_app
from prompt_toolkit.input import Input
from prompt_toolkit.input.vt100_parser import ANSI_SEQUENCES  # type: ignore[attr-defined]
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.output import Output

CHAT_INPUT_HINT = (
    "Arrow keys: edit your prompt | Enter: send | Shift+Enter or Alt+Enter "
    "(Mac: Option+Enter): new line | If unsupported: Esc, then Enter | /help: commands"
)

# Terminals using the Kitty keyboard protocol can distinguish Shift+Enter from
# Enter. Map its two common encodings to Control-J, which our bindings reserve
# for inserting a newline. Terminals that send an ordinary CR for Shift+Enter
# cannot be distinguished; Meta/Option+Enter and Esc then Enter remain portable.
ANSI_SEQUENCES.setdefault("\x1b[13;2u", Keys.ControlJ)
ANSI_SEQUENCES.setdefault("\x1b[27;2;13~", Keys.ControlJ)


class ChatInput(Protocol):
    """Read one complete chat prompt without owning chat command semantics."""

    async def read(self, prompt: str) -> str: ...


class PlainChatInput:
    """Compatibility input for redirected streams and unit-test consoles."""

    async def read(self, prompt: str) -> str:
        return input(prompt)


def _chat_bindings() -> KeyBindings:
    bindings = KeyBindings()

    @bindings.add("enter")
    def _send_prompt(event: object) -> None:
        get_app().current_buffer.validate_and_handle()

    @bindings.add("c-j")
    def _shift_enter(event: object) -> None:
        get_app().current_buffer.insert_text("\n")

    @bindings.add("escape", "enter", eager=True)
    def _meta_enter(event: object) -> None:
        get_app().current_buffer.insert_text("\n")

    return bindings


class EditableChatInput:
    """Prompt-toolkit editor with cursor navigation and multiline composition."""

    def __init__(self, *, input_stream: Input | None = None, output: Output | None = None) -> None:
        self._session: PromptSession[str] = PromptSession(
            multiline=True,
            key_bindings=_chat_bindings(),
            input=input_stream,
            output=output,
        )

    async def read(self, prompt: str) -> str:
        return await self._session.prompt_async(
            prompt,
            prompt_continuation=lambda width, _line, _soft: "." * min(width, 3) + " ",
        )


def chat_input_for_terminal() -> ChatInput:
    """Use terminal editing only when both sides are interactive terminals."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        return EditableChatInput()
    return PlainChatInput()
