from __future__ import annotations

import json
import subprocess
import sys
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


def test_managed_driver_directories_exist() -> None:
    missing = [name for name in MANAGED_DRIVERS if not (ROOT / name).is_dir()]
    assert missing == []


def test_historical_repository_is_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/NinjaClawBot/" in gitignore


def test_driver_change_authorization_manifest_exists() -> None:
    path = ROOT / "docs" / "validation" / "authorized_driver_changes.json"
    assert path.is_file()


def test_driver_provenance_manifests_match_worktree() -> None:
    baseline = ROOT / "docs" / "validation" / "immutable_driver_baseline.json"
    authorizations = ROOT / "docs" / "validation" / "authorized_driver_changes.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "verify_immutable_drivers.py"),
            "--baseline",
            str(baseline),
            "--authorizations",
            str(authorizations),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_driver_provenance_rejects_unknown_authorization(tmp_path: Path) -> None:
    source = ROOT / "docs" / "validation" / "authorized_driver_changes.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["files"]["pi5unknown/example.py"] = {}
    authorizations = tmp_path / "authorizations.json"
    authorizations.write_text(json.dumps(payload), encoding="utf-8")
    baseline = ROOT / "docs" / "validation" / "immutable_driver_baseline.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "verify_immutable_drivers.py"),
            "--baseline",
            str(baseline),
            "--authorizations",
            str(authorizations),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "invalid authorization: pi5unknown/example.py" in result.stdout


def test_driver_provenance_ignores_documented_runtime_data() -> None:
    script = ROOT / "scripts" / "verify_immutable_drivers.py"
    namespace: dict[str, object] = {
        "__file__": str(script),
        "__name__": "verify_immutable_drivers_test",
    }
    exec(compile(script.read_text(encoding="utf-8"), str(script), "exec"), namespace)
    is_generated = namespace["_is_generated"]

    assert is_generated(Path("pi5buzzer/buzzer.json"))
    assert is_generated(Path("pi5servo/servo.json"))
    assert is_generated(Path("pi5vl53l0x/src/pi5vl53l0x/config/vl53l0x.json"))
    assert is_generated(Path("pi5camera/photo/test.jpg"))
    assert is_generated(Path("pi5camera/camera_data/index/encodings.json"))
    assert not is_generated(Path("pi5camera/src/pi5camera/driver.py"))
    assert not is_generated(Path("pi5buzzer/pyproject.toml"))


def test_required_project_documents_exist() -> None:
    required = (
        "README.md",
        "DevelopmentGuide.md",
        "DevelopmentLog.md",
        "InstallationGuide.md",
        "NinjaRobotPi5V4_ImplementationPlan.md",
    )
    missing = [name for name in required if not (ROOT / name).is_file()]
    assert missing == []
