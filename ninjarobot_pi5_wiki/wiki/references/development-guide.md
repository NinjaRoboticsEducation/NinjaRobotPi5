---
type: Reference
title: Development guide
description: Find the complete versioned development guide.
status: draft
tags:
- ninjarobotpi5
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260918-developmentguide
  resource: urn:llmwiki:source:src-20260918-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:a4295e369acd972b74b34383683623b37ef8a1a4cf1d2e066c50d7d4fc6ec649
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
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
  target_hash: sha256:98bbbc00efc81674476132a5726eb3001637304dba14c81ed0df61eab7b09fc8
---

# Development guide

The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20260918-developmentguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Web interface refinement, modular frontend, and terminal menu consolidation

The 18 September 2026 revision (`2026-09-18`) documents the dual-page web interface (`/agent`
and `/gamepad`), modular frontend scripts (`app-shared.js`, `app-gamepad.js`, `app-agent.js`),
user-created behavior execution with motion safety confirmation modals, high-contrast button styling
and toggle states (A/B/X/Y and audio controls), 4-language i18n parity, and IDE terminal menu
restructuring (options 1–5, Q), alongside 17 September calendar setup and unified `CONFIRM` / `CANCEL`
flow, 15–16 September distance game and servo repairs, Phase 4 information services (T04 calendar,
T05 research, T06 notes/checklists/briefings, `InformationStore`, `InformationControls`, migration 7),
Phase 4 foundations, and system clock access.[^src-20260918-developmentguide]


[^src-20260918-developmentguide]: DevelopmentGuide.md, source version `ui-refinement-260918`; registered source `src-20260918-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
