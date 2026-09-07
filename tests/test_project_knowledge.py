"""Check drift and broken navigation without importing or operating robot devices."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKS = runpy.run_path(str(ROOT / "scripts/verify_project_knowledge.py"))
verify = CHECKS["verify"]
fingerprint = CHECKS["fingerprint"]
local_links = CHECKS["local_links"]


@pytest.fixture
def knowledge(tmp_path: Path) -> Path:
    wiki = tmp_path / "ninjarobot_pi5_wiki"
    files = {
        "AGENTS.md": "# Policy\n",
        "CLAUDE.md": "@AGENTS.md\n",
        "code/example.py": "VALUE = 1\n",
        "README.md": "[Manual](ninjarobot_pi5_wiki/raw/articles/v1/Guide.md)\n",
        "ninjarobot_pi5_wiki/raw/articles/v1/Guide.md": "# Example\n\nEvidence.\n",
        "ninjarobot_pi5_wiki/README.md": "[Guide](raw/articles/v1/Guide.md)\n",
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    source_hash = fingerprint(wiki / "raw/articles/v1/Guide.md")
    page = wiki / "wiki/references/guide.md"
    page.parent.mkdir(parents=True)
    page.write_text(f"# Guide\n\nsrc-test\n{source_hash}\n")
    catalog = wiki / "raw/_catalog/src-test.yaml"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        f"id: src-test\npath: raw/articles/v1/Guide.md\ncontent_hash: {source_hash}\n"
    )
    data = {
        "integration_status": "ready",
        "documents": [
            {
                "name": "Guide.md",
                "path": "raw/articles/v1/Guide.md",
                "source_id": "src-test",
                "content_hash": source_hash,
                "pages": ["wiki/references/guide.md"],
            }
        ],
        "implementation_roots": ["code"],
        "implementation_files": {
            "code/example.py": {
                "content_hash": fingerprint(tmp_path / "code/example.py"),
                "pages": ["wiki/references/guide.md"],
                "review_note": "Example evidence",
            }
        },
        "adapters": [{"path": "CLAUDE.md", "target": "AGENTS.md", "reference": "@AGENTS.md"}],
        "link_documents": ["README.md"],
    }
    (wiki / "project-knowledge.json").write_text(json.dumps(data))
    return tmp_path


def test_knowledge_check_is_read_only(knowledge: Path) -> None:
    before = {p: p.read_bytes() for p in knowledge.rglob("*") if p.is_file()}
    assert verify(knowledge) == []
    assert verify(knowledge) == []
    assert before == {p: p.read_bytes() for p in knowledge.rglob("*") if p.is_file()}


def test_changed_and_new_code_require_review(knowledge: Path) -> None:
    (knowledge / "code/example.py").write_text("VALUE = 2\n")
    (knowledge / "code/new.py").write_text("VALUE = 3\n")
    issues = verify(knowledge)
    assert any("Implementation needs knowledge review" in issue for issue in issues)
    assert any("New implementation file needs classification" in issue for issue in issues)


def test_missing_manual_and_broken_heading_are_detected(knowledge: Path) -> None:
    (knowledge / "README.md").write_text(
        "[Manual](ninjarobot_pi5_wiki/raw/articles/v1/Guide.md#missing)\n"
    )
    assert any("missing heading" in issue for issue in verify(knowledge))
    (knowledge / "ninjarobot_pi5_wiki/raw/articles/v1/Guide.md").unlink()
    assert any("Manual missing" in issue for issue in verify(knowledge))


def test_source_catalog_and_current_readme_must_agree(knowledge: Path) -> None:
    (knowledge / "ninjarobot_pi5_wiki/README.md").write_text("Old manual pointer\n")
    (knowledge / "ninjarobot_pi5_wiki/raw/_catalog/src-test.yaml").write_text("id: old\n")
    issues = verify(knowledge)
    assert any("README does not link" in issue for issue in issues)
    assert any("Catalog and current source disagree" in issue for issue in issues)


def test_adapter_wrong_relative_target_is_detected(knowledge: Path) -> None:
    path = knowledge / "ninjarobot_pi5_wiki/project-knowledge.json"
    data = json.loads(path.read_text())
    data["adapters"][0]["reference"] = "@../AGENTS.md"
    path.write_text(json.dumps(data))
    (knowledge / "CLAUDE.md").write_text("@../AGENTS.md\n")
    assert any("resolves incorrectly" in issue for issue in verify(knowledge))


def test_markdown_examples_are_not_treated_as_live_links(tmp_path: Path) -> None:
    page = tmp_path / "guide.md"
    page.write_text("# Guide\n\n```markdown\n[Example](nonexistent.md)\n```\n")
    assert local_links(page, tmp_path) == []


def test_new_manual_version_requires_current_pointers(knowledge: Path) -> None:
    wiki = knowledge / "ninjarobot_pi5_wiki"
    old = wiki / "raw/articles/v1/Guide.md"
    original = old.read_bytes()
    new = wiki / "raw/articles/v2/Guide.md"
    new.parent.mkdir()
    new.write_text("# Example\n\nUpdated evidence.\n")
    manifest = wiki / "project-knowledge.json"
    data = json.loads(manifest.read_text())
    data["documents"][0].update(path="raw/articles/v2/Guide.md", content_hash=fingerprint(new))
    manifest.write_text(json.dumps(data))
    issues = verify(knowledge)
    assert any("Root README does not link" in issue for issue in issues)
    assert any("Page needs current source review" in issue for issue in issues)
    assert old.read_bytes() == original
