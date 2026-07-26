"""Unit tests for backend-aware CLI commands."""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock

from click.testing import CliRunner

from pi5servo.cli._common import format_endpoint_label, parse_pin_list, resolve_backend_settings
from pi5servo.config import ConfigManager

cmd_module = importlib.import_module("pi5servo.cli.cmd")
move_module = importlib.import_module("pi5servo.cli.move")


class FakeServo:
    """Simple fake servo for CLI tests."""

    def __init__(self) -> None:
        self.angles: list[float] = []
        self.closed = False

    def set_angle(self, angle: float) -> None:
        self.angles.append(angle)

    def close(self) -> None:
        self.closed = True


class FakeGroup:
    """Simple fake servo group for CLI tests."""

    def __init__(self, success: bool = True) -> None:
        self.success = success
        self.commands: list[str] = []
        self.closed = False

    def execute_command(self, command: str) -> bool:
        self.commands.append(command)
        return self.success

    def close(self) -> None:
        self.closed = True


def test_resolve_backend_settings_normalizes_config_mappings(tmp_path) -> None:
    """Backend settings should normalize JSON-loaded mapping keys."""
    config_path = tmp_path / "servo.json"
    manager = ConfigManager(config_path)
    manager.set_backend_config(
        "pca9685",
        {
            "address": 64,
            "channel_map": {"12": 0, "13": 1},
        },
    )
    manager.save()
    manager.load()

    backend_name, kwargs = resolve_backend_settings(manager)

    assert backend_name == "pca9685"
    assert kwargs["channel_map"] == {12: 0, 13: 1}


def test_resolve_backend_settings_accepts_dfr0566_bus_override(tmp_path) -> None:
    """DFR0566 backend settings should keep explicit bus and address overrides."""
    config_path = tmp_path / "servo.json"
    manager = ConfigManager(config_path)
    manager.set_backend_config("dfr0566", {"bus_id": 1, "address": "0x10"})
    manager.save()
    manager.load()

    backend_name, kwargs = resolve_backend_settings(
        manager,
        backend_name="dfr0566",
        bus_id=3,
        address="0x12",
    )

    assert backend_name == "dfr0566"
    assert kwargs["bus_id"] == 3
    assert kwargs["address"] == 0x12


def test_parse_pin_list_supports_explicit_endpoints() -> None:
    """Comma-separated endpoint lists should support mixed endpoint types."""
    assert parse_pin_list("12,hat_pwm1,gpio13") == [12, "hat_pwm1", 13]
    assert format_endpoint_label("hat_pwm1") == "hat_pwm1"


def test_move_command_uses_backend_aware_creation(monkeypatch) -> None:
    """`move` should operate through the shared backend-aware helper."""
    runner = CliRunner()
    servo = FakeServo()
    manager = MagicMock()

    def fake_create_servo_from_config(**kwargs):
        del kwargs
        return servo, manager, None, "hardware_pwm", {"chip": 0}

    monkeypatch.setattr(move_module, "create_servo_from_config", fake_create_servo_from_config)
    monkeypatch.setattr(move_module.time, "sleep", lambda _: None)

    result = runner.invoke(move_module.move, ["12", "center", "--config", "servo.json"])

    assert result.exit_code == 0, result.output
    assert servo.angles == [0.0]
    assert servo.closed is True


def test_move_command_supports_hat_endpoint(monkeypatch) -> None:
    """`move` should accept explicit HAT PWM endpoint identifiers."""
    runner = CliRunner()
    servo = FakeServo()
    manager = MagicMock()

    def fake_create_servo_from_config(**kwargs):
        assert kwargs["pin"] == "hat_pwm1"
        return servo, manager, None, "dfr0566", {"address": 0x10}

    monkeypatch.setattr(move_module, "create_servo_from_config", fake_create_servo_from_config)
    monkeypatch.setattr(move_module.time, "sleep", lambda _: None)

    result = runner.invoke(move_module.move, ["hat_pwm1", "center", "--config", "servo.json"])

    assert result.exit_code == 0, result.output
    assert "Moving hat_pwm1 to 0.0°" in result.output
    assert servo.closed is True


def test_cmd_command_executes_and_closes_group(monkeypatch) -> None:
    """`cmd` should execute through ServoGroup and release resources on exit."""
    runner = CliRunner()
    group = FakeGroup(success=True)
    manager = MagicMock()
    manager.get_all_calibrations.return_value = {}

    def fake_create_group_from_config(**kwargs):
        del kwargs
        return group, manager, None, "hardware_pwm", {"chip": 0}

    monkeypatch.setattr(cmd_module, "create_group_from_config", fake_create_group_from_config)

    result = runner.invoke(cmd_module.cmd, ["12:45", "--pins", "12,13"])

    assert result.exit_code == 0, result.output
    assert group.commands == ["12:45"]
    assert group.closed is True


def test_cmd_command_supports_mixed_endpoint_list(monkeypatch) -> None:
    """`cmd` should pass mixed endpoint selections through the shared helper."""
    runner = CliRunner()
    group = FakeGroup(success=True)
    manager = MagicMock()

    def fake_create_group_from_config(**kwargs):
        assert kwargs["pins"] == [12, "hat_pwm1"]
        return group, manager, None, "auto", {}

    monkeypatch.setattr(cmd_module, "create_group_from_config", fake_create_group_from_config)

    result = runner.invoke(
        cmd_module.cmd,
        ["gpio12:45/hat_pwm1:-30", "--pins", "12,hat_pwm1"],
    )

    assert result.exit_code == 0, result.output
    assert group.commands == ["gpio12:45/hat_pwm1:-30"]
    assert group.closed is True
