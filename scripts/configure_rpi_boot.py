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
    finished = False
    for line in lines:
        stripped = line.strip()
        if stripped == BEGIN_MARKER:
            if inside or finished:
                raise ValueError("nested or duplicated NinjaRobotPi5 PWM configuration blocks")
            inside = True
            continue
        if stripped == END_MARKER:
            if not inside:
                raise ValueError("orphan NinjaRobotPi5 PWM configuration end marker")
            inside = False
            finished = True
            continue
        if not inside:
            if finished and stripped and not stripped.startswith("#"):
                raise ValueError("the managed PWM block must be the final configuration section")
            rendered.append(line)
    if inside:
        raise ValueError("unterminated NinjaRobotPi5 PWM configuration block")
    return rendered


def _directives(lines: list[str]) -> list[tuple[str, str]]:
    """Keep section context; never guess the value of a machine-specific filter."""
    section = "all"
    result: list[tuple[str, str]] = []
    for line in lines:
        value = line.split("#", 1)[0].strip()
        if not value:
            continue
        if value.startswith("[") and value.endswith("]"):
            # Filters of different types can accumulate until [all]. A later
            # model filter must not accidentally clear [none] or a serial filter.
            if value == "[all]":
                section = "all"
            elif value == "[none]" or section == "none":
                section = "none"
            else:
                section = "conditional"
            continue
        if value.startswith("include "):
            raise ValueError("included boot files require manual review before PWM configuration")
        result.append((section, value))
    return result


def _unconditional_overlays(lines: list[str]) -> list[str]:
    overlays: list[str] = []
    for section, value in _directives(lines):
        if not value.startswith("dtoverlay="):
            continue
        name = value.partition("=")[2].partition(",")[0].strip()
        if name not in {"pwm", "pwm-2chan"} or section == "none":
            continue
        if value != PWM_OVERLAY:
            raise ValueError("an unmanaged PWM overlay already exists with different settings")
        if section != "all":
            raise ValueError("move the existing PWM overlay to an unconditional [all] section")
        overlays.append(value)
    if len(overlays) > 1:
        raise ValueError("duplicated active PWM overlays require manual review")
    return overlays


def render_boot_config(source: str) -> str:
    """Return an idempotent config with the approved two-channel PWM setup."""
    lines = _without_managed_block(source.splitlines())
    active_overlays = _unconditional_overlays(lines)

    while lines and not lines[-1].strip():
        lines.pop()
    block = ["", BEGIN_MARKER, "[all]", AUDIO_OFF]
    if PWM_OVERLAY not in active_overlays:
        block.append(PWM_OVERLAY)
    block.append(END_MARKER)
    rendered = "\n".join([*lines, *block]) + "\n"
    valid, detail = validate_boot_config(rendered)
    if not valid:
        raise ValueError(detail)
    return rendered


def validate_boot_config(source: str) -> tuple[bool, str]:
    """Check the managed block and approved GPIO12/GPIO13 overlay."""
    lines = source.splitlines()
    stripped = [line.strip() for line in lines]
    if stripped.count(BEGIN_MARKER) != 1 or stripped.count(END_MARKER) != 1:
        return False, "the NinjaRobotPi5 PWM block is missing or duplicated"
    try:
        _without_managed_block(lines)
        overlays = _unconditional_overlays(lines)
        directives = _directives(lines)
    except ValueError as exc:
        return False, str(exc)
    begin = stripped.index(BEGIN_MARKER)
    end = stripped.index(END_MARKER)
    managed = [line.split("#", 1)[0].strip() for line in lines[begin + 1 : end]]
    managed = [line for line in managed if line]
    if managed not in (["[all]", AUDIO_OFF], ["[all]", AUDIO_OFF, PWM_OVERLAY]):
        return False, "the managed PWM block must contain the approved unconditional settings"
    audio = [
        (section, parameter)
        for section, value in directives
        if value.startswith("dtparam=")
        for parameter in value.removeprefix("dtparam=").split(",")
        if parameter.strip().startswith("audio=") and section != "none"
    ]
    if not audio or audio[-1] != ("all", "audio=off"):
        return False, "onboard analogue audio is not disabled"
    if len(overlays) != 1:
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
