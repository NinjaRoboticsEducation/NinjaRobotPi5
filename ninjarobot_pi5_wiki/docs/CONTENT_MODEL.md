# Content Model

The `wiki/` folder is an Open Knowledge Format v0.2 bundle. A normal page is Markdown with YAML frontmatter. Its concept ID is its full path inside `wiki/`, without `.md`.

For example, `wiki/concepts/example-concept.md` has the ID `concepts/example-concept`.

## Small page example

```markdown
---
type: Concept
title: Example Concept
description: A small example showing how sourced knowledge is represented.
tags: [example]
status: draft
generated:
  by: codex/example
  at: 2026-08-22T00:00:00Z
sources:
  - id: src-20260822-example-paper
    resource: /references/example-paper.md
    title: Example Paper
    content_hash: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
---

# Example Concept

This sentence makes a source-derived claim.[^src-20260822-example-paper]

See [Related Concept](/concepts/related-concept.md) for a related idea.

[^src-20260822-example-paper]: Example Paper, section 2.
```

`type` is the only field required by OKF itself. This template also warns when ordinary pages omit `title` or `description`, because indexes and people need them.

## Trust and verification

Omit `verified` until a real review occurs. After a review, record the event rather than assigning a vague label:

```yaml
verified:
  - by: human:owner
    at: 2026-08-22T01:00:00Z
```

The CLI displays pages with no event as unverified, machine-only events as machine-confirmed, and at least one `human:` event as human-reviewed. The event records what happened; it is not a guarantee that the page can never become outdated.

## Sources and citations

Register raw evidence before using it. The catalog ID is stable even when the file title changes. A page-level `sources` entry identifies relevant evidence, while a matching Markdown footnote shows which sentence it supports.

For a portable bundle, point a local source resource at its `wiki/references/` page. Include the catalog `content_hash` so lint can prove which registered version the page used. The Reference page should use an immutable file revision URL, or `urn:llmwiki:source:<source-id>` when the original has no public URL.

## Lifecycle

- Use `draft` when a page is incomplete, uncertain, or intentionally under review.
- Use `stable` when the page passes the template's strict publishable-quality lint gate. Stable does not mean human-reviewed; verification remains a separate signal.
- Use `deprecated` when a page remains for history or incoming links but has a replacement.
- `stale_after` is optional. When used, it is an absolute ISO 8601 time; do not write `30d` into a page.

## Image evidence

An image remains an immutable registered source under `raw/media/`. Its Reference page describes direct observations, OCR text, interpretations, limitations, and the exact source hash. A reviewed plan may add a sanitized rendition under `wiki/assets/sources/`:

```markdown
![Useful description of the interface](/assets/sources/src-20260822-interface.png)
```

Successful image decoding, OCR, AI visual description, and human review are different events. Only an actual human review may add a `human:<id>` verification event.

Normal internal links use standard Markdown and include `.md`. The leading `/` means the root of `wiki/`, not the root of the computer.

## Lightweight semantic review

A page may optionally contain one `semantic_review` block. This is a compact evidence-checking record, not a sentence-level claim ledger and not a verification event:

```yaml
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: 2026-08-22T12:00:00Z
  target_hash: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
    - "The page describes documented behavior rather than independently tested behavior."
```

Run `uv run llmwiki review prepare PAGE` to calculate the target hash and print a neutral checklist. The hash covers the page body and meaning-bearing metadata, including source versions, but excludes the review itself and verification history. Meaningful edits therefore make the review stale without creating a self-referencing hash.

Normal lint warns about missing or stale reviews on every sourced page and any additional configured status. `uv run llmwiki lint --strict` turns those review gaps into errors. A source-free blank draft remains exempt, while a sourced draft stays usable under normal lint until it is reviewed. `uv run llmwiki stats` reports sourced-page review coverage. A semantic review never creates `verified` history automatically.
