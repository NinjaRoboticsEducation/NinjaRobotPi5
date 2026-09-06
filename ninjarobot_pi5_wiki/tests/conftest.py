from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from llmwiki.config import Config
from llmwiki.indexes import build_indexes


PROJECT_ROOT = Path(__file__).parents[1]


@pytest.fixture
def project(tmp_path: Path) -> tuple[Path, Config]:
    root = tmp_path / "wiki-project"
    root.mkdir()
    shutil.copy2(PROJECT_ROOT / "llmwiki.yaml", root / "llmwiki.yaml")
    for name in ("schemas", "templates"):
        shutil.copytree(PROJECT_ROOT / name, root / name)
    for path in (
        "wiki/concepts", "wiki/entities", "wiki/references", "wiki/analyses",
        "raw/articles", "raw/papers", "raw/notes", "raw/media", "raw/_catalog", "raw/_derived",
    ):
        (root / path).mkdir(parents=True, exist_ok=True)
    (root / "wiki/log.md").write_text("# Wiki Update Log\n", encoding="utf-8")
    (root / "wiki/overview.md").write_text(valid_page("Overview"), encoding="utf-8")
    (root / "raw/_catalog/index.yaml").write_text("version: 2\nsources: []\n", encoding="utf-8")
    config = Config.load(root)
    build_indexes(config.bundle_root)
    return root, config


def valid_page(title: str = "Test Concept", body: str = "A small test page.") -> str:
    return f'''---
type: Concept
title: {title}
description: A concept used by the automated test suite.
status: draft
generated:
  by: test-suite/1
  at: 2026-08-22T00:00:00Z
---

# {title}

{body}
'''
