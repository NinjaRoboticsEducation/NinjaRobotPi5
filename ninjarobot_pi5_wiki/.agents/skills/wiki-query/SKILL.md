---
name: wiki-query
description: Answer questions from the local LLM Wiki with traceable page and source references. Use for research, lookup, summaries, comparisons, and finding gaps without changing the wiki.
---

# Wiki Query

This is a read-only workflow unless the user separately asks to capture new knowledge.

## Workflow

1. Search with `uv run llmwiki search "QUESTION OR KEYWORDS"`.
2. Open the strongest matching pages and follow their normal Markdown links.
3. Check each page's status, trust level, source-version hashes, provenance, and cited source records. Check optional freshness when present.
4. Prefer version-current material. Clearly label draft, stale, conflicting, OCR-only, visually unreviewed, semantically unreviewed, stale-review, concern, or weakly sourced claims.
5. Answer in plain language and name the local pages and sources that support the answer.
6. If the wiki does not contain enough evidence, say what is missing. Do not fill the gap from memory while presenting it as wiki knowledge.

## Capturing New Knowledge

If the user wants the answer saved, switch to the `wiki-ingest` workflow. Create a plan, show its diff, and wait for explicit approval before changing files.
