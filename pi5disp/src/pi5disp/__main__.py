"""pi5disp CLI — Command-line interface for ST7789V display control."""

from __future__ import annotations

import click

from .cli.display_tool import display_tool
from .cli.demo_cmd import demo
from .cli.image_cmd import image
from .cli.info_cmd import info
from .cli.init_cmd import init
from .cli.text_cmd import text
from .cli._common import create_display
from .config.config_manager import ConfigManager


@click.group()
def cli() -> None:
    """pi5disp — ST7789V Display Driver CLI."""


cli.add_command(init)
cli.add_command(display_tool, name="display-tool")
cli.add_command(image)
cli.add_command(text)
cli.add_command(demo)
cli.add_command(info)


@cli.command()
def clear() -> None:
    """Clear the display (fill with black)."""
    try:
        lcd = create_display()
        lcd.clear()
        click.echo("Display cleared.")
        lcd.close()
    except Exception as exc:
        click.echo(f"Error: {exc}")


@cli.command()
@click.argument("percent", type=int)
def brightness(percent: int) -> None:
    """Set display brightness (0-100%)."""
    try:
        clamped = max(0, min(100, percent))
        config_manager = ConfigManager()
        config_manager.load()
        config_manager.set("brightness", clamped)
        lcd = create_display()
        click.echo(f"Brightness set to {clamped}%")
        lcd.close()
    except Exception as exc:
        click.echo(f"Error: {exc}")


@cli.group()
def config() -> None:
    """Manage display configuration."""


@config.command()
def show() -> None:
    """Show current configuration."""
    config_manager = ConfigManager()
    cfg = config_manager.load()
    click.echo(click.style("\n📋 Display Configuration:", bold=True))
    for key, value in cfg.items():
        click.echo(f"  {key}: {value}")
    click.echo()


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration value."""
    config_manager = ConfigManager()
    config_manager.load()
    try:
        parsed_value = int(value)
    except ValueError:
        parsed_value = value
    config_manager.set(key, parsed_value)
    click.echo(f"Set {key} = {parsed_value}")


@config.command("export")
@click.argument("path")
def config_export(path: str) -> None:
    """Export configuration to a file."""
    config_manager = ConfigManager()
    config_manager.load()
    config_manager.export_config(path)
    click.echo(f"Configuration exported to {path}")


@config.command("import")
@click.argument("path")
def config_import(path: str) -> None:
    """Import configuration from a file."""
    config_manager = ConfigManager()
    config_manager.import_config(path)
    click.echo(f"Configuration imported from {path}")


if __name__ == "__main__":
    cli()
