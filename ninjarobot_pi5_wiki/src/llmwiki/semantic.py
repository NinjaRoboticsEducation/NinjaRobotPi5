from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .frontmatter import Document


SEMANTIC_FIELDS = ("type", "title", "description", "resource", "tags", "status", "sources")
ABSOLUTE_CLAIM_RE = re.compile(
    r"\b(?:always|never|guarantee(?:d|s)?|cannot|completely|exclusively|proven|safe|secure|all)\b",
    re.IGNORECASE,
)


def semantic_target_hash(document: Document) -> str:
    """Hash meaning-bearing page content without hashing the review itself."""
    metadata = {
        key: document.metadata[key]
        for key in SEMANTIC_FIELDS
        if key in document.metadata
    }
    payload = {
        "metadata": metadata,
        "body": document.body.replace("\r\n", "\n").strip() + "\n",
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def semantic_review_state(document: Document) -> str:
    """Return the page-level semantic review state used by lint and statistics."""
    review = document.metadata.get("semantic_review")
    if not isinstance(review, dict):
        return "missing"
    if review.get("target_hash") != semantic_target_hash(document):
        return "stale"
    result = str(review.get("result", "incomplete"))
    return result if result in {"passed", "concerns", "incomplete"} else "incomplete"


def has_absolute_claims(body: str) -> bool:
    return bool(ABSOLUTE_CLAIM_RE.search(body))


def review_template(document: Document) -> dict[str, Any]:
    """Return a neutral review skeleton; the reviewer must fill in honest results."""
    return {
        "semantic_review": {
            "version": 1,
            "performed_by": "agent:replace-with-tool-name",
            "performed_at": "replace-with-current-ISO-8601-time",
            "target_hash": semantic_target_hash(document),
            "result": "incomplete",
            "checks": {
                "source_support": "concern",
                "contradictions": "concern",
                "limitations": "concern",
                "claim_strength": "concern",
                "visual_evidence": "not_applicable",
            },
            "notes": [],
        }
    }
