from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from ninjarobot_pi5_agent.deployment import (
    HELPER_PATH,
    SUDOERS_PATH,
    UNIT_NAME,
    UNIT_PATH,
    DeploymentManager,
    DeploymentSpec,
    create_backup,
    current_spec,
    render_unit,
    restore_backup,
)

from ninjarobot_pi5_ide import load_robot_config


def _spec(tmp_path: Path) -> DeploymentSpec:
    root = Path(__file__).resolve().parents[2]
    config = tmp_path / "config.toml"
    config.write_text(
        (root / "config" / "ninjarobot_pi5.toml.example").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    mcp = tmp_path / "mcp.toml"
    mcp.write_text("schema_version = 1\nservers = []\n", encoding="utf-8")
    secret = tmp_path / "secrets.env"
    secret.write_text("", encoding="utf-8")
    secret.chmod(0o600)
    return DeploymentSpec(
        user=os.environ.get("USER", "rogerchang"),
        python=Path(sys.executable).resolve(),
        working_directory=root,
        config=config.resolve(),
        mcp_config=mcp.resolve(),
        secret_file=secret.resolve(),
        skill_dir=(tmp_path / "skills").resolve(),
        database=(tmp_path / "state" / "conversation.sqlite3").resolve(),
        ledger=(tmp_path / "state" / "ledger.sqlite3").resolve(),
        socket=(tmp_path / "run" / "agent.sock").resolve(),
        lock=(tmp_path / "run" / "agent.lock").resolve(),
        benchmark_dir=(tmp_path / "benchmarks").resolve(),
        whisper_command=(tmp_path / "whisper-cli").resolve(),
        whisper_model=(tmp_path / "whisper.bin").resolve(),
        web_certificate=(tmp_path / "tls" / "cert.pem").resolve(),
        web_key=(tmp_path / "tls" / "key.pem").resolve(),
    )


def test_rendered_unit_is_real_hardware_absolute_hardened_and_not_uv(tmp_path: Path) -> None:
    spec = _spec(tmp_path)

    unit = render_unit(spec)

    assert f"User={spec.user}" in unit
    assert f"WorkingDirectory={spec.working_directory}" in unit
    assert f"ExecStart={spec.python} -m ninjarobot_pi5_agent.service_main" in unit
    assert " --real" in unit
    assert "uv run" not in unit
    assert "Restart=on-failure" in unit
    assert "Restart=always" not in unit
    assert "SupplementaryGroups=audio video gpio i2c spi" in unit
    assert "ProtectSystem=strict" in unit
    assert "NoNewPrivileges" not in unit
    assert str(spec.secret_file) not in repr({"spec": "configured-private-file"})
    analyzer = shutil.which("systemd-analyze")
    if analyzer is not None:
        unit_path = tmp_path / UNIT_NAME
        unit_path.write_text(unit, encoding="utf-8")
        verified = subprocess.run(
            [analyzer, "verify", str(unit_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        assert verified.returncode == 0, verified.stderr


def test_current_spec_preserves_virtual_environment_interpreter_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_python = tmp_path / "uv-python"
    base_python.write_text("", encoding="utf-8")
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.symlink_to(base_python)
    monkeypatch.setattr(sys, "executable", str(venv_python))
    monkeypatch.setattr("getpass.getuser", lambda: "robot-user")
    paths = {
        name: tmp_path / name
        for name in (
            "config",
            "mcp_config",
            "secret_file",
            "skill_dir",
            "conversation_db",
            "ledger",
            "service_socket",
            "service_lock",
            "benchmark_dir",
            "whisper_command",
            "whisper_model",
            "web_certificate",
            "web_key",
        )
    }

    spec = current_spec(SimpleNamespace(**paths))

    assert spec.python == venv_python.absolute()
    assert spec.python != base_python.resolve()


def test_installer_is_disabled_by_default_idempotent_and_uses_fixed_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec(tmp_path)
    calls: list[list[str]] = []

    def runner(command: object) -> subprocess.CompletedProcess[str]:
        rendered = list(command)  # type: ignore[arg-type]
        calls.append(rendered)
        if rendered[1:3] == ["is-enabled", UNIT_NAME]:
            return subprocess.CompletedProcess(rendered, 1, "disabled\n", "")
        return subprocess.CompletedProcess(rendered, 0, "", "")

    monkeypatch.setattr(Path, "exists", lambda path: False if path == UNIT_PATH else path.is_file())
    result = DeploymentManager(spec, runner=runner).install(confirmed=True)

    assert result["enabled"] is False
    destinations = {command[-1] for command in calls if "install" in command[1]}
    assert destinations == {str(UNIT_PATH), str(HELPER_PATH), str(SUDOERS_PATH)}
    assert any(command[:2] == ["/usr/bin/systemd-analyze", "verify"] for command in calls)
    assert any(command[:2] == ["/usr/sbin/visudo", "-cf"] for command in calls)
    assert ["/usr/bin/sudo", "/usr/bin/systemctl", "disable", UNIT_NAME] in calls
    with pytest.raises(ValueError, match="requires --confirm"):
        DeploymentManager(spec, runner=runner).install(confirmed=False)


def test_enable_and_disable_persist_boot_onboarding_without_deleting_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(tmp_path)
    calls: list[list[str]] = []

    def runner(command: object) -> subprocess.CompletedProcess[str]:
        rendered = list(command)  # type: ignore[arg-type]
        calls.append(rendered)
        return subprocess.CompletedProcess(rendered, 0, "enabled\n", "")

    manager = DeploymentManager(spec, runner=runner)
    monkeypatch.setattr(
        manager,
        "artifact_status",
        lambda: {
            "systemd_unit": True,
            "poweroff_helper": True,
            "sudoers_rule": True,
        },
    )
    enabled = manager.enable(confirmed=True)
    config = load_robot_config(spec.config)
    assert enabled["next_boot"] == "real_hardware_agent_starts"
    assert config.deployment.auto_start_enabled is True
    assert config.deployment.web_poweroff_enabled is True
    assert config.onboarding.enabled is True

    manager.disable()
    assert load_robot_config(spec.config).deployment.auto_start_enabled is False
    assert spec.secret_file.is_file()
    assert ["/usr/bin/sudo", "/usr/bin/systemctl", "disable", "--now", UNIT_NAME] in calls


def test_enable_rejects_partial_privileged_install_before_changing_config(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    before = spec.config.read_bytes()
    manager = DeploymentManager(
        spec,
        runner=lambda command: subprocess.CompletedProcess(list(command), 0, "", ""),
    )
    manager.artifact_status = lambda: {  # type: ignore[method-assign]
        "systemd_unit": True,
        "poweroff_helper": False,
        "sudoers_rule": False,
    }

    with pytest.raises(RuntimeError, match="deployment is incomplete"):
        manager.enable(confirmed=True)

    assert spec.config.read_bytes() == before


def test_artifact_status_does_not_read_protected_sudoers_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(tmp_path)
    calls: list[list[str]] = []
    original_is_file = Path.is_file

    def protected_is_file(path: Path) -> bool:
        if path == SUDOERS_PATH:
            raise PermissionError("protected sudoers directory")
        if path in {UNIT_PATH, HELPER_PATH}:
            return True
        return original_is_file(path)

    def runner(command: object) -> subprocess.CompletedProcess[str]:
        rendered = list(command)  # type: ignore[arg-type]
        calls.append(rendered)
        return subprocess.CompletedProcess(rendered, 0, "allowed\n", "")

    monkeypatch.setattr(Path, "is_file", protected_is_file)
    artifacts = DeploymentManager(spec, runner=runner).artifact_status()

    assert artifacts == {
        "systemd_unit": True,
        "poweroff_helper": True,
        "sudoers_rule": True,
    }
    assert ["/usr/bin/sudo", "-n", "-l", str(HELPER_PATH)] in calls


def test_install_and_enable_starts_service_in_one_transaction(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    calls: list[list[str]] = []

    def runner(command: object) -> subprocess.CompletedProcess[str]:
        rendered = list(command)  # type: ignore[arg-type]
        calls.append(rendered)
        return subprocess.CompletedProcess(rendered, 0, "", "")

    manager = DeploymentManager(spec, runner=runner)
    manager.artifact_status = Mock(
        return_value={  # type: ignore[method-assign]
            "systemd_unit": False,
            "poweroff_helper": False,
            "sudoers_rule": False,
        }
    )
    manager.install = Mock(return_value={"installed": True})  # type: ignore[method-assign]
    manager.enable = Mock(return_value={"enabled": True})  # type: ignore[method-assign]

    result = manager.install_and_enable(confirmed=True)

    assert result["running_now"] is True
    assert ["/usr/bin/sudo", "/usr/bin/systemctl", "start", UNIT_NAME] in calls


def test_backup_is_private_and_contains_only_user_data(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    spec.database.parent.mkdir(parents=True)
    spec.database.write_bytes(b"sqlite-data")
    spec.skill_dir.mkdir()
    (spec.skill_dir / "skill.txt").write_text("safe", encoding="utf-8")

    backup = create_backup(spec, tmp_path / "backup" / "robot.tar.gz")

    assert backup.stat().st_mode & 0o777 == 0o600
    with tarfile.open(backup, "r:gz") as archive:
        names = set(archive.getnames())
    assert "manifest.json" in names
    assert f"data/{spec.config.relative_to('/')}" in names
    assert f"data/{spec.database.relative_to('/')}" in names
    assert all("ninjarobot-agent.service" not in name for name in names)

    spec.config.write_text("broken", encoding="utf-8")
    restored = restore_backup(spec, backup, confirmed=True)
    assert restored["restored_files"] >= 4
    assert load_robot_config(spec.config).schema_version == 1
    with pytest.raises(ValueError, match="requires --confirm"):
        restore_backup(spec, backup, confirmed=False)


def test_poweroff_helper_and_sudoers_are_exact_and_argument_free() -> None:
    assets = Path(__file__).resolve().parents[1] / "src" / "ninjarobot_pi5_agent" / "deployment"
    helper = (assets / "ninjarobot-poweroff").read_text(encoding="utf-8")
    sudoers = (assets / "ninjarobot-poweroff.sudoers.in").read_text(encoding="utf-8")
    assert helper == "#!/bin/sh\nset -eu\nexec /usr/bin/systemctl poweroff --no-wall\n"
    assert sudoers == "@USER@ ALL=(root) NOPASSWD: /usr/libexec/ninjarobot-poweroff\n"
