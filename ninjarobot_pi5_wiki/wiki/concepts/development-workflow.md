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
- ui-refinement
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20260918-developmentguide
  resource: urn:llmwiki:source:src-20260918-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:a4295e369acd972b74b34383683623b37ef8a1a4cf1d2e066c50d7d4fc6ec649
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-18T16:50:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 18 September UI refinement, modular web
    frontend, and terminal menu consolidation evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair, monetary spending cap, and physical mobile Wi-Fi
    checks.
  target_hash: sha256:c00b22c04962bd09c2f003101873eed53f7afe10311cba836ec960c88a3e6685
---

# Development and documentation workflow

Before significant development, consult the local wiki and current full
manuals, inspect relevant code, and identify missing or conflicting evidence.
The root project policy requires an approved phased plan and preservation of
robot interfaces and managed-driver rules.[^src-20260918-developmentguide]

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

The active manuals are versioned under `raw/articles/ninjarobotpi5/2026-09-18/`
and `raw/notes/ninjarobotpi5/2026-09-18/`. This version consolidates:
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
11. Unified single-word `CONFIRM` flow across event create, update, and delete, eliminating direct command confirmation bypasses,
12. Hash-checked runtime public project help with bounded sections (`project_documents.py`, `project_help_sources.json`), and
13. Web interface refinement into dedicated Game Pad and Agent Interface surfaces, modular frontend (`app-shared.js`, `app-gamepad.js`, `app-agent.js`), user-created behavior execution with motion safety modals, button toggle states, 4-language i18n parity, and IDE terminal menu consolidation (1–5, Q, `2026-09-18`).[^src-20260918-developmentguide]

Automated validation covers extensive unit tests, compilation, linting, formatting,
type checks, and driver verification gates. Passing software gates does not
substitute for owner physical acceptance testing on real hardware with raised wheels.[^src-20260918-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260918-developmentguide]: DevelopmentGuide.md, source version `ui-refinement-260918`; registered source `src-20260918-developmentguide`.
