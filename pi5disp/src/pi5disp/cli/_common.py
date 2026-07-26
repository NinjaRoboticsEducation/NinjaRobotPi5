"""Shared CLI helpers for pi5disp."""

from __future__ import annotations

from pi5disp.config.config_manager import ConfigManager
from pi5disp.core.driver import ST7789V


def load_config() -> tuple[ConfigManager, dict]:
    """Load the current display configuration."""
    manager = ConfigManager()
    return manager, manager.load()


def create_display(*, rotation: int | None = None) -> ST7789V:
    """Create an ST7789V instance from the saved config."""
    _manager, config = load_config()
    display_rotation = rotation if rotation is not None else config.get("rotation", 0)
    brightness = int(config.get("brightness", 100))
    lcd = ST7789V(
        dc_pin=config.get("dc_pin", 14),
        rst_pin=config.get("rst_pin", 15),
        backlight_pin=config.get("backlight_pin", 16),
        width=config.get("width", 240),
        height=config.get("height", 320),
        rotation=display_rotation,
        speed_hz=config.get("spi_speed_mhz", 32) * 1_000_000,
    )
    lcd.set_brightness(max(0, min(100, brightness)))
    return lcd
