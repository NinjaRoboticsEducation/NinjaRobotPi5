"""Owner-private active behavior registration for cross-process stop."""

from __future__ import annotations

import json
import os
import signal
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_ACTIVE_BEHAVIOR_FILE = Path(
    "~/.local/state/ninjarobot_pi5/active_behavior.json"
).expanduser()


class ActiveBehaviorRegistry:
    """Register and safely signal one foreground real behavior process."""

    def __init__(self, path: str | Path = DEFAULT_ACTIVE_BEHAVIOR_FILE) -> None:
        self._path = Path(path).expanduser()

    def register(self, behavior: str) -> None:
        """Write the current PID and Linux start token without silent takeover."""
        existing = self.read()
        if existing is not None and self._is_same_process(existing):
            raise RuntimeError(f"another real behavior is active: {existing['behavior']}")
        payload = {
            "schema_version": 1,
            "pid": os.getpid(),
            "start_token": _process_start_token(os.getpid()),
            "behavior": behavior,
        }
        self._write(payload)

    def clear(self) -> None:
        """Remove registration only when it still belongs to this process."""
        existing = self.read()
        if (
            existing is not None
            and existing.get("pid") == os.getpid()
            and existing.get("start_token") == _process_start_token(os.getpid())
        ):
            self._path.unlink(missing_ok=True)

    def request_stop(self) -> bool:
        """Send SIGINT only when PID and process-start token still match."""
        existing = self.read()
        if existing is None:
            return False
        if not self._is_same_process(existing):
            self._path.unlink(missing_ok=True)
            return False
        os.kill(int(existing["pid"]), signal.SIGINT)
        return True

    def read(self) -> dict[str, Any] | None:
        """Return validated registration or None."""
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or not isinstance(payload.get("pid"), int)
            or not isinstance(payload.get("start_token"), str)
            or not isinstance(payload.get("behavior"), str)
        ):
            return None
        return payload

    def _is_same_process(self, payload: dict[str, Any]) -> bool:
        pid = int(payload["pid"])
        try:
            return str(payload["start_token"]) == _process_start_token(pid)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            return False

    def _write(self, payload: dict[str, Any]) -> None:
        directory = self._path.parent
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".active-",
            suffix=".tmp",
            dir=directory,
            text=True,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
            self._path.chmod(0o600)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise


def _process_start_token(pid: int) -> str:
    stat_path = Path("/proc") / str(pid) / "stat"
    content = stat_path.read_text(encoding="utf-8")
    _prefix, separator, suffix = content.rpartition(") ")
    if not separator:
        raise ProcessLookupError(f"unable to read process start token for PID {pid}")
    fields_after_name = suffix.split()
    if len(fields_after_name) < 20:
        raise ProcessLookupError(f"unable to read process start token for PID {pid}")
    return fields_after_name[19]
