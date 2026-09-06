from __future__ import annotations

import pytest

from llmwiki.frontmatter import Document
from llmwiki.semantic import has_absolute_claims, semantic_review_state, semantic_target_hash


@pytest.mark.parametrize(
    "title, body",
    [
        ("Software", "The library exposes a documented interface."),
        ("History", "The archive records an event in 1912."),
        ("Science", "The experiment reports a measured result."),
        ("Product", "The specification lists a two-year warranty."),
    ],
)
def test_semantic_hash_is_topic_neutral_and_deterministic(title: str, body: str) -> None:
    document = Document(
        metadata={"type": "Concept", "title": title, "description": "Evidence summary.", "status": "stable"},
        body=body,
    )
    assert semantic_target_hash(document) == semantic_target_hash(document)
    assert semantic_target_hash(document).startswith("sha256:")


def test_review_hash_ignores_review_and_verification_but_detects_meaning_changes() -> None:
    document = Document(
        metadata={
            "type": "Concept",
            "title": "Example",
            "description": "Evidence summary.",
            "status": "stable",
            "sources": [{
                "id": "src-example",
                "resource": "urn:llmwiki:source:src-example",
                "content_hash": "sha256:" + "a" * 64,
            }],
        },
        body="A supported claim.\n",
    )
    target = semantic_target_hash(document)
    document.metadata["semantic_review"] = {
        "version": 1,
        "performed_by": "agent:test",
        "performed_at": "2026-08-22T00:00:00Z",
        "target_hash": target,
        "result": "passed",
        "checks": {
            "source_support": "passed",
            "contradictions": "passed",
            "limitations": "passed",
            "claim_strength": "passed",
            "visual_evidence": "not_applicable",
        },
    }
    document.metadata["verified"] = {"by": "agent:test", "at": "2026-08-22T01:00:00Z"}
    assert semantic_target_hash(document) == target
    assert semantic_review_state(document) == "passed"

    document.metadata["sources"][0]["content_hash"] = "sha256:" + "b" * 64
    assert semantic_review_state(document) == "stale"
    document.metadata["sources"][0]["content_hash"] = "sha256:" + "a" * 64

    document.body = "A materially changed claim.\n"
    assert semantic_review_state(document) == "stale"


def test_absolute_language_is_only_a_review_cue() -> None:
    assert has_absolute_claims("This method always succeeds.")
    assert not has_absolute_claims("This method succeeded in the documented example.")
