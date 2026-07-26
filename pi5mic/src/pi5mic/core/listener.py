"""Local voice listener state machine for pi5mic."""

from __future__ import annotations

import secrets
import time
from threading import RLock

from pi5mic.errors import ListenerBusyError

from .session import ListenerSnapshot, ListenerState


class MicListener:
    """Single-flight listener state manager with cooldown protection."""

    def __init__(
        self,
        *,
        cooldown_seconds: float = 1.0,
        time_source=None,
    ) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._time = time_source or time.monotonic
        self._lock = RLock()
        self._state = ListenerState.IDLE
        self._active_request_id: str | None = None
        self._cooldown_until = 0.0
        self._last_error: str | None = None

    def arm(self) -> ListenerSnapshot:
        """Arm the listener for the next trigger."""
        with self._lock:
            self._transition_out_of_cooldown_if_needed()
            if self._state in {
                ListenerState.LISTENING,
                ListenerState.TRANSCRIBING,
                ListenerState.DISPATCHING,
                ListenerState.WAITING_FOR_REPLY,
            }:
                raise ListenerBusyError("Listener is busy and cannot be armed right now.")
            self._state = ListenerState.ARMED
            self._last_error = None
            return self.snapshot()

    def can_accept_trigger(self) -> bool:
        """Return whether a new wake-word or manual trigger can be accepted."""
        with self._lock:
            self._transition_out_of_cooldown_if_needed()
            return self._state in {ListenerState.IDLE, ListenerState.ARMED}

    def start_listening(self, request_id: str | None = None) -> ListenerSnapshot:
        """Enter the listening state for a new request."""
        with self._lock:
            self._transition_out_of_cooldown_if_needed()
            if not self.can_accept_trigger():
                raise ListenerBusyError(f"Listener is busy in state '{self._state.value}'.")
            self._state = ListenerState.LISTENING
            self._active_request_id = request_id or self._generate_request_id()
            self._last_error = None
            return self.snapshot()

    def mark_transcribing(self, request_id: str) -> ListenerSnapshot:
        """Advance an active request into transcription."""
        return self._advance(request_id, ListenerState.LISTENING, ListenerState.TRANSCRIBING)

    def mark_dispatching(self, request_id: str) -> ListenerSnapshot:
        """Advance an active request into dispatching."""
        return self._advance(request_id, ListenerState.TRANSCRIBING, ListenerState.DISPATCHING)

    def mark_waiting_for_reply(self, request_id: str) -> ListenerSnapshot:
        """Advance an active request into reply waiting."""
        return self._advance(
            request_id,
            ListenerState.DISPATCHING,
            ListenerState.WAITING_FOR_REPLY,
        )

    def complete(self, request_id: str) -> ListenerSnapshot:
        """Complete an active request and enter cooldown."""
        with self._lock:
            self._require_active_request(request_id)
            self._state = ListenerState.COOLDOWN
            self._active_request_id = None
            self._cooldown_until = self._time() + self._cooldown_seconds
            return self.snapshot()

    def fail(self, request_id: str, message: str) -> ListenerSnapshot:
        """Mark an active request as failed."""
        with self._lock:
            self._require_active_request(request_id)
            self._state = ListenerState.ERROR
            self._active_request_id = None
            self._last_error = message
            self._cooldown_until = 0.0
            return self.snapshot()

    def reset(self) -> ListenerSnapshot:
        """Reset the listener back to idle."""
        with self._lock:
            self._state = ListenerState.IDLE
            self._active_request_id = None
            self._cooldown_until = 0.0
            self._last_error = None
            return self.snapshot()

    def snapshot(self) -> ListenerSnapshot:
        """Return an immutable snapshot of the current state."""
        with self._lock:
            self._transition_out_of_cooldown_if_needed()
            cooldown_remaining = max(0.0, self._cooldown_until - self._time())
            return ListenerSnapshot(
                state=self._state,
                active_request_id=self._active_request_id,
                cooldown_remaining_seconds=round(cooldown_remaining, 6),
                last_error=self._last_error,
            )

    def _advance(
        self,
        request_id: str,
        expected_state: ListenerState,
        next_state: ListenerState,
    ) -> ListenerSnapshot:
        with self._lock:
            self._require_active_request(request_id)
            if self._state is not expected_state:
                raise ListenerBusyError(
                    f"Cannot enter '{next_state.value}' from '{self._state.value}'."
                )
            self._state = next_state
            return self.snapshot()

    def _require_active_request(self, request_id: str) -> None:
        if self._active_request_id != request_id:
            raise ListenerBusyError("Request id does not match the active listener request.")

    def _transition_out_of_cooldown_if_needed(self) -> None:
        if self._state is ListenerState.COOLDOWN and self._time() >= self._cooldown_until:
            self._state = ListenerState.IDLE
            self._cooldown_until = 0.0

    @staticmethod
    def _generate_request_id() -> str:
        return secrets.token_hex(8)
