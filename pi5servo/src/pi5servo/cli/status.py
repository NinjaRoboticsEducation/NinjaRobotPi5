"""CLI status command for servo system configuration and backend readiness."""

from __future__ import annotations

import click

from ..core import parse_servo_endpoint
from ._common import (
    LEGACY_BACKENDS,
    backend_options,
    close_runtime_handle,
    create_group_from_config,
    format_endpoint_label,
    parse_pin_list,
)


@click.command("status")
@click.option(
    "-c",
    "--config",
    type=click.Path(),
    default="servo.json",
    help="Path to configuration file.",
)
@click.option(
    "-p",
    "--pins",
    default="12,13",
    help="Comma-separated list of servo endpoints.",
)
@click.option(
    "--probe/--no-probe",
    default=True,
    help="Try to initialize the configured backend for the listed pins.",
)
@backend_options
def status(
    config: str,
    pins: str,
    probe: bool,
    backend_name: str | None,
    chip: int | None,
    bus_id: int | None,
    frequency_hz: int | None,
    address: str | None,
    pin_channel_map: str | None,
    channel_map: str | None,
) -> None:
    """Show servo system status."""
    from ..config import ConfigManager

    pin_list = parse_pin_list(pins)
    manager = ConfigManager(config)
    loaded = manager.load()
    resolved_backend, backend_kwargs = (
        manager.get_backend_config()["name"],
        manager.get_backend_config()["kwargs"],
    )

    if (
        backend_name is not None
        or chip is not None
        or bus_id is not None
        or frequency_hz is not None
        or address is not None
        or pin_channel_map is not None
        or channel_map is not None
    ):
        from ._common import resolve_backend_settings

        resolved_backend, backend_kwargs = resolve_backend_settings(
            manager,
            backend_name=backend_name,
            chip=chip,
            bus_id=bus_id,
            frequency_hz=frequency_hz,
            address=address,
            pin_channel_map=pin_channel_map,
            channel_map=channel_map,
        )

    click.echo("=== pi5servo Status ===\n")
    click.echo(f"Configured backend: {resolved_backend}")
    click.echo(f"Backend kwargs: {backend_kwargs or '{}'}")
    click.echo(f"Config file: {config}")
    click.echo(f"Config exists: {'yes' if manager.exists() else 'no (using defaults)'}")

    click.echo("\nConfigured endpoints:")
    for pin in pin_list:
        cal = manager.get_calibration(pin)
        has_custom = loaded and parse_servo_endpoint(pin).identifier in manager._data
        marker = "✓" if has_custom else "○"
        click.echo(
            f"  {marker} {format_endpoint_label(pin)}: "
            f"pulse=[{cal.pulse_min}, {cal.pulse_center}, {cal.pulse_max}] speed={cal.speed}%"
        )

    if not probe:
        return

    click.echo("\nBackend probe:")
    group = None
    runtime = None
    try:
        group, _, runtime, probe_backend, _ = create_group_from_config(
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
        click.echo(f"  ✓ Ready ({probe_backend})")
        if probe_backend in LEGACY_BACKENDS:
            click.echo("  Legacy pigpio runtime connected")
        else:
            click.echo("  Standalone backend initialized")
    except Exception as exc:
        click.echo(f"  ✗ Failed: {exc}")
    finally:
        if group is not None:
            group.close()
        close_runtime_handle(runtime)
