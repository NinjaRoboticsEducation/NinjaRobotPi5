"""CLI command execution for servo command strings."""

from __future__ import annotations

import sys

import click

from ._common import (
    backend_options,
    close_runtime_handle,
    create_group_from_config,
    format_endpoint_label,
    parse_pin_list,
)


@click.command("cmd")
@click.argument("command")
@click.option(
    "-p",
    "--pins",
    default="12,13",
    help="Comma-separated list of servo endpoints to control.",
)
@click.option(
    "-c",
    "--config",
    type=click.Path(),
    default="servo.json",
    help="Path to servo configuration file.",
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Enable debug output.",
)
@backend_options
def cmd(
    command: str,
    pins: str,
    config: str,
    debug: bool,
    backend_name: str | None,
    chip: int | None,
    bus_id: int | None,
    frequency_hz: int | None,
    address: str | None,
    pin_channel_map: str | None,
    channel_map: str | None,
) -> None:
    """Execute a servo command string.

    COMMAND: Servo command in format ``[SPEED_]PIN:ANGLE[/PIN:ANGLE...]``
    """
    pin_list = parse_pin_list(pins)

    group = None
    runtime = None
    try:
        group, manager, runtime, resolved_backend, backend_kwargs = create_group_from_config(
            pins=pin_list,
            config_path=config,
            backend_name=backend_name,
            chip=chip,
            bus_id=bus_id,
            frequency_hz=frequency_hz,
            address=address,
            pin_channel_map=pin_channel_map,
            channel_map=channel_map,
        )

        if debug:
            click.echo(f"Pins: {[format_endpoint_label(pin) for pin in pin_list]}")
            click.echo(f"Config: {config}")
            click.echo(f"Backend: {resolved_backend}")
            click.echo(f"Backend kwargs: {backend_kwargs}")
            click.echo(
                "Calibrations: "
                f"{ {format_endpoint_label(pin): manager.get_calibration(pin) for pin in pin_list} }"
            )

        click.echo(f"Executing: {command}")
        success = group.execute_command(command)

        if success:
            click.echo("✓ Command completed")
            return

        click.echo("✗ Command aborted or failed", err=True)
        sys.exit(1)
    finally:
        if group is not None:
            group.close()
        close_runtime_handle(runtime)
