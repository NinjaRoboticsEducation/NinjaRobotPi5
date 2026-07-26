"""Text ticker effect for pi5disp."""

from __future__ import annotations

import importlib.resources
import threading
import time

from PIL import Image, ImageDraw, ImageFont


def load_font(language: str = "en", size: int = 32) -> ImageFont.FreeTypeFont:
    """Load a bundled font based on language preference."""
    font_map = {
        "en": "NotoSans-Regular.ttf",
        "ja": "NotoSansJP-Regular.otf",
        "zh-tw": "NotoSansTC-Regular.otf",
    }
    font_file = font_map.get(language, font_map["en"])

    try:
        font_ref = importlib.resources.files("pi5disp.fonts").joinpath(font_file)
        with importlib.resources.as_file(font_ref) as path:
            return ImageFont.truetype(str(path), size)
    except (FileNotFoundError, OSError, ModuleNotFoundError):
        try:
            return ImageFont.truetype(font_file, size)
        except (OSError, IOError):
            return ImageFont.load_default()


class TextTicker:
    """Scrolling marquee effect for ST7789V displays."""

    def __init__(
        self,
        lcd,
        text: str,
        *,
        font_size: int = 32,
        color: tuple[int, int, int] = (255, 255, 255),
        bg_color: tuple[int, int, int] = (0, 0, 0),
        speed: float = 2.0,
        language: str = "en",
    ) -> None:
        self._lcd = lcd
        self._text = text
        self._font_size = font_size
        self._color = color
        self._bg_color = bg_color
        self._speed = speed
        self._language = language
        self._font = load_font(language, font_size)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        temp_image = Image.new("RGB", (1, 1), bg_color)
        temp_draw = ImageDraw.Draw(temp_image)
        bbox = temp_draw.textbbox((0, 0), text, font=self._font)
        self._text_width = bbox[2] - bbox[0]
        self._text_height = bbox[3] - bbox[1]

    def start(self) -> None:
        """Start the scrolling effect."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scroll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the scrolling effect."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    @property
    def is_running(self) -> bool:
        """Whether the ticker thread is currently running."""
        return self._thread is not None and self._thread.is_alive()

    def _scroll_loop(self) -> None:
        """Main scrolling animation loop."""
        display_w = self._lcd.width
        display_h = self._lcd.height
        x_pos = float(display_w)
        y_pos = (display_h - self._text_height) // 2

        while not self._stop_event.is_set():
            image = Image.new("RGB", (display_w, display_h), self._bg_color)
            draw = ImageDraw.Draw(image)
            draw.text(
                (int(x_pos), y_pos),
                self._text,
                font=self._font,
                fill=self._color,
            )

            try:
                self._lcd.display(image)
            except Exception:
                break

            x_pos -= self._speed
            if x_pos < -self._text_width:
                x_pos = float(display_w)

            time.sleep(1 / 30)
