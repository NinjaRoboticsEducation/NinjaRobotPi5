"""Direct user review and correction of local memory, independent of a model."""

from __future__ import annotations

import json
import shlex

from .memory_services import memory_explanation
from .memory_store import MemoryStore


async def memory_command(store: MemoryStore, user_id: str, text: str) -> str:
    try:
        parts = shlex.split(text)
        if parts == ["/memory", "review"]:
            records = await store.memories(user_id, limit=100)
            summaries: list[str] = []
            for item in records:
                summary = json.dumps(
                    {
                        "id": item.memory_id,
                        "content": item.content,
                        "confidence": item.confidence,
                        **memory_explanation(item),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                if sum(map(len, summaries)) + len(summary) > 14_000:
                    summaries.append(
                        "More items are available through the local memory list command."
                    )
                    break
                summaries.append(summary)
            return "\n\n".join(summaries) or "No saved memory items for the active user."
        if len(parts) == 3 and parts[1] == "confirm":
            item = await store.correct_preference(user_id, parts[2])
            return f"Preference confirmed: {item.memory_id}: {item.content}"
        if len(parts) >= 4 and parts[1] == "edit":
            item = await store.correct_preference(user_id, parts[2], " ".join(parts[3:]))
            return f"Preference corrected and confirmed: {item.memory_id}: {item.content}"
        if len(parts) == 3 and parts[1] == "forget":
            removed = await store.delete_memory(user_id, parts[2], actor="direct-user-forget")
            return (
                "Memory item removed, including its active preference value."
                if removed
                else "Item not found."
            )
        return (
            "Use /memory review to see source, confidence, reason and confirmation. "
            "Use /memory confirm ID to confirm a reviewed preference, /memory edit ID NEW TEXT "
            "to correct it, or /memory forget ID to remove it. These affect only the active user. "
            "Technical behavior outcomes can be reviewed or removed, not rewritten as successes."
        )
    except (ValueError, KeyError) as error:
        return f"Memory not changed: {error}"
