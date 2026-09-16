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
- id: src-20260916-developmentguide
  resource: urn:llmwiki:source:src-20260916-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:3630ca96f9314ad2d253476a2131e1160f87fe3c0bdae3f10ed5c89f85ae21e0
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-16T00:26:00Z'
  target_hash: sha256:053be363f9f926209699f9c90cd148b7568e48d5daab215023511e6a957b56cc
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 16 September distance game and follow-up
    evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
---

# Development guide

The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20260916-developmentguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: distance game hand-placement correction and follow-up repairs

The 16 September 2026 revision (`2026-09-16`) details the implementation map for
the distance game hand-placement timing correction and 15 September follow-up repairs
(`servo.stop` priority allowlist with LOW risk rating, rolling context in `AgentLoop`,
default distance game enablement, servo ramp stop cause preservation, bounded distance
preparation/recovery, repeated-game buzzer preparation, and cleanup watchdog heartbeats),
alongside Phase 4 information services (T04 calendar, T05 research, T06 notes/checklists/briefings,
`InformationStore`, `InformationControls`, migration 7), Phase 4 foundations, and system clock access.[^src-20260916-developmentguide]


[^src-20260916-developmentguide]: DevelopmentGuide.md, source version `distance-game-hand-placement-260916`; registered source `src-20260916-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
