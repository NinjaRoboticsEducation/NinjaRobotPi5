from __future__ import annotations

import stat
from pathlib import Path

from ninjarobot_pi5_ide.runtime_control import ActiveBehaviorRegistry


def test_active_behavior_registration_is_private_and_owner_clearable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "active.json"
    registry = ActiveBehaviorRegistry(path)

    registry.register("move_forward")

    payload = registry.read()
    assert payload is not None
    assert payload["behavior"] == "move_forward"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    registry.clear()
    assert registry.read() is None
