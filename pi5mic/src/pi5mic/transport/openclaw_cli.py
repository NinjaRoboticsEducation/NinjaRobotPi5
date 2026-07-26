"""OpenClaw CLI-backed transport for pi5mic."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pi5mic.errors import TransportError
from pi5mic.integration.openclaw_session import normalize_openclaw_session_id
from pi5mic.models import DispatchResult

from .base import TextTransport

_LOCAL_GATEWAY_URLS = {
    "",
    "ws://127.0.0.1:18789",
    "ws://localhost:18789",
    "wss://127.0.0.1:18789",
    "wss://localhost:18789",
}


def normalize_gateway_url(gateway_url: str | None) -> str | None:
    """Normalize an OpenClaw gateway URL for CLI use."""
    if gateway_url is None:
        return None
    normalized = gateway_url.strip()
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://")):
        raise TransportError(
            "OpenClaw gateway URLs for pi5mic must use ws:// or wss://, not http:// or https://."
        )
    if not normalized.startswith(("ws://", "wss://")):
        raise TransportError(
            "OpenClaw gateway URL must start with ws:// or wss:// when explicitly configured."
        )
    return normalized


def find_openclaw_command(command: str | Path | None = None) -> Path | None:
    """Return the resolved `openclaw` CLI path when available."""
    if command is not None:
        candidate = Path(command).expanduser()
        return candidate.resolve() if candidate.exists() else None

    discovered = shutil.which("openclaw")
    return Path(discovered).resolve() if discovered else None


def resolve_openclaw_command(command: str | Path | None = None) -> Path:
    """Resolve the OpenClaw CLI path or raise a helpful error."""
    resolved = find_openclaw_command(command)
    if resolved is None:
        raise TransportError(
            "Could not find the 'openclaw' CLI. Install OpenClaw first or configure "
            "integration.openclaw.command explicitly."
        )
    return resolved


def build_gateway_cli_args(gateway_url: str | None) -> list[str]:
    """Build `--url` and auth args for the OpenClaw CLI."""
    normalized = normalize_gateway_url(gateway_url)
    if normalized is None or normalized in _LOCAL_GATEWAY_URLS:
        return []

    token = os.getenv("OPENCLAW_GATEWAY_TOKEN")
    password = os.getenv("OPENCLAW_GATEWAY_PASSWORD")
    if token:
        return ["--url", normalized, "--token", token]
    if password:
        return ["--url", normalized, "--password", password]
    raise TransportError(
        "Remote OpenClaw gateway access requires OPENCLAW_GATEWAY_TOKEN or "
        "OPENCLAW_GATEWAY_PASSWORD in the environment."
    )


def parse_json_output(output: str) -> dict[str, Any]:
    """Parse CLI JSON output, tolerating leading log lines."""
    trimmed = output.strip()
    if not trimmed:
        return {}
    try:
        payload = json.loads(trimmed)
        return payload if isinstance(payload, dict) else {"value": payload}
    except json.JSONDecodeError:
        start = trimmed.find("{")
        end = trimmed.rfind("}")
        if start >= 0 and end > start:
            payload = json.loads(trimmed[start : end + 1])
            return payload if isinstance(payload, dict) else {"value": payload}
    raise TransportError(f"Could not parse OpenClaw JSON output: {trimmed}")


def extract_reply_text(payload: Any) -> str | None:
    """Extract the most useful text reply from a nested OpenClaw payload."""
    if isinstance(payload, str):
        text = payload.strip()
        return text or None

    if isinstance(payload, list):
        parts: list[str] = []
        for item in payload:
            text = extract_reply_text(item)
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
        return None

    if not isinstance(payload, dict):
        return None

    direct_text = payload.get("text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    content = payload.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            else:
                text = extract_reply_text(item)
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts)

    for key in ("reply", "response", "final", "result", "assistant", "output", "message"):
        nested = payload.get(key)
        text = extract_reply_text(nested)
        if text:
            return text

    for value in payload.values():
        text = extract_reply_text(value)
        if text:
            return text
    return None


class OpenClawAgentTransport(TextTransport):
    """Dispatch transcript text through the supported `openclaw agent` CLI."""

    def __init__(
        self,
        *,
        command: str | Path | None,
        gateway_url: str | None,
        agent_id: str,
        session_key: str,
        session_strategy: str = "dedicated_mic",
        delivery_mode: str,
        reply_channel: str | None = None,
        reply_to: str | None = None,
        reply_account: str | None = None,
        timeout_seconds: int = 180,
    ) -> None:
        self.command = resolve_openclaw_command(command)
        self.gateway_args = build_gateway_cli_args(gateway_url)
        self.agent_id = agent_id.strip()
        self.session_key = normalize_openclaw_session_id(session_key)
        self.session_strategy = session_strategy.strip().lower()
        self.delivery_mode = delivery_mode.strip()
        self.reply_channel = reply_channel.strip() if reply_channel else None
        self.reply_to = reply_to.strip() if reply_to else None
        self.reply_account = reply_account.strip() if reply_account else None
        self.timeout_seconds = timeout_seconds

        if not self.agent_id:
            raise TransportError("OpenClaw agent_id must not be empty.")
        if not self.session_key:
            raise TransportError("OpenClaw session_key must not be empty.")
        if self.session_strategy not in {"dedicated_mic", "agent_main"}:
            raise TransportError(
                "OpenClaw session_strategy must be 'dedicated_mic' or 'agent_main'."
            )

    def dispatch(self, text: str) -> DispatchResult:
        """Submit transcript text into OpenClaw and parse the reply."""
        transcript = text.strip()
        if not transcript:
            raise TransportError("Cannot dispatch an empty transcript to OpenClaw.")

        command = [
            str(self.command),
            "agent",
            "--agent",
            self.agent_id,
            "--message",
            transcript,
            "--json",
        ]
        if self.session_strategy == "dedicated_mic":
            command[4:4] = ["--session-id", self.session_key]
        command.extend(self.gateway_args)
        command.extend(self._delivery_args())

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransportError("OpenClaw agent request timed out.") from exc
        except OSError as exc:
            raise TransportError(f"Could not start the OpenClaw CLI: {exc}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise TransportError(f"OpenClaw agent request failed: {stderr}")

        payload = parse_json_output(result.stdout)
        return DispatchResult(
            transcript=transcript,
            reply_text=extract_reply_text(payload),
            raw=payload,
        )

    def _delivery_args(self) -> list[str]:
        if self.delivery_mode == "local_only":
            return []

        if self.delivery_mode != "local_plus_explicit_channel_target":
            raise TransportError(f"Unsupported delivery mode: {self.delivery_mode}")
        if not self.reply_channel or not self.reply_to:
            raise TransportError(
                "Delivery mode 'local_plus_explicit_channel_target' requires reply_channel "
                "and reply_to."
            )

        args = [
            "--deliver",
            "--reply-channel",
            self.reply_channel,
            "--reply-to",
            self.reply_to,
        ]
        if self.reply_account:
            args.extend(["--reply-account", self.reply_account])
        return args
