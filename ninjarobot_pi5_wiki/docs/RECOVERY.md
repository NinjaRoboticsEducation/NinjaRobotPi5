# Recovery Guide

Normal changes are staged and checked before the live `wiki/` folder is replaced. A successful apply keeps the previous bundle at `.llmwiki/backups/<plan-id>/`.

## Restore a successful change

1. Stop other writers.
2. Copy the current `wiki/` folder somewhere safe for inspection.
3. Confirm the plan ID and inspect `.llmwiki/backups/<plan-id>/`.
4. A current backup contains both `wiki/` and `catalog/`. Restore both together using your normal file or Git recovery tool.
5. Run `uv run llmwiki index build` and `uv run llmwiki lint`.

The CLI does not restore automatically because that could overwrite useful work created after the original plan.

## An interrupted or failed change

Inspect `.llmwiki/staging/<plan-id>/`. It may contain the proposed bundle or a `failed-wiki/` folder. Do not copy it into place until you understand the failure and lint it.

If `.llmwiki/lock` remains after a crash, read it and confirm that its recorded process is no longer running. Only then remove the lock and retry with a new plan ID.

## Source recovery

The CLI never rewrites raw originals. Restore a source through your normal backup or Git workflow, then run `uv run llmwiki source status`. Re-register or re-ingest changed evidence instead of hiding the new hash.

## Runtime status and pruning

Use `uv run llmwiki runtime status` to inspect locks, incomplete staging directories, and backup sizes. Preview retention cleanup with `uv run llmwiki runtime prune --keep 10 --dry-run`. Deletion requires the separate `--approve` flag and always retains at least one backup.

Image renditions under `raw/_derived/` are rebuildable. Approved assets under `wiki/assets/` are part of the wiki transaction and must be restored with the matching wiki and catalog backup.
