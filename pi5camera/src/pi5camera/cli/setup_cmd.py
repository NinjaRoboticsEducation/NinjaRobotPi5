"""Guided setup wizard for pi5camera."""

from __future__ import annotations

from pathlib import Path

import click

from pi5camera.cli._common import load_manager
from pi5camera.errors import ConfigError


def _resolve_dir(raw_value: str) -> str:
    return str(Path(raw_value).expanduser().resolve())


@click.command("setup")
@click.pass_context
def setup_cmd(ctx: click.Context) -> None:
    """Run the guided first-run setup wizard."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    config = manager.config
    camera_config = config["camera"]
    recognition_config = config["recognition"]
    paths = config["paths"]

    click.echo("pi5camera setup wizard")
    click.echo("--------------------")
    click.echo(f"Active project root: {manager.active_root}")

    proposed_photo_dir = str(paths.get("photo_dir") or manager.default_photo_dir)
    photo_dir = click.prompt(
        "\nPhoto directory (absolute path)",
        default=proposed_photo_dir,
    ).strip()
    paths["photo_dir"] = _resolve_dir(photo_dir)

    proposed_data_dir = str(paths.get("data_dir") or manager.default_data_dir)
    data_dir = click.prompt(
        "Camera data directory (absolute path)",
        default=proposed_data_dir,
    ).strip()
    paths["data_dir"] = _resolve_dir(data_dir)

    camera_config["width"] = click.prompt(
        "Image width",
        type=int,
        default=int(camera_config.get("width", 1280)),
    )
    camera_config["height"] = click.prompt(
        "Image height",
        type=int,
        default=int(camera_config.get("height", 720)),
    )
    camera_config["warmup_seconds"] = click.prompt(
        "Camera warm-up time (seconds)",
        type=float,
        default=float(camera_config.get("warmup_seconds", 1.0)),
    )
    camera_config["use_preview"] = click.confirm(
        "Use camera preview when supported?",
        default=bool(camera_config.get("use_preview", False)),
    )
    camera_config["autofocus_mode"] = click.prompt(
        "Autofocus mode",
        type=click.Choice(["continuous", "auto", "manual", "none"]),
        default=str(camera_config.get("autofocus_mode", "continuous")),
        show_choices=True,
    )
    recognition_config["tolerance"] = click.prompt(
        "Recognition tolerance (lower is stricter)",
        type=float,
        default=float(recognition_config.get("tolerance", 0.6)),
    )
    recognition_config["save_unknown_crops"] = click.confirm(
        "Save crops for unknown faces in pending results?",
        default=bool(recognition_config.get("save_unknown_crops", True)),
    )
    recognition_config["pending_ttl_seconds"] = click.prompt(
        "Pending-recognition expiry (seconds)",
        type=int,
        default=int(recognition_config.get("pending_ttl_seconds", 86_400)),
    )

    try:
        manager.replace(config)
        manager.save()
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"\nSaved config to {manager.path}")
    click.echo(f"Photo directory: {paths['photo_dir']}")
    click.echo(f"Camera data directory: {paths['data_dir']}")
