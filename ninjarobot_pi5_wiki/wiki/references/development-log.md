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
- id: src-20261027-developmentlog
  resource: urn:llmwiki:source:src-20261027-developmentlog
  title: DevelopmentLog.md
  content_hash: sha256:037599cf40c9a4e13efcd885d7ef6a1d77d52fa14cad75ade77b0149f806c821
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
  target_hash: sha256:327c55a592c73df841a320e1ad6d998fa09745171f3d5b0e0f84421d3883180e
---

# Development log

The complete log preserves dated implementation decisions and validation reports. Historical test results describe their recorded checkout and date; they are not fresh verification.[^src-20261027-developmentlog]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Multi-HAT expansion upgrade and SunFounder hardware audit

The 25 October 2026 entries record the multi-HAT expansion upgrade and physical SunFounder hardware audit across `install.sh` (`INSTALL_REF=HEAD`),
`pi5servo` (dual `0x14`/`0x17` SunFounder MCU backend with automatic fallback, PCA9685 smbus2 controller at `0x40` accepting `hat_pwm0`..`15`,
8 authorized changes recorded in `docs/validation/authorized_driver_changes.json`), `ninjarobot_pi5_ide` (pin collision fix for display/buzzer, flexible
PWM calibration, embedded I2S speaker with GPIO12 amp enable and `0x17` register `0x31`, auxiliary-only servo roles in behaviors, battery undervoltage
monitoring at 7.15V/6.90V for `0x14`/`0x17`), and `ninjarobot_pi5_agent` (onboarding hardware profile selection and embedded speaker flow). 1,087
root/IDE/Agent tests and 139 `pi5servo` tests passed, alongside 23 September 2026 entries recording the refined onboarding interface with ASCII welcome
screen, numeric menus, bulk settings reuse ("2) Apply existing settings for all modules"), automatic configuration checks, Enter-to-continue summaries,
removal of redundant typed YES/APPLY phrases, detailed Mac SSH port forwarding for Google Calendar OAuth (`ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765`),
waiting feedback, callback receipt acknowledgment, end-to-end read-only Calendar MCP validation, candidate credential cleanup, key rollback, isolated
microphone asset checking via `ninjarobot_pi5_ide.hardware_config_probe` subprocess to preserve runtime containment, passage of 1,065 full-suite tests,
and root installer branch disambiguation, custom installation directory support (`--install-dir`), and `/dev/tty` controlling terminal confirmation,
alongside 22 September guided onboarding CLI, prompt-toolkit multiline chat, 18 September web controller dual views, 17 September Google Calendar
guided OAuth setup with primary-calendar discovery, port 8765 loopback SSH tunnel, field validation error handling, unified `CONFIRM` / `CANCEL` chat
authorization across create, update, and delete, runtime project help hash checking, 16 September distance game hand-placement timing, 15 September
repairs, Phase 4 information assistant completion, narrowed Phase 4 foundations, Phase 5 evaluation, and system clock access.[^src-20261027-developmentlog]


[^src-20261027-developmentlog]: DevelopmentLog.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-developmentlog`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
