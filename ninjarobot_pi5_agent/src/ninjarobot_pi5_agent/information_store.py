"""Owned bounded records in the existing database; compare revisions before edits."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class InformationStore:
    """Short transactions, no network calls or model-selected ownership."""

    def __init__(self, path: Path) -> None:
        self.path = path

    async def action(
        self,
        user: str,
        operation: str,
        *,
        kind: str = "",
        record_id: str = "",
        revision: int = 0,
        payload: dict[str, Any] | None = None,
        after: str = "",
        limit: int = 20,
    ) -> dict[str, Any]:
        if not user or not 1 <= limit <= 100:
            raise ValueError("a resolved local user and bounded limit are required")
        if payload is not None and len(json.dumps(payload).encode()) > 65536:
            raise ValueError("information record exceeds 64 KiB")
        return await asyncio.to_thread(
            self._action, user, operation, kind, record_id, revision, payload, after, limit
        )

    def _action(
        self,
        user: str,
        operation: str,
        kind: str,
        record_id: str,
        revision: int,
        payload: dict[str, Any] | None,
        after: str,
        limit: int,
    ) -> dict[str, Any]:
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if not connection.execute(
                    "SELECT 1 FROM users WHERE user_id=?", (user,)
                ).fetchone():
                    raise ValueError("local user no longer exists")
                if operation == "list":
                    rows = connection.execute(
                        "SELECT * FROM assistant_records WHERE user_id=? AND kind=? AND "
                        "record_id>? "
                        "ORDER BY record_id LIMIT ?",
                        (user, kind, after, limit + 1),
                    ).fetchall()
                    return {
                        "records": [self._decode(row) for row in rows[:limit]],
                        "next_after": rows[limit - 1]["record_id"] if len(rows) > limit else None,
                    }
                if operation == "create":
                    if kind not in {
                        "note",
                        "note_preview",
                        "research",
                        "calendar_connection",
                        "calendar_operation",
                    }:
                        raise ValueError("unknown information record kind")
                    count = connection.execute(
                        "SELECT COUNT(*) FROM assistant_records WHERE user_id=? AND kind=?",
                        (user, kind),
                    ).fetchone()[0]
                    if count >= 1000:
                        raise ValueError("record limit reached; review and remove old records")
                    record_id = record_id or "info-" + uuid.uuid4().hex
                    now = datetime.now(UTC).isoformat()
                    connection.execute(
                        "INSERT INTO assistant_records VALUES (?,?,?,?,?,?,?)",
                        (record_id, user, kind, 1, json.dumps(payload or {}), now, now),
                    )
                    return self._decode(
                        connection.execute(
                            "SELECT * FROM assistant_records WHERE user_id=? AND record_id=?",
                            (user, record_id),
                        ).fetchone()
                    )
                row = connection.execute(
                    "SELECT * FROM assistant_records WHERE user_id=? AND record_id=?",
                    (user, record_id),
                ).fetchone()
                if row is None:
                    raise KeyError("unknown owned information record")
                if operation == "get":
                    return self._decode(row)
                if operation == "confirm_note":
                    approval = json.loads(row["payload_json"])
                    approval_time = datetime.now(UTC)
                    if (
                        row["kind"] != "note_preview"
                        or approval.get("state") != "pending"
                        or payload is None
                        or approval.get("session") != payload.get("session")
                        or approval.get("review_hash") != payload.get("review_hash")
                        or approval_time >= datetime.fromisoformat(approval["expires_at"])
                        or approval_time < datetime.fromisoformat(row["created_at"])
                    ):
                        raise ValueError(
                            "note preview is expired, changed, consumed or belongs to "
                            "another session"
                        )
                    change = approval["change"]
                    ident = change["record_id"]
                    if change["action"] == "create":
                        if (
                            connection.execute(
                                "SELECT COUNT(*) FROM assistant_records WHERE user_id=? "
                                "AND kind='note'",
                                (user,),
                            ).fetchone()[0]
                            >= 1000
                        ):
                            raise ValueError("note limit reached")
                        connection.execute(
                            "INSERT INTO assistant_records VALUES (?,?,?,?,?,?,?)",
                            (
                                ident,
                                user,
                                "note",
                                1,
                                json.dumps(change["content"]),
                                approval_time.isoformat(),
                                approval_time.isoformat(),
                            ),
                        )
                    else:
                        current = connection.execute(
                            "SELECT revision FROM assistant_records WHERE user_id=? AND "
                            "record_id=? AND kind='note'",
                            (user, ident),
                        ).fetchone()
                        if current is None or current["revision"] != change["revision"]:
                            raise ValueError("note changed; read and review its current revision")
                        if change["action"] == "delete":
                            connection.execute(
                                "DELETE FROM assistant_records WHERE user_id=? AND record_id=?",
                                (user, ident),
                            )
                        else:
                            connection.execute(
                                "UPDATE assistant_records SET "
                                "payload_json=?,revision=revision+1,updated_at=? WHERE "
                                "user_id=? AND record_id=?",
                                (
                                    json.dumps(change["content"]),
                                    approval_time.isoformat(),
                                    user,
                                    ident,
                                ),
                            )
                    approval["state"] = "completed"
                    connection.execute(
                        "UPDATE assistant_records SET "
                        "payload_json=?,revision=revision+1,updated_at=? WHERE user_id=? "
                        "AND record_id=?",
                        (json.dumps(approval), approval_time.isoformat(), user, record_id),
                    )
                    if change["action"] == "delete":
                        return {"record_id": ident, "deleted": True}
                    return self._decode(
                        connection.execute(
                            "SELECT * FROM assistant_records WHERE user_id=? AND record_id=?",
                            (user, ident),
                        ).fetchone()
                    )
                if row["revision"] != revision:
                    raise ValueError("record changed; read and review its current revision")
                if operation == "update":
                    connection.execute(
                        "UPDATE assistant_records SET "
                        "payload_json=?,revision=revision+1,updated_at=? "
                        "WHERE user_id=? AND record_id=? AND revision=?",
                        (
                            json.dumps(payload or {}),
                            datetime.now(UTC).isoformat(),
                            user,
                            record_id,
                            revision,
                        ),
                    )
                    return self._decode(
                        connection.execute(
                            "SELECT * FROM assistant_records WHERE user_id=? AND record_id=?",
                            (user, record_id),
                        ).fetchone()
                    )
                if operation == "delete":
                    connection.execute(
                        "DELETE FROM assistant_records WHERE user_id=? AND record_id=? "
                        "AND revision=?",
                        (user, record_id, revision),
                    )
                    return {"record_id": record_id, "deleted": True}
                raise ValueError("unknown information operation")
        finally:
            connection.close()

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "record_id": row["record_id"],
            "kind": row["kind"],
            "revision": row["revision"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "payload": json.loads(row["payload_json"]),
        }

    async def recover(self) -> None:
        """Expire pending authority on startup; unknown dispatched effects remain unknown."""

        def run() -> None:
            connection = sqlite3.connect(
                self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5
            )
            try:
                with connection:
                    for ident, kind, raw in connection.execute(
                        "SELECT record_id,kind,payload_json FROM assistant_records "
                        "WHERE kind IN ('calendar_operation','note_preview')"
                    ).fetchall():
                        payload = json.loads(raw)
                        if payload.get("state") in {"pending", "dispatching"}:
                            payload["state"] = (
                                "uncertain" if payload["state"] == "dispatching" else "expired"
                            )
                            connection.execute(
                                "UPDATE assistant_records SET payload_json=?,revision=revision+1 "
                                "WHERE record_id=?",
                                (json.dumps(payload), ident),
                            )
                    cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
                    connection.execute(
                        "DELETE FROM assistant_records WHERE kind IN ('research','note_preview') "
                        "AND updated_at<?",
                        (cutoff,),
                    )
            finally:
                connection.close()

        await asyncio.to_thread(run)
