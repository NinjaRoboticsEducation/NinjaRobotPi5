"""Init command — First-time display setup wizard."""

from __future__ import annotations

import click

from pi5disp.config.config_manager import ConfigManager


@click.command()
@click.option("--defaults", is_flag=True, help="Use all default values (no prompts).")
def init(defaults: bool) -> None:
    """Initialize display configuration."""
    config_manager = ConfigManager()
    config_manager.init_config(interactive=not defaults)
