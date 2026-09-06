from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class LockError(RuntimeError):
    """Raised when another write operation holds the project lock."""


class ProjectLock:
    def __init__(self, root: Path) -> None:
        self.path = root / ".llmwiki" / "lock"
        self._held = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            owner = self.path.read_text(encoding="utf-8", errors="replace") if self.path.exists() else "unknown"
            raise LockError(f"Another write operation holds {self.path}: {owner}") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        self._held = True

    def release(self) -> None:
        if self._held:
            self.path.unlink(missing_ok=True)
            self._held = False

    def __enter__(self) -> "ProjectLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
