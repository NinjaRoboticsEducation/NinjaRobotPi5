"""Interactive camera tool for pi5camera."""

from __future__ import annotations

import click


@click.command("camera-tool")
@click.pass_context
def camera_tool(ctx: click.Context) -> None:
    """Open a simple first-run menu for common pi5camera tasks."""
    click.echo("pi5camera camera-tool")
    click.echo("---------------------")

    while True:
        click.echo("\n1. Run setup wizard")
        click.echo("2. Run doctor")
        click.echo("3. Show status")
        click.echo("4. Capture photo")
        click.echo("5. Recognize faces")
        click.echo("6. List known faces")
        click.echo("7. Remove a known face")
        click.echo("8. Exit")

        choice = click.prompt(
            "Choose an action",
            type=click.Choice(["1", "2", "3", "4", "5", "6", "7", "8"]),
            default="1",
            show_choices=False,
        )

        try:
            if choice == "1":
                from pi5camera.cli.setup_cmd import setup_cmd

                ctx.invoke(setup_cmd)
            elif choice == "2":
                from pi5camera.cli.doctor import doctor

                ctx.invoke(doctor)
            elif choice == "3":
                from pi5camera.cli.status import status

                ctx.invoke(status)
            elif choice == "4":
                from pi5camera.cli.capture_cmd import capture_cmd

                ctx.invoke(capture_cmd, output=None, prefix="photo")
            elif choice == "5":
                from pi5camera.cli.recognize_cmd import recognize_cmd

                ctx.invoke(recognize_cmd, image_file=None, prompt_for_names=True)
            elif choice == "6":
                from pi5camera.cli.manage_faces_cmd import list_faces

                ctx.invoke(list_faces)
            elif choice == "7":
                name = click.prompt("Name to remove").strip()
                from pi5camera.cli.manage_faces_cmd import remove_face

                ctx.invoke(remove_face, name=name)
            else:
                click.echo("Leaving pi5camera camera-tool.")
                break
        except click.ClickException as exc:
            click.echo(f"\nERROR: {exc}")
            click.echo("Fix the issue above, then choose the action again from this menu.")
