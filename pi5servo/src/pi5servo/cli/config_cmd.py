"""Config management CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from ..config import BACKEND_CONFIG_KEY, ConfigManager
from ..core import ServoCalibration, parse_servo_endpoint


@click.group("config")
def config_cmd() -> None:
    """Manage servo configuration files."""


@config_cmd.command("show")
@click.option(
    "-c",
    "--config",
    "config_path",
    default="servo.json",
    help="Path to calibration config file.",
)
@click.option(
    "-p",
    "--pin",
    type=int,
    default=None,
    help="Show only this pin's configuration.",
)
@click.option(
    "-e",
    "--endpoint",
    type=str,
    default=None,
    help="Show only this explicit endpoint configuration, for example 'hat_pwm1'.",
)
def show_config(config_path: str, pin: int | None, endpoint: str | None) -> None:
    """Display current servo configuration."""
    if pin is not None and endpoint is not None:
        raise click.BadParameter("Use either --pin or --endpoint, not both.")

    manager = ConfigManager(config_path)
    manager.load()

    click.echo("=== Servo Configuration ===")
    backend_config = manager.get_backend_config()
    click.echo(f"Backend: {backend_config['name']}")
    click.echo(f"Backend kwargs: {backend_config['kwargs'] or '{}'}")

    configs = manager.get_all_endpoint_calibrations()
    if pin is not None or endpoint is not None:
        try:
            endpoint_id = parse_servo_endpoint(endpoint if endpoint is not None else pin).identifier
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc
        if endpoint_id not in configs:
            click.echo(f"\n{endpoint_id}: Not configured")
            return

        cal = configs[endpoint_id]
        click.echo(f"\n{endpoint_id}:")
        click.echo(f"  pulse_min:    {cal.pulse_min}")
        click.echo(f"  pulse_center: {cal.pulse_center}")
        click.echo(f"  pulse_max:    {cal.pulse_max}")
        click.echo(f"  angle_min:    {cal.angle_min}")
        click.echo(f"  angle_center: {cal.angle_center}")
        click.echo(f"  angle_max:    {cal.angle_max}")
        click.echo(f"  speed:        {cal.speed}%")
        return

    if not configs:
        click.echo("\nNo servos configured. Run calibration first.")
        return

    click.echo()
    for endpoint_id, cal in sorted(configs.items()):
        click.echo(
            f"  {endpoint_id}: pulse=[{cal.pulse_min}, {cal.pulse_center}, {cal.pulse_max}] speed={cal.speed}%"
        )


@config_cmd.command("export")
@click.argument("output_path", type=click.Path())
@click.option(
    "-c",
    "--config",
    "config_path",
    default="servo.json",
    help="Source config file.",
)
def export_config(output_path: str, config_path: str) -> None:
    """Export configuration to a file."""
    manager = ConfigManager(config_path)
    manager.load()

    output = Path(output_path)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(manager._to_dict(), handle, indent=2)

    click.echo(f"✓ Exported to {output_path}")


@config_cmd.command("import")
@click.argument("input_path", type=click.Path(exists=True))
@click.option(
    "-c",
    "--config",
    "config_path",
    default="servo.json",
    help="Target config file.",
)
@click.option(
    "--merge/--replace",
    default=True,
    help="Merge with existing or replace entirely.",
)
def import_config(input_path: str, config_path: str, merge: bool) -> None:
    """Import configuration from a file."""
    manager = ConfigManager(config_path)
    if merge:
        manager.load()

    with Path(input_path).open(encoding="utf-8") as handle:
        data = json.load(handle)

    backend_config = data.get(BACKEND_CONFIG_KEY)
    if isinstance(backend_config, dict):
        manager.set_backend_config(
            backend_config.get("name", "auto"),
            backend_config.get("kwargs", {}),
        )

    for pin_str, cal_data in data.items():
        if pin_str == BACKEND_CONFIG_KEY:
            continue
        endpoint = parse_servo_endpoint(pin_str)
        manager.set_calibration(
            endpoint,
            ServoCalibration(
                pulse_min=cal_data.get("pulse_min", 500),
                pulse_max=cal_data.get("pulse_max", 2500),
                pulse_center=cal_data.get("pulse_center", 1500),
                angle_min=cal_data.get("angle_min", -90.0),
                angle_max=cal_data.get("angle_max", 90.0),
                angle_center=cal_data.get("angle_center", 0.0),
                speed=cal_data.get("speed", 80),
            ),
        )

    manager.save()
    click.echo(f"✓ Imported from {input_path}")
    click.echo(f"  Mode: {'merge' if merge else 'replace'}")
