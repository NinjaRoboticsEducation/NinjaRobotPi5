from __future__ import annotations

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
