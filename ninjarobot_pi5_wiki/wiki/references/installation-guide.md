---
type: Reference
title: Installation guide
description: Find the complete versioned installation guide.
status: draft
tags:
- ninjarobotpi5
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260923-installationguide-2
  resource: urn:llmwiki:source:src-20260923-installationguide-2
  title: InstallationGuide.md
  content_hash: sha256:d08eb44241ce1a46f5e9e0e9df149cd293fb817c0bd4fe0a4c43dde47ee5d6ca
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
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
  target_hash: sha256:4bcf729d99e1ed7ba2c10e35ec375f108a394ac7b3642e08b0ab0d823eef2db7
---

# Installation guide

The full guide covers beginner setup, hardware initialization and calibration, startup, and troubleshooting. Hardware commands require stated operator precautions.[^src-20260923-installationguide-2]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Refined onboarding, bulk settings reuse, and installer repairs

The 23 September 2026 revisions (`2026-09-23` and `2026-09-23-02`) document the root installer curl streaming
bootstrap with revision branch disambiguation and `--install-dir` custom installation path support, `/dev/tty`
controlling terminal confirmation, `ninjarobot onboard` refinements (ASCII NINJAROBOT welcome screen, numeric menus,
bulk settings reuse option "2) Apply existing settings for all modules", automatic configuration checks, Enter-to-continue
summaries, and removal of redundant typed YES/APPLY phrases), Mac SSH port forwarding for Google Calendar OAuth
(`ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765`), waiting updates, callback receipt acknowledgment,
end-to-end read-only Calendar MCP validation, candidate credential cleanup, key rollback, alongside 22 September
guided onboarding, prompt-toolkit multiline chat, 18 September web controller dual-view interface, 17 September Google
Calendar guided authorization and unified `CONFIRM` / `CANCEL` chat authorization, 16 September distance game hand-placement
procedure, Phase 4 information setup, Phase 4 foundations, and headless Lite audio with Bluetooth wizard. Software tests
do not substitute for physical hardware validation.[^src-20260923-installationguide-2]


[^src-20260923-installationguide-2]: InstallationGuide.md, source version `onboarding-refinement-260923`; registered source `src-20260923-installationguide-2`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
