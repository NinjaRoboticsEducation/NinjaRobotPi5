"""CLI smoke tests for pi5disp."""

from __future__ import annotations

from click.testing import CliRunner

from pi5disp.__main__ import cli
from pi5disp.cli import _common


def test_cli_help_shows_commands() -> None:
    """Help output should include the migrated commands."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "display-tool" in result.output
    assert "brightness" in result.output
    assert "config" in result.output


def test_config_show_works() -> None:
    """Config show should print the saved display settings."""
    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert "Display Configuration" in result.output


def test_create_display_applies_saved_brightness(monkeypatch) -> None:
    """Saved brightness should be applied when creating a display."""

    class FakeDisplay:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.brightness_calls: list[int] = []

        def set_brightness(self, percent: int) -> None:
            self.brightness_calls.append(percent)

    monkeypatch.setattr(
        _common,
        "load_config",
        lambda: (
            object(),
            {
                "dc_pin": 14,
                "rst_pin": 15,
                "backlight_pin": 16,
                "width": 240,
                "height": 320,
                "rotation": 90,
                "brightness": 37,
                "spi_speed_mhz": 32,
            },
        ),
    )
    monkeypatch.setattr(_common, "ST7789V", FakeDisplay)

    lcd = _common.create_display()

    assert lcd.brightness_calls == [37]


def test_brightness_command_persists_config(monkeypatch) -> None:
    """Brightness command should save the requested brightness."""
    runner = CliRunner()
    saved: dict[str, int] = {}

    class FakeConfigManager:
        def load(self) -> dict[str, int]:
            return {"brightness": 100}

        def set(self, key: str, value: int) -> None:
            saved[key] = value

    class FakeDisplay:
        def close(self) -> None:
            saved["closed"] = 1

    monkeypatch.setattr("pi5disp.__main__.ConfigManager", FakeConfigManager)
    monkeypatch.setattr("pi5disp.__main__.create_display", lambda: FakeDisplay())

    result = runner.invoke(cli, ["brightness", "50"])

    assert result.exit_code == 0
    assert saved["brightness"] == 50
    assert saved["closed"] == 1
