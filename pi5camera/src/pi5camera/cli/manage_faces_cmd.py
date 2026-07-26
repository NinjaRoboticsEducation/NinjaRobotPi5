"""Manage known faces for pi5camera."""

from __future__ import annotations

import click

from pi5camera.cli._common import load_manager
from pi5camera.errors import ConfigError, StorageError
from pi5camera.storage.face_index import FaceIndex


@click.group("manage-faces")
@click.pass_context
def manage_faces(ctx: click.Context) -> None:
    """List or remove known faces."""
    ctx.ensure_object(dict)


@manage_faces.command("list")
@click.pass_context
def list_faces(ctx: click.Context) -> None:
    """List known enrolled identities."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
        index = FaceIndex(manager.config)
        names = index.list_known_faces()
    except (ConfigError, StorageError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not names:
        click.echo("No known faces saved yet.")
        return

    click.echo("Known faces:")
    for name in names:
        click.echo(f"- {name}")


@manage_faces.command("remove")
@click.argument("name")
@click.pass_context
def remove_face(ctx: click.Context, name: str) -> None:
    """Remove a known enrolled identity."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
        index = FaceIndex(manager.config)
        removed = index.remove_known_face(name)
    except (ConfigError, StorageError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not removed:
        raise click.ClickException(f"Unknown saved face '{name}'.")

    click.echo(f"Removed saved face '{name}'.")
