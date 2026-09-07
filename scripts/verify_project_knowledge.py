#!/usr/bin/env python3
"""Read-only checks for current manuals, evidence drift, adapters and Markdown links."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WIKI = "ninjarobot_pi5_wiki"
LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)")


def fingerprint(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def prose(text: str) -> str:
    return re.sub(r"^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text, flags=re.M | re.S)


def headings(text: str) -> set[str]:
    found = set(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', text))
    counts: dict[str, int] = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*$", prose(text), re.M):
        heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
        slug = "".join(
            c for c in heading.lower() if c in "_- " or unicodedata.category(c)[0] in "LN"
        ).replace(" ", "-")
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        found.add(slug + (f"-{number}" if number else ""))
    return found


def local_links(document: Path, root: Path) -> list[str]:
    errors = []
    for raw in LINK.findall(prose(document.read_text(encoding="utf-8"))):
        target = raw.strip("<>")
        if urlsplit(target).scheme or target.startswith("//"):
            continue
        path, _, fragment = target.partition("#")
        resolved = (document.parent / unquote(path)).resolve() if path else document.resolve()
        if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
            errors.append(f"{document.relative_to(root)}: missing local link {target}")
        elif fragment and resolved.is_file() and resolved.suffix.lower() == ".md":
            if unquote(fragment) not in headings(resolved.read_text(encoding="utf-8")):
                errors.append(f"{document.relative_to(root)}: missing heading {target}")
    return errors


def verify(root: Path) -> list[str]:
    manifest = root / WIKI / "project-knowledge.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    errors = []
    if data.get("integration_status") != "ready":
        errors.append("Knowledge publication is pending; review the recorded semantic plan")
    for item in data["documents"]:
        source = root / WIKI / item["path"]
        if not source.is_file() or fingerprint(source) != item["content_hash"]:
            errors.append(f"Manual missing or changed: {item['name']}")
        readme_text = (root / "README.md").read_text(encoding="utf-8")
        if f"]({WIKI}/{item['path']})" not in readme_text:
            errors.append(f"Root README does not link to the current manual: {item['name']}")
        readme = root / WIKI / "README.md"
        if f"]({item['path']})" not in readme.read_text(encoding="utf-8"):
            errors.append(f"Wiki README does not link to the current manual: {item['name']}")
        catalog = root / WIKI / "raw/_catalog" / f"{item['source_id']}.yaml"
        if not catalog.is_file():
            errors.append(f"Source record missing: {item['source_id']}")
        else:
            # These scalars are emitted by the existing wiki catalog writer.
            fields = dict(re.findall(r"^(id|path|content_hash): (.+)$", catalog.read_text(), re.M))
            for key, expected in (
                ("id", item["source_id"]),
                ("path", item["path"]),
                ("content_hash", item["content_hash"]),
            ):
                if fields.get(key, "").strip("\"'") != expected:
                    errors.append(f"Catalog and current source disagree: {item['name']} ({key})")
        for page in item["pages"]:
            path = root / WIKI / page
            if not path.is_file():
                errors.append(f"Knowledge page missing: {page}")
                continue
            text = path.read_text(encoding="utf-8")
            if item["source_id"] not in text or item["content_hash"] not in text:
                errors.append(f"Page needs current source review: {page}")
    covered = data["implementation_files"]
    for relative, evidence in covered.items():
        path = root / relative
        if not path.is_file() or fingerprint(path) != evidence["content_hash"]:
            errors.append(f"Implementation needs knowledge review: {relative}")
        if not evidence.get("review_note") or not evidence.get("pages"):
            errors.append(f"Implementation mapping lacks review context: {relative}")
        for page in evidence.get("pages", []):
            if not (root / WIKI / page).is_file():
                errors.append(f"Mapped knowledge page missing: {page}")
    for directory in data["implementation_roots"]:
        for path in (root / directory).rglob("*"):
            if not path.is_file() or any(
                x.startswith(".") or x == "__pycache__"
                for x in path.relative_to(root / directory).parts
            ):
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            if path.relative_to(root).as_posix() not in covered:
                errors.append(
                    f"New implementation file needs classification: {path.relative_to(root)}"
                )
    for adapter in data["adapters"]:
        path = root / adapter["path"]
        target = root / adapter["target"]
        if not path.is_file() or not target.is_file():
            errors.append(f"Adapter or canonical target missing: {adapter['path']}")
        elif adapter["reference"] not in path.read_text(encoding="utf-8"):
            errors.append(f"Adapter does not reference shared policy: {adapter['path']}")
        else:
            reference = adapter["reference"].lstrip("@")
            base = path.parent if reference.startswith(".") else root
            if (base / reference).resolve() != target.resolve():
                errors.append(f"Adapter target resolves incorrectly: {adapter['path']}")
    for relative in data["link_documents"]:
        path = root / relative
        if path.is_file():
            errors.extend(local_links(path, root))
        else:
            errors.append(f"Document missing: {relative}")
    return list(dict.fromkeys(errors))


def main() -> int:
    try:
        errors = verify(ROOT)
    except (OSError, ValueError, KeyError) as error:
        print(f"Knowledge configuration error: {error}")
        return 1
    for error in errors:
        print(error)
    if not errors:
        print("PASS: current manuals, mapped implementation, adapters, and local links.")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
