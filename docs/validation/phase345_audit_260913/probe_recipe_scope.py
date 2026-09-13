"""Audit diagnostic: synthetic data only; run from the checkout root.

Reports current behavior, including defects; exit zero is not feature acceptance.
Uses the repository test fixture, never a live Agent, hardware or Google account.
"""

# ruff: noqa: E402
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "ninjarobot_pi5_agent/tests"))
from ninjarobot_pi5_agent.memory_mcp import MemoryMCPProvider
from ninjarobot_pi5_agent.memory_services import MemoryRetrievalService
from ninjarobot_pi5_agent.recipe_controls import recipe_action
from ninjarobot_pi5_agent.tools import ToolRegistry
from test_information_controls import runtime_for


async def run(path):
    r = await runtime_for(path)
    original_tools = r.tools
    try:
        owner = await r.memory.profile("local-user")
        member = await r.memory.create_profile("Audit Member")
        await r._set_active_user("one", owner)
        retrieval = MemoryRetrievalService(r.memory)
        original = retrieval.profile_payload
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(user):
            result = await original(user)
            entered.set()
            await release.wait()
            return result

        retrieval.profile_payload = delayed
        r.tools = ToolRegistry((MemoryMCPProvider(retrieval, r.store),))
        await r.tools.start()
        recipe = {
            "id": "audit-profile",
            "name": "Audit profile",
            "purpose": "Read owned profile",
            "steps": [{"tool": "memory.profile.get", "expected": "Current owned profile"}],
        }
        preview = await recipe_action(r, "one", {"operation": "preview", "recipe": recipe})
        saved = await recipe_action(
            r, "one", {"operation": "save", "recipe": recipe, "review_hash": preview["review_hash"]}
        )
        worker = asyncio.create_task(
            recipe_action(
                r,
                "one",
                {
                    "operation": "run",
                    "recipe_id": "audit-profile",
                    "version": saved["version"],
                    "confirmed": True,
                },
            )
        )
        await asyncio.wait_for(entered.wait(), 3)
        await r._set_active_user("one", member)
        release.set()
        result = await worker
        print("recipe scope changed:", (await r.task_scope("one"))[1] == member.user_id)
        print("recipe result:", result["status"])
        print("previous owner data returned:", "local-user" in str(result["results"]))
    finally:
        await r.close()
        await original_tools.close()


with tempfile.TemporaryDirectory(prefix="ninja-audit-recipe-") as d:
    asyncio.run(run(Path(d)))
