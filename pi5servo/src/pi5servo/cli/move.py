"""CLI single-servo movement command."""

from __future__ import annotations

import time

import click

from ._common import (
    backend_options,
    close_runtime_handle,
    create_servo_from_config,
    format_endpoint_label,
    parse_endpoint_value,
)

# Special position keywords
POSITION_KEYWORDS = {
    "min": -90.0,
    "m": -90.0,
    "center": 0.0,
    "c": 0.0,
    "max": 90.0,
    "x": 90.0,
}


@click.command("move")
@click.argument("pin", type=str)
@click.argument("angle", type=str)
@click.option(
    "-c",
    "--config",
    type=click.Path(),
    default="servo.json",
    help="Path to servo configuration file.",
)
@click.option(
    "-s",
    "--sleep",
    type=float,
    default=1.0,
    help="Time to hold position before releasing the output (seconds).",
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Enable debug output.",
)
@backend_options
def move(
    pin: str,
    angle: str,
    config: str,
    sleep: float,
    debug: bool,
    backend_name: str | None,
    chip: int | None,
    bus_id: int | None,
    frequency_hz: int | None,
    address: str | None,
    pin_channel_map: str | None,
    channel_map: str | None,
) -> None:
    """Move a single servo to an angle or named position."""
    try:
        pin_value = parse_endpoint_value(pin)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="pin") from exc
    angle_lower = angle.lower()
    if angle_lower in POSITION_KEYWORDS:
        angle_val = POSITION_KEYWORDS[angle_lower]
    else:
        try:
            angle_val = float(angle)
        except ValueError as exc:
            raise click.BadParameter(
                f"Invalid angle '{angle}'. Use -90 to 90 or min/center/max."
            ) from exc

    if angle_val < -90.0 or angle_val > 90.0:
        raise click.BadParameter(f"Angle {angle_val} out of range (-90 to 90).")

    servo = None
    runtime = None
    try:
        servo, manager, runtime, resolved_backend, backend_kwargs = create_servo_from_config(
            pin=pin_value,
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
            click.echo(f"Config: {config}")
            click.echo(f"Backend: {resolved_backend}")
            click.echo(f"Backend kwargs: {backend_kwargs}")
            click.echo(f"Calibration: {manager.get_calibration(pin_value)}")

        click.echo(f"Moving {format_endpoint_label(pin_value)} to {angle_val}°")
        servo.set_angle(angle_val)
        time.sleep(sleep)
        click.echo("✓ Done")
    finally:
        if servo is not None:
            servo.close()
        close_runtime_handle(runtime)
