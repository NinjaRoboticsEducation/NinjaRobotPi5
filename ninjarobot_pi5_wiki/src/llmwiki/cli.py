from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import Config, ConfigError
from .indexes import build_indexes
from .lint import lint_project, trust_tier
from .normalize import normalize_source
from .paths import iter_markdown
from .plans import PlanError, load_plan, plan_diff, validate_plan
from .search import search_bundle
from .semantic import review_template, semantic_review_state
from .sources import SourceError, add_source, list_records, load_record, record_status, update_source
from .transactions import apply_plan, prune_runtime, runtime_status

console = Console()


def _config() -> Config:
    try:
        return Config.load(Path.cwd())
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc


def _json(data: object) -> None:
    click.echo(json.dumps(data, indent=2, default=str, ensure_ascii=False))


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
def main() -> None:
    """Build and maintain a local OKF v0.2 wiki."""


@main.command()
def doctor() -> None:
    """Check the project layout and local runtime."""
    config = _config()
    git_executable = shutil.which("git")
    git_repository = False
    git_dirty: bool | None = None
    if git_executable:
        probe = subprocess.run(
            [git_executable, "-C", str(config.root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        git_repository = probe.returncode == 0 and probe.stdout.strip() == "true"
        if git_repository:
            status = subprocess.run(
                [git_executable, "-C", str(config.root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
            )
            git_dirty = bool(status.stdout.strip()) if status.returncode == 0 else None
    try:
        import PIL

        pillow_version: str | None = PIL.__version__
    except ImportError:
        pillow_version = None
    tesseract = shutil.which("tesseract")
    tesseract_version: str | None = None
    ocr_languages: list[str] = []
    if tesseract:
        try:
            version_probe = subprocess.run(
                [tesseract, "--version"], capture_output=True, text=True, check=False, timeout=10
            )
            tesseract_version = (version_probe.stdout or version_probe.stderr).splitlines()[0].strip()
            language_probe = subprocess.run(
                [tesseract, "--list-langs"], capture_output=True, text=True, check=False, timeout=10
            )
            ocr_languages = [line.strip() for line in language_probe.stdout.splitlines()[1:] if line.strip()]
        except (OSError, subprocess.TimeoutExpired):
            tesseract_version = "unavailable (probe failed)"
    checks = {
        "project": str(config.root),
        "python": platform.python_version(),
        "bundle_exists": config.bundle_root.is_dir(),
        "raw_exists": config.raw_root.is_dir(),
        "schemas_exist": (config.root / "schemas/change-plan.schema.json").is_file(),
        "git": git_executable is not None,
        "git_repository": git_repository,
        "git_dirty": git_dirty,
        "uv": shutil.which("uv") is not None,
        "write_lock": (config.root / ".llmwiki/lock").exists(),
        "pillow": pillow_version,
        "tesseract": tesseract_version,
        "ocr_languages": ocr_languages,
        "git_reminder": None if git_repository else "Initialize Git and make a baseline commit before the first real ingestion (recommended, not automatic).",
    }
    _json(checks)
    if not all(checks[key] for key in ("bundle_exists", "raw_exists", "schemas_exist", "uv")):
        raise click.ClickException("Project setup is incomplete")


@main.command(name="init")
def init_command() -> None:
    """Initialize disposable runtime directories without replacing content."""
    config = _config()
    for path in (config.catalog_root, config.derived_root, config.root / ".llmwiki/plans", config.root / ".llmwiki/staging"):
        path.mkdir(parents=True, exist_ok=True)
    build_indexes(config.bundle_root)
    click.echo(f"Initialized {config.root}")


@main.group()
def source() -> None:
    """Register, inspect, and normalize source originals."""


@source.command("add")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.option("--title")
@click.option("--uri", "original_uri")
@click.option("--source-version")
def source_add(path: Path, title: str | None, original_uri: str | None, source_version: str | None) -> None:
    config = _config()
    try:
        record, created = add_source(
            config, path, title=title, original_uri=original_uri, source_version=source_version
        )
    except SourceError as exc:
        raise click.ClickException(str(exc)) from exc
    _json({"created": created, "source": record})


@source.command("list")
@click.option("--json-output", is_flag=True)
def source_list(json_output: bool) -> None:
    config = _config()
    records = list_records(config)
    rows = [{**record, "current_status": record_status(config, record)} for record in records]
    if json_output:
        _json(rows)
        return
    table = Table("ID", "Kind", "State", "OCR", "Title", "Path")
    for row in rows:
        table.add_row(
            row["id"], str(row.get("kind", "text")), row["current_status"],
            str((row.get("image") or {}).get("ocr_status", "—")), row["title"], row["path"]
        )
    console.print(table)


@source.command("show")
@click.argument("source_id")
def source_show(source_id: str) -> None:
    try:
        _json(load_record(_config(), source_id))
    except SourceError as exc:
        raise click.ClickException(str(exc)) from exc


@source.command("status")
def source_status() -> None:
    config = _config()
    _json([
        {
            "id": record["id"],
            "kind": record.get("kind", "text"),
            "status": record_status(config, record),
            "source_version": record.get("source_version"),
            "ocr_status": (record.get("image") or {}).get("ocr_status"),
            "asset_status": (record.get("image") or {}).get("asset_status"),
        }
        for record in list_records(config)
    ])


@source.command("update")
@click.argument("source_id")
@click.option("--title")
@click.option("--uri", "original_uri")
@click.option("--source-version")
def source_update(source_id: str, title: str | None, original_uri: str | None, source_version: str | None) -> None:
    try:
        record = update_source(
            _config(), source_id, title=title, original_uri=original_uri, source_version=source_version
        )
    except SourceError as exc:
        raise click.ClickException(str(exc)) from exc
    _json(record)


@source.command("normalize")
@click.argument("source_id")
@click.option("--ocr", type=click.Choice(["auto", "off", "required"]), default="auto")
@click.option("--ocr-lang", "ocr_languages", default="eng", show_default=True)
def source_normalize(source_id: str, ocr: str, ocr_languages: str) -> None:
    try:
        path = normalize_source(_config(), source_id, ocr=ocr, ocr_languages=ocr_languages)
    except SourceError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(path)


@main.command("lint")
@click.option("--format", "output_format", type=click.Choice(["text", "json", "markdown"]), default="text")
@click.option("--strict", is_flag=True, help="Treat semantic review gaps on configured stable pages as errors.")
def lint_command(output_format: str, strict: bool) -> None:
    issues = lint_project(_config(), strict=strict)
    if output_format == "json":
        _json([issue.to_dict() for issue in issues])
    elif output_format == "markdown":
        click.echo("# LLM Wiki Lint Report\n")
        if not issues:
            click.echo("No issues found.")
        for severity in ("error", "warning", "suggestion"):
            selected = [issue for issue in issues if issue.severity == severity]
            if selected:
                click.echo(f"## {severity.title()}s\n")
                for issue in selected:
                    location = f" `{issue.path}`" if issue.path else ""
                    click.echo(f"- **{issue.code}**{location}: {issue.message}")
                click.echo()
    else:
        if not issues:
            click.echo("No issues found.")
        for issue in issues:
            location = f" {issue.path}" if issue.path else ""
            line = f":{issue.line}" if issue.line else ""
            click.echo(f"{issue.severity.upper():10} {issue.code:20}{location}{line} {issue.message}")
        counts = Counter(issue.severity for issue in issues)
        click.echo(f"Errors: {counts['error']}; warnings: {counts['warning']}; suggestions: {counts['suggestion']}")
    if any(issue.severity == "error" for issue in issues):
        raise click.exceptions.Exit(1)


@main.group()
def index() -> None:
    """Build or check progressive directory indexes."""


@index.command("build")
def index_build() -> None:
    changed = build_indexes(_config().bundle_root)
    click.echo(f"Updated {len(changed)} index file(s).")


@index.command("check")
def index_check() -> None:
    changed = build_indexes(_config().bundle_root, check=True)
    if changed:
        for path in changed:
            click.echo(path)
        raise click.exceptions.Exit(1)
    click.echo("Indexes are current.")


@main.group()
def link() -> None:
    """Inspect internal wiki links."""


@link.command("check")
def link_check() -> None:
    issues = [issue for issue in lint_project(_config()) if issue.code in {"broken-link", "broken-anchor", "unsafe-link", "wikilink"}]
    for issue in issues:
        click.echo(f"{issue.severity.upper()} {issue.path or ''}: {issue.message}")
    if any(issue.severity == "error" for issue in issues):
        raise click.exceptions.Exit(1)


@main.command("search")
@click.argument("query")
@click.option("--limit", type=click.IntRange(1, 100))
@click.option("--json-output", is_flag=True)
def search_command(query: str, limit: int | None, json_output: bool) -> None:
    config = _config()
    results = search_bundle(config.bundle_root, query, limit=limit or config.query_max_results)
    if json_output:
        _json([item.to_dict() for item in results])
        return
    for item in results:
        flags = ", ".join(filter(None, [item.status, item.trust, "stale" if item.stale else ""]))
        click.echo(f"{item.score:3} {item.concept_id} — {item.title} [{flags}]\n    {item.excerpt}")


@main.group()
def review() -> None:
    """Prepare lightweight, source-grounded page reviews."""


@review.command("prepare")
@click.argument("path", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option("--format", "output_format", type=click.Choice(["yaml", "json"]), default="yaml")
def review_prepare(path: Path, output_format: str) -> None:
    """Print a neutral review block and checklist without changing the page."""
    config = _config()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(config.bundle_root)
    except ValueError as exc:
        raise click.ClickException("Review targets must be Markdown pages inside wiki/") from exc
    if resolved.suffix.lower() != ".md" or resolved.name in {"index.md", "log.md"}:
        raise click.ClickException("Review targets must be ordinary Markdown knowledge pages")
    from .frontmatter import FrontmatterError, parse_file

    try:
        document = parse_file(resolved)
    except FrontmatterError as exc:
        raise click.ClickException(str(exc)) from exc
    block = review_template(document)["semantic_review"]
    payload = {
        "page": f"wiki/{relative.as_posix()}",
        "target_hash": block["target_hash"],
        "source_versions": {
            str(item.get("id")): str(item.get("content_hash", "missing"))
            for item in document.metadata.get("sources", [])
            if isinstance(item, dict) and item.get("id")
        },
        "questions": [
            "Do the cited sources materially support the important claims?",
            "Do the cited sources contradict or weaken any important claim?",
            "Are important limitations, exceptions, or uncertainties missing?",
            "Is any wording stronger than the evidence permits?",
            "If visual meaning is described, was the original image actually inspected?",
        ],
        "semantic_review": block,
    }
    if output_format == "json":
        _json(payload)
    else:
        click.echo(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip())


@main.command("stats")
def stats_command() -> None:
    config = _config()
    type_counts: Counter[str] = Counter()
    trust_counts: Counter[str] = Counter()
    total = 0
    lifecycle_counts: Counter[str] = Counter()
    source_usage: Counter[str] = Counter()
    semantic_counts: Counter[str] = Counter()
    sourced_pages = 0
    reviewed_sourced_pages = 0
    from .frontmatter import FrontmatterError, parse_file

    for path in iter_markdown(config.bundle_root):
        try:
            document = parse_file(path)
        except FrontmatterError:
            continue
        total += 1
        type_counts[str(document.metadata.get("type", "unknown"))] += 1
        trust_counts[trust_tier(document.metadata)] += 1
        lifecycle_counts[str(document.metadata.get("status", "unspecified"))] += 1
        semantic_state = semantic_review_state(document)
        semantic_settings = config.settings.get("semantic_review") or {}
        required_statuses = set(semantic_settings.get("strict_for_status") or ["stable"])
        page_has_sources = any(
            isinstance(item, dict) and item.get("id")
            for item in document.metadata.get("sources", [])
        )
        required = semantic_settings.get("enabled", True) and (
            document.metadata.get("status") in required_statuses
            or (semantic_settings.get("strict_for_sourced_pages", True) and page_has_sources)
        )
        if semantic_state == "missing" and not required:
            semantic_state = "not_required"
        semantic_counts[semantic_state] += 1
        if page_has_sources:
            sourced_pages += 1
            if semantic_state == "passed":
                reviewed_sourced_pages += 1
        for item in document.metadata.get("sources", []):
            if isinstance(item, dict) and item.get("id"):
                source_usage[str(item["id"])] += 1
    records = list_records(config)
    source_status_counts = Counter(record_status(config, record) for record in records)
    image_records = [record for record in records if record.get("kind") == "image"]
    asset_files = [
        path for path in (config.bundle_root / "assets").rglob("*")
        if path.is_file() and not path.name.startswith(".")
    ] if (config.bundle_root / "assets").exists() else []
    _json({
        "pages": total,
        "by_type": type_counts,
        "by_lifecycle": lifecycle_counts,
        "by_trust": trust_counts,
        "semantic_reviews": {
            **semantic_counts,
            "sourced_pages": sourced_pages,
            "passed_sourced_pages": reviewed_sourced_pages,
            "remaining_sourced_pages": sourced_pages - reviewed_sourced_pages,
            "coverage_percent": (
                round(reviewed_sourced_pages * 100 / sourced_pages, 1)
                if sourced_pages else None
            ),
        },
        "sources": len(records),
        "source_status": source_status_counts,
        "source_usage": source_usage,
        "images": {
            "registered": len(image_records),
            "ocr": Counter(str((record.get("image") or {}).get("ocr_status", "not-normalized")) for record in image_records),
            "published": sum((record.get("image") or {}).get("asset_status") == "published" for record in image_records),
        },
        "assets": len(asset_files),
        "runtime": runtime_status(config),
    })


@main.group()
def runtime() -> None:
    """Inspect and explicitly prune recoverable runtime state."""


@runtime.command("status")
def runtime_status_command() -> None:
    _json(runtime_status(_config()))


@runtime.command("prune")
@click.option("--keep", type=click.IntRange(1), default=10, show_default=True)
@click.option("--dry-run", is_flag=True)
@click.option("--approve", is_flag=True, help="Confirm deletion of old recoverable backups.")
def runtime_prune_command(keep: int, dry_run: bool, approve: bool) -> None:
    try:
        removed = prune_runtime(_config(), keep=keep, approved=approve, dry_run=dry_run)
    except PlanError as exc:
        raise click.ClickException(str(exc)) from exc
    _json({"dry_run": dry_run, "would_remove" if dry_run else "removed": removed})


@main.group()
def plan() -> None:
    """Validate, inspect, and apply reviewed change plans."""


@plan.command("validate")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
def plan_validate(path: Path) -> None:
    try:
        summaries = validate_plan(_config(), load_plan(path))
    except PlanError as exc:
        raise click.ClickException(str(exc)) from exc
    _json({"valid": True, "operations": summaries})


@plan.command("show")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
def plan_show(path: Path) -> None:
    _json(load_plan(path))


@plan.command("diff")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def plan_diff_command(path: Path, output_format: str) -> None:
    try:
        config = _config()
        loaded = load_plan(path)
        diff = plan_diff(config, loaded)
        if output_format == "json":
            _json({"id": loaded["id"], "risk": loaded["risk"], "diff": diff})
        else:
            click.echo(diff)
    except PlanError as exc:
        raise click.ClickException(str(exc)) from exc


@plan.command("apply")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.option("--approve", is_flag=True, help="Confirm that a human reviewed this plan and its diff.")
def plan_apply(path: Path, approve: bool) -> None:
    try:
        backup = apply_plan(_config(), load_plan(path), approved=approve)
    except (PlanError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Applied plan. Recoverable backup: {backup}")


if __name__ == "__main__":
    main()
