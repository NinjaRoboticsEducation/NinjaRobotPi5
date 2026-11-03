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


def test_check_reports_unreadable_interfaces_without_traceback(monkeypatch):
    original = Path.read_text

    def read(path, *args, **kwargs):
        if str(path) in {"/sys/class/fusion_hat/fusion_hat/version", "/proc/asound/cards"}:
            raise PermissionError("simulated access denial")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    result = setup.check()
    assert result["installed_version"] is None
    assert result["version_error"] == "PermissionError"
    assert result["sound_card_ready"] is False
    assert result["ready"] is False


@pytest.mark.parametrize("action", ["prepare", "install"])
def test_incomplete_source_reports_recovery_without_deleting_files(
    monkeypatch, tmp_path, action, capsys
):
    import sys

    source = tmp_path / "incomplete"
    source.mkdir()
    keep = source / "operator-note.txt"
    keep.write_text("keep")
    monkeypatch.setattr(setup, "manifest", lambda: {"build_files": {"driver/missing.dts": "hash"}})
    monkeypatch.setattr(setup.subprocess, "run", lambda *a, **kw: pytest.fail("must not build"))
    monkeypatch.setattr(sys, "argv", ["fusion_hat_setup.py", action, "--source", str(source)])
    with pytest.raises(SystemExit) as exc:
        setup.main()
    assert exc.value.code == 1
    error = capsys.readouterr().err
    assert "missing driver/missing.dts" in error
    assert "prepare --source" in error
    assert "new empty path" in error
    assert "Traceback" not in error
    assert keep.read_text() == "keep"


def test_missing_source_is_a_clear_preparation_error(tmp_path):
    with pytest.raises(ValueError, match="Run prepare --source"):
        setup.verify_source(tmp_path / "missing")


def test_prepare_downloads_verified_source_and_rerun_is_offline(monkeypatch, tmp_path, capsys):
    import io
    import tarfile

    archive_stream = io.BytesIO()
    with tarfile.open(fileobj=archive_stream, mode="w:gz") as tar:
        info = tarfile.TarInfo("pinned/driver/a.c")
        content = b"reviewed"
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    archive = archive_stream.getvalue()
    monkeypatch.setattr(
        setup,
        "manifest",
        lambda: {
            "revision": "pinned",
            "archive_sha256": setup.digest(archive),
            "patches": [],
            "build_files": {"driver/a.c": setup.digest(content)},
        },
    )
    monkeypatch.setattr(setup.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(archive))
    source = tmp_path / "prepared"
    setup.prepare(source)
    setup.verify_source(source)
    monkeypatch.setattr(
        setup.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("must not download twice")
    )
    setup.prepare(source)
    assert "already verified; unchanged" in capsys.readouterr().out
    assert (source / "driver/a.c").read_bytes() == content


def test_prepare_rejects_archive_missing_required_file_without_partial_destination(
    monkeypatch, tmp_path
):
    import io
    import tarfile

    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz"):
        pass
    archive = stream.getvalue()
    monkeypatch.setattr(
        setup,
        "manifest",
        lambda: {
            "revision": "pinned",
            "archive_sha256": setup.digest(archive),
            "patches": [],
            "build_files": {"driver/required.dts": "hash"},
        },
    )
    monkeypatch.setattr(setup.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(archive))
    source = tmp_path / "prepared"
    with pytest.raises(ValueError, match="missing driver/required.dts"):
        setup.prepare(source)
    assert not source.exists()
    assert list(tmp_path.iterdir()) == []


def test_source_verification_rejects_parent_symlink_and_special_file(monkeypatch, tmp_path):
    import os

    monkeypatch.setattr(setup, "manifest", lambda: {"build_files": {"driver/a.c": "hash"}})
    real = tmp_path / "real"
    real.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    (source / "driver").symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        setup.verify_source(source)
    (source / "driver").unlink()
    (source / "driver").mkdir()
    os.mkfifo(source / "driver/a.c")
    with pytest.raises(ValueError, match="not a regular file"):
        setup.verify_source(source)
