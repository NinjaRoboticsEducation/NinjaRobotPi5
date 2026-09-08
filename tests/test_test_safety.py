"""Exercise opt-in flags with synthetic tests that never open real hardware."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ([], "1 passed, 2 skipped"),
        (["--run-hardware"], "2 passed, 1 skipped"),
        (["--run-provider-live"], "2 passed, 1 skipped"),
        (["--run-hardware", "--run-provider-live"], "3 passed"),
        (["-m", "hardware"], "1 skipped, 2 deselected"),
    ],
)
def test_opt_in_is_required_even_with_marker_selection(tmp_path: Path, options, expected) -> None:
    root = Path(__file__).resolve().parents[1]
    shutil.copyfile(root / "conftest.py", tmp_path / "conftest.py")
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    hardware: synthetic hardware marker\n"
        "    provider_live: synthetic provider marker\n"
    )
    (tmp_path / "test_synthetic.py").write_text(
        "import pytest\n"
        "def test_safe():\n    assert True\n"
        "@pytest.mark.hardware\ndef test_fake_hardware():\n    assert True\n"
        "@pytest.mark.provider_live\ndef test_fake_provider():\n    assert True\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--strict-markers", *options],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert expected in result.stdout
