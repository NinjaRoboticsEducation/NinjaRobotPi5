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
- id: src-20260923-developmentguide-2
  resource: urn:llmwiki:source:src-20260923-developmentguide-2
  title: DevelopmentGuide.md
  content_hash: sha256:17ba019c024248a5273bf2de3124d7fd62421e82ec2554cd3f756248ebd7ace5
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
  target_hash: sha256:cc7282c04370a8124fd92e51aac9458335906dcfd8956f62be055e7cc62df8e1
---

# Development guide

The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20260923-developmentguide-2]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Refined onboarding, bulk settings reuse, and installer repairs

The 23 September 2026 revision (`2026-09-23-02`) documents the refined `setup_wizard.py` orchestration layer,
bulk hardware settings reuse calling `hardware_setup_status`, isolated microphone asset checking via the
`ninjarobot_pi5_ide.hardware_config_probe` subprocess (preserving microphone runtime containment), offline simulation
rehearsal isolation, `--resume` rechecking saved settings, Google Calendar OAuth output callbacks, Mac loopback SSH
forwarding (`ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765`), waiting updates, callback receipt
acknowledgment, end-to-end read-only Calendar MCP validation, candidate credential cleanup, secret rollback on save failure,
and bootstrap revision disambiguation and `--install-dir` support, alongside 22 September guided onboarding and prompt-toolkit
chat, 18 September web controller dual-view architecture, 17 September calendar setup and unified `CONFIRM` / `CANCEL`
flow, 15–16 September distance game and servo repairs, Phase 4 information services (T04 calendar, T05 research, T06
notes/checklists/briefings, migration 7), Phase 4 foundations, and system clock access.[^src-20260923-developmentguide-2]


[^src-20260923-developmentguide-2]: DevelopmentGuide.md, source version `onboarding-refinement-260923`; registered source `src-20260923-developmentguide-2`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
