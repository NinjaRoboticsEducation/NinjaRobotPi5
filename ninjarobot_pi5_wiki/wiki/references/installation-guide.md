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
- id: src-20261102-installationguide
  resource: urn:llmwiki:source:src-20261102-installationguide
  title: InstallationGuide.md
  content_hash: sha256:802998dc63e28cf49612c003f69965ab6f0f9b408ea185415292a58a1a428e06
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-11-02T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 2 November runtime remediation and Multi-HAT
    hardware refinement evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:5f22e653056b2a99589d03a9230316a5b8d4398d53194b0ee4f5ef9053e29296
---

# Installation guide

The full guide covers beginner setup, hardware initialization and calibration, startup, and troubleshooting. Hardware commands require stated operator precautions.[^src-20261102-installationguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Runtime remediation and Multi-HAT hardware refinement

The 2 November 2026 revision (`2026-11-02`) documents web startup proxy-header disabling (`proxy_headers=False`) to inspect actual loopback peers under ngrok fallback while denying forged LAN requests; distinct `battery_undervoltage` reason keeping measured voltage/cutoff in persisted fault detail; SunFounder sysfs-informed `0x17` preset avoiding probing and legacy charging GPIO23; completed transient full stop clearing local presentation gate; embedded audio using Fusion kernel speaker node when present, removing raw I2C `0x31` write; Fusion PWM/timer registers advancing by two bytes at `0x17`; config import preserving explicit servo roles without companion fabrication; Ollama catalog discovery querying local models without credentials and cloud models when an API key is stored, carrying route through CLI/IPC/runtime/persistence as `base_url`; CLI model selection (`ninjarobot model list/select --route local|cloud`); and audio inspection via `/speech status` and `/speech outputs`, alongside 25 October 2026 Multi-HAT expansion support (DFRobot DFR0566 IO Expansion HAT + Geekworm X1208 UPS, SunFounder Robot HAT v4 `0x14` and Fusion HAT / Robot HAT v5 `0x17` with auto-detection and fallback, and General PCA9685 PWM Expansion HAT `0x40`), default-branch cURL bootstrap from GitHub (`INSTALL_REF=HEAD`), onboarding Hardware Expansion Profile Selection menu, flexible Digital header pin assignments for Buzzer and Display, battery voltage protection, 23 September onboarding refinements, Mac Calendar SSH forwarding, and earlier checkpoints. Software tests do not substitute for physical hardware validation.[^src-20261102-installationguide]


[^src-20261102-installationguide]: InstallationGuide.md, source version `runtime-remediation-261102`; registered source `src-20261102-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
