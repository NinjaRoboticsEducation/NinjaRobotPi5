"""Config management CLI for pi5mic."""

from __future__ import annotations

import json
from pathlib import Path

import click

from pi5mic.errors import ConfigError

from ._common import load_manager


@click.group("config")
def config_cmd() -> None:
    """Manage `mic.json` configuration files."""


@config_cmd.command("show")
@click.pass_context
def show_config(ctx: click.Context) -> None:
    """Show the current effective config."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(json.dumps(manager.config, indent=2))
    click.echo(f"\nConfig file: {manager.path}")


@config_cmd.command("export")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_context
def export_config(ctx: click.Context, path: Path) -> None:
    """Export the current config to another file."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
        exported = manager.export_config(path)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Exported config to {exported}")


@config_cmd.command("import")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def import_config(ctx: click.Context, path: Path) -> None:
    """Import a config file into the active config path."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
        manager.import_config(path)
        manager.save()
    except (ConfigError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Imported config from {path}")
    click.echo(f"Saved active config to {manager.path}")
