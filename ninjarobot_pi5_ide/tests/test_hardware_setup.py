from __future__ import annotations

from pathlib import Path

import pytest

from ninjarobot_pi5_ide import hardware_setup


def test_status_is_read_only_and_reports_saved_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool = hardware_setup.TOOLS["servo"]
    config = tmp_path / "servo.json"
    config.write_text("{}")
    monkeypatch.setitem(
        hardware_setup.TOOLS,
        "servo",
        hardware_setup.HardwareSetupTool(
            tool.component, tool.command, config, tool.required, moves_actuators=True
        ),
    )
    monkeypatch.setattr(hardware_setup.shutil, "which", lambda _name: "/safe/pi5servo")

    from ninjarobot_pi5_ide.config_import import DiscoveredConfig

    monkeypatch.setattr(
        hardware_setup, "discover_pi5_configs", lambda: [DiscoveredConfig("pi5servo", config, True)]
    )
    status = hardware_setup.hardware_setup_status("servo")

    assert status["configuration_saved"] is True
    assert status["moves_actuators"] is True


def test_runner_receives_only_allowlisted_resolved_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(hardware_setup.shutil, "which", lambda _name: "/safe/pi5buzzer")

    result = hardware_setup.run_hardware_setup(
        "buzzer",
        ownership_path=tmp_path / "hardware.lock",
        runner=lambda command: calls.append(tuple(command)) or 0,
    )

    assert result == 0
    assert calls == [("/safe/pi5buzzer", "buzzer-tool")]
    assert (tmp_path / "hardware.lock").is_file()


def test_unknown_component_cannot_inject_a_command() -> None:
    with pytest.raises(ValueError, match="unknown hardware"):
        hardware_setup.run_hardware_setup("servo; shutdown now")


@pytest.mark.parametrize(
    "component,filename,payload,valid",
    [
        ("buzzer", "buzzer", {"pin": 17}, True),
        ("buzzer", "buzzer", {"pin": "secret-invalid"}, False),
        ("buzzer", "buzzer", {}, False),
        ("distance", "vl53l0x", {"offset_mm": 0}, True),
        ("distance", "vl53l0x", {"offset_mm": "bad"}, False),
        ("camera", "camera", {"camera": {"width": -1}}, False),
        ("camera", "camera", {"camera": {"width": 1280, "height": 720}}, True),
        ("servo", "servo", {"12": {}, "13": {}}, False),
        ("servo", "servo", {"12": {"pulse_center": 1500}, "13": {"pulse_center": 1500}}, True),
        ("servo", "servo", {"12": {"pulse_center": 0}, "13": {"pulse_center": 1500}}, False),
        ("microphone", "mic", {"audio": {"channels": 1}}, False),
    ],
)
def test_saved_settings_checked_without_opening_hardware(
    monkeypatch, tmp_path, component, filename, payload, valid
):
    import json

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.chdir(tmp_path)
    library = hardware_setup.TOOLS[component].component
    config = tmp_path / "xdg" / library / f"{filename}.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(payload))
    monkeypatch.setattr(hardware_setup.subprocess, "run", lambda *a, **k: pytest.fail("no devices"))
    result = hardware_setup.hardware_setup_status(component)
    assert result["configuration_saved"] is True
    assert result["configuration_valid"] is valid
    assert "secret-invalid" not in str(result["summary"])


def test_project_local_settings_use_same_discovery_as_import(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "buzzer.json").write_text('{"pin":17}')
    result = hardware_setup.hardware_setup_status("buzzer")
    assert result["configuration_valid"] is True
    assert result["configuration"] == str(tmp_path / "buzzer.json")


def test_microphone_asset_probe_preserves_runtime_import_containment(tmp_path):
    import sys

    command = tmp_path / "whisper-cli"
    command.write_text("#!/bin/sh\nexit 99\n")
    command.chmod(0o700)
    model = tmp_path / "model.bin"
    model.write_bytes(b"fixture")
    wake = tmp_path / "hey_Ninja.onnx"
    wake.write_bytes(b"fixture")
    before = {name for name in sys.modules if name.startswith("pi5mic")}
    hardware_setup._check_microphone_assets(
        {
            "stt": {
                "selected": "whisper_cpp",
                "whisper_cpp": {"command": str(command), "model_path": str(model)},
            },
            "wakeword": {"model_path": str(wake)},
            "voiceinput": {"enabled": True},
        }
    )
    assert {name for name in sys.modules if name.startswith("pi5mic")} == before
