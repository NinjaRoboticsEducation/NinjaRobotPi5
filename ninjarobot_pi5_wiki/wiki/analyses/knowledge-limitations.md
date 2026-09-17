---
type: Analysis
title: Knowledge limitations and verification
description: Search gaps, stale evidence, source versions, editor access, and review
  boundaries.
status: draft
tags:
- limitations
- stale
- verification
- search
- known
- issues
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
  target_hash: sha256:f73097d6914154c141e9366afc2dd9fe01a14198ce93ead4ab1e7dfef3d61c8c
---

# Knowledge limitations and verification

Keyword search covers curated pages rather than all raw manual text. It does not
follow citations for the caller. Try focused terms, read the overview, and open
full sources. Search expiry flags, source fingerprints, and semantic review
status are separate signals and must be checked together.[^src-20260907-knowledgeintegration]

A missing result is an evidence gap, not proof a feature is absent. A page can be
structurally valid while its explanation needs review. Current implementation
fingerprints identify files needing knowledge review but cannot prove that prose
is correct. AI-reviewed pages are not human-verified or hardware-tested pages.
Editor adapters need actual session activation checks; a wiki-only workspace may
not expose parent robot code.[^src-20260907-knowledgeintegration]

The development guide's older quality-gate example uses narrower lint paths than
the current root policy. Follow the root operating policy for the current full
checks, and preserve the source's historical context rather than silently treating
an older example as the complete current gate.[^src-20260917-developmentguide][^src-20260907-knowledgeintegration]

[Project overview](/overview.md).

## Limits of recent checkpoints (Phase 4, Phase 5, and Calendar follow-up)

The current manual checkpoint (`2026-09-17-03`) consolidates system time access,
Phase 4 information work, 15–16 September distance game/servo repairs, and 17 September
Google Calendar setup and unified CONFIRM flow. Software validation is not physical acceptance:[^src-20260917-developmentguide]
- **Clock**: `system.time.get` reads local OS clock; it does not set the clock or verify NTP synchronization.[^src-20260917-developmentguide]
- **Distance game hand placement**: Tested against unit and mock suites; hand placement timing (5–60 cm immediately at request time, before final chat response) and buzzer audibility require live physical verification. Hardware proposals (movable head, edge sensors, touch) are uninstalled concepts.[^src-20260917-developmentguide]
- **Phase 4 calendar and research**: Google Calendar requires user SSH loopback OAuth (port 8765); read-only default; write operations require `--write` and plain single-word `CONFIRM`. Preparing a create preview does not perform Google write operations; software mock gates do not guarantee Google API acceptance or handle account-level quota issues. Tavily search snippet citations provide evidence links but do not certify external factual truth.[^src-20260917-developmentguide]
- **Project help**: Runtime document section hashes ensure published section integrity, but cannot guarantee factual perfection of upstream documentation.[^src-20260917-developmentguide]
- **Model boundaries**: Rolling transcript suffix truncation preserves safety context and fits provider request character caps, but does not enforce a currency-denominated spending cap. Display font repair and physical acceptance remain open.[^src-20260917-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260917-developmentguide]: DevelopmentGuide.md, source version `calendar-confirm-260917`; registered source `src-20260917-developmentguide`.
