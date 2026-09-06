from __future__ import annotations

from pathlib import Path

import yaml

from llmwiki.config import Config
from llmwiki.indexes import build_indexes
from llmwiki.lint import lint_project


ROOT = Path(__file__).parents[2]
SKILLS = ("wiki-ingest", "wiki-query", "wiki-lint", "wiki-review", "wiki-maintain")


def test_checked_in_blank_template_is_healthy() -> None:
    config = Config.load(ROOT)
    assert not [issue for issue in lint_project(config) if issue.severity == "error"]
    assert build_indexes(config.bundle_root, check=True) == []


def test_every_adapter_points_to_a_canonical_skill() -> None:
    for name in SKILLS:
        canonical = ROOT / ".agents" / "skills" / name / "SKILL.md"
        wrapper = ROOT / ".claude" / "skills" / name / "SKILL.md"
        assert canonical.is_file()
        assert wrapper.is_file()
        pointer = next(line for line in wrapper.read_text(encoding="utf-8").splitlines() if line.startswith("Read and follow"))
        relative = pointer.split("`", 2)[1]
        assert (wrapper.parent / relative).resolve() == canonical.resolve()


def test_adapters_share_the_same_operating_manual() -> None:
    assert "AGENTS.md" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in (ROOT / ".cursor" / "rules" / "llm-wiki.mdc").read_text(encoding="utf-8")


def test_antigravity_rule_points_to_the_operating_manual() -> None:
    rule = ROOT / ".agents" / "rules" / "llm-wiki.md"
    text = rule.read_text(encoding="utf-8")
    pointer = next(part for part in text.split() if part.startswith("@") and part.endswith("AGENTS.md"))
    assert (rule.parent / pointer[1:]).resolve() == (ROOT / "AGENTS.md").resolve()
    assert len(text) < 12_000


def test_antigravity_workflows_point_to_canonical_skills() -> None:
    workflow_root = ROOT / ".agents" / "workflows"
    for name in SKILLS:
        workflow = workflow_root / f"{name}.md"
        text = workflow.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        _, frontmatter, _ = text.split("---", 2)
        metadata = yaml.safe_load(frontmatter)
        assert isinstance(metadata.get("description"), str)
        pointer = next(part.rstrip(".,") for part in text.split() if part.startswith("@../skills/"))
        canonical = ROOT / ".agents" / "skills" / name / "SKILL.md"
        assert (workflow.parent / pointer[1:]).resolve() == canonical.resolve()
        assert len(text) < 12_000


def test_antigravity_guide_lists_every_workflow() -> None:
    guide = (ROOT / "docs" / "ANTIGRAVITY.md").read_text(encoding="utf-8")
    for name in SKILLS:
        assert f"/{name}" in guide


def test_readme_explains_git_source_folders_images_and_batch_ingest() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for folder in ("raw/articles/", "raw/papers/", "raw/notes/", "raw/media/"):
        assert folder in readme
    assert "before the first ingestion" in readme
    assert "`.png`, `.jpg`, `.jpeg`" in readme
    assert "Tesseract" in readme
    assert "sanitized rendition" in readme
    assert "Discover files that are not registered yet" in readme
    assert "llmwiki lint --strict" in readme
    assert "llmwiki review prepare" in readme
    for name in SKILLS:
        assert name in readme
