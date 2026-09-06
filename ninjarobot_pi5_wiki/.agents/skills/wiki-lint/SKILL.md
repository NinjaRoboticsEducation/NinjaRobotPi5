---
name: wiki-lint
description: Audit an LLM Wiki for OKF metadata, provenance, links, citations, source drift, semantic review state, and index consistency.
---

# Wiki Lint

## Workflow

1. Run `uv run llmwiki lint` for routine health. Missing semantic reviews on sourced pages and other configured statuses are warnings, so ordinary ingestion stays usable.
2. Run `uv run llmwiki lint --strict` only for a higher-confidence release or when the user explicitly requests the semantic quality gate.
3. For machine-readable output, add `--format json`.
4. Group findings into errors, warnings, and suggestions and explain their practical effect.
5. Use `link check`, `source status`, `runtime status`, `index check`, `stats`, or `review prepare PAGE` for focused diagnosis.
6. Check raw, catalog, page, derived, asset, and semantic-review hashes as one version chain.
7. `uv run llmwiki index build` may repair generated indexes directly. Knowledge-page fixes must use a validated plan and explicit approval.
8. Re-run the same lint mode after any repair.

## Safety rules

- Do not create facts, citations, or review results just to silence lint.
- Missing review means “not semantically reviewed,” not “false.”
- Absolute-language findings are review cues, not automatic proof of error.
- Do not mark a page verified unless a real verification occurred.
- Do not merge or delete pages without a reviewed plan.
- Sourced-unreviewed pages remain valid under normal lint; strict lint requires their semantic review records. Source-free blank drafts remain exempt.
