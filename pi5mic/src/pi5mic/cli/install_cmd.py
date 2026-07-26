"""Install and registration helpers for pi5mic."""

from __future__ import annotations

from pathlib import Path

import click

from pi5mic.errors import ConfigError, STTError, WakeWordError
from pi5mic.install.openwakeword import (
    ensure_openwakeword_runtime_assets,
    resolve_openwakeword_inference_framework,
    resolve_openwakeword_model_path,
)
from pi5mic.install.whisper_cpp import (
    DEFAULT_MODEL_FILE,
    find_whisper_cpp_command,
    resolve_model_path,
)

from ._common import load_manager


@click.group("install")
def install_cmd() -> None:
    """Install or register local backend assets."""


@install_cmd.command("whispercpp")
@click.option(
    "--command",
    "command_override",
    type=click.Path(path_type=Path),
    default=None,
    help="Explicit path to whisper-cli.",
)
@click.option(
    "--model-path",
    type=click.Path(path_type=Path),
    default=None,
    help="Explicit path to the multilingual ggml-base.bin model.",
)
@click.option("--save/--no-save", default=True, help="Save discovered paths into mic.json.")
@click.pass_context
def install_whispercpp(
    ctx: click.Context,
    command_override: Path | None,
    model_path: Path | None,
    save: bool,
) -> None:
    """Register an existing whisper.cpp install for pi5mic."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    config = manager.config
    whisper_config = config["stt"]["whisper_cpp"]
    command_candidate = command_override or whisper_config.get("command")
    resolved_command = find_whisper_cpp_command(command_candidate)
    if resolved_command is None:
        raise click.ClickException(
            "Could not find 'whisper-cli'.\n"
            "Suggested next steps:\n"
            "  git clone https://github.com/ggml-org/whisper.cpp.git\n"
            "  cd whisper.cpp\n"
            "  sh ./models/download-ggml-model.sh base\n"
            "  cmake -B build\n"
            "  cmake --build build -j --config Release\n"
        )

    model_candidate = model_path or whisper_config.get("model_path")
    if not model_candidate:
        default_model = Path.home() / ".local" / "share" / "pi5mic" / "models" / DEFAULT_MODEL_FILE
        raise click.ClickException(
            "No whisper.cpp model path is configured.\n"
            f"Suggested model location: {default_model}\n"
            "Download with whisper.cpp's official helper:\n"
            "  sh ./models/download-ggml-model.sh base\n"
        )

    try:
        resolved_model = resolve_model_path(model_candidate)
    except STTError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"whisper.cpp command: {resolved_command}")
    click.echo(f"whisper.cpp model:   {resolved_model}")

    if save:
        whisper_config["command"] = str(resolved_command)
        whisper_config["model_path"] = str(resolved_model)
        config["stt"]["selected"] = "whisper_cpp"
        manager.replace(config)
        manager.save()
        click.echo(f"Saved whisper.cpp settings to {manager.path}")


@install_cmd.command("openwakeword")
@click.option(
    "--model-path",
    type=click.Path(path_type=Path),
    required=True,
    help="Path to the custom openWakeWord model (.tflite or .onnx).",
)
@click.option(
    "--keyword",
    default="ninja",
    show_default=True,
    help="Friendly wake-word label shown in pi5mic status output.",
)
@click.option(
    "--framework",
    type=click.Choice(["auto", "tflite", "onnx"]),
    default="auto",
    show_default=True,
    help="Inference framework to use for the supplied model.",
)
@click.option(
    "--threshold",
    type=float,
    default=0.5,
    show_default=True,
    help="Detection threshold between 0 and 1.",
)
@click.option(
    "--vad-threshold",
    type=float,
    default=0.0,
    show_default=True,
    help="Optional openWakeWord VAD threshold between 0 and 1.",
)
@click.option(
    "--noise-suppression/--no-noise-suppression",
    default=False,
    show_default=True,
    help="Enable openWakeWord Speex noise suppression.",
)
@click.option(
    "--download-assets/--no-download-assets",
    default=True,
    show_default=True,
    help="Download shared openWakeWord runtime assets if they are missing.",
)
@click.option("--save/--no-save", default=True, help="Save discovered paths into mic.json.")
@click.pass_context
def install_openwakeword(
    ctx: click.Context,
    model_path: Path,
    keyword: str,
    framework: str,
    threshold: float,
    vad_threshold: float,
    noise_suppression: bool,
    download_assets: bool,
    save: bool,
) -> None:
    """Register a custom openWakeWord model and optional runtime assets."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    if threshold <= 0 or threshold > 1:
        raise click.ClickException(
            "Wake-word threshold must be greater than 0 and less than or equal to 1."
        )
    if vad_threshold < 0 or vad_threshold > 1:
        raise click.ClickException("Wake-word VAD threshold must be between 0 and 1.")

    try:
        resolved_model = resolve_openwakeword_model_path(model_path)
        resolved_framework = resolve_openwakeword_inference_framework(
            model_path=resolved_model,
            configured_framework=framework,
        )
    except WakeWordError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"openWakeWord model:      {resolved_model}")
    click.echo(f"openWakeWord keyword:    {keyword.strip() or 'ninja'}")
    click.echo(f"openWakeWord framework:  {resolved_framework}")
    click.echo(f"openWakeWord threshold:  {threshold:.2f}")
    click.echo(f"openWakeWord VAD:        {vad_threshold:.2f}")
    click.echo(f"Noise suppression:       {'enabled' if noise_suppression else 'disabled'}")

    downloaded_assets: list[Path] = []
    if download_assets:
        try:
            downloaded_assets = ensure_openwakeword_runtime_assets(
                inference_framework=resolved_framework,
                include_vad=vad_threshold > 0,
            )
        except WakeWordError as exc:
            raise click.ClickException(str(exc)) from exc
        if downloaded_assets:
            click.echo("Downloaded runtime assets:")
            for asset in downloaded_assets:
                click.echo(f"  - {asset}")
        else:
            click.echo("openWakeWord runtime assets are already present.")
    else:
        click.echo("Skipped runtime-asset download. `pi5mic doctor` will verify them later.")

    if save:
        config = manager.config
        wakeword_config = config["wakeword"]
        wakeword_config["backend"] = "openwakeword"
        wakeword_config["keyword"] = keyword.strip() or "ninja"
        wakeword_config["model_path"] = str(resolved_model)
        wakeword_config["threshold"] = float(threshold)
        wakeword_config["vad_threshold"] = float(vad_threshold)
        wakeword_config["enable_noise_suppression"] = bool(noise_suppression)
        wakeword_config["inference_framework"] = resolved_framework
        manager.replace(config)
        manager.save()
        click.echo(f"Saved openWakeWord settings to {manager.path}")
