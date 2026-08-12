from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ninjarobot_pi5_agent import (
    BehaviorAttemptStatus,
    FaceEnrollmentStatus,
    MemoryKind,
    MemorySettings,
    MemoryStore,
    ProfileDeletionError,
    UserRole,
    memory_migrations,
)


def test_profiles_preserve_single_owner_and_protect_active_users(tmp_path: Path) -> None:
    async def exercise() -> None:
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()

        owner = await store.create_profile("Roger Chang")
        member = await store.create_profile("Student One")
        assert owner.user_id == "local-user"
        assert owner.role is UserRole.OWNER
        assert member.role is UserRole.MEMBER
        assert (await store.owner()) == owner

        with pytest.raises(ProfileDeletionError, match="active"):
            await store.delete_profile(member.user_id, active_user_ids={member.user_id})
        with pytest.raises(ProfileDeletionError, match="ownership"):
            await store.delete_profile(owner.user_id)

        await store.transfer_owner(member.user_id)
        assert (await store.owner()).user_id == member.user_id  # type: ignore[union-attr]
        await store.delete_profile(owner.user_id)
        assert [profile.user_id for profile in await store.profiles()] == [member.user_id]
        await store.close()

    asyncio.run(exercise())


def test_memory_is_strictly_user_scoped_and_searchable(tmp_path: Path) -> None:
    async def exercise() -> None:
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()
        owner = await store.create_profile("Owner")
        member = await store.create_profile("Member")
        first = await store.add_memory(
            owner.user_id,
            MemoryKind.SUCCESSFUL_BEHAVIOR,
            "Wave the left arm and show a happy face",
            payload={"behavior_id": "wave-happy"},
        )
        await store.add_memory(
            member.user_id,
            MemoryKind.SUCCESSFUL_BEHAVIOR,
            "Wave the right arm and play a tone",
        )

        assert [item.memory_id for item in await store.search(owner.user_id, "wave happy")] == [
            first.memory_id
        ]
        assert await store.search(member.user_id, "happy") == ()
        with pytest.raises(KeyError):
            await store.memory(member.user_id, first.memory_id)
        assert not await store.delete_memory(member.user_id, first.memory_id)
        assert await store.memory(owner.user_id, first.memory_id) == first
        await store.close()

    asyncio.run(exercise())


def test_preferences_face_data_settings_and_failure_retention(tmp_path: Path) -> None:
    async def exercise() -> None:
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()
        owner = await store.create_profile("Owner")
        preference = await store.upsert_preference(
            owner.user_id,
            "favorite color",
            "blue",
            source="explicit user statement",
            inferred=False,
        )
        assert preference.kind is MemoryKind.PREFERENCE
        face = await store.set_face_profile(
            owner.user_id,
            face_index_name="face-owner",
            profile_image_path="/var/lib/ninjarobot/faces/owner.jpg",
            model_metadata={"backend": "pi5camera"},
        )
        assert face.user_id == owner.user_id
        assert (await store.profile(owner.user_id)).face_status is FaceEnrollmentStatus.ENROLLED

        settings = await store.update_settings(
            conversation_retention_days=14,
            failed_behavior_retention_days=30,
            failed_behavior_cap=10,
        )
        assert settings.conversation_retention_days == 14
        old = datetime(2026, 1, 1, tzinfo=UTC)
        await store.add_memory(
            owner.user_id,
            MemoryKind.FAILED_BEHAVIOR,
            "Servo command failed",
            now=old,
        )
        await store.record_behavior_attempt(
            owner.user_id,
            tool_name="robot.servo.move",
            request={"endpoint": "gpio12"},
            result={"error": "test"},
            status=BehaviorAttemptStatus.FAILED,
            failure_class="hardware",
            now=old,
        )
        pruned = await store.prune(now=old + timedelta(days=31))
        assert pruned["memory_items"] == 1
        assert pruned["behavior_attempts"] == 1
        await store.close()

    asyncio.run(exercise())


def test_conversation_migration_backfills_user_scope(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE messages (
            message_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(session_id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            name TEXT,
            tool_call_id TEXT,
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        );
        INSERT INTO sessions VALUES (
            'legacy-session', 'legacy-user',
            '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
        );
        INSERT INTO messages VALUES (
            'legacy-message', 'legacy-session', 'user', 'hello', NULL, NULL,
            '2026-01-01T00:00:00+00:00', '{}'
        );
        """
    )
    connection.close()

    async def exercise() -> None:
        store = MemoryStore(path)
        await store.start()
        await store.close()

    asyncio.run(exercise())
    connection = sqlite3.connect(path)
    row = connection.execute(
        "SELECT user_id, tool_calls_json FROM messages WHERE message_id = 'legacy-message'"
    ).fetchone()
    versions = connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()
    connection.close()
    assert row == ("legacy-user", "[]")
    assert versions == [(1,), (2,), (3,)]


def test_configured_defaults_initialize_once_without_overwriting_cli_settings(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()
        initialized = await store.initialize_settings(
            MemorySettings(
                conversation_retention_days=12,
                failed_behavior_retention_days=90,
            )
        )
        assert initialized.conversation_retention_days == 12
        await store.update_settings(conversation_retention_days=20)
        preserved = await store.initialize_settings(MemorySettings(conversation_retention_days=3))
        assert preserved.conversation_retention_days == 20
        await store.close()

    asyncio.run(exercise())


def test_failed_migration_rolls_back_schema_and_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "rollback.sqlite3"
    original = memory_migrations._MIGRATIONS  # noqa: SLF001

    def failing_migration(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE partial_phase7_change(value TEXT)")
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(memory_migrations, "_MIGRATIONS", (*original, failing_migration))
    connection = sqlite3.connect(path)
    with pytest.raises(RuntimeError, match="simulated migration failure"):
        memory_migrations.migrate_agent_database(connection)
    partial = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'partial_phase7_change'"
    ).fetchone()
    versions = connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()
    connection.close()
    assert partial is None
    assert versions == [(1,), (2,), (3,)]
