from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
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
