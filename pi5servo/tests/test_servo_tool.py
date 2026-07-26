"""Regression tests for the interactive servo tool."""

from __future__ import annotations

import importlib
from contextlib import nullcontext

from click.testing import CliRunner

from pi5servo.config import ConfigManager
from pi5servo.core import ServoCalibration
from pi5servo.core.backend_errors import BackendConfigurationError

servo_tool_module = importlib.import_module("pi5servo.cli.servo_tool")


class FakeTerminal:
    """Minimal blessed.Terminal stand-in for menu tests."""

    def clear(self) -> str:
        return ""

    def bold(self, text: str) -> str:
        return text

    def cyan(self, text: str) -> str:
        return text

    def green(self, text: str) -> str:
        return text

    def red(self, text: str) -> str:
        return text

    def yellow(self, text: str) -> str:
        return text

    def cbreak(self):
        return nullcontext()

    def hidden_cursor(self):
        return nullcontext()


class FakePersistentGroup:
    """Simple persistent group stub used by the interactive tool."""

    def __init__(
        self,
        *,
        pins: list[int | str],
        backend: object,
        servos: dict[int | str, object] | None = None,
    ) -> None:
        self.pins = pins
        self.backend = backend
        self._servos = dict(servos or {})
        self.centered = False
        self.closed = False
        self.off_called = False
        self.move_calls: list[tuple[list[float], str, bool]] = []
        self.execute_calls: list[tuple[str, bool]] = []
        self.updated_calibrations: list[tuple[int | str, ServoCalibration]] = []

    def center_all(self) -> None:
        self.centered = True

    def move_all_sync(
        self,
        angles: list[float],
        *,
        speed_mode: str,
        force: bool,
    ) -> None:
        self.move_calls.append((angles, speed_mode, force))

    def off(self) -> None:
        self.off_called = True

    def execute_command(self, command: str, *, force: bool = False) -> bool:
        self.execute_calls.append((command, force))
        return True

    def get_servo(self, pin: int | str):
        return self._servos.get(pin)

    def update_calibration(self, pin: int | str, calibration: ServoCalibration) -> None:
        self.updated_calibrations.append((pin, calibration))
        servo = self.get_servo(pin)
        if servo is not None:
            servo.calibration = calibration

    def close(self) -> None:
        self.closed = True


class FakeTransientServo:
    """Simple temporary servo stub for calibration flow tests."""

    def __init__(
        self,
        _runtime,
        pin,
        _calibration,
        *,
        backend=None,
        backend_kwargs=None,
        owns_backend=None,
    ) -> None:
        self.pin = pin
        self.backend = backend
        self.backend_kwargs = backend_kwargs
        self.owns_backend = owns_backend
        self.calibration = _calibration or ServoCalibration()
        self.closed = False
        self.off_called = False
        self.angles: list[float] = []
        self.pulses: list[int] = []

    def close(self) -> None:
        self.closed = True

    def off(self) -> None:
        self.off_called = True

    def set_angle(self, angle: float) -> None:
        self.angles.append(angle)

    def set_pulse(self, pulse: int) -> None:
        self.pulses.append(pulse)


class FakeCalibApp:
    """Calibration app stub that avoids interactive TUI behavior."""

    def __init__(self, servo, *_args, owns_servo=True, **_kwargs) -> None:
        self.servo = servo
        self.owns_servo = owns_servo

    def main(self) -> None:
        return None

    def end(self) -> None:
        self.servo.off()
        if self.owns_servo:
            self.servo.close()


def test_servo_tool_uses_auto_backend_for_hat_calibration(monkeypatch, tmp_path) -> None:
    """Calibrating a new HAT endpoint should not reuse the persistent GPIO backend."""
    config_path = tmp_path / "servo.json"
    manager = ConfigManager(config_path)
    manager.set_calibration(12, ServoCalibration())
    manager.save()
    manager.load()

    persistent_group = FakePersistentGroup(pins=[12], backend=object())
    captured: dict[str, object] = {}

    class CapturingServo(FakeTransientServo):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            captured["pin"] = self.pin
            captured["backend"] = self.backend
            captured["backend_kwargs"] = self.backend_kwargs

    monkeypatch.setattr(servo_tool_module, "HAS_BLESSED", True)
    monkeypatch.setattr(servo_tool_module, "Terminal", FakeTerminal)
    monkeypatch.setattr(servo_tool_module, "CalibApp", FakeCalibApp)
    monkeypatch.setattr(servo_tool_module, "Servo", CapturingServo)
    monkeypatch.setattr(servo_tool_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        servo_tool_module,
        "create_group_from_config",
        lambda **_kwargs: (persistent_group, manager, None, "auto", {}),
    )

    runner = CliRunner()
    result = runner.invoke(
        servo_tool_module.servo_tool, ["--config", str(config_path)], input="3\nhat_pwm1\nq\n"
    )

    assert result.exit_code == 0, result.output
    assert captured["pin"] == "hat_pwm1"
    assert captured["backend"] == "auto"
    assert captured["backend_kwargs"] == {}
    assert "✓ Config reloaded" in result.output


def test_servo_tool_uses_isolated_backend_for_unconfigured_native_calibration(
    monkeypatch,
    tmp_path,
) -> None:
    """Unconfigured native endpoints should still use an isolated temporary servo."""
    config_path = tmp_path / "servo.json"
    manager = ConfigManager(config_path)
    manager.set_calibration(12, ServoCalibration())
    manager.save()
    manager.load()

    shared_backend = object()
    persistent_group = FakePersistentGroup(pins=[12], backend=shared_backend)
    refreshed_group = FakePersistentGroup(pins=[12], backend=object())
    captured: dict[str, object] = {}
    groups = iter(
        [
            (persistent_group, manager, None, "auto", {}),
            (refreshed_group, manager, None, "auto", {}),
        ]
    )

    class CapturingServo(FakeTransientServo):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            captured["pin"] = self.pin
            captured["backend"] = self.backend
            captured["backend_kwargs"] = self.backend_kwargs

    monkeypatch.setattr(servo_tool_module, "HAS_BLESSED", True)
    monkeypatch.setattr(servo_tool_module, "Terminal", FakeTerminal)
    monkeypatch.setattr(servo_tool_module, "CalibApp", FakeCalibApp)
    monkeypatch.setattr(servo_tool_module, "Servo", CapturingServo)
    monkeypatch.setattr(servo_tool_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        servo_tool_module,
        "create_group_from_config",
        lambda **_kwargs: next(groups),
    )

    runner = CliRunner()
    result = runner.invoke(
        servo_tool_module.servo_tool, ["--config", str(config_path)], input="3\n13\nq\n"
    )

    assert result.exit_code == 0, result.output
    assert captured["pin"] == 13
    assert captured["backend"] == "auto"
    assert captured["backend_kwargs"] == {}
    assert persistent_group.closed is True


def test_servo_tool_reuses_persistent_servo_for_configured_native_calibration(
    monkeypatch,
    tmp_path,
) -> None:
    """Configured native endpoints should calibrate in place without reopening PWM."""
    config_path = tmp_path / "servo.json"
    manager = ConfigManager(config_path)
    manager.set_calibration(12, ServoCalibration())
    manager.set_calibration(13, ServoCalibration())
    manager.save()
    manager.load()

    borrowed_servo = FakeTransientServo(None, 13, manager.get_calibration(13))
    persistent_group = FakePersistentGroup(
        pins=[12, 13],
        backend=object(),
        servos={13: borrowed_servo},
    )
    captured: dict[str, object] = {"group_builds": 0}

    class CapturingCalibApp(FakeCalibApp):
        def __init__(self, servo, *args, owns_servo=True, **kwargs) -> None:
            super().__init__(servo, *args, owns_servo=owns_servo, **kwargs)
            captured["servo"] = servo
            captured["owns_servo"] = owns_servo
            captured["persistent_group_closed_when_calibration_started"] = persistent_group.closed

    class UnexpectedTransientServo(FakeTransientServo):
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("configured native calibration should reuse the persistent servo")

    monkeypatch.setattr(servo_tool_module, "HAS_BLESSED", True)
    monkeypatch.setattr(servo_tool_module, "Terminal", FakeTerminal)
    monkeypatch.setattr(servo_tool_module, "CalibApp", CapturingCalibApp)
    monkeypatch.setattr(servo_tool_module, "Servo", UnexpectedTransientServo)
    monkeypatch.setattr(servo_tool_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        servo_tool_module,
        "create_group_from_config",
        lambda **_kwargs: (
            captured.__setitem__("group_builds", captured["group_builds"] + 1)
            or (persistent_group, manager, None, "auto", {})
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        servo_tool_module.servo_tool, ["--config", str(config_path)], input="3\n13\nq\n"
    )

    assert result.exit_code == 0, result.output
    assert captured["servo"] is borrowed_servo
    assert captured["owns_servo"] is False
    assert captured["persistent_group_closed_when_calibration_started"] is False
    assert captured["group_builds"] == 1
    assert borrowed_servo.closed is False
    assert borrowed_servo.off_called is True
    assert persistent_group.updated_calibrations == [(13, manager.get_calibration(13))]


def test_servo_tool_skips_persistent_group_when_config_is_empty(monkeypatch, tmp_path) -> None:
    """Empty configs should no longer default the interactive tool to GPIO12/GPIO13."""
    config_path = tmp_path / "servo.json"
    ConfigManager(config_path).save()

    monkeypatch.setattr(servo_tool_module, "HAS_BLESSED", True)
    monkeypatch.setattr(servo_tool_module, "Terminal", FakeTerminal)
    monkeypatch.setattr(
        servo_tool_module,
        "create_group_from_config",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("should not build a persistent group")
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        servo_tool_module.servo_tool, ["--config", str(config_path)], input="q\n"
    )

    assert result.exit_code == 0, result.output
    assert "No configured endpoints found." in result.output


def test_servo_tool_recovers_from_endpoint_error(monkeypatch, tmp_path) -> None:
    """Calibration errors should stay inside the menu instead of crashing the whole tool."""
    config_path = tmp_path / "servo.json"
    ConfigManager(config_path).save()

    class RaisingServo(FakeTransientServo):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            raise BackendConfigurationError("RP1 hardware PWM only supports native GPIO endpoints.")

    monkeypatch.setattr(servo_tool_module, "HAS_BLESSED", True)
    monkeypatch.setattr(servo_tool_module, "Terminal", FakeTerminal)
    monkeypatch.setattr(servo_tool_module, "Servo", RaisingServo)

    runner = CliRunner()
    result = runner.invoke(
        servo_tool_module.servo_tool,
        ["--config", str(config_path)],
        input="3\nhat_pwm1\n\nq\n",
    )

    assert result.exit_code == 0, result.output
    assert "✗ Error: RP1 hardware PWM only supports native GPIO endpoints." in result.output
    assert "Goodbye!" in result.output


def test_servo_tool_quick_move_forces_command_execution(monkeypatch, tmp_path) -> None:
    """Quick move should force PWM writes so return-to-center commands are not skipped."""
    config_path = tmp_path / "servo.json"
    manager = ConfigManager(config_path)
    manager.set_calibration(12, ServoCalibration())
    manager.set_calibration(13, ServoCalibration())
    manager.save()
    manager.load()

    persistent_group = FakePersistentGroup(pins=[12, 13], backend=object())

    monkeypatch.setattr(servo_tool_module, "HAS_BLESSED", True)
    monkeypatch.setattr(servo_tool_module, "Terminal", FakeTerminal)
    monkeypatch.setattr(servo_tool_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        servo_tool_module,
        "create_group_from_config",
        lambda **_kwargs: (persistent_group, manager, None, "auto", {}),
    )

    runner = CliRunner()
    result = runner.invoke(
        servo_tool_module.servo_tool,
        ["--config", str(config_path)],
        input="1\nF_gpio12:0/gpio13:0\nq\nq\n",
    )

    assert result.exit_code == 0, result.output
    assert persistent_group.execute_calls == [("F_gpio12:0/gpio13:0", True)]
    assert "✓ Done" in result.output


def test_servo_tool_rebuilds_persistent_group_after_calibration(monkeypatch, tmp_path) -> None:
    """Quick Move after isolated calibration should use a rebuilt persistent group."""
    config_path = tmp_path / "servo.json"
    manager = ConfigManager(config_path)
    manager.set_calibration(12, ServoCalibration())
    manager.save()
    manager.load()

    first_group = FakePersistentGroup(pins=[12], backend=object())
    second_group = FakePersistentGroup(pins=[12], backend=object())
    groups = iter(
        [
            (first_group, manager, None, "auto", {}),
            (second_group, manager, None, "auto", {}),
        ]
    )

    monkeypatch.setattr(servo_tool_module, "HAS_BLESSED", True)
    monkeypatch.setattr(servo_tool_module, "Terminal", FakeTerminal)
    monkeypatch.setattr(servo_tool_module, "CalibApp", FakeCalibApp)
    monkeypatch.setattr(servo_tool_module, "Servo", FakeTransientServo)
    monkeypatch.setattr(servo_tool_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        servo_tool_module,
        "create_group_from_config",
        lambda **_kwargs: next(groups),
    )

    runner = CliRunner()
    result = runner.invoke(
        servo_tool_module.servo_tool,
        ["--config", str(config_path)],
        input="3\n13\n1\nF_12:0\nq\nq\n",
    )

    assert result.exit_code == 0, result.output
    assert first_group.closed is True
    assert first_group.execute_calls == []
    assert second_group.execute_calls == [("F_12:0", True)]


def test_servo_tool_single_move_reuses_persistent_servo_for_configured_native_endpoint(
    monkeypatch,
    tmp_path,
) -> None:
    """Configured native Single Move should use the live servo and keep the group open."""
    config_path = tmp_path / "servo.json"
    manager = ConfigManager(config_path)
    manager.set_calibration(12, ServoCalibration())
    manager.set_calibration(13, ServoCalibration())
    manager.save()
    manager.load()

    borrowed_servo = FakeTransientServo(None, 13, manager.get_calibration(13))
    persistent_group = FakePersistentGroup(
        pins=[12, 13],
        backend=object(),
        servos={13: borrowed_servo},
    )
    captured: dict[str, object] = {"group_builds": 0}

    class UnexpectedTransientServo(FakeTransientServo):
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("configured native single-move should reuse the persistent servo")

    def capture_angle(angle: float) -> None:
        captured["persistent_group_closed_when_moving"] = persistent_group.closed
        borrowed_servo.angles.append(angle)

    borrowed_servo.set_angle = capture_angle

    monkeypatch.setattr(servo_tool_module, "HAS_BLESSED", True)
    monkeypatch.setattr(servo_tool_module, "Terminal", FakeTerminal)
    monkeypatch.setattr(servo_tool_module, "Servo", UnexpectedTransientServo)
    monkeypatch.setattr(servo_tool_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        servo_tool_module,
        "create_group_from_config",
        lambda **_kwargs: (
            captured.__setitem__("group_builds", captured["group_builds"] + 1)
            or (persistent_group, manager, None, "auto", {})
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        servo_tool_module.servo_tool,
        ["--config", str(config_path)],
        input="2\n13\ncenter\nq\nq\n",
    )

    assert result.exit_code == 0, result.output
    assert captured["persistent_group_closed_when_moving"] is False
    assert captured["group_builds"] == 1
    assert borrowed_servo.closed is False
    assert borrowed_servo.angles == [0.0]
    assert borrowed_servo.off_called is True


def test_servo_tool_single_move_releases_persistent_group_for_unconfigured_native_endpoint(
    monkeypatch,
    tmp_path,
) -> None:
    """Unconfigured native Single Move should still suspend the live group first."""
    config_path = tmp_path / "servo.json"
    manager = ConfigManager(config_path)
    manager.set_calibration(12, ServoCalibration())
    manager.save()
    manager.load()

    first_group = FakePersistentGroup(pins=[12], backend=object())
    second_group = FakePersistentGroup(pins=[12], backend=object())
    groups = iter(
        [
            (first_group, manager, None, "auto", {}),
            (second_group, manager, None, "auto", {}),
        ]
    )
    captured: dict[str, object] = {}

    class CapturingServo(FakeTransientServo):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            captured["pin"] = self.pin
            captured["persistent_group_closed_before_servo"] = first_group.closed

    monkeypatch.setattr(servo_tool_module, "HAS_BLESSED", True)
    monkeypatch.setattr(servo_tool_module, "Terminal", FakeTerminal)
    monkeypatch.setattr(servo_tool_module, "Servo", CapturingServo)
    monkeypatch.setattr(servo_tool_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        servo_tool_module,
        "create_group_from_config",
        lambda **_kwargs: next(groups),
    )

    runner = CliRunner()
    result = runner.invoke(
        servo_tool_module.servo_tool,
        ["--config", str(config_path)],
        input="2\n13\ncenter\nq\nq\n",
    )

    assert result.exit_code == 0, result.output
    assert captured["pin"] == 13
    assert captured["persistent_group_closed_before_servo"] is True
    assert first_group.closed is True
    assert second_group.execute_calls == []
