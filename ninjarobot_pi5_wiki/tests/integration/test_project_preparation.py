"""Exercise the parent project's text-cache preparation in disposable wiki fixtures."""

from __future__ import annotations

import os
import runpy
import shutil
from pathlib import Path

import pytest
from llmwiki.sources import add_source

LAUNCHER = Path(__file__).resolve().parents[3] / "scripts/wiki.py"
MODULE = runpy.run_path(str(LAUNCHER))


def test_fresh_checkout_preparation_preserves_sources_and_catalog(project) -> None:
    root, config = project
    source = root / "raw/notes/evidence.md"
    source.write_text("# Evidence\n\nOriginal text.\n")
    record, _ = add_source(config, source)
    catalog = {p: p.read_bytes() for p in config.catalog_root.glob("*.yaml")}
    original = source.read_bytes()
    shutil.rmtree(config.derived_root)
    assert MODULE["prepare"](root) == 0
    assert (config.derived_root / record["id"] / "content.md").is_file()
    assert MODULE["prepare"](root) == 0
    assert source.read_bytes() == original
    assert catalog == {p: p.read_bytes() for p in config.catalog_root.glob("*.yaml")}


def test_changed_source_preparation_fails_without_refreshing_catalog(project) -> None:
    root, config = project
    source = root / "raw/notes/evidence.md"
    source.write_text("Original\n")
    add_source(config, source)
    catalog = {p: p.read_bytes() for p in config.catalog_root.glob("*.yaml")}
    source.write_text("Changed without review\n")
    with pytest.raises(ValueError, match="needs review"):
        MODULE["prepare"](root)
    assert catalog == {p: p.read_bytes() for p in config.catalog_root.glob("*.yaml")}


def test_launcher_clears_only_child_environment(monkeypatch) -> None:
    monkeypatch.setenv("VIRTUAL_ENV", "/unrelated/robot-env")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/unrelated/override")
    child = MODULE["child_environment"]()
    assert "VIRTUAL_ENV" not in child
    assert "UV_PROJECT_ENVIRONMENT" not in child
    assert os.environ["VIRTUAL_ENV"] == "/unrelated/robot-env"


@pytest.mark.parametrize("inside_wiki", [False, True])
def test_prepare_rejects_a_redirected_cache_before_writing(project, tmp_path, inside_wiki) -> None:
    root, config = project
    outside = (config.raw_root if inside_wiki else tmp_path) / "unrelated"
    outside.mkdir()
    shutil.rmtree(config.derived_root)
    try:
        config.derived_root.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError, match="Symlinked|outside the project"):
        MODULE["prepare"](root)
    assert list(outside.iterdir()) == []
