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
- id: src-20261102-developmentguide
  resource: urn:llmwiki:source:src-20261102-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:d106f1e107b08da8a11f85ef97a4195e2483dcda7753aaa167f762457ee3eeb4
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
  target_hash: sha256:72ba7a2631f1caff2a0734e2589f6df88e6dd9ae6c7ca7c2dc9553989671c66c
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20261102-developmentguide]

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

## Current checkpoint: Runtime remediation and Multi-HAT hardware refinement

The project consolidates 2 November 2026 runtime remediation and 25 October 2026 Multi-HAT hardware support (DFRobot DFR0566 IO Expansion HAT, SunFounder Robot HAT v4 `0x14` and Fusion HAT / Robot HAT v5 `0x17` with automatic fallback, and General PCA9685 `0x40` PWM Expansion HAT), default-branch `install.sh` bootstrap (`HEAD`), flexible digital pins for Buzzer (`17, 4, 27, 22`) and ST7789V Display (`DC=27, RST=22, BL=6`), arbitrary calibrated PWM channels (`hat_pwm0`..`hat_pwm11` on SunFounder, `0`..`15` on PCA9685), embedded I2S speaker (`GPIO12` amp enable and Fusion kernel speaker control), and onboarding Hardware Expansion Profile Selection menu, alongside 23 September 2026 onboarding interface refinements, bulk settings reuse, Mac Calendar OAuth loopback forwarding, and installer branch/directory repairs. The Agent/IDE/driver boundary remains intact: setup wizard orchestration belongs to the Agent layer, while hardware locking and dispatch belong to the IDE.[^src-20261102-developmentguide]

Recent updates add web startup proxy-header disabling (`proxy_headers=False`) to inspect actual loopback peers under ngrok fallback while rejecting forged LAN headers, distinct `battery_undervoltage` cutoff preserving measured voltage and cutoff details with non-finite reading safeguards, sysfs-informed SunFounder `0x17` preset selection without probing or assigning legacy charging GPIO23, transient full stop local presentation gate clearance upon completion, embedded audio using Fusion kernel speaker control without raw I2C `0x31` writes, PipeWire/ALSA audio health alignment, 2-byte register stride for Fusion PWM/timers at `0x17`, config import preserving explicit servo roles without companion fabrication, and route-persisting local/cloud Ollama catalog discovery and selection. Earlier additions provide dual `0x14`/`0x17` MCU auto-fallback on `[Errno 121] Remote I/O error`, built-in `smbus2` controller in `PCA9685ServoBackend`, single-component pin validation in `hardware_setup_status`, auxiliary-only servo role targets in behaviors, ASCII welcome screen, numeric menus, bulk hardware reuse, automatic configuration checks, Enter-to-continue summaries, Mac SSH forwarding instructions (`-L 127.0.0.1:8765:127.0.0.1:8765`), waiting updates, callback receipt acknowledgment, read-only Calendar MCP validation, candidate credential cleanup, key rollback, microphone subprocess containment, and simulation isolation. Physical acceptance, live accounts, display font repair, and monetary spending caps remain unverified.[^src-20261102-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20261102-developmentguide]: DevelopmentGuide.md, source version `runtime-remediation-261102`; registered source `src-20261102-developmentguide`.
