"""Music helpers layered on top of the pi5buzzer core driver."""

from __future__ import annotations

import logging
from typing import Optional

from pi5buzzer.core.driver import Buzzer, PWMBackend
from pi5buzzer.notes import (
    DEMO_SONG,
    EMOTION_SOUNDS,
    KEYBOARD_MAP,
    NOTES,
    get_emotion_names,
)

try:
    from ninja_utils import get_logger

    log = get_logger(__name__)
except ImportError:
    log = logging.getLogger(__name__)


class MusicBuzzer(Buzzer):
    """Extended buzzer with named notes, songs, and emotion sounds."""

    def __init__(
        self,
        pin: int,
        pi: Optional[PWMBackend] = None,
        volume: int = 128,
        backend: Optional[PWMBackend] = None,
    ):
        super().__init__(pin=pin, pi=pi, volume=volume, backend=backend)

    def play_note(self, note_name: str, duration: float = 0.3) -> None:
        """Play a named note if it exists in the shared note table."""
        frequency = NOTES.get(note_name.upper())
        if frequency:
            self.execute({"frequency": frequency, "duration": duration})
            return

        log.warning("Unknown note: %s", note_name)

    def play_song(self, song: list[tuple[str, float]]) -> None:
        """Queue a song as note and pause tuples."""
        for note_name, duration in song:
            if note_name == "pause":
                self.queue_pause(duration)
                continue

            frequency = NOTES.get(note_name.upper())
            if frequency:
                self.execute({"frequency": frequency, "duration": duration})
            else:
                log.warning("Unknown note in song: %s", note_name)

    def play_emotion(self, name: str) -> None:
        """Queue one of the predefined emotion sounds."""
        sound = EMOTION_SOUNDS.get(name)
        if sound is None:
            log.warning(
                "Unknown emotion: %s. Available: %s",
                name,
                ", ".join(get_emotion_names()),
            )
            return

        self.play_song(sound)

    def play_demo(self) -> None:
        """Play the built-in demo melody."""
        self.play_song(DEMO_SONG)

    def play_music(self) -> None:
        """Interactive keyboard piano mode."""
        if not self.is_initialized:
            log.warning("Buzzer not initialized. Call initialize() first.")
            return

        print("\nInteractive Piano Mode")
        print("=" * 40)
        print("Bottom row (z x c v b n m) -> C4-B4")
        print("Home row   (a s d f g h j) -> C5-B5")
        print("Top row    (q w e r t y u) -> C6-B6")
        print("Type 'quit' or press Ctrl+C to exit")
        print("=" * 40)

        try:
            while True:
                try:
                    key = input("> ").strip()
                except EOFError:
                    break

                if key.lower() in ("quit", "exit", "q"):
                    print("Exiting piano mode.")
                    break

                if not key:
                    continue

                for char in key:
                    note_name = KEYBOARD_MAP.get(char.lower())
                    if note_name:
                        frequency = NOTES[note_name]
                        print(f"  * {note_name} ({frequency} Hz)")
                        self.play_sound(frequency, 0.3)
                    else:
                        print(f"  ? Unknown key: '{char}'")
        except KeyboardInterrupt:
            print("\nExiting piano mode.")
