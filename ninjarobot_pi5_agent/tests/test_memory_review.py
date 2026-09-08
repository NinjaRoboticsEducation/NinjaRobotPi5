from __future__ import annotations

import asyncio

import pytest
from ninjarobot_pi5_agent.memory_controls import memory_command
from ninjarobot_pi5_agent.memory_services import MemoryRetrievalService, memory_explanation
from ninjarobot_pi5_agent.memory_store import MemoryStore
from ninjarobot_pi5_agent.models import MemoryKind


def test_inference_cannot_replace_or_demote_confirmed_preference(tmp_path):
    async def exercise():
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()
        try:
            user = await store.create_profile("Test owner")
            confirmed = await store.upsert_preference(user.user_id, "drink", "tea", source="user")
            repeated = await store.upsert_preference(
                user.user_id, "drink", "tea", source="guess", confidence=0.5, inferred=True
            )
            assert repeated == confirmed
            suggested = await store.upsert_preference(
                user.user_id, "drink", "coffee", source="guess", confidence=0.5, inferred=True
            )
            assert await store.preference_value(user.user_id, "drink") == "tea"
            assert suggested.memory_id != confirmed.memory_id
            assert memory_explanation(suggested)["category"] == "unconfirmed_suggestion"
            review = await memory_command(store, user.user_id, "/memory review")
            assert "conflicts with a confirmed preference" in review
            assert "last_confirmed_at" in review
            await memory_command(store, user.user_id, f"/memory confirm {suggested.memory_id}")
            assert await store.preference_value(user.user_id, "drink") == "coffee"
            with pytest.raises(KeyError):
                await store.memory(user.user_id, suggested.memory_id)
            await memory_command(store, user.user_id, f"/memory edit {confirmed.memory_id} water")
            assert await store.preference_value(user.user_id, "drink") == "water"
            await memory_command(store, user.user_id, f"/memory forget {confirmed.memory_id}")
            assert await store.preference_value(user.user_id, "drink") is None
            assert await store.search(user.user_id, "water") == ()
        finally:
            await store.close()

    asyncio.run(exercise())


def test_review_preserves_scope_and_distinguishes_suggestions(tmp_path):
    async def exercise():
        store = MemoryStore(tmp_path / "memory.sqlite3")
        await store.start()
        try:
            first = await store.create_profile("First")
            second = await store.create_profile("Second")
            item = await store.add_memory(
                first.user_id,
                MemoryKind.PREFERENCE,
                "User likes tea",
                payload={"inferred": True},
                confidence=0.8,
                source_session_id="source-session",
            )
            context = await MemoryRetrievalService(store).context(first.user_id, "drink")
            assert "Unconfirmed suggestion: User likes tea" in context
            with pytest.raises(KeyError):
                await store.correct_preference(second.user_id, item.memory_id, "Other")
            await store.correct_preference(first.user_id, item.memory_id)
            context = await MemoryRetrievalService(store).context(first.user_id, "drink")
            assert "Confirmed preference: User likes tea" in context
            reviewed = await store.memory(first.user_id, item.memory_id)
            assert memory_explanation(reviewed)["source"]["session"] == "source-session"
            assert memory_explanation(reviewed)["last_confirmed_at"] is not None
            outcome = await store.add_memory(first.user_id, MemoryKind.FAILED_BEHAVIOR, "Failed")
            assert memory_explanation(outcome)["category"] == "task_outcome"
            with pytest.raises(ValueError, match="technical evidence"):
                await store.correct_preference(first.user_id, outcome.memory_id, "Succeeded")
        finally:
            await store.close()

    asyncio.run(exercise())
