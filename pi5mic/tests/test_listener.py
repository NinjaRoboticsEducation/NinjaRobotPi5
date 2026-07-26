"""Tests for the pi5mic listener state machine."""

from __future__ import annotations

import pytest

from pi5mic.core.listener import MicListener
from pi5mic.core.session import ListenerState
from pi5mic.errors import ListenerBusyError


class _FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def test_listener_moves_through_happy_path() -> None:
    clock = _FakeClock()
    listener = MicListener(cooldown_seconds=1.5, time_source=clock)

    assert listener.arm().state is ListenerState.ARMED
    listening = listener.start_listening("req-1")
    assert listening.state is ListenerState.LISTENING
    assert listening.active_request_id == "req-1"
    assert listener.mark_transcribing("req-1").state is ListenerState.TRANSCRIBING
    assert listener.mark_dispatching("req-1").state is ListenerState.DISPATCHING
    assert listener.mark_waiting_for_reply("req-1").state is ListenerState.WAITING_FOR_REPLY

    cooldown = listener.complete("req-1")
    assert cooldown.state is ListenerState.COOLDOWN
    assert cooldown.active_request_id is None
    assert cooldown.cooldown_remaining_seconds == 1.5

    clock.value = 2.0
    assert listener.snapshot().state is ListenerState.IDLE
    assert listener.can_accept_trigger() is True


def test_listener_rejects_trigger_while_busy() -> None:
    listener = MicListener()
    listener.arm()
    listener.start_listening("req-1")

    with pytest.raises(ListenerBusyError, match="busy"):
        listener.start_listening("req-2")


def test_listener_fail_records_last_error() -> None:
    listener = MicListener()
    listener.arm()
    listener.start_listening("req-1")

    failed = listener.fail("req-1", "network timeout")

    assert failed.state is ListenerState.ERROR
    assert failed.last_error == "network timeout"


def test_listener_rejects_wrong_request_id() -> None:
    listener = MicListener()
    listener.arm()
    listener.start_listening("req-1")

    with pytest.raises(ListenerBusyError, match="does not match"):
        listener.mark_transcribing("req-2")
