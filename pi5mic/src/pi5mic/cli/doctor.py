"""Diagnostics for pi5mic."""

from __future__ import annotations

import importlib.util

import click

from pi5mic.core.devices import list_input_devices, resolve_supported_input_settings
from pi5mic.core.system_info import (
    is_raspberry_pi,
    read_linux_mem_available_mb,
    read_raspberry_pi_model,
    read_raspberry_pi_temperature_celsius,
    read_raspberry_pi_throttled_state,
)
from pi5mic.core.voiceinput import (
    build_voiceinput_runtime_paths,
    read_voiceinput_state,
    validate_voiceinput_readiness,
)
from pi5mic.errors import (
    ConfigError,
    DeviceError,
    IntegrationError,
    STTError,
    TransportError,
    WakeWordError,
)
from pi5mic.install.whisper_cpp import resolve_model_path, resolve_whisper_cpp_command
from pi5mic.integration.delivery import describe_delivery_mode, format_reply_target
from pi5mic.integration.openclaw_setup import (
    discover_openclaw_auto_config,
    explain_openclaw_error,
    probe_openclaw_voice_ready,
)
from pi5mic.stt.gemini import describe_gemini_env_help, resolve_gemini_api_key
from pi5mic.stt.whisper_cpp import describe_whisper_runtime, recommend_whisper_threads

from ._common import build_openclaw_transport, load_manager


@click.command("doctor")
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Check local config, microphone readiness, and STT prerequisites."""
    failures: list[str] = []
    warnings: list[str] = []

    try:
        manager = load_manager(ctx.obj.get("config_file"))
        config = manager.config
        click.echo(f"OK   config loaded: {manager.path}")
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        devices = list_input_devices()
        click.echo(f"OK   audio devices discovered: {len(devices)}")
    except DeviceError as exc:
        failures.append(f"audio devices unavailable: {exc}")
        devices = []

    if is_raspberry_pi():
        model = read_raspberry_pi_model()
        if model:
            click.echo(f"INFO Raspberry Pi: {model}")
        temperature = read_raspberry_pi_temperature_celsius()
        if temperature is not None:
            click.echo(f"INFO Raspberry Pi temp: {temperature:.1f} C")
            if temperature >= 75.0:
                warnings.append(
                    "Raspberry Pi temperature is already high. Heavy whisper.cpp runs may "
                    "throttle or become unstable without better cooling."
                )
        throttled_hex, throttled_issues = read_raspberry_pi_throttled_state()
        if throttled_hex is not None:
            click.echo(f"INFO Raspberry Pi throttled state: {throttled_hex}")
        for issue in throttled_issues:
            warnings.append(
                "Raspberry Pi firmware reported " + issue + ". "
                "If the board powered off after recording, check the power supply and cooling."
            )

    if devices:
        audio_config = config["audio"]
        try:
            resolved_device, actual_rate, device_info, warning = resolve_supported_input_settings(
                selector=audio_config.get("input_device"),
                sample_rate=int(audio_config["sample_rate"]),
                channels=int(audio_config["channels"]),
            )
            device_label = (
                f"{device_info.name} [{device_info.index}]"
                if device_info is not None
                else f"default ({resolved_device if resolved_device is not None else 'auto'})"
            )
            click.echo(f"OK   input stream settings: {device_label} @ {actual_rate} Hz")
            if warning:
                warnings.append(warning)
        except DeviceError as exc:
            failures.append(str(exc))

    selected_backend = str(config["stt"]["selected"])
    click.echo(f"INFO active STT backend: {selected_backend}")
    if selected_backend == "whisper_cpp":
        whisper_config = config["stt"]["whisper_cpp"]
        try:
            resolved_command = resolve_whisper_cpp_command(whisper_config.get("command"))
            resolved_model = resolve_model_path(whisper_config.get("model_path"))
            click.echo(f"OK   whisper.cpp command: {resolved_command}")
            click.echo(f"OK   whisper.cpp model:   {resolved_model}")
            configured_threads = (
                int(whisper_config["threads"])
                if whisper_config.get("threads") not in (None, "")
                else None
            )
            click.echo("OK   whisper.cpp runtime: " + describe_whisper_runtime(configured_threads))
            if (
                is_raspberry_pi()
                and configured_threads is None
                and recommend_whisper_threads(None) is not None
            ):
                warnings.append(
                    "whisper.cpp thread count is not explicitly configured. "
                    "pi5mic will cap it to a safer Raspberry Pi default automatically."
                )
            max_clip_seconds = float(config["audio"].get("max_clip_seconds", 12.0))
            if is_raspberry_pi() and max_clip_seconds > 12.0:
                warnings.append(
                    f"Maximum clip length is {max_clip_seconds:.0f}s. "
                    "The current preview path records the full clip before transcription, "
                    "so 8 to 12 seconds is a safer Raspberry Pi starting point."
                )
            available_mb = read_linux_mem_available_mb()
            if is_raspberry_pi() and available_mb is not None and available_mb < 1024:
                warnings.append(
                    f"Only about {available_mb} MiB of memory is currently available. "
                    "Close other apps, lower clip length, or switch to Gemini if whisper.cpp "
                    "still destabilizes the Pi."
                )
        except STTError as exc:
            failures.append(str(exc))
    elif selected_backend == "gemini":
        try:
            gemini_spec = importlib.util.find_spec("google.genai")
        except ModuleNotFoundError:
            gemini_spec = None
        if gemini_spec is None:
            failures.append(
                "The 'google-genai' package is not installed. Run 'uv sync --extra dev' "
                "from the NinjaClawBot root so pi5mic can use the Gemini backend."
            )
        try:
            credential_name, _api_key = resolve_gemini_api_key()
            click.echo(f"OK   Gemini credentials found in environment ({credential_name})")
        except STTError as exc:
            failures.append(f"{exc} {describe_gemini_env_help()}")
    else:
        failures.append(f"Unsupported STT backend configured: {selected_backend}")

    voiceinput_enabled = bool(config.get("voiceinput", {}).get("enabled", False))
    click.echo(f"INFO always-on voice input: {'enabled' if voiceinput_enabled else 'disabled'}")
    if voiceinput_enabled:
        try:
            readiness = validate_voiceinput_readiness(config)
            click.echo(
                "OK   wake-word detector: "
                f"{readiness['backend']} @ {readiness['detector_sample_rate']} Hz "
                f"(frame length {readiness['detector_frame_length']})"
            )
            click.echo(f"OK   wake word:         {readiness['keyword']}")
            click.echo(f"OK   wake model:        {readiness['model_path']}")
            click.echo(f"OK   wake framework:    {readiness['resolved_inference_framework']}")
            click.echo(f"OK   wake threshold:    {readiness['threshold']:.2f}")
            click.echo(f"OK   wake VAD:          {readiness['wakeword_vad_threshold']:.2f}")
            click.echo(
                "OK   noise suppression: "
                + ("enabled" if readiness["enable_noise_suppression"] else "disabled")
            )
            click.echo(
                "OK   capture policy:    "
                f"silence {readiness['silence_timeout_seconds']:.1f}s, "
                f"max {readiness['max_capture_seconds']:.1f}s, "
                f"cooldown {readiness['cooldown_seconds']:.1f}s"
            )

            runtime_paths = build_voiceinput_runtime_paths(manager.path)
            runtime_state = read_voiceinput_state(runtime_paths)
            click.echo(
                "INFO voice input service: "
                + (
                    f"running (PID {runtime_state['pid']})"
                    if runtime_state["running"]
                    else str(runtime_state.get("mode") or "stopped")
                )
            )
            click.echo(f"INFO voice input state: {runtime_paths.state_file}")
            click.echo(f"INFO voice input log:   {runtime_paths.log_file}")
            if runtime_state.get("last_error"):
                warnings.append(
                    "The voice input service recorded a recent error: "
                    + str(runtime_state["last_error"])
                )
        except (ConfigError, WakeWordError) as exc:
            failures.append(str(exc))
    elif bool(config.get("wakeword", {}).get("enabled", False)):
        warnings.append(
            "Wake-word detection is enabled in the config, but always-on voice input is disabled. "
            "Rerun `uv run pi5mic setup` if you want to finish the always-on setup."
        )

    if config["profile"] == "openclaw":
        openclaw_config = config["integration"]["openclaw"]
        delivery_mode = str(config["integration"].get("delivery_mode", "local_only"))
        configured_reply_target = format_reply_target(
            openclaw_config.get("reply_channel"),
            openclaw_config.get("reply_to"),
            reply_account=openclaw_config.get("reply_account"),
        )
        try:
            transport = build_openclaw_transport(config)
            click.echo(f"OK   OpenClaw command:  {transport.command}")
            click.echo(
                "OK   OpenClaw delivery: "
                + describe_delivery_mode(
                    delivery_mode,
                    reply_channel=openclaw_config.get("reply_channel"),
                    reply_to=openclaw_config.get("reply_to"),
                    reply_account=openclaw_config.get("reply_account"),
                )
            )
            discovery = discover_openclaw_auto_config(
                command=openclaw_config.get("command"),
                saved_gateway_url=openclaw_config.get("gateway_url"),
                saved_agent_id=openclaw_config.get("agent_id"),
                saved_session_key=openclaw_config.get("session_key"),
                saved_reply_channel=openclaw_config.get("reply_channel"),
                saved_reply_to=openclaw_config.get("reply_to"),
                saved_reply_account=openclaw_config.get("reply_account"),
            )
            config_display = (
                str(discovery.config_path)
                if discovery.config_path is not None
                else "not found (using pi5mic saved values/defaults)"
            )
            click.echo(f"OK   OpenClaw config:   {config_display}")
            click.echo(
                "OK   OpenClaw telegram: "
                + ("enabled" if discovery.telegram_enabled else "not enabled")
            )
            if discovery.telegram_reply_target is not None:
                click.echo("OK   Telegram target:  " + discovery.telegram_reply_target.describe())
            elif discovery.telegram_enabled:
                warnings.append(
                    "OpenClaw Telegram is enabled, but pi5mic could not detect a recent Telegram "
                    "chat or topic target yet. Send one short Telegram message to the bot, then "
                    "rerun `uv run pi5mic setup` to mirror voice replies there."
                )
                if discovery.telegram_reply_target_error:
                    warnings.append(discovery.telegram_reply_target_error)

            if delivery_mode == "local_plus_explicit_channel_target":
                if not configured_reply_target:
                    failures.append(
                        "OpenClaw delivery is set to local+channel, but pi5mic does not have a "
                        "complete reply target saved."
                    )
                elif (
                    not discovery.telegram_enabled
                    and str(openclaw_config.get("reply_channel")) == "telegram"
                ):
                    failures.append(
                        "pi5mic is configured to mirror replies to Telegram, but OpenClaw "
                        "Telegram is not enabled in openclaw.json."
                    )
                else:
                    click.echo(f"OK   Saved reply target: {configured_reply_target}")
                    discovered_target = (
                        format_reply_target(
                            discovery.telegram_reply_target.channel,
                            discovery.telegram_reply_target.target,
                            reply_account=discovery.telegram_reply_target.account_id,
                        )
                        if discovery.telegram_reply_target is not None
                        else None
                    )
                    if (
                        discovered_target
                        and configured_reply_target != discovered_target
                        and str(openclaw_config.get("reply_channel")) == "telegram"
                    ):
                        warnings.append(
                            "OpenClaw's latest Telegram route differs from the reply target saved "
                            "in pi5mic. If replies are going to the wrong chat, rerun "
                            "`uv run pi5mic setup` to switch to the current Telegram target."
                        )
            elif discovery.telegram_reply_target is not None:
                warnings.append(
                    "OpenClaw already has a Telegram reply target available, but pi5mic is still "
                    "set to local-only delivery. Rerun `uv run pi5mic setup` if you want each "
                    "voice turn to reply both locally and in Telegram."
                )
            if not discovery.plugin_ready:
                warnings.append(
                    "The local OpenClaw config does not yet look fully ready for the "
                    "NinjaClawBot plugin. If voice handoff fails, confirm the plugin is "
                    "installed, allowlisted, and enabled, then restart the gateway."
                )
            report = probe_openclaw_voice_ready(
                command=openclaw_config.get("command"),
                gateway_url=openclaw_config.get("gateway_url"),
                check_presence=bool(config["integration"].get("presence_enabled", True)),
            )
            for line in report.ok_lines:
                click.echo(f"OK   {line}")
            warnings.extend(report.warnings)
        except (ConfigError, IntegrationError, TransportError) as exc:
            failures.append(explain_openclaw_error(str(exc)))

    if failures:
        click.echo("\nFailures:")
        for failure in failures:
            click.echo(f"  - {failure}")
        raise click.ClickException("pi5mic doctor detected configuration problems.")

    if warnings:
        click.echo("\nWarnings:")
        for warning in warnings:
            click.echo(f"  - {warning}")
        click.echo("\npi5mic doctor passed with warnings.")
        return

    click.echo("\npi5mic doctor passed.")
