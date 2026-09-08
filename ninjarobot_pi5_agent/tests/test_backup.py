from __future__ import annotations

import io
import json
import sqlite3
import tarfile
from dataclasses import fields
from pathlib import Path

import pytest
from ninjarobot_pi5_agent.deployment import DeploymentSpec
from ninjarobot_pi5_agent.service import ServiceAlreadyRunningError, ServiceOwnership
from ninjarobot_pi5_ide.hardware_ownership import HardwareOwnership, HardwareOwnershipError

from ninjarobot_pi5_agent import backup
from ninjarobot_pi5_ide import load_robot_config, save_robot_config


@pytest.fixture
def spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DeploymentSpec:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    paths = {
        field.name: tmp_path / field.name
        for field in fields(DeploymentSpec)
        if field.name != "user"
    }
    result = DeploymentSpec(user="test", **paths)
    config = load_robot_config(
        Path(__file__).resolve().parents[2] / "config/ninjarobot_pi5.toml.example"
    )
    save_robot_config(config, result.config, overwrite=False)
    result.mcp_config.write_text("schema_version = 1\nservers = []\n")
    result.secret_file.write_text("EXAMPLE=value\n")
    with sqlite3.connect(result.database) as database:
        database.execute("CREATE TABLE notes (text TEXT)")
        database.execute("INSERT INTO notes VALUES ('saved')")
    return result


def _archive(path: Path, entries: list[tuple[str, bytes]], *, manifest: bytes = b"{}") -> Path:
    with tarfile.open(path, "w:gz") as archive:
        for name, data in [("manifest.json", manifest), *entries]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


def _name(path: Path) -> str:
    return "data/" + str(path.relative_to("/"))


def test_backup_includes_committed_wal_rows(spec: DeploymentSpec, tmp_path: Path) -> None:
    database = sqlite3.connect(spec.database)
    try:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("PRAGMA wal_autocheckpoint=0")
        database.execute("INSERT INTO notes VALUES ('in journal')")
        database.commit()
        assert Path(str(spec.database) + "-wal").stat().st_size > 0
        saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
        with tarfile.open(saved) as archive:
            content = archive.extractfile(_name(spec.database))
            assert content is not None
            snapshot = tmp_path / "snapshot.sqlite"
            snapshot.write_bytes(content.read())
        with sqlite3.connect(snapshot) as restored:
            assert restored.execute("SELECT text FROM notes").fetchall() == [
                ("saved",),
                ("in journal",),
            ]
    finally:
        database.close()


def test_backup_restore_preserves_reviewed_local_reminder(
    spec: DeploymentSpec, tmp_path: Path
) -> None:
    import asyncio
    from datetime import UTC, datetime, timedelta

    from ninjarobot_pi5_agent.memory_migrations import migrate_agent_database
    from ninjarobot_pi5_agent.task_service import TaskService

    with sqlite3.connect(spec.database) as database:
        migrate_agent_database(database)

    async def prepare():
        async def forbidden(task):
            pytest.fail("backup test must never deliver a notification")

        service = TaskService(spec.database, forbidden)
        await service.start(background=False)
        try:
            item = await service.preview(
                scope="session:backup",
                user_id=None,
                session_id="backup",
                title="Test reminder",
                due_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                timezone="UTC",
            )
            return await service.change(item.owner_scope, item.task_id, "confirm")
        finally:
            await service.close()

    reviewed = asyncio.run(prepare())
    archive = backup.create_backup(spec, tmp_path / "task-backup.tar.gz")
    with sqlite3.connect(spec.database) as database:
        database.execute("DELETE FROM local_tasks")
    backup.restore_backup(spec, archive, confirmed=True)
    with sqlite3.connect(spec.database) as database:
        record = database.execute(
            "SELECT record_json FROM local_tasks WHERE task_id=?", (reviewed.task_id,)
        ).fetchone()
    assert record is not None
    assert json.loads(record[0]) == reviewed.model_dump(mode="json")


def test_inventory_includes_optional_private_data(spec: DeploymentSpec, tmp_path: Path) -> None:
    inventory = backup._inventory(spec)
    for path, kind in inventory.items():
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "directory":
            path.mkdir()
            (path / "example").write_text("test fixture")
        elif kind == "database":
            with sqlite3.connect(path) as database:
                database.execute("CREATE TABLE example (value TEXT)")
        else:
            path.write_text("test fixture")
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    assert saved.stat().st_mode & 0o777 == 0o600
    with tarfile.open(saved) as archive:
        names = set(archive.getnames())
    for path, kind in inventory.items():
        assert _name(path / "example" if kind == "directory" else path) in names


def test_backup_refuses_overwrite_and_source_symlinks(spec: DeploymentSpec, tmp_path: Path) -> None:
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    before = saved.read_bytes()
    with pytest.raises(FileExistsError):
        backup.create_backup(spec, saved)
    assert saved.read_bytes() == before
    spec.skill_dir.mkdir()
    (spec.skill_dir / "linked").symlink_to(spec.secret_file)
    with pytest.raises(ValueError, match="symbolic"):
        backup.create_backup(spec, tmp_path / "bad.tar.gz")
    assert not (tmp_path / "bad.tar.gz").exists()


@pytest.mark.parametrize("unsafe", ["data/etc/unapproved", "data/../bad", "data//tmp/bad"])
def test_late_unsafe_member_prevents_all_replacement(
    spec: DeploymentSpec, tmp_path: Path, unsafe: str
) -> None:
    original = spec.secret_file.read_bytes()
    saved = _archive(
        tmp_path / "unsafe.tar.gz",
        [
            (_name(spec.config), spec.config.read_bytes()),
            (_name(spec.secret_file), b"changed"),
            (unsafe, b"unsafe"),
        ],
    )
    with pytest.raises(ValueError):
        backup.restore_backup(spec, saved, confirmed=True)
    assert spec.secret_file.read_bytes() == original


def test_invalid_configuration_is_checked_before_replacement(
    spec: DeploymentSpec, tmp_path: Path
) -> None:
    original = spec.secret_file.read_bytes()
    saved = _archive(
        tmp_path / "invalid.tar.gz",
        [
            (_name(spec.secret_file), b"changed"),
            (_name(spec.config), b"not valid toml"),
        ],
    )
    with pytest.raises(ValueError, match="validation failed"):
        backup.restore_backup(spec, saved, confirmed=True)
    assert spec.secret_file.read_bytes() == original


def test_duplicate_and_hash_mismatch_rejected(spec: DeploymentSpec, tmp_path: Path) -> None:
    saved = _archive(
        tmp_path / "duplicate.tar.gz",
        [(_name(spec.config), spec.config.read_bytes()), (_name(spec.config), b"duplicate")],
    )
    with pytest.raises(ValueError, match="duplicate"):
        backup.restore_backup(spec, saved, confirmed=True)
    saved = _archive(
        tmp_path / "hash.tar.gz",
        [(_name(spec.config), spec.config.read_bytes())],
        manifest=json.dumps(
            {"version": 2, "files": {_name(spec.config): {"size": 1, "sha256": "wrong"}}}
        ).encode(),
    )
    with pytest.raises(ValueError, match="hash"):
        backup.restore_backup(spec, saved, confirmed=True)


def test_restore_preserves_newer_files_and_current_safety(
    spec: DeploymentSpec, tmp_path: Path
) -> None:
    config = load_robot_config(spec.config)
    safety = Path(config.behaviors.safety_state_file).expanduser()
    safety.parent.mkdir(parents=True)
    safety.write_text('{"motion_latched":false}')
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    safety.write_text('{"motion_latched":true}')
    spec.skill_dir.mkdir()
    newer = spec.skill_dir / "newer"
    newer.write_text("keep")
    spec.secret_file.write_text("changed")
    result = backup.restore_backup(spec, saved, confirmed=True)
    assert result["restored_files"] >= 4
    assert spec.secret_file.read_text() == "EXAMPLE=value\n"
    assert newer.read_text() == "keep"
    assert json.loads(safety.read_text())["motion_latched"] is True


def test_interrupted_replacement_rolls_back_all_files(
    spec: DeploymentSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    spec.secret_file.write_text("newer secret")
    originals = {
        p: p.read_bytes() for p in (spec.config, spec.database, spec.secret_file, spec.mcp_config)
    }
    replace = backup._replace_file
    calls = 0

    def fail_once(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("injected write failure")
        replace(source, target)

    monkeypatch.setattr(backup, "_replace_file", fail_once)
    with pytest.raises(OSError, match="injected"):
        backup.restore_backup(spec, saved, confirmed=True)
    assert all(path.read_bytes() == data for path, data in originals.items())
    assert not list(tmp_path.glob(".ninja-restore-*"))


def test_restore_refuses_running_owners(spec: DeploymentSpec, tmp_path: Path) -> None:
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    owner = ServiceOwnership(spec.lock)
    owner.acquire()
    try:
        with pytest.raises(ServiceAlreadyRunningError):
            backup.restore_backup(spec, saved, confirmed=True)
    finally:
        owner.release()
    hardware = HardwareOwnership()
    hardware.acquire()
    try:
        with pytest.raises(HardwareOwnershipError):
            backup.restore_backup(spec, saved, confirmed=True)
    finally:
        hardware.release()


def test_restore_refuses_existing_database_journal(spec: DeploymentSpec, tmp_path: Path) -> None:
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    Path(str(spec.database) + "-wal").touch()
    with pytest.raises(ValueError, match="checkpoint"):
        backup.restore_backup(spec, saved, confirmed=True)


def test_empty_directories_survive_backup(spec: DeploymentSpec, tmp_path: Path) -> None:
    spec.skill_dir.mkdir()
    empty = spec.skill_dir / "empty"
    empty.mkdir()
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    empty.rmdir()
    backup.restore_backup(spec, saved, confirmed=True)
    assert empty.is_dir()
    assert empty.stat().st_mode & 0o777 == 0o700


def test_corrupt_database_never_publishes_backup(spec: DeploymentSpec, tmp_path: Path) -> None:
    spec.database.write_bytes(b"not a database")
    with pytest.raises(sqlite3.DatabaseError):
        backup.create_backup(spec, tmp_path / "bad.tar.gz")
    assert not (tmp_path / "bad.tar.gz").exists()


def test_archive_limit_is_checked_before_replacement(
    spec: DeploymentSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    original = spec.config.read_bytes()
    monkeypatch.setattr(backup, "MAX_BACKUP_BYTES", 20)
    with pytest.raises(ValueError, match="size"):
        backup.restore_backup(spec, saved, confirmed=True)
    assert spec.config.read_bytes() == original


def test_rollback_failure_keeps_recovery_files_and_blocks_repeat(
    spec: DeploymentSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    original = spec.config.read_bytes()

    def fail(source: Path, target: Path) -> None:
        raise OSError("injected persistent disk failure")

    monkeypatch.setattr(backup, "_replace_file", fail)
    with pytest.raises(RuntimeError, match="recovery:"):
        backup.restore_backup(spec, saved, confirmed=True)
    journals = list(tmp_path.glob(".ninja-restore-*/recovery.json"))
    assert len(journals) == 1
    records = json.loads(journals[0].read_text())
    assert Path(records[str(spec.config)]).read_bytes() == original
    assert journals[0].parent.stat().st_mode & 0o777 == 0o700
    with pytest.raises(ValueError, match="manual recovery"):
        backup.restore_backup(spec, saved, confirmed=True)


def test_destination_symlink_cannot_redirect_restore(spec: DeploymentSpec, tmp_path: Path) -> None:
    saved = backup.create_backup(spec, tmp_path / "saved.tar.gz")
    outside = tmp_path / "outside"
    outside.write_text("keep")
    spec.secret_file.unlink()
    spec.secret_file.symlink_to(outside)
    with pytest.raises(ValueError, match="symbolic"):
        backup.restore_backup(spec, saved, confirmed=True)
    assert outside.read_text() == "keep"
