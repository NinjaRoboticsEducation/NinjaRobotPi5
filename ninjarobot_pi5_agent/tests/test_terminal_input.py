from __future__ import annotations

import asyncio

from ninjarobot_pi5_agent.terminal_input import EditableChatInput
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput


def _edit(keys: bytes) -> str:
    async def run() -> str:
        with create_pipe_input() as pipe:
            reader = EditableChatInput(input_stream=pipe, output=DummyOutput())
            pipe.send_bytes(keys)
            return await reader.read("You> ")

    return asyncio.run(run())


def test_arrow_keys_edit_without_leaking_escape_sequences() -> None:
    assert _edit(b"ac\x1b[Db\r") == "abc"


def test_meta_enter_adds_newline_and_enter_sends() -> None:
    assert _edit(b"first\x1b\rsecond\r") == "first\nsecond"


def test_shift_enter_kitty_sequence_adds_newline() -> None:
    assert _edit(b"first\x1b[13;2usecond\r") == "first\nsecond"


def test_multiline_arrows_move_between_lines() -> None:
    assert _edit(b"ab\x1b\rcd\x1b[A\x1b[DZ\r") == "aZb\ncd"
