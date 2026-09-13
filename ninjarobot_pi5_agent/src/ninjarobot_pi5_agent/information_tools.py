"""Shared owned notes/calendar/research controls and narrowly scoped model tools."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ninjarobot_pi5_ide import RiskLevel

from .briefing_service import BriefingService
from .calendar_google import READ_SCOPE, WRITE_SCOPE, GoogleCalendarBackend
from .calendar_service import CalendarChange, CalendarService
from .information_store import InformationStore
from .models import (
    ProviderHealth,
    ProviderHealthStatus,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
)
from .notes_service import NoteChange, NotesService
from .research_service import ResearchService
from .secrets import SecretStore
from .task_service import TaskService
from .tools import CancellationToken

Scope = Callable[[str], Awaitable[tuple[str, str | None]]]
Execute = Callable[..., Awaitable[ToolExecutionResult]]


def object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required or [],
    }


def text_schema(maximum: int = 300) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": maximum}


class InformationProvider:
    provider_id = "local-information"

    def __init__(
        self, path: Path, secrets: SecretStore, tasks: TaskService, scope: Scope, execute: Execute
    ) -> None:
        self.store = InformationStore(path)
        self.secrets = secrets
        self.scope = scope
        self.execute = execute
        self.notes = NotesService(self.store)
        self.google = GoogleCalendarBackend(secrets)
        self.calendar = CalendarService(self.store, self.google)
        self.research = ResearchService(self.store, self.notes, self._search)
        self.briefing = BriefingService(self.notes, tasks, self.calendar, self.research)
        self._active: set[asyncio.Task[Any]] = set()
        self._owners: dict[asyncio.Task[Any], str] = {}

    async def start(self) -> None:
        await self.store.recover()

    async def close(self) -> None:
        workers = tuple(self._active - {asyncio.current_task()})
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.provider_id,
            status=ProviderHealthStatus.READY,
            checked_at=datetime.now(UTC),
            detail="Local information ready; calendar stays disconnected until "
            "explicitly authorized.",
        )

    async def user(self, session: str) -> str:
        _, user = await self.scope(session)
        if user is None:
            raise ValueError(
                "create or select a local user profile before storing private information"
            )
        return user

    async def _search(
        self, session: str, query: str, cancel: CancellationToken
    ) -> ToolExecutionResult:
        from .agent_loop import TOOL_BUDGET

        budget = TOOL_BUDGET.get()
        if budget is not None:
            if budget[0] <= 0:
                raise ValueError("outer request tool budget exhausted")
            budget[0] -= 1
        return await self.execute(
            tool_name="mcp.tavily.tavily-search",
            arguments={"query": query},
            session_id=session,
            requested_by="bounded-research",
            cancellation=cancel,
        )

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        ident = {"record_id": text_schema(100)}
        change = NoteChange.model_json_schema()
        change["properties"].pop("action")
        change["required"] = [key for key in change.get("required", []) if key != "action"]
        queries = {"type": "array", "items": text_schema(), "minItems": 1, "maxItems": 3}
        specifications = [
            ("notes.list", object_schema({"after": text_schema(100)}), False),
            (
                "notes.read",
                object_schema({**ident, "page": {"type": "integer", "minimum": 1}}, ["record_id"]),
                False,
            ),
            (
                "notes.preview",
                object_schema({**ident, "page": {"type": "integer", "minimum": 1}}, ["record_id"]),
                False,
            ),
            ("calendar.connections", object_schema({}), False),
            (
                "research.answer",
                object_schema(
                    {
                        "run_id": text_schema(100),
                        "claims": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 5,
                            "items": object_schema(
                                {
                                    "text": text_schema(500),
                                    "source_ids": {
                                        "type": "array",
                                        "items": text_schema(10),
                                        "minItems": 1,
                                        "maxItems": 5,
                                    },
                                },
                                ["text", "source_ids"],
                            ),
                        },
                    },
                    ["run_id", "claims"],
                ),
                False,
            ),
            *((f"notes.{op}", change, True) for op in ("create", "update", "delete")),
            (
                "checklists.set_item",
                object_schema(
                    {
                        **ident,
                        "revision": {"type": "integer", "minimum": 1},
                        "item_id": text_schema(100),
                        "completed": {"type": "boolean"},
                    },
                    ["record_id", "revision", "item_id", "completed"],
                ),
                True,
            ),
            (
                "calendar.list_events",
                object_schema(
                    {
                        "connection_id": text_schema(100),
                        "start": text_schema(100),
                        "end": text_schema(100),
                        "timezone": text_schema(100),
                    },
                    ["connection_id", "start", "end", "timezone"],
                ),
                False,
            ),
            ("calendar.propose_change", CalendarChange.model_json_schema(), True),
            (
                "calendar.operation_status",
                object_schema({"operation_id": text_schema(100)}, ["operation_id"]),
                False,
            ),
            ("research.search", object_schema({"queries": queries}, ["queries"]), True),
            (
                "research.save_note",
                object_schema(
                    {
                        "run_id": text_schema(100),
                        "title": text_schema(200),
                        "summary": text_schema(8000),
                        "citations": {
                            "type": "array",
                            "items": text_schema(10),
                            "minItems": 1,
                            "maxItems": 10,
                        },
                    },
                    ["run_id", "title", "summary", "citations"],
                ),
                True,
            ),
            (
                "briefing.build",
                object_schema(
                    {
                        "timezone": text_schema(100),
                        "note_ids": {"type": "array", "items": text_schema(100), "maxItems": 10},
                        "connection_id": text_schema(100),
                        "research_queries": {**queries, "maxItems": 1},
                    },
                    ["timezone"],
                ),
                True,
            ),
        ]
        calendar_read = next(
            schema for name, schema, _ in specifications if name == "calendar.list_events"
        )
        specifications.append(
            (
                "calendar.suggest_time",
                {
                    **calendar_read,
                    "properties": {
                        **calendar_read["properties"],
                        "minutes": {"type": "integer", "minimum": 1, "maximum": 240},
                    },
                },
                False,
            )
        )
        return tuple(
            ToolDefinition(
                name=name,
                version="1.0.0",
                description={
                    "notes.list": "List this user's saved note IDs and titles, 20 per "
                    "page; use next_after.",
                    "notes.read": "Read a saved note by ID. Large notes have numbered "
                    "pages; read all relevant pages.",
                    "notes.preview": "Read the exact pending note change before the user "
                    "confirms it; supports pages.",
                    "notes.create": "On explicit request, preview a new private "
                    "note/checklist. Does not save the final note.",
                    "notes.update": "Preview replacement note content using its latest "
                    "revision. Preserve unchanged checklist IDs.",
                    "notes.delete": "Preview deletion of the exact note and revision; only "
                    "the user's direct confirmation deletes it.",
                    "checklists.set_item": "Preview checking/unchecking one stable checklist item "
                    "ID at the current note revision.",
                    "calendar.connections": "List the user's explicitly authorized calendars and "
                    "read/write modes; no credentials.",
                    "calendar.list_events": "Read an explicit dated interval and named time zone, "
                    "up to 31 days. Incomplete is not empty or free.",
                    "calendar.suggest_time": (
                        "Suggest slots from a complete calendar read. "
                        "Nothing is reserved; supply interval, zone and duration."
                    ),
                    "calendar.propose_change": "Preview one exact event create/update/cancel; no "
                    "attendees/recurrence. Only the user's direct "
                    "confirmation dispatches.",
                    "calendar.operation_status": "Read the saved result of a reviewed calendar "
                    "operation. Never repeat an uncertain write.",
                    "research.search": "Search one to three explicit public queries within 30 "
                    "seconds using approved Tavily; return real source IDs "
                    "and excerpts.",
                    "research.answer": "Render up to five cited claims from a research run. "
                    "Unknown IDs fail; interpretations are qualified; "
                    "return dated references.",
                    "research.save_note": "Only on explicit request: preview saving a cited "
                    "research note. Repeated saves for this run reuse its "
                    "preview.",
                    "briefing.build": "On request only: today's local reminders and selected "
                    "checklist IDs, optional calendar and public search. "
                    "Offline text works; no automatic saving.",
                }[name],
                input_schema=schema,
                output_schema={"type": "object"},
                risk=RiskLevel.LOW if write else RiskLevel.READ_ONLY,
                default_timeout_seconds=35.0
                if name.startswith(("research.", "briefing."))
                else 18.0,
                idempotent=not write,
                cancellable=True,
                confirmation_required=False,
                source=self.provider_id,
            )
            for name, schema, write in specifications
        )

    async def call(
        self, invocation: ToolInvocation, cancellation: CancellationToken
    ) -> ToolExecutionResult:
        call = invocation.call
        definition = next(
            (item for item in await self.list_tools() if item.name == call.name), None
        )
        if definition is None:
            raise KeyError("unknown information tool")
        try:
            Draft202012Validator(definition.input_schema).validate(call.arguments)
            data = await self.action(invocation.session_id, call.name, call.arguments, cancellation)
            # Bound model projections; direct controllers can read full records.
            if (
                "external_untrusted_content" in data
                and "events" in data["external_untrusted_content"]
            ):
                events = data["external_untrusted_content"]["events"]
                if len(events) > 20:
                    data = {
                        **data,
                        "complete": False,
                        "warning": "Model view limited to 20 events; narrow the interval. "
                        "No free-slot conclusion.",
                        "external_untrusted_content": {"events": events[:20]},
                    }
            if call.name == "briefing.build":
                data = {
                    key: data[key]
                    for key in ("text", "spoken_summary", "checked_at", "interval", "saved")
                }
            if len(json.dumps(data, ensure_ascii=False)) > 16000:
                data = {
                    key: data[key]
                    for key in ("record_id", "kind", "revision", "executed", "instruction")
                    if key in data
                } | {
                    "truncated": True,
                    "instruction": "Read the full exact preview with /info notes.preview "
                    "before confirming. Do not repeat the edit.",
                }
        except asyncio.CancelledError:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.CANCELLED,
                error="Information request cancelled; no further dispatch.",
            )
        except Exception as exc:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.FAILED,
                error=f"Information request refused ({type(exc).__name__}): "
                + (
                    str(exc)[:400]
                    if isinstance(exc, (ValueError, KeyError, PermissionError))
                    else "Source unavailable."
                ),
                definitely_not_executed=False,
            )
        return ToolExecutionResult(
            call_id=call.call_id,
            tool_name=call.name,
            status=ToolExecutionStatus.SUCCEEDED,
            data=data,
        )

    async def action(
        self,
        session: str,
        operation: str,
        args: dict[str, Any],
        cancel: CancellationToken,
        *,
        trusted: bool = False,
    ) -> dict[str, Any]:
        if cancel.cancelled:
            raise asyncio.CancelledError
        definition = next(
            (item for item in await self.list_tools() if item.name == operation), None
        )
        if definition is not None:
            Draft202012Validator(definition.input_schema).validate(args)
        user = await self.user(session)
        worker = asyncio.current_task()
        assert worker is not None
        already_tracked = worker in self._active
        self._active.add(worker)
        self._owners[worker] = user

        async def stop_on_cancel() -> None:
            await cancel.wait()
            worker.cancel()

        watcher = asyncio.create_task(stop_on_cancel())
        try:
            async with asyncio.timeout(40):
                data = await self._action(user, session, operation, args, cancel, trusted=trusted)
            if cancel.cancelled:
                raise asyncio.CancelledError
            if user != await self.user(session):
                raise ValueError("active user changed; old user's delayed result was withheld")
            if data.get("kind") in {"note", "note_preview"}:
                data = self._note_page(data, args.get("page", 1))
            return data
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
            if not already_tracked:
                self._owners.pop(worker, None)
                self._active.discard(worker)

    async def _action(
        self,
        user: str,
        session: str,
        operation: str,
        args: dict[str, Any],
        cancel: CancellationToken,
        *,
        trusted: bool,
    ) -> dict[str, Any]:
        if operation == "notes.list":
            return await self.notes.list(user, **args)
        if operation in {"notes.read", "notes.preview"}:
            record = await self.store.action(user, "get", record_id=args["record_id"])
            expected = "note" if operation == "notes.read" else "note_preview"
            if record["kind"] != expected:
                raise ValueError("unexpected note record kind")
            return self._note_page(record, args.get("page", 1))
        if operation == "research.answer":
            return await self.research.answer(user, **args)
        if operation in {"notes.create", "notes.update", "notes.delete"}:
            change = NoteChange.model_validate_json(
                json.dumps({**args, "action": operation.split(".")[1]})
            )
            return await self.notes.propose(user, session, change)
        if operation == "checklists.set_item":
            return await self.notes.set_item(user, session, **args)
        if operation == "calendar.suggest_time":
            return await self.calendar.suggest_time(user, **args)
        if operation == "calendar.list_events":
            return await self.calendar.list_events(user, **args)
        if operation == "calendar.propose_change":
            return await self.calendar.propose(
                user, session, CalendarChange.model_validate_json(json.dumps(args))
            )
        if operation == "calendar.operation_status":
            return await self.calendar.status(user, **args)
        if operation == "research.search":
            return await self.research.run(user, session, args["queries"], cancel)
        if operation == "research.save_note":
            return await self.research.save_preview(user, session, **args)
        if operation == "briefing.build":
            return await self.briefing.build(user, session, cancel=cancel, **args)
        if operation == "calendar.connections":
            page = await self.store.action(user, "list", kind="calendar_connection")
            return {
                "connections": [
                    {
                        "connection_id": r["record_id"],
                        "revision": r["revision"],
                        **{
                            key: r["payload"][key]
                            for key in ("calendar_id", "account_label", "enabled", "write_enabled")
                        },
                    }
                    for r in page["records"]
                ]
            }
        if not trusted:
            raise PermissionError("this operation requires a direct trusted controller")
        if operation == "notes.confirm":
            return await self.notes.confirm(user, session, **args)
        if operation == "calendar.confirm":
            return await self.calendar.confirm(user, session, **args)
        if operation == "calendar.cancel":
            return await self.calendar.cancel(user, **args)
        if operation == "calendar.reconcile":
            return await self.calendar.status(user, reconcile=True, **args)
        if operation == "calendar.connect":
            calendar_id = args["calendar_id"]
            if not isinstance(calendar_id, str) or "@" not in calendar_id or len(calendar_id) > 300:
                raise ValueError(
                    "copy the explicit Google calendar ID; the alias primary is not accepted"
                )
            credential = args["credential"]
            if not isinstance(credential, dict) or any(
                not isinstance(credential.get(key), str) or not 1 <= len(credential[key]) <= 8192
                for key in ("client_id", "client_secret", "refresh_token", "scope")
            ):
                raise ValueError("invalid calendar credential")
            scope = WRITE_SCOPE if args.get("write") is True else READ_SCOPE
            if credential.get("scope") != scope:
                raise ValueError("credential scope does not match selected mode")
            reference = "NINJA_CAL_" + uuid.uuid4().hex.upper()
            self.secrets.set(reference, json.dumps(credential))
            try:
                record = await self.store.action(
                    user,
                    "create",
                    kind="calendar_connection",
                    payload={
                        "calendar_id": calendar_id,
                        "account_label": str(args["account_label"])[:200],
                        "secret_ref": reference,
                        "enabled": True,
                        "write_enabled": args.get("write") is True,
                    },
                )
            except BaseException:
                self.secrets.delete(reference)
                raise
            return {
                "connection_id": record["record_id"],
                "calendar_id": calendar_id,
                "write_enabled": args.get("write") is True,
            }
        if operation == "calendar.disconnect":
            record = await self.calendar.connection(user, args["connection_id"])
            await self.store.action(
                user,
                "update",
                record_id=record["record_id"],
                revision=record["revision"],
                payload={**record["payload"], "enabled": False},
            )
            await self._stop_user_work(user)
            self.google.forget(record["payload"]["secret_ref"])
            self.secrets.delete(record["payload"]["secret_ref"])
            return {"disconnected": True, "remote_events_unchanged": True}
        raise ValueError("unknown information operation")

    @staticmethod
    def _note_page(record: dict[str, Any], page: int) -> dict[str, Any]:
        if type(page) is not int or page < 1:
            raise ValueError("page must be a positive integer")
        raw = json.dumps(record, ensure_ascii=False, indent=2)
        total = max(1, (len(raw) + 7999) // 8000)
        if page > total:
            raise ValueError("page is outside this note")
        if total == 1:
            return record
        return {
            "record_id": record["record_id"],
            "revision": record["revision"],
            "page": page,
            "pages": total,
            "content_chunk": raw[(page - 1) * 8000 : page * 8000],
            "review_hash": record["payload"].get("review_hash"),
            "instruction": "Read every page of this revision before confirming. "
            "Concatenate content_chunk in page order for the exact record.",
        }

    async def _stop_user_work(self, user: str) -> None:
        workers = [
            worker
            for worker, owner in self._owners.items()
            if owner == user and worker is not asyncio.current_task()
        ]
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)

    async def disconnect_user(self, user: str) -> None:
        await self._stop_user_work(user)
        after = ""
        while True:
            page = await self.store.action(
                user, "list", kind="calendar_connection", limit=100, after=after
            )
            for record in page["records"]:
                if record["payload"]["enabled"]:
                    await self._action(
                        user,
                        "profile-deletion",
                        "calendar.disconnect",
                        {"connection_id": record["record_id"]},
                        CancellationToken(),
                        trusted=True,
                    )
                else:
                    self.google.forget(record["payload"]["secret_ref"])
                    self.secrets.delete(record["payload"]["secret_ref"])
            if not page["next_after"]:
                break
            after = page["next_after"]
