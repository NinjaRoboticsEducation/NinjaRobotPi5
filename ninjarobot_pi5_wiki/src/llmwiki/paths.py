from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable


class UnsafePathError(ValueError):
    """Raised when a path leaves its allowed root."""


def ensure_within(path: Path, root: Path, *, must_exist: bool = False) -> Path:
    root = root.resolve()
    candidate = path.resolve(strict=must_exist)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"Path escapes allowed root {root}: {path}") from exc
    return candidate


def project_relative(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def safe_project_path(project_root: Path, value: str, allowed_root: Path) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        raise UnsafePathError(f"Absolute paths are not allowed: {value}")
    return ensure_within(project_root / raw, allowed_root)


def iter_markdown(root: Path, *, include_reserved: bool = False) -> Iterable[Path]:
    if not root.exists():
        return []
    paths = []
    for path in root.rglob("*.md"):
        if path.is_symlink():
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if not include_reserved and path.name in {"index.md", "log.md"}:
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(root).as_posix())


def concept_id(path: Path, bundle_root: Path) -> str:
    relative = path.resolve().relative_to(bundle_root.resolve())
    return relative.with_suffix("").as_posix()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "untitled"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def sha256_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def sha256_tree(root: Path) -> str:
    """Hash file paths and contents so an unrelated concurrent edit is visible."""
    digest = hashlib.sha256()
    symlinks = [item for item in root.rglob("*") if item.is_symlink()]
    if symlinks:
        raise UnsafePathError(f"Symlinks are not allowed in the wiki bundle: {symlinks[0]}")
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
