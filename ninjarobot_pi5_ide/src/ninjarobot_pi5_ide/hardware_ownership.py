"""Cross-process ownership for the integrated Raspberry Pi hardware assembly."""

from __future__ import annotations

import fcntl
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

DEFAULT_HARDWARE_LOCK = Path("~/.local/state/ninjarobot_pi5/hardware-owner.lock")


class HardwareOwnershipError(RuntimeError):
    """Raised when another process already owns the integrated hardware."""


class HardwareOwnership:
    """Hold one advisory file lock for all integrated hardware resources."""

    def __init__(self, path: str | Path = DEFAULT_HARDWARE_LOCK) -> None:
        self._path = Path(path).expanduser()
        self._handle: TextIO | None = None

    @property
    def owned(self) -> bool:
        """Return whether this object currently holds the process lock."""

        return self._handle is not None

    def acquire(self) -> None:
        """Claim hardware ownership or raise an actionable conflict error."""

        if self._handle is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = self._path.open("a+", encoding="utf-8")
        os.chmod(self._path, 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.seek(0)
            owner = handle.read().strip()
            handle.close()
            detail = f" Current owner: {owner}" if owner else ""
            raise HardwareOwnershipError(
                "NinjaRobotPi5 hardware is already owned by another process."
                f"{detail} Stop the running agent service before using "
                "ninjarobot-ide-tool directly, or control the robot through "
                "the connected agent interface."
            ) from exc
        try:
            payload = {
                "acquired_at": datetime.now(UTC).isoformat(),
                "pid": os.getpid(),
                "program": Path(sys.argv[0]).name or "python",
            }
            handle.seek(0)
            handle.truncate()
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        except Exception:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
            raise
        self._handle = handle

    def release(self) -> None:
        """Release ownership and remove stale owner metadata."""

        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            handle.seek(0)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
