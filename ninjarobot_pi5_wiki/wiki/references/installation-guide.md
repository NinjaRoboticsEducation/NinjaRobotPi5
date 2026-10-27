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
- id: src-20261027-installationguide
  resource: urn:llmwiki:source:src-20261027-installationguide
  title: InstallationGuide.md
  content_hash: sha256:39799fdf6b229fb7fb64288bf54c1339ac110a3a173af9b6f48c846ec9304065
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
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
  target_hash: sha256:04a71262fed5307f0ee24555222fc25202a2e9743187e2e3b98f537f902f36f1
---

# Installation guide

The full guide covers beginner setup, hardware initialization and calibration, startup, and troubleshooting. Hardware commands require stated operator precautions.[^src-20261027-installationguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Multi-HAT expansion support and SunFounder hardware audit

The 25 October 2026 revision (`2026-10-25`) documents support for three Raspberry Pi 5 Expansion HAT profiles
(DFRobot DFR0566 IO Expansion HAT + Geekworm X1208 UPS, SunFounder Robot HAT v4 `0x14` and Fusion HAT / Robot HAT v5 `0x17` with
auto-detection and fallback, and General PCA9685 PWM Expansion HAT `0x40`), default-branch cURL bootstrap from GitHub (`INSTALL_REF=HEAD`),
onboarding Hardware Expansion Profile Selection menu with automatic preset writing to `servo.json` and sync via `config import`,
SunFounder Embedded Speaker Initialization and verification chime (without Bluetooth prompt), flexible Digital header pin
assignments for Buzzer (`17, 4, 27, 22`) and ST7789V Display (`DC=27, RST=22, BL=6`), and battery voltage protection (warning at
`7.15 V`, motion cutoff at `6.90 V`), alongside 23 September 2026 refined onboarding interface with ASCII welcome, bulk settings reuse,
Mac Calendar OAuth SSH forwarding (`-L 127.0.0.1:8765:127.0.0.1:8765`), waiting updates, callback receipt acknowledgment, read-only
Calendar MCP validation, candidate credential cleanup, key rollback, root installer branch disambiguation and `--install-dir`,
22 September guided onboarding, prompt-toolkit multiline chat, 18 September web controller dual views, 17 September Google Calendar
guided setup and unified `CONFIRM` / `CANCEL` chat authorization, 16 September distance game hand-placement procedure, Phase 4
information setup, Phase 4 foundations, and headless Lite audio with Bluetooth wizard. Software tests do not substitute for
physical hardware validation.[^src-20261027-installationguide]


[^src-20261027-installationguide]: InstallationGuide.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
