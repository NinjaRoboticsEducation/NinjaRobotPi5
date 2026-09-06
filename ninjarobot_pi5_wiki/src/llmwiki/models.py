from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

Severity = Literal["error", "warning", "suggestion"]


@dataclass(frozen=True)
class Issue:
    severity: Severity
    code: str
    message: str
    path: str | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchResult:
    concept_id: str
    path: Path
    title: str
    description: str
    page_type: str
    status: str
    trust: str
    stale: bool
    score: int
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data
