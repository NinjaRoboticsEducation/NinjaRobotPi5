from __future__ import annotations

import asyncio
import json

import pytest
from ninjarobot_pi5_agent.calendar_google import READ_SCOPE
from ninjarobot_pi5_agent.external_mcp import google_calendar
from ninjarobot_pi5_agent.external_mcp.google_calendar import (
    _load_credential,
    _time_window,
    create_server,
)


def _credential(path) -> None:
    path.write_text(
        json.dumps(
            {
                "client_id": "client",
                "client_secret": "secret",
                "refresh_token": "refresh",
                "scope": READ_SCOPE,
                "calendar_id": "owner@example.com",
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)


def test_calendar_server_exposes_only_read_only_today_tool(tmp_path) -> None:
    path = tmp_path / "calendar.json"
    _credential(path)

    async def exercise() -> None:
        tools = await create_server(path).list_tools()
        assert [tool.name for tool in tools] == ["list_today_events"]
        assert tools[0].annotations is not None
        assert tools[0].annotations.readOnlyHint is True

    asyncio.run(exercise())


def test_calendar_credential_requires_exact_schema_scope_and_permissions(tmp_path) -> None:
    path = tmp_path / "calendar.json"
    _credential(path)
    assert _load_credential(path)["calendar_id"] == "owner@example.com"

    path.chmod(0o644)
    with pytest.raises(PermissionError, match="0600"):
        _load_credential(path)


def test_calendar_time_window_rejects_unknown_timezone() -> None:
    start, end, local_date = _time_window("Asia/Tokyo")
    assert start.endswith("+00:00") and end.endswith("+00:00")
    assert len(local_date) == 10
    with pytest.raises(ValueError, match="IANA"):
        _time_window("not/a-zone")


def test_calendar_tool_reuses_backend_and_omits_private_event_fields(tmp_path, monkeypatch) -> None:
    path = tmp_path / "calendar.json"
    _credential(path)
    calls = []

    class FakeBackend:
        def __init__(self, _source) -> None:
            pass

        async def request(self, connection, method, **kwargs):
            calls.append((connection, method, kwargs))
            return {
                "items": [
                    {
                        "summary": "Private appointment",
                        "start": {"dateTime": "2026-09-22T09:00:00+09:00"},
                        "end": {"dateTime": "2026-09-22T10:00:00+09:00"},
                        "status": "confirmed",
                        "description": "must not leave the adapter",
                        "attendees": [{"email": "private@example.com"}],
                    }
                ]
            }

    monkeypatch.setattr(google_calendar, "GoogleCalendarBackend", FakeBackend)

    async def exercise() -> None:
        result = await create_server(path).call_tool(
            "list_today_events", {"timezone": "Asia/Tokyo", "max_results": 1}
        )
        rendered = str(result)
        assert "Private appointment" in rendered
        assert "must not leave" not in rendered
        assert "private@example.com" not in rendered

    asyncio.run(exercise())
    assert calls[0][1] == "GET"
    assert calls[0][0]["calendar_id"] == "owner@example.com"
    assert calls[0][2]["max_bytes"] == 262_144
