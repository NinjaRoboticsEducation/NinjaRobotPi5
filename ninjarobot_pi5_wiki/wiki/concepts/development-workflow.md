---
type: Concept
title: Development and documentation workflow
description: Retrieve evidence, plan, implement, review wiki impact, version manuals,
  and validate.
status: draft
tags:
- development
- workflow
- documentation
- update
- codex
- claude
- cursor
- antigravity
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20260908-developmentguide
  resource: urn:llmwiki:source:src-20260908-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:640cb37251c7d9c7d41a23a4998aa0b25dcbfa8bba952435adeda61f821fd6e6
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-08T15:25:18.461989+00:00'
  target_hash: sha256:6fb90d4737801aed3be54d072fefda2254692c32487c339fa8faed71bb4457e9
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against its registered manual checkpoint and retained source
    text; no human verification is claimed.
  - New checkpoint claims distinguish software tests from physical acceptance, pending
    managed changes and the monetary-budget gap; retained navigation claims remain
    source-supported.
---

# Development and documentation workflow

Before significant development, consult the local wiki and the current full
manuals, inspect relevant code, and identify missing or conflicting evidence.
The root project policy requires an approved phased plan and preservation of
robot interfaces and managed-driver rules.[^src-20260908-developmentguide]

Feature completion includes a wiki impact assessment. Update affected manual
versions, topic pages, specifications and architecture guidance, then record
the change and validation in the development log. If no documentation change is
needed, record a specific reason. A new source version preserves the old source;
current navigation and the knowledge map identify the active version.[^src-20260907-knowledgeintegration]

Use the project's maintenance guide outside the knowledge bundle for exact
commands. Prepare a semantic page plan, validate it, show the actual diff, and
apply the approved plan with the wiki CLI. Review source support honestly and
check current pointers, file fingerprints, links, indexes and review coverage.
AI review is distinct from human verification.[^src-20260907-knowledgeintegration]

[Development guide](/references/development-guide.md) ·
[History](/concepts/development-history.md).


## Refinement consolidation exception

For this approved refinement, the owner's latest instruction defers documentation
and wiki changes during code implementation, consolidates them at Phase 2, and
pauses before Phase 3. This replaces the earlier all-phases deferral. The old
F02-only wiki proposal is stale. Registered originals stay unchanged, new full
manuals are versioned, and searchable changes use an approved semantic diff.
Software checks do not substitute for owner hardware tests.[^src-20260908-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260908-developmentguide]: DevelopmentGuide.md, source version `refinement-phase2-260909`; registered source `src-20260908-developmentguide`.
