"""Read-only Fusion prerequisites and IDE-owned embedded audio selection."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

VERSION = "1.1.0-ninja1"
ROOT = Path("/sys/class/fusion_hat/fusion_hat")


def require_fusion_driver() -> None:
    try:
        ready = (ROOT / "version").read_text().strip() == VERSION
    except OSError:
        ready = False
    if not ready:
        raise RuntimeError(
            "Fusion driver prerequisite missing or outdated. Run scripts/fusion_hat_setup.py "
            "check, review prepare/install, then reboot manually."
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
