"""Tests for lightweight pi5camera startup."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_importing_pi5camera_package_is_lightweight() -> None:
    result = _run_python(
        "import json, sys, pi5camera; "
        "print(json.dumps({"
        "'capture': 'pi5camera.core.capture' in sys.modules, "
        "'face_index': 'pi5camera.storage.face_index' in sys.modules, "
        "'pil': 'PIL' in sys.modules"
        "}))"
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload == {"capture": False, "face_index": False, "pil": False}


def test_cli_help_is_lightweight() -> None:
    result = _run_python(
        "import json, sys; "
        "from click.testing import CliRunner; "
        "from pi5camera.__main__ import cli; "
        "run = CliRunner().invoke(cli, ['--help']); "
        "print(json.dumps({"
        "'exit_code': run.exit_code, "
        "'capture': 'pi5camera.core.capture' in sys.modules, "
        "'face_index': 'pi5camera.storage.face_index' in sys.modules, "
        "'pil': 'PIL' in sys.modules"
        "}))"
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload == {"exit_code": 0, "capture": False, "face_index": False, "pil": False}
