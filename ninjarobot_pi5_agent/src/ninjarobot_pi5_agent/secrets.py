"""Owner-private agent secret storage with environment override support."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


class SecretStore:
    """Resolve secrets without placing values in ordinary configuration."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()

    @property
    def path(self) -> Path:
        """Return the expanded secret-file path."""
        return self._path

    def set(self, name: str, value: str) -> None:
        """Atomically save one secret with owner-only permissions."""
        _validate_name(name)
        if not value or "\n" in value or "\r" in value or "\x00" in value:
            raise ValueError("secret values must be non-empty single-line text")
        secrets = self._read_file()
        secrets[name] = value
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._path.parent.chmod(0o700)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        body = "".join(f"{key}={secrets[key]}\n" for key in sorted(secrets))
        temporary.write_text(body, encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self._path)
        self._path.chmod(0o600)

    def get(self, name: str) -> str | None:
        """Resolve the process environment first, then the owner secret file."""
        _validate_name(name)
        environment_value = os.environ.get(name)
        if environment_value:
            return environment_value
        return self._read_file().get(name)

    def require(self, name: str) -> str:
        """Resolve a secret or raise an error that never contains its value."""
        value = self.get(name)
        if value is None:
            raise KeyError(f"required secret is not configured: {name}")
        return value

    def contains(self, name: str) -> bool:
        """Report whether a secret resolves without revealing its value."""
        return self.get(name) is not None

    def delete(self, name: str) -> bool:
        """Remove one file-backed secret without changing the process environment."""
        _validate_name(name)
        secrets = self._read_file()
        if name not in secrets:
            return False
        secrets.pop(name)
        if not secrets:
            self._path.unlink(missing_ok=True)
            return True
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        body = "".join(f"{key}={secrets[key]}\n" for key in sorted(secrets))
        temporary.write_text(body, encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self._path)
        self._path.chmod(0o600)
        return True

    def redact(self, value: Any) -> Any:
        """Recursively replace known secret values in diagnostics."""
        known = tuple(secret for secret in self._read_file().values() if secret)
        return _redact_value(value, known)

    def _read_file(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        secrets: dict[str, str] = {}
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if separator and _NAME_PATTERN.fullmatch(name):
                secrets[name] = value
        return secrets


def _validate_name(name: str) -> None:
    if _NAME_PATTERN.fullmatch(name) is None:
        raise ValueError("secret names must use uppercase letters, digits, and underscores")


def _redact_value(value: Any, known: tuple[str, ...]) -> Any:
    if isinstance(value, str):
        redacted = value
        for secret in known:
            redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    if isinstance(value, dict):
        return {key: _redact_value(item, known) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, known) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item, known) for item in value)
    return value
