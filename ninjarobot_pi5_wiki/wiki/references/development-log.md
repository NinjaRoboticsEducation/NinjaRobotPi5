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
- id: src-20261109-developmentlog
  resource: urn:llmwiki:source:src-20261109-developmentlog
  title: DevelopmentLog.md
  content_hash: sha256:c4a0fab292e729b1edafcd2a8039a65cdd63c1bdd8e18970a4d6c370afed2214
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-11-09T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 9 November browser reconnection, controller
    handoff, and connected welcome/idle refinement evidence (development log); no
    human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:75937302fad3de39272f1c133f600131622f62387b9e1ffe80fbbe295cd656fb
---

# Development log

The complete log preserves dated implementation decisions and validation reports. Historical test results describe their recorded checkout and date; they are not fresh verification.[^src-20261109-developmentlog]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Browser reconnection, controller handoff, and welcome/idle refinement

The 9 November 2026 entries record two milestones: (1) Welcome and connected Idle refinement follow-up: converted per-service Greeting suppression to per-controller-lease welcome coordinator in `onboarding.py`; lease and heartbeat processing continue during tracked cancellable welcome task while normal actions wait; delayed remote events verify endpoint generation before revoking live browsers; interrupted welcome does not suppress first successful startup completion; and same-lease grace reconnect restores Idle. Passed 1,157 root tests and all six managed suites. (2) Browser reconnection: implemented serialized lease cleanup, attachment generations, immediate revocation, automatic pairing QR redisplay, durable waiting display reservation, endpoint invalidation, and browser departure/Back-Forward recovery. Commands from lost connections are rejected and active requests, movement, speech, and capture are cancelled; clean disconnect reserves lease for up to 10 seconds (or heartbeat deadline) for same-browser reconnect without action replay; unannounced loss detected by 15s heartbeat deadline and watchdog polling. Passed 1,152 root tests and managed driver suites across separate processes without live actuator movement. Consolidates 4 November Fusion HAT+ agent integration remediation (safety latch timestamping, `ServoDevice.status` motion latch exposure, Level 1 `/resume` dispatch, `/arm`/`/disarm` commands, signed `-90`..`90` single-servo routing, live `speech_output`, Piper TTS provisioning, standalone `install-poweroff` helper, browser microphone retention until `onend`, 48 kHz chunk scaling), 3 November Fusion HAT+ kernel integration and in-memory calibration draft staging, 2 November runtime remediation, 25 October Multi-HAT expansion upgrade, and earlier checkpoints.[^src-20261109-developmentlog]


[^src-20261109-developmentlog]: DevelopmentLog.md; registered source `src-20261109-developmentlog`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
