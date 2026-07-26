"""Interactive run flow for pi5mic."""

from __future__ import annotations

from pathlib import Path

import click

from pi5mic.core.listener import MicListener
from pi5mic.core.recorder import record_temp_wav
from pi5mic.errors import (
    ConfigError,
    DeviceError,
    IntegrationError,
    ListenerBusyError,
    RecordingError,
    STTError,
    TransportError,
)
from pi5mic.integration.delivery import describe_delivery_mode
from pi5mic.integration.openclaw_setup import explain_openclaw_error
from pi5mic.models import DispatchResult, RecorderSettings, TranscriptionResult

from ._common import (
    build_openclaw_transport,
    build_presence_controller,
    build_stt_backend,
    load_manager,
)


def _build_recorder_settings(config: dict, duration_override: float | None) -> RecorderSettings:
    audio_config = config["audio"]
    duration = (
        duration_override
        if duration_override is not None
        else float(audio_config.get("max_clip_seconds", 30.0))
    )
    return RecorderSettings(
        device=audio_config.get("input_device"),
        sample_rate=int(audio_config["sample_rate"]),
        channels=int(audio_config["channels"]),
        sample_width_bytes=int(audio_config["sample_width_bytes"]),
        block_size=int(audio_config["block_size"]),
        duration_seconds=duration,
    )


def _best_effort_presence(controller, mode: str, *, reason: str) -> None:
    try:
        controller.set_mode(mode, reason=reason)
    except (IntegrationError, TransportError) as exc:
        click.echo(f"WARNING: Presence update '{mode}' failed: {explain_openclaw_error(str(exc))}")


def _format_cycle_error(config: dict, exc: Exception) -> str:
    """Return a user-facing run error with OpenClaw guidance when relevant."""
    message = str(exc)
    if str(config.get("profile", "standalone")) == "openclaw":
        return explain_openclaw_error(message)
    return message


def _echo_cycle_result(
    *,
    transcription: TranscriptionResult,
    dispatch_result: DispatchResult | None,
    audio_path: Path,
    kept_audio: bool,
) -> None:
    click.echo("\nTranscript:")
    click.echo(transcription.text)
    click.echo(f"\nSTT backend: {transcription.backend} ({transcription.model})")
    if transcription.language:
        click.echo(f"Language:    {transcription.language}")

    if dispatch_result is not None:
        click.echo("\nOpenClaw reply:")
        click.echo(dispatch_result.reply_text or "(reply completed, but no text was extracted)")

    if kept_audio:
        click.echo(f"\nSaved audio: {audio_path}")


def _run_cycle(
    *,
    config: dict,
    audio_file: Path | None,
    duration_override: float | None,
    keep_audio: bool,
):
    listener = MicListener(cooldown_seconds=1.0)
    stt_backend = build_stt_backend(config)
    profile = str(config.get("profile", "standalone"))

    presence_controller = None
    transport = None
    if profile == "openclaw":
        integration_config = config.get("integration", {})
        if bool(integration_config.get("presence_enabled", True)):
            presence_controller = build_presence_controller(config)
        transport = build_openclaw_transport(config)

    request_id: str | None = None
    clip_path: Path | None = None
    created_temp_audio = False

    try:
        listener.arm()
        snapshot = listener.start_listening()
        request_id = snapshot.active_request_id
        if request_id is None:  # pragma: no cover - defensive
            raise ListenerBusyError("Listener did not produce a request id.")

        if presence_controller is not None:
            _best_effort_presence(presence_controller, "listening", reason="pi5mic.listening")

        if audio_file is not None:
            clip_path = audio_file.expanduser().resolve()
        else:
            click.echo("\nRecording...")
            clip = record_temp_wav(_build_recorder_settings(config, duration_override))
            click.echo(f"Recorded {clip.duration_seconds:.2f}s of audio.")
            clip_path = clip.path
            created_temp_audio = True

        listener.mark_transcribing(request_id)
        transcription = stt_backend.transcribe(clip_path)

        dispatch_result = None
        if transport is not None:
            if presence_controller is not None:
                _best_effort_presence(presence_controller, "thinking", reason="pi5mic.dispatch")
            listener.mark_dispatching(request_id)
            listener.mark_waiting_for_reply(request_id)
            dispatch_result = transport.dispatch(transcription.text)

        listener.complete(request_id)
        return transcription, dispatch_result, clip_path, created_temp_audio
    except (
        ConfigError,
        DeviceError,
        IntegrationError,
        ListenerBusyError,
        RecordingError,
        STTError,
        TransportError,
        ValueError,
    ):
        if request_id is not None:
            try:
                listener.fail(request_id, "cycle failed")
            except ListenerBusyError:
                listener.reset()
        raise
    finally:
        if presence_controller is not None:
            _best_effort_presence(presence_controller, "idle", reason="pi5mic.idle")
        if created_temp_audio and clip_path is not None and not keep_audio:
            clip_path.unlink(missing_ok=True)


@click.command("run")
@click.option("--once", is_flag=True, help="Run a single capture/transcribe cycle and exit.")
@click.option(
    "--audio-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Use an existing audio file instead of recording live audio.",
)
@click.option(
    "--duration",
    type=float,
    default=None,
    help="Override the configured max clip length for this run.",
)
@click.option(
    "--keep-audio",
    is_flag=True,
    help="Keep temporary recorded WAV clips instead of deleting them after the cycle.",
)
@click.pass_context
def run_cmd(
    ctx: click.Context,
    once: bool,
    audio_file: Path | None,
    duration: float | None,
    keep_audio: bool,
) -> None:
    """Run the configured standalone/OpenClaw microphone workflow."""
    if audio_file is not None:
        once = True

    try:
        manager = load_manager(ctx.obj.get("config_file"))
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    config = manager.config
    click.echo(f"Profile: {config['profile']}")
    click.echo(f"STT:     {config['stt']['selected']}")
    if str(config.get("profile")) == "openclaw":
        openclaw_config = config["integration"]["openclaw"]
        delivery_mode = describe_delivery_mode(
            str(config["integration"].get("delivery_mode", "local_only")),
            reply_channel=openclaw_config.get("reply_channel"),
            reply_to=openclaw_config.get("reply_to"),
            reply_account=openclaw_config.get("reply_account"),
        )
        click.echo(f"Delivery: {delivery_mode}")

    while True:
        if not once:
            choice = click.prompt(
                "\nPress Enter to record, or type 'q' to quit",
                default="",
                show_default=False,
            ).strip()
            if choice.lower() == "q":
                break

        try:
            transcription, dispatch_result, clip_path, created_temp_audio = _run_cycle(
                config=config,
                audio_file=audio_file,
                duration_override=duration,
                keep_audio=keep_audio,
            )
        except (
            ConfigError,
            DeviceError,
            IntegrationError,
            ListenerBusyError,
            RecordingError,
            STTError,
            TransportError,
            ValueError,
        ) as exc:
            message = _format_cycle_error(config, exc)
            if once:
                raise click.ClickException(message) from exc
            click.echo(f"ERROR: {message}")
            continue

        _echo_cycle_result(
            transcription=transcription,
            dispatch_result=dispatch_result,
            audio_path=clip_path,
            kept_audio=keep_audio and created_temp_audio,
        )

        if once:
            break
