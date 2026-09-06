from __future__ import annotations

import json

import yaml
from PIL import Image
from click.testing import CliRunner

from llmwiki.cli import main

from conftest import valid_page


def test_cli_blank_state_and_source_workflow(project, monkeypatch) -> None:
    root, _ = project
    monkeypatch.chdir(root)
    runner = CliRunner()

    doctor = runner.invoke(main, ["doctor"])
    assert doctor.exit_code == 0, doctor.output
    assert json.loads(doctor.output)["bundle_exists"] is True
    assert "git_repository" in json.loads(doctor.output)

    lint = runner.invoke(main, ["lint", "--format", "json"])
    assert lint.exit_code == 0, lint.output
    assert json.loads(lint.output) == []

    source = root / "raw" / "notes" / "cli.md"
    source.write_text("# CLI source\n\nEvidence.\n", encoding="utf-8")
    added = runner.invoke(main, ["source", "add", str(source)])
    assert added.exit_code == 0, added.output
    source_id = json.loads(added.output)["source"]["id"]
    normalized = runner.invoke(main, ["source", "normalize", source_id])
    assert normalized.exit_code == 0, normalized.output
    assert source_id in normalized.output


def test_cli_plan_json_diff(project, monkeypatch) -> None:
    root, _ = project
    monkeypatch.chdir(root)
    plan = {
        "version": 1,
        "id": "cli-plan-diff",
        "created_at": "2026-08-22T00:00:00Z",
        "actor": "test-suite/1",
        "risk": "low",
        "operations": [{"op": "write", "path": "wiki/concepts/cli.md", "content": valid_page("CLI")}],
    }
    plan_path = root / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")
    result = CliRunner().invoke(main, ["plan", "diff", str(plan_path), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["id"] == "cli-plan-diff"
    assert "+# CLI" in payload["diff"]


def test_cli_image_status_doctor_and_runtime(project, monkeypatch) -> None:
    root, _ = project
    monkeypatch.chdir(root)
    runner = CliRunner()
    image = root / "raw/media/cli-image.png"
    Image.new("RGB", (12, 6), "purple").save(image)
    added = runner.invoke(main, ["source", "add", str(image)])
    assert added.exit_code == 0, added.output
    source_id = json.loads(added.output)["source"]["id"]
    normalized = runner.invoke(main, ["source", "normalize", source_id, "--ocr", "off"])
    assert normalized.exit_code == 0, normalized.output
    status = json.loads(runner.invoke(main, ["source", "status"]).output)
    assert status[0]["kind"] == "image"
    assert status[0]["ocr_status"] == "off"
    doctor = json.loads(runner.invoke(main, ["doctor"]).output)
    assert doctor["pillow"]
    assert doctor["git_reminder"]
    runtime = json.loads(runner.invoke(main, ["runtime", "status"]).output)
    assert runtime == {"write_lock": False, "staging": [], "backups": []}


def test_cli_semantic_review_prepare_and_strict_gate(project, monkeypatch) -> None:
    root, config = project
    monkeypatch.chdir(root)
    runner = CliRunner()
    page = config.bundle_root / "concepts" / "science.md"
    page.write_text(valid_page("Science").replace("status: draft", "status: stable"), encoding="utf-8")
    from llmwiki.indexes import build_indexes

    build_indexes(config.bundle_root)
    prepared = runner.invoke(main, ["review", "prepare", str(page), "--format", "json"])
    assert prepared.exit_code == 0, prepared.output
    payload = json.loads(prepared.output)
    assert payload["page"] == "wiki/concepts/science.md"
    assert payload["target_hash"].startswith("sha256:")
    assert len(payload["questions"]) == 5
    assert payload["semantic_review"]["result"] == "incomplete"

    normal = runner.invoke(main, ["lint", "--format", "json"])
    strict = runner.invoke(main, ["lint", "--strict", "--format", "json"])
    assert normal.exit_code == 0
    assert strict.exit_code == 1
    assert "semantic-review-missing" in strict.output


def test_cli_stats_reports_sourced_page_review_coverage(project, monkeypatch) -> None:
    root, config = project
    monkeypatch.chdir(root)
    source_path = root / "raw/notes/stats-source.md"
    source_path.write_text("Coverage evidence.\n", encoding="utf-8")
    from llmwiki.sources import add_source
    from llmwiki.indexes import build_indexes

    record, _ = add_source(config, source_path)
    page = config.bundle_root / "concepts/stats-page.md"
    page.write_text(
        f"""---
type: Concept
title: Stats Page
description: A sourced page used to check review coverage.
status: draft
sources:
  - id: {record["id"]}
    resource: urn:llmwiki:source:{record["id"]}
    content_hash: {record["content_hash"]}
---

# Stats Page

This page has evidence.[^{record["id"]}]

[^{record["id"]}]: Registered coverage evidence.
""",
        encoding="utf-8",
    )
    build_indexes(config.bundle_root)
    result = CliRunner().invoke(main, ["stats"])
    assert result.exit_code == 0, result.output
    semantic = json.loads(result.output)["semantic_reviews"]
    assert semantic["sourced_pages"] == 1
    assert semantic["passed_sourced_pages"] == 0
    assert semantic["remaining_sourced_pages"] == 1
    assert semantic["coverage_percent"] == 0.0
