"""Public document retrieval uses fake files only and never runs their instructions."""

import hashlib
import json

import pytest
from ninjarobot_pi5_agent.project_documents import lookup_documents, sections


def setup_docs(tmp_path, text):
    name = "InstallationGuide.md"
    path = f"raw/articles/ninjarobotpi5/2026-09-17/{name}"
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    target.write_text(text)
    entry = dict(
        name=name, path=path, content_hash="sha256:" + hashlib.sha256(text.encode()).hexdigest()
    )
    (tmp_path / "project-knowledge.json").write_text(json.dumps(dict(version=1, documents=[entry])))
    return target, entry


def test_search_and_continuation_preserve_later_steps(tmp_path):
    text = (
        "# Calendar setup\n"
        + "Authorize Google Calendar with the terminal.\n" * 100
        + "LAST STEP: confirm the connection.\n"
    )
    target, entry = setup_docs(tmp_path, text)

    def query(q, read=False):
        return lookup_documents(tmp_path, q, read=read, overlay=tmp_path / "none.json")

    result = query("how to authorize Google Calendar")
    current = result["results"][0]
    bodies = []
    while current:
        bodies.append(current["excerpt"])
        assert len(current["excerpt"]) <= 3000
        assert current["source_path"] == entry["path"]
        assert current["content_hash"] == entry["content_hash"]
        next_id = current["next_document_id"]
        current = query(next_id, True)["results"][0] if next_id else None
    assert "LAST STEP" in "".join(bodies)
    assert len(json.dumps(result)) < 16000
    target.write_text(text + "changed")
    assert not query("Calendar")["results"]
    assert "hash" in " ".join(query("Calendar")["warnings"])


@pytest.mark.parametrize("attack", ["symlink", "traversal", "oversize"])
def test_current_map_rejects_unsafe_sources(tmp_path, attack):
    target, entry = setup_docs(tmp_path, "# Setup\nCalendar")
    if attack == "symlink":
        target.unlink()
        secret = tmp_path / "secret"
        secret.write_text("private")
        target.symlink_to(secret)
    elif attack == "traversal":
        entry["path"] = "../secret"
        (tmp_path / "project-knowledge.json").write_text(
            json.dumps(dict(version=1, documents=[entry]))
        )
    else:
        target.write_text("x" * 524289)
    result = lookup_documents(tmp_path, "Calendar", read=False, overlay=tmp_path / "none")
    assert not result["results"]
    assert "withheld" in " ".join(result["warnings"])


def test_fenced_headings_and_long_lines_are_bounded():
    text = "# Calendar\n```bash\n# not a heading\necho example\n```\n" + "x" * 7000
    parts = sections(text)
    assert all(p[0] == "Calendar" for p in parts)
    assert all(len(p[2]) <= 3000 for p in parts)
    assert "".join(p[2] for p in parts) == text


def test_pending_sources_and_later_registered_versions(tmp_path):
    target, entry = setup_docs(tmp_path, "# Calendar\nRegistered old setup.")
    later = target.parent.with_name("2026-09-17-02") / target.name
    later.parent.mkdir()
    later.write_text("# Calendar\nNew unpublished setup.")
    pending = dict(
        entry,
        path=str(later.relative_to(tmp_path)),
        content_hash="sha256:" + hashlib.sha256(later.read_bytes()).hexdigest(),
    )
    overlay = tmp_path / "overlay.json"
    overlay.write_text(json.dumps(dict(version=1, documents=[pending])))
    result = lookup_documents(tmp_path, "Calendar", read=False, overlay=overlay)
    assert result["results"][0]["page_state"] == "unpublished"
    assert "New unpublished" in result["results"][0]["excerpt"]
    # Once that source is registered, its actual map metadata wins.
    (tmp_path / "project-knowledge.json").write_text(
        json.dumps(dict(version=1, documents=[pending]))
    )
    result = lookup_documents(tmp_path, "Calendar", read=False, overlay=overlay)
    assert result["results"][0]["page_state"] == "source"
    # A release manifest for the base date cannot override the later same-day version.
    overlay.write_text(json.dumps(dict(version=1, documents=[entry])))
    result = lookup_documents(tmp_path, "Calendar", read=False, overlay=overlay)
    assert "New unpublished" in result["results"][0]["excerpt"]
