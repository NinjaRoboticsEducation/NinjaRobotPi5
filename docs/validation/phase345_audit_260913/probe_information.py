"""Audit diagnostic: synthetic data only; run from the checkout root.

Reports current behavior, including defects; exit zero is not feature acceptance.
Uses the repository test fixture, never a live Agent, hardware or Google account.
"""

# ruff: noqa: E402
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path.cwd() / "ninjarobot_pi5_agent/tests"))
from ninjarobot_pi5_agent.calendar_google import READ_SCOPE
from ninjarobot_pi5_agent.calendar_service import CalendarChange
from ninjarobot_pi5_agent.information_controls import information_action
from ninjarobot_pi5_agent.notes_service import NoteChange, NoteContent
from ninjarobot_pi5_agent.tools import CancellationToken
from test_information_controls import runtime_for


async def run(root):
    r = await runtime_for(root)
    p = r.information
    try:
        # Synthetic credentials only; no Google backend request is made.
        args = {
            "calendar_id": "synthetic@example.org",
            "account_label": "Audit fake",
            "expected_user_id": "local-user",
            "credential": {
                "client_id": "fake",
                "client_secret": "fake",
                "refresh_token": "fake",
                "scope": READ_SCOPE,
            },
        }
        c = await information_action(
            r, "one", {"operation": "calendar.connect", "arguments": args, "confirmed": True}
        )
        record = await p.store.action("local-user", "get", record_id=c["connection_id"])
        old_stop = p._stop_user_work

        async def interrupted(user):
            raise asyncio.CancelledError()

        p._stop_user_work = interrupted
        try:
            await information_action(
                r,
                "one",
                {
                    "operation": "calendar.disconnect",
                    "arguments": {"connection_id": c["connection_id"]},
                    "confirmed": True,
                },
            )
        except asyncio.CancelledError:
            pass
        p._stop_user_work = old_stop
        remains = p.secrets.contains(record["payload"]["secret_ref"])
        try:
            await information_action(
                r,
                "one",
                {
                    "operation": "calendar.disconnect",
                    "arguments": {"connection_id": c["connection_id"]},
                    "confirmed": True,
                },
            )
            retry = "succeeded"
        except ValueError as e:
            retry = str(e)
        print("disconnect:", json.dumps({"credential_remains": remains, "retry": retry}))
        # 21 connections including the disabled record above.
        for i in range(20):
            await p.store.action(
                "local-user",
                "create",
                kind="calendar_connection",
                payload={**record["payload"], "account_label": f"Audit {i}", "enabled": True},
            )
        page = await p.action("one", "calendar.connections", {}, CancellationToken())
        print(
            "connection_list:",
            json.dumps(
                {
                    "stored": 21,
                    "returned": len(page["connections"]),
                    "cursor_exposed": "next_after" in page,
                }
            ),
        )
        # Shorten only the test runtime budget, then simulate a slow optional speaker.
        r.loop.execution_limits = lambda: {"request_seconds": 0.1}
        entered = asyncio.Event()

        async def slow_speech(text):
            entered.set()
            await asyncio.sleep(10)

        r.speech = SimpleNamespace(enabled=True, speak=slow_speech, close=AsyncMock())
        try:
            await information_action(
                r, "one", {"operation": "briefing.build", "arguments": {"timezone": "Asia/Tokyo"}}
            )
            result = "returned text"
        except TimeoutError:
            result = "TimeoutError: no briefing returned"
        print(
            "briefing:",
            json.dumps({"text_built_and_speech_started": entered.is_set(), "result": result}),
        )
        # A legitimate owned event receipt and a fake existing remote event.
        active = await p.store.action(
            "local-user",
            "create",
            kind="calendar_connection",
            payload={**record["payload"], "enabled": True, "write_enabled": True},
        )
        await p.store.action(
            "local-user",
            "create",
            kind="calendar_operation",
            payload={
                "action": "create",
                "state": "verified",
                "event_id": "synthetic-event",
                "connection_id": active["record_id"],
            },
        )
        p.calendar.backend = SimpleNamespace(
            request=AsyncMock(
                return_value={
                    "etag": "audit-version",
                    "summary": "Dentist appointment",
                    "start": {"dateTime": "2026-09-14T10:00:00+09:00"},
                    "end": {"dateTime": "2026-09-14T11:00:00+09:00"},
                }
            )
        )
        preview = await p.calendar.propose(
            "local-user",
            "one",
            CalendarChange(
                action="cancel", connection_id=active["record_id"], event_id="synthetic-event"
            ),
        )
        print(
            "calendar_cancel_preview:",
            json.dumps(
                {
                    "body": preview["payload"]["body"],
                    "current_title_present": "Dentist appointment" in json.dumps(preview),
                    "current_time_present": "2026-09-14T10:" in json.dumps(preview),
                }
            ),
        )
        note = await p.store.action(
            "local-user",
            "create",
            kind="note",
            payload=NoteContent(title="Important checklist").model_dump(mode="json"),
        )
        preview = await p.notes.propose(
            "local-user",
            "one",
            NoteChange(action="delete", record_id=note["record_id"], revision=note["revision"]),
        )
        print(
            "note_delete_preview:",
            json.dumps(
                {
                    "content": preview["payload"]["change"]["content"],
                    "current_title_present": "Important checklist" in json.dumps(preview),
                }
            ),
        )
        # Two existing operation records above; fill only this temporary database.
        for _ in range(998):
            await p.store.action(
                "local-user", "create", kind="calendar_operation", payload={"state": "expired"}
            )
        for stage in ("before_restart_recovery", "after_restart_recovery"):
            try:
                await p.store.action(
                    "local-user", "create", kind="calendar_operation", payload={"state": "pending"}
                )
                result = "created"
            except ValueError as error:
                result = str(error)
            print("calendar_capacity:", stage, result)
            await p.store.recover()
    finally:
        await r.close()


with tempfile.TemporaryDirectory(prefix="ninja-audit-") as directory:
    asyncio.run(run(Path(directory)))
