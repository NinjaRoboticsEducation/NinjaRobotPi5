"""Read the service host's clock and OS timezone without changing either."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


def system_time_snapshot() -> dict[str, Any]:
    """Read afresh on each call, including timezone changes while the Agent runs.

    /etc/localtime is the OS timezone authority on Raspberry Pi OS. Do not use
    a provider's timezone, a conversation timestamp, or a process TZ override.
    An unknown regional name must not be invented for reminder validation.
    """
    zone: ZoneInfo | None = None
    name: str | None = None
    source = Path("/etc/localtime")
    try:
        resolved_path = source.resolve(strict=True)
        with resolved_path.open("rb") as handle:
            zone = ZoneInfo.from_file(handle)
        resolved = str(resolved_path)
        if "/zoneinfo/" in resolved:
            candidate = resolved.split("/zoneinfo/", 1)[1]
            if candidate and not candidate.startswith(("posix/", "right/")):
                # The name and rules must refer to the same file, not a stale
                # /etc/timezone text setting or a different process environment.
                name = candidate
    except (OSError, ValueError):
        pass
    now = datetime.now(UTC)
    local = now.astimezone(zone) if zone is not None else now
    offset = local.utcoffset()
    return {
        "utc": now.isoformat(timespec="seconds"),
        "local": local.isoformat(timespec="seconds"),
        "date": local.date().isoformat(),
        "weekday": local.strftime("%A"),
        "timezone": name,
        "timezone_abbreviation": local.tzname(),
        "utc_offset_seconds": int(offset.total_seconds()) if offset is not None else 0,
        "unix_seconds": now.timestamp(),
        "source": "Agent host system clock; read at request time",
        "timezone_status": "system" if zone is not None else "unavailable; showing UTC",
        "network_clock_sync": "not checked by this read-only tool",
    }
