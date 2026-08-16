#!/usr/bin/env python3
"""Render and validate the NinjaRobotPi5 Raspberry Pi PWM boot configuration."""

from __future__ import annotations

import argparse
from pathlib import Path

BEGIN_MARKER = "# BEGIN NinjaRobotPi5 managed PWM"
END_MARKER = "# END NinjaRobotPi5 managed PWM"
PWM_OVERLAY = "dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4"
AUDIO_OFF = "dtparam=audio=off"


def _without_managed_block(lines: list[str]) -> list[str]:
    rendered: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if stripped == BEGIN_MARKER:
            if inside:
                raise ValueError("nested NinjaRobotPi5 PWM configuration blocks")
            inside = True
            continue
        if stripped == END_MARKER:
            if not inside:
                raise ValueError("orphan NinjaRobotPi5 PWM configuration end marker")
            inside = False
            continue
        if not inside:
            rendered.append(line)
    if inside:
        raise ValueError("unterminated NinjaRobotPi5 PWM configuration block")
    return rendered


def render_boot_config(source: str) -> str:
    """Return an idempotent config with the approved two-channel PWM setup."""
    lines = _without_managed_block(source.splitlines())
    active_overlays = [
        line.strip()
        for line in lines
        if line.strip().startswith("dtoverlay=pwm-2chan") and not line.lstrip().startswith("#")
    ]
    conflicting = [line for line in active_overlays if line != PWM_OVERLAY]
    if conflicting:
        raise ValueError(
            "an unmanaged pwm-2chan overlay already exists with different settings: "
            + "; ".join(conflicting)
        )

    while lines and not lines[-1].strip():
        lines.pop()
    block = ["", BEGIN_MARKER, "[all]", AUDIO_OFF]
    if PWM_OVERLAY not in active_overlays:
        block.append(PWM_OVERLAY)
    block.append(END_MARKER)
    return "\n".join([*lines, *block]) + "\n"


def validate_boot_config(source: str) -> tuple[bool, str]:
    """Check the managed block and approved GPIO12/GPIO13 overlay."""
    lines = source.splitlines()
    if lines.count(BEGIN_MARKER) != 1 or lines.count(END_MARKER) != 1:
        return False, "the NinjaRobotPi5 PWM block is missing or duplicated"
    active = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if AUDIO_OFF not in active:
        return False, "onboard analogue audio is not disabled"
    if PWM_OVERLAY not in active:
        return False, "the GPIO12/GPIO13 pwm-2chan overlay is missing"
    return True, "GPIO12/PWM0 and GPIO13/PWM1 are configured"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    source = arguments.source.read_text(encoding="utf-8")
    if arguments.check:
        valid, detail = validate_boot_config(source)
        print(detail)
        return 0 if valid else 1
    if arguments.output is None:
        parser.error("--output is required unless --check is used")
    arguments.output.write_text(render_boot_config(source), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
