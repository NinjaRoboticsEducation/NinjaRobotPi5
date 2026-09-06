#!/usr/bin/env python3
"""Run the independent project wiki from any working directory."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "ninjarobot_pi5_wiki"


def reject_symlinks(path: Path, root: Path) -> None:
    """Reject redirected evidence/cache paths before reading or writing them."""
    current = root
    for part in path.relative_to(root).parts:
        if part == "..":
            raise ValueError("Path escapes the wiki")
        current /= part
        if current.is_symlink():
            raise ValueError(f"Symlinked evidence/cache path: {current.name}")


def child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("VIRTUAL_ENV", None)
    environment.pop("UV_PROJECT_ENVIRONMENT", None)
    return environment


def prepare(wiki: Path) -> int:
    """Rebuild text evidence in isolation; never refresh a tracked source hash."""
    from llmwiki.config import Config
    from llmwiki.normalize import normalize_source
    from llmwiki.paths import sha256_file
    from llmwiki.sources import list_records

    config = Config.load(wiki)
    reject_symlinks(wiki / "raw/_catalog", wiki)
    reject_symlinks(wiki / "raw/_derived", wiki)
    records = list_records(config)
    for record in records:
        source = wiki / record["path"]
        reject_symlinks(source, wiki)
        if source.is_symlink() or not source.resolve().is_relative_to(config.raw_root.resolve()):
            raise ValueError(f"Unsafe source: {record['id']}")
        if sha256_file(source) != record["content_hash"]:
            raise ValueError(f"Source needs review: {record['id']}; original left unchanged")
        if source.suffix.lower() not in {".md", ".markdown", ".txt"}:
            raise ValueError(f"Prepare supports text only: {record['id']}; use the ingest skill")
    catalog_before = {p.name: p.read_bytes() for p in config.catalog_root.glob("*.yaml")}
    with tempfile.TemporaryDirectory(prefix="ninjarobot-wiki-prepare-") as directory:
        staged = Path(directory)
        shutil.copy2(wiki / "llmwiki.yaml", staged / "llmwiki.yaml")
        shutil.copytree(wiki / "schemas", staged / "schemas")
        # Copy registered evidence only, never runtime, secrets, media, or ignored history.
        shutil.copytree(config.catalog_root, staged / "raw/_catalog")
        for record in records:
            target = staged / record["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wiki / record["path"], target)
        staged_config = Config.load(staged)
        for record in records:
            normalize_source(staged_config, record["id"])
        if catalog_before != {p.name: p.read_bytes() for p in config.catalog_root.glob("*.yaml")}:
            raise ValueError("Catalog changed during preparation; retry after the writer finishes")
        for record in records:
            if sha256_file(wiki / record["path"]) != record["content_hash"]:
                raise ValueError("Source changed during preparation; no generated files installed")
        for record in records:
            destination = config.derived_root / record["id"]
            reject_symlinks(destination, wiki)
            if destination.is_symlink() or not destination.resolve().is_relative_to(wiki.resolve()):
                raise ValueError("Unsafe derived destination")
            destination.mkdir(parents=True, exist_ok=True)
            for source in (staged_config.derived_root / record["id"]).iterdir():
                target = destination / source.name
                if target.is_symlink():
                    raise ValueError("Unsafe derived file")
                # A manifest timestamp may change; only ignored derived files are written.
                shutil.copy2(source, target)
    print(f"Prepared {len(records)} text sources; tracked sources and catalogs unchanged.")
    return 0


def main(arguments: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if arguments == ["--prepare-worker"]:
        return prepare(WIKI)
    if not arguments or arguments == ["--help"]:
        print("Usage: python scripts/wiki.py setup | prepare | check | <llmwiki arguments>")
        print("setup installs the locked wiki environment; prepare rebuilds ignored text evidence.")
        print("check validates project knowledge; other arguments call llmwiki without syncing.")
        return 0
    executable = shutil.which("uv")
    if executable is None:
        raise ValueError("uv is unavailable. Read the local wiki README and manuals directly.")
    if arguments == ["setup"]:
        command = [executable, "sync", "--directory", str(WIKI), "--frozen", "--all-extras"]
    else:
        python = WIKI / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.exists():
            raise ValueError("Wiki environment missing. Run: python scripts/wiki.py setup")
        command = [executable, "run", "--directory", str(WIKI), "--frozen", "--no-sync"]
        if arguments == ["prepare"]:
            command += ["python", str(Path(__file__).resolve()), "--prepare-worker"]
        elif arguments == ["check"]:
            command += ["python", str(ROOT / "scripts/verify_project_knowledge.py")]
        else:
            command += ["llmwiki", *arguments]
    return subprocess.run(command, env=child_environment(), check=False, timeout=600).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Wiki: {error}", file=sys.stderr)
        raise SystemExit(1) from error
