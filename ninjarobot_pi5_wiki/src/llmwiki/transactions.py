from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config
from .indexes import build_indexes
from .lint import lint_bundle
from .locks import ProjectLock
from .paths import safe_project_path, sha256_tree
from .plans import PlanError, source_refs, validate_plan
from .sources import load_record, save_record_to_catalog


def _staged_path(stage_root: Path, config: Config, project_path: str) -> Path:
    target = safe_project_path(config.root, project_path, config.bundle_root)
    return stage_root / "wiki" / target.relative_to(config.bundle_root)


def _append_log(bundle_root: Path, plan: dict[str, Any]) -> None:
    path = bundle_root / "log.md"
    today = datetime.now(timezone.utc).date().isoformat()
    source_ids = [item["id"] for item in source_refs(plan)]
    source_note = f" Sources: {', '.join(f'`{item}`' for item in source_ids)}." if source_ids else ""
    assets = sum(operation["op"] == "copy_asset" for operation in plan["operations"])
    asset_note = f" Assets: {assets}." if assets else ""
    entry = (
        f"* **Update**: Applied plan `{plan['id']}` — {plan.get('summary') or 'wiki changes'}."
        f"{source_note}{asset_note}"
    )
    current = path.read_text(encoding="utf-8") if path.exists() else "# Wiki Update Log\n"
    heading = f"## {today}"
    if heading in current:
        current = current.replace(heading, f"{heading}\n\n{entry}", 1)
    else:
        header, _, rest = current.partition("\n")
        current = f"{header}\n\n{heading}\n\n{entry}\n"
        if rest.strip():
            current += "\n" + rest.lstrip()
    path.write_text(current.rstrip() + "\n", encoding="utf-8")


def _mark_sources_ingested(config: Config, plan: dict[str, Any], staged_catalog: Path) -> None:
    copied_asset_ids = {
        operation["source_id"] for operation in plan["operations"] if operation["op"] == "copy_asset"
    }
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for source_ref in source_refs(plan):
        record = load_record(config, source_ref["id"])
        record["state"] = "ingested"
        record["ingested_at"] = timestamp
        record["last_plan"] = plan["id"]
        if record["id"] in copied_asset_ids:
            image = dict(record.get("image") or {})
            image["asset_status"] = "published"
            record["image"] = image
        save_record_to_catalog(config, record, staged_catalog)


def _restore_after_failed_swap(config: Config, stage: Path, backup: Path) -> None:
    if config.bundle_root.exists() and (backup / "wiki").exists():
        os.replace(config.bundle_root, stage / "failed-wiki")
    if (backup / "wiki").exists():
        os.replace(backup / "wiki", config.bundle_root)
    if config.catalog_root.exists() and (backup / "catalog").exists():
        os.replace(config.catalog_root, stage / "failed-catalog")
    if (backup / "catalog").exists():
        os.replace(backup / "catalog", config.catalog_root)


def apply_plan(config: Config, plan: dict[str, Any], *, approved: bool) -> Path:
    if not approved:
        raise PlanError("Applying a plan requires explicit approval")
    state_root = config.root / ".llmwiki"
    stage = state_root / "staging" / plan["id"]
    backup = state_root / "backups" / plan["id"]
    with ProjectLock(config.root):
        validate_plan(config, plan, check_hashes=True)
        if stage.exists() or backup.exists():
            raise PlanError(f"Runtime state already exists for plan {plan['id']}; inspect it before retrying")
        baseline_wiki_hash = sha256_tree(config.bundle_root)
        baseline_catalog_hash = sha256_tree(config.catalog_root)
        stage.mkdir(parents=True)
        shutil.copytree(config.bundle_root, stage / "wiki")
        shutil.copytree(config.catalog_root, stage / "catalog")

        for operation in plan["operations"]:
            target = _staged_path(stage, config, operation["path"])
            if operation["op"] == "write":
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(operation["content"].rstrip() + "\n", encoding="utf-8")
            elif operation["op"] == "move":
                source = _staged_path(stage, config, operation["from"])
                target.parent.mkdir(parents=True, exist_ok=True)
                source.replace(target)
            elif operation["op"] == "delete":
                target.unlink()
            elif operation["op"] == "copy_asset":
                source = safe_project_path(config.root, operation["from"], config.derived_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

        build_indexes(stage / "wiki")
        _append_log(stage / "wiki", plan)
        errors = [
            issue
            for issue in lint_bundle(stage / "wiki", config, include_index_check=True)
            if issue.severity == "error"
        ]
        if errors:
            detail = "; ".join(f"{issue.path or ''}: {issue.message}" for issue in errors)
            raise PlanError(f"Staged bundle failed validation: {detail}")

        validate_plan(config, plan, check_hashes=True)
        if sha256_tree(config.bundle_root) != baseline_wiki_hash:
            raise PlanError("The wiki changed while the plan was staged; create a fresh plan")
        if sha256_tree(config.catalog_root) != baseline_catalog_hash:
            raise PlanError("The source catalog changed while the plan was staged; create a fresh plan")
        _mark_sources_ingested(config, plan, stage / "catalog")

        backup.mkdir(parents=True)
        try:
            os.replace(config.bundle_root, backup / "wiki")
            os.replace(config.catalog_root, backup / "catalog")
            os.replace(stage / "wiki", config.bundle_root)
            os.replace(stage / "catalog", config.catalog_root)
        except Exception:
            _restore_after_failed_swap(config, stage, backup)
            raise
        shutil.rmtree(stage)
        return backup


def runtime_status(config: Config) -> dict[str, Any]:
    state_root = config.root / ".llmwiki"
    staging = state_root / "staging"
    backups = state_root / "backups"

    def entries(root: Path) -> list[dict[str, Any]]:
        if not root.exists():
            return []
        result = []
        for path in sorted(item for item in root.iterdir() if item.is_dir()):
            size = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
            result.append({"id": path.name, "bytes": size})
        return result

    return {
        "write_lock": (state_root / "lock").exists(),
        "staging": entries(staging),
        "backups": entries(backups),
    }


def prune_runtime(config: Config, *, keep: int, approved: bool, dry_run: bool) -> list[str]:
    if keep < 1:
        raise PlanError("At least one backup must be retained")
    backup_root = config.root / ".llmwiki/backups"
    candidates = sorted(
        (path for path in backup_root.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if backup_root.exists() else []
    selected = candidates[keep:]
    if selected and not dry_run and not approved:
        raise PlanError("Pruning backups requires explicit approval")
    if not dry_run:
        for path in selected:
            shutil.rmtree(path)
    return [path.name for path in selected]
