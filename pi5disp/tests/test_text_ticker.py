"""Tests for the text ticker effect."""

from __future__ import annotations

import time

from pi5disp.effects.text_ticker import TextTicker, load_font


class DummyDisplay:
    """Simple fake display for ticker tests."""

    width = 240
    height = 320

    def __init__(self) -> None:
        self.frames = 0

    def display(self, image) -> None:
        del image
        self.frames += 1


def test_load_font_returns_font_object() -> None:
    """A font should always be returned, even if bundled assets fail."""
    font = load_font("en", 20)
    assert font is not None


def test_ticker_start_stop() -> None:
    """Ticker should start, render, and stop cleanly."""
    lcd = DummyDisplay()
    ticker = TextTicker(lcd, "Hello")
    ticker.start()
    time.sleep(0.05)
    ticker.stop()
    assert lcd.frames > 0
    assert ticker.is_running is False
