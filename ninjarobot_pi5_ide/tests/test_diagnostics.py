from __future__ import annotations

from importlib.machinery import ModuleSpec
from pathlib import Path

import pytest
from ninjarobot_pi5_ide.config import load_robot_config

from ninjarobot_pi5_ide import diagnostics


def test_development_does_not_probe_optional_hardware(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def discover(name: str) -> ModuleSpec:
        seen.append(name)
        assert not name.startswith("pi5")
        return ModuleSpec(name, None, origin=f"/fake/{name}.py")

    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", discover)
    result = diagnostics.diagnose_environment(profile="development")
    assert result["ok"]
    assert "pytest" in seen
    assert "No hardware was opened" in result["limitations"]


def test_missing_driver_is_reported_without_import(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", lambda name: None)
    result = diagnostics.diagnose_environment()
    display = next(item for item in result["checks"] if item["name"] == "pi5disp")
    assert not result["ok"]
    assert display["status"] == "fail"
    assert "--extra hardware" in display["remedy"]
    assert "--no-sync" in display["remedy"]


def test_disabled_devices_are_not_requirements(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def discover(name: str) -> None:
        seen.append(name)

    config = load_robot_config(
        Path(__file__).resolve().parents[2] / "config/ninjarobot_pi5.toml.example"
    )
    config = config.model_copy(
        update={
            "hardware": config.hardware.model_copy(
                update={
                    name: getattr(config.hardware, name).model_copy(update={"enabled": False})
                    for name in ("display", "servos", "buzzer", "camera", "microphone")
                }
            )
        }
    )
    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", discover)
    diagnostics.diagnose_environment(config=config)
    assert "pi5disp" not in seen
    assert "pi5servo" not in seen
    assert "pi5mic" not in seen
    assert "pi5vl53l0x" in seen


def test_wrong_driver_checkout_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        diagnostics.importlib.util,
        "find_spec",
        lambda name: ModuleSpec(name, None, origin=f"/other/{name}/__init__.py"),
    )
    report = diagnostics.diagnose_environment(root=tmp_path)
    assert next(c for c in report["checks"] if c["name"] == "pi5disp")["status"] == "fail"


def test_broken_module_spec_is_a_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(name: str) -> None:
        raise ValueError("broken import metadata")

    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", broken)
    assert not diagnostics.diagnose_environment(profile="development")["ok"]
