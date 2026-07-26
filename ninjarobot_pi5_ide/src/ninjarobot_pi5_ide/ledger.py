"""Small durable SQLite ledger for authoritative IDE action state."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .models import ActionRecord, ActionRequest, ActionResult, ActionStatus


class ActionLedger:
    """Persist action requests and results without storing hardware objects."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self._path, check_same_thread=False)
        self._closed = False
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS action_ledger (
                    action_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    accepted_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def reserve(self, request: ActionRequest, accepted_at: datetime) -> tuple[ActionRecord, bool]:
        """Atomically reserve an action, returning an existing match when repeated."""
        record = ActionRecord(
            request=request,
            status=ActionStatus.ACCEPTED,
            accepted_at=accepted_at,
            updated_at=accepted_at,
        )
        with self._lock, self._connection:
            try:
                self._connection.execute(
                    """
                    INSERT INTO action_ledger (
                        action_id, idempotency_key, request_json, status,
                        result_json, accepted_at, updated_at
                    ) VALUES (?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        request.action_id,
                        request.idempotency_key,
                        request.model_dump_json(),
                        record.status.value,
                        accepted_at.isoformat(),
                        accepted_at.isoformat(),
                    ),
                )
                return record, True
            except sqlite3.IntegrityError:
                by_action = self._get_by_field("action_id", request.action_id)
                by_key = self._get_by_field("idempotency_key", request.idempotency_key)
                if (
                    by_action is not None
                    and by_key is not None
                    and by_action.request.action_id != by_key.request.action_id
                ):
                    raise ValueError("action_id and idempotency_key belong to different actions")
                existing = by_action or by_key
                if existing is None:
                    raise RuntimeError("action reservation conflicted without an existing record")
                return existing, False

    def mark_running(self, action_id: str, updated_at: datetime) -> ActionRecord:
        """Persist that adapter execution has begun."""
        return self._update(action_id, ActionStatus.RUNNING, updated_at, result=None)

    def finish(self, result: ActionResult) -> ActionRecord:
        """Persist one terminal result."""
        return self._update(
            result.action_id,
            result.status,
            result.finished_at,
            result=result,
        )

    def get(self, action_id: str) -> ActionRecord | None:
        """Look up an action by its public identifier."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM action_ledger WHERE action_id = ?",
                (action_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def list(self, limit: int = 100) -> tuple[ActionRecord, ...]:
        """Return newest action records first."""
        if limit < 1 or limit > 1000:
            raise ValueError("ledger list limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM action_ledger
                ORDER BY accepted_at DESC, action_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def unfinished(self) -> tuple[ActionRecord, ...]:
        """Return records that need deterministic restart recovery."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM action_ledger
                WHERE status IN (?, ?)
                ORDER BY accepted_at, action_id
                """,
                (ActionStatus.ACCEPTED.value, ActionStatus.RUNNING.value),
            ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def close(self) -> None:
        """Close the database safely and idempotently."""
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def _get_by_field(self, field: str, value: str) -> ActionRecord | None:
        if field not in {"action_id", "idempotency_key"}:
            raise ValueError(f"unsupported action-ledger field: {field}")
        row = self._connection.execute(
            f"SELECT * FROM action_ledger WHERE {field} = ? LIMIT 1",
            (value,),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def _update(
        self,
        action_id: str,
        status: ActionStatus,
        updated_at: datetime,
        *,
        result: ActionResult | None,
    ) -> ActionRecord:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE action_ledger
                SET status = ?, result_json = ?, updated_at = ?
                WHERE action_id = ?
                """,
                (
                    status.value,
                    result.model_dump_json() if result is not None else None,
                    updated_at.isoformat(),
                    action_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown action: {action_id}")
            row = self._connection.execute(
                "SELECT * FROM action_ledger WHERE action_id = ?",
                (action_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError(f"updated action disappeared: {action_id}")
        return self._row_to_record(row)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ActionRecord:
        result_json = row["result_json"]
        return ActionRecord(
            request=ActionRequest.model_validate_json(row["request_json"]),
            status=ActionStatus(row["status"]),
            result=(
                ActionResult.model_validate_json(result_json) if result_json is not None else None
            ),
            accepted_at=datetime.fromisoformat(row["accepted_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
