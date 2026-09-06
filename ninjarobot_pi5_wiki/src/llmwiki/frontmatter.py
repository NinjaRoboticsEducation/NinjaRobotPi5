from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class FrontmatterError(ValueError):
    """Raised for invalid or missing YAML frontmatter."""


@dataclass
class Document:
    metadata: dict[str, Any]
    body: str


def _plain_yaml(value: Any) -> Any:
    """Convert PyYAML date objects back to portable OKF string values."""
    if isinstance(value, datetime):
        if value.tzinfo == timezone.utc:
            return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _plain_yaml(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_yaml(item) for item in value]
    return value


def parse_text(text: str, *, source: str = "<text>") -> Document:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise FrontmatterError(f"{source}: missing opening YAML frontmatter delimiter")
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise FrontmatterError(f"{source}: missing closing YAML frontmatter delimiter")
    yaml_text = normalized[4:end]
    try:
        metadata = _plain_yaml(yaml.safe_load(yaml_text) or {})
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"{source}: invalid YAML: {exc}") from exc
    if not isinstance(metadata, dict):
        raise FrontmatterError(f"{source}: frontmatter must be a mapping")
    return Document(metadata=metadata, body=normalized[end + 5 :])


def parse_file(path: Path) -> Document:
    try:
        return parse_text(path.read_text(encoding="utf-8"), source=str(path))
    except UnicodeDecodeError as exc:
        raise FrontmatterError(f"{path}: not valid UTF-8") from exc


def dump_document(document: Document) -> str:
    yaml_text = yaml.safe_dump(
        document.metadata,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip()
    body = document.body.lstrip("\n")
    return f"---\n{yaml_text}\n---\n\n{body.rstrip()}\n"


def write_file(path: Path, document: Document) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_document(document), encoding="utf-8")
