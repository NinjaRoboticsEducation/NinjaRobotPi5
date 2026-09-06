from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .frontmatter import FrontmatterError, parse_file
from .lint import is_stale, trust_tier
from .models import SearchResult
from .paths import concept_id, iter_markdown


TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "do", "does",
    "explain", "for", "from", "how", "i", "in", "is", "it", "me", "of", "on", "or",
    "please", "show", "that", "the", "this", "to", "use", "using", "via", "what", "when",
    "where", "which", "with", "work", "works", "would", "you",
})
TERM_EQUIVALENCE_GROUPS = (
    frozenset({"electronic", "electronics", "electrical", "hardware", "component", "components"}),
    frozenset({"module", "modules", "component", "components", "subsystem", "subsystems"}),
    frozenset({"diagram", "diagrams", "schematic", "schematics", "pinout", "pinouts", "table", "tables"}),
    frozenset({"wire", "wires", "wired", "wiring", "connection", "connections"}),
    frozenset({"connect", "connects", "connected", "connecting", "connection", "connections", "connectivity"}),
)


def _tokens(value: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(value.lower()) if len(token) > 1]


def _search_terms(value: str) -> list[str]:
    tokens = list(dict.fromkeys(_tokens(value)))
    meaningful = [token for token in tokens if token not in STOP_WORDS]
    return meaningful or tokens


def _term_variants(term: str) -> frozenset[str]:
    variants = {term}
    for group in TERM_EQUIVALENCE_GROUPS:
        if term in group:
            variants.update(group)
    return frozenset(variants)


def _term_matches(term: str, tokens: set[str]) -> bool:
    return not _term_variants(term).isdisjoint(tokens)


def _term_count(term: str, counts: Counter[str]) -> int:
    return sum(counts[variant] for variant in _term_variants(term))


def _required_matches(term_count: int) -> int:
    if term_count <= 2:
        return term_count
    return max(2, (term_count + 1) // 2)


def search_bundle(bundle_root: Path, query: str, *, limit: int = 20) -> list[SearchResult]:
    terms = _search_terms(query)
    if not terms:
        return []
    results: list[SearchResult] = []
    for path in iter_markdown(bundle_root):
        try:
            document = parse_file(path)
        except FrontmatterError:
            continue
        metadata = document.metadata
        title = str(metadata.get("title") or path.stem)
        description = str(metadata.get("description") or "")
        tags = " ".join(str(tag) for tag in metadata.get("tags", []))
        fields = {
            "title": title,
            "description": description,
            "tags": tags,
            "body": document.body,
        }
        counts = {name: Counter(_tokens(value)) for name, value in fields.items()}
        combined_tokens = set().union(*(set(field) for field in counts.values()))
        matched = [term for term in terms if _term_matches(term, combined_tokens)]
        if len(matched) < _required_matches(len(terms)):
            continue
        score = sum(
            _term_count(term, counts["title"]) * 8
            + _term_count(term, counts["description"]) * 4
            + _term_count(term, counts["tags"]) * 5
            + _term_count(term, counts["body"])
            for term in terms
        )
        phrase = " ".join(terms)
        normalized_fields = "\n".join(" ".join(_tokens(value)) for value in fields.values())
        if phrase and phrase in normalized_fields:
            score += 20
        if len(matched) == len(terms):
            score += 10
        score += len(matched) * 3
        lines = [line.strip() for line in document.body.splitlines() if line.strip() and not line.startswith("#")]
        excerpt = next(
            (line for line in lines if any(_term_matches(term, set(_tokens(line))) for term in terms)),
            description,
        )
        results.append(
            SearchResult(
                concept_id=concept_id(path, bundle_root),
                path=path,
                title=title,
                description=description,
                page_type=str(metadata.get("type", "")),
                status=str(metadata.get("status", "stable")),
                trust=trust_tier(metadata),
                stale=is_stale(metadata),
                score=score,
                excerpt=excerpt[:240],
            )
        )
    return sorted(results, key=lambda item: (-item.score, item.concept_id))[:limit]
