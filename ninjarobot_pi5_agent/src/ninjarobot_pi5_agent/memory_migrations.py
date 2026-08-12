"""Idempotent SQLite schema migrations shared by conversation and memory stores."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

Migration = Callable[[sqlite3.Connection], None]


def migrate_agent_database(connection: sqlite3.Connection) -> None:
    """Apply all agent database migrations transactionally and idempotently."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    applied = {
        int(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for version, migration in enumerate(_MIGRATIONS, start=1):
        if version in applied:
            continue
        try:
            connection.execute("BEGIN IMMEDIATE")
            migration(connection)
            connection.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)",
                (version,),
            )
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()


def _core_schema(connection: sqlite3.Connection) -> None:
    _execute_script(
        connection,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            name TEXT,
            tool_call_id TEXT,
            tool_calls_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS messages_session_time
            ON messages(session_id, created_at, message_id);
        """,
    )


def _conversation_user_scope(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)")}
    if "tool_calls_json" not in columns:
        connection.execute(
            "ALTER TABLE messages ADD COLUMN tool_calls_json TEXT NOT NULL DEFAULT '[]'"
        )
    if "user_id" not in columns:
        connection.execute("ALTER TABLE messages ADD COLUMN user_id TEXT")
    connection.execute(
        """
        UPDATE messages
        SET user_id = (
            SELECT sessions.user_id FROM sessions
            WHERE sessions.session_id = messages.session_id
        )
        WHERE user_id IS NULL
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS messages_user_session_time
        ON messages(user_id, session_id, created_at, message_id)
        """
    )


def _memory_schema(connection: sqlite3.Connection) -> None:
    _execute_script(
        connection,
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            preferred_robot_name TEXT,
            role TEXT NOT NULL CHECK(role IN ('owner', 'member')),
            face_status TEXT NOT NULL DEFAULT 'pending'
                CHECK(face_status IN ('pending', 'enrolled', 'unavailable', 'failed')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS users_single_owner
            ON users(role) WHERE role = 'owner';

        CREATE TABLE IF NOT EXISTS face_profiles (
            user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
            face_index_name TEXT NOT NULL UNIQUE,
            profile_image_path TEXT NOT NULL,
            model_metadata_json TEXT NOT NULL DEFAULT '{}',
            enrolled_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS preferences (
            preference_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            preference_key TEXT NOT NULL,
            value_json TEXT NOT NULL,
            source TEXT NOT NULL,
            confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
            inferred INTEGER NOT NULL CHECK(inferred IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, preference_key)
        );

        CREATE TABLE IF NOT EXISTS memory_items (
            memory_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK(kind IN (
                'user_profile', 'preference', 'task_recipe', 'episodic_summary',
                'successful_behavior', 'failed_behavior'
            )),
            content TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            source_session_id TEXT,
            source_message_id TEXT,
            source_action_id TEXT,
            confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
            sensitive INTEGER NOT NULL CHECK(sensitive IN (0, 1)),
            expires_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS memory_items_user_kind_time
            ON memory_items(user_id, kind, created_at DESC, memory_id);
        CREATE INDEX IF NOT EXISTS memory_items_expiration
            ON memory_items(expires_at) WHERE expires_at IS NOT NULL;

        CREATE TABLE IF NOT EXISTS behavior_attempts (
            attempt_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            action_id TEXT,
            tool_name TEXT NOT NULL,
            request_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN (
                'succeeded', 'failed', 'denied', 'cancelled', 'timed_out'
            )),
            failure_class TEXT,
            memory_id TEXT REFERENCES memory_items(memory_id) ON DELETE SET NULL,
            user_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(user_confirmed IN (0, 1)),
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS behavior_attempts_user_time
            ON behavior_attempts(user_id, created_at DESC, attempt_id);

        CREATE TABLE IF NOT EXISTS pending_memory_confirmations (
            confirmation_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            session_id TEXT NOT NULL,
            attempt_id TEXT NOT NULL REFERENCES behavior_attempts(attempt_id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, session_id)
        );

        CREATE TABLE IF NOT EXISTS memory_settings (
            settings_id INTEGER PRIMARY KEY CHECK(settings_id = 1),
            conversation_retention_days INTEGER NOT NULL
                CHECK(conversation_retention_days BETWEEN 1 AND 365),
            failed_behavior_retention_days INTEGER NOT NULL
                CHECK(failed_behavior_retention_days BETWEEN 1 AND 3650),
            failed_behavior_cap INTEGER NOT NULL
                CHECK(failed_behavior_cap BETWEEN 10 AND 100000),
            retrieval_limit INTEGER NOT NULL CHECK(retrieval_limit BETWEEN 1 AND 20),
            retrieval_character_budget INTEGER NOT NULL
                CHECK(retrieval_character_budget BETWEEN 256 AND 20000)
        );
        INSERT OR IGNORE INTO memory_settings(
            settings_id, conversation_retention_days,
            failed_behavior_retention_days, failed_behavior_cap,
            retrieval_limit, retrieval_character_budget
        ) VALUES (1, 7, 180, 1000, 6, 4000);

        CREATE TABLE IF NOT EXISTS memory_audit_events (
            event_id TEXT PRIMARY KEY,
            operation TEXT NOT NULL,
            actor TEXT NOT NULL,
            target_user_id TEXT,
            target_memory_id TEXT,
            detail_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS memory_audit_time
            ON memory_audit_events(created_at DESC, event_id);
        """,
    )
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                memory_id UNINDEXED,
                user_id UNINDEXED,
                kind UNINDEXED,
                content,
                tokenize='unicode61'
            )
            """
        )
    except sqlite3.OperationalError as error:
        if "no such module: fts5" not in str(error).casefold():
            raise
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_fts (
                memory_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL
            )
            """
        )


_MIGRATIONS: tuple[Migration, ...] = (
    _core_schema,
    _conversation_user_scope,
    _memory_schema,
)


def _execute_script(connection: sqlite3.Connection, script: str) -> None:
    """Execute complete statements without the implicit commits of executescript()."""
    buffered: list[str] = []
    for line in script.splitlines():
        buffered.append(line)
        candidate = "\n".join(buffered).strip()
        if not candidate or not sqlite3.complete_statement(candidate):
            continue
        connection.execute(candidate)
        buffered.clear()
    if "\n".join(buffered).strip():
        raise sqlite3.OperationalError("migration contained an incomplete SQL statement")
