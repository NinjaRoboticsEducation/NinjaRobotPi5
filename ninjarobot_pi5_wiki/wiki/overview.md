---
type: Concept
title: NinjaRobotPi5 project overview
description: Architecture, primary manuals, hardware ownership boundaries, and AI
  workflow.
status: draft
tags:
- ninjarobotpi5
- architecture
- overview
- phase4
- phase5
- information
- distance-game
- calendar
- web-controller
- onboarding
- expansion-hat
- sunfounder
- pca9685
- reconnection
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20261109-developmentguide
  resource: urn:llmwiki:source:src-20261109-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:075a560ad59fcc46cbed6118928c0d1a342f86eda4464221beafde76138ca221
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
    handoff, and connected welcome/idle refinement evidence (development guide); no
    human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:a4810105b172ce88e988668b9379db58d5d7af2501572a84dcec1974474ac11c
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20261109-developmentguide]

The local wiki is the primary developer knowledge collection. Full manuals are
versioned under raw source folders; outer README links and the project knowledge
map point to the current versions. The primary entry points are:

- [Architecture and boundaries](/concepts/architecture.md)
- [Installation and hardware checks](/concepts/installation.md)
- [Development workflow](/concepts/development-workflow.md)
- [Features, MCP tools, and Agent Skills](/concepts/features-and-tools.md)
- [Development history and decisions](/concepts/development-history.md)
- [Knowledge limitations and verification](/analyses/knowledge-limitations.md)
- [Installation guide](references/installation-guide.md)
- [Development guide](references/development-guide.md)
- [Development log](references/development-log.md)
- [MCP and skills tutorial](references/mcp-skills-guide.md)

## Current checkpoint: Browser reconnection, controller handoff, and welcome/idle refinement

The project consolidates 9 November 2026 browser disconnect, reconnect, and controller handoff alongside connected welcome and idle refinement, in addition to 4 November 2026 SunFounder Fusion HAT+ agent integration remediation, web microphone lifecycle repair, and documentation reconciliation, 3 November 2026 SunFounder Fusion HAT+ kernel driver integration and in-memory servo calibration draft staging, 2 November runtime remediation, 25 October 2026 Multi-HAT hardware support (DFRobot DFR0566 IO Expansion HAT + Geekworm X1208 UPS, SunFounder Fusion HAT+ backed exclusively by reviewed kernel driver `1.1.0-ninja1` via sysfs, and General PCA9685 `0x40` PWM Expansion HAT), default-branch `install.sh` bootstrap (`HEAD`), flexible digital pins for Buzzer (`17, 4, 27, 22`) and ST7789V Display (`DC=27, RST=22, BL=6`), arbitrary calibrated PWM channels (`hat_pwm0`..`hat_pwm11` on Fusion HAT+, `0`..`15` on PCA9685), embedded I2S speaker (`GPIO12` amp enable and Fusion kernel speaker node control), and onboarding Hardware Expansion Profile Selection menu, alongside earlier checkpoints. The Agent/IDE/driver boundary remains intact: setup wizard orchestration belongs to the Agent layer, while hardware locking, sysfs coordination, and dispatch belong to the IDE.[^src-20261109-developmentguide]

Recent 9 November updates implement serialized browser controller lease cleanup, attachment generations, immediate revocation, automatic non-revoking pairing QR redisplay, durable waiting display reservation, endpoint invalidation, and browser departure/Back-Forward recovery across all supported Expansion HAT profiles. When a browser closes its tab or window, navigates away, or drops connectivity, commands from the old connection are rejected and active requests, movement, speech, and capture are cancelled, while browser-enabled robot voice listening is stopped without altering saved preferences. Clean disconnect reserves the lease until the earlier of its previous heartbeat deadline and ten seconds after loss, permitting the same browser to reconnect with its existing token and chat identity during that window while locking out others; reconnecting the same lease restores Idle without replaying its completed welcome. Unannounced departure is detected by the 15-second heartbeat deadline and watchdog polling (at most one second). Each newly acquired controller lease runs Greeting through the IDE, followed by the repeating silent Idle animation; the lease is delivered and heartbeats are processed while Greeting runs, with normal interactions waiting for completion while emergency/stop requests remain prompt. Delayed ngrok ready events verify endpoint generation before revoking a live controller. Earlier 4 November updates provide safety latch diagnostics, Level 1 motion-only `/resume`, `/arm` and `/disarm` commands, signed single-servo routing, live `speech_output` context, automated Piper TTS provisioning, standalone web power-off helper, and browser microphone lifecycle retention until `onend`. Physical acceptance, live accounts, display font repair, and monetary spending caps remain unverified.[^src-20261109-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20261109-developmentguide]: DevelopmentGuide.md; registered source `src-20261109-developmentguide`.
