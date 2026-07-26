"""Command-line interface for standalone pi5buzzer control."""

from __future__ import annotations

import json
import time

import click

from pi5buzzer.config.config_manager import BuzzerConfigManager
from pi5buzzer.core.driver import create_default_backend
from pi5buzzer.notes import get_emotion_names


def _connect_backend():
    """Create a Pi 5 compatible GPIO backend instance."""
    try:
        return create_default_backend()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


def _create_buzzer(pi, config_path=None):
    """Create and initialize a MusicBuzzer from config."""
    from pi5buzzer.core.music import MusicBuzzer

    config_manager = BuzzerConfigManager(config_path)
    config_manager.load()
    pin = config_manager.get_pin()
    volume = config_manager.get_volume()

    buzzer = MusicBuzzer(pin=pin, pi=pi, volume=volume)
    buzzer.initialize()
    return buzzer


@click.group(
    invoke_without_command=True,
    help="pi5buzzer - Passive buzzer driver for Raspberry Pi 5.",
)
@click.pass_context
@click.option(
    "--config-file",
    "-C",
    type=str,
    default=None,
    help="Path to config file (default: buzzer.json).",
)
def cli(ctx, config_file):
    """pi5buzzer CLI tool."""
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config_file

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("pin", type=int)
@click.pass_context
def init(ctx, pin):
    """Initialize buzzer config with the given GPIO pin."""
    config_manager = BuzzerConfigManager(ctx.obj.get("config_file"))

    try:
        config_manager.init_config(pin)
        click.echo(f"OK: Buzzer config saved to {config_manager.path}")
        click.echo(f"  Pin: GPIO {pin}")
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        pi = _connect_backend()
        from pi5buzzer.core.driver import Buzzer

        buzzer = Buzzer(pin=pin, pi=pi)
        buzzer.initialize()
        click.echo("  Playing test beep...")
        buzzer.play_sound(440, 0.3)
        time.sleep(0.5)
        buzzer.off()
        pi.stop()
        click.echo("OK: Test beep successful")
    except click.ClickException:
        click.echo("WARNING: Could not test beep (GPIO backend unavailable).")
    except Exception as exc:
        click.echo(f"WARNING: Test beep failed: {exc}")


@cli.command()
@click.argument("frequency", type=int, default=440)
@click.argument("duration", type=float, default=0.5)
@click.pass_context
def beep(ctx, frequency, duration):
    """Play a single tone."""
    pi = _connect_backend()
    try:
        buzzer = _create_buzzer(pi, ctx.obj.get("config_file"))
        click.echo(f"Playing {frequency} Hz for {duration}s...")
        buzzer.play_sound(frequency, duration)
        time.sleep(duration + 0.1)
        buzzer.off()
    finally:
        pi.stop()


@cli.command()
@click.argument("emotion", type=str)
@click.pass_context
def play(ctx, emotion):
    """Play a predefined emotion sound."""
    emotions = get_emotion_names()
    if emotion not in emotions:
        raise click.ClickException(
            f"Unknown emotion: '{emotion}'. Available: {', '.join(emotions)}"
        )

    pi = _connect_backend()
    try:
        buzzer = _create_buzzer(pi, ctx.obj.get("config_file"))
        click.echo(f"Playing emotion: {emotion}")
        buzzer.play_emotion(emotion)
        time.sleep(2.0)
        buzzer.off()
    finally:
        pi.stop()


@cli.command()
@click.option("--health-check", is_flag=True, help="Verify hardware connectivity.")
@click.pass_context
def info(ctx, health_check):
    """Show buzzer configuration and status."""
    config_manager = BuzzerConfigManager(ctx.obj.get("config_file"))
    config = config_manager.load()

    click.echo("pi5buzzer Status Report")
    click.echo(f"  Config file: {config_manager.path}")
    click.echo(f"  Pin:         GPIO {config.get('pin', 'N/A')}")
    click.echo(f"  Volume:      {config.get('volume', 'N/A')}/255")

    if not health_check:
        return

    click.echo("\nHealth Check:")
    try:
        pi = _connect_backend()
        click.echo("  OK: GPIO backend connection")

        from pi5buzzer.core.driver import Buzzer

        buzzer = Buzzer(pin=config["pin"], pi=pi)
        buzzer.initialize()
        click.echo(f"  OK: GPIO {config['pin']} mode set")
        buzzer.play_sound(440, 0.2)
        time.sleep(0.4)
        buzzer.off()
        pi.stop()
        click.echo("  OK: Test beep")
        click.echo("\n  Result: All checks passed")
    except click.ClickException as exc:
        click.echo(f"  ERROR: {exc.message}")
    except Exception as exc:
        click.echo(f"  ERROR: Health check failed: {exc}")


@cli.group()
def config():
    """Configuration management (show/export/import)."""


@config.command("show")
@click.pass_context
def config_show(ctx):
    """Show current buzzer configuration."""
    config_manager = BuzzerConfigManager(ctx.obj.get("config_file"))
    config = config_manager.load()
    click.echo(json.dumps(config, indent=2))
    click.echo(f"\nConfig file: {config_manager.path}")


@config.command("export")
@click.argument("path")
@click.pass_context
def config_export(ctx, path):
    """Export configuration to a file."""
    config_manager = BuzzerConfigManager(ctx.obj.get("config_file"))
    config_manager.load()
    config_manager.export_config(path)
    click.echo(f"OK: Config exported to {path}")


@config.command("import")
@click.argument("path")
@click.pass_context
def config_import(ctx, path):
    """Import configuration from a file."""
    config_manager = BuzzerConfigManager(ctx.obj.get("config_file"))
    try:
        config_manager.import_config(path)
        config_manager.save()
        click.echo(f"OK: Config imported from {path}")
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("buzzer-tool")
@click.pass_context
def buzzer_tool_cmd(ctx):
    """Launch the interactive buzzer tool."""
    from pi5buzzer.cli.buzzer_tool import buzzer_tool

    buzzer_tool(ctx.obj.get("config_file"))


if __name__ == "__main__":
    cli()
