"""Owner-private agent secret storage with environment override support."""

from __future__ import annotations

import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_BUILT_IN_SENSITIVE_NAMES = {
    "NGROK_AUTHTOKEN",
    "NINJAROBOT_PAIRING_SECRET",
    "NINJAROBOT_SESSION_SECRET",
    "NINJAROBOT_REMOTE_HEADER_SECRET",
}


class SecretStore:
    """Resolve secrets without placing values in ordinary configuration."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()
        self._resolved_names: set[str] = set()

    @property
    def path(self) -> Path:
        """Return the expanded secret-file path."""
        return self._path

    def set(self, name: str, value: str) -> None:
        """Atomically save one secret with owner-only permissions."""
        _validate_name(name)
        if not value or "\n" in value or "\r" in value or "\x00" in value:
            raise ValueError("secret values must be non-empty single-line text")
        stored = self._read_file()
        stored[name] = value
        self._resolved_names.add(name)
        self._write_file(stored)

    def get(self, name: str) -> str | None:
        """Resolve the process environment first, then the owner secret file."""
        _validate_name(name)
        self._resolved_names.add(name)
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
        self._write_file(secrets)
        return True

    def redact(self, value: Any) -> Any:
        """Recursively replace known secret values in diagnostics."""
        stored = self._read_file()
        names = set(stored) | self._resolved_names | _BUILT_IN_SENSITIVE_NAMES
        known = tuple(
            dict.fromkeys(
                secret_value
                for name in names
                if (secret_value := os.environ.get(name) or stored.get(name))
            )
        )
        return _redact_value(value, known)

    def _read_file(self) -> dict[str, str]:
        if self._path.is_symlink():
            raise ValueError("secret storage file must not be a symbolic link")
        if not self._path.exists():
            return {}
        self._validate_private_path(for_write=False)
        secrets: dict[str, str] = {}
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if separator and _NAME_PATTERN.fullmatch(name):
                secrets[name] = value
        return secrets

    def _write_file(self, secrets: dict[str, str]) -> None:
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._validate_private_path(for_write=True)
        self._path.parent.chmod(0o700)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self._path.name}-",
            suffix=".tmp",
            dir=self._path.parent,
            text=True,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            body = "".join(f"{key}={secrets[key]}\n" for key in sorted(secrets))
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
            self._path.chmod(0o600)
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
            raise

    def _validate_private_path(self, *, for_write: bool) -> None:
        parent = self._path.parent
        if parent.is_symlink() or parent.resolve() != parent.absolute():
            raise ValueError("secret storage directory must not be a symbolic link")
        if self._path.is_symlink():
            raise ValueError("secret storage file must not be a symbolic link")
        if self._path.exists():
            mode = self._path.stat().st_mode
            if not stat.S_ISREG(mode):
                raise ValueError("secret storage path must be a regular file")
            if not for_write and stat.S_IMODE(mode) & 0o077:
                raise ValueError("secret storage file permissions must be owner-only")


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
