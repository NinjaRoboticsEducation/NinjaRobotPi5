"""Owner-private Google OAuth credential storage and refresh."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from .cloud_common import CloudAuthenticationError

GEMINI_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language.retriever",
)


def gemini_credential_path(secret_file: str | Path, provider_id: str) -> Path:
    """Return a confined, owner-private token path for one configured provider."""
    secret_path = Path(secret_file).expanduser()
    provider_digest = hashlib.sha256(provider_id.encode("utf-8")).hexdigest()[:16]
    return secret_path.parent / "oauth" / f"gemini-{provider_digest}.json"


def save_google_credentials(path: str | Path, credentials: Credentials) -> None:
    """Atomically save Google credentials with owner-only permissions."""
    destination = Path(path).expanduser()
    try:
        payload = json.loads(credentials.to_json())  # type: ignore[no-untyped-call]
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CloudAuthenticationError("Google returned invalid OAuth credentials") from exc
    if not isinstance(payload, dict) or not payload.get("token"):
        raise CloudAuthenticationError("Google OAuth credentials do not contain an access token")
    if not payload.get("refresh_token"):
        raise CloudAuthenticationError(
            "Google did not return a refresh token; revoke the app grant and try web login again"
        )
    if destination.parent.is_symlink():
        raise CloudAuthenticationError("refusing to use a symbolic-link OAuth directory")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.parent.chmod(0o700)
    if destination.is_symlink():
        raise CloudAuthenticationError("refusing to replace a symbolic-link OAuth credential file")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            os.fchmod(temporary.fileno(), 0o600)
            json.dump(payload, temporary, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        Path(temporary_name).replace(destination)
        destination.chmod(0o600)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class GoogleOAuthCredential:
    """Load and refresh a NinjaRobotAgent-managed Google OAuth token."""

    credential_file: Path
    scopes: tuple[str, ...] = GEMINI_SCOPES

    async def headers(self) -> dict[str, str]:
        return await asyncio.to_thread(self._headers)

    def _headers(self) -> dict[str, str]:
        path = self.credential_file.expanduser()
        if not path.is_file() or path.is_symlink():
            raise CloudAuthenticationError(
                "Gemini web-login credentials are missing; run provider login gemini"
            )
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise CloudAuthenticationError(
                "Gemini web-login credential permissions are unsafe; run chmod 600 on the file"
            )
        try:
            credentials = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
                path,
                self.scopes,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise CloudAuthenticationError(
                "Gemini web-login credentials are unreadable or invalid"
            ) from exc
        if not credentials.valid:
            if not credentials.expired or not credentials.refresh_token:
                raise CloudAuthenticationError(
                    "Gemini web-login credentials are unavailable or expired"
                )
            try:
                credentials.refresh(Request())
            except GoogleAuthError as exc:
                raise CloudAuthenticationError(
                    "Gemini web-login credentials could not be refreshed"
                ) from exc
            save_google_credentials(path, credentials)
        if not credentials.token:
            raise CloudAuthenticationError(
                "Gemini web-login credentials do not contain an access token"
            )
        return {"Authorization": f"Bearer {credentials.token}"}

    def status(self) -> dict[str, object]:
        path = self.credential_file.expanduser()
        return {
            "method": "oauth",
            "credential_store": "ninjarobot_pi5",
            "configured": path.is_file() and not path.is_symlink(),
        }
