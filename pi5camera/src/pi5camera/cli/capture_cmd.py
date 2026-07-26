"""One-shot photo capture command for pi5camera."""

from __future__ import annotations

from pathlib import Path

import click

from pi5camera.cli._common import load_manager
from pi5camera.core.capture import capture_photo
from pi5camera.errors import CameraError


@click.command("capture")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Optional output path. Defaults to the configured photo directory.",
)
@click.option("--prefix", default="photo", show_default=True, help="Photo filename prefix.")
@click.pass_context
def capture_cmd(ctx: click.Context, output: Path | None, prefix: str) -> None:
    """Capture one still image."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
        result = capture_photo(manager.config, output_path=output, filename_prefix=prefix)
    except (CameraError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Saved photo to {result.path}")
    if result.metadata:
        click.echo(f"Metadata keys: {', '.join(sorted(str(k) for k in result.metadata))}")
