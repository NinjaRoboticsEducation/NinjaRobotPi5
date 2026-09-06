from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.normalize import normalize_source
from llmwiki.sources import SourceError, add_source, load_record, record_status


def test_add_normalize_and_detect_changed_source(project) -> None:
    root, config = project
    source = root / "raw" / "notes" / "idea.md"
    source.write_text("# Idea\n\nUseful evidence.\n", encoding="utf-8")
    record, created = add_source(config, source)
    assert created
    unchanged, created_again = add_source(config, source)
    assert not created_again
    assert unchanged["id"] == record["id"]

    derived = normalize_source(config, record["id"])
    assert "Useful evidence" in derived.read_text(encoding="utf-8")

    source.write_text("# Idea\n\nChanged evidence.\n", encoding="utf-8")
    assert record_status(config, load_record(config, record["id"])) == "needs-review"
    changed, _ = add_source(config, source)
    assert changed["state"] == "needs-review"
    assert changed["previous_content_hash"] == record["content_hash"]


def test_rejects_binary_text_and_symlinks(project) -> None:
    root, config = project
    binary = root / "raw" / "notes" / "binary.txt"
    binary.write_bytes(b"text\x00binary")
    with pytest.raises(SourceError, match="binary"):
        add_source(config, binary)

    original = root / "raw" / "notes" / "real.md"
    original.write_text("evidence", encoding="utf-8")
    linked = root / "raw" / "notes" / "linked.md"
    try:
        linked.symlink_to(original)
    except OSError:
        pytest.skip("Symlinks are unavailable on this platform")
    with pytest.raises(SourceError, match="Symlinked"):
        add_source(config, linked)

    non_utf8 = root / "raw" / "notes" / "latin1.txt"
    non_utf8.write_bytes("café".encode("latin-1"))
    with pytest.raises(SourceError, match="UTF-8"):
        add_source(config, non_utf8)


def test_html_normalization_removes_executable_markup(project) -> None:
    root, config = project
    source = root / "raw" / "articles" / "page.html"
    source.write_text(
        "<html><style>secret style</style><h1>Title</h1><p>Useful text.</p><script>deleteWiki()</script></html>",
        encoding="utf-8",
    )
    record, _ = add_source(config, source)
    content = normalize_source(config, record["id"]).read_text(encoding="utf-8")
    assert "Useful text" in content
    assert "deleteWiki" not in content
    assert "secret style" not in content
