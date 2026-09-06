from __future__ import annotations

from llmwiki.indexes import build_indexes
from llmwiki.lint import lint_project
from llmwiki.sources import add_source

from conftest import valid_page


def test_blank_template_has_no_lint_errors(project) -> None:
    _, config = project
    assert not [issue for issue in lint_project(config) if issue.severity == "error"]


def test_lint_finds_broken_link_wikilink_and_secret(project) -> None:
    _, config = project
    page = config.bundle_root / "concepts" / "unsafe.md"
    page.write_text(
        valid_page("Unsafe", "See [missing](missing.md) and [[legacy]].\n\napi_key = 'abcdefghijklmnop'"),
        encoding="utf-8",
    )
    build_indexes(config.bundle_root)
    codes = {issue.code for issue in lint_project(config)}
    assert {"broken-link", "wikilink", "possible-secret"} <= codes


def test_index_build_is_idempotent(project) -> None:
    _, config = project
    (config.bundle_root / "concepts" / "alpha.md").write_text(valid_page("Alpha"), encoding="utf-8")
    assert build_indexes(config.bundle_root)
    assert build_indexes(config.bundle_root) == []


def test_minimal_okf_page_is_valid_with_local_profile_warnings(project) -> None:
    _, config = project
    page = config.bundle_root / "concepts" / "minimal.md"
    page.write_text("---\ntype: FutureType\n---\n\n# Minimal\n", encoding="utf-8")
    build_indexes(config.bundle_root)
    page_issues = [issue for issue in lint_project(config) if issue.path == "wiki/concepts/minimal.md"]
    assert not [issue for issue in page_issues if issue.severity == "error"]
    assert {issue.code for issue in page_issues} >= {"profile-field", "unknown-type"}


def test_stable_unverified_is_valid_but_source_versions_are_strict(project) -> None:
    root, config = project
    source_path = root / "raw/notes/evidence.md"
    source_path.write_text("Version one.", encoding="utf-8")
    record, _ = add_source(config, source_path)
    page = config.bundle_root / "concepts/versioned.md"
    page.write_text(
        f"""---
type: Concept
title: Versioned
description: A stable but unverified page.
status: stable
sources:
  - id: {record['id']}
    resource: urn:llmwiki:source:{record['id']}
    content_hash: {record['content_hash']}
---

# Versioned

The local evidence contains version one.[^{record['id']}]

[^{record['id']}]: Registered source.
""",
        encoding="utf-8",
    )
    build_indexes(config.bundle_root)
    codes = {issue.code for issue in lint_project(config)}
    assert "stable-unverified" not in codes
    assert "source-version-mismatch" not in codes

    source_path.write_text("Version two.", encoding="utf-8")
    add_source(config, source_path)
    issues = lint_project(config)
    mismatch = [issue for issue in issues if issue.code == "source-version-mismatch"]
    assert mismatch and mismatch[0].severity == "error"
