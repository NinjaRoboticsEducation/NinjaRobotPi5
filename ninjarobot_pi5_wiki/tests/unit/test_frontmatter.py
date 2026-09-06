from __future__ import annotations

import pytest

from llmwiki.frontmatter import Document, FrontmatterError, dump_document, parse_text


def test_frontmatter_round_trip_preserves_unknown_fields() -> None:
    text = """---
type: CustomType
title: Example
future_field:
  enabled: true
generated:
  by: test/1
  at: 2026-08-22T00:00:00Z
---

# Example
"""
    document = parse_text(text)
    assert document.metadata["future_field"] == {"enabled": True}
    assert document.metadata["generated"]["at"] == "2026-08-22T00:00:00Z"
    reparsed = parse_text(dump_document(document))
    assert reparsed == document


def test_minimal_okf_page_is_parseable() -> None:
    assert parse_text("---\ntype: Concept\n---\n\nBody\n").metadata == {"type": "Concept"}


def test_missing_delimiter_is_rejected() -> None:
    with pytest.raises(FrontmatterError, match="opening"):
        parse_text("type: Concept\n")


def test_dump_adds_stable_trailing_newline() -> None:
    assert dump_document(Document({"type": "Concept"}, "Body")).endswith("Body\n")
