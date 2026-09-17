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
- id: src-20260917-developmentguide
  resource: urn:llmwiki:source:src-20260917-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:55b061c1a72d4b5f81693f83f2ae39200ff8ed7ea992645e83e661ac5efcd0f0
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
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
  target_hash: sha256:719d653a904c9e1cf17b4cd1fb4d2351f86a6f98ef5af6d0e1e4c9a5108f2d10
---

# Development guide

The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20260917-developmentguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Calendar guided setup, unified CONFIRM flow, and project help

The 17 September 2026 revision (`2026-09-17-03`) details the implementation map for
`calendar_chat.py` unified single-word `CONFIRM` / `CANCEL` flow across event create,
update, and delete (strictly rejecting command bypasses), field-specific preview errors,
Google Calendar service primary-calendar auto-discovery and token reuse, and `project_documents.py`
hash-checked bounded sections for runtime public help, alongside 15–16 September distance game
and servo repairs, Phase 4 information services (T04 calendar, T05 research, T06 notes/checklists/briefings,
`InformationStore`, `InformationControls`, migration 7), Phase 4 foundations, and system clock access.[^src-20260917-developmentguide]


[^src-20260917-developmentguide]: DevelopmentGuide.md, source version `calendar-confirm-260917`; registered source `src-20260917-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
