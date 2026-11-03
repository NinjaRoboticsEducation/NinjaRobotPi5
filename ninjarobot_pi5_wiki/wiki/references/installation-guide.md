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
- id: src-20261103-installationguide
  resource: urn:llmwiki:source:src-20261103-installationguide
  title: InstallationGuide.md
  content_hash: sha256:82026b1b823dcf781f718cfe49d69b5c89262a95412ea634c3fa931969c9ae84
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-11-03T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 3 November SunFounder Fusion HAT+ kernel
    driver integration and calibration draft staging evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:0f91c02caea148446bf4d3ace073328329131901c7073959de2b4c40dbbbd283
---

# Installation guide

The full guide covers beginner setup, hardware initialization and calibration, startup, and troubleshooting. Hardware commands require stated operator precautions.[^src-20261103-installationguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: SunFounder Fusion HAT+ kernel driver integration and calibration draft staging

The 3 November 2026 revision (`2026-11-03-04`) documents the supported SunFounder **Fusion HAT+ only** path backed exclusively by reviewed kernel driver `1.1.0-ninja1` via sysfs (`/sys/devices/platform/soc/.../pwm/pwmchipX`), eliminating raw userspace I2C writes, address probing, and reset pulsing; `scripts/fusion_hat_setup.py` prepare/preview/install tool with persistent cache recovery (`$HOME/.cache/ninjarobot/fusion-source-recovered`); non-moving onboarding prerequisite validation halting gracefully on missing driver/sysfs paths without tracebacks; in-memory servo calibration draft staging (stage Min/Max/Center in any order with Enter/Space, atomic commit with F requiring `500 <= Min < Center < Max <= 2500` microseconds, discard with Q, clean exit without centering); kernel `voltage_now` battery telemetry (microvolts divided by 1,000,000 once) with distinct `battery_undervoltage` cutoff (6.90 V); orderly web OS shutdown; alongside 2 November runtime remediation (`proxy_headers=False`, transient stop gate clearance, embedded audio kernel node), 25 October Multi-HAT expansion support, default-branch curl bootstrap from GitHub (`INSTALL_REF=HEAD`), onboarding Hardware Expansion Profile Selection menu, flexible Digital header pin assignments for Buzzer and Display, and earlier checkpoints. Software tests do not substitute for physical hardware validation.[^src-20261103-installationguide]


[^src-20261103-installationguide]: InstallationGuide.md, source version `fusion-hat-plus-261103`; registered source `src-20261103-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
