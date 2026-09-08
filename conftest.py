"""Require explicit opt-in before executing hardware or live-provider tests."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("ninjarobot-safety")
    group.addoption(
        "--run-hardware",
        action="store_true",
        default=False,
        help="Enable hardware-marked tests only after explicit operator approval and safe setup.",
    )
    group.addoption(
        "--run-provider-live",
        action="store_true",
        default=False,
        help="Enable provider_live tests only after approving network access, privacy and costs.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    gates = {
        "hardware": ("--run-hardware", "Physical hardware tests require --run-hardware."),
        "provider_live": (
            "--run-provider-live",
            "Live provider tests require --run-provider-live.",
        ),
    }
    for item in items:
        for marker, (option, reason) in gates.items():
            if item.get_closest_marker(marker) is not None and not config.getoption(option):
                item.add_marker(pytest.mark.skip(reason=reason))
