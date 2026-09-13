"""Requested evidence bundles with a useful deterministic offline summary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .calendar_service import CalendarService
from .notes_service import NotesService
from .research_service import ResearchService
from .task_service import TaskService
from .tools import CancellationToken


class BriefingService:
    def __init__(
        self,
        notes: NotesService,
        tasks: TaskService,
        calendar: CalendarService,
        research: ResearchService,
    ) -> None:
        self.notes = notes
        self.tasks = tasks
        self.calendar = calendar
        self.research = research

    async def build(
        self,
        user: str,
        session: str,
        timezone: str,
        cancel: CancellationToken,
        *,
        note_ids: list[str] | None = None,
        connection_id: str = "",
        research_queries: list[str] | None = None,
    ) -> dict[str, Any]:
        zone = ZoneInfo(timezone)
        today = datetime.now(zone).date()
        start = datetime.combine(today, time(), zone)
        end = datetime.combine(today + timedelta(days=1), time(), zone)
        if len(note_ids or []) > 10 or len(research_queries or []) > 1:
            raise ValueError(
                "a briefing accepts ten selected notes and one requested public search"
            )
        if cancel.cancelled:
            raise asyncio.CancelledError
        sections: list[dict[str, Any]] = []
        tasks = await self.tasks.list("user:" + user)
        due = [
            {
                "task_id": t.task_id,
                "title": t.title,
                "status": t.status.value,
                "due_at": t.due_at.isoformat(),
            }
            for t in tasks
            if t.kind == "reminder"
            and t.status.value not in {"cancelled", "failed"}
            and start.astimezone(UTC) <= t.due_at < end.astimezone(UTC)
        ]
        sections.append(
            {
                "source": "local_tasks",
                "state": "incomplete" if len(tasks) >= 100 or len(due) > 20 else "available",
                "items": due[:20],
            }
        )
        items = []
        for ident in note_ids or []:
            record = await self.notes.read(user, ident)
            for item in record["payload"].get("items", []):
                if not item["completed"]:
                    items.append(
                        {"note_id": ident, "item_id": item["item_id"], "text": item["text"]}
                    )
        sections.append(
            {
                "source": "selected_checklists",
                "state": "incomplete" if len(items) > 20 else "available",
                "items": items[:20],
            }
        )
        semaphore = asyncio.Semaphore(2)

        async def external(name: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    async with asyncio.timeout(16 if name == "calendar" else 30):
                        data = (
                            await self.calendar.list_events(
                                user, connection_id, start.isoformat(), end.isoformat(), timezone
                            )
                            if name == "calendar"
                            else await self.research.run(
                                user, session, research_queries or [], cancel
                            )
                        )
                    return {
                        "source": name,
                        "state": "available" if data["complete"] else "incomplete",
                        "data": data,
                    }
                except Exception:
                    return {
                        "source": name,
                        "state": "unavailable",
                        "warning": "Local briefing remains useful; this source could not "
                        "be checked.",
                    }

        names = (["calendar"] if connection_id else []) + (["research"] if research_queries else [])
        sections.extend(await asyncio.gather(*(external(name) for name in names)))
        if cancel.cancelled:
            raise asyncio.CancelledError
        lines = [
            f"Briefing for {today.isoformat()} ({timezone}).",
            f"Local reminders in this interval: {len(due[:20])}.",
            *(f"- {item['task_id']}: {item['title']} at {item['due_at']}" for item in due[:20]),
            f"Selected unfinished checklist items: {len(items[:20])}.",
            *(f"- {item['note_id']} / {item['item_id']}: {item['text']}" for item in items[:20]),
        ]
        lines.extend(f"{section['source']}: {section['state']}." for section in sections[2:])
        for section in sections[2:]:
            content = section.get("data", {}).get("external_untrusted_content", {})
            for event in content.get("events", [])[:10]:
                lines.append(f"- Calendar {event['event_id']}: {event['title']} ({event['start']})")
            for source in content.get("sources", [])[:3]:
                lines.append(
                    f"- [{source['source_id']}] {source['title']}: "
                    f"{source['excerpt'][:300]} ({source['url']})"
                )
        if any(section["state"] != "available" for section in sections):
            lines.append("Some sources are incomplete or unavailable; this is not a full schedule.")
        return {
            "text": "\n".join(lines)[:6000],
            "spoken_summary": (
                f"Today's local briefing has {len(due[:20])} reminders and "
                f"{len(items[:20])} selected unfinished checklist items. "
                "Read the full text for source coverage."
            ),
            "checked_at": datetime.now(UTC).isoformat(),
            "interval": {"start": start.isoformat(), "end": end.isoformat(), "timezone": timezone},
            "sections": sections,
            "saved": False,
        }
