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
- id: src-20260906-developmentguide
  resource: urn:llmwiki:source:src-20260906-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-07T00:45:19Z'
  target_hash: sha256:bd0acfbe3e2dd04f8011e991bed09941a8bde1b6f2d3686aec176e84bf869eb2
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Rechecked the navigation-only correction and updated source versions; other cited
    explanations are unchanged.
  - AI evidence review; no human verification or hardware test is claimed.
---

# Development and documentation workflow

Before significant development, consult the local wiki and the current full
manuals, inspect relevant code, and identify missing or conflicting evidence.
The root project policy requires an approved phased plan and preservation of
robot interfaces and managed-driver rules.[^src-20260906-developmentguide]

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


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.
