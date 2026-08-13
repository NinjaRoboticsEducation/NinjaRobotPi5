"""Optional ngrok lifecycle with offline boot, sanitized status, and pairing."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import stat
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol, cast

from ninjarobot_pi5_ide import RemoteAccessConfig, load_robot_config, save_robot_config

from .events import AgentEventType, EventBroker
from .pairing import (
    REMOTE_MARKER_HEADER,
    PairingSessionManager,
    validate_public_https_origin,
)
from .release_foundations import ReleaseFeatureState, ReleaseStatusRegistry
from .secrets import SecretStore

PersistRemoteSetting = Callable[[bool], Awaitable[None]]
StartWebServer = Callable[[], Awaitable[dict[str, object]]]


class RemoteAccessError(RuntimeError):
    """A safe stable category for tunnel failures; provider bodies are omitted."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RemoteTunnelBackend(Protocol):
    """Minimal fakeable lifecycle around the pyngrok-owned process."""

    async def connect(self) -> str: ...

    async def healthy(self, public_url: str) -> bool: ...

    async def close(self, public_url: str | None) -> None: ...


class PyngrokTunnelBackend:
    """Own one exact pyngrok config, endpoint, and ngrok child process."""

    def __init__(
        self,
        *,
        config: RemoteAccessConfig,
        secrets: SecretStore,
        local_ca_certificate: str | Path,
        remote_header_secret: str,
    ) -> None:
        self._settings = config
        self._secrets = secrets
        self._ca_certificate = Path(local_ca_certificate).expanduser().resolve()
        self._remote_header_secret = remote_header_secret
        self._pyngrok_config: object | None = None

    async def connect(self) -> str:
        """Connect only when explicit setup already installed every dependency."""
        return await asyncio.to_thread(self._connect_sync)

    def _connect_sync(self) -> str:
        executable = _private_path(self._settings.executable)
        config_file = _private_path(self._settings.config_file)
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise RemoteAccessError("executable_unavailable")
        if not self._ca_certificate.is_file():
            raise RemoteAccessError("local_ca_unavailable")
        token = self._secrets.get(self._settings.authtoken_env)
        if token is None:
            raise RemoteAccessError("authtoken_unavailable")
        _write_private_ngrok_config(config_file, token=token)
        try:
            from pyngrok import conf, ngrok  # type: ignore[import-untyped]

            logging.getLogger("pyngrok").setLevel(logging.WARNING)
            pyngrok_config = conf.PyngrokConfig(
                ngrok_path=str(executable),
                config_path=str(config_file),
                auth_token=None,
                monitor_thread=True,
                startup_timeout=max(5, int(self._settings.connect_timeout_seconds)),
                request_timeout=min(10.0, self._settings.connect_timeout_seconds),
                max_logs=20,
                ngrok_version="3",
                config_version="2",
            )
            pyngrok_config.auth_token = None
            tunnel = ngrok.connect(
                addr=self._settings.local_upstream,
                proto="http",
                bind_tls=True,
                upstream_tls_verify=True,
                upstream_tls_verify_cas=str(self._ca_certificate),
                request_header_remove=[REMOTE_MARKER_HEADER],
                request_header_add=[f"{REMOTE_MARKER_HEADER}:{self._remote_header_secret}"],
                pyngrok_config=pyngrok_config,
            )
            public_url = validate_public_https_origin(str(tunnel.public_url))
        except RemoteAccessError:
            raise
        except Exception as exc:
            raise RemoteAccessError(_classify_ngrok_failure(exc)) from None
        finally:
            _write_private_ngrok_config(config_file, token=None)
        self._pyngrok_config = pyngrok_config
        return public_url

    async def healthy(self, public_url: str) -> bool:
        return await asyncio.to_thread(self._healthy_sync, public_url)

    def _healthy_sync(self, public_url: str) -> bool:
        config = self._pyngrok_config
        if config is None:
            return False
        try:
            from pyngrok import ngrok, process

            executable = str(getattr(config, "ngrok_path"))
            if not process.is_process_running(executable):
                return False
            return any(
                validate_public_https_origin(str(tunnel.public_url)) == public_url
                for tunnel in ngrok.get_tunnels(pyngrok_config=config)
            )
        except Exception:
            return False

    async def close(self, public_url: str | None) -> None:
        await asyncio.to_thread(self._close_sync, public_url)

    def _close_sync(self, public_url: str | None) -> None:
        config = self._pyngrok_config
        self._pyngrok_config = None
        if config is None:
            return
        try:
            from pyngrok import ngrok

            if public_url is not None:
                try:
                    ngrok.disconnect(public_url, pyngrok_config=config)
                except Exception:
                    pass
            ngrok.kill(pyngrok_config=config)
        except Exception:
            return


class RemoteAccessService:
    """Supervise remote connectivity without blocking local robot operation."""

    def __init__(
        self,
        *,
        backend: RemoteTunnelBackend,
        pairing: PairingSessionManager,
        events: EventBroker,
        release_status: ReleaseStatusRegistry,
        config: RemoteAccessConfig,
        start_web: StartWebServer,
        persist_enabled: PersistRemoteSetting,
    ) -> None:
        self._backend = backend
        self._pairing = pairing
        self._events = events
        self._release_status = release_status
        self._config = config
        self._start_web = start_web
        self._persist_enabled = persist_enabled
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._first_attempt = asyncio.Event()
        self._public_url: str | None = None
        self._last_error_code: str | None = None
        self._enabled = config.enabled
        self._lock = asyncio.Lock()

    async def start_configured(self) -> dict[str, object]:
        if not self._config.enabled:
            return self.status()
        return await self.activate(persist=False)

    async def activate(self, *, persist: bool = True) -> dict[str, object]:
        """Start web first, then one bounded/recovering tunnel supervisor."""
        async with self._lock:
            if self._task is not None and not self._task.done():
                return self.status()
            await self._start_web()
            if persist:
                await self._persist_enabled(True)
            self._enabled = True
            self._stop.clear()
            self._first_attempt.clear()
            self._release_status.set_enabled("remote_access", True)
            self._release_status.set_enabled("pairing", True)
            self._release_status.update(
                "remote_access",
                ReleaseFeatureState.CONNECTING,
                detail=None,
            )
            self._task = asyncio.create_task(
                self._supervise(),
                name="ninjarobot-ngrok-supervisor",
            )
        try:
            await asyncio.wait_for(
                self._first_attempt.wait(),
                timeout=self._config.connect_timeout_seconds + 1.0,
            )
        except TimeoutError:
            pass
        return self.status()

    async def deactivate(self, *, persist: bool = True) -> dict[str, object]:
        """Stop the exact endpoint/process and revoke every remote credential."""
        async with self._lock:
            task = self._task
            self._task = None
            self._enabled = False
            self._stop.set()
            if task is not None:
                task.cancel()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        public_url = self._public_url
        self._public_url = None
        await self._backend.close(public_url)
        self._pairing.clear_remote_url()
        self._release_status.set_enabled("remote_access", False)
        self._release_status.set_enabled("pairing", False)
        if persist:
            await self._persist_enabled(False)
        await self._events.publish(
            AgentEventType.REMOTE_ACCESS,
            "Remote access was disabled and all remote browser sessions were revoked.",
            data={"kind": "remote_disabled"},
        )
        return self.status()

    def status(self) -> dict[str, object]:
        """Return local-operator status without pairing fragments or provider bodies."""
        pairing = self._pairing.status()
        state = cast(
            dict[str, object],
            self._release_status.status()["remote_access"],
        )
        return {
            "enabled": self._enabled,
            "state": state["state"],
            "detail": state["detail"],
            "public_url": self._public_url,
            "pairing_available": pairing.pairing_available,
            "active_sessions": pairing.active_sessions,
        }

    def pairing_url(self) -> str:
        """Return a fragment-bearing URL only over the local owner IPC channel."""
        return self._pairing.pairing_url()

    async def rotate_pairing(self) -> dict[str, object]:
        url = self._pairing.rotate(invalidate_sessions=True)
        await self._events.publish(
            AgentEventType.PAIRING,
            "Remote browser sessions were revoked and a new pairing code was generated.",
            data={"kind": "pairing_rotated"},
        )
        return {"pairing_url": url, "sessions_revoked": True}

    async def controller_authenticated(self, remote: bool) -> None:
        """Reflect only a paired remote WebSocket, never an HTTP probe."""
        if not remote or self._public_url is None:
            return
        self._release_status.update(
            "remote_access",
            ReleaseFeatureState.CONNECTED,
            detail=None,
        )
        self._release_status.update(
            "pairing",
            ReleaseFeatureState.AUTHENTICATED,
            detail=None,
        )
        await self._events.publish(
            AgentEventType.PAIRING,
            "A paired remote browser controller connected.",
            data={"kind": "remote_controller_connected"},
        )

    async def close(self) -> None:
        await self.deactivate(persist=False)

    async def _supervise(self) -> None:
        failures = 0
        try:
            while not self._stop.is_set():
                self._release_status.update(
                    "remote_access",
                    ReleaseFeatureState.CONNECTING,
                    detail=self._last_error_code,
                )
                try:
                    public_url = await self._backend.connect()
                    self._public_url = public_url
                    self._last_error_code = None
                    self._pairing.set_remote_url(public_url)
                    self._release_status.update(
                        "remote_access",
                        ReleaseFeatureState.WAITING_FOR_CONNECTION,
                        detail=None,
                    )
                    self._release_status.update(
                        "pairing",
                        ReleaseFeatureState.PAIRING,
                        detail=None,
                    )
                    await self._events.publish(
                        AgentEventType.REMOTE_ACCESS,
                        "Secure remote access is ready and waiting for a paired browser.",
                        data={"kind": "remote_ready"},
                    )
                    failures = 0
                    self._first_attempt.set()
                    while not self._stop.is_set():
                        try:
                            await asyncio.wait_for(
                                self._stop.wait(),
                                timeout=self._config.health_interval_seconds,
                            )
                        except TimeoutError:
                            if self._public_url is not None and await self._backend.healthy(
                                self._public_url
                            ):
                                continue
                            raise RemoteAccessError("tunnel_lost") from None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    code = exc.code if isinstance(exc, RemoteAccessError) else "tunnel_unavailable"
                    self._last_error_code = code
                    self._first_attempt.set()
                    lost_url: str | None = self._public_url
                    self._public_url = None
                    self._pairing.clear_remote_url()
                    await self._backend.close(lost_url)
                    failures += 1
                    state = (
                        ReleaseFeatureState.FAILED
                        if failures > self._config.retry_limit
                        else ReleaseFeatureState.DEGRADED
                    )
                    self._release_status.update("remote_access", state, detail=code)
                    self._release_status.update("pairing", state, detail=code)
                    await self._events.publish(
                        AgentEventType.REMOTE_ACCESS,
                        "Remote access is unavailable; local agent and web control remain ready.",
                        data={"kind": "remote_error", "code": code},
                    )
                    delay = min(
                        self._config.retry_initial_seconds * (2 ** min(failures - 1, 16)),
                        self._config.retry_max_seconds,
                    )
                    if failures > self._config.retry_limit:
                        failures = 0
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=delay)
                    except TimeoutError:
                        continue
        finally:
            self._first_attempt.set()


async def persist_remote_access_enabled(config_path: str | Path, enabled: bool) -> None:
    await asyncio.to_thread(_persist_remote_access_enabled, config_path, enabled)


def _persist_remote_access_enabled(config_path: str | Path, enabled: bool) -> None:
    config = load_robot_config(config_path)
    payload = config.model_dump(mode="python")
    payload["remote_access"]["enabled"] = enabled
    save_robot_config(type(config).model_validate(payload), config_path, overwrite=True)


def install_ngrok_binary(path: str | Path) -> Path:
    """Explicit setup-only download; the unattended service never calls this."""
    try:
        destination = _private_path(path)
    except RemoteAccessError as exc:
        raise ValueError("ngrok executable path must not use symbolic links") from exc
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    from pyngrok import installer

    installer.install_ngrok(str(destination), ngrok_version="3")
    if not destination.is_file():
        raise RuntimeError("ngrok installation did not produce an executable")
    os.chmod(destination, 0o700)
    return destination


def _ensure_private_ngrok_config(path: Path) -> None:
    path = _private_path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise RemoteAccessError("config_path_unsafe")
    if path.exists():
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
            raise RemoteAccessError("config_path_unsafe")
        return
    _write_private_ngrok_config(path, token=None)


def _write_private_ngrok_config(path: Path, *, token: str | None) -> None:
    """Atomically write the private agent config; token use is startup-transient."""
    path = _private_path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise RemoteAccessError("config_path_unsafe")
    if path.exists():
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
            raise RemoteAccessError("config_path_unsafe")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}-",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write('version: "2"\nupdate_check: false\nweb_addr: 127.0.0.1:4041\n')
            if token is not None:
                handle.write(f"authtoken: {json.dumps(token)}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def _classify_ngrok_failure(error: Exception) -> str:
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    if "auth" in name or "authtoken" in message or "authentication" in message:
        return "authentication_failed"
    if "account" in message or "limit" in message or "quota" in message:
        return "account_rejected"
    if "config" in name or "config" in message or "yaml" in message:
        return "configuration_invalid"
    if any(word in message for word in ("network", "resolve", "timeout", "connection")):
        return "network_unavailable"
    return "tunnel_unavailable"


def _private_path(path: str | Path) -> Path:
    candidate = Path(os.path.abspath(Path(path).expanduser()))
    current = candidate
    while True:
        if current.is_symlink():
            raise RemoteAccessError("config_path_unsafe")
        if current.parent == current:
            return candidate
        current = current.parent
