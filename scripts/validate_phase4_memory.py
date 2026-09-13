"""Measure bounded retrieval on synthetic data in an automatically removed database."""

from __future__ import annotations

import asyncio
import json
import statistics
import tempfile
import time
from pathlib import Path

from ninjarobot_pi5_agent.memory_services import MemoryRetrievalService
from ninjarobot_pi5_agent.memory_store import MemoryStore
from ninjarobot_pi5_agent.models import MemoryKind


async def evaluate(path: Path) -> dict[str, object]:
    store = MemoryStore(path)
    await store.start()
    try:
        owner = await store.create_profile("Synthetic owner")
        other = await store.create_profile("Synthetic second user")
        target = await store.add_memory(
            owner.user_id, MemoryKind.EPISODIC_SUMMARY, "Repaired the blue greeting display"
        )
        for index in range(1000):
            await store.add_memory(
                owner.user_id if index % 2 else other.user_id,
                MemoryKind.EPISODIC_SUMMARY,
                f"Unrelated synthetic record {index} about red lights",
            )
        # A matching second user's text must not steal the result.
        await store.add_memory(
            other.user_id, MemoryKind.EPISODIC_SUMMARY, "Repaired the blue greeting display"
        )
        durations = []
        for _ in range(50):
            start = time.perf_counter()
            found = await store.search(owner.user_id, "blue greeting")
            durations.append((time.perf_counter() - start) * 1000)
            assert found and found[0].memory_id == target.memory_id
            assert all(item.user_id == owner.user_id for item in found)
        context = await MemoryRetrievalService(store).context(owner.user_id, "blue greeting")
        assert target.content in context
        assert len(context) <= (await store.settings()).retrieval_character_budget
        return {
            "synthetic_records": 1002,
            "users": 2,
            "queries": 50,
            "top_result_misses": 0,
            "median_ms": round(statistics.median(durations), 3),
            "max_ms": round(max(durations), 3),
            "context_characters": len(context),
            "hardware_actions": 0,
        }
    finally:
        await store.close()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ninja-memory-evaluation-") as directory:
        print(json.dumps(asyncio.run(evaluate(Path(directory) / "synthetic.sqlite3")), indent=2))


if __name__ == "__main__":
    main()
