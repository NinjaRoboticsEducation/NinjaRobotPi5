"""Synthetic retrieval checks; no personal conversation or hardware."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ninjarobot_pi5_agent.memory_store import MemoryStore
from ninjarobot_pi5_agent.models import MemoryKind


@pytest.mark.parametrize("fallback", [False, True])
def test_bounded_owner_ranking_and_expiration(tmp_path: Path, fallback: bool) -> None:
    async def exercise() -> None:
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()
        try:
            owner = await store.create_profile("Owner")
            other = await store.create_profile("Other")
            if fallback:
                with store._lock:
                    connection = store._require_connection()
                    connection.execute("DROP TABLE memory_fts")
                    connection.execute(
                        "CREATE TABLE memory_fts(memory_id TEXT, user_id TEXT, "
                        "kind TEXT, content TEXT)"
                    )
            relevant = await store.add_memory(
                owner.user_id, MemoryKind.PREFERENCE, "green tea", payload={"inferred": False}
            )
            await store.add_memory(
                owner.user_id, MemoryKind.PREFERENCE, "tea", payload={"inferred": True}
            )
            await store.add_memory(other.user_id, MemoryKind.PREFERENCE, "green tea")
            await store.add_memory(
                owner.user_id, MemoryKind.PREFERENCE, "green tea secret", sensitive=True
            )
            await store.add_memory(
                owner.user_id,
                MemoryKind.PREFERENCE,
                "green tea expired",
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
            results = await store.search(owner.user_id, "green tea")
            assert results[0].memory_id == relevant.memory_id
            assert len(results) == 2
            assert await store.search(owner.user_id, '" OR * _') == ()
            assert await store.search(owner.user_id, "") == ()
            assert len(await store.search(owner.user_id, "tea " * 10000)) <= 6
            await store.correct_preference(owner.user_id, relevant.memory_id, "coffee")
            assert all(
                item.memory_id != relevant.memory_id
                for item in await store.search(owner.user_id, "tea")
            )
            await store.delete_memory(owner.user_id, relevant.memory_id)
            assert await store.search(owner.user_id, "coffee") == ()
            japanese = await store.add_memory(
                owner.user_id, MemoryKind.EPISODIC_SUMMARY, "朝は緑茶が好きです"
            )
            chinese = await store.add_memory(
                owner.user_id, MemoryKind.EPISODIC_SUMMARY, "早餐喜歡綠茶"
            )
            assert (await store.search(owner.user_id, "緑茶"))[0] == japanese
            assert (await store.search(owner.user_id, "綠茶"))[0] == chinese
        finally:
            await store.close()

    asyncio.run(exercise())
