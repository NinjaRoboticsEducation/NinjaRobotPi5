"""Enrollment command for pi5camera."""

from __future__ import annotations

from pathlib import Path

import click

from pi5camera.cli._common import load_manager
from pi5camera.errors import CameraError


@click.command("enroll")
@click.option("--name", required=True, help="Name to assign to the enrolled face.")
@click.option(
    "--image-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Enroll from an existing image file.",
)
@click.option("--recognition-id", default=None, help="Pending recognition id to enroll from.")
@click.option("--face-id", default=None, help="Pending face id to enroll from.")
@click.pass_context
def enroll_cmd(
    ctx: click.Context,
    name: str,
    image_file: Path | None,
    recognition_id: str | None,
    face_id: str | None,
) -> None:
    """Enroll a known face from an image or a pending recognition result."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
        if recognition_id and face_id:
            from pi5camera.core.enrollment import enroll_pending_face

            result = enroll_pending_face(
                manager.config,
                recognition_id=recognition_id,
                face_id=face_id,
                name=name,
            )
        elif image_file is not None:
            from pi5camera.core.enrollment import enroll_face_from_image

            result = enroll_face_from_image(manager.config, name=name, image_path=image_file)
        else:
            raise click.ClickException(
                "Provide either --image-file or both --recognition-id and --face-id."
            )
    except (CameraError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Saved {result['name']} to {result['saved_image_path']}")
