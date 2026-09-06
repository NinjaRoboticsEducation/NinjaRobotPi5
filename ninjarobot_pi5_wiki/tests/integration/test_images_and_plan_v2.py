from __future__ import annotations

from datetime import datetime, timezone

import pytest
import yaml
from PIL import Image

from llmwiki.normalize import normalize_source
from llmwiki.paths import sha256_file
from llmwiki.plans import PlanError, plan_diff, validate_plan
from llmwiki.sources import SourceError, add_source, load_record, update_source
from llmwiki.transactions import apply_plan, prune_runtime
from llmwiki import transactions


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_image_registration_and_metadata_only_normalization(project) -> None:
    root, config = project
    path = root / "raw/media/ui-guide.png"
    Image.new("RGB", (64, 32), "navy").save(path)

    record, created = add_source(config, path, original_uri="urn:example:ui-guide")
    assert created
    assert record["kind"] == "image"
    assert record["image"]["format"] == "PNG"
    assert record["image"]["width"] == 64

    content = normalize_source(config, record["id"], ocr="off")
    assert "No OCR text is available (status: off)" in content.read_text(encoding="utf-8")
    manifest = yaml.safe_load((content.parent / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["source_hash"] == record["content_hash"]
    assert manifest["ocr"]["status"] == "off"
    assert (content.parent / "rendition.png").is_file()
    assert load_record(config, record["id"])["image"]["ocr_status"] == "off"


def test_image_extension_and_dimension_limits_are_enforced(project) -> None:
    root, config = project
    disguised = root / "raw/media/disguised.jpg"
    Image.new("RGB", (8, 8), "white").save(disguised, format="PNG")
    with pytest.raises(SourceError, match="extension says JPEG"):
        add_source(config, disguised)

    too_wide = root / "raw/media/too-wide.png"
    Image.new("1", (config.max_image_width + 1, 1)).save(too_wide)
    with pytest.raises(SourceError, match="dimensions"):
        add_source(config, too_wide)


def test_ocr_auto_warns_and_required_fails_when_tesseract_is_absent(project, monkeypatch) -> None:
    root, config = project
    image_path = root / "raw/media/no-ocr.png"
    Image.new("RGB", (16, 8), "white").save(image_path)
    record, _ = add_source(config, image_path)
    monkeypatch.setattr("llmwiki.normalize.shutil.which", lambda _name: None)

    content = normalize_source(config, record["id"], ocr="auto")
    manifest = yaml.safe_load((content.parent / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["ocr"]["status"] == "unavailable"

    with pytest.raises(SourceError, match="required but is not installed"):
        normalize_source(config, record["id"], ocr="required")


def test_safe_source_metadata_update_preserves_identity(project) -> None:
    root, config = project
    path = root / "raw/notes/versioned.md"
    path.write_text("Evidence.", encoding="utf-8")
    record, _ = add_source(config, path)
    updated = update_source(
        config,
        record["id"],
        title="Readable Evidence",
        original_uri="https://github.com/example/repo/blob/abc123/docs/versioned.md",
        source_version="abc123",
    )
    assert updated["id"] == record["id"]
    assert updated["content_hash"] == record["content_hash"]
    assert updated["source_version"] == "abc123"


def test_plan_v2_checks_every_source_and_rejects_noop(project) -> None:
    root, config = project
    records = []
    for name in ("one", "two"):
        path = root / f"raw/notes/{name}.md"
        path.write_text(f"{name} evidence", encoding="utf-8")
        records.append(add_source(config, path)[0])
    plan = {
        "version": 2,
        "id": "multi-source-version-check",
        "created_at": _now(),
        "actor": "test-suite/2",
        "risk": "low",
        "sources": [{"id": item["id"], "content_hash": item["content_hash"]} for item in records],
        "operations": [
            {
                "op": "write",
                "path": "wiki/concepts/multi.md",
                "content": """---
type: Concept
title: Multi
description: Multi-source evidence.
status: stable
sources:
  - id: %s
    resource: /references/one.md
    content_hash: %s
  - id: %s
    resource: /references/two.md
    content_hash: %s
---

# Multi

Evidence one.[^%s]

Evidence two.[^%s]

[^%s]: One.
[^%s]: Two.
""" % (
                    records[0]["id"], records[0]["content_hash"], records[1]["id"], records[1]["content_hash"],
                    records[0]["id"], records[1]["id"], records[0]["id"], records[1]["id"],
                ),
            }
        ],
    }
    validate_plan(config, plan)
    (root / records[1]["path"]).write_text("changed", encoding="utf-8")
    with pytest.raises(PlanError, match="changed after creation"):
        validate_plan(config, plan)

    overview = config.bundle_root / "overview.md"
    no_op = {
        "version": 2,
        "id": "reject-identical-write",
        "created_at": _now(),
        "actor": "test-suite/2",
        "risk": "low",
        "operations": [{
            "op": "write",
            "path": "wiki/overview.md",
            "content": overview.read_text(encoding="utf-8"),
            "expected_sha256": sha256_file(overview),
        }],
    }
    with pytest.raises(PlanError, match="No-op write"):
        validate_plan(config, no_op)


def test_image_reference_and_asset_apply_as_one_transaction(project) -> None:
    root, config = project
    image_path = root / "raw/media/layout.png"
    Image.new("RGB", (40, 20), "teal").save(image_path)
    record, _ = add_source(config, image_path, original_uri="urn:llmwiki:source:layout")
    normalize_source(config, record["id"], ocr="off")
    rendition = config.derived_root / record["id"] / "rendition.png"
    target = f"wiki/assets/sources/{record['id']}.png"
    page = f"""---
type: Reference
title: Layout Image
description: A visual reference used by the test suite.
resource: urn:llmwiki:source:{record['id']}
status: stable
generated:
  by: test-suite/2
  at: 2026-08-22T00:00:00Z
sources:
  - id: {record['id']}
    resource: urn:llmwiki:source:{record['id']}
    title: Layout Image
    content_hash: {record['content_hash']}
---

# Layout Image

The image is a small synthetic layout fixture.[^{record['id']}]

![Synthetic teal layout](/assets/sources/{record['id']}.png)

[^{record['id']}]: Registered image source `{record['id']}`.
"""
    plan = {
        "version": 2,
        "id": "publish-reviewed-image",
        "created_at": _now(),
        "actor": "test-suite/2",
        "risk": "medium",
        "sources": [{"id": record["id"], "content_hash": record["content_hash"]}],
        "operations": [
            {"op": "write", "path": "wiki/references/layout-image.md", "content": page},
            {
                "op": "copy_asset",
                "path": target,
                "from": rendition.relative_to(root).as_posix(),
                "source_id": record["id"],
                "expected_sha256": sha256_file(rendition),
            },
        ],
    }
    assert "Binary asset" in plan_diff(config, plan)
    backup = apply_plan(config, plan, approved=True)
    assert (root / target).is_file()
    assert (backup / "wiki").is_dir()
    assert not (root / ".llmwiki/staging/publish-reviewed-image").exists()
    applied_record = load_record(config, record["id"])
    assert applied_record["state"] == "ingested"
    assert applied_record["image"]["asset_status"] == "published"


def test_catalog_and_wiki_roll_back_together(project, monkeypatch) -> None:
    root, config = project
    source_path = root / "raw/notes/rollback.md"
    source_path.write_text("Rollback evidence.", encoding="utf-8")
    record, _ = add_source(config, source_path)
    page = f"""---
type: Concept
title: Rollback
description: Transaction rollback evidence.
status: stable
sources:
  - id: {record['id']}
    resource: urn:llmwiki:source:{record['id']}
    content_hash: {record['content_hash']}
---

# Rollback

This page uses the rollback fixture.[^{record['id']}]

[^{record['id']}]: Registered rollback source.
"""
    plan = {
        "version": 2,
        "id": "catalog-rollback-together",
        "created_at": _now(),
        "actor": "test-suite/2",
        "risk": "low",
        "sources": [{"id": record["id"], "content_hash": record["content_hash"]}],
        "operations": [{"op": "write", "path": "wiki/concepts/rollback.md", "content": page}],
    }
    real_replace = transactions.os.replace
    calls = 0

    def fail_catalog_install(source, target):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("injected catalog install failure")
        return real_replace(source, target)

    monkeypatch.setattr(transactions.os, "replace", fail_catalog_install)
    with pytest.raises(OSError, match="catalog install"):
        apply_plan(config, plan, approved=True)
    assert not (config.bundle_root / "concepts/rollback.md").exists()
    assert load_record(config, record["id"])["state"] == "pending"


def test_runtime_pruning_is_previewed_and_requires_approval(project) -> None:
    root, config = project
    backup_root = root / ".llmwiki/backups"
    for name in ("older", "newer"):
        directory = backup_root / name
        directory.mkdir(parents=True)
        (directory / "marker").write_text(name, encoding="utf-8")
    preview = prune_runtime(config, keep=1, approved=False, dry_run=True)
    assert len(preview) == 1
    with pytest.raises(PlanError, match="explicit approval"):
        prune_runtime(config, keep=1, approved=False, dry_run=False)
    removed = prune_runtime(config, keep=1, approved=True, dry_run=False)
    assert removed == preview
