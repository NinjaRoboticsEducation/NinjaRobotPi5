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
- phase3
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
  target_hash: sha256:258b04ad3ea7e9c557eb9c9debcf29d5d0e661817c920b63ea59babef8140904
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
an older example as the complete current gate.[^src-20260912-developmentguide][^src-20260907-knowledgeintegration]

[Project overview](/overview.md).

## Limits of the Phase 3 follow-up checkpoint

The current manual checkpoint supersedes pre-Phase 3 behavior descriptions.
Current software validation is not physical acceptance. Raspberry Pi 5 audio
playback, Bluetooth RF pairing, and speaker latency require physical testing.
Reminders require a running service; general requests do not automatically resume;
unknown external effects are not replayed.[^src-20260912-developmentguide]

Headless Lite audio configuration depends on WirePlumber version (0.4 vs 0.5+)
and user session lingering. Memory conflict protection is limited to structured
preferences. Bounded model usage does not enforce a currency-denominated spending cap.
Face cleanup and the Traditional Chinese display font remain pending managed changes.
Do not turn these qualifications into a claim that physical hardware acceptance is complete.[^src-20260912-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260912-developmentguide]: DevelopmentGuide.md, source version `refinement-phase3-followup-260912`; registered source `src-20260912-developmentguide`.
