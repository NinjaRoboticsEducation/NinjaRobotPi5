"""Tests for the interactive display tool session behavior."""

from __future__ import annotations

from pi5disp.cli import display_tool as display_tool_module


class FakeDisplay:
    """Minimal display stub for interactive tool tests."""

    def __init__(self) -> None:
        self.clear_calls = 0
        self.brightness_calls: list[int] = []
        self.close_calls = 0

    def health_check(self) -> bool:
        return True

    def clear(self) -> None:
        self.clear_calls += 1

    def set_brightness(self, percent: int) -> None:
        self.brightness_calls.append(percent)

    def close(self) -> None:
        self.close_calls += 1


def test_display_tool_reuses_display_between_demo_and_brightness(monkeypatch) -> None:
    """Demo, brightness, then demo again should reuse one live display."""
    create_calls: list[FakeDisplay] = []
    fake_display = FakeDisplay()
    saved: dict[str, int] = {}

    def fake_create_display():
        create_calls.append(fake_display)
        return fake_display

    class FakeConfigManager:
        def load(self) -> dict[str, int]:
            return {"brightness": 100}

        def set(self, key: str, value: int) -> None:
            saved[key] = value

    prompt_values = iter([3, 10.0, 50, 3, 10.0])

    monkeypatch.setattr(display_tool_module, "create_display", fake_create_display)
    monkeypatch.setattr(
        "pi5disp.cli.demo_cmd._run_ball_demo",
        lambda lcd, num_balls, fps, duration: None,
    )
    monkeypatch.setattr(display_tool_module, "ConfigManager", FakeConfigManager)
    monkeypatch.setattr(
        display_tool_module.click,
        "prompt",
        lambda *args, **kwargs: next(prompt_values),
    )

    session = display_tool_module.DisplayToolSession()
    display_tool_module._do_demo(session)
    display_tool_module._do_brightness(session)
    display_tool_module._do_demo(session)
    session.close()

    assert len(create_calls) == 1
    assert saved["brightness"] == 50
    assert fake_display.brightness_calls == [50]
    assert fake_display.clear_calls == 2
    assert fake_display.close_calls == 1


def test_do_init_closes_existing_session(monkeypatch) -> None:
    """Re-initializing config should invalidate the live display session."""

    class FakeConfigManager:
        def init_config(self, interactive: bool = True) -> dict[str, int]:
            assert interactive is True
            return {"brightness": 100}

    fake_display = FakeDisplay()
    session = display_tool_module.DisplayToolSession(lcd=fake_display)

    monkeypatch.setattr(display_tool_module, "ConfigManager", FakeConfigManager)

    display_tool_module._do_init(session)

    assert session.lcd is None
    assert fake_display.close_calls == 1
