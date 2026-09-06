from __future__ import annotations

from PIL import Image

from llmwiki.frontmatter import dump_document, parse_file
from llmwiki.indexes import build_indexes
from llmwiki.lint import lint_project
from llmwiki.semantic import semantic_target_hash
from llmwiki.sources import add_source

from conftest import valid_page


CHECKS = {
    "source_support": "passed",
    "contradictions": "passed",
    "limitations": "passed",
    "claim_strength": "passed",
    "visual_evidence": "not_applicable",
}


def _add_review(path, *, result="passed", checks=None) -> None:
    document = parse_file(path)
    document.metadata["semantic_review"] = {
        "version": 1,
        "performed_by": "agent:test",
        "performed_at": "2026-08-22T00:00:00Z",
        "target_hash": semantic_target_hash(document),
        "result": result,
        "checks": checks or CHECKS,
        "notes": [],
    }
    path.write_text(dump_document(document), encoding="utf-8")


def test_normal_lint_warns_and_strict_lint_gates_stable_pages(project) -> None:
    _, config = project
    page = config.bundle_root / "concepts/semantic.md"
    page.write_text(valid_page("Semantic").replace("status: draft", "status: stable"), encoding="utf-8")
    build_indexes(config.bundle_root)

    normal = [issue for issue in lint_project(config) if issue.code == "semantic-review-missing"]
    strict = [issue for issue in lint_project(config, strict=True) if issue.code == "semantic-review-missing"]
    assert normal and normal[0].severity == "warning"
    assert strict and strict[0].severity == "error"

    _add_review(page)
    assert not [issue for issue in lint_project(config, strict=True) if issue.code.startswith("semantic-")]

    document = parse_file(page)
    document.body += "\nA changed conclusion.\n"
    page.write_text(dump_document(document), encoding="utf-8")
    stale = [issue for issue in lint_project(config, strict=True) if issue.code == "semantic-review-stale"]
    assert stale and stale[0].severity == "error"


def test_source_free_draft_page_does_not_require_semantic_review(project) -> None:
    root, config = project
    page = config.bundle_root / "concepts/history.md"
    page.write_text(valid_page("History", "A provisional historical note."), encoding="utf-8")
    build_indexes(config.bundle_root)
    assert not [issue for issue in lint_project(config, strict=True) if issue.path == "wiki/concepts/history.md" and issue.code.startswith("semantic-")]


def test_absolute_language_stays_a_nonblocking_cue_on_source_free_drafts(project) -> None:
    _, config = project
    page = config.bundle_root / "concepts/absolute-draft.md"
    page.write_text(valid_page("Absolute Draft", "This provisional rule always applies."), encoding="utf-8")
    build_indexes(config.bundle_root)

    normal = [issue for issue in lint_project(config) if issue.path == "wiki/concepts/absolute-draft.md"]
    strict = [issue for issue in lint_project(config, strict=True) if issue.path == "wiki/concepts/absolute-draft.md"]
    assert any(issue.code == "absolute-claim-review" and issue.severity == "suggestion" for issue in normal)
    assert any(issue.code == "absolute-claim-review" and issue.severity == "suggestion" for issue in strict)
    assert not any(issue.code == "semantic-review-missing" for issue in strict)


def test_sourced_draft_warns_normally_and_is_gated_strictly(project) -> None:
    root, config = project
    source_path = root / "raw/notes/sourced-draft.md"
    source_path.write_text("Evidence for a draft.\n", encoding="utf-8")
    record, _ = add_source(config, source_path)
    page = config.bundle_root / "concepts/sourced-draft.md"
    page.write_text(
        f"""---
type: Concept
title: Sourced Draft
description: A draft backed by a registered source.
status: draft
sources:
  - id: {record["id"]}
    resource: urn:llmwiki:source:{record["id"]}
    content_hash: {record["content_hash"]}
---

# Sourced Draft

This draft has registered evidence.[^{record["id"]}]

[^{record["id"]}]: Registered draft evidence.
""",
        encoding="utf-8",
    )
    build_indexes(config.bundle_root)

    normal = [issue for issue in lint_project(config) if issue.path == "wiki/concepts/sourced-draft.md"]
    strict = [issue for issue in lint_project(config, strict=True) if issue.path == "wiki/concepts/sourced-draft.md"]
    assert any(issue.code == "semantic-review-missing" and issue.severity == "warning" for issue in normal)
    assert any(issue.code == "semantic-review-missing" and issue.severity == "error" for issue in strict)


def test_image_evidence_requires_an_actual_visual_review(project) -> None:
    root, config = project
    image_path = root / "raw/media/design.png"
    Image.new("RGB", (16, 8), "blue").save(image_path)
    record, _ = add_source(config, image_path)
    page = config.bundle_root / "references/design.md"
    page.write_text(
        f'''---
type: Reference
title: Design Image
description: A visual design reference.
status: draft
sources:
  - id: {record["id"]}
    resource: urn:llmwiki:source:{record["id"]}
    content_hash: {record["content_hash"]}
---

# Design Image

The image provides visual evidence.[^{record["id"]}]

[^{record["id"]}]: Registered image source.
''',
        encoding="utf-8",
    )
    build_indexes(config.bundle_root)
    normal = [issue for issue in lint_project(config) if issue.path == "wiki/references/design.md"]
    strict = [issue for issue in lint_project(config, strict=True) if issue.path == "wiki/references/design.md"]
    assert any(issue.code == "visual-review-missing" and issue.severity == "warning" for issue in normal)
    assert any(issue.code == "semantic-review-missing" and issue.severity == "warning" for issue in normal)
    assert any(issue.code == "visual-review-missing" and issue.severity == "error" for issue in strict)
    assert any(issue.code == "semantic-review-missing" and issue.severity == "error" for issue in strict)
