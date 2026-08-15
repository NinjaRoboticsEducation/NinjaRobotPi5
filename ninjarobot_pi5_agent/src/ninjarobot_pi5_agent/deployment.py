"""Explicit, data-preserving systemd deployment for one real-hardware service."""

from __future__ import annotations

import getpass
import json
import pwd
import shlex
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ninjarobot_pi5_ide import load_robot_config, save_robot_config

from .mcp_config import MCPConfiguration, load_mcp_configuration, save_mcp_configuration

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
RASPI_CONFIG = Path("/usr/bin/raspi-config")
RPI_EEPROM_CONFIG = Path("/usr/bin/rpi-eeprom-config")
EEPROM_UPDATE_PATHS = (
    Path("/boot/firmware/pieeprom.upd"),
    Path("/boot/pieeprom.upd"),
)
MAX_DEPLOYMENT_DIAGNOSTIC_CHARACTERS = 500

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
ReadinessProbe = Callable[[Path], bool]


@dataclass(frozen=True, slots=True)
class FullPoweroffStatus:
    """Raspberry Pi bootloader state required for a true PMIC power-off."""

    available: bool
    configured: bool
    update_pending: bool
    pending_configured: bool
    power_off_on_halt: str | None
    wake_on_gpio: str | None
    pending_power_off_on_halt: str | None = None
    pending_wake_on_gpio: str | None = None
    detail: str | None = None

    @property
    def ready(self) -> bool:
        return self.configured and not self.update_pending

    @property
    def scheduled(self) -> bool:
        """Return whether full power-off is active or queued for the next boot."""
        return self.ready or (self.update_pending and self.pending_configured)

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "configured": self.configured,
            "update_pending": self.update_pending,
            "pending_configured": self.pending_configured,
            "scheduled": self.scheduled,
            "ready": self.ready,
            "power_off_on_halt": self.power_off_on_halt,
            "wake_on_gpio": self.wake_on_gpio,
            "pending_power_off_on_halt": self.pending_power_off_on_halt,
            "pending_wake_on_gpio": self.pending_wake_on_gpio,
            "detail": self.detail,
        }


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
        load_mcp_configuration(self.mcp_config)


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

    def __init__(
        self,
        spec: DeploymentSpec,
        *,
        runner: CommandRunner | None = None,
        readiness_probe: ReadinessProbe | None = None,
        readiness_timeout_seconds: float = 30.0,
    ) -> None:
        if readiness_timeout_seconds < 0:
            raise ValueError("deployment readiness timeout must not be negative")
        self.spec = spec
        self._runner = runner or _run
        self._readiness_probe = readiness_probe or _agent_ipc_ready
        self._readiness_timeout_seconds = readiness_timeout_seconds

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
            # HELPER_PATH and SUDOERS_PATH deliberately share the basename
            # ``ninjarobot-poweroff``. Staging by destination basename would
            # therefore overwrite the helper with the sudoers rule.
            # systemd-analyze derives the unit type from the filename. Keep
            # the canonical .service suffix while giving the two same-basename
            # power-off artifacts distinct staging names.
            unit_source = root / UNIT_NAME
            helper_source = root / "poweroff-helper.install"
            sudoers_source = root / "poweroff-sudoers.install"
            if len({unit_source, helper_source, sudoers_source}) != 3:
                raise RuntimeError("deployment staging paths are not unique")
            unit_source.write_text(unit, encoding="utf-8")
            helper_source.write_text(helper, encoding="utf-8")
            sudoers_source.write_text(sudoers, encoding="utf-8")
            if helper_source.read_text(encoding="utf-8") != helper:
                raise RuntimeError("power-off helper staging verification failed")
            if sudoers_source.read_text(encoding="utf-8") != sudoers:
                raise RuntimeError("power-off sudoers staging verification failed")
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
        poweroff = self._ensure_full_poweroff_configuration()
        return {
            "installed": True,
            "enabled": self.is_enabled(),
            "full_poweroff": poweroff["status"],
            "poweroff_reboot_required": poweroff["changed"] or poweroff["pending"],
            "spec": _public_spec(self.spec),
        }

    def enable(self, *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("auto-start enablement requires --confirm")
        artifacts = self.artifact_status()
        if not all(artifacts.values()):
            missing = ", ".join(name for name, ready in artifacts.items() if not ready)
            raise RuntimeError(
                f"deployment is incomplete ({missing}); install or repair it before enabling"
            )
        poweroff = self._full_poweroff_status()
        if not poweroff.scheduled:
            raise RuntimeError(
                "full Raspberry Pi power-off is not configured; run deployment setup/repair"
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
        systemd = self._systemd_status()
        artifacts = self.artifact_status()
        active = systemd.get("ActiveState") == "active"
        ipc_ready = active and self._readiness_probe(self.spec.socket)
        poweroff = self._full_poweroff_status()
        return {
            "installed": all(artifacts.values()),
            "artifacts": artifacts,
            "enabled": self.is_enabled(),
            "running": active,
            "ready": ipc_ready,
            "full_poweroff": poweroff.as_dict(),
            "next_step": _full_poweroff_next_step(poweroff),
            "systemd": systemd,
            "spec": _public_spec(self.spec),
        }

    def validate(self) -> dict[str, Any]:
        self.spec.validate()
        artifacts = self.artifact_status()
        poweroff = self._full_poweroff_status()
        return {
            "valid": all(artifacts.values()) and poweroff.ready,
            "artifacts": artifacts,
            "full_poweroff": poweroff.as_dict(),
            "next_step": _full_poweroff_next_step(poweroff),
            "spec": _public_spec(self.spec),
        }

    def install_and_enable(self, *, confirmed: bool, repair: bool = False) -> dict[str, Any]:
        """Install, enable, and start the real-hardware service transactionally."""
        if not confirmed:
            raise ValueError("deployment setup requires --confirm")
        existing = self.artifact_status()
        upgrade = repair or any(existing.values())
        installed = self.install(confirmed=True, upgrade=upgrade)
        enabled = self.enable(confirmed=True)
        try:
            self._checked([str(SUDO), str(SYSTEMCTL), "reset-failed", UNIT_NAME])
            started = self.action("start")
            readiness = self._wait_for_readiness()
        except Exception:
            # A failed first start must not leave a broken unit enabled for the
            # next boot. User data and installed artifacts remain available for
            # diagnosis and repair.
            try:
                self.disable()
            except Exception:
                pass
            raise
        return {
            "installed": installed["installed"],
            **enabled,
            "started": started["accepted"],
            "running_now": readiness["running"],
            "ready": readiness["ready"],
            "full_poweroff": installed.get("full_poweroff"),
            "poweroff_reboot_required": installed.get("poweroff_reboot_required", False),
            "systemd": readiness["systemd"],
        }

    def _wait_for_readiness(self) -> dict[str, Any]:
        """Wait until systemd is active and the owner IPC endpoint responds."""
        deadline = time.monotonic() + self._readiness_timeout_seconds
        last_state: dict[str, str] = {}
        while True:
            last_state = self._systemd_status()
            active_state = last_state.get("ActiveState")
            if active_state == "failed":
                raise RuntimeError(_deployment_failure_message(last_state))
            if active_state == "active" and self._readiness_probe(self.spec.socket):
                return {"running": True, "ready": True, "systemd": last_state}
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "automatic startup did not become Agent-ready within "
                    f"{self._readiness_timeout_seconds:g} seconds; "
                    f"systemd state: {last_state or 'unavailable'}"
                )
            time.sleep(0.25)

    def _systemd_status(self) -> dict[str, str]:
        result = self._runner(
            [
                str(SYSTEMCTL),
                "show",
                UNIT_NAME,
                "--property=ActiveState,SubState,UnitFileState,Result,NRestarts,ExecMainStatus",
                "--no-pager",
            ]
        )
        if result.returncode != 0:
            return {"status": "unavailable"}
        return _parse_systemd_properties(result.stdout)

    def artifact_status(self) -> dict[str, bool]:
        """Report privileged artifacts without directly traversing protected sudoers."""
        return {
            "systemd_unit": _safe_is_file(UNIT_PATH),
            "poweroff_helper": validate_poweroff_helper(),
            "sudoers_rule": self._poweroff_authorized(),
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
            diagnostic = _bounded_command_diagnostic(result)
            suffix = f": {diagnostic}" if diagnostic else ""
            raise RuntimeError(
                f"deployment command failed: {Path(command[0]).name} "
                f"(exit {result.returncode}){suffix}"
            )

    def _poweroff_authorized(self) -> bool:
        """Check the exact passwordless helper authorization without reading /etc/sudoers.d."""
        result = self._runner([str(SUDO), "-n", "-l", str(HELPER_PATH)])
        return result.returncode == 0

    def _full_poweroff_status(self) -> FullPoweroffStatus:
        return read_full_poweroff_status(runner=self._runner)

    def _ensure_full_poweroff_configuration(self) -> dict[str, object]:
        status = self._full_poweroff_status()
        if not status.available:
            raise RuntimeError(
                "Raspberry Pi EEPROM configuration is unavailable; install/update "
                "raspi-config and rpi-eeprom before repairing deployment"
            )
        if status.ready:
            return {
                "changed": False,
                "pending": status.update_pending,
                "status": status.as_dict(),
            }
        if status.update_pending:
            if status.pending_configured:
                return {
                    "changed": False,
                    "pending": True,
                    "status": status.as_dict(),
                }
            raise RuntimeError(
                "a different Raspberry Pi EEPROM update is pending; reboot or cancel it "
                "before repairing full power-off"
            )
        self._checked(
            [
                str(SUDO),
                str(RASPI_CONFIG),
                "nonint",
                "do_power_off_on_halt",
                "B1",
            ]
        )
        updated = self._full_poweroff_status()
        if not updated.scheduled:
            raise RuntimeError(
                "Raspberry Pi full power-off configuration was not scheduled successfully"
            )
        return {
            "changed": True,
            "pending": updated.update_pending,
            "status": updated.as_dict(),
        }

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
        for path in (self.spec.mcp_config, self.spec.secret_file):
            if path.is_symlink():
                raise ValueError(f"deployment user file must not be a symbolic link: {path}")
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.parent.chmod(0o700)
        if not self.spec.mcp_config.exists():
            save_mcp_configuration(MCPConfiguration(), self.spec.mcp_config)
        if not self.spec.secret_file.exists():
            self.spec.secret_file.write_text("", encoding="utf-8")
        self.spec.mcp_config.chmod(0o600)
        self.spec.secret_file.chmod(0o600)


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
        # Preserve the venv entry point. Resolving this symlink reaches uv's
        # base interpreter and loses the project's installed environment when
        # systemd executes it directly.
        python=Path(sys.executable).absolute(),
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


def read_full_poweroff_status(
    *,
    runner: CommandRunner | None = None,
    pending_paths: Sequence[Path] = EEPROM_UPDATE_PATHS,
) -> FullPoweroffStatus:
    """Read the effective/pending EEPROM shutdown configuration without changing it."""
    command_runner = runner or _run
    try:
        result = command_runner([str(RPI_EEPROM_CONFIG)])
    except (OSError, subprocess.SubprocessError):
        result = None
    pending_path = next((path for path in pending_paths if _safe_is_file(path)), None)
    pending = pending_path is not None
    pending_values: dict[str, str] = {}
    if pending_path is not None:
        try:
            pending_result = command_runner([str(RPI_EEPROM_CONFIG), str(pending_path)])
        except (OSError, subprocess.SubprocessError):
            pending_result = None
        if pending_result is not None and pending_result.returncode == 0:
            pending_values = _parse_bootloader_configuration(pending_result.stdout)
    pending_power_off = pending_values.get("POWER_OFF_ON_HALT")
    pending_wake = pending_values.get("WAKE_ON_GPIO")
    pending_configured = pending_power_off == "1" and pending_wake == "0"
    if result is None or result.returncode != 0:
        return FullPoweroffStatus(
            available=False,
            configured=False,
            update_pending=pending,
            pending_configured=pending_configured,
            power_off_on_halt=None,
            wake_on_gpio=None,
            pending_power_off_on_halt=pending_power_off,
            pending_wake_on_gpio=pending_wake,
            detail="Raspberry Pi EEPROM configuration could not be read",
        )
    values = _parse_bootloader_configuration(result.stdout)
    power_off = values.get("POWER_OFF_ON_HALT")
    wake = values.get("WAKE_ON_GPIO")
    configured = power_off == "1" and wake == "0"
    detail: str | None = None
    if pending and not pending_configured:
        detail = (
            "a pending EEPROM update does not enable full PMIC power-off; "
            "reboot or cancel it before deployment repair"
        )
    elif pending:
        detail = "EEPROM update is pending; reboot once before using web power-off"
    elif not configured:
        detail = "full PMIC power-off requires POWER_OFF_ON_HALT=1 and WAKE_ON_GPIO=0"
    return FullPoweroffStatus(
        available=True,
        configured=configured,
        update_pending=pending,
        pending_configured=pending_configured,
        power_off_on_halt=power_off,
        wake_on_gpio=wake,
        pending_power_off_on_halt=pending_power_off,
        pending_wake_on_gpio=pending_wake,
        detail=detail,
    )


def _parse_bootloader_configuration(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "[")):
            continue
        key, separator, value = line.partition("=")
        if separator and key:
            values[key.strip()] = value.strip()
    return values


def _full_poweroff_next_step(status: FullPoweroffStatus) -> str | None:
    if status.update_pending:
        if status.pending_configured:
            return "Reboot once to apply the Raspberry Pi full power-off EEPROM setting."
        return "Reboot or cancel the incompatible pending EEPROM update, then repair deployment."
    if not status.configured:
        return (
            "Run Install and deploy automatic startup Agent to configure full "
            "Raspberry Pi power-off."
        )
    return None


def _agent_ipc_ready(socket_path: Path) -> bool:
    """Probe the owner-only Agent IPC endpoint without mutating robot state."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(1.0)
            connection.connect(str(socket_path))
            connection.sendall(b'{"command":"startup_status"}\n')
            payload = b""
            while b"\n" not in payload and len(payload) <= 65_536:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                payload += chunk
    except OSError:
        return False
    try:
        message = json.loads(payload.partition(b"\n")[0])
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(message, dict) and message.get("type") == "result"


def _parse_systemd_properties(output: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator and key:
            properties[key] = value
    return properties


def _deployment_failure_message(state: dict[str, str]) -> str:
    result = state.get("Result", "unknown")
    exit_status = state.get("ExecMainStatus", "unknown")
    restarts = state.get("NRestarts", "unknown")
    return (
        "automatic startup Agent exited before becoming ready "
        f"(result={result}, exit_status={exit_status}, restarts={restarts}); "
        "inspect `journalctl -u ninjarobot-agent.service` and the Agent service log"
    )


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True, timeout=30.0)


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _bounded_command_diagnostic(completed: subprocess.CompletedProcess[str]) -> str:
    """Return one bounded printable line from a deployment subprocess."""
    output = completed.stderr.strip() or completed.stdout.strip()
    printable = "".join(character if character.isprintable() else " " for character in output)
    normalized = " ".join(printable.split())
    return normalized[:MAX_DEPLOYMENT_DIAGNOSTIC_CHARACTERS]


def validate_poweroff_helper(
    path: Path = HELPER_PATH,
    *,
    expected_uid: int = 0,
    expected_gid: int = 0,
) -> bool:
    """Verify the fixed helper identity, bytes, ownership, and executable mode."""
    try:
        if path.is_symlink() or not path.is_file():
            return False
        metadata = path.stat()
        if metadata.st_uid != expected_uid or metadata.st_gid != expected_gid:
            return False
        if stat.S_IMODE(metadata.st_mode) != 0o755:
            return False
        return path.read_text(encoding="utf-8") == _asset("ninjarobot-poweroff")
    except (OSError, UnicodeError):
        return False
