from __future__ import annotations

from datetime import datetime, timezone

import pytest

from llmwiki import transactions
from llmwiki.paths import sha256_file
from llmwiki.plans import PlanError, plan_diff, validate_plan
from llmwiki.transactions import apply_plan

from conftest import valid_page


def make_plan(plan_id: str = "test-create-page") -> dict:
    return {
        "version": 1,
        "id": plan_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actor": "test-suite/1",
        "risk": "low",
        "summary": "Create one test page",
        "operations": [
            {
                "op": "write",
                "path": "wiki/concepts/planned.md",
                "content": valid_page("Planned"),
            }
        ],
    }


def test_plan_validate_diff_and_apply_transaction(project) -> None:
    _, config = project
    plan = make_plan()
    assert validate_plan(config, plan) == ["write: wiki/concepts/planned.md"]
    assert "+# Planned" in plan_diff(config, plan)
    with pytest.raises(PlanError, match="explicit approval"):
        apply_plan(config, plan, approved=False)
    backup = apply_plan(config, plan, approved=True)
    assert (config.bundle_root / "concepts" / "planned.md").is_file()
    assert backup.is_dir()
    assert "test-create-page" in (config.bundle_root / "log.md").read_text(encoding="utf-8")


def test_stale_target_hash_is_rejected(project) -> None:
    _, config = project
    target = config.bundle_root / "overview.md"
    plan = make_plan("test-stale-target")
    plan["operations"][0] = {
        "op": "write",
        "path": "wiki/overview.md",
        "content": valid_page("Changed Overview"),
        "expected_sha256": sha256_file(target),
    }
    target.write_text(valid_page("Someone Else Changed It"), encoding="utf-8")
    with pytest.raises(PlanError, match="Stale plan"):
        validate_plan(config, plan)


def test_path_escape_is_rejected(project) -> None:
    _, config = project
    plan = make_plan("test-path-escape")
    plan["operations"][0]["path"] = "wiki/../../outside.md"
    with pytest.raises(PlanError, match="escapes"):
        validate_plan(config, plan)


def test_delete_requires_a_reviewed_hash(project) -> None:
    _, config = project
    page = config.bundle_root / "concepts" / "temporary.md"
    page.write_text(valid_page("Temporary"), encoding="utf-8")
    plan = make_plan("test-delete-hash")
    plan["risk"] = "high"
    plan["operations"] = [{"op": "delete", "path": "wiki/concepts/temporary.md"}]
    with pytest.raises(PlanError, match="requires expected_sha256"):
        validate_plan(config, plan)


def test_failed_atomic_swap_restores_original_bundle(project, monkeypatch) -> None:
    _, config = project
    original = (config.bundle_root / "overview.md").read_bytes()
    real_replace = transactions.os.replace
    calls = 0

    def fail_second_replace(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected swap failure")
        return real_replace(source, target)

    monkeypatch.setattr(transactions.os, "replace", fail_second_replace)
    with pytest.raises(OSError, match="injected"):
        apply_plan(config, make_plan("test-rollback"), approved=True)
    assert (config.bundle_root / "overview.md").read_bytes() == original
    assert not (config.bundle_root / "concepts" / "planned.md").exists()


def test_unrelated_edit_during_staging_is_not_overwritten(project, monkeypatch) -> None:
    _, config = project
    real_lint = transactions.lint_bundle

    def edit_live_wiki_then_lint(bundle_root, loaded_config, **kwargs):
        live_page = loaded_config.bundle_root / "overview.md"
        live_page.write_text(valid_page("Manual Concurrent Edit"), encoding="utf-8")
        return real_lint(bundle_root, loaded_config, **kwargs)

    monkeypatch.setattr(transactions, "lint_bundle", edit_live_wiki_then_lint)
    with pytest.raises(PlanError, match="changed while"):
        apply_plan(config, make_plan("test-concurrent-edit"), approved=True)
    assert "Manual Concurrent Edit" in (config.bundle_root / "overview.md").read_text(encoding="utf-8")
    assert not (config.bundle_root / "concepts" / "planned.md").exists()


def test_move_and_inbound_link_update_apply_together(project) -> None:
    _, config = project
    old = config.bundle_root / "concepts" / "old-name.md"
    inbound = config.bundle_root / "concepts" / "reader.md"
    old.write_text(valid_page("Old Name"), encoding="utf-8")
    inbound.write_text(valid_page("Reader", "See [Old Name](old-name.md)."), encoding="utf-8")
    plan = {
        "version": 1,
        "id": "test-safe-rename",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actor": "test-suite/1",
        "risk": "medium",
        "summary": "Rename a concept and update its incoming link",
        "operations": [
            {
                "op": "move",
                "from": "wiki/concepts/old-name.md",
                "path": "wiki/concepts/new-name.md",
                "expected_sha256": sha256_file(old),
            },
            {
                "op": "write",
                "path": "wiki/concepts/reader.md",
                "content": valid_page("Reader", "See [New Name](new-name.md)."),
                "expected_sha256": sha256_file(inbound),
            },
        ],
    }
    apply_plan(config, plan, approved=True)
    assert not old.exists()
    assert (config.bundle_root / "concepts" / "new-name.md").exists()
    assert "new-name.md" in inbound.read_text(encoding="utf-8")
