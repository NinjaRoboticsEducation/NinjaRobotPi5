#!/usr/bin/env python3
"""Run the supported Calendar setup using this checkout's locked environment."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    executable = root / ".venv/bin/ninjarobot-agent"
    if not executable.is_file():
        raise SystemExit(
            "Install the NinjaRobotPi5 environment first; .venv/bin/ninjarobot-agent is missing."
        )
    arguments = sys.argv[1:]
    read_only = "--read-only" in arguments
    if read_only and "--write" in arguments:
        raise SystemExit("Choose either --read-only or --write, not both.")
    arguments = [value for value in arguments if value != "--read-only"]
    mode = [] if read_only or "--write" in arguments else ["--write"]
    print(
        "Calendar setup: read-only."
        if read_only
        else "Calendar setup: read and reviewed event creation; Google consent is required.",
        flush=True,
    )
    os.execv(str(executable), [str(executable), "calendar-connect", *mode, *arguments])


if __name__ == "__main__":
    main()
