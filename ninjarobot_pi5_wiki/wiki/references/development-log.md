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
- id: src-20261103-developmentlog
  resource: urn:llmwiki:source:src-20261103-developmentlog
  title: DevelopmentLog.md
  content_hash: sha256:72165a9673ce7cb920920d014845c07f88cf7e5956c6249167e65a50feceb1a9
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
  target_hash: sha256:b6a2a9b06040d1ed8ae01c5b927d3e27986a6c0a69d7498995d056bdf77054a0
---

# Development log

The complete log preserves dated implementation decisions and validation reports. Historical test results describe their recorded checkout and date; they are not fresh verification.[^src-20261103-developmentlog]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: SunFounder Fusion HAT+ kernel driver integration and calibration draft staging

The 3 November 2026 entries record SunFounder Fusion HAT+ integration and follow-up repairs: Phase 0/1 reviewed kernel driver `1.1.0-ninja1` sysfs PWM ownership (`hat_pwm0`..`hat_pwm11` in 3 groups of 4 at fixed 50 Hz) and patch `0001-safe-pwm-and-battery.patch`; Phase 2 `scripts/fusion_hat_setup.py` installer tool and source preparation recovery in persistent cache (`$HOME/.cache/ninjarobot/fusion-source-recovered`); Phase 3 non-moving onboarding prerequisite validation (`hardware_setup.py`) halting gracefully on missing driver/sysfs nodes without tracebacks; Phase 4 in-memory servo calibration draft staging (<kbd>V</kbd>/<kbd>X</kbd>/<kbd>C</kbd> &rarr; <kbd>F</kbd>/<kbd>Q</kbd>) in `calib.py`; Phase 5 battery telemetry dividing kernel `voltage_now` by 1,000,000 once with distinct `battery_undervoltage` cutoff (6.90 V); and orderly web OS shutdown. All 1,132 repository unit tests, 159 `pi5servo` tests (including all draft entry orders), and separate driver suites passed without live actuator movement. Validation recorded in `docs/validation/fusion_implementation_261103.md`, `fusion_prerequisite_repair_261103.md`, `fusion_source_preparation_repair_261103.md`, and `fusion_calibration_draft_repair_261103.md`, alongside earlier 2 November runtime remediation, 25 October Multi-HAT expansion upgrade, 23 September onboarding refinements, 22 September guided onboarding, 18 September web controller dual views, 17 September calendar setup and unified CONFIRM authorization, 15–16 September distance game and servo repairs, Phase 4 information services, Phase 4 foundations, and system clock access.[^src-20261103-developmentlog]


[^src-20261103-developmentlog]: DevelopmentLog.md, source version `fusion-hat-plus-261103`; registered source `src-20261103-developmentlog`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
