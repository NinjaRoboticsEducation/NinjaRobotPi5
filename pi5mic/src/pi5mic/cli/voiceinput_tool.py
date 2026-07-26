"""Manual control surface for the always-on pi5mic voice input loop."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import click

from pi5mic.core.voiceinput import (
    VoiceInputLoop,
    build_voiceinput_runtime_paths,
    normalize_voiceinput_config,
    read_voiceinput_state,
    update_voiceinput_state,
    validate_voiceinput_readiness,
)
from pi5mic.errors import (
    ConfigError,
    DeviceError,
    IntegrationError,
    ListenerBusyError,
    RecordingError,
    STTError,
    TransportError,
    WakeWordError,
)

from ._common import load_manager

_START_TIMEOUT_SECONDS = 8.0
_STOP_TIMEOUT_SECONDS = 10.0


def _append_service_log(log_path: Path, message: str) -> None:
    timestamp = datetime.now(UTC).isoformat()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def _tail_service_log(log_path: Path, *, lines: int) -> list[str]:
    if not log_path.exists():
        return []
    try:
        content = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return content[-lines:]


def _load_voiceinput_context(ctx: click.Context) -> tuple[object, dict, object]:
    manager = load_manager(ctx.obj.get("config_file"))
    config = manager.config
    paths = build_voiceinput_runtime_paths(manager.path)
    return manager, config, paths


def _ensure_voiceinput_enabled(config: dict) -> dict:
    return validate_voiceinput_readiness(config)


def _print_voiceinput_status(*, manager_path: Path, config: dict, paths) -> None:
    state = read_voiceinput_state(paths)
    voiceinput_enabled = bool(config.get("voiceinput", {}).get("enabled", False))
    wakeword_enabled = bool(config.get("wakeword", {}).get("enabled", False))

    click.echo("pi5mic Voice Input")
    click.echo(f"  Config file:      {manager_path}")
    click.echo(f"  Enabled:          {'yes' if voiceinput_enabled else 'no'}")
    click.echo(f"  Wake word ready:  {'yes' if wakeword_enabled else 'no'}")
    if voiceinput_enabled:
        try:
            normalized = normalize_voiceinput_config(config)
            click.echo(f"  Wake word:        {normalized['keyword']}")
            if normalized["model_path"]:
                click.echo(f"  Wake model:       {normalized['model_path']}")
            click.echo(f"  Wake threshold:   {normalized['threshold']:.2f}")
            click.echo(f"  Wake VAD:         {normalized['wakeword_vad_threshold']:.2f}")
            click.echo(
                "  Noise filter:     "
                + ("enabled" if normalized["enable_noise_suppression"] else "disabled")
            )
            click.echo(f"  Wake framework:   {normalized['inference_framework']}")
            click.echo(f"  Silence timeout:  {normalized['silence_timeout_seconds']:.1f}s")
            click.echo(f"  Max capture:      {normalized['max_capture_seconds']:.1f}s")
            click.echo(f"  Cooldown:         {normalized['cooldown_seconds']:.1f}s")
            click.echo(f"  Session strategy: {normalized['session_strategy']}")
        except ConfigError as exc:
            click.echo(f"  Voice config:     invalid ({exc})")
    click.echo(f"  Running:          {'yes' if state['running'] else 'no'}")
    click.echo(f"  Mode:             {state.get('mode') or 'unknown'}")
    click.echo(f"  Listener state:   {state.get('listener_state') or 'unknown'}")
    if state.get("pid") is not None:
        click.echo(f"  PID:              {state['pid']}")
    if state.get("last_triggered_at"):
        click.echo(f"  Last triggered:   {state['last_triggered_at']}")
    if state.get("last_completed_at"):
        click.echo(f"  Last completed:   {state['last_completed_at']}")
    if state.get("last_error"):
        click.echo(f"  Last error:       {state['last_error']}")
    click.echo(f"  Wake-word hits:   {state.get('wakeword_hits', 0)}")
    click.echo(f"  Cycles complete:  {state.get('cycles_completed', 0)}")
    click.echo(f"  State file:       {paths.state_file}")
    click.echo(f"  Log file:         {paths.log_file}")


def _run_voiceinput_loop(
    *,
    manager_path: Path,
    config: dict,
    paths,
    echo_logs: bool,
) -> None:
    normalized = normalize_voiceinput_config(config)

    def _log(message: str) -> None:
        _append_service_log(paths.log_file, message)
        if echo_logs:
            click.echo(message)

    stop_event = Event()

    def _handle_stop(_signum, _frame) -> None:
        stop_event.set()

    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    update_voiceinput_state(
        paths,
        running=False,
        pid=None,
        mode="starting",
        profile=str(config.get("profile", "standalone")),
        config_file=str(manager_path),
        session_strategy=normalized["session_strategy"],
        wakeword_backend=normalized["backend"],
        wakeword_keyword=normalized["keyword"],
        listener_state="idle",
        last_error=None,
    )
    _log("Starting always-on voice input loop.")

    try:
        loop = VoiceInputLoop(
            config=config,
            config_path=manager_path,
            state_paths=paths,
            event_logger=_log,
            detail_logger=click.echo if echo_logs else None,
        )
        loop.run(stop_event)
        _log("Voice input loop stopped cleanly.")
    except (
        ConfigError,
        DeviceError,
        IntegrationError,
        ListenerBusyError,
        RecordingError,
        STTError,
        TransportError,
        WakeWordError,
        ValueError,
    ) as exc:
        _append_service_log(paths.log_file, f"ERROR {exc}")
        update_voiceinput_state(
            paths,
            running=False,
            pid=None,
            mode="error",
            listener_state="idle",
            last_error=str(exc),
        )
        raise click.ClickException(str(exc)) from exc
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)


@click.group("voiceinput-tool", invoke_without_command=True)
@click.pass_context
def voiceinput_tool(ctx: click.Context) -> None:
    """Start, stop, and inspect the manual always-on voice input service."""
    if ctx.invoked_subcommand is not None:
        return

    click.echo("pi5mic voiceinput-tool")
    click.echo("---------------------")
    click.echo(
        "This tool controls the always-on wake-word listener. It never starts automatically; "
        "you choose when to start or stop it."
    )

    while True:
        click.echo("\n1. Show voice input status")
        click.echo("2. Start background listener")
        click.echo("3. Stop background listener")
        click.echo("4. Run listener in foreground")
        click.echo("5. Show recent voice input logs")
        click.echo("6. Exit")

        choice = click.prompt(
            "Choose an action",
            type=click.Choice(["1", "2", "3", "4", "5", "6"]),
            default="1",
            show_choices=False,
        )

        try:
            if choice == "1":
                ctx.invoke(voiceinput_status)
            elif choice == "2":
                ctx.invoke(voiceinput_start)
            elif choice == "3":
                ctx.invoke(voiceinput_stop)
            elif choice == "4":
                ctx.invoke(voiceinput_foreground)
            elif choice == "5":
                ctx.invoke(voiceinput_logs, lines=20)
            else:
                click.echo("Leaving pi5mic voiceinput-tool.")
                break
        except click.ClickException as exc:
            click.echo(f"\nERROR: {exc}")
            click.echo("Fix the issue above, then choose the action again from this menu.")


@voiceinput_tool.command("status")
@click.pass_context
def voiceinput_status(ctx: click.Context) -> None:
    """Show the always-on voice input config and runtime state."""
    try:
        manager, config, paths = _load_voiceinput_context(ctx)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    _print_voiceinput_status(manager_path=manager.path, config=config, paths=paths)


@voiceinput_tool.command("logs")
@click.option("--lines", type=int, default=20, show_default=True, help="Lines to show.")
@click.pass_context
def voiceinput_logs(ctx: click.Context, lines: int) -> None:
    """Show recent always-on voice input log lines."""
    try:
        manager, _config, paths = _load_voiceinput_context(ctx)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    del manager
    recent_lines = _tail_service_log(paths.log_file, lines=max(1, lines))
    if not recent_lines:
        click.echo(f"No voice input log entries found yet at {paths.log_file}.")
        return

    click.echo(f"Recent voice input logs from {paths.log_file}:")
    for line in recent_lines:
        click.echo(f"  {line}")


@voiceinput_tool.command("start")
@click.pass_context
def voiceinput_start(ctx: click.Context) -> None:
    """Start the always-on voice input loop in the background."""
    try:
        manager, config, paths = _load_voiceinput_context(ctx)
        readiness = _ensure_voiceinput_enabled(config)
    except (ConfigError, WakeWordError) as exc:
        raise click.ClickException(str(exc)) from exc

    state = read_voiceinput_state(paths)
    if state["running"]:
        click.echo(
            f"Voice input is already running in the background (PID {state['pid']}). "
            "Use `uv run pi5mic voiceinput-tool stop` before starting another copy."
        )
        return

    update_voiceinput_state(
        paths,
        running=False,
        pid=None,
        mode="starting",
        profile=str(config.get("profile", "standalone")),
        config_file=str(manager.path),
        session_strategy=readiness["session_strategy"],
        wakeword_backend=readiness["backend"],
        wakeword_keyword=readiness["keyword"],
        listener_state="idle",
        last_error=None,
    )
    _append_service_log(paths.log_file, "Launching background voice input listener.")

    command = [
        sys.executable,
        "-m",
        "pi5mic",
        "--config-file",
        str(manager.path),
        "voiceinput-tool",
        "_run",
    ]
    with paths.log_file.open("a", encoding="utf-8") as handle:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(manager.path.parent),
                stdout=handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            raise click.ClickException(f"Could not start the voice input background process: {exc}")

    deadline = time.monotonic() + _START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        state = read_voiceinput_state(paths)
        if state["running"] and state["pid"] == process.pid:
            click.echo(
                "Started the always-on voice input listener in the background.\n"
                "Use `uv run pi5mic voiceinput-tool stop` to stop it later."
            )
            return
        if process.poll() is not None:
            break
        time.sleep(0.2)

    recent_logs = _tail_service_log(paths.log_file, lines=12)
    details = "\n".join(recent_logs) if recent_logs else "No log output was captured."
    raise click.ClickException(
        "Voice input did not start cleanly. Recent log output:\n"
        f"{details}\n"
        "Run `uv run pi5mic voiceinput-tool foreground` for an interactive debug run if needed."
    )


@voiceinput_tool.command("stop")
@click.pass_context
def voiceinput_stop(ctx: click.Context) -> None:
    """Stop the background always-on voice input loop."""
    try:
        _manager, _config, paths = _load_voiceinput_context(ctx)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    state = read_voiceinput_state(paths)
    if not state["running"] or state["pid"] is None:
        click.echo("Voice input is not running right now.")
        return

    pid = int(state["pid"])
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        update_voiceinput_state(
            paths,
            running=False,
            pid=None,
            mode="stopped",
            listener_state="idle",
            last_error=f"Process {pid} was not running when stop was requested: {exc}",
        )
        click.echo("Voice input was already stopped.")
        return

    deadline = time.monotonic() + _STOP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        updated_state = read_voiceinput_state(paths)
        if not updated_state["running"]:
            click.echo("Stopped the always-on voice input listener.")
            return
        time.sleep(0.2)

    raise click.ClickException(
        "The voice input process did not stop within 10 seconds. "
        "Check the log and stop it manually if necessary."
    )


@voiceinput_tool.command("foreground")
@click.pass_context
def voiceinput_foreground(ctx: click.Context) -> None:
    """Run the always-on voice input loop in the foreground for testing."""
    try:
        manager, config, paths = _load_voiceinput_context(ctx)
        readiness = _ensure_voiceinput_enabled(config)
    except (ConfigError, WakeWordError) as exc:
        raise click.ClickException(str(exc)) from exc

    state = read_voiceinput_state(paths)
    if state["running"]:
        raise click.ClickException(
            f"Voice input is already running in the background (PID {state['pid']}). "
            "Stop it before starting a foreground debug session."
        )

    click.echo("Starting voice input in the foreground.")
    click.echo("Press Ctrl+C to stop it.")
    click.echo(
        f"Wake word: {readiness['keyword']} | Silence stop: {readiness['silence_timeout_seconds']:.1f}s | "
        f"Max capture: {readiness['max_capture_seconds']:.1f}s"
    )
    _run_voiceinput_loop(
        manager_path=manager.path,
        config=config,
        paths=paths,
        echo_logs=True,
    )


@voiceinput_tool.command("_run", hidden=True)
@click.pass_context
def voiceinput_runner(ctx: click.Context) -> None:
    """Internal background runner for the always-on voice input loop."""
    try:
        manager, config, paths = _load_voiceinput_context(ctx)
        _ensure_voiceinput_enabled(config)
    except (ConfigError, WakeWordError) as exc:
        raise click.ClickException(str(exc)) from exc

    _run_voiceinput_loop(
        manager_path=manager.path,
        config=config,
        paths=paths,
        echo_logs=False,
    )
