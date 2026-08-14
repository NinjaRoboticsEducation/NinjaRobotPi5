"""Explicit, data-preserving systemd deployment for one real-hardware service."""

from __future__ import annotations

import getpass
import json
import pwd
import shlex
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ninjarobot_pi5_ide import load_robot_config, save_robot_config

UNIT_NAME = "ninjarobot-agent.service"
UNIT_PATH = Path("/etc/systemd/system/ninjarobot-agent.service")
HELPER_PATH = Path("/usr/libexec/ninjarobot-poweroff")
SUDOERS_PATH = Path("/etc/sudoers.d/ninjarobot-poweroff")
SYSTEMCTL = Path("/usr/bin/systemctl")
JOURNALCTL = Path("/usr/bin/journalctl")
SUDO = Path("/usr/bin/sudo")
INSTALL = Path("/usr/bin/install")
SYSTEMD_ANALYZE = Path("/usr/bin/systemd-analyze")
VISUDO = Path("/usr/sbin/visudo")

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class DeploymentSpec:
    user: str
    python: Path
    working_directory: Path
    config: Path
    mcp_config: Path
    secret_file: Path
    skill_dir: Path
    database: Path
    ledger: Path
    socket: Path
    lock: Path
    benchmark_dir: Path
    whisper_command: Path
    whisper_model: Path
    web_certificate: Path
    web_key: Path

    def validate(self) -> None:
        account = pwd.getpwnam(self.user)
        if account.pw_uid == 0:
            raise ValueError("the NinjaRobot service must not run as root")
        for path in (
            self.python,
            self.working_directory,
            self.config,
            self.mcp_config,
            self.secret_file,
            self.skill_dir,
            self.database,
            self.ledger,
            self.socket,
            self.lock,
            self.benchmark_dir,
            self.whisper_command,
            self.whisper_model,
            self.web_certificate,
            self.web_key,
        ):
            if not path.is_absolute():
                raise ValueError("deployment paths must be absolute")
        if not self.python.is_file():
            raise ValueError("installed Python executable is unavailable")
        if not self.config.is_file():
            raise ValueError("robot configuration is unavailable")
        if not self.mcp_config.is_file():
            raise ValueError("MCP configuration is unavailable")
        if not self.secret_file.is_file():
            raise ValueError("agent secret file is unavailable")
        load_robot_config(self.config)


def render_unit(spec: DeploymentSpec) -> str:
    """Render fixed arguments; systemd never invokes a shell or `uv run`."""
    spec.validate()
    command = [
        str(spec.python),
        "-m",
        "ninjarobot_pi5_agent.service_main",
        "--socket",
        str(spec.socket),
        "--lock",
        str(spec.lock),
        "--database",
        str(spec.database),
        "--ledger",
        str(spec.ledger),
        "--config",
        str(spec.config),
        "--mcp-config",
        str(spec.mcp_config),
        "--secret-file",
        str(spec.secret_file),
        "--skill-dir",
        str(spec.skill_dir),
        "--benchmark-dir",
        str(spec.benchmark_dir),
        "--whisper-command",
        str(spec.whisper_command),
        "--whisper-model",
        str(spec.whisper_model),
        "--web-certificate",
        str(spec.web_certificate),
        "--web-key",
        str(spec.web_key),
        "--real",
    ]
    writable = sorted(
        {
            str(path.parent)
            for path in (
                spec.config,
                spec.mcp_config,
                spec.secret_file,
                spec.database,
                spec.ledger,
                spec.socket,
                spec.lock,
                spec.web_certificate,
                spec.web_key,
            )
        }
        | {str(spec.skill_dir), str(spec.benchmark_dir)}
    )
    return (
        _asset("ninjarobot-agent.service.in")
        .replace("@USER@", spec.user)
        .replace("@WORKING_DIRECTORY@", _systemd_escape(str(spec.working_directory)))
        .replace("@EXEC_START@", " ".join(_systemd_escape(value) for value in command))
        .replace("@READ_WRITE_PATHS@", " ".join(_systemd_escape(value) for value in writable))
    )


class DeploymentManager:
    """Install or operate only the fixed NinjaRobot systemd artifacts."""

    def __init__(self, spec: DeploymentSpec, *, runner: CommandRunner | None = None) -> None:
        self.spec = spec
        self._runner = runner or _run

    def install(self, *, confirmed: bool, upgrade: bool = False) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("deployment installation requires --confirm")
        self._prepare_optional_user_files()
        self.spec.validate()
        if UNIT_PATH.exists() and not upgrade:
            raise ValueError("deployment already exists; use deployment upgrade --confirm")
        unit = render_unit(self.spec)
        helper = _asset("ninjarobot-poweroff")
        sudoers = _asset("ninjarobot-poweroff.sudoers.in").replace("@USER@", self.spec.user)
        with tempfile.TemporaryDirectory(prefix="ninjarobot-deploy-") as temporary:
            root = Path(temporary)
            unit_source = root / UNIT_PATH.name
            helper_source = root / HELPER_PATH.name
            sudoers_source = root / SUDOERS_PATH.name
            unit_source.write_text(unit, encoding="utf-8")
            helper_source.write_text(helper, encoding="utf-8")
            sudoers_source.write_text(sudoers, encoding="utf-8")
            self._checked([str(SYSTEMD_ANALYZE), "verify", str(unit_source)])
            self._checked([str(VISUDO), "-cf", str(sudoers_source)])
            commands = (
                [
                    str(SUDO),
                    str(INSTALL),
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0644",
                    str(unit_source),
                    str(UNIT_PATH),
                ],
                [
                    str(SUDO),
                    str(INSTALL),
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0755",
                    str(helper_source),
                    str(HELPER_PATH),
                ],
                [
                    str(SUDO),
                    str(INSTALL),
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0440",
                    str(sudoers_source),
                    str(SUDOERS_PATH),
                ],
                [str(SUDO), str(SYSTEMCTL), "daemon-reload"],
            )
            for command in commands:
                self._checked(command)
            if not upgrade:
                self._checked([str(SUDO), str(SYSTEMCTL), "disable", UNIT_NAME])
        return {"installed": True, "enabled": self.is_enabled(), "spec": _public_spec(self.spec)}

    def enable(self, *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("auto-start enablement requires --confirm")
        artifacts = self.artifact_status()
        if not all(artifacts.values()):
            missing = ", ".join(name for name, ready in artifacts.items() if not ready)
            raise RuntimeError(
                f"deployment is incomplete ({missing}); install or repair it before enabling"
            )
        self._checked([str(SUDO), str(SYSTEMCTL), "enable", UNIT_NAME])
        try:
            self._persist_auto_start(True)
        except Exception:
            # Do not leave a boot-enabled unit whose configuration still says
            # deployment/onboarding is disabled.
            self._checked([str(SUDO), str(SYSTEMCTL), "disable", UNIT_NAME])
            raise
        return {
            "enabled": True,
            "onboarding_enabled": True,
            "web_poweroff_enabled": True,
            "next_boot": "real_hardware_agent_starts",
        }

    def disable(self) -> dict[str, Any]:
        self._checked([str(SUDO), str(SYSTEMCTL), "disable", "--now", UNIT_NAME])
        self._persist_auto_start(False)
        return {"enabled": False, "stopped": True}

    def action(self, action: str) -> dict[str, Any]:
        if action not in {"start", "stop", "restart"}:
            raise ValueError("deployment action is not allowed")
        self._checked([str(SUDO), str(SYSTEMCTL), action, UNIT_NAME])
        return {"action": action, "accepted": True}

    def status(self) -> dict[str, Any]:
        result = self._runner(
            [
                str(SYSTEMCTL),
                "show",
                UNIT_NAME,
                "--property=ActiveState,SubState,UnitFileState",
                "--no-pager",
            ]
        )
        return {
            "installed": all(self.artifact_status().values()),
            "artifacts": self.artifact_status(),
            "enabled": self.is_enabled(),
            "systemd": result.stdout.strip() if result.returncode == 0 else "unavailable",
            "spec": _public_spec(self.spec),
        }

    def validate(self) -> dict[str, Any]:
        self.spec.validate()
        artifacts = self.artifact_status()
        return {
            "valid": all(artifacts.values()),
            "artifacts": artifacts,
            "spec": _public_spec(self.spec),
        }

    def install_and_enable(self, *, confirmed: bool, repair: bool = False) -> dict[str, Any]:
        """Install all privileged artifacts, then transactionally enable boot."""
        if not confirmed:
            raise ValueError("deployment setup requires --confirm")
        existing = self.artifact_status()
        upgrade = repair or any(existing.values())
        installed = self.install(confirmed=True, upgrade=upgrade)
        enabled = self.enable(confirmed=True)
        return {"installed": installed["installed"], **enabled}

    @staticmethod
    def artifact_status() -> dict[str, bool]:
        """Report every privileged artifact required by boot and web power-off."""
        return {
            "systemd_unit": UNIT_PATH.is_file(),
            "poweroff_helper": HELPER_PATH.is_file(),
            "sudoers_rule": SUDOERS_PATH.is_file(),
        }

    def logs(self, *, lines: int = 100) -> subprocess.CompletedProcess[str]:
        if not 1 <= lines <= 1000:
            raise ValueError("journal line count must be from 1 through 1000")
        return self._runner([str(JOURNALCTL), "-u", UNIT_NAME, "-n", str(lines), "--no-pager"])

    def uninstall(self, *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("deployment removal requires --confirm")
        self.disable()
        for target in (UNIT_PATH, HELPER_PATH, SUDOERS_PATH):
            self._checked([str(SUDO), "/usr/bin/rm", "-f", str(target)])
        self._checked([str(SUDO), str(SYSTEMCTL), "daemon-reload"])
        return {"uninstalled": True, "user_data_preserved": True}

    def is_enabled(self) -> bool:
        result = self._runner([str(SYSTEMCTL), "is-enabled", UNIT_NAME])
        return result.returncode == 0 and result.stdout.strip() == "enabled"

    def _checked(self, command: Sequence[str]) -> None:
        result = self._runner(command)
        if result.returncode != 0:
            raise RuntimeError(f"deployment command failed: {Path(command[0]).name}")

    def _persist_auto_start(self, enabled: bool) -> None:
        config = load_robot_config(self.spec.config)
        payload = config.model_dump(mode="python")
        payload["deployment"]["auto_start_enabled"] = enabled
        if enabled:
            payload["deployment"]["web_poweroff_enabled"] = True
            payload["onboarding"]["enabled"] = True
        save_robot_config(type(config).model_validate(payload), self.spec.config, overwrite=True)

    def _prepare_optional_user_files(self) -> None:
        """Materialize optional empty files required by the hardened unit sandbox."""
        for directory in (self.spec.skill_dir, self.spec.benchmark_dir):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory.chmod(0o700)
        for path, initial in (
            (self.spec.mcp_config, "schema_version = 1\nservers = []\n"),
            (self.spec.secret_file, ""),
        ):
            if path.is_symlink():
                raise ValueError(f"deployment user file must not be a symbolic link: {path}")
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.parent.chmod(0o700)
            if not path.exists():
                path.write_text(initial, encoding="utf-8")
            path.chmod(0o600)


def create_backup(spec: DeploymentSpec, output: Path) -> Path:
    """Archive user-owned configuration/state without deleting or following links."""
    destination = output.expanduser().resolve()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    sources = {
        path.resolve()
        for path in (spec.config, spec.mcp_config, spec.secret_file, spec.database, spec.ledger)
        if path.is_file() and not path.is_symlink()
    } | {
        path.resolve()
        for path in (spec.skill_dir, spec.benchmark_dir)
        if path.is_dir() and not path.is_symlink()
    }
    metadata = {
        "created_at": datetime.now(UTC).isoformat(),
        "user": spec.user,
        "sources": [str(path) for path in sorted(sources)],
    }
    with tarfile.open(destination, "w:gz") as archive:
        for source in sorted(sources):
            archive.add(source, arcname=f"data/{source.relative_to('/')}", recursive=True)
        payload = json.dumps(metadata, indent=2).encode("utf-8")
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(payload)
            handle.flush()
            archive.add(handle.name, arcname="manifest.json")
    destination.chmod(0o600)
    return destination


def restore_backup(spec: DeploymentSpec, backup: Path, *, confirmed: bool) -> dict[str, Any]:
    """Overlay one verified NinjaRobot backup without deleting newer user data."""
    if not confirmed:
        raise ValueError("backup rollback requires --confirm")
    source = backup.expanduser().resolve()
    if not source.is_file() or source.is_symlink():
        raise ValueError("backup archive is unavailable")
    allowed = tuple(
        path.resolve()
        for path in (
            spec.config,
            spec.mcp_config,
            spec.secret_file,
            spec.database,
            spec.ledger,
            spec.skill_dir,
            spec.benchmark_dir,
        )
    )
    restored = 0
    with tarfile.open(source, "r:gz") as archive:
        if archive.getmember("manifest.json").isfile() is False:
            raise ValueError("backup manifest is invalid")
        for member in archive.getmembers():
            if member.name == "manifest.json":
                continue
            if not member.name.startswith("data/") or member.issym() or member.islnk():
                raise ValueError("backup contains an unsafe member")
            target = Path("/") / member.name.removeprefix("data/")
            resolved = target.resolve()
            if not any(resolved == base or resolved.is_relative_to(base) for base in allowed):
                raise ValueError("backup member is outside approved user-data paths")
            if member.isdir():
                resolved.mkdir(mode=0o700, parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError("backup contains an unsupported member type")
            content = archive.extractfile(member)
            if content is None:
                raise ValueError("backup member could not be read")
            resolved.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=resolved.parent, delete=False) as temporary:
                temporary.write(content.read())
                temporary_path = Path(temporary.name)
            temporary_path.chmod(member.mode & 0o700 or 0o600)
            temporary_path.replace(resolved)
            restored += 1
    load_robot_config(spec.config)
    return {"restored_files": restored, "newer_unarchived_data_preserved": True}


def current_spec(arguments: Any) -> DeploymentSpec:
    """Resolve the active CLI paths and installed interpreter to absolutes."""
    user = getpass.getuser()
    if user == "root":
        raise ValueError("run deployment commands as the non-root robot user")
    return DeploymentSpec(
        user=user,
        python=Path(sys.executable).resolve(),
        working_directory=Path.cwd().resolve(),
        config=arguments.config.expanduser().resolve(),
        mcp_config=arguments.mcp_config.expanduser().resolve(),
        secret_file=arguments.secret_file.expanduser().resolve(),
        skill_dir=arguments.skill_dir.expanduser().resolve(),
        database=arguments.conversation_db.expanduser().resolve(),
        ledger=arguments.ledger.expanduser().resolve(),
        socket=arguments.service_socket.expanduser().resolve(),
        lock=arguments.service_lock.expanduser().resolve(),
        benchmark_dir=arguments.benchmark_dir.expanduser().resolve(),
        whisper_command=arguments.whisper_command.expanduser().resolve(),
        whisper_model=arguments.whisper_model.expanduser().resolve(),
        web_certificate=arguments.web_certificate.expanduser().resolve(),
        web_key=arguments.web_key.expanduser().resolve(),
    )


def _asset(name: str) -> str:
    return (Path(__file__).with_name("deployment") / name).read_text(encoding="utf-8")


def _systemd_escape(value: str) -> str:
    if any(character in value for character in "\n\r\x00"):
        raise ValueError("systemd value contains forbidden control characters")
    return shlex.quote(value)


def _public_spec(spec: DeploymentSpec) -> dict[str, str]:
    hidden = {"secret_file"}
    return {
        key: "configured-private-file" if key in hidden else str(value)
        for key, value in asdict(spec).items()
    }


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True, timeout=30.0)
