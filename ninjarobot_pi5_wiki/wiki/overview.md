---
type: Concept
title: NinjaRobotPi5 project overview
description: Start here for architecture, setup, features, development history, and
  current evidence.
status: draft
tags:
- ninjarobotpi5
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20261103-developmentguide
  resource: urn:llmwiki:source:src-20261103-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:b6f8ff4f81477bbd155436abf135e93acfb0dab78568e498a11986ca8efd43a4
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
  target_hash: sha256:3678f871152f681debd622d71457d90056c62ff6cd903b9e41939d01706f4e1e
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20261103-developmentguide]

The local wiki is the primary developer knowledge collection. Full manuals are
versioned under raw source folders; outer README links and the project knowledge
map identify the current versions. Read source records and limitations, then
compare important claims with the current checkout before coding.[^src-20260907-knowledgeintegration]

## Browse project knowledge

- [Architecture and hardware ownership](concepts/architecture.md)
- [Development and documentation workflow](concepts/development-workflow.md)
- [Installation and hardware checks](concepts/installation.md)
- [Features, MCP tools, and Agent Skills](concepts/features-and-tools.md)
- [Development history](concepts/development-history.md)
- [Known knowledge limitations](analyses/knowledge-limitations.md)
- [Installation manual](references/installation-guide.md)
- [Development manual](references/development-guide.md)
- [Development log](references/development-log.md)
- [MCP and skills tutorial](references/mcp-skills-guide.md)

## Current checkpoint: SunFounder Fusion HAT+ kernel driver integration and calibration draft staging

The project consolidates 3 November 2026 SunFounder Fusion HAT+ kernel driver integration and in-memory servo calibration draft staging alongside 2 November runtime remediation, 25 October 2026 Multi-HAT hardware support (DFRobot DFR0566 IO Expansion HAT + Geekworm X1208 UPS, SunFounder Fusion HAT+ backed exclusively by reviewed kernel driver `1.1.0-ninja1` via sysfs, and General PCA9685 `0x40` PWM Expansion HAT), default-branch `install.sh` bootstrap (`HEAD`), flexible digital pins for Buzzer (`17, 4, 27, 22`) and ST7789V Display (`DC=27, RST=22, BL=6`), arbitrary calibrated PWM channels (`hat_pwm0`..`hat_pwm11` on Fusion HAT+, `0`..`15` on PCA9685), embedded I2S speaker (`GPIO12` amp enable and Fusion kernel speaker node control), and onboarding Hardware Expansion Profile Selection menu, alongside 23 September 2026 onboarding interface refinements, bulk settings reuse, Mac Calendar OAuth loopback forwarding, and installer branch/directory repairs. The Agent/IDE/driver boundary remains intact: setup wizard orchestration belongs to the Agent layer, while hardware locking, sysfs coordination, and dispatch belong to the IDE.[^src-20261103-developmentguide]

Recent updates introduce the supported SunFounder **Fusion HAT+ only** path backed by the reviewed `1.1.0-ninja1` kernel driver via sysfs (`/sys/devices/platform/soc/...`), removing userspace I2C address probing, legacy reset, and raw bus contention. All 12 PWM channels share timers in groups of 4 at a fixed 50 Hz carrier. The `scripts/fusion_hat_setup.py` tool automates checksum-pinned archive preparation and patch application into persistent cache (`$HOME/.cache/ninjarobot/fusion-source-recovered`) with explicit preview vs administrative installation (`--apply`). Onboarding checks driver version, 12 sysfs interfaces, permissions, and shared locks without pulsing hardware, exiting cleanly on failure. Servo calibration introduces session-local in-memory draft staging: Min (V), Max (X), and Center (C) points can be adjusted and staged in any order with Enter/Space without immediate disk writes, finalized and validated atomically with F (`500 <= Min < Center < Max <= 2500` microseconds) to `servo.json`, or discarded with Q, shutting off PWM without centering. Earlier updates provide web startup proxy-header disabling (`proxy_headers=False`), distinct `battery_undervoltage` cutoff (6.90 V) preserving measured microvolt telemetry with stale sample rejection, transient stop presentation clearance, route-persisting local/cloud Ollama selection, dual MCU fallback, single-component pin isolation, and auxiliary-only servo roles. Physical acceptance, live accounts, display font repair, and monetary spending caps remain unverified.[^src-20261103-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20261103-developmentguide]: DevelopmentGuide.md, source version `fusion-hat-plus-261103`; registered source `src-20261103-developmentguide`.
