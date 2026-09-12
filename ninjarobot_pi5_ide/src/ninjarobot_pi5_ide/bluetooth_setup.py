"""Headless speaker setup and independent, opt-in user-service lifecycle."""

from __future__ import annotations

import asyncio
import fcntl
import os
import signal
import sys
from pathlib import Path
from typing import Any

import click

from .audio_process import run_audio_process
from .bluetooth_speaker import BluetoothError, BlueZSpeaker, speaker_output
from .config import BluetoothSpeakerConfig, RobotConfig
from .config_import import DEFAULT_USER_CONFIG, load_effective_config, save_robot_config

SERVICE = "ninjarobot-speaker-reconnect.service"


async def terminal_prompt(message: str) -> str:
    """Cancellable terminal input; no stranded input thread after a pairing timeout."""
    click.echo(message + ": ", nl=False)
    loop = asyncio.get_running_loop()
    answer: asyncio.Future[str] = loop.create_future()
    descriptor = sys.stdin.fileno()

    def ready() -> None:
        if not answer.done():
            line = sys.stdin.readline()
            if not line:
                answer.set_exception(BluetoothError("Terminal closed; setup cancelled."))
            else:
                answer.set_result(line.rstrip("\r\n"))

    loop.add_reader(descriptor, ready)
    try:
        return await answer
    finally:
        loop.remove_reader(descriptor)


def save_selection(
    path: Path, expected: bytes | None, config: RobotConfig, address: str, adapter: str, output: str
) -> Path:
    """Preserve all settings and refuse overwriting concurrent edits or symlinks."""
    path = path.expanduser().absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise BluetoothError("Use a real private config path, not a symbolic link.")
    lock = path.with_name(path.name + ".speaker-lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = path.read_bytes() if path.exists() else None
        if current != expected:
            raise BluetoothError(
                "Configuration changed during setup. No settings were saved; retry."
            )
        updated = config.model_copy(
            update={
                "speech_output": config.speech_output.model_copy(update={"output_node": output}),
                "bluetooth_speaker": BluetoothSpeakerConfig(
                    address=address,
                    adapter=adapter,
                    auto_reconnect=True,
                ),
            }
        )
        # Keep a private previous version; do not overwrite an earlier backup.
        if expected is not None:
            backup = path.with_name(path.name + ".before-speaker")
            try:
                backup_fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(backup_fd, "wb") as handle:
                    handle.write(expected)
                    handle.flush()
                    os.fsync(handle.fileno())
        return save_robot_config(updated, path, overwrite=expected is not None)
    finally:
        os.close(descriptor)


def service_text(config_path: Path, python: Path | None = None) -> str:
    def quote(value: str) -> str:
        if any(c in value for c in "\n\r\0"):
            raise ValueError("service paths cannot contain control characters")
        # systemd performs specifier and environment expansion even inside quotes.
        return (
            '"'
            + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
            + '"'
        )

    executable = quote(str(python or Path(sys.executable)))
    config = quote(str(config_path.expanduser().absolute()))
    return (
        "[Unit]\nDescription=NinjaRobot selected Bluetooth speaker reconnect\n"
        "After=pipewire.service wireplumber.service\n"
        "Wants=pipewire.service wireplumber.service\n\n"
        "[Service]\nType=simple\n"
        f"ExecStart={executable} -m ninjarobot_pi5_ide.bluetooth_setup run --config {config}\n"
        "Restart=on-failure\nRestartSec=15\nTimeoutStopSec=10\n"
        "NoNewPrivileges=yes\nUMask=0077\n\n[Install]\nWantedBy=default.target\n"
    )


async def install_service(
    config_path: Path,
    *,
    apply: bool = False,
    directory: Path | None = None,
    runner: Any = run_audio_process,
) -> str:
    content = service_text(config_path)
    if not apply:
        return content
    target_dir = directory or Path("~/.config/systemd/user").expanduser()
    if target_dir.is_symlink():
        raise BluetoothError("User service directory must not be a symbolic link.")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / SERVICE
    if target.is_symlink():
        raise BluetoothError("User service file must not be a symbolic link.")
    if target.exists() and target.read_text() != content:
        raise BluetoothError(
            "Reconnect unit differs from this configuration. "
            "Review the existing unit before replacing it."
        )
    if not target.exists():
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
    await runner(["systemctl", "--user", "daemon-reload"], timeout=10)
    await runner(["systemctl", "--user", "enable", "--now", SERVICE], timeout=15)
    return "Independent speaker reconnect service enabled. Agent startup is unchanged."


async def connect_wizard(
    config_path: Path | None = None,
    *,
    backend_factory: Any = BlueZSpeaker,
    prompt: Any = terminal_prompt,
    runner: Any = run_audio_process,
    output_resolver: Any = speaker_output,
) -> None:
    path = (config_path or DEFAULT_USER_CONFIG).expanduser().absolute()
    expected = path.read_bytes() if path.exists() else None
    config = load_effective_config(config_path)
    backend = backend_factory(config.bluetooth_speaker.adapter, prompt=prompt)
    try:
        click.echo(
            "Bluetooth Speaker Connection. Turn on the speaker and enable pairing mode.\n"
            "Only Bluetooth/audio services are used; no robot or microphone is started."
        )
        # Starting installed user audio services is idempotent and does not capture audio.
        try:
            await runner(
                ["systemctl", "--user", "start", "pipewire.service", "wireplumber.service"],
                timeout=15,
            )
        except (OSError, RuntimeError, TimeoutError) as error:
            raise BluetoothError(
                "User audio services are unavailable. Follow the Lite audio setup "
                "instructions; check systemctl --user status pipewire wireplumber."
            ) from error
        await backend.start()
        while True:
            click.echo("Scanning for 10 seconds. The list also includes previously known devices.")
            devices = await backend.scan()
            for number, device in enumerate(devices, 1):
                click.echo(
                    f"{number}. {device.name} [{device.address}] "
                    f"paired={device.paired} connected={device.connected}"
                )
            choice = (await prompt("Choose a number, r to rescan, or q to cancel")).strip().lower()
            if choice == "q":
                return
            if choice == "r":
                continue
            if not choice.isdecimal() or not 1 <= int(choice) <= len(devices):
                click.echo("Invalid selection. Scan again or enter q to cancel.")
                continue
            selected = devices[int(choice) - 1]
            await backend.connect(selected.address, pair=True)
            output = ""
            for attempt in range(10):
                try:
                    output = await output_resolver(selected.address)
                    break
                except (BluetoothError, RuntimeError, OSError):
                    if attempt == 9:
                        raise
                    await asyncio.sleep(1)
            save_selection(
                path, expected, config, selected.address, config.bluetooth_speaker.adapter, output
            )
            click.echo(
                f"Connected and saved: {selected.name}. Voice and volume settings were preserved.\n"
                "Restart an already-running Agent when convenient to load the saved output."
            )
            click.echo(service_text(path))
            answer = await prompt(
                "Enable this user service to reconnect even while the Agent is stopped? [y/N]"
            )
            if answer.strip().lower() in {"y", "yes"}:
                click.echo(await install_service(path, apply=True, runner=runner))
                click.echo(
                    'For reconnect after logout/reboot, check: loginctl show-user "$USER" -p Linger'
                )
            else:
                click.echo("Service not enabled. Use bluetooth service --apply when ready.")
            click.echo("No test sound was played. Use the walkthrough's opt-in sound test.")
            return
    finally:
        await backend.close()


async def reconnect_once(
    config: RobotConfig,
    *,
    backend_factory: Any = BlueZSpeaker,
    output_resolver: Any = speaker_output,
) -> str:
    selected = config.bluetooth_speaker
    if not selected.auto_reconnect or not selected.address:
        return "disabled"
    backend = backend_factory(selected.adapter)
    try:
        await backend.start()
        await backend.connect(selected.address)  # Never scan, pair or trust from this service.
        await output_resolver(selected.address)
        return "ready"
    finally:
        await backend.close()


async def reconnect_forever(config_path: Path) -> None:
    delay = 5
    last = ""
    while True:
        try:
            result = await reconnect_once(load_effective_config(config_path))
            delay = 5 if result == "ready" else 30
        except (OSError, ValueError, RuntimeError, TimeoutError) as error:
            result = f"Waiting for selected speaker ({type(error).__name__}). "
            delay = min(60, delay * 2)
        if result != last:
            click.echo(result)
            last = result
        await asyncio.sleep(delay)


async def run_service(config_path: Path) -> None:
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    assert task is not None
    loop.add_signal_handler(signal.SIGTERM, task.cancel)
    try:
        await reconnect_forever(config_path)
    finally:
        loop.remove_signal_handler(signal.SIGTERM)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Independent selected-speaker reconnect helper")
    parser.add_argument("operation", choices=["run"])
    parser.add_argument("--config", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        asyncio.run(run_service(arguments.config))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
