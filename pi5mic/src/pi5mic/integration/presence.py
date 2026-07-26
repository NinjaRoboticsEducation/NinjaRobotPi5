"""OpenClaw presence-control helpers for pi5mic."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from pi5mic.errors import IntegrationError
from pi5mic.transport.openclaw_cli import (
    build_gateway_cli_args,
    parse_json_output,
    resolve_openclaw_command,
)

_ALLOWED_PRESENCE_MODES = {"idle", "thinking", "listening"}


class OpenClawPresenceController:
    """Best-effort caller for the plugin-owned presence Gateway method."""

    def __init__(
        self,
        *,
        command: str | Path | None,
        gateway_url: str | None,
        method_name: str = "ninjaclawbot.presence.set",
        timeout_seconds: int = 3,
    ) -> None:
        self.command = resolve_openclaw_command(command)
        self.gateway_args = build_gateway_cli_args(gateway_url)
        self.method_name = method_name
        self.timeout_seconds = timeout_seconds

    def set_mode(self, mode: str, *, reason: str = "pi5mic") -> dict[str, Any]:
        """Request a robot presence change through the active OpenClaw plugin."""
        normalized = mode.strip()
        if normalized not in _ALLOWED_PRESENCE_MODES:
            raise IntegrationError(
                f"Unsupported presence mode: {normalized}. "
                f"Expected one of: {', '.join(sorted(_ALLOWED_PRESENCE_MODES))}."
            )

        command = [
            str(self.command),
            "gateway",
            "call",
            self.method_name,
            "--params",
            json.dumps({"mode": normalized, "reason": reason}),
        ]
        command.extend(self.gateway_args)

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise IntegrationError("OpenClaw presence update timed out.") from exc
        except OSError as exc:
            raise IntegrationError(f"Could not start the OpenClaw CLI: {exc}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise IntegrationError(f"OpenClaw presence update failed: {stderr}")

        if not result.stdout.strip():
            return {"mode": normalized, "reason": reason}
        return parse_json_output(result.stdout)
