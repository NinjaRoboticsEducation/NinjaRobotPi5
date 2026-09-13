"""Exact reviewed calendar changes, conservative recovery and bounded schedule reads."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import StringConstraints, model_validator

from .calendar_google import CalendarHTTPError
from .information_store import InformationStore
from .models import AgentContractModel
from .notes_service import fingerprint


def interval(start: str, end: str, timezone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    values = [datetime.fromisoformat(value) for value in (start, end)]
    for value in values:
        if value.tzinfo is None or value.astimezone(zone).utcoffset() != value.utcoffset():
            raise ValueError("include an explicit UTC offset matching the selected time zone")
    first, last = (value.astimezone(UTC) for value in values)
    if not timedelta(0) < last - first <= timedelta(days=31):
        raise ValueError("choose an increasing interval of at most 31 days")
    return first, last


class CalendarEvent(AgentContractModel):
    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    start: str
    end: str
    timezone: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    all_day: bool = False
    description: Annotated[str, StringConstraints(max_length=2000)] = ""
    location: Annotated[str, StringConstraints(max_length=300)] = ""

    @model_validator(mode="after")
    def times(self) -> CalendarEvent:
        ZoneInfo(self.timezone)
        if self.all_day:
            first, last = date.fromisoformat(self.start), date.fromisoformat(self.end)
            if not timedelta(0) < last - first <= timedelta(days=31):
                raise ValueError("all-day end is exclusive, after start, within 31 days")
        else:
            interval(self.start, self.end, self.timezone)
        return self

    def google(self) -> dict[str, Any]:
        def instant(value: str) -> dict[str, str]:
            return (
                {"date": value} if self.all_day else {"dateTime": value, "timeZone": self.timezone}
            )

        return {
            "summary": self.title,
            "description": self.description,
            "location": self.location,
            "start": instant(self.start),
            "end": instant(self.end),
        }


class CalendarChange(AgentContractModel):
    action: Literal["create", "update", "cancel"]
    connection_id: str
    event_id: str = ""
    event: CalendarEvent | None = None

    @model_validator(mode="after")
    def fields(self) -> CalendarChange:
        if (self.action == "cancel") != (self.event is None):
            raise ValueError("create/update needs event content; cancel does not accept it")
        if (self.action == "create") == bool(self.event_id):
            raise ValueError("only update/cancel takes an existing event ID")
        return self


class CalendarBackend(Protocol):
    async def request(
        self,
        connection: dict[str, Any],
        method: str,
        *,
        event_id: str = "",
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        etag: str | None = None,
        max_bytes: int = 1048576,
    ) -> dict[str, Any]: ...


class CalendarService:
    def __init__(self, store: InformationStore, backend: CalendarBackend) -> None:
        self.store = store
        self.backend = backend
        self._inflight: dict[tuple[str, str], asyncio.Task[Any]] = {}

    async def connection(self, user: str, ident: str, *, write: bool = False) -> dict[str, Any]:
        record = await self.store.action(user, "get", record_id=ident)
        data = record["payload"]
        if record["kind"] != "calendar_connection" or not data.get("enabled"):
            raise ValueError("calendar connection is disabled or disconnected")
        if write and not data.get("write_enabled"):
            raise PermissionError(
                "calendar connection is read-only; explicit reauthorization is required"
            )
        return record

    async def list_events(
        self, user: str, connection_id: str, start: str, end: str, timezone: str
    ) -> dict[str, Any]:
        first, last = interval(start, end, timezone)
        connection = await self.connection(user, connection_id)
        events = []
        page = ""
        used = 0
        complete = False
        unavailable = None
        try:
            async with asyncio.timeout(15):
                for _ in range(5):
                    params = {
                        "timeMin": first.isoformat(),
                        "timeMax": last.isoformat(),
                        "timeZone": timezone,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 40,
                    }
                    if page:
                        params["pageToken"] = page
                    for attempt in range(3):
                        try:
                            result = await self.backend.request(
                                connection["payload"],
                                "GET",
                                params=params,
                                max_bytes=1048576 - used,
                            )
                            break
                        except CalendarHTTPError as exc:
                            if exc.status not in {429, 500, 502, 503} or attempt == 2:
                                raise
                            await asyncio.sleep(0.2 * (attempt + 1))
                    used += len(json.dumps(result).encode())
                    if used > 1048576:
                        break
                    for event in result.get("items", []):
                        if not isinstance(event, dict):
                            continue
                        events.append(
                            {
                                "event_id": str(event.get("id", ""))[:300],
                                "title": str(event.get("summary", "Untitled"))[:200],
                                "start": self._instant(event.get("start", {})),
                                "end": self._instant(event.get("end", {})),
                                "status": str(event.get("status", ""))[:30],
                                "transparency": str(event.get("transparency", "opaque"))[:30],
                            }
                        )
                        if len(events) >= 200:
                            break
                    page = result.get("nextPageToken", "")
                    if not page:
                        complete = True
                        break
                    if len(events) >= 200:
                        break
        except Exception as exc:
            complete = False
            unavailable = (
                f"HTTP {exc.status}" if isinstance(exc, CalendarHTTPError) else type(exc).__name__
            )
        current = await self.connection(user, connection_id)
        if current["revision"] != connection["revision"]:
            raise ValueError("account changed while calendar was being read")
        return {
            "connection_id": connection_id,
            "calendar_id": connection["payload"]["calendar_id"],
            "timezone": timezone,
            "interval": {"start": start, "end": end},
            "checked_at": datetime.now(UTC).isoformat(),
            "complete": complete,
            "unavailable": unavailable,
            "external_untrusted_content": {"events": events},
            "warning": None if complete else "Incomplete results do not prove a time slot is free.",
        }

    @staticmethod
    def _instant(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {
            key: value[key][:100]
            for key in ("date", "dateTime", "timeZone")
            if isinstance(value.get(key), str)
        }

    async def suggest_time(
        self, user: str, connection_id: str, start: str, end: str, timezone: str, minutes: int = 30
    ) -> dict[str, Any]:
        if type(minutes) is not int or not 1 <= minutes <= 240:
            raise ValueError("duration must be one through 240 minutes")
        result = await self.list_events(user, connection_id, start, end, timezone)
        result["suggestions"] = []
        result["reserved"] = False
        if not result["complete"]:
            return result
        first, last = interval(start, end, timezone)
        zone = ZoneInfo(timezone)
        busy = []
        try:
            for event in result["external_untrusted_content"]["events"]:
                if event["status"] == "cancelled" or event["transparency"] == "transparent":
                    continue
                values = []
                for key in ("start", "end"):
                    point = event[key]
                    if "date" in point:
                        instant = datetime.combine(
                            date.fromisoformat(point["date"]), datetime.min.time(), zone
                        )
                    else:
                        instant = datetime.fromisoformat(point["dateTime"])
                        if instant.tzinfo is None:
                            raise ValueError("event has no offset")
                    values.append(instant.astimezone(UTC))
                if values[1] <= values[0]:
                    raise ValueError("invalid event interval")
                busy.append((max(first, values[0]), min(last, values[1])))
        except (KeyError, ValueError):
            return {
                **result,
                "complete": False,
                "warning": "An event has invalid dates; free time cannot be established.",
            }
        cursor = first
        for left, right in sorted(busy) + [(last, last)]:
            if left - cursor >= timedelta(minutes=minutes):
                result["suggestions"].append(
                    {
                        "start": cursor.astimezone(zone).isoformat(),
                        "end": (cursor + timedelta(minutes=minutes)).astimezone(zone).isoformat(),
                    }
                )
                if len(result["suggestions"]) == 3:
                    break
            cursor = max(cursor, right)
        result["warning"] = (
            "Suggestions only: no time is reserved and the remote calendar can change."
        )
        return result

    async def propose(self, user: str, session: str, change: CalendarChange) -> dict[str, Any]:
        connection = await self.connection(user, change.connection_id, write=True)
        event_id = uuid.uuid4().hex if change.action == "create" else change.event_id
        etag = None
        if change.action != "create":
            # A remote marker alone does not prove this integration created the event.
            known = await self.store.action(user, "list", kind="calendar_operation", limit=100)
            while known["next_after"]:
                page_records = await self.store.action(
                    user, "list", kind="calendar_operation", limit=100, after=known["next_after"]
                )
                known["records"].extend(page_records["records"])
                known["next_after"] = page_records["next_after"]
            if not any(
                r["payload"].get("action") == "create"
                and r["payload"].get("state") == "verified"
                and r["payload"].get("event_id") == event_id
                and r["payload"].get("connection_id") == change.connection_id
                for r in known["records"]
            ):
                raise ValueError(
                    "only previously verified events created by this connection may be changed"
                )
            remote = await self.backend.request(connection["payload"], "GET", event_id=event_id)
            if (
                remote.get("attendees")
                or remote.get("recurrence")
                or remote.get("recurringEventId")
            ):
                raise ValueError("attendees and recurring events are not supported")
            etag = remote.get("etag")
            if not isinstance(etag, str) or not etag:
                raise ValueError("remote event version unavailable; cannot preview a safe change")
        body = change.event.google() if change.event else {}
        payload = {
            "action": change.action,
            "connection_id": change.connection_id,
            "connection_revision": connection["revision"],
            "calendar_id": connection["payload"]["calendar_id"],
            "account_label": connection["payload"]["account_label"],
            "event_id": event_id,
            "body": body,
            "etag": etag,
            "session": session,
            "state": "pending",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        payload["review_hash"] = fingerprint(payload)
        result = await self.store.action(user, "create", kind="calendar_operation", payload=payload)
        return {
            **result,
            "executed": False,
            "instruction": "Review account, calendar, exact change and expiry; only direct "
            "calendar confirm can dispatch.",
        }

    async def confirm(
        self, user: str, session: str, operation_id: str, review_hash: str
    ) -> dict[str, Any]:
        key = (user, operation_id)
        if key in self._inflight:
            raise ValueError("this calendar operation is already running")
        worker = asyncio.current_task()
        assert worker is not None
        self._inflight[key] = worker
        try:
            return await self._confirm(user, session, operation_id, review_hash)
        finally:
            self._inflight.pop(key, None)

    async def _confirm(
        self, user: str, session: str, operation_id: str, review_hash: str
    ) -> dict[str, Any]:
        record = await self.store.action(user, "get", record_id=operation_id)
        data = record["payload"]
        now = datetime.now(UTC)
        if (
            record["kind"] != "calendar_operation"
            or data["state"] != "pending"
            or data["session"] != session
            or data["review_hash"] != review_hash
            or now >= datetime.fromisoformat(data["expires_at"])
            or now < datetime.fromisoformat(record["created_at"])
        ):
            raise ValueError(
                "calendar approval is expired, changed, consumed or belongs to another session"
            )
        connection = await self.connection(user, data["connection_id"], write=True)
        if connection["revision"] != data["connection_revision"]:
            raise ValueError("calendar account changed; make a new preview")
        claimed = await self.store.action(
            user,
            "update",
            record_id=operation_id,
            revision=record["revision"],
            payload={**data, "state": "dispatching"},
        )
        # Receipt is durable before dispatch. Writes are never automatically retried.
        method = {"create": "POST", "update": "PATCH", "cancel": "DELETE"}[data["action"]]
        body = dict(data["body"])
        if data["action"] == "create":
            body["id"] = data["event_id"]
        try:
            current = await self.status(user, operation_id)
            current_connection = await self.connection(user, data["connection_id"], write=True)
            if (
                current["revision"] != claimed["revision"]
                or current_connection["revision"] != connection["revision"]
            ):
                raise ValueError("approval or connection changed before dispatch")
            await self.backend.request(
                connection["payload"],
                method,
                event_id="" if data["action"] == "create" else data["event_id"],
                params={"sendUpdates": "none"},
                body=body if method != "DELETE" else None,
                etag=data["etag"],
            )
            verified = await self._verify(connection["payload"], data)
            state = "verified" if verified else "uncertain"
        except BaseException as exc:
            state = "uncertain"
            try:
                await self.store.action(
                    user,
                    "update",
                    record_id=operation_id,
                    revision=claimed["revision"],
                    payload={**data, "state": state},
                )
            except (KeyError, ValueError):
                pass  # Deleted owner/operation must never be recreated by a callback.
            if isinstance(exc, asyncio.CancelledError):
                raise
            return {
                "operation_id": operation_id,
                "state": state,
                "warning": "An external effect may have occurred. Reconcile the saved ID; "
                "do not repeat the write.",
            }
        return await self.store.action(
            user,
            "update",
            record_id=operation_id,
            revision=claimed["revision"],
            payload={**data, "state": state},
        )

    async def _verify(self, connection: dict[str, Any], data: dict[str, Any]) -> bool:
        try:
            remote = await self.backend.request(connection, "GET", event_id=data["event_id"])
        except CalendarHTTPError as exc:
            return data["action"] == "cancel" and exc.status in {404, 410}
        if data["action"] == "cancel":
            return remote.get("status") == "cancelled"
        if remote.get("id") != data["event_id"] or remote.get("status") == "cancelled":
            return False
        for key, value in data["body"].items():
            actual = remote.get(key, "" if isinstance(value, str) else {})
            if key in {"start", "end"}:
                if "date" in value:
                    if actual.get("date") != value["date"]:
                        return False
                elif datetime.fromisoformat(actual.get("dateTime", "")) != datetime.fromisoformat(
                    value["dateTime"]
                ):
                    return False
            elif actual != value:
                return False
        return True

    async def status(
        self, user: str, operation_id: str, *, reconcile: bool = False
    ) -> dict[str, Any]:
        record = await self.store.action(user, "get", record_id=operation_id)
        if record["kind"] != "calendar_operation":
            raise ValueError("not a calendar operation")
        data = record["payload"]
        if reconcile and data["state"] == "uncertain":
            connection = await self.connection(user, data["connection_id"])
            if await self._verify(connection["payload"], data):
                record = await self.store.action(
                    user,
                    "update",
                    record_id=operation_id,
                    revision=record["revision"],
                    payload={**data, "state": "verified"},
                )
        return record

    async def cancel(self, user: str, operation_id: str) -> dict[str, Any]:
        record = await self.status(user, operation_id)
        data = record["payload"]
        state = (
            "cancelled"
            if data["state"] == "pending"
            else "uncertain"
            if data["state"] == "dispatching"
            else data["state"]
        )
        result = await self.store.action(
            user,
            "update",
            record_id=operation_id,
            revision=record["revision"],
            payload={**data, "state": state},
        )
        worker = self._inflight.get((user, operation_id))
        if worker is not None and worker is not asyncio.current_task():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        return {**result, "warning": "Cancelling after dispatch does not undo a remote change."}
