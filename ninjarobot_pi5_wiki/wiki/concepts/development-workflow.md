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
- phase4
- phase5
- calendar
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20260917-developmentguide
  resource: urn:llmwiki:source:src-20260917-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:55b061c1a72d4b5f81693f83f2ae39200ff8ed7ea992645e83e661ac5efcd0f0
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-17T15:40:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 17 September calendar CONFIRM flow, guided
    authorization, and project help evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
  target_hash: sha256:03ba30cf1d4432a0d214a539c47565e3911791853105cc0f685d6d92bdf2a6fa
---

# Development and documentation workflow

Before significant development, consult the local wiki and current full
manuals, inspect relevant code, and identify missing or conflicting evidence.
The root project policy requires an approved phased plan and preservation of
robot interfaces and managed-driver rules.[^src-20260917-developmentguide]

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

## Milestones and source consolidation

The active manuals are versioned under `raw/articles/ninjarobotpi5/2026-09-17-03/`
and `raw/notes/ninjarobotpi5/2026-09-17-03/`. This version consolidates:
1. System clock access (`/time` and `system.time.get`, `2026-09-12-02`),
2. Refinement Phase 5 software foundations and distance game (`2026-09-13`),
3. Narrowed Phase 4 foundations (M03 memory ranking, M04 read-only recipes, X01 v2 skills, X05 help, `2026-09-13-02`),
4. Completed Phase 4 information assistant (T04 calendar, T05 research, T06 notes/checklists/briefings, `2026-09-13-03`),
5. Servo stop priority allowlist (LOW risk), rolling chat context, and default distance game (`2026-09-15`),
6. Approved servo and sensor recovery repair with stop cause preservation (`2026-09-15-02`),
7. Web controller admission fix, repeated-game buzzer preparation, and cleanup watchdog heartbeat (`2026-09-15-03`),
8. Distance game hand-placement timing correction and out-of-range sensor handling (`2026-09-16`),
9. Google Calendar guided OAuth setup with primary-calendar discovery and port 8765 loopback SSH tunnel (`2026-09-17`),
10. Field-specific preview validation errors and plain `CONFIRM` / `CANCEL` chat authorization for calendar writes,
11. Unified single-word `CONFIRM` flow across event create, update, and delete, eliminating direct command confirmation bypasses, and
12. Hash-checked runtime public project help with bounded sections (`project_documents.py`, `project_help_sources.json`).[^src-20260917-developmentguide]

Automated validation covers extensive unit tests, compilation, linting, formatting,
type checks, and driver verification gates. Passing software gates does not
substitute for owner physical acceptance testing on real hardware with raised wheels.[^src-20260917-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260917-developmentguide]: DevelopmentGuide.md, source version `calendar-confirm-260917`; registered source `src-20260917-developmentguide`.
