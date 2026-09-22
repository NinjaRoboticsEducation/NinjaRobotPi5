from __future__ import annotations

import hashlib
import os
import pty
import select
import shutil
import stat
import subprocess
import sys
import time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("configure_rpi_boot", ROOT / "scripts/configure_rpi_boot.py")
assert SPEC is not None and SPEC.loader is not None
BOOT_CONFIG = module_from_spec(SPEC)
sys.modules[SPEC.name] = BOOT_CONFIG
SPEC.loader.exec_module(BOOT_CONFIG)
AUDIO_OFF = BOOT_CONFIG.AUDIO_OFF
BEGIN_MARKER = BOOT_CONFIG.BEGIN_MARKER
END_MARKER = BOOT_CONFIG.END_MARKER
PWM_OVERLAY = BOOT_CONFIG.PWM_OVERLAY
render_boot_config = BOOT_CONFIG.render_boot_config
validate_boot_config = BOOT_CONFIG.validate_boot_config


@pytest.fixture
def local_bootstrap(tmp_path):
    """Use real Git and an inert installer; never access GitHub or OS setup."""
    source = tmp_path / "source"
    source.mkdir()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()

    git("init", "-q", "-b", "main")
    (source / "scripts").mkdir()
    (source / "install.sh").write_text("#!/bin/bash\nprintf 'delegated:%s\\n' \"$*\"\n")
    (source / "install.sh").chmod(0o755)
    for name in ("uv.lock", "scripts/install-rpi.sh", "scripts/install-versions.env"):
        (source / name).write_text("# fixture\n")
    git("add", ".")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
    sha = git("rev-parse", "HEAD")
    for name in ("public_v07", "release/public_v08", "collision"):
        git("branch", name)
    git("tag", "v1")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "tag",
        "-am",
        "annotated",
        "v2",
    )
    git("tag", "collision")
    config = tmp_path / "gitconfig"
    config.write_text(
        f'[url "{source}"]\n insteadOf = https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git\n'
    )
    environment = {**os.environ, "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1"}
    return sha, environment


@pytest.mark.parametrize(
    "ref",
    [
        "main",
        "public_v07",
        "release/public_v08",
        "v1",
        "v2",
        "COMMIT",
        "refs/heads/collision",
        "refs/tags/collision",
        "missing",
        "collision",
    ],
)
def test_streamed_bootstrap_with_real_git(tmp_path, local_bootstrap, ref):
    sha, environment = local_bootstrap
    parent = tmp_path / "custom Ninja folder"
    parent.mkdir()
    destination = parent / "NinjaRobotPi5"
    result = subprocess.run(
        [
            "bash",
            "-s",
            "--",
            "--ref",
            sha if ref == "COMMIT" else ref,
            "--install-dir",
            str(destination),
            "--profile",
            "development",
        ],
        input=(ROOT / "install.sh").read_text(),
        env=environment,
        cwd=parent,
        text=True,
        capture_output=True,
        timeout=20,
    )
    if ref in {"missing", "collision"}:
        assert result.returncode != 0
        assert ("Cannot resolve" if ref == "missing" else "Ambiguous") in result.stderr
        assert not destination.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert "delegated:--profile development" in result.stdout
        assert (
            subprocess.check_output(
                ["git", "-C", str(destination), "rev-parse", "HEAD"], text=True
            ).strip()
            == sha
        )
        assert (
            subprocess.run(
                ["git", "-C", str(destination), "symbolic-ref", "-q", "HEAD"], capture_output=True
            ).returncode
            == 1
        )
    assert not list(parent.glob(".ninjarobot-bootstrap.*"))


@pytest.mark.parametrize("assume_yes", [False, True])
def test_confirmation_without_terminal_is_explicit(assume_yes):
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; ASSUME_YES="$2"; confirm_plan',
            "test",
            str(ROOT / "scripts/install-rpi.sh"),
            str(int(assume_yes)),
        ],
        input="INSTALL\n",
        text=True,
        capture_output=True,
        start_new_session=True,
        timeout=5,
    )
    assert result.returncode == (0 if assume_yes else 1)
    if not assume_yes:
        assert "No controlling terminal" in result.stderr


def test_confirmation_uses_terminal_when_stdin_is_a_pipe():
    pid, terminal = pty.fork()
    if pid == 0:
        os.execlp(
            "bash",
            "bash",
            "-c",
            'printf "wrong\\n" | bash -c \'source "$1"; confirm_plan\' test "$1"',
            "test",
            str(ROOT / "scripts/install-rpi.sh"),
        )
    try:
        output = b""
        deadline = time.monotonic() + 5
        while b"Type INSTALL" not in output and time.monotonic() < deadline:
            if select.select([terminal], [], [], 0.1)[0]:
                output += os.read(terminal, 4096)
        assert b"Type INSTALL" in output
        os.write(terminal, b"INSTALL\n")
        while time.monotonic() < deadline:
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited:
                pid = 0
                assert os.waitstatus_to_exitcode(status) == 0
                break
            time.sleep(0.01)
        else:
            pytest.fail("terminal confirmation did not finish")
    finally:
        os.close(terminal)
        if pid:
            import signal

            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)


def _install_fake_git(tmp_path: Path, *, resolved: str) -> Path:
    """Install a deterministic Git shim for bootstrap integration tests."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "git"
    executable.write_text(
        """#!/usr/bin/env python3
import os
import sys
from pathlib import Path

arguments = sys.argv[1:]
if arguments and arguments[0] == "clone":
    checkout = Path(arguments[-1])
    (checkout / "scripts").mkdir(parents=True)
    installer = checkout / "install.sh"
    installer.write_text(
        "#!/usr/bin/env python3\\nimport sys\\n"
        "print('delegated:' + ' '.join(sys.argv[1:]))\\n",
        encoding="utf-8",
    )
    installer.chmod(0o700)
    (checkout / "scripts" / "install-rpi.sh").write_text("#!/usr/bin/env bash\\n")
    (checkout / "scripts" / "install-versions.env").write_text("# test fixture\\n")
    (checkout / "uv.lock").write_text("# test fixture\\n")
elif len(arguments) >= 4 and arguments[0] == "-C" and arguments[2] == "checkout":
    pass
elif arguments[0] == "-C" and arguments[2] == "rev-parse":
    if arguments[-1].startswith("refs/"):
        raise SystemExit(1)
    print(os.environ["FAKE_GIT_RESOLVED"])
else:
    raise SystemExit(f"unexpected fake git arguments: {arguments!r}")
""",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return bin_dir


def test_shell_installer_syntax_and_dry_run_are_safe() -> None:
    for script in (ROOT / "install.sh", ROOT / "scripts/install-rpi.sh"):
        checked = subprocess.run(
            ["bash", "-n", str(script)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert checked.returncode == 0, checked.stderr

    dry_run = subprocess.run(
        [str(ROOT / "install.sh"), "--dry-run"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert "no commands were executed" in dry_run.stdout
    assert "Ollama model" in dry_run.stdout


def test_standalone_bootstrap_dry_run_does_not_create_destination(tmp_path: Path) -> None:
    script = tmp_path / "install.sh"
    shutil.copyfile(ROOT / "install.sh", script)
    script.chmod(0o700)
    destination = tmp_path / "NinjaRobotPi5"

    result = subprocess.run(
        [str(script), "--install-dir", str(destination), "--ref", "reviewed-ref", "--dry-run"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "reviewed-ref" in result.stdout
    assert str(destination) in result.stdout
    assert "No commands were executed" in result.stdout
    assert not destination.exists()


def test_streamed_bootstrap_does_not_trust_files_in_the_current_directory(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "NinjaRobotPi5"
    result = subprocess.run(
        ["bash", "-s", "--", "--install-dir", str(destination), "--dry-run"],
        cwd=ROOT,
        input=(ROOT / "install.sh").read_text(encoding="utf-8"),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "NinjaRobot bootstrap preview" in result.stdout
    assert "No commands were executed" in result.stdout
    assert not destination.exists()


def test_standalone_bootstrap_check_reports_missing_installation(tmp_path: Path) -> None:
    script = tmp_path / "install.sh"
    shutil.copyfile(ROOT / "install.sh", script)
    script.chmod(0o700)
    destination = tmp_path / "missing"

    result = subprocess.run(
        [str(script), "--install-dir", str(destination), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "is not installed" in result.stderr
    assert not destination.exists()


def test_standalone_bootstrap_refuses_existing_destination(tmp_path: Path) -> None:
    script = tmp_path / "install.sh"
    shutil.copyfile(ROOT / "install.sh", script)
    script.chmod(0o700)
    destination = tmp_path / "existing"
    destination.mkdir()

    result = subprocess.run(
        [str(script), "--install-dir", str(destination), "--ref", "reviewed-ref"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Refusing to overwrite" in result.stderr


def test_standalone_bootstrap_verifies_revision_and_delegates_arguments(tmp_path: Path) -> None:
    script = tmp_path / "bootstrap.sh"
    shutil.copyfile(ROOT / "install.sh", script)
    script.chmod(0o700)
    revision = "a" * 40
    bin_dir = _install_fake_git(tmp_path, resolved=revision)
    destination = tmp_path / "NinjaRobotPi5"
    environment = {
        **os.environ,
        "FAKE_GIT_RESOLVED": revision,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
    }

    result = subprocess.run(
        [
            str(script),
            "--install-dir",
            str(destination),
            "--ref",
            revision,
            "--profile",
            "development",
            "--yes",
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert f"Verified revision {revision}" in result.stdout
    assert "delegated:--profile development --yes" in result.stdout
    assert (destination / "uv.lock").is_file()
    assert not tuple(tmp_path.glob(".ninjarobot-bootstrap.*"))


def test_standalone_bootstrap_rejects_exact_revision_mismatch(tmp_path: Path) -> None:
    script = tmp_path / "bootstrap.sh"
    shutil.copyfile(ROOT / "install.sh", script)
    script.chmod(0o700)
    requested = "a" * 40
    bin_dir = _install_fake_git(tmp_path, resolved="b" * 40)
    destination = tmp_path / "NinjaRobotPi5"
    environment = {
        **os.environ,
        "FAKE_GIT_RESOLVED": "b" * 40,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
    }

    result = subprocess.run(
        [str(script), "--install-dir", str(destination), "--ref", requested],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "does not match --ref" in result.stderr
    assert not destination.exists()
    assert not tuple(tmp_path.glob(".ninjarobot-bootstrap.*"))


def test_pwm_renderer_is_idempotent_and_preserves_unrelated_configuration() -> None:
    original = "# Raspberry Pi\ndtparam=i2c_arm=on\ndtparam=spi=on\ndtparam=audio=on\n"
    rendered = render_boot_config(original)

    assert render_boot_config(rendered) == rendered
    assert "dtparam=i2c_arm=on" in rendered
    assert "dtparam=spi=on" in rendered
    assert rendered.count(BEGIN_MARKER) == 1
    assert rendered.count(END_MARKER) == 1
    assert rendered.count(AUDIO_OFF) == 1
    assert rendered.count(PWM_OVERLAY) == 1
    assert validate_boot_config(rendered)[0] is True


def test_pwm_renderer_preserves_an_existing_approved_overlay_without_duplication() -> None:
    rendered = render_boot_config(f"[all]\n{PWM_OVERLAY}\n")

    assert rendered.count(PWM_OVERLAY) == 1
    assert validate_boot_config(rendered)[0] is True


def test_pwm_renderer_rejects_conflicting_or_malformed_configuration() -> None:
    with pytest.raises(ValueError, match="different settings"):
        render_boot_config("dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2\n")
    with pytest.raises(ValueError, match="unterminated"):
        render_boot_config(f"{BEGIN_MARKER}\n{AUDIO_OFF}\n")


def test_disabled_overlay_does_not_satisfy_required_configuration() -> None:
    original = f"[none]\n{PWM_OVERLAY}\n[pi5]\n# still filtered\n"
    rendered = render_boot_config(original)
    assert rendered.startswith(original)
    assert rendered.count(PWM_OVERLAY) == 2
    assert validate_boot_config(rendered)[0]
    assert render_boot_config(rendered) == rendered


@pytest.mark.parametrize("section", ["pi4", "pi5", "0x12345678", "HDMI:0", "gpio4=1"])
def test_conditional_overlay_requires_explicit_review(section: str) -> None:
    source = f"[{section}]\n{PWM_OVERLAY}\n"
    with pytest.raises(ValueError, match="unconditional"):
        render_boot_config(source)


@pytest.mark.parametrize(
    "source",
    [
        f"{END_MARKER}\n{BEGIN_MARKER}\n[all]\n{AUDIO_OFF}\n{PWM_OVERLAY}\n",
        f"{BEGIN_MARKER}\n[none]\n{AUDIO_OFF}\n{PWM_OVERLAY}\n{END_MARKER}\n",
        f"{BEGIN_MARKER}\n[all]\n{AUDIO_OFF}\n[none]\n{PWM_OVERLAY}\n{END_MARKER}\n",
        f"include other.txt\n{BEGIN_MARKER}\n[all]\n{AUDIO_OFF}\n{PWM_OVERLAY}\n{END_MARKER}\n",
    ],
)
def test_validation_rejects_false_positive_boot_text(source: str) -> None:
    assert not validate_boot_config(source)[0]


@pytest.mark.parametrize("suffix", ["dtparam=audio=on", "[pi5]\ndtparam=audio=on", "include x"])
def test_later_settings_are_not_silently_moved_ahead_of_managed_block(suffix: str) -> None:
    source = render_boot_config("") + suffix + "\n"
    assert not validate_boot_config(source)[0]
    with pytest.raises(ValueError, match="final configuration section"):
        render_boot_config(source)


def test_duplicate_unmanaged_overlays_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicated"):
        render_boot_config(f"{PWM_OVERLAY}\n{PWM_OVERLAY}\n")


def test_installer_does_not_pull_models_or_start_robot_services() -> None:
    installer = (ROOT / "scripts/install-rpi.sh").read_text(encoding="utf-8")

    forbidden = (
        "ollama pull",
        "ninjarobot-agent service start",
        "systemctl enable --now ninjarobot-agent",
        "sudo reboot",
    )
    assert all(command not in installer for command in forbidden)


def test_installer_creates_idempotent_private_ninjarobot_launcher(tmp_path: Path) -> None:
    environment = {**os.environ, "HOME": str(tmp_path)}
    script = 'source "$1"\ninstall_cli_launcher\ninstall_cli_launcher\n'

    result = subprocess.run(
        ["bash", "-c", script, "test", str(ROOT / "scripts/install-rpi.sh")],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    launcher = tmp_path / ".local/bin/ninjarobot"
    assert result.returncode == 0, result.stderr
    assert launcher.is_symlink()
    assert launcher.resolve() == (ROOT / ".venv/bin/ninjarobot").resolve()
    assert stat.S_IMODE(launcher.parent.stat().st_mode) == 0o755


def test_readiness_check_covers_pinned_tools_camera_and_driver_provenance() -> None:
    installer = (ROOT / "scripts/install-rpi.sh").read_text(encoding="utf-8")

    expected = (
        "UV_NO_MODIFY_PATH=1",
        'uv --version)" == "uv ${UV_VERSION}',
        "ollama --version",
        "systemctl is-active --quiet ollama",
        "dpkg-query -W",
        "rev-parse HEAD",
        "import libcamera, picamera2",
        "verify_workspace_driver_sources.py",
        "verify_immutable_drivers.py",
    )
    assert all(fragment in installer for fragment in expected)


def test_development_profile_preview_does_not_change_environment() -> None:
    result = subprocess.run(
        [str(ROOT / "install.sh"), "--profile", "development", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert ".venv-dev" in result.stdout
    assert "no commands were executed" in result.stdout
    assert "OS setup untouched" in result.stdout


def test_installer_rejects_unknown_profile() -> None:
    result = subprocess.run(
        [str(ROOT / "install.sh"), "--profile", "typo", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0


def test_installer_checksum_guard_accepts_exact_bytes_only(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    artifact.write_bytes(b"reviewed")
    script = 'source "$1"\nverify_sha256 "$2" "$3"\n'
    for checksum, expected in ((hashlib.sha256(b"reviewed").hexdigest(), 0), ("0" * 64, 1)):
        result = subprocess.run(
            [
                "bash",
                "-c",
                script,
                "check",
                str(ROOT / "scripts/install-rpi.sh"),
                str(artifact),
                checksum,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == expected
    assert artifact.read_bytes() == b"reviewed"


def test_development_install_targets_separate_environment(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for filename in ("install-rpi.sh", "install-versions.env"):
        shutil.copyfile(ROOT / "scripts" / filename, scripts / filename)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    uv = fake_bin / "uv"
    uv.write_text('#!/bin/sh\nprintf "%s\\n" "$UV_PROJECT_ENVIRONMENT" "$@"\n')
    uv.chmod(0o700)
    dev_bin = tmp_path / ".venv-dev/bin"
    dev_bin.mkdir(parents=True)
    doctor = dev_bin / "ninjarobot_pi5_cli"
    doctor.write_text('#!/bin/sh\nprintf "doctor %s\\n" "$*"\n')
    doctor.chmod(0o700)
    hardware = tmp_path / ".venv"
    hardware.mkdir()
    (hardware / "preserve").write_text("keep")
    result = subprocess.run(
        ["bash", str(scripts / "install-rpi.sh"), "--profile", "development", "--yes"],
        env={**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert str(tmp_path / ".venv-dev") in result.stdout
    assert "--frozen" in result.stdout
    assert "doctor doctor --profile development" in result.stdout
    assert (hardware / "preserve").read_text() == "keep"
