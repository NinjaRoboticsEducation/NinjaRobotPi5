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
- id: src-20261104-installationguide
  resource: urn:llmwiki:source:src-20261104-installationguide
  title: InstallationGuide.md
  content_hash: sha256:2851ccda47e03c5c0e703cb58c528a905b2de3eb0c8315e5328d19d1a2ac8175
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
  target_hash: sha256:89bdc485bc727a0f371c4f981cdfc03648302338ae53e16f189083fa240428d8
---

# Installation guide

The full guide covers beginner setup, hardware initialization and calibration, startup, and troubleshooting. Hardware commands require stated operator precautions.[^src-20261104-installationguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Fusion agent integration remediation and documentation reconciliation

The 4 November 2026 revision (`2026-11-04-03`) documents the current user workflow and post-onboarding Fusion HAT+ integration remediation: persistent cache path `$HOME/.cache/ninjarobot/fusion-source` for `scripts/fusion_hat_setup.py`; Level 1 `/resume` and `/arm`/`/disarm` commands; Piper TTS automated provisioning (`scripts/prepare_speech_voice.py --install-piper --configure --apply`); standalone power-off helper installation (`ninjarobot-agent deployment install-poweroff --confirm`); web microphone lifecycle awaiting `onend` with LAN HTTP push-to-talk fallback; 48 kHz voice input stability; alongside the supported SunFounder **Fusion HAT+ only** path backed exclusively by reviewed kernel driver `1.1.0-ninja1` via sysfs (`/sys/devices/platform/soc/.../pwm/pwmchipX`), eliminating raw userspace I2C writes, address probing, and reset pulsing; non-moving onboarding prerequisite validation halting gracefully on missing driver/sysfs paths without tracebacks; in-memory servo calibration draft staging (stage Min/Max/Center in any order with Enter/Space, atomic commit with F requiring `500 <= Min < Center < Max <= 2500` microseconds, discard with Q, clean exit without centering); kernel `voltage_now` battery telemetry (microvolts divided by 1,000,000 once) with distinct `battery_undervoltage` cutoff (6.90 V); orderly web OS shutdown; alongside 2 November runtime remediation (`proxy_headers=False`, transient stop gate clearance, embedded audio kernel node), 25 October Multi-HAT expansion support, default-branch curl bootstrap from GitHub (`INSTALL_REF=HEAD`), onboarding Hardware Expansion Profile Selection menu, flexible Digital header pin assignments for Buzzer and Display, and earlier checkpoints. Software tests do not substitute for physical hardware validation.[^src-20261104-installationguide]


[^src-20261104-installationguide]: InstallationGuide.md, source version `fusion-agent-remediation-261104`; registered source `src-20261104-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
