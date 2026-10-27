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
- id: src-20261027-developmentguide
  resource: urn:llmwiki:source:src-20261027-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:3ab4adc6f8052f7975b17a7ebcdd893df425e47b9f16e2127a2751f71d9e73c7
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
  target_hash: sha256:5f0c05489cb273b10b5a9b7c4fe6a345a19d10cdeaf196b8721c3281d0a0fb50
---

# Development guide

The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20261027-developmentguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Multi-HAT servo backends, IDE config import, and onboarding profiles

The 25 October 2026 revision (`2026-10-25`) documents `SunFounderRobotHatBackend` (`0x14`/`0x17` dual MCU with automatic fallback,
3-byte Big-Endian transactions, class-level `RLock`), `PCA9685ServoBackend` with built-in `smbus2` controller, `ServoEndpoint` (0..15),
IDE `SUPPORTED_SERVO_ENDPOINTS`, `PowerConfig` (`fuel_gauge_address` `0x36`, `0x14`, `0x17`, `warning_voltage = 7.15`, `cutoff_voltage = 6.90`),
`SpeechOutputConfig.speaker_enable_gpio`, `audio_output.py` I2S sink discovery and GPIO12 amp enable (`0x17` register `0x31`), single-component
pin collision fix in `hardware_setup.py`, flexible PWM channels, auxiliary-only servo roles in `safety.py`, and onboarding wizard profile selection,
alongside 23 September 2026 refined `setup_wizard.py` orchestration layer, bulk hardware settings reuse calling `hardware_setup_status`, isolated
microphone asset checking via `ninjarobot_pi5_ide.hardware_config_probe` subprocess (preserving microphone runtime containment), offline
simulation rehearsal isolation, `--resume` rechecking saved settings, Google Calendar OAuth output callbacks, Mac loopback SSH forwarding
(`ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765`), waiting updates, callback receipt acknowledgment, end-to-end read-only
Calendar MCP validation, candidate credential cleanup, secret rollback on save failure, root installer revision disambiguation and `--install-dir`
support, 22 September guided onboarding and prompt-toolkit chat, 18 September web controller dual-view architecture, 17 September calendar setup
and unified `CONFIRM` / `CANCEL` flow, 15–16 September distance game and servo repairs, Phase 4 information services (T04 calendar, T05 research,
T06 notes/checklists/briefings, migration 7), Phase 4 foundations, and system clock access.[^src-20261027-developmentguide]


[^src-20261027-developmentguide]: DevelopmentGuide.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
