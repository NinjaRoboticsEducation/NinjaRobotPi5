---
type: Reference
title: Development log
description: Find the complete versioned development log.
status: draft
tags:
- ninjarobotpi5
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20261104-developmentlog
  resource: urn:llmwiki:source:src-20261104-developmentlog
  title: DevelopmentLog.md
  content_hash: sha256:4cf5e316ededeb861a25dd0aef7ceb39b39561d9a0784bbcec48595c11b8ae80
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-11-04T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 4 November SunFounder Fusion HAT+ agent
    integration remediation, web microphone lifecycle repair, and documentation reconciliation
    evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:89e32a2b1a7a1631c4890aea4d55c931ea8067cca8bcd4c955519a3bbf6a6fc5
---

# Development log

The complete log preserves dated implementation decisions and validation reports. Historical test results describe their recorded checkout and date; they are not fresh verification.[^src-20261104-developmentlog]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Fusion agent integration remediation and documentation reconciliation

The 4 November 2026 entries record post-onboarding Fusion HAT+ agent integration remediation across four areas: (1) servo control safety latch timestamping, `ServoDevice.status` motion latch exposure, Level 1 `/resume` dispatch, `/arm` and `/disarm` chat commands, signed `-90`..`90` single-servo angle routing, and camera/mic health retry; (2) live `speech_output` runtime awareness, `--install-piper` voice provisioning, and `memory-notice` turn filtering; (3) standalone `install-poweroff` helper deployment and LAN session pairing; (4) browser microphone session retention until `onend`, HTTP push-to-talk fallback, 48 kHz chunk scaling, `PaErrorCode -9985` retry, ALSA overflow tolerance, Whisper `[BLANK_AUDIO]` re-arm, and audio child process stdin closure cleanup. All 1,141 main tests and driver suites passed across separate processes without live actuator movement. Validation recorded in `docs/project-history/NinjaSunFounderIntegrationAudit_261104.md`, `docs/validation/web_mic_lifecycle_261104.md`, and `docs/validation/documentation_reconciliation_261104.md`, alongside 3 November SunFounder Fusion HAT+ integration and follow-up repairs (`docs/validation/fusion_implementation_261103.md`, `fusion_prerequisite_repair_261103.md`, `fusion_source_preparation_repair_261103.md`, `fusion_calibration_draft_repair_261103.md`), 2 November runtime remediation, 25 October Multi-HAT expansion upgrade, 23 September onboarding refinements, 22 September guided onboarding, 18 September web controller dual views, 17 September calendar setup and unified CONFIRM authorization, 15–16 September distance game and servo repairs, Phase 4 information services, Phase 4 foundations, and system clock access.[^src-20261104-developmentlog]


[^src-20261104-developmentlog]: DevelopmentLog.md, source version `fusion-agent-remediation-261104`; registered source `src-20261104-developmentlog`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
