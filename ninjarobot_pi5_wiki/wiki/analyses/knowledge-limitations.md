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
- expansion-hat
- sunfounder
- pca9685
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20261027-developmentguide
  resource: urn:llmwiki:source:src-20261027-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:3ab4adc6f8052f7975b17a7ebcdd893df425e47b9f16e2127a2751f71d9e73c7
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-10-27T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 25 October multi-HAT expansion and SunFounder
    hardware audit evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:e3e1e3d618c0b6bd807a3bb916b663fd975c11ea37bce0280866c11fdedc5f1a
---

# Knowledge limitations and verification

Keyword search covers curated pages rather than all raw manual text. It does not
follow citations for the caller. Try focused terms, read the overview, and open
full sources. Search expiry flags, source fingerprints, and semantic review
status are separate signals and must be checked together.[^src-20260907-knowledgeintegration]

A missing result is an evidence gap, not proof a feature is absent. A page can be
structually valid while its explanation needs review. Current implementation
fingerprints identify files needing knowledge review but cannot prove that prose
is correct. AI-reviewed pages are not human-verified or hardware-tested pages.
Editor adapters need actual session activation checks; a wiki-only workspace may
not expose parent robot code.[^src-20260907-knowledgeintegration]

The development guide's older quality-gate example uses narrower lint paths than
the current root policy. Follow the root operating policy for the current full
checks, and preserve the source's historical context rather than silently treating
an older example as the complete current gate.[^src-20261027-developmentguide][^src-20260907-knowledgeintegration]

[Project overview](/overview.md).

## Limits of recent checkpoints (Multi-HAT Expansion, Onboarding Refinement, Phase 4, Phase 5, Calendar, and UI refinement)

The current manual checkpoint (`2026-10-25`) consolidates multi-HAT expansion support and SunFounder hardware audit alongside system time access, Phase 4 information work, 15–16 September distance game/servo repairs, 17 September Google Calendar setup and unified CONFIRM flow, 18 September UI refinement, 22 September guided onboarding, curl bootstrap, and editable chat, and 23 September onboarding refinements and installer repairs. Software validation is not physical acceptance:[^src-20261027-developmentguide]
- **Multi-HAT expansion & hardware support**: Dual `0x14`/`0x17` MCU auto-fallback, PCA9685 endpoint mapping, embedded I2S speaker amplifier control, and battery fuel gauge monitoring passed 1,087 synthetic software tests and 139 driver unit tests. Physical validation on a physical SunFounder Robot HAT or PCA9685 HAT requires raised wheels, power precautions, and live acoustic speaker checks.[^src-20261027-developmentguide]
- **Guided onboarding & bulk reuse**: Automatic configuration checks verify saved setting files, but do not certify live physical device operation or motor movement; raised wheels remain mandatory for servo testing; camera/mic privacy consent choices remain manual operator decisions. Google Calendar Mac SSH tunnel (`-L 127.0.0.1:8765:127.0.0.1:8765`) and live account authorization require user browser interaction. Simulated verification records never satisfy real-hardware readiness. External Calendar MCP tests are read-only and separate from the native Calendar feature. Microphone configuration probe subprocess does not record, transcribe, or run inference.[^src-20261027-developmentguide]
- **Web interface refinement & IDE menu**: UI components, websocket event messaging, user-behavior execution modals, and terminal menu consolidation have passed 125 automated unit tests and mock validations; physical acceptance on mobile devices over real Wi-Fi networks and touch-screen D-pad latency require live operator verification.[^src-20261027-developmentguide]
- **Clock**: `system.time.get` reads local OS clock; it does not set the clock or verify NTP synchronization.[^src-20261027-developmentguide]
- **Distance game hand placement**: Tested against unit and mock suites; hand placement timing (5–60 cm immediately at request time, before final chat response) and buzzer audibility require live physical verification. Hardware proposals (movable head, edge sensors, touch) are uninstalled concepts.[^src-20261027-developmentguide]
- **Phase 4 calendar and research**: Google Calendar requires user SSH loopback OAuth (port 8765); read-only default; write operations require `--write` and plain single-word `CONFIRM`. Preparing a create preview does not perform Google write operations; software mock gates do not guarantee Google API acceptance or handle account-level quota issues. Tavily search snippet citations provide evidence links but do not certify external factual truth.[^src-20261027-developmentguide]
- **Project help**: Runtime document section hashes ensure published section integrity, but cannot guarantee factual perfection of upstream documentation.[^src-20261027-developmentguide]
- **Model boundaries**: Rolling transcript suffix truncation preserves safety context and fits provider request character caps, but does not enforce a currency-denominated spending cap. Display font repair and physical acceptance remain open.[^src-20261027-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20261027-developmentguide]: DevelopmentGuide.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-developmentguide`.
