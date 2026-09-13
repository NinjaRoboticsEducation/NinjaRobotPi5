"""No live accounts: ownership, exact review and restart recovery checks."""

import asyncio
from pathlib import Path

import pytest
from ninjarobot_pi5_agent.information_store import InformationStore
from ninjarobot_pi5_agent.memory_store import MemoryStore
from ninjarobot_pi5_agent.notes_service import NoteChange, NoteContent, NotesService


def test_owned_notes_exact_review_and_concurrent_confirmation(tmp_path: Path) -> None:
    async def run() -> None:
        memory = MemoryStore(tmp_path / "memory.db")
        await memory.start()
        owner = await memory.create_profile("Owner")
        member = await memory.create_profile("Member")
        notes = NotesService(InformationStore(memory.path))
        preview = await notes.propose(
            owner.user_id, "cli", NoteChange(action="create", content=NoteContent(title="Packing"))
        )
        assert (await notes.list(owner.user_id))["notes"] == []
        args = (preview["record_id"], preview["payload"]["review_hash"])
        with pytest.raises(KeyError):
            await notes.confirm(member.user_id, "cli", *args)
        with pytest.raises(ValueError):
            await notes.confirm(owner.user_id, "other", *args)
        results = await asyncio.gather(
            *(notes.confirm(owner.user_id, "cli", *args) for _ in range(2)), return_exceptions=True
        )
        assert sum(isinstance(item, dict) for item in results) == 1
        record = (await notes.list(owner.user_id))["notes"][0]
        assert (await notes.list(member.user_id))["notes"] == []
        change = NoteChange(
            action="update",
            record_id=record["record_id"],
            revision=1,
            content=NoteContent(title="New"),
        )
        first = await notes.propose(owner.user_id, "cli", change)
        stale = await notes.propose(owner.user_id, "cli", change)
        await notes.confirm(
            owner.user_id, "cli", first["record_id"], first["payload"]["review_hash"]
        )
        with pytest.raises(ValueError):
            await notes.confirm(
                owner.user_id, "cli", stale["record_id"], stale["payload"]["review_hash"]
            )
        await memory.close()

    asyncio.run(run())


def test_restart_expires_authority_and_deleted_owner_cannot_reappear(tmp_path: Path) -> None:
    async def run() -> None:
        memory = MemoryStore(tmp_path / "memory.db")
        await memory.start()
        await memory.create_profile("Owner")
        member = await memory.create_profile("Member")
        store = InformationStore(memory.path)
        notes = NotesService(store)
        preview = await notes.propose(
            member.user_id, "cli", NoteChange(action="create", content=NoteContent(title="Private"))
        )
        await store.recover()
        with pytest.raises(ValueError):
            await notes.confirm(
                member.user_id, "cli", preview["record_id"], preview["payload"]["review_hash"]
            )
        await memory.delete_profile(member.user_id)
        with pytest.raises(ValueError, match="no longer exists"):
            await notes.list(member.user_id)
        await memory.close()

    asyncio.run(run())


def test_notes_bound_bytes_and_stable_identifiers() -> None:
    with pytest.raises(ValueError):
        NoteContent(title="Large", body="語" * 6000)
    with pytest.raises(ValueError):
        NoteContent.model_validate_json(
            '{"title":"duplicate","items":[{"item_id":"item-00000000000000000000000000000000","text":"a"},{"item_id":"item-00000000000000000000000000000000","text":"b"}]}'
        )


def test_calendar_lost_response_reconciliation_and_no_duplicate_write(tmp_path: Path) -> None:
    from ninjarobot_pi5_agent.calendar_service import CalendarChange, CalendarEvent, CalendarService

    class Backend:
        def __init__(self):
            self.event = {}
            self.writes = 0
            self.lose = True

        async def request(self, connection, method, **kwargs):
            if method == "POST":
                self.writes += 1
                self.event = {**kwargs["body"], "etag": "v1"}
                if self.lose:
                    raise TimeoutError("lost response")
            return self.event

    async def run() -> None:
        memory = MemoryStore(tmp_path / "memory.db")
        await memory.start()
        user = (await memory.create_profile("Owner")).user_id
        store = InformationStore(memory.path)
        connection = await store.action(
            user,
            "create",
            kind="calendar_connection",
            payload={
                "enabled": True,
                "write_enabled": True,
                "calendar_id": "test@example.org",
                "account_label": "Test",
            },
        )
        backend = Backend()
        calendar = CalendarService(store, backend)
        event = CalendarEvent(
            title="Planning",
            start="2026-09-15T10:00:00+09:00",
            end="2026-09-15T10:30:00+09:00",
            timezone="Asia/Tokyo",
        )
        preview = await calendar.propose(
            user,
            "cli",
            CalendarChange(action="create", connection_id=connection["record_id"], event=event),
        )
        assert backend.writes == 0
        with pytest.raises(ValueError):
            await calendar.confirm(user, "cli", preview["record_id"], "invented")
        result = await calendar.confirm(
            user, "cli", preview["record_id"], preview["payload"]["review_hash"]
        )
        assert result["state"] == "uncertain"
        with pytest.raises(ValueError):
            await calendar.confirm(
                user, "cli", preview["record_id"], preview["payload"]["review_hash"]
            )
        result = await calendar.status(user, preview["record_id"], reconcile=True)
        assert result["payload"]["state"] == "verified"
        assert backend.writes == 1
        cancelled = await calendar.propose(
            user,
            "cli",
            CalendarChange(action="create", connection_id=connection["record_id"], event=event),
        )
        await calendar.cancel(user, cancelled["record_id"])
        with pytest.raises(ValueError):
            await calendar.confirm(
                user, "cli", cancelled["record_id"], cancelled["payload"]["review_hash"]
            )
        assert backend.writes == 1
        await memory.close()

    asyncio.run(run())


def test_calendar_offsets_and_all_day_exclusive_end() -> None:
    from ninjarobot_pi5_agent.calendar_service import CalendarEvent, interval

    with pytest.raises(ValueError):
        interval("2026-09-15T10:00:00", "2026-09-15T11:00:00", "Asia/Tokyo")
    with pytest.raises(ValueError):
        interval("2026-09-15T10:00:00+00:00", "2026-09-15T11:00:00+00:00", "Asia/Tokyo")
    first, last = interval(
        "2026-11-01T01:30:00-04:00", "2026-11-01T01:30:00-05:00", "America/New_York"
    )
    assert (last - first).total_seconds() == 3600
    event = CalendarEvent(
        title="Day", start="2026-09-15", end="2026-09-16", timezone="Asia/Tokyo", all_day=True
    )
    assert event.google()["end"] == {"date": "2026-09-16"}


def test_research_real_sources_and_idempotent_save(tmp_path: Path) -> None:
    from ninjarobot_pi5_agent.models import ToolExecutionResult, ToolExecutionStatus
    from ninjarobot_pi5_agent.research_service import ResearchService, public_url
    from ninjarobot_pi5_agent.tools import CancellationToken

    async def search(session, query, cancel):
        return ToolExecutionResult(
            call_id="test",
            tool_name="mcp.tavily.tavily-search",
            status=ToolExecutionStatus.SUCCEEDED,
            data={
                "external_untrusted_content": {
                    "structuredContent": {
                        "results": [
                            {
                                "url": "https://example.org/evidence",
                                "title": "Evidence",
                                "content": "Some evidence.",
                            },
                            {"url": "http://127.0.0.1/private", "content": "private"},
                        ]
                    }
                }
            },
        )

    async def run() -> None:
        memory = MemoryStore(tmp_path / "memory.db")
        await memory.start()
        user = (await memory.create_profile("Owner")).user_id
        store = InformationStore(memory.path)
        notes = NotesService(store)
        research = ResearchService(store, notes, search)
        result = await research.run(user, "cli", ["Public question"], CancellationToken())
        sources = result["external_untrusted_content"]["sources"]
        assert len(sources) == 1 and sources[0]["source_id"] == "S1"
        assert sources[0]["published_at"] is None
        with pytest.raises(ValueError):
            await research.save_preview(user, "cli", result["run_id"], "Result", "Unknown", ["S9"])
        one = await research.save_preview(
            user, "cli", result["run_id"], "Result", "Summary", ["S1"]
        )
        two = await research.save_preview(
            user, "cli", result["run_id"], "Result", "Summary", ["S1"]
        )
        assert one["record_id"] == two["record_id"]
        assert (await notes.list(user))["notes"] == []
        await memory.close()

    for url in ("http://127.0.0.1/", "http://device.local/", "https://user:password@example.org/"):
        with pytest.raises(ValueError):
            public_url(url)
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["cancel", "version_conflict", "read_only", "partial"])
def test_calendar_failure_boundaries(tmp_path: Path, failure: str) -> None:
    from ninjarobot_pi5_agent.calendar_google import CalendarHTTPError
    from ninjarobot_pi5_agent.calendar_service import CalendarChange, CalendarEvent, CalendarService

    async def run():
        memory = MemoryStore(tmp_path / "memory.db")
        await memory.start()
        user = (await memory.create_profile("Owner")).user_id
        store = InformationStore(memory.path)
        connection = await store.action(
            user,
            "create",
            kind="calendar_connection",
            payload={
                "enabled": True,
                "write_enabled": failure != "read_only",
                "calendar_id": "test@example.org",
                "account_label": "Test",
            },
        )
        entered = asyncio.Event()

        class Backend:
            writes = 0
            reads = 0
            event = {}
            etag = None

            async def request(self, connection, method, **kwargs):
                if method == "GET":
                    self.reads += 1
                    if not kwargs.get("event_id"):
                        return (
                            {"items": [], "nextPageToken": "another"}
                            if failure == "partial"
                            else {"items": []}
                        )
                    return self.event
                self.writes += 1
                self.etag = kwargs.get("etag")
                if failure == "cancel":
                    entered.set()
                    await asyncio.Event().wait()
                if method == "PATCH":
                    raise CalendarHTTPError(412)
                self.event = {**kwargs["body"], "etag": "original-version"}
                return self.event

        backend = Backend()
        calendar = CalendarService(store, backend)
        event = CalendarEvent(
            title="Plan",
            start="2026-09-15T10:00:00+09:00",
            end="2026-09-15T10:30:00+09:00",
            timezone="Asia/Tokyo",
        )
        draft = CalendarChange(action="create", connection_id=connection["record_id"], event=event)
        if failure == "read_only":
            with pytest.raises(PermissionError):
                await calendar.propose(user, "cli", draft)
            assert backend.writes == 0
        elif failure == "partial":
            result = await calendar.suggest_time(
                user, connection["record_id"], event.start, event.end, event.timezone
            )
            assert not result["complete"] and result["suggestions"] == []
            assert backend.reads == 5 and backend.writes == 0
        else:
            preview = await calendar.propose(user, "cli", draft)
            args = (user, "cli", preview["record_id"], preview["payload"]["review_hash"])
            if failure == "cancel":
                worker = asyncio.create_task(calendar.confirm(*args))
                await entered.wait()
                with pytest.raises(ValueError, match="already running"):
                    await calendar.confirm(*args)
                cancelled = await calendar.cancel(user, preview["record_id"])
                assert cancelled["payload"]["state"] == "uncertain"
                with pytest.raises(asyncio.CancelledError):
                    await worker
                assert backend.writes == 1
            else:
                original = await calendar.confirm(*args)
                assert original["payload"]["state"] == "verified"
                updated = await calendar.propose(
                    user,
                    "cli",
                    CalendarChange(
                        action="update",
                        connection_id=connection["record_id"],
                        event_id=original["payload"]["event_id"],
                        event=event.model_copy(update={"title": "Changed"}),
                    ),
                )
                result = await calendar.confirm(
                    user, "cli", updated["record_id"], updated["payload"]["review_hash"]
                )
                assert result["state"] == "uncertain" and backend.writes == 2
                assert backend.etag == "original-version"
                assert (await calendar.status(user, updated["record_id"], reconcile=True))[
                    "payload"
                ]["state"] == "uncertain"
        await memory.close()

    asyncio.run(run())
