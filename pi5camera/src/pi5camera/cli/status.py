"""Status command for pi5camera."""

from __future__ import annotations

import click

from pi5camera.cli._common import describe_camera_stack, load_manager
from pi5camera.errors import ConfigError


@click.command("status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show the current config and local readiness summary."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
        summary = describe_camera_stack(manager.config)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("pi5camera status")
    click.echo("----------------")
    click.echo(f"Config path: {manager.path}")
    click.echo(f"Active root: {manager.active_root}")
    click.echo(f"Python:      {summary['python_executable']}")
    click.echo(f"Photo dir:   {summary['photo_dir']}")
    click.echo(f"Data dir:    {summary['data_dir']}")
    click.echo(f"Resolution:  {summary['resolution']['width']}x{summary['resolution']['height']}")
    click.echo(f"Warm-up:     {summary['warmup_seconds']:.1f}s")
    click.echo(f"Camera:      {summary['camera_backend']} ({summary['camera_backend_state']})")
    click.echo(
        f"Recognition: {summary['recognition_backend']} ({summary['recognition_backend_state']})"
    )
    click.echo(f"Detection:   {summary['detection_mode']}")
    if summary["camera_backend_help_text"] is not None:
        click.echo(f"Camera fix:  {summary['camera_backend_help_text']}")
    if summary["recognition_backend_help_text"] is not None:
        click.echo(f"Recogn fix:  {summary['recognition_backend_help_text']}")
