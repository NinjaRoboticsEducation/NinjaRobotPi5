"""Private, bounded backup snapshots and prevalidated offline restore."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ninjarobot_pi5_ide.hardware_ownership import HardwareOwnership

from ninjarobot_pi5_ide import load_robot_config

from .mcp_config import load_mcp_configuration
from .service import ServiceOwnership

if TYPE_CHECKING:
    from .deployment import DeploymentSpec

MAX_BACKUP_BYTES = 1024 * 1024 * 1024
MAX_BACKUP_FILES = 20_000


@contextmanager
def _offline(spec: DeploymentSpec) -> Iterator[None]:
    service = ServiceOwnership(_plain_path(spec.lock))
    hardware = HardwareOwnership()
    service.acquire()
    try:
        hardware.acquire()
        try:
            yield
        finally:
            hardware.release()
    finally:
        service.release()


def _plain_path(path: Path) -> Path:
    """Reject links before resolution, including symlinked parent directories."""
    result = path.expanduser().absolute()
    if ".." in result.parts or any(p.is_symlink() for p in (result, *result.parents)):
        raise ValueError("backup paths must not contain symbolic links or parent traversal")
    return result


def _inventory(spec: DeploymentSpec, *, allow_invalid_config: bool = False) -> dict[Path, str]:
    inventory = {
        spec.config: "file",
        spec.mcp_config: "file",
        spec.secret_file: "file",
        spec.database: "database",
        spec.ledger: "database",
        spec.skill_dir: "directory",
        spec.benchmark_dir: "directory",
        spec.web_certificate: "file",
        spec.web_key: "file",
    }
    try:
        config = load_robot_config(spec.config)
    except (OSError, ValueError):
        if not allow_invalid_config:
            raise ValueError("validate the active configuration before creating a backup") from None
    else:
        inventory.update(
            {
                Path(config.memory.face_data_directory): "directory",
                Path(config.behaviors.user_directory): "directory",
                Path(config.hardware.servos.calibration_file): "file",
                Path(config.behaviors.safety_state_file): "safety",
            }
        )
    result = {_plain_path(path): kind for path, kind in inventory.items()}
    for path, kind in result.items():
        if path == Path("/"):
            raise ValueError("the filesystem root cannot be a backup source")
        if path.exists() and (path.is_dir() != (kind == "directory")):
            raise ValueError("a backup source has an unexpected file type")
        if any(path != other and path.is_relative_to(other) for other in result):
            raise ValueError(
                "overlapping backup source paths require explicit configuration repair"
            )
    return result


def _snapshot_database(source: Path, destination: Path) -> None:
    deadline = time.monotonic() + 10

    def progress(status: int, remaining: int, total: int) -> None:
        if time.monotonic() > deadline:
            raise TimeoutError("database snapshot exceeded ten seconds; retry while idle")

    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=1)) as reader:
        with closing(sqlite3.connect(destination)) as writer:
            reader.backup(writer, pages=256, progress=progress, sleep=0.05)
            writer.execute("PRAGMA journal_mode=DELETE")
            if writer.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("database snapshot failed integrity validation")


def _digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_backup(spec: DeploymentSpec, output: Path) -> Path:
    """Publish a complete private archive only after all snapshots succeed."""
    destination = _plain_path(output)
    inventory = _inventory(spec)
    if any(destination == p or destination.is_relative_to(p) for p in inventory):
        raise ValueError("backup output must be outside the archived source paths")
    if destination.exists():
        raise FileExistsError("backup output already exists; choose a new filename")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ninja-backup-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        entries: dict[str, dict[str, Any]] = {}
        directories: list[Path] = []
        total = 0
        for root, kind in sorted(inventory.items()):
            if not root.exists():
                continue
            paths = [root, *sorted(root.rglob("*"))] if kind == "directory" else [root]
            for source in paths:
                _plain_path(source)
                if len(entries) + len(directories) >= MAX_BACKUP_FILES:
                    raise ValueError("backup exceeds the supported file count")
                if source.is_dir():
                    directories.append(source)
                    continue
                if not source.is_file() or source.stat().st_nlink != 1:
                    raise ValueError("backup sources must be regular files without links")
                if (
                    len(entries) >= MAX_BACKUP_FILES
                    or total + source.stat().st_size > MAX_BACKUP_BYTES
                ):
                    raise ValueError("backup exceeds the supported file count or size")
                copied = stage / str(len(entries))
                if kind == "database":
                    _snapshot_database(source, copied)
                else:
                    shutil.copyfile(source, copied)
                copied.chmod(0o600 | (source.stat().st_mode & 0o100))
                total += copied.stat().st_size
                if total > MAX_BACKUP_BYTES:
                    raise ValueError("backup snapshots exceed the supported size")
                name = "data/" + str(source.relative_to("/"))
                entries[name] = {
                    "sha256": _digest(copied),
                    "size": copied.stat().st_size,
                    "snapshot": copied.name,
                }
        manifest = {
            "version": 2,
            "created_at": datetime.now(UTC).isoformat(),
            "user": spec.user,
            "sources": [str(path) for path in inventory],
            "missing_sources": [str(path) for path in inventory if not path.exists()],
            "files": {
                name: {k: v for k, v in entry.items() if k != "snapshot"}
                for name, entry in entries.items()
            },
            "consistency": (
                "Each SQLite database is consistent; stop writers for a cross-file snapshot."
            ),
        }
        archive_path = stage / "archive.tar.gz"
        with archive_path.open("xb") as handle:
            os.chmod(archive_path, 0o600)
            with tarfile.open(fileobj=handle, mode="w:gz") as archive:
                for directory in directories:
                    info = tarfile.TarInfo("data/" + str(directory.relative_to("/")))
                    info.type, info.mode = tarfile.DIRTYPE, 0o700
                    archive.addfile(info)
                for name, entry in entries.items():
                    archive.add(stage / entry["snapshot"], arcname=name, recursive=False)
                payload = json.dumps(manifest, sort_keys=True).encode()
                info = tarfile.TarInfo("manifest.json")
                info.size, info.mode = len(payload), 0o600
                archive.addfile(info, io.BytesIO(payload))
            handle.flush()
            os.fsync(handle.fileno())
        # Hard-link publication is atomic and refuses an existing destination.
        os.link(archive_path, destination)
        _sync_directory(destination.parent)
    return destination


def _stage_archive(
    spec: DeploymentSpec, source: Path, stage: Path, inventory: dict[Path, str]
) -> tuple[dict[Path, Path], set[Path]]:
    staged: dict[Path, Path] = {}
    directories: set[Path] = set()
    with tarfile.open(source, "r:gz") as archive:
        members: list[tarfile.TarInfo] = []
        seen: set[str] = set()
        total = 0
        for member in archive:
            total += member.size
            if len(members) >= MAX_BACKUP_FILES + 1 or total > MAX_BACKUP_BYTES:
                raise ValueError("archive exceeds the supported file count or size")
            if member.name in seen or member.size < 0:
                raise ValueError("archive contains a duplicate or invalid member")
            seen.add(member.name)
            if not member.isfile() and not member.isdir():
                raise ValueError("archive contains links or unsupported members")
            members.append(member)
        manifests = [m for m in members if m.name == "manifest.json" and m.isfile()]
        if len(manifests) != 1 or manifests[0].size > 8 * 1024 * 1024:
            raise ValueError("backup manifest is missing or invalid")
        content = archive.extractfile(manifests[0])
        assert content is not None
        with content:
            manifest = json.load(content)
        if not isinstance(manifest, dict) or manifest.get("version") not in (None, 2):
            raise ValueError("backup manifest version is unsupported")
        expected = manifest.get("files")
        if expected is not None and not isinstance(expected, dict):
            raise ValueError("backup file inventory is invalid")
        if manifest.get("version") == 2 and not isinstance(expected, dict):
            raise ValueError("backup file inventory is invalid")
        for member in members:
            if member.name == "manifest.json":
                continue
            parts = member.name.split("/")
            if parts[0] != "data" or any(part in ("", ".", "..") for part in parts):
                raise ValueError("backup contains an unsafe member path")
            target = _plain_path(Path("/").joinpath(*parts[1:]))
            if not any(
                target == base or (kind == "directory" and target.is_relative_to(base))
                for base, kind in inventory.items()
            ):
                raise ValueError("backup member is outside current approved user-data paths")
            if member.isdir():
                if target in inventory and inventory[target] != "directory":
                    raise ValueError("archive directory conflicts with a configured file")
                if target.exists() and not target.is_dir():
                    raise ValueError("archive directory conflicts with a current file")
                directories.add(target)
                continue
            if target.is_dir() or inventory.get(target) == "directory":
                raise ValueError("archive file conflicts with a directory")
            content = archive.extractfile(member)
            if content is None:
                raise ValueError("backup member could not be read")
            copied = stage / str(len(staged))
            with content, copied.open("xb") as handle:
                shutil.copyfileobj(content, handle, length=1024 * 1024)
            copied.chmod(0o600 | (member.mode & 0o100))
            if expected is not None and expected.get(member.name) != {
                "size": copied.stat().st_size,
                "sha256": _digest(copied),
            }:
                raise ValueError("backup member failed its recorded size or hash check")
            staged[target] = copied
        if expected is not None and set(expected) != {
            "data/" + str(p.relative_to("/")) for p in staged
        }:
            raise ValueError("backup is missing recorded files")
    config_path = _plain_path(spec.config)
    if any(parent in staged for target in (*staged, *directories) for parent in target.parents):
        raise ValueError("archive paths conflict with each other")
    if config_path not in staged:
        raise ValueError("backup does not contain the robot configuration")
    try:
        restored_config = load_robot_config(staged[config_path])
        # A backup must not redirect future runtime writes to paths that the
        # operator's current configuration did not authorize for this restore.
        try:
            current_config = load_robot_config(spec.config)
        except (OSError, ValueError):
            current_config = None
        if current_config is not None:
            for old, new in (
                (
                    current_config.memory.face_data_directory,
                    restored_config.memory.face_data_directory,
                ),
                (current_config.behaviors.user_directory, restored_config.behaviors.user_directory),
                (
                    current_config.behaviors.safety_state_file,
                    restored_config.behaviors.safety_state_file,
                ),
                (
                    current_config.hardware.servos.calibration_file,
                    restored_config.hardware.servos.calibration_file,
                ),
            ):
                if _plain_path(Path(old)) != _plain_path(Path(new)):
                    raise ValueError("backup persistent paths differ from current configuration")
        if _plain_path(spec.mcp_config) in staged:
            load_mcp_configuration(staged[_plain_path(spec.mcp_config)])
        for path, copied in staged.items():
            if inventory.get(path) == "database":
                with closing(sqlite3.connect(copied.as_uri() + "?mode=ro", uri=True)) as database:
                    if database.execute("PRAGMA quick_check").fetchone() != ("ok",):
                        raise ValueError("invalid database")
    except (OSError, ValueError, sqlite3.Error):
        raise ValueError(
            "backup configuration or database validation failed; no data restored"
        ) from None
    return staged, directories


def _replace_file(source: Path, target: Path) -> None:
    """Use a same-filesystem private temporary file for each atomic replacement."""
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            with source.open("rb") as reader:
                shutil.copyfileobj(reader, handle)
            os.fchmod(handle.fileno(), source.stat().st_mode & 0o777)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, target)
            _sync_directory(target.parent)
        finally:
            temporary.unlink(missing_ok=True)


def restore_backup(spec: DeploymentSpec, backup: Path, *, confirmed: bool) -> dict[str, Any]:
    """Validate every member first; roll back changed files on an ordinary failure."""
    if not confirmed:
        raise ValueError("backup rollback requires --confirm")
    with _offline(spec):
        return _restore_offline(spec, backup)


def _restore_offline(spec: DeploymentSpec, backup: Path) -> dict[str, Any]:
    source = _plain_path(backup)
    inventory = _inventory(spec, allow_invalid_config=True)
    if not source.is_file():
        raise ValueError("backup archive is unavailable")
    # The caller stops the service. Also refuse leftovers from open SQLite clients;
    # replacing a main database while a WAL still exists can replay unrelated data.
    for path, kind in inventory.items():
        if kind == "database" and any(
            Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm")
        ):
            raise ValueError("close all database clients and checkpoint SQLite before restore")
    parent = _plain_path(spec.config).parent
    if any(parent.glob(".ninja-restore-*/recovery.json")):
        raise ValueError("an interrupted restore needs manual recovery before another restore")
    stage = Path(tempfile.mkdtemp(prefix=".ninja-restore-", dir=parent))
    keep_recovery = False
    changed: list[Path] = []
    originals: dict[Path, Path | None] = {}
    created_directories: list[Path] = []

    def make_directory(path: Path) -> None:
        missing = [p for p in (path, *path.parents) if not p.exists()]
        for directory in reversed(missing):
            _plain_path(directory)
            directory.mkdir(mode=0o700)
            created_directories.append(directory)

    try:
        staged, directories = _stage_archive(spec, source, stage, inventory)
        # Never clear a current safety latch as a side effect of data recovery.
        staged = {
            p: c for p, c in staged.items() if not (inventory.get(p) == "safety" and p.exists())
        }
        for index, path in enumerate(staged):
            if path.exists():
                original = stage / f"original-{index}"
                shutil.copyfile(path, original)
                original.chmod(path.stat().st_mode & 0o777)
                with original.open("rb") as original_handle:
                    os.fsync(original_handle.fileno())
                originals[path] = original
            else:
                originals[path] = None
        journal = stage / "recovery.json"
        with journal.open("x", encoding="utf-8") as handle:
            json.dump({str(p): str(old) if old else None for p, old in originals.items()}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        _sync_directory(stage)
        _sync_directory(parent)
        try:
            for directory in sorted(directories):
                make_directory(directory)
            for path, copied in staged.items():
                _plain_path(path)
                make_directory(path.parent)
                changed.append(path)
                _replace_file(copied, path)
        except BaseException:
            for path in reversed(changed):
                try:
                    prior = originals[path]
                    if prior is None:
                        path.unlink(missing_ok=True)
                    else:
                        _replace_file(prior, path)
                except OSError:
                    keep_recovery = True
            for directory in reversed(created_directories):
                try:
                    directory.rmdir()
                except OSError:
                    keep_recovery = True
            if keep_recovery:
                raise RuntimeError(
                    f"restore and rollback failed; keep robot stopped; recovery: {stage}"
                ) from None
            raise
        return {
            "restored_files": len(changed),
            "newer_unarchived_data_preserved": True,
            "current_safety_state_preserved": True,
        }
    finally:
        if not keep_recovery:
            shutil.rmtree(stage)
