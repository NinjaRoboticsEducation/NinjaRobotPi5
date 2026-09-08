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
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20260908-developmentguide
  resource: urn:llmwiki:source:src-20260908-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:640cb37251c7d9c7d41a23a4998aa0b25dcbfa8bba952435adeda61f821fd6e6
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-08T15:25:18.461989+00:00'
  target_hash: sha256:60ed284c2e5f7ef83f8cb493852105a696e59d333ec441143bf6db0b6519b99b
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against its registered manual checkpoint and retained source
    text; no human verification is claimed.
  - New checkpoint claims distinguish software tests from physical acceptance, pending
    managed changes and the monetary-budget gap; retained navigation claims remain
    source-supported.
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
an older example as the complete current gate.[^src-20260908-developmentguide][^src-20260907-knowledgeintegration]

[Project overview](/overview.md).


## Limits of the refinement checkpoint

The new manual checkpoint supersedes pre-refinement behavior descriptions.
Current software validation is not physical acceptance. Reminders require a
running service; general requests do not automatically resume; unknown external
effects are not replayed. Memory conflict protection is limited to structured
preferences. Bounded usage does not enforce a currency-denominated spending cap.
Face cleanup and the Traditional Chinese display font remain pending managed
changes. Do not turn these qualifications into a claim that all refinements are
finished.[^src-20260908-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260908-developmentguide]: DevelopmentGuide.md, source version `refinement-phase2-260909`; registered source `src-20260908-developmentguide`.
