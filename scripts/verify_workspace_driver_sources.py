#!/usr/bin/env python3
"""Verify that the root environment executes managed drivers from this checkout."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGED_DRIVERS = (
    "pi5buzzer",
    "pi5camera",
    "pi5disp",
    "pi5mic",
    "pi5servo",
    "pi5vl53l0x",
)


def verify_driver_sources(root: Path = ROOT) -> list[str]:
    """Return clear failures for drivers that do not resolve into this checkout."""
    failures: list[str] = []
    for package in MANAGED_DRIVERS:
        expected_root = (root / package / "src" / package).resolve()
        spec = importlib.util.find_spec(package)
        if spec is None or spec.origin is None:
            failures.append(f"{package}: package is not installed")
            continue

        origin = Path(spec.origin).resolve()
        if not origin.is_relative_to(expected_root):
            failures.append(
                f"{package}: resolves to {origin}, expected a file under {expected_root}"
            )
    return failures


def main() -> int:
    """Print a concise pass/fail result for shell and bootstrap use."""
    failures = verify_driver_sources()
    if failures:
        print("FAIL: managed driver source mismatch")
        for failure in failures:
            print(f"- {failure}")
        print("Run: uv sync --frozen --extra hardware")
        return 1

    print("PASS: all 6 managed Pi5 libraries execute directly from this checkout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
