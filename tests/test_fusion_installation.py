"""Installer checks never invoke package management, kernel loading or live writes."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "fusion_setup", Path(__file__).resolve().parents[1] / "scripts/fusion_hat_setup.py"
)
assert SPEC and SPEC.loader
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


def test_preview_is_read_only(monkeypatch, tmp_path):
    monkeypatch.setattr(setup, "STATE", tmp_path / "state")
    monkeypatch.setattr(setup.subprocess, "run", lambda *a, **k: pytest.fail("must not execute"))
    monkeypatch.setattr(setup, "verify_source", lambda path: None)
    setup.install(tmp_path, apply=False)
    assert not (tmp_path / "state").exists()
    result = setup.preview()
    assert result["loads_module"] is False
    assert result["installs_packages"] is False
    assert result["changes_audio_defaults"] is False


def test_source_verification_rejects_changed_or_symlinked_input(monkeypatch, tmp_path):
    expected = setup.digest(b"reviewed")
    monkeypatch.setattr(setup, "manifest", lambda: {"build_files": {"driver/a.c": expected}})
    path = tmp_path / "driver/a.c"
    path.parent.mkdir()
    path.write_bytes(b"reviewed")
    setup.verify_source(tmp_path)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Unreviewed"):
        setup.verify_source(tmp_path)
    path.unlink()
    other = tmp_path / "other"
    other.write_bytes(b"reviewed")
    path.symlink_to(other)
    with pytest.raises(ValueError, match="Unreviewed"):
        setup.verify_source(tmp_path)


def test_rollback_refuses_later_user_edits(monkeypatch, tmp_path):
    import json

    state = tmp_path / "state"
    state.mkdir()
    target = tmp_path / "boot.txt"
    target.write_bytes(b"later user edit")
    (state / "0").write_bytes(b"old")
    (state / "transaction.json").write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": str(target),
                        "backup": "0",
                        "installed_hash": setup.digest(b"installed"),
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(setup, "STATE", state)
    with pytest.raises(RuntimeError, match="Changed since installation"):
        setup.rollback(apply=False)
    assert target.read_bytes() == b"later user edit"


def test_partial_installation_rollback_restores_only_transaction_files(monkeypatch, tmp_path):
    import json

    state = tmp_path / "state"
    state.mkdir()
    original = tmp_path / "boot.txt"
    original.write_bytes(b"new")
    untouched = tmp_path / "unrelated"
    untouched.write_bytes(b"keep")
    absent = tmp_path / "not-yet-installed"
    (state / "0").write_bytes(b"old")
    (state / "transaction.json").write_text(
        json.dumps(
            {
                "kernel": "test",
                "files": [
                    {
                        "path": str(original),
                        "backup": "0",
                        "backup_hash": setup.digest(b"old"),
                        "installed_hash": setup.digest(b"new"),
                        "mode": 0o640,
                    },
                    {
                        "path": str(absent),
                        "backup": None,
                        "installed_hash": setup.digest(b"pending"),
                    },
                ],
            }
        )
    )
    monkeypatch.setattr(setup, "STATE", state)
    monkeypatch.setattr(setup.os, "geteuid", lambda: 0)
    monkeypatch.setattr(setup.os, "chown", lambda *args: None)
    real_exists = Path.exists
    monkeypatch.setattr(
        Path, "exists", lambda p: False if str(p) == "/sys/class/fusion_hat" else real_exists(p)
    )
    commands = []
    monkeypatch.setattr(setup.subprocess, "run", lambda command, **kwargs: commands.append(command))
    setup.rollback(apply=True)
    assert original.read_bytes() == b"old"
    assert original.stat().st_mode & 0o777 == 0o640
    assert untouched.read_bytes() == b"keep"
    assert not absent.exists()
    assert not state.exists()
    assert commands == [["depmod", "-a", "test"]]
