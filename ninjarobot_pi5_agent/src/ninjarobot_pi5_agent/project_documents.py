"""Section retrieval from explicitly public, hash-checked current project manuals."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

MANUALS = frozenset(
    {"InstallationGuide.md", "DevelopmentGuide.md", "DevelopmentLog.md", "NinjaRobot_MCP_Skill.md"}
)
STOP_WORDS = frozenset(
    (
        "a an the to of in on for and or is are can how what where me my please give "
        "step by instructions set up setup project robot ninjarobot wiki about"
    ).split()
)


def source_version(path: str) -> tuple[str, int]:
    if not isinstance(path, str):
        raise ValueError("invalid source path")
    value = path.split("/")[-2] if "/" in path else ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:-\d{2})?", value):
        raise ValueError("invalid source version")
    return value[:10], int(value[11:]) if len(value) > 10 else 0


def lookup_documents(root: Path, query: str, *, read: bool, overlay: Path) -> dict[str, Any]:
    # Import here to share the existing secure file opener without an import cycle.
    from .project_help import confined_read

    warnings = [
        "Public reference evidence only, not live device/account status. "
        "Review labels are source metadata, not hardware verification."
    ]
    catalog = json.loads(confined_read(root, "project-knowledge.json", 262144))
    if (
        not isinstance(catalog, dict)
        or catalog.get("version") != 1
        or not isinstance(catalog.get("documents"), list)
    ):
        raise ValueError("invalid current document map")
    if len(catalog["documents"]) > 100:
        raise ValueError("oversized current document map")
    documents: dict[str, dict[str, Any]] = {}
    for entry in catalog["documents"]:
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("name"), str)
            and entry["name"] in MANUALS
        ):
            documents[entry["name"]] = {
                **entry,
                "review_state": "Registered source; consult wiki review metadata",
                "page_state": "source",
            }
    if overlay.is_file():
        pending = json.loads(confined_read(overlay.parent, overlay.name, 65536))
        if (
            not isinstance(pending, dict)
            or pending.get("version") != 1
            or not isinstance(pending.get("documents"), list)
            or len(pending["documents"]) > 4
        ):
            raise ValueError("invalid runtime public-source manifest")
        for entry in pending["documents"]:
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("name"), str)
                or entry["name"] not in MANUALS
            ):
                raise ValueError("runtime manifest contains a non-public manual")
            existing = documents.get(entry["name"])
            # A later registered manual always supersedes this release's pending source.
            if existing is None or source_version(entry["path"]) > source_version(existing["path"]):
                documents[entry["name"]] = {
                    **entry,
                    "review_state": "Unpublished source; wiki ingestion and review pending",
                    "page_state": "unpublished",
                }
    tokens = tuple(
        dict.fromkeys(t for t in re.findall(r"\w+", query.casefold()) if t not in STOP_WORDS)
    )[:24]
    if not tokens and not read:
        tokens = ("features",)
    hits: list[tuple[int, dict[str, Any]]] = []
    total = 0
    for name in (
        "InstallationGuide.md",
        "NinjaRobot_MCP_Skill.md",
        "DevelopmentGuide.md",
        "DevelopmentLog.md",
    ):
        if name not in documents:
            continue
        entry = documents[name]
        try:
            path = entry["path"]
            kind = "notes" if name == "DevelopmentLog.md" else "articles"
            if not isinstance(path, str) or not re.fullmatch(
                rf"raw/{kind}/ninjarobotpi5/\d{{4}}-\d{{2}}-\d{{2}}(?:-\d{{2}})?/{re.escape(name)}",
                path,
            ):
                raise ValueError("not an approved public manual path")
            data = confined_read(root, path, 524288)
            total += len(data)
            if total > 2097152:
                raise ValueError("public document read budget exceeded")
            digest = "sha256:" + hashlib.sha256(data).hexdigest()
            if digest != entry.get("content_hash"):
                raise ValueError(
                    "content changed; source hash needs explicit documentation maintenance"
                )
            parts = sections(data.decode("utf-8"))
            prefix = name.removesuffix(".md") + ":" + digest[7:19] + ":"
            for index, (heading, start_line, body) in enumerate(parts):
                ident = prefix + str(index)
                if read and query != ident:
                    continue
                score = sum(
                    20 * (t in (heading + " " + body).casefold())
                    + 8 * (t in heading.casefold())
                    + min(3, body.casefold().count(t))
                    for t in tokens
                )
                if not read and not score:
                    continue
                if name == "DevelopmentLog.md" and not {"history", "log", "changes"} & set(tokens):
                    score = max(1, score // 2)
                hits.append(
                    (
                        score,
                        {
                            "document_id": ident,
                            "title": name,
                            "section": heading,
                            "source_path": path,
                            "start_line": start_line,
                            "source_version": path.split("/")[-2],
                            "content_hash": digest,
                            "page_state": entry["page_state"],
                            "review_state": entry["review_state"],
                            "excerpt": body,
                            "next_document_id": prefix + str(index + 1)
                            if index + 1 < len(parts)
                            else None,
                        },
                    )
                )
        except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
            warnings.append(f"{name}: withheld ({type(exc).__name__}: {str(exc)[:120]}).")
    hits.sort(key=lambda hit: -hit[0])
    results = []
    seen: set[str] = set()
    for _, hit in hits:
        if hit["excerpt"] in seen:
            continue
        seen.add(hit["excerpt"])
        results.append(hit)
        if len(results) >= (1 if read else 3):
            break
    if not results:
        warnings.append(
            "No matching verified section. Try focused keywords or refresh an outdated section ID."
        )
    return {"results": results, "warnings": warnings[:8], "executed": False}


def sections(text: str) -> list[tuple[str, int, str]]:
    """Split at real headings outside fences; bound each continuation to 3000 chars."""
    result: list[tuple[str, int, str]] = []
    heading = "Introduction"
    lines: list[str] = []
    start = 1
    fenced = False

    def flush() -> None:
        if lines:
            result.append((heading, start, "".join(lines)))

    for number, line in enumerate(text.splitlines(keepends=True), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        new_heading = not fenced and re.match(r"^#{1,6} ", line)
        if new_heading:
            flush()
            lines = []
            heading = line.strip().lstrip("# ")
            start = number
        if sum(map(len, lines)) + len(line) > 3000:
            flush()
            lines = []
            start = number
        # Very long generated lines also receive bounded continuation IDs.
        while len(line) > 3000:
            result.append((heading, number, line[:3000]))
            line = line[3000:]
        lines.append(line)
    flush()
    return result
