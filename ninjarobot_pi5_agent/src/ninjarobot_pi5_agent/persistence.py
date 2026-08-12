"""Owner-only SQLite conversation persistence with bounded retention."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import Field

from .memory_migrations import migrate_agent_database
from .models import (
    AgentContractModel,
    Identifier,
    MessageRole,
    ModelMessage,
    SessionRecord,
    ToolCall,
)


class StoredMessage(AgentContractModel):
    """One persisted conversation message."""

    message_id: Identifier
    session_id: Identifier
    user_id: Identifier
    message: ModelMessage
    created_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)


class ConversationStore:
    """Small SQLite store that owns no model-provider state."""

    def __init__(self, path: str | Path, *, retention_days: int = 7) -> None:
        if not 1 <= retention_days <= 365:
            raise ValueError("retention_days must be between 1 and 365")
        self._path = Path(path).expanduser()
        self._retention = timedelta(days=retention_days)
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        """Return the expanded database path."""
        return self._path

    async def start(self) -> None:
        """Create the owner-only database and schema."""
        await asyncio.to_thread(self._start_sync)

    async def create_session(
        self,
        session_id: str,
        *,
        user_id: str = "local-user",
        now: datetime | None = None,
    ) -> SessionRecord:
        """Create a session without overwriting an existing identity."""
        return await asyncio.to_thread(
            self._create_session_sync,
            session_id,
            user_id,
            now or datetime.now(UTC),
        )

    async def append_message(
        self,
        session_id: str,
        message: ModelMessage,
        *,
        message_id: str,
        user_id: str | None = None,
        now: datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredMessage:
        """Append one message and advance the session update time."""
        return await asyncio.to_thread(
            self._append_message_sync,
            session_id,
            message,
            message_id,
            user_id,
            now or datetime.now(UTC),
            metadata or {},
        )

    async def messages(
        self,
        session_id: str,
        *,
        user_id: str | None = None,
    ) -> tuple[StoredMessage, ...]:
        """Read one session, optionally enforcing an active-user boundary."""
        return await asyncio.to_thread(self._messages_sync, session_id, user_id)

    async def set_session_user(self, session_id: str, user_id: str) -> SessionRecord:
        """Switch the active profile without reassigning historical messages."""
        return await asyncio.to_thread(self._set_session_user_sync, session_id, user_id)

    async def sessions(self) -> tuple[SessionRecord, ...]:
        """List sessions from most recently updated to oldest."""
        return await asyncio.to_thread(self._sessions_sync)

    async def clear_session(self, session_id: str, *, user_id: str | None = None) -> int:
        """Delete a session transcript while retaining its identity."""
        return await asyncio.to_thread(self._clear_session_sync, session_id, user_id)

    def set_retention_days(self, retention_days: int) -> None:
        """Apply a validated persisted retention setting to future pruning."""
        if not 1 <= retention_days <= 365:
            raise ValueError("retention_days must be between 1 and 365")
        self._retention = timedelta(days=retention_days)

    async def prune(self, *, now: datetime | None = None) -> int:
        """Delete messages older than the configured retention window."""
        return await asyncio.to_thread(self._prune_sync, now or datetime.now(UTC))

    async def close(self) -> None:
        """Close safely and idempotently."""
        await asyncio.to_thread(self._close_sync)

    def _start_sync(self) -> None:
        with self._lock:
            if self._connection is not None:
                return
            self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self._path.parent, 0o700)
            connection = sqlite3.connect(self._path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 5000")
            migrate_agent_database(connection)
            self._connection = connection
            os.chmod(self._path, 0o600)

    def _create_session_sync(
        self,
        session_id: str,
        user_id: str,
        now: datetime,
    ) -> SessionRecord:
        timestamp = _utc(now)
        with self._lock:
            connection = self._require_connection()
            connection.execute(
                """
                INSERT INTO sessions(session_id, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (session_id, user_id, timestamp.isoformat(), timestamp.isoformat()),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            assert row is not None
            return _session_from_row(row)

    def _append_message_sync(
        self,
        session_id: str,
        message: ModelMessage,
        message_id: str,
        user_id: str | None,
        now: datetime,
        metadata: dict[str, str],
    ) -> StoredMessage:
        import json

        timestamp = _utc(now)
        with self._lock:
            connection = self._require_connection()
            session = connection.execute(
                "SELECT user_id FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise KeyError(f"unknown session: {session_id}")
            effective_user_id = user_id or session["user_id"]
            connection.execute(
                """
                INSERT INTO messages(
                    message_id, session_id, user_id, role, content, name, tool_call_id,
                    tool_calls_json, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    effective_user_id,
                    message.role.value,
                    message.content,
                    message.name,
                    message.tool_call_id,
                    json.dumps(
                        [call.model_dump(mode="json") for call in message.tool_calls],
                        sort_keys=True,
                    ),
                    timestamp.isoformat(),
                    json.dumps(metadata, sort_keys=True),
                ),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (timestamp.isoformat(), session_id),
            )
            connection.commit()
        return StoredMessage(
            message_id=message_id,
            session_id=session_id,
            user_id=effective_user_id,
            message=message,
            created_at=timestamp,
            metadata=metadata,
        )

    def _messages_sync(
        self,
        session_id: str,
        user_id: str | None,
    ) -> tuple[StoredMessage, ...]:
        import json

        with self._lock:
            sql = """
                SELECT messages.*, COALESCE(messages.user_id, sessions.user_id) AS effective_user_id
                FROM messages JOIN sessions USING(session_id)
                WHERE messages.session_id = ?
            """
            parameters: list[str] = [session_id]
            if user_id is not None:
                sql += " AND COALESCE(messages.user_id, sessions.user_id) = ?"
                parameters.append(user_id)
            sql += " ORDER BY messages.created_at, messages.message_id"
            rows = self._require_connection().execute(sql, parameters).fetchall()
        return tuple(
            StoredMessage(
                message_id=row["message_id"],
                session_id=row["session_id"],
                user_id=row["effective_user_id"],
                message=ModelMessage(
                    role=MessageRole(row["role"]),
                    content=row["content"],
                    name=row["name"],
                    tool_call_id=row["tool_call_id"],
                    tool_calls=tuple(
                        ToolCall.model_validate(item) for item in json.loads(row["tool_calls_json"])
                    ),
                ),
                created_at=datetime.fromisoformat(row["created_at"]),
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        )

    def _sessions_sync(self) -> tuple[SessionRecord, ...]:
        with self._lock:
            rows = (
                self._require_connection()
                .execute("SELECT * FROM sessions ORDER BY updated_at DESC, session_id")
                .fetchall()
            )
        return tuple(_session_from_row(row) for row in rows)

    def _set_session_user_sync(self, session_id: str, user_id: str) -> SessionRecord:
        timestamp = datetime.now(UTC).isoformat()
        with self._lock:
            connection = self._require_connection()
            cursor = connection.execute(
                "UPDATE sessions SET user_id = ?, updated_at = ? WHERE session_id = ?",
                (user_id, timestamp, session_id),
            )
            if not cursor.rowcount:
                raise KeyError(f"unknown session: {session_id}")
            connection.commit()
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            assert row is not None
        return _session_from_row(row)

    def _clear_session_sync(self, session_id: str, user_id: str | None) -> int:
        with self._lock:
            connection = self._require_connection()
            if user_id is None:
                cursor = connection.execute(
                    "DELETE FROM messages WHERE session_id = ?",
                    (session_id,),
                )
            else:
                cursor = connection.execute(
                    "DELETE FROM messages WHERE session_id = ? AND user_id = ?",
                    (session_id, user_id),
                )
            connection.commit()
            return cursor.rowcount

    def _prune_sync(self, now: datetime) -> int:
        cutoff = (_utc(now) - self._retention).isoformat()
        with self._lock:
            connection = self._require_connection()
            cursor = connection.execute(
                "DELETE FROM messages WHERE created_at < ?",
                (cutoff,),
            )
            connection.execute(
                """
                DELETE FROM sessions
                WHERE updated_at < ?
                  AND NOT EXISTS (
                      SELECT 1 FROM messages
                      WHERE messages.session_id = sessions.session_id
                  )
                """,
                (cutoff,),
            )
            connection.commit()
            return cursor.rowcount

    def _close_sync(self) -> None:
        with self._lock:
            if self._connection is None:
                return
            self._connection.close()
            self._connection = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("conversation store is not started")
        return self._connection


def _session_from_row(row: sqlite3.Row) -> SessionRecord:
    return SessionRecord(
        session_id=row["session_id"],
        user_id=row["user_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(UTC)
