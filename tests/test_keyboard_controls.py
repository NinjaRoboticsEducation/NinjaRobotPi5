from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_keyboard_controls_stop_on_release_and_focus_loss() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the fake browser keyboard regression check")
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [node, str(root / "tests/check_keyboard_controls.cjs")],
        cwd=root,
        check=True,
        timeout=10,
        capture_output=True,
        text=True,
    )
