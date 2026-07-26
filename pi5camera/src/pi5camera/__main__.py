"""CLI entry point for pi5camera."""

from __future__ import annotations

import importlib
from pathlib import Path

import click


class LazyGroup(click.Group):
    """Load CLI subcommands only when they are requested."""

    def __init__(
        self,
        *args,
        lazy_subcommands: dict[str, tuple[str, str]] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.lazy_subcommands = lazy_subcommands or {}

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(self.lazy_subcommands)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        entry = self.lazy_subcommands.get(cmd_name)
        if entry is None:
            return None
        import_path, _ = entry
        module_name, command_name = import_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        command = getattr(module, command_name)
        if not isinstance(command, click.Command):
            raise TypeError(f"Lazy command {import_path} did not resolve to a click.Command")
        return command

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        rows = [
            (command_name, short_help)
            for command_name, (_, short_help) in sorted(self.lazy_subcommands.items())
        ]
        if rows:
            with formatter.section("Commands"):
                formatter.write_dl(rows)


@click.group(
    cls=LazyGroup,
    lazy_subcommands={
        "camera-tool": (
            "pi5camera.cli.camera_tool.camera_tool",
            "Open the interactive camera menu.",
        ),
        "capture": ("pi5camera.cli.capture_cmd.capture_cmd", "Capture one still image."),
        "doctor": ("pi5camera.cli.doctor.doctor", "Check config and backend readiness."),
        "enroll": (
            "pi5camera.cli.enroll_cmd.enroll_cmd",
            "Save a named face from an image or pending record.",
        ),
        "manage-faces": (
            "pi5camera.cli.manage_faces_cmd.manage_faces",
            "List or remove saved identities.",
        ),
        "recognize": (
            "pi5camera.cli.recognize_cmd.recognize_cmd",
            "Capture or load an image and run face recognition.",
        ),
        "setup": ("pi5camera.cli.setup_cmd.setup_cmd", "Run the camera setup wizard."),
        "status": ("pi5camera.cli.status.status", "Show the current config and readiness."),
    },
)
@click.option(
    "--config-file",
    "-C",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to camera config file (default: ./camera.json).",
)
@click.pass_context
def cli(ctx: click.Context, config_file: Path | None) -> None:
    """pi5camera - Standalone-first Raspberry Pi 5 camera tools."""
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config_file


if __name__ == "__main__":
    cli()
