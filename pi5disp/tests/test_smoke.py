"""Smoke tests for the scaffolded pi5disp package."""

from pi5disp import ConfigManager, ST7789V


def test_package_exports() -> None:
    """The package should export the expected top-level symbols."""
    assert ConfigManager is not None
    assert ST7789V is not None
