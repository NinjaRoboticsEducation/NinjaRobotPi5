"""Read-only Fusion prerequisites and IDE-owned embedded audio selection."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

VERSION = "1.1.0-ninja1"
ROOT = Path("/sys/class/fusion_hat/fusion_hat")


class FusionPrerequisiteError(RuntimeError):
    """A safe diagnostic that onboarding may display without private file contents."""


def require_fusion_driver() -> None:
    try:
        version = (ROOT / "version").read_text().strip()
    except FileNotFoundError as exc:
        raise FusionPrerequisiteError(
            "Fusion kernel interface is missing (driver not installed, not bound, or reboot "
            "pending). Run: uv run --frozen python scripts/fusion_hat_setup.py check. "
            "Follow the Fusion installation guide: prepare, preview, explicit install, "
            "then manually reboot. Re-selecting the HAT does not install its driver."
        ) from exc
    except OSError as exc:
        raise FusionPrerequisiteError(
            "Fusion driver version cannot be read. Check device permissions and kernel logs. "
            "Run scripts/fusion_hat_setup.py check as the normal robot user."
        ) from exc
    if version != VERSION:
        raise FusionPrerequisiteError(
            f"Fusion driver is incompatible; reviewed version {VERSION} is required. "
            "Review scripts/fusion_hat_setup.py check and schedule driver replacement "
            "and manual reboot; do not use a raw I2C fallback."
        )


def require_fusion_servo() -> None:
    """Read-only preflight: never instantiate a backend or write a PWM file."""
    require_fusion_driver()
    for channel in range(12):
        for attribute in ("period", "duty_cycle", "enable"):
            path = ROOT / "pwm" / f"pwm{channel}" / attribute
            if not path.is_file():
                raise FusionPrerequisiteError(
                    f"Fusion PWM{channel} {attribute} interface is missing. "
                    "Check kernel probe logs and the reviewed driver installation after reboot."
                )
            if not os.access(path, os.W_OK):
                raise FusionPrerequisiteError(
                    f"Fusion PWM{channel} is not writable by this user. Check gpio group "
                    "membership and the installed udev rule; log in again after group changes. "
                    "Do not run onboarding as root."
                )
    lock = Path("/run/lock/ninjarobot-fusion.lock")
    if lock.is_symlink() or not lock.is_file() or not os.access(lock, os.R_OK | os.W_OK):
        raise FusionPrerequisiteError(
            "Fusion shared session lock is missing or inaccessible. Verify the installed "
            "tmpfiles rule, gpio group membership and reboot. Do not create a per-user lock."
        )


def set_fusion_speaker(enabled: bool) -> None:
    require_fusion_driver()
    (ROOT / "speaker").write_text("1\n" if enabled else "0\n")


async def set_fusion_speaker_async(enabled: bool) -> None:
    """Join a kernel write before cancellation can begin the opposite write."""
    worker = asyncio.create_task(asyncio.to_thread(set_fusion_speaker, enabled))
    try:
        await asyncio.shield(worker)
    except asyncio.CancelledError:
        await worker
        raise


def configure_fusion_microphone(config_path: Path) -> str:
    """Enumerate input devices without recording; persist an explicitly requested selection."""
    from .config import RobotConfig
    from .config_import import discover_pi5_configs, load_effective_config, save_robot_config
    from .microphone import _load_microphone_backend

    require_fusion_driver()
    backend = _load_microphone_backend()
    matches = [
        device
        for device in backend.list_input_devices()
        if device.max_input_channels > 0
        and any(token in device.name.lower() for token in ("googlevoicehat", "sndrpigooglevoi"))
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Fusion microphone missing or ambiguous; verify the installed sound card"
        )
    # PortAudio appends a numeric ALSA address. Persist the stable card name prefix.
    selector = matches[0].name.split(" (hw:")[0]
    current = load_effective_config(config_path if config_path.exists() else None)
    payload = current.model_dump()
    payload["hardware"]["microphone"]["device_selector"] = selector
    candidate = RobotConfig.model_validate(payload)
    item = next(item for item in discover_pi5_configs() if item.library == "pi5mic")
    path = item.path.expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.resolve() != path.parent:
        raise ValueError("microphone configuration must not use symlinks")
    data = json.loads(path.read_text()) if path.exists() else {}
    data.setdefault("audio", {})["input_device"] = selector
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    save_robot_config(candidate, config_path, overwrite=config_path.exists())
    return selector
