from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from .paths import ensure_within

MARKDOWN_LINK_RE = re.compile(r"(?P<image>!)?\[(?P<label>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Link:
    target: str
    label: str
    image: bool
    line: int


def extract_links(text: str) -> list[Link]:
    links = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        links.append(
            Link(
                target=match.group("target"),
                label=match.group("label"),
                image=bool(match.group("image")),
                line=text.count("\n", 0, match.start()) + 1,
            )
        )
    return links


def extract_wikilinks(text: str) -> list[tuple[str, int]]:
    return [
        (match.group(1), text.count("\n", 0, match.start()) + 1)
        for match in WIKILINK_RE.finditer(text)
    ]


def is_external(target: str) -> bool:
    parsed = urlparse(target)
    return bool(parsed.scheme or target.startswith("mailto:"))


def resolve_link(source: Path, target: str, bundle_root: Path) -> tuple[Path | None, str | None]:
    if not target or target.startswith("#"):
        return source, target[1:] or None
    if is_external(target):
        return None, None
    path_text, _, anchor = unquote(target).partition("#")
    if path_text.startswith("/"):
        candidate = bundle_root / path_text.lstrip("/")
    else:
        candidate = source.parent / path_text
    return ensure_within(candidate, bundle_root), anchor or None


def heading_slug(value: str) -> str:
    value = re.sub(r"[`*_~]", "", value.strip().lower())
    value = re.sub(r"[^\w\- ]", "", value, flags=re.UNICODE)
    return value.replace(" ", "-")


def anchors(text: str) -> set[str]:
    return {heading_slug(match.group(1)) for match in HEADING_RE.finditer(text)}
