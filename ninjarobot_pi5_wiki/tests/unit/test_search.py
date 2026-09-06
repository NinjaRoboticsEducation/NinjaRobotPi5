from __future__ import annotations

from llmwiki.search import search_bundle

from conftest import valid_page


def test_search_returns_structured_ranked_results(project) -> None:
    _, config = project
    strong = config.bundle_root / "concepts" / "robotics.md"
    weak = config.bundle_root / "concepts" / "other.md"
    strong.write_text(valid_page("Robotics", "Robotics combines sensing, planning, and control."), encoding="utf-8")
    weak.write_text(valid_page("Other", "A passing mention of robotics."), encoding="utf-8")
    results = search_bundle(config.bundle_root, "robotics", limit=5)
    assert results[0].concept_id == "concepts/robotics"
    assert results[0].status == "draft"
    assert results[0].trust == "unverified"


def test_search_uses_exact_terms_and_rejects_partial_topic_matches(project) -> None:
    _, config = project
    relevant = config.bundle_root / "concepts" / "blockly.md"
    false_positive = config.bundle_root / "references" / "licenses.md"
    substring = config.bundle_root / "concepts" / "provide.md"
    relevant.write_text(valid_page("Blockly Runtime", "Blockly code generates Python."), encoding="utf-8")
    false_positive.write_text(valid_page("Licenses", "Third-party source code notices."), encoding="utf-8")
    substring.write_text(valid_page("Provider", "This page provides unrelated material."), encoding="utf-8")

    results = search_bundle(config.bundle_root, "Please explain Blockly code", limit=10)
    assert [result.concept_id for result in results] == ["concepts/blockly"], [
        (result.concept_id, result.score, result.excerpt) for result in results
    ]
    assert search_bundle(config.bundle_root, "IDE", limit=10) == []


def test_search_uses_explicit_engineering_term_equivalences(project) -> None:
    _, config = project
    wiring = config.bundle_root / "references" / "wiring.md"
    wiring.write_text(
        valid_page(
            "Hardware Wiring Reference",
            "Hardware components are documented in the complete pinout connection table.",
        ),
        encoding="utf-8",
    )

    results = search_bundle(config.bundle_root, "electronic modules wiring diagram", limit=10)
    assert results[0].concept_id == "references/wiring"
