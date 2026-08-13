"""Short-lived, passwordless browser pairing for optional remote access."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

PAIRING_FRAGMENT_KEY = "pair"
SESSION_COOKIE_NAME = "ninjarobot_session"
REMOTE_MARKER_HEADER = "x-ninjarobot-remote"
TOKEN_BYTES = 32
MAX_PAIRING_TOKEN_LENGTH = 128


class PairingError(PermissionError):
    """A pairing credential was missing, expired, replayed, or malformed."""


@dataclass(frozen=True, slots=True)
class PairingStatus:
    """Credential-free status safe for runtime and interface reporting."""

    remote_origin_configured: bool
    pairing_available: bool
    active_sessions: int
    active_scope: str | None


class PairingSessionManager:
    """Issue one-use fragment tokens and revocable HttpOnly browser sessions."""

    def __init__(
        self,
        *,
        pairing_secret: bytes,
        session_secret: bytes,
        remote_header_secret: str,
        pairing_lifetime_seconds: int,
        session_lifetime_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if len(pairing_secret) < 32 or len(session_secret) < 32:
            raise ValueError("pairing and session secrets must contain at least 32 bytes")
        if not _valid_token(remote_header_secret):
            raise ValueError("remote header secret must be a URL-safe random token")
        if not 60 <= pairing_lifetime_seconds <= 900:
            raise ValueError("pairing lifetime must be from 60 through 900 seconds")
        if not 300 <= session_lifetime_seconds <= 2_592_000:
            raise ValueError("session lifetime must be from 300 through 2592000 seconds")
        self._pairing_secret = pairing_secret
        self._session_secret = session_secret
        self._remote_header_secret = remote_header_secret
        self._pairing_lifetime = pairing_lifetime_seconds
        self._session_lifetime = session_lifetime_seconds
        self._clock = clock
        self._remote_origin: str | None = None
        self._pairing_origin: str | None = None
        self._pairing_scope: str | None = None
        self._pending_hash: bytes | None = None
        self._pending_raw: str | None = None
        self._pending_expires = 0.0
        self._sessions: dict[bytes, float] = {}

    @property
    def session_lifetime_seconds(self) -> int:
        return self._session_lifetime

    @property
    def pairing_lifetime_seconds(self) -> int:
        return self._pairing_lifetime

    def set_remote_url(self, public_url: str) -> None:
        """Bind future pairing and sessions to one exact validated HTTPS origin."""
        origin = validate_public_https_origin(public_url)
        self._remote_origin = origin
        self._set_endpoint(origin, scope="remote")

    def set_local_url(self, local_url: str) -> None:
        """Bind physical-presence pairing to one exact local HTTPS origin."""
        self._remote_origin = None
        self._set_endpoint(validate_local_https_origin(local_url), scope="local")

    def clear_remote_url(self) -> None:
        """Invalidate every remote credential when a tunnel is removed or replaced."""
        self._remote_origin = None
        if self._pairing_scope != "remote":
            return
        self.clear_endpoint()

    def clear_endpoint(self) -> None:
        """Invalidate the current endpoint, pending code, and browser sessions."""
        self._pairing_origin = None
        self._pairing_scope = None
        self._pending_hash = None
        self._pending_raw = None
        self._pending_expires = 0.0
        self._sessions.clear()

    def rotate(self, *, invalidate_sessions: bool = True) -> str:
        """Issue a fresh one-use token and optionally revoke every browser session."""
        if self._pairing_origin is None:
            raise PairingError("pairing endpoint is not ready")
        raw = secrets.token_urlsafe(TOKEN_BYTES)
        self._pending_hash = self._digest(self._pairing_secret, raw)
        self._pending_raw = raw
        self._pending_expires = self._clock() + self._pairing_lifetime
        if invalidate_sessions:
            self._sessions.clear()
        return self.pairing_url()

    def pairing_url(self) -> str:
        """Return the local-operator/QR-only URL containing the fragment token."""
        if (
            self._pairing_origin is None
            or self._pending_raw is None
            or self._pending_hash is None
            or self._clock() >= self._pending_expires
        ):
            raise PairingError("no current pairing code is available")
        return f"{self._pairing_origin}/#{PAIRING_FRAGMENT_KEY}={self._pending_raw}"

    def exchange(
        self,
        token: str,
        *,
        origin: str | None,
        host: str,
        remote_marker: str | None,
    ) -> str:
        """Consume one exact fragment token and return a new opaque session token."""
        self._require_endpoint_request(
            origin=origin,
            host=host,
            remote_marker=remote_marker,
            require_origin=True,
        )
        if not _valid_token(token):
            raise PairingError("pairing token is malformed")
        now = self._clock()
        pending = self._pending_hash
        if pending is None or now >= self._pending_expires:
            self._pending_hash = None
            self._pending_raw = None
            raise PairingError("pairing token is expired or unavailable")
        supplied = self._digest(self._pairing_secret, token)
        if not hmac.compare_digest(pending, supplied):
            raise PairingError("pairing token is invalid")
        self._pending_hash = None
        self._pending_raw = None
        self._pending_expires = 0.0
        session = secrets.token_urlsafe(TOKEN_BYTES)
        self._sessions[self._digest(self._session_secret, session)] = now + self._session_lifetime
        return session

    def authorize_remote(
        self,
        session: str | None,
        *,
        origin: str | None,
        host: str,
        remote_marker: str | None,
        require_origin: bool = True,
    ) -> bool:
        """Validate a remote cookie and same-origin browser request."""
        if require_origin:
            self._require_remote_request(
                origin=origin,
                host=host,
                remote_marker=remote_marker,
            )
        elif self.request_scope(host, remote_marker=remote_marker) != "remote":
            raise PairingError("request did not use the active remote endpoint")
        if session is None or not _valid_token(session):
            return False
        self._prune()
        digest = self._digest(self._session_secret, session)
        expiry = self._sessions.get(digest)
        return expiry is not None and self._clock() < expiry

    def authorize_controller(
        self,
        session: str | None,
        *,
        origin: str | None,
        host: str,
        remote_marker: str | None,
        require_origin: bool = True,
    ) -> bool:
        """Validate a browser session against the currently displayed endpoint."""
        self._require_endpoint_request(
            origin=origin,
            host=host,
            remote_marker=remote_marker,
            require_origin=require_origin,
        )
        if session is None or not _valid_token(session):
            return False
        self._prune()
        expiry = self._sessions.get(self._digest(self._session_secret, session))
        return expiry is not None and self._clock() < expiry

    def request_scope(self, host: str, *, remote_marker: str | None = None) -> str:
        """Classify a Host header as local, the active remote endpoint, or denied."""
        hostname, port = _host_parts(host)
        if remote_marker is not None:
            if not hmac.compare_digest(remote_marker, self._remote_header_secret):
                return "denied"
            if (
                self._remote_origin is not None
                and hostname == urlsplit(self._remote_origin).hostname
                and port in {None, 443}
            ):
                return "remote"
            return "denied"
        if _is_local_hostname(hostname):
            return "local"
        return "denied"

    def revoke_all(self) -> None:
        """Invalidate pending and completed browser credentials."""
        self._pending_hash = None
        self._pending_raw = None
        self._pending_expires = 0.0
        self._sessions.clear()

    def status(self) -> PairingStatus:
        """Return counts and booleans without a URL, token, cookie, or expiry."""
        self._prune()
        return PairingStatus(
            remote_origin_configured=self._remote_origin is not None,
            pairing_available=(
                self._pending_hash is not None and self._clock() < self._pending_expires
            ),
            active_sessions=len(self._sessions),
            active_scope=self._pairing_scope,
        )

    def _set_endpoint(self, origin: str, *, scope: str) -> None:
        self._pairing_origin = origin
        self._pairing_scope = scope
        self.rotate(invalidate_sessions=True)

    def _require_endpoint_request(
        self,
        *,
        origin: str | None,
        host: str,
        remote_marker: str | None,
        require_origin: bool,
    ) -> None:
        expected_origin = self._pairing_origin
        expected_scope = self._pairing_scope
        if expected_origin is None or expected_scope is None:
            raise PairingError("pairing endpoint is not ready")
        if self.request_scope(host, remote_marker=remote_marker) != expected_scope:
            raise PairingError("request did not use the active pairing endpoint")
        if require_origin and origin != expected_origin:
            raise PairingError("pairing request origin does not match")

    def _require_remote_request(
        self,
        *,
        origin: str | None,
        host: str,
        remote_marker: str | None,
    ) -> None:
        if self.request_scope(host, remote_marker=remote_marker) != "remote":
            raise PairingError("request did not use the active remote endpoint")
        if origin != self._remote_origin:
            raise PairingError("remote request origin does not match")

    def _prune(self) -> None:
        now = self._clock()
        self._sessions = {
            token_hash: expiry for token_hash, expiry in self._sessions.items() if expiry > now
        }
        if self._pending_hash is not None and now >= self._pending_expires:
            self._pending_hash = None
            self._pending_raw = None
            self._pending_expires = 0.0

    @staticmethod
    def _digest(key: bytes, value: str) -> bytes:
        return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def validate_public_https_origin(public_url: str) -> str:
    """Return a bounded origin or reject paths, credentials, fragments, and HTTP."""
    if len(public_url) > 512:
        raise ValueError("remote URL exceeds 512 characters")
    parsed = urlsplit(public_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.port not in {None, 443}
    ):
        raise ValueError("remote URL must be one plain HTTPS origin")
    hostname = parsed.hostname.encode("idna").decode("ascii").lower()
    if len(hostname) > 253 or "." not in hostname or _is_local_hostname(hostname):
        raise ValueError("remote URL hostname is not a public DNS name")
    return f"https://{hostname}"


def validate_local_https_origin(local_url: str) -> str:
    """Return one plain local HTTPS origin with an optional bounded port."""
    if len(local_url) > 512:
        raise ValueError("local URL exceeds 512 characters")
    parsed = urlsplit(local_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("local URL must be one plain HTTPS origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("local URL port is invalid") from exc
    hostname = parsed.hostname.encode("idna").decode("ascii").lower()
    if not _is_local_hostname(hostname):
        raise ValueError("local URL hostname is not local")
    rendered_host = f"[{hostname}]" if ":" in hostname else hostname
    return f"https://{rendered_host}{f':{port}' if port is not None else ''}"


def _valid_token(value: str) -> bool:
    return 32 <= len(value) <= MAX_PAIRING_TOKEN_LENGTH and all(
        character.isalnum() or character in "-_" for character in value
    )


def _host_parts(host: str) -> tuple[str, int | None]:
    if not host or len(host) > 512 or any(character.isspace() for character in host):
        raise PairingError("request host is malformed")
    parsed = urlsplit(f"//{host}")
    if parsed.hostname is None or parsed.username is not None or parsed.password is not None:
        raise PairingError("request host is malformed")
    try:
        port = parsed.port
    except ValueError as exc:
        raise PairingError("request host is malformed") from exc
    return parsed.hostname.encode("idna").decode("ascii").lower(), port


def _is_local_hostname(hostname: str) -> bool:
    fixed = {
        "localhost",
        socket.gethostname().rstrip(".").lower(),
        f"{socket.gethostname().rstrip('.').lower()}.local",
    }
    if hostname in fixed or hostname.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local
