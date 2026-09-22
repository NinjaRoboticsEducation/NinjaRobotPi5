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
