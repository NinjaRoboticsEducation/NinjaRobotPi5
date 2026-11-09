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
- id: src-20261109-installationguide
  resource: urn:llmwiki:source:src-20261109-installationguide
  title: InstallationGuide.md
  content_hash: sha256:80c8fc5602fa8b63b85f64af6326885b08480906e5bbe00a71feaacb0901cb5e
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
    handoff, and connected welcome/idle refinement evidence (installation guide);
    no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:15d229dc0c812d165197bb7b031d4a32612d013c7f8763e3f12a23e2aeb5faa3
---

# Installation guide

The full guide covers beginner setup, hardware initialization and calibration, startup, and troubleshooting. Hardware commands require stated operator precautions.[^src-20261109-installationguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Browser reconnection, controller handoff, and welcome/idle refinement

The 9 November 2026 revision (`2026-11-09-02`) documents browser disconnect, reconnect, and controller handoff along with connected welcome and idle refinement: when a browser closes its tab/window, navigates away, or loses connectivity, the Agent and ngrok tunnel continue running across all supported Expansion HAT profiles (DFR0566 + X1208, Fusion HAT+, PCA9685). Old commands are rejected and active movement, speech, and capture are cancelled. Clean disconnect reserves the lease until the earlier of its heartbeat deadline and 10 seconds after loss, allowing same-lease reconnection with retained chat identity and disarmed AI motion/camera; unannounced loss is detected by the 15-second heartbeat deadline and watchdog polling (at most one second). After cleanup and reservation expiry, the robot displays a fresh, one-use ngrok pairing QR while waiting for an authenticated browser. Each newly acquired controller lease receives Greeting followed by repeating silent Idle; reconnecting during grace restores Idle without replaying Greeting. Includes step-by-step manual handoff validation procedures (testing exclusive control, reservation expiry, grace reconnect, multi-refresh QR scanning, bounded movement disconnect stop, speech/capture interruption, and explicit remote deactivation). Reconciled with 4 November post-onboarding Fusion HAT+ integration remediation (`fusion-source` cache, Level 1 `/resume`, `/arm`/`/disarm`, Piper TTS provisioning, standalone web power-off helper, web microphone retention until `onend`, 48 kHz voice input), 3 November kernel driver sysfs ownership, non-moving onboarding prerequisites, in-memory calibration draft staging, and earlier checkpoints. Software tests do not substitute for physical hardware validation.[^src-20261109-installationguide]


[^src-20261109-installationguide]: InstallationGuide.md; registered source `src-20261109-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
