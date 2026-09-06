from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .config import Config
from .frontmatter import FrontmatterError, parse_text
from .paths import UnsafePathError, safe_project_path, sha256_file
from .sources import load_record


class PlanError(ValueError):
    """Raised when a change plan is invalid or stale."""


def load_plan(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise PlanError(f"Could not read plan {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PlanError("Plan must be a mapping")
    return data


def source_refs(plan: dict[str, Any]) -> list[dict[str, str]]:
    if plan.get("version") == 1:
        return [plan["source"]] if isinstance(plan.get("source"), dict) else []
    return list(plan.get("sources") or [])


def _validate_source_refs(config: Config, plan: dict[str, Any], *, check_hashes: bool) -> set[str]:
    refs = source_refs(plan)
    ids = [item["id"] for item in refs]
    if len(ids) != len(set(ids)):
        raise PlanError("Plan lists a source more than once")
    if not check_hashes:
        return set(ids)
    for source_ref in refs:
        record = load_record(config, source_ref["id"])
        if record["content_hash"] != source_ref["content_hash"]:
            raise PlanError(f"Plan source hash no longer matches catalog record: {source_ref['id']}")
        source_path = config.root / record["path"]
        if not source_path.is_file() or sha256_file(source_path) != source_ref["content_hash"]:
            raise PlanError(f"Plan source changed after creation: {source_ref['id']}")
    return set(ids)


def _page_source_ids(content: str) -> tuple[set[str], dict[str, str]]:
    try:
        metadata = parse_text(content, source="plan content").metadata
    except FrontmatterError:
        return set(), {}
    ids: set[str] = set()
    hashes: dict[str, str] = {}
    for item in metadata.get("sources", []):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        source_id = str(item["id"])
        ids.add(source_id)
        if item.get("content_hash"):
            hashes[source_id] = str(item["content_hash"])
    return ids, hashes


def _validate_asset(config: Config, operation: dict[str, Any], plan_source_ids: set[str], *, check_hashes: bool) -> Path:
    if operation.get("source_id") not in plan_source_ids:
        raise PlanError("copy_asset source_id must be listed in the plan sources array")
    try:
        source = safe_project_path(config.root, operation["from"], config.derived_root)
        target = safe_project_path(config.root, operation["path"], config.bundle_root / "assets")
    except UnsafePathError as exc:
        raise PlanError(str(exc)) from exc
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg"} or target.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise PlanError("copy_asset supports PNG and JPEG files only")
    if source.is_symlink() or target.is_symlink():
        raise PlanError("Asset symlinks are not allowed")
    if not source.is_file():
        raise PlanError(f"Derived asset does not exist: {operation['from']}")
    if check_hashes and sha256_file(source) != operation["expected_sha256"]:
        raise PlanError(f"Derived asset hash changed: {operation['from']}")
    manifest_path = source.parent / "manifest.yaml"
    if not manifest_path.is_file():
        raise PlanError("Derived asset is missing its manifest")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if manifest.get("source_id") != operation["source_id"]:
        raise PlanError("Derived asset manifest has the wrong source ID")
    if (manifest.get("rendition") or {}).get("content_hash") != operation["expected_sha256"]:
        raise PlanError("Derived asset hash does not match its manifest")
    target_expected = operation.get("expected_target_sha256")
    if target.exists():
        if not isinstance(target_expected, str):
            raise PlanError("Replacing an existing asset requires expected_target_sha256")
        if check_hashes and sha256_file(target) != target_expected:
            raise PlanError(f"Stale target asset: {operation['path']}")
        if check_hashes and sha256_file(target) == operation["expected_sha256"]:
            raise PlanError(f"No-op asset copy is not allowed: {operation['path']}")
    elif target_expected is not None:
        raise PlanError(f"Expected target asset is missing: {operation['path']}")
    return target


def validate_plan(config: Config, plan: dict[str, Any], *, check_hashes: bool = True) -> list[str]:
    schema = json.loads((config.root / "schemas/change-plan.schema.json").read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(plan),
        key=lambda item: list(item.path),
    )
    if errors:
        details = []
        for error in errors:
            location = ".".join(str(item) for item in error.path)
            details.append(f"{location}: {error.message}" if location else error.message)
        raise PlanError("Invalid plan: " + "; ".join(details))

    plan_source_ids = _validate_source_refs(config, plan, check_hashes=check_hashes)
    operations = plan["operations"]
    if any(op["op"] == "delete" for op in operations) and plan.get("risk") != "high":
        raise PlanError("Plans containing delete operations require risk: high")
    if plan.get("risk") == "low" and (len(operations) > 10 or any(op["op"] in {"move", "copy_asset"} for op in operations)):
        raise PlanError("This plan is too large or disruptive for risk: low")
    if any(op["op"] == "copy_asset" for op in plan["operations"]) and plan.get("version") != 2:
        raise PlanError("copy_asset requires change-plan version 2")

    seen: set[str] = set()
    summaries: list[str] = []
    page_source_ids: set[str] = set()
    for operation in plan["operations"]:
        if operation["op"] == "copy_asset":
            target = _validate_asset(config, operation, plan_source_ids, check_hashes=check_hashes)
            key = target.as_posix()
            if key in seen:
                raise PlanError(f"Plan touches target more than once: {operation['path']}")
            seen.add(key)
            summaries.append(f"copy_asset: {operation['from']} -> {operation['path']}")
            continue
        try:
            target = safe_project_path(config.root, operation["path"], config.bundle_root)
            source = None
            if operation["op"] == "move":
                source = safe_project_path(config.root, operation["from"], config.bundle_root)
        except UnsafePathError as exc:
            raise PlanError(str(exc)) from exc
        key = target.as_posix()
        if key in seen:
            raise PlanError(f"Plan touches target more than once: {operation['path']}")
        seen.add(key)
        if target.name in {"index.md", "log.md"}:
            raise PlanError("Plans cannot write reserved index.md or log.md files directly")
        if target.suffix.lower() != ".md" or (source is not None and source.suffix.lower() != ".md"):
            raise PlanError("Wiki page operations may touch Markdown concept pages only")
        expected = operation.get("expected_sha256")
        current_path = source if source is not None else target
        if operation["op"] in {"move", "delete"} and not isinstance(expected, str):
            raise PlanError(f"{operation['op']} requires expected_sha256: {operation['path']}")
        if check_hashes and expected is not None:
            if not current_path.exists():
                raise PlanError(f"Expected existing file is missing: {current_path}")
            actual = sha256_file(current_path)
            if actual != expected:
                raise PlanError(f"Stale plan for {current_path}: expected {expected}, found {actual}")
        if operation["op"] == "write":
            proposed = operation["content"].rstrip() + "\n"
            if target.exists() and expected is None:
                raise PlanError(f"Writing an existing page requires expected_sha256: {operation['path']}")
            if check_hashes and target.exists() and target.read_text(encoding="utf-8") == proposed:
                raise PlanError(f"No-op write is not allowed: {operation['path']}")
            ids, hashes = _page_source_ids(operation["content"])
            page_source_ids.update(ids)
            for source_id, content_hash in hashes.items():
                record = load_record(config, source_id)
                if content_hash != record["content_hash"]:
                    raise PlanError(f"Page source hash does not match the catalog: {source_id}")
        if operation["op"] in {"move", "delete"} and not current_path.exists():
            raise PlanError(f"Operation source does not exist: {current_path}")
        if operation["op"] == "move" and target.exists():
            raise PlanError(f"Move target already exists: {operation['path']}")
        summaries.append(f"{operation['op']}: {operation.get('from', '')} -> {operation['path']}".replace(":  ->", ":"))

    if plan.get("version") == 2 and not page_source_ids.issubset(plan_source_ids):
        missing = ", ".join(sorted(page_source_ids - plan_source_ids))
        raise PlanError(f"Page content uses sources missing from the plan: {missing}")
    return summaries


def plan_diff(config: Config, plan: dict[str, Any]) -> str:
    validate_plan(config, plan, check_hashes=True)
    output = [f"Plan {plan['id']}: {plan.get('summary', '')}\n", f"Risk: {plan['risk']}\n\n"]
    for operation in plan["operations"]:
        output.append(f"## {operation['op']} {operation['path']}\n")
        if operation["op"] == "copy_asset":
            source = safe_project_path(config.root, operation["from"], config.derived_root)
            output.append(
                f"Binary asset from `{operation['from']}` ({source.stat().st_size} bytes, "
                f"{operation['expected_sha256']}) for source `{operation['source_id']}`.\n"
            )
        else:
            path = safe_project_path(config.root, operation["path"], config.bundle_root)
            if operation["op"] == "write":
                old = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []
                new = (operation["content"].rstrip() + "\n").splitlines(keepends=True)
                output.extend(difflib.unified_diff(old, new, fromfile=str(path), tofile=str(path)))
            elif operation["op"] == "move":
                output.append(f"Move from {operation['from']}\n")
            else:
                output.append("Delete this page after approval.\n")
        output.append("\n")
    return "".join(output).rstrip() + "\n"
