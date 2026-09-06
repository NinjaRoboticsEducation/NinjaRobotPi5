from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.links import anchors, extract_links, resolve_link
from llmwiki.paths import UnsafePathError, concept_id, safe_project_path


def test_concept_id_uses_full_bundle_path(tmp_path: Path) -> None:
    bundle = tmp_path / "wiki"
    page = bundle / "concepts" / "example.md"
    page.parent.mkdir(parents=True)
    page.touch()
    assert concept_id(page, bundle) == "concepts/example"


def test_safe_path_rejects_traversal(tmp_path: Path) -> None:
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    with pytest.raises(UnsafePathError):
        safe_project_path(tmp_path, "wiki/../../outside.md", bundle)


def test_links_resolve_from_bundle_root(tmp_path: Path) -> None:
    bundle = tmp_path / "wiki"
    source = bundle / "concepts" / "a.md"
    source.parent.mkdir(parents=True)
    target, anchor = resolve_link(source, "/entities/b.md#Details", bundle)
    assert target == bundle / "entities" / "b.md"
    assert anchor == "Details"


def test_markdown_parser_and_unicode_anchors() -> None:
    links = extract_links("See [the page](../page.md#part).")
    assert links[0].target == "../page.md#part"
    assert "日本語-heading" in anchors("# 日本語 Heading\n")
