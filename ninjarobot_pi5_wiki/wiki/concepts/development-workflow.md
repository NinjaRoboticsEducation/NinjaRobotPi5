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
- id: src-20260912-developmentguide
  resource: urn:llmwiki:source:src-20260912-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:9843060f7eb54f90846eb51f4dac8ab23e1a3d5dae78211a1d2dae4cd198d376
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-12T09:37:00Z'
  target_hash: sha256:f8e4ca0a72d0c56b9c8b42fd8b174fce73b9cce7a60afe2b9f0b0bf9e973f2c2
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered Phase 3 follow-up evidence; no human verification
    is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
---

# Development and documentation workflow

Before significant development, consult the local wiki and current full
manuals, inspect relevant code, and identify missing or conflicting evidence.
The root project policy requires an approved phased plan and preservation of
robot interfaces and managed-driver rules.[^src-20260912-developmentguide]

Feature completion includes a wiki impact assessment. Update affected manual
versions, topic pages, specifications, and architecture guidance, then record
the change and validation in the development log. If no documentation change is
needed, record a specific reason. A new source version preserves the old source;
current navigation and the knowledge map identify the active version.[^src-20260907-knowledgeintegration]

Use the project's maintenance guide outside the knowledge bundle for exact
commands. Prepare a semantic page plan, validate it, show the actual diff, and
apply the approved plan with the wiki CLI. Review source support honestly and
check current pointers, file fingerprints, links, indexes, and review coverage.
AI review is distinct from human verification.[^src-20260907-knowledgeintegration]

[Development guide](/references/development-guide.md) ·
[History](/concepts/development-history.md).

## Phase 3 follow-up consolidation

The current manuals are versioned under `raw/articles/ninjarobotpi5/2026-09-12/`
and `raw/notes/ninjarobotpi5/2026-09-12/`, consolidating Phase 3 local audio and
the Phase 3 follow-up (Bluetooth setup wizard, reconnect helper daemon, lead-in
silence buffer, command-help skill, and CLI `/help` / `/guide` commands). Intermediate
Raspberry Pi OS Lite setup revisions from 9 September (`2026-09-09-03`) are also registered
in the source catalog.[^src-20260912-developmentguide]

Automated validation covers extensive unit tests, compilation, linting, formatting,
type checks, and driver verification gates. Passing software gates does not
substitute for owner physical acceptance testing on real hardware with raised wheels.[^src-20260912-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260912-developmentguide]: DevelopmentGuide.md, source version `refinement-phase3-followup-260912`; registered source `src-20260912-developmentguide`.
