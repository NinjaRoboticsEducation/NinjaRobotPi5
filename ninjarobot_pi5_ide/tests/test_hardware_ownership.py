from __future__ import annotations

import json
from pathlib import Path

import pytest
from ninjarobot_pi5_ide.hardware_ownership import (
    HardwareOwnership,
    HardwareOwnershipError,
)


def test_hardware_ownership_is_exclusive_and_reusable(tmp_path: Path) -> None:
    lock_path = tmp_path / "hardware-owner.lock"
    first = HardwareOwnership(lock_path)
    second = HardwareOwnership(lock_path)

    first.acquire()
    assert first.owned is True
    metadata = json.loads(lock_path.read_text(encoding="utf-8"))
    assert metadata["pid"] > 0
    assert metadata["program"]

    with pytest.raises(HardwareOwnershipError, match="already owned") as failure:
        second.acquire()
    assert '"pid":' in str(failure.value)

    first.release()
    assert first.owned is False
    second.acquire()
    assert second.owned is True
    second.release()
    assert lock_path.read_text(encoding="utf-8") == ""


def test_hardware_ownership_release_is_idempotent(tmp_path: Path) -> None:
    ownership = HardwareOwnership(tmp_path / "hardware-owner.lock")

    ownership.release()
    ownership.acquire()
    ownership.release()
    ownership.release()

    assert ownership.owned is False
