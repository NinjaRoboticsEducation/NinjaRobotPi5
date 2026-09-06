from __future__ import annotations

import re
import yaml
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .config import Config
from .frontmatter import FrontmatterError, parse_file
from .indexes import build_indexes
from .links import anchors, extract_links, extract_wikilinks, resolve_link
from .models import Issue
from .paths import concept_id, iter_markdown, sha256_file
from .semantic import has_absolute_claims, semantic_review_state
from .sources import IMAGE_EXTENSIONS, list_records, record_status
from .secrets import detected_secret_kinds

FOOTNOTE_REF_RE = re.compile(r"\[\^([A-Za-z0-9_-]+)\](?!:)")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^([A-Za-z0-9_-]+)\]:", re.MULTILINE)


def _severity(config: Config, setting: str, default: str) -> str:
    value = str((config.settings.get("lint") or {}).get(setting, default))
    return value if value in {"error", "warning", "suggestion"} else default


def _broad_resource(resource: str) -> bool:
    value = resource.rstrip("/")
    return bool(
        re.fullmatch(r"https?://github\.com/[^/]+/[^/]+", value)
        or "/blob/main/" in value
        or "/blob/master/" in value
    )


def _uncited_paragraphs(body: str) -> list[int]:
    paragraphs: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start = 1
    fenced = False
    for number, line in enumerate(body.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        if not line.strip():
            if current:
                paragraphs.append((start, current))
                current = []
            continue
        if not current:
            start = number
        current.append(line)
    if current:
        paragraphs.append((start, current))
    findings = []
    for line, lines in paragraphs:
        text = " ".join(item.strip() for item in lines)
        if (
            len(text.split()) >= 18
            and "[^" not in text
            and not text.startswith(("#", "-", "*", ">", "|", "![", "[^") )
        ):
            findings.append(line)
    return findings


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def trust_tier(metadata: dict[str, Any]) -> str:
    verified = metadata.get("verified")
    if not verified:
        return "unverified"
    events = verified if isinstance(verified, list) else [verified]
    if any(isinstance(item, dict) and str(item.get("by", "")).startswith("human:") for item in events):
        return "human-reviewed"
    return "machine-confirmed"


def is_stale(metadata: dict[str, Any], now: datetime | None = None) -> bool:
    value = _parse_datetime(metadata.get("stale_after"))
    if value is None:
        return False
    now = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return now >= value


def _profile_errors(config: Config, metadata: dict[str, Any], relative: str) -> list[Issue]:
    import json

    schema = json.loads((config.root / "schemas/okf-v0.2-profile.schema.json").read_text(encoding="utf-8"))
    issues = []
    for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(metadata):
        location = ".".join(str(item) for item in error.path)
        message = f"{location}: {error.message}" if location else error.message
        issues.append(Issue("error", "frontmatter-schema", message, relative))
    return issues


def _semantic_issues(
    config: Config,
    document: Any,
    relative: str,
    records_by_id: dict[str, dict[str, Any]],
    *,
    strict: bool,
) -> list[Issue]:
    settings = config.settings.get("semantic_review") or {}
    if not settings.get("enabled", True):
        return []
    required_statuses = set(settings.get("strict_for_status") or ["stable"])
    source_ids = {
        str(item.get("id"))
        for item in document.metadata.get("sources", [])
        if isinstance(item, dict) and item.get("id")
    }
    required = document.metadata.get("status") in required_statuses or (
        settings.get("strict_for_sourced_pages", True) and bool(source_ids)
    )
    review = document.metadata.get("semantic_review")
    checks = review.get("checks", {}) if isinstance(review, dict) else {}
    issues: list[Issue] = []

    if (
        settings.get("flag_absolute_language", True)
        and has_absolute_claims(document.body)
        and checks.get("claim_strength") != "passed"
    ):
        issues.append(Issue(
            "suggestion",
            "absolute-claim-review",
            "Absolute wording needs source-based claim-strength review",
            relative,
        ))

    if not required and not isinstance(review, dict):
        return issues

    severity = "error" if strict and required else "warning"
    state = semantic_review_state(document)
    if state == "missing":
        issues.append(Issue(severity, "semantic-review-missing", "Page requiring semantic review has no page-level review", relative))
    elif state == "stale":
        issues.append(Issue(severity, "semantic-review-stale", "Semantic review no longer matches the page content or evidence", relative))
    elif state == "incomplete":
        issues.append(Issue(severity, "semantic-review-incomplete", "Semantic review is incomplete", relative))
    elif state == "concerns":
        issues.append(Issue(severity, "semantic-review-concern", "Semantic review records unresolved concerns", relative))

    concern_checks = sorted(name for name, value in checks.items() if value in {"concern", "not_inspected"})
    if state == "passed" and concern_checks:
        issues.append(Issue(
            severity,
            "semantic-review-concern",
            "Review is marked passed but still contains concerns: " + ", ".join(concern_checks),
            relative,
        ))

    has_image_evidence = any(
        records_by_id.get(source_id, {}).get("kind") == "image"
        for source_id in source_ids
    ) or any(link.image for link in extract_links(document.body))
    if (
        settings.get("require_visual_review", True)
        and has_image_evidence
        and checks.get("visual_evidence") != "passed"
    ):
        issues.append(Issue(severity, "visual-review-missing", "Image-based evidence requires actual visual inspection before semantic review can pass", relative))
    return issues


def lint_bundle(bundle_root: Path, config: Config, *, include_index_check: bool = True, strict: bool = False) -> list[Issue]:
    issues: list[Issue] = []
    try:
        records_by_id = {record["id"]: record for record in list_records(config)}
    except Exception:
        records_by_id = {}
    referenced_assets: set[Path] = set()
    for path in bundle_root.rglob("*"):
        if path.is_symlink():
            relative = f"wiki/{path.relative_to(bundle_root).as_posix()}"
            issues.append(Issue("error", "symlink", "Symlinks are not allowed inside the OKF bundle", relative))
    seen_ids: Counter[str] = Counter()
    pages = list(iter_markdown(bundle_root))
    parsed: dict[Path, Any] = {}

    root_index = bundle_root / "index.md"
    if not root_index.is_file():
        issues.append(Issue("error", "missing-root-index", "wiki/index.md is required", "wiki/index.md"))
    else:
        try:
            root_doc = parse_file(root_index)
            if root_doc.metadata != {"okf_version": "0.2"}:
                issues.append(Issue("error", "okf-version", 'Root index must declare only okf_version: "0.2"', "wiki/index.md"))
        except FrontmatterError as exc:
            issues.append(Issue("error", "okf-version", str(exc), "wiki/index.md"))

    for path in pages:
        relative = f"wiki/{path.relative_to(bundle_root).as_posix()}"
        page_id = concept_id(path, bundle_root)
        seen_ids[page_id] += 1
        try:
            document = parse_file(path)
            parsed[path] = document
        except (FrontmatterError, OSError) as exc:
            issues.append(Issue("error", "frontmatter", str(exc), relative))
            continue
        metadata = document.metadata
        for kind in detected_secret_kinds(document.body):
            issues.append(Issue("warning", "possible-secret", f"Possible {kind} found; review before sharing", relative))
        issues.extend(_profile_errors(config, metadata, relative))
        for field in config.required_profile_fields:
            if not metadata.get(field):
                issues.append(Issue("warning", "profile-field", f"Missing recommended profile field: {field}", relative))
        page_type = metadata.get("type")
        if page_type and config.allowed_types and page_type not in config.allowed_types:
            issues.append(Issue("suggestion", "unknown-type", f"Unknown local page type is still valid OKF: {page_type}", relative))
        if is_stale(metadata):
            issues.append(Issue("warning", "stale", "Page is past stale_after", relative))

        source_ids = {
            str(item.get("id"))
            for item in metadata.get("sources", [])
            if isinstance(item, dict) and item.get("id")
        }
        definitions = set(FOOTNOTE_DEF_RE.findall(document.body))
        references = set(FOOTNOTE_REF_RE.findall(document.body))
        for label in sorted(references - definitions):
            issues.append(Issue("error", "missing-footnote-definition", f"Footnote '{label}' has no definition", relative))
        for label in sorted(references | definitions):
            if label not in source_ids:
                issues.append(Issue("error", "citation-source", f"Footnote '{label}' has no matching sources[].id", relative))
        for source_id in sorted(source_ids):
            if source_id not in references:
                severity = "error" if metadata.get("status") == "stable" else "suggestion"
                issues.append(Issue(severity, "unused-source", f"Source '{source_id}' is not cited in the body", relative))
        for item in metadata.get("sources", []):
            if not isinstance(item, dict) or not item.get("resource"):
                continue
            source_id = str(item.get("id") or "")
            record = records_by_id.get(source_id)
            if source_id and record is None:
                issues.append(Issue("error", "unknown-source", f"No catalog record exists for source '{source_id}'", relative))
            elif record is not None:
                page_hash = item.get("content_hash")
                if not page_hash:
                    severity = "error" if metadata.get("status") == "stable" else "warning"
                    issues.append(Issue(severity, "source-version-missing", f"Source '{source_id}' has no content_hash", relative))
                elif page_hash != record.get("content_hash"):
                    issues.append(Issue("error", "source-version-mismatch", f"Source '{source_id}' uses an older or unknown content hash", relative))
            resource = str(item["resource"])
            if _broad_resource(resource):
                issues.append(Issue("warning", "broad-source-resource", f"Use an immutable file revision or source URN instead of: {resource}", relative))
            try:
                source_target, _ = resolve_link(path, resource, bundle_root)
            except ValueError:
                issues.append(Issue("error", "source-resource", f"Source resource leaves the OKF bundle: {resource}", relative))
                continue
            if source_target is not None and not source_target.exists():
                issues.append(Issue("error", "source-resource", f"Source resource does not exist: {resource}", relative))
        if metadata.get("status") == "stable" and metadata.get("type") in {"Reference", "Analysis"} and not source_ids:
            issues.append(Issue("error", "stable-without-source", "A stable Reference or Analysis page must list traceable sources", relative))
        if metadata.get("type") == "Reference" and metadata.get("resource") and _broad_resource(str(metadata["resource"])):
            issues.append(Issue("warning", "broad-reference-resource", "Reference resource should identify an exact revision or source URN", relative))
        if source_ids:
            uncited_severity = _severity(config, "uncited_paragraphs", "suggestion")
            for line in _uncited_paragraphs(document.body):
                issues.append(Issue(uncited_severity, "uncited-paragraph", "Factual-looking paragraph has no source footnote; review it", relative, line))
        issues.extend(_semantic_issues(config, document, relative, records_by_id, strict=strict))
        for target, line in extract_wikilinks(document.body):
            issues.append(Issue("error", "wikilink", f"Use a standard Markdown link instead of [[{target}]]", relative, line))

    for page_id, count in seen_ids.items():
        if count > 1:
            issues.append(Issue("error", "duplicate-id", f"Duplicate concept ID: {page_id}"))

    inbound: Counter[Path] = Counter()
    for path, document in parsed.items():
        relative = f"wiki/{path.relative_to(bundle_root).as_posix()}"
        full_text = document.body
        for link in extract_links(full_text):
            try:
                target, anchor = resolve_link(path, link.target, bundle_root)
            except ValueError as exc:
                issues.append(Issue("error", "unsafe-link", str(exc), relative, link.line))
                continue
            if target is None:
                if link.image:
                    issues.append(Issue("warning", "external-image", "External image is not a portable, versioned bundle asset", relative, link.line))
                continue
            if not target.exists():
                issues.append(Issue(_severity(config, "broken_links", "error"), "broken-link", f"Missing target: {link.target}", relative, link.line))
                continue
            if link.image:
                if not link.label.strip():
                    issues.append(Issue("warning", "image-alt", "Image link needs useful alt text", relative, link.line))
                try:
                    target.resolve().relative_to((bundle_root / "assets").resolve())
                except ValueError:
                    issues.append(Issue("error", "image-location", "Local image assets must stay under wiki/assets/", relative, link.line))
                else:
                    referenced_assets.add(target.resolve())
            if target.suffix == ".md" and target.name not in {"index.md", "log.md"}:
                inbound[target.resolve()] += 1
            if anchor and target.is_file() and target.suffix == ".md":
                if anchor not in anchors(target.read_text(encoding="utf-8")):
                    issues.append(Issue(_severity(config, "broken_anchors", "error"), "broken-anchor", f"Missing anchor '{anchor}' in {link.target}", relative, link.line))
    for path in pages:
        if path.name == "overview.md":
            continue
        if inbound[path.resolve()] == 0:
            relative = f"wiki/{path.relative_to(bundle_root).as_posix()}"
            issues.append(Issue(_severity(config, "orphan_pages", "warning"), "orphan", "Page has no inbound concept links", relative))

    assets_root = bundle_root / "assets"
    if assets_root.exists():
        for asset in sorted(item for item in assets_root.rglob("*") if item.is_file() and not item.name.startswith(".")):
            relative = f"wiki/{asset.relative_to(bundle_root).as_posix()}"
            if asset.suffix.lower() not in IMAGE_EXTENSIONS:
                issues.append(Issue("error", "unsupported-asset", "Only PNG and JPEG supporting assets are allowed", relative))
                continue
            if asset.resolve() not in referenced_assets:
                issues.append(Issue("warning", "orphan-asset", "Asset is not referenced by a wiki page", relative))
            if "sources" not in asset.relative_to(assets_root).parts:
                issues.append(Issue("warning", "asset-location", "Source renditions should live under wiki/assets/sources/", relative))
            source_id = asset.stem
            record = records_by_id.get(source_id)
            if not record or record.get("kind") != "image":
                issues.append(Issue("error", "asset-provenance", "Asset filename does not match a registered image source ID", relative))
            elif (record.get("image") or {}).get("rendition_hash") != sha256_file(asset):
                issues.append(Issue("error", "asset-version-mismatch", "Asset bytes do not match the registered sanitized rendition", relative))

    if include_index_check:
        for path in build_indexes(bundle_root, check=True):
            relative = f"wiki/{path.relative_to(bundle_root).as_posix()}"
            issues.append(Issue("warning", "index-drift", "Generated index is out of date", relative))
    return sorted(issues, key=lambda item: ({"error": 0, "warning": 1, "suggestion": 2}[item.severity], item.path or "", item.code))


def lint_project(config: Config, *, strict: bool = False) -> list[Issue]:
    issues = lint_bundle(config.bundle_root, config, strict=strict)
    try:
        records = list_records(config)
    except Exception as exc:
        issues.append(Issue("error", "catalog", str(exc), "raw/_catalog"))
        return issues
    for record in records:
        status = record_status(config, record)
        if status == "missing":
            issues.append(Issue("error", "missing-source", f"Source file is missing: {record['path']}", record["path"]))
        elif status == "needs-review":
            issues.append(Issue(_severity(config, "changed_sources", "error"), "changed-source", f"Source changed since registration: {record['id']}", record["path"]))
        derived_manifest = config.derived_root / record["id"] / "manifest.yaml"
        if record.get("normalized_at"):
            if not derived_manifest.is_file():
                issues.append(Issue("error", "missing-derived-manifest", "Normalized source is missing its derived manifest", record["path"]))
            else:
                manifest = yaml.safe_load(derived_manifest.read_text(encoding="utf-8")) or {}
                if manifest.get("source_hash") != record.get("content_hash"):
                    issues.append(Issue("error", "derived-version-mismatch", "Derived output was built from a different source hash", record["path"]))
                derived_content = derived_manifest.parent / "content.md"
                if not derived_content.is_file() or manifest.get("content_hash") != (sha256_file(derived_content) if derived_content.is_file() else None):
                    issues.append(Issue("error", "derived-content-mismatch", "Derived content is missing or differs from its manifest", record["path"]))
                rendition = manifest.get("rendition") or {}
                if rendition:
                    rendition_path = derived_manifest.parent / str(rendition.get("path", ""))
                    if not rendition_path.is_file() or rendition.get("content_hash") != (sha256_file(rendition_path) if rendition_path.is_file() else None):
                        issues.append(Issue("error", "derived-asset-mismatch", "Sanitized rendition is missing or differs from its manifest", record["path"]))
        image_metadata = record.get("image") or {}
        if image_metadata.get("contains_gps_metadata") or image_metadata.get("contains_sensitive_metadata"):
            issues.append(Issue("warning", "sensitive-image-metadata", "Original image contains GPS or identifying EXIF metadata; review privacy before sharing", record["path"]))
        if record.get("original_uri") and _broad_resource(str(record["original_uri"])):
            issues.append(Issue("warning", "broad-original-uri", "Catalog URI should identify an immutable file revision", record["path"]))
        source_path = config.root / record["path"]
        if source_path.is_file() and source_path.suffix.lower() in {".md", ".markdown", ".txt", ".html", ".htm"}:
            text = source_path.read_text(encoding="utf-8", errors="replace")
            for kind in detected_secret_kinds(text):
                issues.append(Issue("warning", "possible-secret", f"Possible {kind} in source; review privacy before remote use", record["path"]))
    registered_paths = {str(record.get("path")) for record in records}
    for folder in ("articles", "papers", "notes", "media"):
        root = config.raw_root / folder
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.name.startswith(".")):
            relative = path.relative_to(config.root).as_posix()
            if relative in registered_paths:
                continue
            if path.suffix.lower() in config.allowed_extensions:
                issues.append(Issue("suggestion", "unregistered-source", "Supported raw source is not registered", relative))
            else:
                issues.append(Issue("suggestion", "unsupported-source", f"Unsupported raw source extension: {path.suffix or '<none>'}", relative))
    return sorted(issues, key=lambda item: ({"error": 0, "warning": 1, "suggestion": 2}[item.severity], item.path or "", item.code))
