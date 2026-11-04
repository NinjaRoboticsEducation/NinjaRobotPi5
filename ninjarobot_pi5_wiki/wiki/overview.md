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
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20261104-developmentguide
  resource: urn:llmwiki:source:src-20261104-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:6d4574560831e69657ce128f16f972a885ba6fbf98c463a433a38a2459b41f4b
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
  target_hash: sha256:66debf0d9b2f7487ebce57db59b60f91a1bea2ddddd60f4929eb12e89c50053c
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20261104-developmentguide]

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

## Current checkpoint: Fusion agent integration remediation and documentation reconciliation

The project consolidates 4 November 2026 SunFounder Fusion HAT+ agent integration remediation, web microphone lifecycle repair, and documentation reconciliation alongside 3 November 2026 SunFounder Fusion HAT+ kernel driver integration and in-memory servo calibration draft staging, 2 November runtime remediation, 25 October 2026 Multi-HAT hardware support (DFRobot DFR0566 IO Expansion HAT + Geekworm X1208 UPS, SunFounder Fusion HAT+ backed exclusively by reviewed kernel driver `1.1.0-ninja1` via sysfs, and General PCA9685 `0x40` PWM Expansion HAT), default-branch `install.sh` bootstrap (`HEAD`), flexible digital pins for Buzzer (`17, 4, 27, 22`) and ST7789V Display (`DC=27, RST=22, BL=6`), arbitrary calibrated PWM channels (`hat_pwm0`..`hat_pwm11` on Fusion HAT+, `0`..`15` on PCA9685), embedded I2S speaker (`GPIO12` amp enable and Fusion kernel speaker node control), and onboarding Hardware Expansion Profile Selection menu, alongside 23 September 2026 onboarding interface refinements, bulk settings reuse, Mac Calendar OAuth loopback forwarding, and installer branch/directory repairs. The Agent/IDE/driver boundary remains intact: setup wizard orchestration belongs to the Agent layer, while hardware locking, sysfs coordination, and dispatch belong to the IDE.[^src-20261104-developmentguide]

Recent updates resolve four post-onboarding issues on Fusion HAT+: (1) safety latch diagnostics record timestamped errors (`persisted safety latch recorded at <timestamp>`), `ServoDevice.status` exposes `motion_latched` and `stop_reason`, Level 1 `/resume` dispatches `robot.motion.resume` when `motion_latched` is active without `system_latched`, `/arm` and `/disarm` commands are explicitly handled in CLI and web chat, single-servo angle commands (`hat_pwm0`–`hat_pwm11`) route directly to `robot.servo.move` with signed `-90`..`90` range (`0` center) while preserving previous angle interpolation, and camera/mic health checks re-attempt suspend/start; (2) `SpeechService` initializes before `runtime_state` so `speech_output` is live, informed in LLM prompts when `/speech on` is active, automated Piper TTS provisioning via `prepare_speech_voice.py --install-piper --configure --apply`, and `agent_loop` filters out `memory-notice` turns; (3) `ninjarobot-agent deployment install-poweroff --confirm` installs standalone helper `/usr/libexec/ninjarobot-poweroff` and `/etc/sudoers.d/ninjarobot-agent-poweroff` for web power-off without requiring boot auto-start, granting direct LAN/localhost controller sessions power-off access; (4) browser microphone retention until `onend` with queued single restart, cancel on Send/hide, fallback to robot push-to-talk over HTTP, PortAudio 48 kHz chunk scaling, `PaErrorCode -9985` 3-retry handling, transient ALSA overflow tolerance, and Whisper `[BLANK_AUDIO]` re-arming. Earlier updates provide SunFounder Fusion HAT+ kernel driver `1.1.0-ninja1` via sysfs, in-memory calibration draft staging (<kbd>V</kbd>/<kbd>X</kbd>/<kbd>C</kbd> &rarr; <kbd>F</kbd>/<kbd>Q</kbd>), battery microvolt telemetry division, web startup `proxy_headers=False`, distinct `battery_undervoltage` cutoff (6.90 V), route-persisting local/cloud Ollama selection, and auxiliary-only servo roles. Physical acceptance, live accounts, display font repair, and monetary spending caps remain unverified.[^src-20261104-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20261104-developmentguide]: DevelopmentGuide.md, source version `fusion-agent-remediation-261104`; registered source `src-20261104-developmentguide`.
