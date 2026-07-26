"""Status reporting for pi5mic."""

from __future__ import annotations

import click

from pi5mic.core.devices import get_default_input_device, list_input_devices
from pi5mic.core.voiceinput import build_voiceinput_runtime_paths, read_voiceinput_state
from pi5mic.errors import ConfigError, DeviceError, STTError
from pi5mic.integration.delivery import describe_delivery_mode, format_reply_target
from pi5mic.stt.gemini import resolve_gemini_api_key
from pi5mic.stt.whisper_cpp import describe_whisper_runtime

from ._common import load_manager


@click.command("status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show config and local microphone readiness."""
    try:
        manager = load_manager(ctx.obj.get("config_file"))
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    config = manager.config
    audio_config = config["audio"]
    stt_config = config["stt"]

    click.echo("pi5mic Status")
    click.echo(f"  Config file:      {manager.path}")
    click.echo(f"  Profile:          {config.get('profile')}")
    click.echo(f"  Input device:     {audio_config.get('input_device') or 'default'}")
    click.echo(f"  Sample rate:      {audio_config.get('sample_rate')} Hz")
    click.echo(f"  Channels:         {audio_config.get('channels')}")
    click.echo(f"  STT backend:      {stt_config.get('selected')}")
    if stt_config.get("selected") == "whisper_cpp":
        whisper_config = stt_config.get("whisper_cpp", {})
        configured_threads = (
            int(whisper_config["threads"])
            if isinstance(whisper_config, dict) and whisper_config.get("threads") not in (None, "")
            else None
        )
        click.echo(f"  Whisper runtime:  {describe_whisper_runtime(configured_threads)}")
    elif stt_config.get("selected") == "gemini":
        try:
            credential_name, _api_key = resolve_gemini_api_key()
            click.echo(f"  Gemini auth:      {credential_name}")
        except STTError:
            click.echo("  Gemini auth:      missing")

    voiceinput_config = config.get("voiceinput", {})
    wakeword_config = config.get("wakeword", {})
    voiceinput_enabled = bool(voiceinput_config.get("enabled", False))
    click.echo(f"  Voice input:      {'enabled' if voiceinput_enabled else 'disabled'}")
    if voiceinput_enabled:
        click.echo(
            "  Wake word:        "
            f"{wakeword_config.get('keyword') or 'unset'} "
            f"({wakeword_config.get('backend') or 'unset'})"
        )
        model_path = wakeword_config.get("model_path")
        if model_path:
            click.echo(f"  Wake model:       {model_path}")
        click.echo(f"  Wake threshold:   {float(wakeword_config.get('threshold', 0.5)):.2f}")
        click.echo(f"  Wake VAD:         {float(wakeword_config.get('vad_threshold', 0.0)):.2f}")
        click.echo(
            "  Noise filter:     "
            + (
                "enabled"
                if bool(wakeword_config.get("enable_noise_suppression", False))
                else "disabled"
            )
        )
        click.echo(f"  Wake framework:   {wakeword_config.get('inference_framework', 'auto')}")
        click.echo(
            f"  Silence stop:     {float(voiceinput_config.get('silence_timeout_seconds', 3.0)):.1f}s"
        )
        click.echo(
            f"  Max capture:      {float(voiceinput_config.get('max_capture_seconds', 10.0)):.1f}s"
        )
        click.echo(f"  Session strategy: {voiceinput_config.get('session_strategy', 'agent_main')}")
        runtime_paths = build_voiceinput_runtime_paths(manager.path)
        runtime_state = read_voiceinput_state(runtime_paths)
        click.echo(
            "  Voice service:    "
            + (
                f"running (PID {runtime_state['pid']})"
                if runtime_state["running"]
                else str(runtime_state.get("mode") or "stopped")
            )
        )
        if runtime_state.get("last_error"):
            click.echo(f"  Voice error:      {runtime_state['last_error']}")
        click.echo(f"  Voice state file: {runtime_paths.state_file}")
        click.echo(f"  Voice log file:   {runtime_paths.log_file}")
    if config.get("profile") == "openclaw":
        openclaw_config = config["integration"]["openclaw"]
        click.echo(f"  OpenClaw command: {openclaw_config.get('command') or 'openclaw (PATH)'}")
        click.echo(
            f"  Gateway URL:      {openclaw_config.get('gateway_url') or 'local CLI config'}"
        )
        click.echo(f"  Agent id:         {openclaw_config.get('agent_id')}")
        click.echo(f"  Session key:      {openclaw_config.get('session_key')}")
        click.echo(
            "  Delivery mode:    "
            + describe_delivery_mode(
                str(config["integration"].get("delivery_mode", "local_only")),
                reply_channel=openclaw_config.get("reply_channel"),
                reply_to=openclaw_config.get("reply_to"),
                reply_account=openclaw_config.get("reply_account"),
            )
        )
        reply_target = format_reply_target(
            openclaw_config.get("reply_channel"),
            openclaw_config.get("reply_to"),
            reply_account=openclaw_config.get("reply_account"),
        )
        if reply_target:
            click.echo(f"  Reply target:     {reply_target}")

    try:
        devices = list_input_devices()
        default_device = get_default_input_device()
        click.echo(f"  Input devices:    {len(devices)}")
        click.echo(
            f"  Default device:   {default_device if default_device is not None else 'none'}"
        )
    except DeviceError as exc:
        click.echo(f"  Audio backend:    unavailable ({exc})")
