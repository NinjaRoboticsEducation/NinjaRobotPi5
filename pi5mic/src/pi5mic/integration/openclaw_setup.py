"""OpenClaw autodiscovery and readiness helpers for pi5mic."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pi5mic.errors import IntegrationError, TransportError
from pi5mic.integration.openclaw_session import (
    DEFAULT_OPENCLAW_SESSION_ID,
    normalize_openclaw_session_id,
)
from pi5mic.integration.presence import OpenClawPresenceController
from pi5mic.transport.openclaw_cli import (
    build_gateway_cli_args,
    parse_json_output,
    resolve_openclaw_command,
)

DEFAULT_OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_GATEWAY_URL = "ws://127.0.0.1:18789"
DEFAULT_AGENT_ID = "main"
DEFAULT_SESSION_KEY = DEFAULT_OPENCLAW_SESSION_ID


@dataclass(frozen=True, slots=True)
class OpenClawReplyTarget:
    """A concrete outbound reply target that pi5mic can hand back to OpenClaw."""

    channel: str
    target: str
    account_id: str | None = None
    source_session_key: str | None = None
    updated_at: int | None = None
    source: str = "saved"

    def describe(self) -> str:
        """Return a short user-facing description of the reply target."""
        parts = [f"{self.channel}:{self.target}"]
        if self.account_id:
            parts.append(f"account={self.account_id}")
        if self.source_session_key:
            parts.append(f"session={self.source_session_key}")
        if self.source:
            parts.append(f"source={self.source}")
        return " | ".join(parts)


@dataclass(frozen=True, slots=True)
class OpenClawAutoConfig:
    """Detected OpenClaw settings that pi5mic can reuse."""

    command: Path
    config_path: Path | None
    gateway_url: str
    agent_id: str
    session_key: str
    gateway_mode: str
    gateway_bind: str | None
    plugin_enabled: bool
    plugin_allowlisted: bool
    plugin_install_found: bool
    telegram_enabled: bool
    telegram_accounts: tuple[str, ...]
    telegram_default_account: str | None
    telegram_reply_target: OpenClawReplyTarget | None
    telegram_reply_target_error: str | None = None
    used_defaults: tuple[str, ...] = ()

    @property
    def plugin_ready(self) -> bool:
        """Return True when the NinjaClawBot plugin looks configured."""
        return self.plugin_enabled and self.plugin_allowlisted and self.plugin_install_found


@dataclass(frozen=True, slots=True)
class OpenClawVoiceReadyReport:
    """Result of a safe OpenClaw voice-path readiness probe."""

    ok_lines: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def get_openclaw_config_path(command: str | Path | None = None) -> Path | None:
    """Return the local OpenClaw config file path when it can be located."""
    if DEFAULT_OPENCLAW_CONFIG_PATH.is_file():
        return DEFAULT_OPENCLAW_CONFIG_PATH

    resolved_command = resolve_openclaw_command(command)
    try:
        result = subprocess.run(
            [str(resolved_command), "config", "file"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    candidate = Path(result.stdout.strip()).expanduser()
    return candidate if candidate.is_file() else None


def discover_openclaw_auto_config(
    *,
    command: str | Path | None,
    saved_gateway_url: str | None = None,
    saved_agent_id: str | None = None,
    saved_session_key: str | None = None,
    saved_reply_channel: str | None = None,
    saved_reply_to: str | None = None,
    saved_reply_account: str | None = None,
) -> OpenClawAutoConfig:
    """Read the local OpenClaw config and derive a ready-to-use pi5mic profile."""
    resolved_command = resolve_openclaw_command(command)
    config_path = get_openclaw_config_path(resolved_command)
    payload: dict[str, Any] = {}
    used_defaults: list[str] = []

    if config_path is not None:
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except json.JSONDecodeError as exc:
            raise TransportError(f"OpenClaw config file is not valid JSON: {config_path}") from exc
        except OSError as exc:
            raise TransportError(f"Could not read OpenClaw config file: {config_path}") from exc
        if isinstance(loaded, dict):
            payload = loaded
        else:
            raise TransportError(f"OpenClaw config file must contain an object: {config_path}")
    else:
        used_defaults.append("config_path")

    gateway = payload.get("gateway")
    gateway_config = gateway if isinstance(gateway, dict) else {}
    gateway_mode = str(gateway_config.get("mode", "local"))
    gateway_bind = gateway_config.get("bind")
    gateway_url = _detect_gateway_url(
        gateway_config,
        fallback=saved_gateway_url or DEFAULT_GATEWAY_URL,
    )
    if not gateway_config:
        used_defaults.append("gateway_url")

    agent_id = _detect_agent_id(payload) or saved_agent_id or DEFAULT_AGENT_ID
    if _detect_agent_id(payload) is None:
        used_defaults.append("agent_id")

    session_key = normalize_openclaw_session_id(saved_session_key or DEFAULT_SESSION_KEY)
    if not saved_session_key:
        used_defaults.append("session_key")

    plugin_enabled, plugin_allowlisted, plugin_install_found = _detect_plugin_state(payload)
    telegram_enabled, telegram_accounts, telegram_default_account = _detect_telegram_state(payload)
    telegram_reply_target, telegram_reply_target_error = _discover_telegram_reply_target(
        command=resolved_command,
        gateway_url=gateway_url,
        agent_id=agent_id,
        telegram_enabled=telegram_enabled,
        saved_reply_channel=saved_reply_channel,
        saved_reply_to=saved_reply_to,
        saved_reply_account=saved_reply_account,
    )

    return OpenClawAutoConfig(
        command=resolved_command,
        config_path=config_path,
        gateway_url=gateway_url,
        agent_id=agent_id,
        session_key=session_key,
        gateway_mode=gateway_mode,
        gateway_bind=str(gateway_bind).strip() if gateway_bind is not None else None,
        plugin_enabled=plugin_enabled,
        plugin_allowlisted=plugin_allowlisted,
        plugin_install_found=plugin_install_found,
        telegram_enabled=telegram_enabled,
        telegram_accounts=telegram_accounts,
        telegram_default_account=telegram_default_account,
        telegram_reply_target=telegram_reply_target,
        telegram_reply_target_error=telegram_reply_target_error,
        used_defaults=tuple(dict.fromkeys(used_defaults)),
    )


def summarize_openclaw_auto_config(discovery: OpenClawAutoConfig) -> list[str]:
    """Return concise user-facing lines describing detected OpenClaw settings."""
    config_display = (
        str(discovery.config_path) if discovery.config_path is not None else "not found"
    )
    plugin_state = "ready" if discovery.plugin_ready else "needs attention"
    lines = [
        f"OpenClaw CLI: {discovery.command}",
        f"OpenClaw config file: {config_display}",
        f"Gateway URL: {discovery.gateway_url}",
        f"Agent id: {discovery.agent_id}",
        f"Session key: {discovery.session_key}",
        f"Gateway mode: {discovery.gateway_mode}",
        f"NinjaClawBot plugin: {plugin_state}",
    ]
    if discovery.telegram_enabled:
        accounts = (
            ", ".join(discovery.telegram_accounts) if discovery.telegram_accounts else "default"
        )
        lines.append(f"Telegram channel: enabled ({accounts})")
        if discovery.telegram_reply_target is not None:
            lines.append("Telegram reply target: " + discovery.telegram_reply_target.describe())
        else:
            lines.append("Telegram reply target: not detected yet")
    else:
        lines.append("Telegram channel: not enabled in OpenClaw config")
    if discovery.used_defaults:
        lines.append("Defaults used for: " + ", ".join(discovery.used_defaults))
    return lines


def is_pairing_required_error(message: str) -> bool:
    """Return True when the error text clearly indicates OpenClaw pairing is required."""
    return "pairing required" in message.lower()


def explain_openclaw_error(message: str) -> str:
    """Add user-facing recovery guidance for common OpenClaw failures."""
    normalized = message.lower()
    if is_pairing_required_error(message):
        return (
            f"{message} OpenClaw is asking for a one-time local device approval. "
            "Run `openclaw devices approve --latest`, or rerun `uv run pi5mic setup` "
            "and let pi5mic approve the newest local request for you."
        )

    if "method not found" in normalized or "unknown method" in normalized:
        return (
            f"{message} The NinjaClawBot plugin presence method is not available. "
            "Confirm the `ninjaclawbot` plugin is installed and enabled, then run "
            "`openclaw gateway restart` and rerun `uv run pi5mic setup`."
        )

    if "connection refused" in normalized or "econnrefused" in normalized:
        return (
            f"{message} The OpenClaw gateway does not appear to be running. Start it with "
            "`openclaw gateway start`, then rerun `uv run pi5mic setup` or "
            "`uv run pi5mic doctor`."
        )

    if "gateway connect failed" in normalized or "gateway closed" in normalized:
        return (
            f"{message} The OpenClaw gateway accepted the CLI but did not complete the "
            "request successfully. Check `openclaw gateway status`, then rerun "
            "`uv run pi5mic setup`."
        )

    if "agent" in normalized and "not found" in normalized:
        return (
            f"{message} The configured OpenClaw agent id does not exist. Check "
            "`openclaw config get agents.list` and rerun `uv run pi5mic setup`."
        )

    if "unknown channel" in normalized or "delivery channel is required" in normalized:
        return (
            f"{message} pi5mic could not determine a Telegram reply target for this voice session. "
            "Send one short Telegram message to your OpenClaw bot, then rerun "
            "`uv run pi5mic setup` so pi5mic can reuse that Telegram route automatically."
        )

    return message


def approve_latest_openclaw_pairing(command: str | Path | None) -> str:
    """Approve the newest pending OpenClaw device request for the local gateway."""
    resolved_command = resolve_openclaw_command(command)
    try:
        result = subprocess.run(
            [str(resolved_command), "devices", "approve", "--latest"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise IntegrationError(
            "Timed out while approving the latest OpenClaw device request."
        ) from exc
    except OSError as exc:
        raise IntegrationError(f"Could not start the OpenClaw CLI: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise IntegrationError("Could not approve the latest OpenClaw device request: " + stderr)
    return result.stdout.strip() or "Approved the latest OpenClaw device request."


def probe_openclaw_voice_ready(
    *,
    command: str | Path | None,
    gateway_url: str | None,
    check_presence: bool = True,
) -> OpenClawVoiceReadyReport:
    """Verify that the gateway is reachable and optionally probe the presence method."""
    resolved_command = resolve_openclaw_command(command)
    health_command = [str(resolved_command), "gateway", "health", "--json"]
    health_command.extend(build_gateway_cli_args(gateway_url))

    try:
        result = subprocess.run(
            health_command,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise TransportError("OpenClaw gateway health check timed out.") from exc
    except OSError as exc:
        raise TransportError(f"Could not start the OpenClaw CLI: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise TransportError(
            explain_openclaw_error("OpenClaw gateway health check failed: " + stderr)
        )

    lines = ["OpenClaw gateway responded."]
    if not check_presence:
        return OpenClawVoiceReadyReport(ok_lines=tuple(lines))

    controller = OpenClawPresenceController(command=resolved_command, gateway_url=gateway_url)
    try:
        controller.set_mode("idle", reason="pi5mic.openclaw.check")
    except IntegrationError as exc:
        message = explain_openclaw_error(str(exc))
        if is_pairing_required_error(message):
            raise IntegrationError(message) from exc
        return OpenClawVoiceReadyReport(
            ok_lines=tuple(lines),
            warnings=(
                "OpenClaw presence updates are not ready right now. Voice handoff can still "
                "work, but robot presence changes will be skipped until the plugin bridge "
                "responds again.",
                message,
            ),
        )

    lines.append("NinjaClawBot presence method responded.")
    return OpenClawVoiceReadyReport(ok_lines=tuple(lines))


def _detect_gateway_url(gateway_config: dict[str, Any], *, fallback: str) -> str:
    remote = gateway_config.get("remote")
    remote_config = remote if isinstance(remote, dict) else {}
    gateway_mode = str(gateway_config.get("mode", "local")).strip().lower()

    if gateway_mode == "remote":
        remote_url = remote_config.get("url")
        if isinstance(remote_url, str) and remote_url.strip():
            return remote_url.strip()

    port = gateway_config.get("port", 18789)
    try:
        port_value = int(port)
    except (TypeError, ValueError):
        return fallback
    return f"ws://127.0.0.1:{port_value}"


def _detect_agent_id(payload: dict[str, Any]) -> str | None:
    agents = payload.get("agents")
    agents_config = agents if isinstance(agents, dict) else {}
    agent_list = agents_config.get("list")
    if not isinstance(agent_list, list):
        return None

    explicit_main = next(
        (
            item
            for item in agent_list
            if isinstance(item, dict) and str(item.get("id", "")).strip() == "main"
        ),
        None,
    )
    if explicit_main is not None:
        return "main"

    first_agent = next(
        (
            str(item.get("id", "")).strip()
            for item in agent_list
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        ),
        None,
    )
    return first_agent or None


def _detect_plugin_state(payload: dict[str, Any]) -> tuple[bool, bool, bool]:
    plugins = payload.get("plugins")
    plugins_config = plugins if isinstance(plugins, dict) else {}

    allow = plugins_config.get("allow")
    allowlist = allow if isinstance(allow, list) else []
    plugin_allowlisted = "ninjaclawbot" in allowlist

    entries = plugins_config.get("entries")
    entries_config = entries if isinstance(entries, dict) else {}
    entry = entries_config.get("ninjaclawbot")
    entry_config = entry if isinstance(entry, dict) else {}
    plugin_enabled = bool(entry_config.get("enabled", False))

    load = plugins_config.get("load")
    load_config = load if isinstance(load, dict) else {}
    paths = load_config.get("paths")
    load_paths = paths if isinstance(paths, list) else []
    path_found = any("ninjaclawbot" in str(item).lower() for item in load_paths)

    installs = plugins_config.get("installs")
    install_config = installs if isinstance(installs, dict) else {}
    plugin_install_found = path_found or "ninjaclawbot" in install_config

    return plugin_enabled, plugin_allowlisted, plugin_install_found


def _detect_telegram_state(payload: dict[str, Any]) -> tuple[bool, tuple[str, ...], str | None]:
    channels = payload.get("channels")
    channels_config = channels if isinstance(channels, dict) else {}

    telegram = channels_config.get("telegram")
    telegram_config = telegram if isinstance(telegram, dict) else {}
    enabled = bool(telegram_config.get("enabled", False))

    accounts = telegram_config.get("accounts")
    if isinstance(accounts, dict):
        account_ids = tuple(
            key.strip() for key in accounts.keys() if isinstance(key, str) and key.strip()
        )
    else:
        account_ids = ()

    bot_token = str(telegram_config.get("botToken", "")).strip()
    if bot_token and not account_ids:
        account_ids = ("default",)

    default_account = None
    if "default" in account_ids:
        default_account = "default"
    elif len(account_ids) == 1:
        default_account = account_ids[0]

    return enabled, account_ids, default_account


def _run_openclaw_json_command(
    command: list[str],
    *,
    timeout_seconds: int,
    error_prefix: str,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise TransportError(f"{error_prefix} timed out.") from exc
    except OSError as exc:
        raise TransportError(f"Could not start the OpenClaw CLI: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise TransportError(f"{error_prefix} failed: {stderr}")
    return parse_json_output(result.stdout)


def _extract_sessions_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [payload]
    result = payload.get("result")
    if isinstance(result, dict):
        candidates.append(result)

    for candidate in candidates:
        sessions = candidate.get("sessions")
        if isinstance(sessions, list):
            return [item for item in sessions if isinstance(item, dict)]
    return []


def _coerce_updated_at(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _reply_target_from_session_row(
    row: dict[str, Any],
    *,
    source: str,
) -> OpenClawReplyTarget | None:
    delivery_context = row.get("deliveryContext")
    context = delivery_context if isinstance(delivery_context, dict) else {}

    channel = str(context.get("channel") or row.get("lastChannel") or "").strip().lower()
    if channel != "telegram":
        return None

    target = str(context.get("to") or row.get("lastTo") or "").strip()
    if not target:
        return None

    account_id = str(context.get("accountId") or row.get("lastAccountId") or "").strip() or None
    source_session_key = str(row.get("key", "")).strip() or None
    updated_at = _coerce_updated_at(row.get("updatedAt"))
    return OpenClawReplyTarget(
        channel="telegram",
        target=target,
        account_id=account_id,
        source_session_key=source_session_key,
        updated_at=updated_at,
        source=source,
    )


def _pick_latest_reply_target(targets: list[OpenClawReplyTarget]) -> OpenClawReplyTarget | None:
    if not targets:
        return None
    return max(targets, key=lambda item: item.updated_at or -1)


def _discover_reply_target_via_gateway(
    *,
    command: Path,
    gateway_url: str,
    agent_id: str,
) -> OpenClawReplyTarget | None:
    payload = _run_openclaw_json_command(
        [
            str(command),
            "gateway",
            "call",
            "sessions.list",
            "--params",
            json.dumps(
                {
                    "agentId": agent_id,
                    "limit": 50,
                    "includeGlobal": False,
                    "includeUnknown": False,
                }
            ),
            *build_gateway_cli_args(gateway_url),
        ],
        timeout_seconds=20,
        error_prefix="OpenClaw sessions.list probe",
    )
    rows = _extract_sessions_from_payload(payload)
    targets = [
        target
        for row in rows
        if (target := _reply_target_from_session_row(row, source="gateway sessions.list"))
        is not None
    ]
    return _pick_latest_reply_target(targets)


def _discover_reply_target_via_sessions_cli(
    *,
    command: Path,
    agent_id: str,
) -> OpenClawReplyTarget | None:
    payload = _run_openclaw_json_command(
        [str(command), "sessions", "--agent", agent_id, "--json"],
        timeout_seconds=20,
        error_prefix="OpenClaw sessions probe",
    )
    rows = _extract_sessions_from_payload(payload)
    targets = [
        target
        for row in rows
        if (target := _reply_target_from_session_row(row, source="sessions --json")) is not None
    ]
    return _pick_latest_reply_target(targets)


def _build_saved_reply_target(
    *,
    reply_channel: str | None,
    reply_to: str | None,
    reply_account: str | None,
) -> OpenClawReplyTarget | None:
    channel = str(reply_channel or "").strip().lower()
    target = str(reply_to or "").strip()
    if channel != "telegram" or not target:
        return None
    account_id = str(reply_account or "").strip() or None
    return OpenClawReplyTarget(
        channel="telegram",
        target=target,
        account_id=account_id,
        source="saved pi5mic config",
    )


def _discover_telegram_reply_target(
    *,
    command: Path,
    gateway_url: str,
    agent_id: str,
    telegram_enabled: bool,
    saved_reply_channel: str | None,
    saved_reply_to: str | None,
    saved_reply_account: str | None,
) -> tuple[OpenClawReplyTarget | None, str | None]:
    saved_target = _build_saved_reply_target(
        reply_channel=saved_reply_channel,
        reply_to=saved_reply_to,
        reply_account=saved_reply_account,
    )
    if not telegram_enabled:
        return saved_target, None

    discovery_errors: list[str] = []
    for strategy in (
        lambda: _discover_reply_target_via_gateway(
            command=command, gateway_url=gateway_url, agent_id=agent_id
        ),
        lambda: _discover_reply_target_via_sessions_cli(command=command, agent_id=agent_id),
    ):
        try:
            target = strategy()
        except TransportError as exc:
            discovery_errors.append(str(exc))
            continue
        if target is not None:
            return target, None

    if saved_target is not None:
        return saved_target, None

    if discovery_errors:
        return None, explain_openclaw_error(discovery_errors[0])
    return None, None
