#!/usr/bin/env python3
"""Synthetic, non-hardware Phase 7 SQLite retrieval benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import tempfile
import time
from pathlib import Path

from ninjarobot_pi5_agent import MemoryKind, MemoryRetrievalService, MemoryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=int, default=1000)
    parser.add_argument("--queries", type=int, default=50)
    parser.add_argument("--max-p95-ms", type=float, default=100.0)
    parser.add_argument("--max-database-mib", type=float, default=16.0)
    return parser


async def benchmark(arguments: argparse.Namespace) -> dict[str, object]:
    if not 100 <= arguments.entries <= 100_000:
        raise ValueError("entries must be between 100 and 100000")
    if not 5 <= arguments.queries <= 10_000:
        raise ValueError("queries must be between 5 and 10000")
    with tempfile.TemporaryDirectory(prefix="ninjarobot-memory-benchmark-") as directory:
        database = Path(directory) / "memory.sqlite3"
        store = MemoryStore(database)
        await store.start()
        owner = await store.create_profile("Benchmark Owner")
        for index in range(arguments.entries):
            await store.add_memory(
                owner.user_id,
                (MemoryKind.SUCCESSFUL_BEHAVIOR if index % 4 else MemoryKind.FAILED_BEHAVIOR),
                f"benchmark behavior {index} wave face tone servo pattern {index % 25}",
                payload={"synthetic": True, "index": index},
            )
        retrieval = MemoryRetrievalService(store)
        samples_ms: list[float] = []
        for index in range(arguments.queries):
            started = time.perf_counter()
            context = await retrieval.context(owner.user_id, f"wave pattern {index % 25}")
            samples_ms.append((time.perf_counter() - started) * 1000)
            if len(context) > (await store.settings()).retrieval_character_budget:
                raise RuntimeError("retrieval exceeded its configured character budget")
        await store.close()
        database_bytes = database.stat().st_size
    ordered = sorted(samples_ms)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    p95_ms = ordered[p95_index]
    max_database_bytes = int(arguments.max_database_mib * 1024 * 1024)
    passed = p95_ms <= arguments.max_p95_ms and database_bytes <= max_database_bytes
    return {
        "entries": arguments.entries,
        "queries": arguments.queries,
        "median_ms": round(statistics.median(samples_ms), 3),
        "p95_ms": round(p95_ms, 3),
        "database_bytes": database_bytes,
        "limits": {
            "max_p95_ms": arguments.max_p95_ms,
            "max_database_bytes": max_database_bytes,
        },
        "passed": passed,
    }


def main() -> int:
    arguments = build_parser().parse_args()
    report = asyncio.run(benchmark(arguments))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
