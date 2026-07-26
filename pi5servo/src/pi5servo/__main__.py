"""pi5servo CLI entry point.

Usage:
    python -m pi5servo [OPTIONS] COMMAND [ARGS]...

Commands:
    cmd         Execute a servo command string
    move        Move a single servo to an angle
    calib       View or set servo calibration
    status      Show servo system status
    servo-tool  Interactive servo control tool
    config      Manage configuration files
"""

import click

from . import __version__
from .cli import calib, cmd, config_cmd, move, servo_tool, status


@click.group()
@click.version_option(__version__, prog_name="pi5servo")
def cli():
    """pi5servo - Servo control library for Raspberry Pi 5."""
    pass


# Register commands
# Register commands
cli.add_command(cmd)
cli.add_command(move)
cli.add_command(calib)
cli.add_command(status)
cli.add_command(servo_tool)
cli.add_command(config_cmd)


if __name__ == "__main__":
    cli()
