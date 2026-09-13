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
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20260913-developmentguide
  resource: urn:llmwiki:source:src-20260913-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:f6ae6ee1dfe85488f3db13c1d6cc927802d92610860605bd42229d6a3a1d53bf
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-13T14:15:00Z'
  target_hash: sha256:580b3efc966d170b6092a5fcad868ee1a5b7104ddda8fedf442503fafee89d1b
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered Phase 4 information evidence; no human verification
    is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
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
an older example as the complete current gate.[^src-20260913-developmentguide][^src-20260907-knowledgeintegration]

[Project overview](/overview.md).

## Limits of recent checkpoints (Phase 4 and Phase 5)

The current manual checkpoint (`2026-09-13-03`) consolidates system time access,
Phase 5 foundations, and Phase 4 information work. Software validation is not physical
acceptance:[^src-20260913-developmentguide]
- **Clock**: `system.time.get` reads local OS clock; it does not set the clock or verify NTP synchronization.[^src-20260913-developmentguide]
- **Phase 5 distance game**: Tested on fake devices; physical 200 ms sensor loop timing, buzzer audibility, and wheel raised state require physical verification. Hardware proposals (movable head, edge sensors, touch) are uninstalled concepts.[^src-20260913-developmentguide]
- **Phase 4 calendar and research**: Google Calendar requires user SSH loopback OAuth; read-only default; write operations require explicit user confirmation. Tavily search snippet citations provide evidence links but do not certify external factual truth.[^src-20260913-developmentguide]
- **Model boundaries**: Request budgets, prompt tokens, and execution bounds do not enforce a currency-denominated spending cap. Display font repair and physical acceptance remain open.[^src-20260913-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260913-developmentguide]: DevelopmentGuide.md, source version `refinement-phase4-information-260913`; registered source `src-20260913-developmentguide`.
