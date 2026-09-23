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
- ui-refinement
- onboarding
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20260923-developmentguide-2
  resource: urn:llmwiki:source:src-20260923-developmentguide-2
  title: DevelopmentGuide.md
  content_hash: sha256:17ba019c024248a5273bf2de3124d7fd62421e82ec2554cd3f756248ebd7ace5
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-23T00:30:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 23 September onboarding refinement, bulk
    settings reuse, Mac Calendar OAuth SSH tunnel, and installer repair evidence; no human
    verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:694ca7dcfe56c0fe85ca96ea03625ca32e82086c098414fce66422be749a2546
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
an older example as the complete current gate.[^src-20260923-developmentguide-2][^src-20260907-knowledgeintegration]

[Project overview](/overview.md).

## Limits of recent checkpoints (Phase 4, Phase 5, Calendar, UI refinement, Guided Onboarding, and Onboarding Refinement)

The current manual checkpoint (`2026-09-23-02`) consolidates system time access,
Phase 4 information work, 15–16 September distance game/servo repairs, 17 September
Google Calendar setup and unified CONFIRM flow, 18 September UI refinement, 22 September guided onboarding, curl bootstrap, and editable chat, and 23 September onboarding refinements and installer repairs. Software validation is not physical acceptance:[^src-20260923-developmentguide-2]
- **Guided onboarding & bulk reuse**: Automatic configuration checks verify saved setting files, but do not certify live physical device operation or motor movement; raised wheels remain mandatory for servo testing; camera/mic privacy consent choices remain manual operator decisions. Google Calendar Mac SSH tunnel (`-L 127.0.0.1:8765:127.0.0.1:8765`) and live account authorization require user browser interaction. Simulated verification records never satisfy real-hardware readiness. External Calendar MCP tests are read-only and separate from the native Calendar feature. Microphone configuration probe subprocess does not record, transcribe, or run inference.[^src-20260923-developmentguide-2]
- **Web interface refinement & IDE menu**: UI components, websocket event messaging, user-behavior execution modals, and terminal menu consolidation have passed 125 automated unit tests and mock validations; physical acceptance on mobile devices over real Wi-Fi networks and touch-screen D-pad latency require live operator verification.[^src-20260923-developmentguide-2]
- **Clock**: `system.time.get` reads local OS clock; it does not set the clock or verify NTP synchronization.[^src-20260923-developmentguide-2]
- **Distance game hand placement**: Tested against unit and mock suites; hand placement timing (5–60 cm immediately at request time, before final chat response) and buzzer audibility require live physical verification. Hardware proposals (movable head, edge sensors, touch) are uninstalled concepts.[^src-20260923-developmentguide-2]
- **Phase 4 calendar and research**: Google Calendar requires user SSH loopback OAuth (port 8765); read-only default; write operations require `--write` and plain single-word `CONFIRM`. Preparing a create preview does not perform Google write operations; software mock gates do not guarantee Google API acceptance or handle account-level quota issues. Tavily search snippet citations provide evidence links but do not certify external factual truth.[^src-20260923-developmentguide-2]
- **Project help**: Runtime document section hashes ensure published section integrity, but cannot guarantee factual perfection of upstream documentation.[^src-20260923-developmentguide-2]
- **Model boundaries**: Rolling transcript suffix truncation preserves safety context and fits provider request character caps, but does not enforce a currency-denominated spending cap. Display font repair and physical acceptance remain open.[^src-20260923-developmentguide-2]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260923-developmentguide-2]: DevelopmentGuide.md, source version `onboarding-refinement-260923`; registered source `src-20260923-developmentguide-2`.
