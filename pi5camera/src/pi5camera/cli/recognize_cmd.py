"""Face-recognition command for pi5camera."""

from __future__ import annotations

from pathlib import Path

import click

from pi5camera.cli._common import load_manager
from pi5camera.errors import CameraError


def _echo_recognition_summary(result: dict) -> None:
    click.echo("Recognition result:")
    click.echo(f"- Photo path: {result['photo_path']}")
    click.echo(f"- Face count: {result['face_count']}")
    if result.get("recognized_names"):
        click.echo(f"- Known faces: {', '.join(result['recognized_names'])}")
    else:
        click.echo("- Known faces: none")

    if result.get("needs_enrollment"):
        click.echo(f"- Unknown faces: {result['unknown_count']}")
        if result.get("recognition_id"):
            click.echo(f"- Recognition id: {result['recognition_id']}")

    for face in result["faces"]:
        label = face["name"] or "unknown"
        click.echo(
            f"  face[{face['index']}] id={face['face_id']} status={face['status']} name={label}"
        )


@click.command("recognize")
@click.option(
    "--image-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Recognize faces from an existing image instead of capturing live.",
)
@click.option(
    "--prompt-for-names",
    is_flag=True,
    help="Prompt to save names for unknown faces after recognition.",
)
@click.pass_context
def recognize_cmd(
    ctx: click.Context,
    image_file: Path | None,
    prompt_for_names: bool,
) -> None:
    """Capture or load an image and run face recognition."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
        from pi5camera.core.recognition import recognize_faces

        result = recognize_faces(manager.config, image_path=image_file)
    except (CameraError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    _echo_recognition_summary(result)

    if not prompt_for_names or not result.get("needs_enrollment"):
        return

    recognition_id = result.get("recognition_id")
    if not recognition_id:
        return

    for face in result["faces"]:
        if face["status"] != "unknown":
            continue
        name = click.prompt(
            f"Enter a name for {face['face_id']} (leave blank to skip)",
            default="",
            show_default=False,
        ).strip()
        if not name:
            continue
        try:
            from pi5camera.core.enrollment import enroll_pending_face

            enrollment = enroll_pending_face(
                manager.config,
                recognition_id=recognition_id,
                face_id=str(face["face_id"]),
                name=name,
            )
        except (CameraError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Saved {enrollment['name']} to {enrollment['saved_image_path']}")
