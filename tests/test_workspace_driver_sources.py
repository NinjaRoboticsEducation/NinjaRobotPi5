"""Regression tests for editable managed-driver workspace configuration."""

from __future__ import annotations

import tomllib
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


def test_all_managed_drivers_are_editable_path_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sources = project["tool"]["uv"]["sources"]

    for package in MANAGED_DRIVERS:
        assert sources[package] == {"path": package, "editable": True}


def test_lockfile_preserves_editable_managed_driver_sources() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = {package["name"]: package for package in lock["package"]}

    for package in MANAGED_DRIVERS:
        assert packages[package]["source"] == {"editable": package}
