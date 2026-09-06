---
name: wiki-maintain
description: Maintain an established LLM Wiki by refreshing stale pages, resolving duplicates, moving or deprecating pages, and keeping links and indexes healthy. Use for structural upkeep rather than first-time ingestion.
---

# Wiki Maintain

## Workflow

1. Run `uv run llmwiki stats`, `source status`, `runtime status`, and `lint` to find maintenance needs.
2. Search before deciding that two pages are duplicates.
3. Choose the least disruptive action: refresh, link, rename, merge, deprecate, or delete.
4. Preserve useful history and provenance. Prefer deprecation with a replacement link when readers may still rely on the old concept ID.
5. Create a change plan with expected hashes for every existing file.
6. Validate the plan and show the diff, including affected incoming links.
7. Apply only after explicit approval.
8. Confirm that indexes rebuild and normal lint has no errors. Run strict lint only when the user requests a higher-confidence release gate.

## Structural Rules

- A rename or move must update incoming links in the same transaction.
- A merge must keep all distinct evidence and record the decision in history.
- Never delete the last copy of useful provenance.
- Generated index pages may be rebuilt; hand-written page content must not be silently reformatted.
- Image replacement or deletion must keep its Reference page, registered source, rendition hash, and incoming image links consistent in one reviewed plan.
