"""Reviewable private notes and stable checklist items; no model approval endpoint."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator

from .information_store import InformationStore
from .models import AgentContractModel


class ChecklistItem(AgentContractModel):
    item_id: Annotated[str, StringConstraints(pattern=r"^item-[a-f0-9]{32}$")] = Field(
        default_factory=lambda: "item-" + uuid.uuid4().hex
    )
    text: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    completed: bool = False


class NoteContent(AgentContractModel):
    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    body: Annotated[str, StringConstraints(max_length=16384)] = ""
    items: Annotated[tuple[ChecklistItem, ...], Field(max_length=100)] = ()
    sources: Annotated[tuple[dict[str, Any], ...], Field(max_length=10)] = ()

    @model_validator(mode="after")
    def bounded(self) -> NoteContent:
        if len(self.body.encode()) > 16384 or len(self.model_dump_json().encode()) > 32768:
            raise ValueError("note exceeds its byte limit")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("checklist item IDs must be unique")
        return self


class NoteChange(AgentContractModel):
    action: Literal["create", "update", "delete"]
    record_id: str = ""
    revision: Annotated[int, Field(ge=0)] = 0
    content: NoteContent | None = None


def fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class NotesService:
    def __init__(self, store: InformationStore) -> None:
        self.store = store

    async def read(self, user: str, record_id: str) -> dict[str, Any]:
        record = await self.store.action(user, "get", record_id=record_id)
        if record["kind"] != "note":
            raise ValueError("record is not a note")
        return record

    async def list(self, user: str, *, after: str = "") -> dict[str, Any]:
        page = await self.store.action(user, "list", kind="note", after=after)
        return {
            "notes": [
                {
                    "record_id": r["record_id"],
                    "revision": r["revision"],
                    "title": r["payload"]["title"],
                    "preview": r["payload"].get("body", "")[:200],
                    "items": len(r["payload"].get("items", [])),
                }
                for r in page["records"]
            ],
            "next_after": page["next_after"],
        }

    async def propose(self, user: str, session: str, change: NoteChange) -> dict[str, Any]:
        data = change.model_dump(mode="json")
        if change.action == "create":
            if change.record_id or change.revision:
                raise ValueError("new notes cannot choose an existing identifier or revision")
            data["record_id"] = "note-" + uuid.uuid4().hex
        else:
            record = await self.read(user, change.record_id)
            if record["revision"] != change.revision:
                raise ValueError("note changed; read the latest revision first")
        if (change.action == "delete") != (change.content is None):
            raise ValueError("create/update requires content; delete must not supply content")
        payload = {
            "change": data,
            "session": session,
            "state": "pending",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        payload["review_hash"] = fingerprint(payload)
        record = await self.store.action(user, "create", kind="note_preview", payload=payload)
        return {
            **record,
            "executed": False,
            "instruction": "Review this exact change; only a direct notes confirm command "
            "applies it.",
        }

    async def set_item(
        self, user: str, session: str, record_id: str, revision: int, item_id: str, completed: bool
    ) -> dict[str, Any]:
        record = await self.read(user, record_id)
        content = NoteContent.model_validate_json(json.dumps(record["payload"]))
        if item_id not in {item.item_id for item in content.items}:
            raise ValueError("unknown stable checklist item ID")
        content = content.model_copy(
            update={
                "items": tuple(
                    item.model_copy(update={"completed": completed})
                    if item.item_id == item_id
                    else item
                    for item in content.items
                )
            }
        )
        return await self.propose(
            user,
            session,
            NoteChange(action="update", record_id=record_id, revision=revision, content=content),
        )

    async def confirm(
        self, user: str, session: str, preview_id: str, review_hash: str
    ) -> dict[str, Any]:
        # The edit and consumed preview commit together in one short SQLite transaction.
        return await self.store.action(
            user,
            "confirm_note",
            record_id=preview_id,
            payload={"session": session, "review_hash": review_hash},
        )
