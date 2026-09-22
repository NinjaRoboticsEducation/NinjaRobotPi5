"""Read-only Google Calendar MCP server for the onboarding preset."""

from __future__ import annotations

import argparse
import asyncio
import json
import stat
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Annotated, Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from ..calendar_google import READ_SCOPE, GoogleCalendarBackend
from ..secrets import SecretStore

_SECRET_REFERENCE = "GOOGLE_CALENDAR_MCP_CREDENTIAL"


class CalendarEvent(BaseModel):
    """Bounded event fields exposed to the Agent."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: str
    start: str
    end: str
    all_day: bool
    status: str


class CalendarResult(BaseModel):
    """Structured result from one bounded Calendar query."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    date: str
    timezone: str
    events: tuple[CalendarEvent, ...]


class _CredentialSource:
    """Minimal SecretStore-compatible view over one private credential file."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().absolute()

    def require(self, reference: str) -> str:
        if reference != _SECRET_REFERENCE:
            raise KeyError("unknown Calendar credential reference")
        return json.dumps(_load_credential(self.path), separators=(",", ":"))

    def get(self, reference: str) -> str | None:
        return self.require(reference)


def _load_credential(path: Path) -> dict[str, str]:
    if path.is_symlink() or path.parent.resolve() != path.parent:
        raise ValueError("Calendar MCP credential must use a real private path")
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PermissionError("Calendar MCP credential must be a mode 0600 regular file")
    if metadata.st_size > 65_536:
        raise ValueError("Calendar MCP credential file is oversized")
    raw = json.loads(path.read_text(encoding="utf-8"))
    required = {"client_id", "client_secret", "refresh_token", "scope", "calendar_id"}
    if set(raw) != required or any(not isinstance(raw[key], str) for key in required):
        raise ValueError("Calendar MCP credential has an invalid schema")
    if raw["scope"] != READ_SCOPE or "@" not in raw["calendar_id"]:
        raise ValueError("Calendar MCP credential is not the reviewed read-only grant")
    return cast(dict[str, str], raw)


def _time_window(timezone: str) -> tuple[str, str, str]:
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("timezone must be an installed IANA timezone name") from exc
    local_date = datetime.now(zone).date()
    start = datetime.combine(local_date, time.min, tzinfo=zone)
    end = start + timedelta(days=1)
    return start.astimezone(UTC).isoformat(), end.astimezone(UTC).isoformat(), str(local_date)


def create_server(credential_file: Path) -> FastMCP[None]:
    """Create a one-tool external server around the existing Calendar backend."""
    credential = _load_credential(credential_file)
    source = _CredentialSource(credential_file)
    backend = GoogleCalendarBackend(cast(SecretStore, source))
    connection = {
        "secret_ref": _SECRET_REFERENCE,
        "calendar_id": credential["calendar_id"],
    }
    server: FastMCP[None] = FastMCP(
        "NinjaRobot Google Calendar",
        instructions=(
            "Read a bounded view of today's events. This external MCP server cannot create, "
            "change, or delete calendar data."
        ),
    )
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )

    @server.tool(
        name="list_today_events",
        description="List a bounded set of events for today in the requested timezone.",
        annotations=annotations,
    )
    async def list_today_events(
        timezone: str = "UTC",
        max_results: Annotated[int, Field(ge=1, le=20)] = 10,
    ) -> CalendarResult:
        time_min, time_max, local_date = _time_window(timezone)
        response = await backend.request(
            connection,
            "GET",
            params={
                "singleEvents": "true",
                "orderBy": "startTime",
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": str(max_results),
                "fields": "items(summary,start,end,status)",
            },
            max_bytes=262_144,
        )
        raw_events = response.get("items", [])
        if not isinstance(raw_events, list):
            raise ValueError("Google Calendar returned an invalid event list")
        events: list[CalendarEvent] = []
        for item in raw_events[:max_results]:
            if not isinstance(item, dict):
                continue
            raw_start = item.get("start")
            raw_end = item.get("end")
            start: dict[str, Any] = raw_start if isinstance(raw_start, dict) else {}
            end: dict[str, Any] = raw_end if isinstance(raw_end, dict) else {}
            start_value = start.get("dateTime") or start.get("date")
            end_value = end.get("dateTime") or end.get("date")
            if not isinstance(start_value, str) or not isinstance(end_value, str):
                continue
            title = item.get("summary", "Untitled event")
            status = item.get("status", "confirmed")
            events.append(
                CalendarEvent(
                    title=str(title)[:300],
                    start=start_value[:64],
                    end=end_value[:64],
                    all_day="date" in start,
                    status=str(status)[:32],
                )
            )
        return CalendarResult(date=local_date, timezone=timezone, events=tuple(events))

    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NinjaRobot read-only Google Calendar MCP")
    parser.add_argument("--credential-file", type=Path, required=True)
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    asyncio.run(create_server(arguments.credential_file).run_stdio_async())


if __name__ == "__main__":
    main()
