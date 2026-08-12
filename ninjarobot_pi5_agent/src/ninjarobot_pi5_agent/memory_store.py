"""Deterministic local persistence for user profiles and long-term memory."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from .memory_migrations import migrate_agent_database
from .memory_models import (
    BehaviorAttempt,
    BehaviorAttemptStatus,
    FaceEnrollmentStatus,
    FaceProfile,
    MemoryItem,
    MemorySettings,
    UserProfile,
    UserRole,
)
from .models import MemoryKind


class MemoryStoreError(RuntimeError):
    """Base error for deterministic memory operations."""


class ProfileConflictError(MemoryStoreError):
    """A profile name or owner invariant would be violated."""


class ProfileDeletionError(MemoryStoreError):
    """A protected active or owner profile cannot be deleted."""


class MemoryStore:
    """Owner-only SQLite store with enforced per-user query boundaries."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    async def start(self) -> None:
        await asyncio.to_thread(self._start_sync)

    async def close(self) -> None:
        await asyncio.to_thread(self._close_sync)

    async def settings(self) -> MemorySettings:
        return await asyncio.to_thread(self._settings_sync)

    async def initialize_settings(self, defaults: MemorySettings) -> MemorySettings:
        """Apply configured defaults once without overwriting later CLI changes."""
        return await asyncio.to_thread(self._initialize_settings_sync, defaults)

    async def update_settings(
        self,
        *,
        conversation_retention_days: int | None = None,
        failed_behavior_retention_days: int | None = None,
        failed_behavior_cap: int | None = None,
        retrieval_limit: int | None = None,
        retrieval_character_budget: int | None = None,
        actor: str = "interactive-tool",
    ) -> MemorySettings:
        current = await self.settings()
        updated = current.model_copy(
            update={
                key: value
                for key, value in {
                    "conversation_retention_days": conversation_retention_days,
                    "failed_behavior_retention_days": failed_behavior_retention_days,
                    "failed_behavior_cap": failed_behavior_cap,
                    "retrieval_limit": retrieval_limit,
                    "retrieval_character_budget": retrieval_character_budget,
                }.items()
                if value is not None
            }
        )
        MemorySettings.model_validate(updated.model_dump())
        return await asyncio.to_thread(self._update_settings_sync, updated, actor)

    async def reset_all(self, defaults: MemorySettings) -> dict[str, int]:
        """Delete all user-scoped memory and restore configured defaults atomically."""
        MemorySettings.model_validate(defaults.model_dump())
        return await asyncio.to_thread(self._reset_all_sync, defaults)

    async def create_profile(
        self,
        display_name: str,
        *,
        user_id: str | None = None,
        actor: str = "registration",
        now: datetime | None = None,
    ) -> UserProfile:
        """Create the first profile as owner and every later profile as member."""
        return await asyncio.to_thread(
            self._create_profile_sync,
            display_name,
            user_id,
            actor,
            now or datetime.now(UTC),
        )

    async def profiles(self) -> tuple[UserProfile, ...]:
        return await asyncio.to_thread(self._profiles_sync)

    async def profile(self, user_id: str) -> UserProfile:
        return await asyncio.to_thread(self._profile_sync, user_id)

    async def owner(self) -> UserProfile | None:
        return await asyncio.to_thread(self._owner_sync)

    async def update_profile(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        preferred_robot_name: str | None = None,
        face_status: FaceEnrollmentStatus | None = None,
        actor: str = "explicit-profile-update",
        now: datetime | None = None,
    ) -> UserProfile:
        return await asyncio.to_thread(
            self._update_profile_sync,
            user_id,
            display_name,
            preferred_robot_name,
            face_status,
            actor,
            now or datetime.now(UTC),
        )

    async def update_personalization(
        self,
        user_id: str,
        *,
        preferred_robot_name: str | None = None,
        preferred_form_of_address: str | None = None,
        actor: str = "explicit-chat-personalization",
        now: datetime | None = None,
    ) -> tuple[UserProfile, MemoryItem | None]:
        """Atomically update explicit conversational identity preferences."""
        return await asyncio.to_thread(
            self._update_personalization_sync,
            user_id,
            preferred_robot_name,
            preferred_form_of_address,
            actor,
            now or datetime.now(UTC),
        )

    async def set_face_profile(
        self,
        user_id: str,
        *,
        face_index_name: str,
        profile_image_path: str,
        model_metadata: dict[str, Any],
        actor: str = "face-enrollment",
        now: datetime | None = None,
    ) -> FaceProfile:
        return await asyncio.to_thread(
            self._set_face_profile_sync,
            user_id,
            face_index_name,
            profile_image_path,
            model_metadata,
            actor,
            now or datetime.now(UTC),
        )

    async def face_profile(self, user_id: str) -> FaceProfile | None:
        return await asyncio.to_thread(self._face_profile_sync, user_id)

    async def clear_face_profile(
        self,
        user_id: str,
        *,
        actor: str = "face-data-reconciliation",
        now: datetime | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._clear_face_profile_sync,
            user_id,
            actor,
            now or datetime.now(UTC),
        )

    async def transfer_owner(
        self,
        new_owner_user_id: str,
        *,
        actor: str = "interactive-tool",
        now: datetime | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._transfer_owner_sync,
            new_owner_user_id,
            actor,
            now or datetime.now(UTC),
        )

    async def delete_profile(
        self,
        user_id: str,
        *,
        active_user_ids: set[str] | frozenset[str] = frozenset(),
        actor: str = "interactive-tool",
    ) -> None:
        await asyncio.to_thread(
            self._delete_profile_sync,
            user_id,
            frozenset(active_user_ids),
            actor,
        )

    async def upsert_preference(
        self,
        user_id: str,
        key: str,
        value: Any,
        *,
        source: str,
        confidence: float = 1.0,
        inferred: bool = False,
        actor: str = "agent-capture",
        now: datetime | None = None,
    ) -> MemoryItem:
        return await asyncio.to_thread(
            self._upsert_preference_sync,
            user_id,
            key,
            value,
            source,
            confidence,
            inferred,
            actor,
            now or datetime.now(UTC),
        )

    async def preference_value(self, user_id: str, key: str) -> Any | None:
        """Return one user-scoped structured preference without model-side scanning."""
        return await asyncio.to_thread(self._preference_value_sync, user_id, key)

    async def add_memory(
        self,
        user_id: str,
        kind: MemoryKind,
        content: str,
        *,
        payload: dict[str, Any] | None = None,
        source_session_id: str | None = None,
        source_message_id: str | None = None,
        source_action_id: str | None = None,
        confidence: float = 1.0,
        sensitive: bool = False,
        expires_at: datetime | None = None,
        actor: str = "agent-capture",
        now: datetime | None = None,
    ) -> MemoryItem:
        return await asyncio.to_thread(
            self._add_memory_sync,
            user_id,
            kind,
            content,
            payload or {},
            source_session_id,
            source_message_id,
            source_action_id,
            confidence,
            sensitive,
            expires_at,
            actor,
            now or datetime.now(UTC),
        )

    async def memory(self, user_id: str, memory_id: str) -> MemoryItem:
        return await asyncio.to_thread(self._memory_sync, user_id, memory_id)

    async def memories(
        self,
        user_id: str,
        *,
        kind: MemoryKind | None = None,
        limit: int = 100,
    ) -> tuple[MemoryItem, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        return await asyncio.to_thread(self._memories_sync, user_id, kind, limit)

    async def search(
        self,
        user_id: str,
        query: str,
        *,
        kinds: tuple[MemoryKind, ...] = (),
        limit: int | None = None,
    ) -> tuple[MemoryItem, ...]:
        settings = await self.settings()
        result_limit = settings.retrieval_limit if limit is None else limit
        if not 1 <= result_limit <= 20:
            raise ValueError("search limit must be between 1 and 20")
        return await asyncio.to_thread(
            self._search_sync,
            user_id,
            query,
            kinds,
            result_limit,
        )

    async def delete_memory(
        self,
        user_id: str,
        memory_id: str,
        *,
        actor: str = "interactive-tool",
    ) -> bool:
        return await asyncio.to_thread(
            self._delete_memory_sync,
            user_id,
            memory_id,
            actor,
        )

    async def record_behavior_attempt(
        self,
        user_id: str,
        *,
        tool_name: str,
        request: dict[str, Any],
        result: dict[str, Any],
        status: BehaviorAttemptStatus,
        action_id: str | None = None,
        failure_class: str | None = None,
        now: datetime | None = None,
    ) -> BehaviorAttempt:
        return await asyncio.to_thread(
            self._record_behavior_attempt_sync,
            user_id,
            tool_name,
            request,
            result,
            status,
            action_id,
            failure_class,
            now or datetime.now(UTC),
        )

    async def set_pending_behavior_confirmation(
        self,
        user_id: str,
        session_id: str,
        attempt_id: str,
        *,
        ttl_seconds: int = 900,
        now: datetime | None = None,
    ) -> None:
        if not 30 <= ttl_seconds <= 3600:
            raise ValueError("ttl_seconds must be between 30 and 3600")
        await asyncio.to_thread(
            self._set_pending_behavior_confirmation_sync,
            user_id,
            session_id,
            attempt_id,
            ttl_seconds,
            now or datetime.now(UTC),
        )

    async def take_pending_behavior_confirmation(
        self,
        user_id: str,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> BehaviorAttempt | None:
        """Atomically consume one unexpired confirmation for the active user."""
        return await asyncio.to_thread(
            self._take_pending_behavior_confirmation_sync,
            user_id,
            session_id,
            now or datetime.now(UTC),
        )

    async def link_behavior_memory(self, attempt_id: str, memory_id: str) -> None:
        await asyncio.to_thread(self._link_behavior_memory_sync, attempt_id, memory_id)

    async def prune(self, *, now: datetime | None = None) -> dict[str, int]:
        return await asyncio.to_thread(self._prune_sync, now or datetime.now(UTC))

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

    def _close_sync(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def _settings_sync(self) -> MemorySettings:
        with self._lock:
            row = (
                self._require_connection()
                .execute("SELECT * FROM memory_settings WHERE settings_id = 1")
                .fetchone()
            )
        assert row is not None
        return MemorySettings(
            conversation_retention_days=row["conversation_retention_days"],
            failed_behavior_retention_days=row["failed_behavior_retention_days"],
            failed_behavior_cap=row["failed_behavior_cap"],
            retrieval_limit=row["retrieval_limit"],
            retrieval_character_budget=row["retrieval_character_budget"],
        )

    def _initialize_settings_sync(self, defaults: MemorySettings) -> MemorySettings:
        with self._lock, self._require_connection() as connection:
            initialized = connection.execute(
                """
                SELECT 1 FROM memory_audit_events
                WHERE operation IN ('initialize_settings', 'update_settings')
                LIMIT 1
                """
            ).fetchone()
            if initialized is None:
                connection.execute(
                    """
                    UPDATE memory_settings SET
                        conversation_retention_days = ?,
                        failed_behavior_retention_days = ?,
                        failed_behavior_cap = ?,
                        retrieval_limit = ?,
                        retrieval_character_budget = ?
                    WHERE settings_id = 1
                    """,
                    (
                        defaults.conversation_retention_days,
                        defaults.failed_behavior_retention_days,
                        defaults.failed_behavior_cap,
                        defaults.retrieval_limit,
                        defaults.retrieval_character_budget,
                    ),
                )
                self._audit(
                    connection,
                    "initialize_settings",
                    "robot-config",
                    detail=defaults.model_dump(mode="json"),
                )
                return defaults
        return self._settings_sync()

    def _update_settings_sync(self, settings: MemorySettings, actor: str) -> MemorySettings:
        with self._lock, self._require_connection() as connection:
            connection.execute(
                """
                UPDATE memory_settings SET
                    conversation_retention_days = ?,
                    failed_behavior_retention_days = ?,
                    failed_behavior_cap = ?,
                    retrieval_limit = ?,
                    retrieval_character_budget = ?
                WHERE settings_id = 1
                """,
                (
                    settings.conversation_retention_days,
                    settings.failed_behavior_retention_days,
                    settings.failed_behavior_cap,
                    settings.retrieval_limit,
                    settings.retrieval_character_budget,
                ),
            )
            self._audit(
                connection,
                "update_settings",
                actor,
                detail=settings.model_dump(mode="json"),
            )
        return settings

    def _reset_all_sync(self, defaults: MemorySettings) -> dict[str, int]:
        table_names = (
            "users",
            "face_profiles",
            "preferences",
            "memory_items",
            "behavior_attempts",
            "pending_memory_confirmations",
            "sessions",
            "messages",
            "memory_audit_events",
            "memory_fts",
        )
        with self._lock, self._require_connection() as connection:
            deleted = {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in table_names
            }
            connection.execute("DELETE FROM memory_fts")
            connection.execute("DELETE FROM sessions")
            connection.execute("DELETE FROM users")
            connection.execute("DELETE FROM memory_audit_events")
            connection.execute(
                """
                UPDATE memory_settings SET
                    conversation_retention_days = ?,
                    failed_behavior_retention_days = ?,
                    failed_behavior_cap = ?,
                    retrieval_limit = ?,
                    retrieval_character_budget = ?
                WHERE settings_id = 1
                """,
                (
                    defaults.conversation_retention_days,
                    defaults.failed_behavior_retention_days,
                    defaults.failed_behavior_cap,
                    defaults.retrieval_limit,
                    defaults.retrieval_character_budget,
                ),
            )
        return deleted

    def _create_profile_sync(
        self,
        display_name: str,
        user_id: str | None,
        actor: str,
        now: datetime,
    ) -> UserProfile:
        name, normalized = _normalize_name(display_name)
        timestamp = _utc(now)
        with self._lock, self._require_connection() as connection:
            has_users = connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
            role = UserRole.MEMBER if has_users else UserRole.OWNER
            assigned_id = user_id or ("local-user" if not has_users else _id("user"))
            try:
                connection.execute(
                    """
                    INSERT INTO users(
                        user_id, display_name, normalized_name, role, face_status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        assigned_id,
                        name,
                        normalized,
                        role.value,
                        FaceEnrollmentStatus.PENDING.value,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ProfileConflictError(
                    "a user with that name or identifier already exists"
                ) from error
            self._audit(connection, "create_profile", actor, target_user_id=assigned_id)
            row = self._user_row(connection, assigned_id)
        return _profile_from_row(row)

    def _profiles_sync(self) -> tuple[UserProfile, ...]:
        with self._lock:
            rows = (
                self._require_connection()
                .execute(
                    """
                SELECT * FROM users
                ORDER BY CASE role WHEN 'owner' THEN 0 ELSE 1 END, created_at, user_id
                """
                )
                .fetchall()
            )
        return tuple(_profile_from_row(row) for row in rows)

    def _profile_sync(self, user_id: str) -> UserProfile:
        with self._lock:
            row = self._user_row(self._require_connection(), user_id)
        return _profile_from_row(row)

    def _owner_sync(self) -> UserProfile | None:
        with self._lock:
            row = (
                self._require_connection()
                .execute("SELECT * FROM users WHERE role = 'owner'")
                .fetchone()
            )
        return None if row is None else _profile_from_row(row)

    def _update_profile_sync(
        self,
        user_id: str,
        display_name: str | None,
        preferred_robot_name: str | None,
        face_status: FaceEnrollmentStatus | None,
        actor: str,
        now: datetime,
    ) -> UserProfile:
        if display_name is None and preferred_robot_name is None and face_status is None:
            raise ValueError("at least one profile field must be updated")
        timestamp = _utc(now)
        with self._lock, self._require_connection() as connection:
            current = self._user_row(connection, user_id)
            name = current["display_name"]
            normalized = current["normalized_name"]
            if display_name is not None:
                name, normalized = _normalize_name(display_name)
            robot_name = (
                current["preferred_robot_name"]
                if preferred_robot_name is None
                else _normalize_name(preferred_robot_name)[0]
            )
            status = current["face_status"] if face_status is None else face_status.value
            try:
                connection.execute(
                    """
                    UPDATE users SET display_name = ?, normalized_name = ?,
                        preferred_robot_name = ?, face_status = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (name, normalized, robot_name, status, timestamp, user_id),
                )
            except sqlite3.IntegrityError as error:
                raise ProfileConflictError("a user with that name already exists") from error
            self._audit(connection, "update_profile", actor, target_user_id=user_id)
            row = self._user_row(connection, user_id)
        return _profile_from_row(row)

    def _update_personalization_sync(
        self,
        user_id: str,
        preferred_robot_name: str | None,
        preferred_form_of_address: str | None,
        actor: str,
        now: datetime,
    ) -> tuple[UserProfile, MemoryItem | None]:
        if preferred_robot_name is None and preferred_form_of_address is None:
            raise ValueError("at least one personalization field must be updated")
        robot_name = (
            _normalize_name(preferred_robot_name)[0] if preferred_robot_name is not None else None
        )
        form_of_address = (
            _normalize_name(preferred_form_of_address)[0]
            if preferred_form_of_address is not None
            else None
        )
        timestamp = _utc(now)
        preference_row: sqlite3.Row | None = None
        with self._lock, self._require_connection() as connection:
            self._user_row(connection, user_id)
            if robot_name is not None:
                connection.execute(
                    """
                    UPDATE users SET preferred_robot_name = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (robot_name, timestamp, user_id),
                )
                self._audit(connection, "update_profile", actor, target_user_id=user_id)
            if form_of_address is not None:
                preference_row = self._upsert_preference_row(
                    connection,
                    user_id=user_id,
                    key="preferred_form_of_address",
                    value=form_of_address,
                    source="explicit-chat-address",
                    confidence=1.0,
                    inferred=False,
                    actor=actor,
                    now=now,
                )
            profile_row = self._user_row(connection, user_id)
        return (
            _profile_from_row(profile_row),
            _memory_from_row(preference_row) if preference_row is not None else None,
        )

    def _set_face_profile_sync(
        self,
        user_id: str,
        face_index_name: str,
        profile_image_path: str,
        model_metadata: dict[str, Any],
        actor: str,
        now: datetime,
    ) -> FaceProfile:
        timestamp = _utc(now)
        with self._lock, self._require_connection() as connection:
            self._user_row(connection, user_id)
            connection.execute(
                """
                INSERT INTO face_profiles(
                    user_id, face_index_name, profile_image_path,
                    model_metadata_json, enrolled_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    face_index_name = excluded.face_index_name,
                    profile_image_path = excluded.profile_image_path,
                    model_metadata_json = excluded.model_metadata_json,
                    enrolled_at = excluded.enrolled_at
                """,
                (
                    user_id,
                    face_index_name,
                    profile_image_path,
                    json.dumps(model_metadata, sort_keys=True),
                    timestamp,
                ),
            )
            connection.execute(
                "UPDATE users SET face_status = 'enrolled', updated_at = ? WHERE user_id = ?",
                (timestamp, user_id),
            )
            self._audit(connection, "set_face_profile", actor, target_user_id=user_id)
        return FaceProfile(
            user_id=user_id,
            face_index_name=face_index_name,
            profile_image_path=profile_image_path,
            model_metadata=model_metadata,
            enrolled_at=datetime.fromisoformat(timestamp),
        )

    def _face_profile_sync(self, user_id: str) -> FaceProfile | None:
        with self._lock:
            row = (
                self._require_connection()
                .execute(
                    "SELECT * FROM face_profiles WHERE user_id = ?",
                    (user_id,),
                )
                .fetchone()
            )
        if row is None:
            return None
        return FaceProfile(
            user_id=row["user_id"],
            face_index_name=row["face_index_name"],
            profile_image_path=row["profile_image_path"],
            model_metadata=json.loads(row["model_metadata_json"]),
            enrolled_at=datetime.fromisoformat(row["enrolled_at"]),
        )

    def _clear_face_profile_sync(self, user_id: str, actor: str, now: datetime) -> None:
        timestamp = _utc(now)
        with self._lock, self._require_connection() as connection:
            self._user_row(connection, user_id)
            connection.execute("DELETE FROM face_profiles WHERE user_id = ?", (user_id,))
            connection.execute(
                "UPDATE users SET face_status = 'pending', updated_at = ? WHERE user_id = ?",
                (timestamp, user_id),
            )
            self._audit(connection, "clear_face_profile", actor, target_user_id=user_id)

    def _transfer_owner_sync(
        self,
        new_owner_user_id: str,
        actor: str,
        now: datetime,
    ) -> None:
        timestamp = _utc(now)
        with self._lock, self._require_connection() as connection:
            new_owner = self._user_row(connection, new_owner_user_id)
            if new_owner["role"] == UserRole.OWNER.value:
                return
            connection.execute("UPDATE users SET role = 'member' WHERE role = 'owner'")
            connection.execute(
                "UPDATE users SET role = 'owner', updated_at = ? WHERE user_id = ?",
                (timestamp, new_owner_user_id),
            )
            self._audit(
                connection,
                "transfer_owner",
                actor,
                target_user_id=new_owner_user_id,
            )

    def _delete_profile_sync(
        self,
        user_id: str,
        active_user_ids: frozenset[str],
        actor: str,
    ) -> None:
        with self._lock, self._require_connection() as connection:
            profile = self._user_row(connection, user_id)
            if user_id in active_user_ids:
                raise ProfileDeletionError("the active user profile cannot be deleted")
            if profile["role"] == UserRole.OWNER.value:
                raise ProfileDeletionError("transfer ownership before deleting the owner profile")
            memory_ids = [
                row[0]
                for row in connection.execute(
                    "SELECT memory_id FROM memory_items WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            ]
            for memory_id in memory_ids:
                connection.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            owner = connection.execute("SELECT user_id FROM users WHERE role = 'owner'").fetchone()
            assert owner is not None
            connection.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            connection.execute(
                "UPDATE sessions SET user_id = ? WHERE user_id = ?",
                (owner["user_id"], user_id),
            )
            connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            self._audit(connection, "delete_profile", actor, target_user_id=user_id)

    def _upsert_preference_sync(
        self,
        user_id: str,
        key: str,
        value: Any,
        source: str,
        confidence: float,
        inferred: bool,
        actor: str,
        now: datetime,
    ) -> MemoryItem:
        with self._lock, self._require_connection() as connection:
            self._user_row(connection, user_id)
            row = self._upsert_preference_row(
                connection,
                user_id=user_id,
                key=key,
                value=value,
                source=source,
                confidence=confidence,
                inferred=inferred,
                actor=actor,
                now=now,
            )
        return _memory_from_row(row)

    def _preference_value_sync(self, user_id: str, key: str) -> Any | None:
        normalized_key = key.strip().casefold().replace(" ", "_")
        if not re.fullmatch(r"[a-z0-9_.-]{1,80}", normalized_key):
            raise ValueError("preference key must contain only letters, digits, '.', '_' or '-'")
        with self._lock:
            connection = self._require_connection()
            self._user_row(connection, user_id)
            row = connection.execute(
                """
                SELECT value_json FROM preferences
                WHERE user_id = ? AND preference_key = ?
                """,
                (user_id, normalized_key),
            ).fetchone()
        return None if row is None else json.loads(row["value_json"])

    def _upsert_preference_row(
        self,
        connection: sqlite3.Connection,
        *,
        user_id: str,
        key: str,
        value: Any,
        source: str,
        confidence: float,
        inferred: bool,
        actor: str,
        now: datetime,
    ) -> sqlite3.Row:
        normalized_key = key.strip().casefold().replace(" ", "_")
        if not re.fullmatch(r"[a-z0-9_.-]{1,80}", normalized_key):
            raise ValueError("preference key must contain only letters, digits, '.', '_' or '-'")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        timestamp = _utc(now)
        preference_id = f"preference:{user_id}:{normalized_key}"
        content = f"{normalized_key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}"
        connection.execute(
            """
            INSERT INTO preferences(
                preference_id, user_id, preference_key, value_json, source,
                confidence, inferred, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, preference_key) DO UPDATE SET
                value_json = excluded.value_json, source = excluded.source,
                confidence = excluded.confidence, inferred = excluded.inferred,
                updated_at = excluded.updated_at
            """,
            (
                preference_id,
                user_id,
                normalized_key,
                json.dumps(value, ensure_ascii=False, sort_keys=True),
                source,
                confidence,
                int(inferred),
                timestamp,
                timestamp,
            ),
        )
        existing = connection.execute(
            """
            SELECT memory_id, created_at FROM memory_items
            WHERE user_id = ? AND kind = 'preference'
              AND json_extract(payload_json, '$.preference_key') = ?
            """,
            (user_id, normalized_key),
        ).fetchone()
        memory_id = existing["memory_id"] if existing else _id("memory")
        created_at = existing["created_at"] if existing else timestamp
        connection.execute(
            """
            INSERT INTO memory_items(
                memory_id, user_id, kind, content, payload_json,
                confidence, sensitive, created_at, updated_at
            ) VALUES (?, ?, 'preference', ?, ?, ?, 0, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                content = excluded.content, payload_json = excluded.payload_json,
                confidence = excluded.confidence, updated_at = excluded.updated_at
            """,
            (
                memory_id,
                user_id,
                content,
                json.dumps(
                    {
                        "preference_key": normalized_key,
                        "value": value,
                        "source": source,
                        "inferred": inferred,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                confidence,
                created_at,
                timestamp,
            ),
        )
        self._sync_fts(connection, memory_id, user_id, MemoryKind.PREFERENCE, content)
        self._audit(
            connection,
            "upsert_preference",
            actor,
            target_user_id=user_id,
            target_memory_id=memory_id,
        )
        return self._memory_row(connection, user_id, memory_id)

    def _add_memory_sync(
        self,
        user_id: str,
        kind: MemoryKind,
        content: str,
        payload: dict[str, Any],
        source_session_id: str | None,
        source_message_id: str | None,
        source_action_id: str | None,
        confidence: float,
        sensitive: bool,
        expires_at: datetime | None,
        actor: str,
        now: datetime,
    ) -> MemoryItem:
        memory_id = _id("memory")
        timestamp = _utc(now)
        expiration = None if expires_at is None else _utc(expires_at)
        candidate = MemoryItem(
            memory_id=memory_id,
            user_id=user_id,
            kind=kind,
            content=content,
            payload=payload,
            source_session_id=source_session_id,
            source_message_id=source_message_id,
            source_action_id=source_action_id,
            confidence=confidence,
            sensitive=sensitive,
            expires_at=None if expiration is None else datetime.fromisoformat(expiration),
            created_at=datetime.fromisoformat(timestamp),
            updated_at=datetime.fromisoformat(timestamp),
        )
        with self._lock, self._require_connection() as connection:
            self._user_row(connection, user_id)
            connection.execute(
                """
                INSERT INTO memory_items(
                    memory_id, user_id, kind, content, payload_json,
                    source_session_id, source_message_id, source_action_id,
                    confidence, sensitive, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    user_id,
                    kind.value,
                    content,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    source_session_id,
                    source_message_id,
                    source_action_id,
                    confidence,
                    int(sensitive),
                    expiration,
                    timestamp,
                    timestamp,
                ),
            )
            self._sync_fts(connection, memory_id, user_id, kind, content)
            self._audit(
                connection,
                "add_memory",
                actor,
                target_user_id=user_id,
                target_memory_id=memory_id,
                detail={"kind": kind.value},
            )
        return candidate

    def _memory_sync(self, user_id: str, memory_id: str) -> MemoryItem:
        with self._lock:
            row = self._memory_row(self._require_connection(), user_id, memory_id)
        return _memory_from_row(row)

    def _memories_sync(
        self,
        user_id: str,
        kind: MemoryKind | None,
        limit: int,
    ) -> tuple[MemoryItem, ...]:
        sql = "SELECT * FROM memory_items WHERE user_id = ?"
        parameters: list[Any] = [user_id]
        if kind is not None:
            sql += " AND kind = ?"
            parameters.append(kind.value)
        sql += " ORDER BY created_at DESC, memory_id LIMIT ?"
        parameters.append(limit)
        with self._lock:
            rows = self._require_connection().execute(sql, parameters).fetchall()
        return tuple(_memory_from_row(row) for row in rows)

    def _search_sync(
        self,
        user_id: str,
        query: str,
        kinds: tuple[MemoryKind, ...],
        limit: int,
    ) -> tuple[MemoryItem, ...]:
        tokens = re.findall(r"[\w-]+", query, flags=re.UNICODE)
        if not tokens:
            return ()
        with self._lock:
            connection = self._require_connection()
            virtual = (
                "VIRTUAL TABLE"
                in str(
                    connection.execute(
                        "SELECT sql FROM sqlite_master WHERE name = 'memory_fts'"
                    ).fetchone()[0]
                ).upper()
            )
            kind_values = tuple(kind.value for kind in kinds)
            if virtual:
                match = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:12])
                sql = (
                    "SELECT m.* FROM memory_fts f JOIN memory_items m "
                    "ON m.memory_id = f.memory_id "
                    "WHERE f.memory_fts MATCH ? AND m.user_id = ?"
                )
                parameters: list[Any] = [match, user_id]
                order = " ORDER BY bm25(memory_fts), m.created_at DESC LIMIT ?"
            else:
                clauses = ["LOWER(m.content) LIKE ?" for _ in tokens[:12]]
                sql = (
                    "SELECT m.* FROM memory_items m WHERE m.user_id = ? AND ("
                    + " OR ".join(clauses)
                    + ")"
                )
                parameters = [user_id, *(f"%{token.casefold()}%" for token in tokens[:12])]
                order = " ORDER BY m.created_at DESC LIMIT ?"
            if kind_values:
                placeholders = ",".join("?" for _ in kind_values)
                sql += f" AND m.kind IN ({placeholders})"
                parameters.extend(kind_values)
            parameters.append(limit)
            rows = connection.execute(sql + order, parameters).fetchall()
        return tuple(_memory_from_row(row) for row in rows)

    def _delete_memory_sync(
        self,
        user_id: str,
        memory_id: str,
        actor: str,
    ) -> bool:
        with self._lock, self._require_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM memory_items WHERE user_id = ? AND memory_id = ?",
                (user_id, memory_id),
            )
            if cursor.rowcount:
                connection.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
                self._audit(
                    connection,
                    "delete_memory",
                    actor,
                    target_user_id=user_id,
                    target_memory_id=memory_id,
                )
            return bool(cursor.rowcount)

    def _record_behavior_attempt_sync(
        self,
        user_id: str,
        tool_name: str,
        request: dict[str, Any],
        result: dict[str, Any],
        status: BehaviorAttemptStatus,
        action_id: str | None,
        failure_class: str | None,
        now: datetime,
    ) -> BehaviorAttempt:
        timestamp = _utc(now)
        attempt_id = _id("attempt")
        with self._lock, self._require_connection() as connection:
            self._user_row(connection, user_id)
            connection.execute(
                """
                INSERT INTO behavior_attempts(
                    attempt_id, user_id, action_id, tool_name, request_json,
                    result_json, status, failure_class, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    user_id,
                    action_id,
                    tool_name,
                    json.dumps(request, ensure_ascii=False, sort_keys=True),
                    json.dumps(result, ensure_ascii=False, sort_keys=True),
                    status.value,
                    failure_class,
                    timestamp,
                ),
            )
        return BehaviorAttempt(
            attempt_id=attempt_id,
            user_id=user_id,
            action_id=action_id,
            tool_name=tool_name,
            request=request,
            result=result,
            status=status,
            failure_class=failure_class,
            created_at=datetime.fromisoformat(timestamp),
        )

    def _set_pending_behavior_confirmation_sync(
        self,
        user_id: str,
        session_id: str,
        attempt_id: str,
        ttl_seconds: int,
        now: datetime,
    ) -> None:
        timestamp = _utc(now)
        expires_at = _utc(now + timedelta(seconds=ttl_seconds))
        confirmation_id = _id("confirmation")
        with self._lock, self._require_connection() as connection:
            attempt = connection.execute(
                """
                SELECT 1 FROM behavior_attempts
                WHERE attempt_id = ? AND user_id = ? AND status = 'succeeded'
                """,
                (attempt_id, user_id),
            ).fetchone()
            if attempt is None:
                raise KeyError(f"unknown successful behavior attempt: {attempt_id}")
            connection.execute(
                """
                INSERT INTO pending_memory_confirmations(
                    confirmation_id, user_id, session_id, attempt_id,
                    expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, session_id) DO UPDATE SET
                    confirmation_id = excluded.confirmation_id,
                    attempt_id = excluded.attempt_id,
                    expires_at = excluded.expires_at,
                    created_at = excluded.created_at
                """,
                (confirmation_id, user_id, session_id, attempt_id, expires_at, timestamp),
            )

    def _take_pending_behavior_confirmation_sync(
        self,
        user_id: str,
        session_id: str,
        now: datetime,
    ) -> BehaviorAttempt | None:
        timestamp = _utc(now)
        with self._lock, self._require_connection() as connection:
            row = connection.execute(
                """
                SELECT behavior_attempts.*
                FROM pending_memory_confirmations
                JOIN behavior_attempts USING(attempt_id)
                WHERE pending_memory_confirmations.user_id = ?
                  AND pending_memory_confirmations.session_id = ?
                  AND pending_memory_confirmations.expires_at >= ?
                """,
                (user_id, session_id, timestamp),
            ).fetchone()
            connection.execute(
                """
                DELETE FROM pending_memory_confirmations
                WHERE user_id = ? AND session_id = ?
                """,
                (user_id, session_id),
            )
        return None if row is None else _attempt_from_row(row)

    def _link_behavior_memory_sync(self, attempt_id: str, memory_id: str) -> None:
        with self._lock, self._require_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE behavior_attempts
                SET memory_id = ?, user_confirmed = 1
                WHERE attempt_id = ?
                """,
                (memory_id, attempt_id),
            )
            if not cursor.rowcount:
                raise KeyError(f"unknown behavior attempt: {attempt_id}")

    def _prune_sync(self, now: datetime) -> dict[str, int]:
        timestamp = _utc(now)
        settings = self._settings_sync()
        failed_cutoff = _utc(now - timedelta(days=settings.failed_behavior_retention_days))
        with self._lock, self._require_connection() as connection:
            expired_ids = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT memory_id FROM memory_items
                    WHERE expires_at IS NOT NULL AND expires_at < ?
                    """,
                    (timestamp,),
                ).fetchall()
            ]
            failed_ids = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT memory_id FROM memory_items
                    WHERE kind = 'failed_behavior' AND created_at < ?
                    """,
                    (failed_cutoff,),
                ).fetchall()
            ]
            overflow_ids = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT memory_id FROM (
                        SELECT memory_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY user_id
                                ORDER BY created_at DESC, memory_id
                            ) AS user_rank
                        FROM memory_items
                        WHERE kind = 'failed_behavior'
                    )
                    WHERE user_rank > ?
                    """,
                    (settings.failed_behavior_cap,),
                ).fetchall()
            ]
            delete_ids = set(expired_ids) | set(failed_ids) | set(overflow_ids)
            for memory_id in delete_ids:
                connection.execute("DELETE FROM memory_items WHERE memory_id = ?", (memory_id,))
                connection.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            attempts = connection.execute(
                "DELETE FROM behavior_attempts WHERE created_at < ? AND status != 'succeeded'",
                (failed_cutoff,),
            ).rowcount
            confirmations = connection.execute(
                "DELETE FROM pending_memory_confirmations WHERE expires_at < ?",
                (timestamp,),
            ).rowcount
        return {
            "memory_items": len(delete_ids),
            "behavior_attempts": attempts,
            "pending_confirmations": confirmations,
        }

    @staticmethod
    def _user_row(connection: sqlite3.Connection, user_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown user: {user_id}")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _memory_row(
        connection: sqlite3.Connection,
        user_id: str,
        memory_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM memory_items WHERE user_id = ? AND memory_id = ?",
            (user_id, memory_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown memory for user: {memory_id}")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _sync_fts(
        connection: sqlite3.Connection,
        memory_id: str,
        user_id: str,
        kind: MemoryKind,
        content: str,
    ) -> None:
        connection.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
        connection.execute(
            "INSERT INTO memory_fts(memory_id, user_id, kind, content) VALUES (?, ?, ?, ?)",
            (memory_id, user_id, kind.value, content),
        )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        operation: str,
        actor: str,
        *,
        target_user_id: str | None = None,
        target_memory_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO memory_audit_events(
                event_id, operation, actor, target_user_id,
                target_memory_id, detail_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _id("audit"),
                operation,
                actor,
                target_user_id,
                target_memory_id,
                json.dumps(detail or {}, ensure_ascii=False, sort_keys=True),
                _utc(datetime.now(UTC)),
            ),
        )

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("memory store is not started")
        return self._connection


def _profile_from_row(row: sqlite3.Row) -> UserProfile:
    return UserProfile(
        user_id=row["user_id"],
        display_name=row["display_name"],
        preferred_robot_name=row["preferred_robot_name"],
        role=UserRole(row["role"]),
        face_status=FaceEnrollmentStatus(row["face_status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _memory_from_row(row: sqlite3.Row) -> MemoryItem:
    return MemoryItem(
        memory_id=row["memory_id"],
        user_id=row["user_id"],
        kind=MemoryKind(row["kind"]),
        content=row["content"],
        payload=json.loads(row["payload_json"]),
        source_session_id=row["source_session_id"],
        source_message_id=row["source_message_id"],
        source_action_id=row["source_action_id"],
        confidence=row["confidence"],
        sensitive=bool(row["sensitive"]),
        expires_at=None if row["expires_at"] is None else datetime.fromisoformat(row["expires_at"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _attempt_from_row(row: sqlite3.Row) -> BehaviorAttempt:
    return BehaviorAttempt(
        attempt_id=row["attempt_id"],
        user_id=row["user_id"],
        action_id=row["action_id"],
        tool_name=row["tool_name"],
        request=json.loads(row["request_json"]),
        result=json.loads(row["result_json"]),
        status=BehaviorAttemptStatus(row["status"]),
        failure_class=row["failure_class"],
        memory_id=row["memory_id"],
        user_confirmed=bool(row["user_confirmed"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _normalize_name(value: str) -> tuple[str, str]:
    display = " ".join(value.split())
    if not 1 <= len(display) <= 80:
        raise ValueError("display name must contain between 1 and 80 characters")
    return display, display.casefold()


def _utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must include timezone information")
    return value.astimezone(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
