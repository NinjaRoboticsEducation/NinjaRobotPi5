"""CLI entry point for pi5mic."""

from __future__ import annotations

from pathlib import Path

import click

from pi5mic.cli import (
    config_cmd,
    doctor,
    install_cmd,
    mic_tool,
    run_cmd,
    setup_cmd,
    status,
    voiceinput_tool,
)
from pi5mic.cli._common import build_stt_backend, load_manager
from pi5mic.core.devices import get_default_input_device, list_input_devices
from pi5mic.core.recorder import RecorderSettings, record_wav
from pi5mic.errors import ConfigError, DeviceError, RecordingError, STTError


@click.group()
@click.option(
    "--config-file",
    "-C",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to mic config file (default: ./mic.json).",
)
@click.pass_context
def cli(ctx: click.Context, config_file: Path | None) -> None:
    """pi5mic - Standalone-first microphone capture tools."""
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config_file


@cli.command("devices")
def devices_cmd() -> None:
    """List available audio input devices."""
    try:
        devices = list_input_devices()
        default_device = get_default_input_device()
    except DeviceError as exc:
        raise click.ClickException(str(exc)) from exc

    if not devices:
        click.echo("No input devices found.")
        return

    click.echo("Available input devices:")
    for device in devices:
        default_marker = " (default)" if device.index == default_device else ""
        samplerate = (
            f"{device.default_samplerate:.0f} Hz"
            if device.default_samplerate is not None
            else "unknown"
        )
        click.echo(
            f"  [{device.index}] {device.name} | channels={device.max_input_channels} | "
            f"default_samplerate={samplerate}{default_marker}"
        )


@cli.command("record")
@click.option("--duration", type=float, default=None, help="Recording length in seconds.")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("mic-test.wav"),
    show_default=True,
    help="Output WAV file path.",
)
@click.option("--device", type=str, default=None, help="Input device index or name.")
@click.option("--sample-rate", type=int, default=None, help="Sample rate in Hz.")
@click.option("--channels", type=int, default=None, help="Input channel count.")
@click.option("--block-size", type=int, default=None, help="Frames read per audio chunk.")
@click.pass_context
def record_cmd(
    ctx: click.Context,
    duration: float | None,
    output: Path,
    device: str | None,
    sample_rate: int | None,
    channels: int | None,
    block_size: int | None,
) -> None:
    """Record a bounded WAV clip."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    audio_config = manager.config["audio"]
    settings = RecorderSettings(
        device=device if device is not None else audio_config.get("input_device"),
        sample_rate=sample_rate if sample_rate is not None else int(audio_config["sample_rate"]),
        channels=channels if channels is not None else int(audio_config["channels"]),
        sample_width_bytes=int(audio_config["sample_width_bytes"]),
        block_size=block_size if block_size is not None else int(audio_config["block_size"]),
        duration_seconds=(
            duration if duration is not None else min(float(audio_config["max_clip_seconds"]), 5.0)
        ),
    )

    try:
        clip = record_wav(output, settings)
    except (RecordingError, DeviceError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Recorded WAV to {clip.path}")
    click.echo(f"  Duration:  {clip.duration_seconds:.2f}s")
    click.echo(f"  SampleRate:{clip.sample_rate} Hz")
    click.echo(f"  Channels:  {clip.channels}")
    click.echo(f"  Frames:    {clip.frames}")
    click.echo(f"  Bytes:     {clip.bytes_written}")
    click.echo(f"  Overflow:  {'yes' if clip.overflowed else 'no'}")


@cli.command("transcribe")
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--backend",
    type=click.Choice(["whisper_cpp", "gemini"]),
    default=None,
    help="Override the configured STT backend.",
)
@click.pass_context
def transcribe_cmd(ctx: click.Context, audio_file: Path, backend: str | None) -> None:
    """Transcribe an existing audio file through the configured STT backend."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
        stt_backend = build_stt_backend(manager.config, backend_name=backend)
        result = stt_backend.transcribe(audio_file)
    except (ConfigError, STTError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(result.text)
    click.echo(f"\nBackend: {result.backend}")
    click.echo(f"Model:   {result.model}")
    if result.language:
        click.echo(f"Language:{result.language}")


cli.add_command(config_cmd)
cli.add_command(doctor)
cli.add_command(install_cmd)
cli.add_command(mic_tool)
cli.add_command(run_cmd)
cli.add_command(setup_cmd)
cli.add_command(status)
cli.add_command(voiceinput_tool)


if __name__ == "__main__":
    cli()
