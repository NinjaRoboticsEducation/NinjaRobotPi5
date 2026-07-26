"""CLI smoke tests for pi5vl53l0x."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pi5vl53l0x.cli.sensor_tool import cli


def test_cli_help_shows_commands() -> None:
    """The main help output should expose the migrated commands."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "sensor-tool" in result.output
    assert "performance" in result.output


def test_config_show_works_with_defaults(tmp_path) -> None:
    """Config show should work even when the config file does not exist yet."""
    runner = CliRunner()
    config_path = tmp_path / "missing.json"
    result = runner.invoke(cli, ["-C", str(config_path), "config", "show"])
    assert result.exit_code == 0
    assert "Config file:" in result.output


def test_quick_test_fails_for_invalid_readings() -> None:
    """The quick test must not report success for the 8191 mm sentinel."""
    sensor = MagicMock()
    sensor.offset_mm = 0
    sensor.get_data.return_value = {
        "distance_mm": 8191,
        "is_valid": False,
        "raw_value": 8191,
    }

    with (
        patch("pi5vl53l0x.cli.sensor_tool._create_sensor", return_value=sensor),
        patch("pi5vl53l0x.cli.sensor_tool.time.sleep"),
    ):
        result = CliRunner().invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "Quick test failed" in result.output
    sensor.close.assert_called_once()


def test_status_fails_for_invalid_reading() -> None:
    """Status should distinguish I2C health from valid ranging data."""
    sensor = MagicMock()
    sensor.offset_mm = 0
    sensor.health_check.return_value = True
    sensor.get_data.return_value = {
        "distance_mm": 8191,
        "is_valid": False,
        "raw_value": 8191,
    }

    with patch("pi5vl53l0x.cli.sensor_tool._create_sensor", return_value=sensor):
        result = CliRunner().invoke(cli, ["status"])

    assert result.exit_code == 1
    assert "✗ INVALID 8191 mm" in result.output
    assert "Sensor diagnostics failed" in result.output
    sensor.close.assert_called_once()
