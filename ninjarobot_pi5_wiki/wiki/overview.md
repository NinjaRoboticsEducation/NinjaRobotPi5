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
- id: src-20261027-developmentguide
  resource: urn:llmwiki:source:src-20261027-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:3ab4adc6f8052f7975b17a7ebcdd893df425e47b9f16e2127a2751f71d9e73c7
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
  target_hash: sha256:79d3b9af6410861bd5a2495cdd977b6ebf4495abedc60d31ecaaabf182c3ba64
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20261027-developmentguide]

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

## Current checkpoint: Multi-HAT expansion upgrade and SunFounder hardware audit

The project consolidates 25 October 2026 Multi-HAT hardware support (DFRobot DFR0566 IO Expansion HAT, SunFounder Robot HAT v4 `0x14` and Fusion HAT / Robot HAT v5 `0x17` with automatic fallback, and General PCA9685 `0x40` PWM Expansion HAT), default-branch `install.sh` bootstrap (`HEAD`), flexible digital pins for Buzzer (`17, 4, 27, 22`) and ST7789V Display (`DC=27, RST=22, BL=6`), arbitrary calibrated PWM channels (`hat_pwm0`..`hat_pwm11` on SunFounder, `0`..`15` on PCA9685), embedded I2S speaker (`GPIO12` amp enable and `0x17` register `0x31` with `googlevoicehat`/`hifiberry` sink), and onboarding Hardware Expansion Profile Selection menu, alongside 23 September 2026 onboarding interface refinements, bulk settings reuse, Mac Calendar OAuth loopback forwarding, and installer branch/directory repairs. The Agent/IDE/driver boundary remains intact: setup wizard orchestration belongs to the Agent layer, while hardware locking and dispatch belong to the IDE.[^src-20261027-developmentguide]

Recent updates add dual `0x14`/`0x17` SunFounder MCU backend auto-fallback on `[Errno 121] Remote I/O error`, built-in `smbus2` controller in `PCA9685ServoBackend`, single-component pin validation in `hardware_setup_status` avoiding sibling pin collision, onboard 2S Li-ion battery voltage monitoring (`7.15 V` warning, `6.90 V` protective cutoff), Embedded Speaker Initialization flow in `ninjarobot onboard`, and auxiliary-only servo role targets in behaviors without requiring wheel roles. Earlier additions provide an ASCII welcome screen, numeric menus, a bulk hardware reuse option ("2) Apply existing settings for all modules"), automatic configuration checks, Enter-to-continue summaries, Mac SSH forwarding instructions (`-L 127.0.0.1:8765:127.0.0.1:8765`), waiting updates, callback receipt acknowledgment, read-only Calendar MCP validation, candidate credential cleanup, key rollback on save failure, microphone subprocess import containment, and simulation isolation. Physical acceptance, live accounts, display font repair, and monetary spending caps remain unverified.[^src-20261027-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20261027-developmentguide]: DevelopmentGuide.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-developmentguide`.
