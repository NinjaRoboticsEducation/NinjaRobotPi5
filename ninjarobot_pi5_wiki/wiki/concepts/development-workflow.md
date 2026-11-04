---
type: Concept
title: Development and documentation workflow
description: Retrieve evidence, plan, implement, review wiki impact, version manuals,
  and validate.
status: draft
tags:
- development
- workflow
- documentation
- update
- codex
- claude
- cursor
- antigravity
- phase4
- phase5
- calendar
- ui-refinement
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
  target_hash: sha256:42cb58c422c84940153491bf291562f1ab604d491135c8d0cbcb12fe4ba181d3
---

# Development and documentation workflow

Before significant development, consult the local wiki and current full
manuals, inspect relevant code, and identify missing or conflicting evidence.
The root project policy requires an approved phased plan and preservation of
robot interfaces and managed-driver rules.[^src-20261104-developmentguide]

Feature completion includes a wiki impact assessment. Update affected manual
versions, topic pages, specifications, and architecture guidance, then record
the change and validation in the development log. If no documentation change is
needed, record a specific reason. A new source version preserves the old source;
current navigation and the knowledge map identify the active version.[^src-20260907-knowledgeintegration]

Use the project's maintenance guide outside the knowledge bundle for exact
commands. Prepare a semantic page plan, validate it, show the actual diff, and
apply the approved plan with the wiki CLI. Review source support honestly and
check current pointers, file fingerprints, links, indexes, and review coverage.
AI review is distinct from human verification.[^src-20260907-knowledgeintegration]

[Development guide](/references/development-guide.md) ·
[History](/concepts/development-history.md).

## Milestones and source consolidation

The active manuals are versioned under `raw/articles/ninjarobotpi5/2026-11-04-03/`
and `raw/notes/ninjarobotpi5/2026-11-04-03/`. This version consolidates:
1. System clock access (`/time` and `system.time.get`, `2026-09-12-02`),
2. Refinement Phase 5 software foundations and distance game (`2026-09-13`),
3. Narrowed Phase 4 foundations (M03 memory ranking, M04 read-only recipes, X01 v2 skills, X05 help, `2026-09-13-02`),
4. Completed Phase 4 information assistant (T04 calendar, T05 research, T06 notes/checklists/briefings, `2026-09-13-03`),
5. Servo stop priority allowlist (LOW risk), rolling chat context, and default distance game (`2026-09-15`),
6. Approved servo and sensor recovery repair with stop cause preservation (`2026-09-15-02`),
7. Web controller admission fix, repeated-game buzzer preparation, and cleanup watchdog heartbeat (`2026-09-15-03`),
8. Distance game hand-placement timing correction and out-of-range sensor handling (`2026-09-16`),
9. Google Calendar guided OAuth setup with primary-calendar discovery and port 8765 loopback SSH tunnel (`2026-09-17`),
10. Field-specific preview validation errors and plain `CONFIRM` / `CANCEL` chat authorization for calendar writes,
11. Unified single-word `CONFIRM` flow across event create, update, and delete, eliminating direct command confirmation bypasses,
12. Hash-checked runtime public project help with bounded sections (`project_documents.py`, `project_help_sources.json`),
13. Web interface refinement into dedicated Game Pad and Agent Interface surfaces, modular frontend (`app-shared.js`, `app-gamepad.js`, `app-agent.js`), user-created behavior execution with motion safety modals, button toggle states, 4-language i18n parity, and IDE terminal menu consolidation (1–5, Q, `2026-09-18`),
14. Guided onboarding CLI (`ninjarobot onboard`) orchestrating 5 mandatory hardware components, model providers, and external read-only MCP presets (Tavily, Calendar, Notion), standalone curl bootstrap installer (`install.sh`), and prompt-toolkit interactive chat (`2026-09-22`),
15. Root installer branch disambiguation, custom installation directory (`--install-dir`), and controlling terminal prompt (`2026-09-23`),
16. Refined onboarding wizard with ASCII welcome, bulk settings reuse option, Enter-to-continue summaries, Mac Calendar OAuth SSH tunnel (`-L 127.0.0.1:8765:127.0.0.1:8765`), waiting updates, callback acknowledgment, read-only Calendar MCP validation, candidate credential cleanup, key rollback, microphone subprocess import containment, and simulation isolation (`2026-09-23-02`),
17. Multi-HAT expansion upgrade and physical SunFounder hardware audit across `install.sh` (`INSTALL_REF=HEAD`), `pi5servo` (dual `0x14`/`0x17` SunFounder MCU backend with automatic fallback, PCA9685 smbus2 controller at `0x40` accepting `hat_pwm0`..`15`, 8 authorized changes recorded in `docs/validation/authorized_driver_changes.json`), `ninjarobot_pi5_ide` (pin collision fix for arbitrary Digital pins for display/buzzer, flexible PWM calibration, embedded I2S speaker with GPIO12 amp enable and `0x17` register `0x31`, auxiliary-only servo roles in behaviors, battery undervoltage monitoring at 7.15V/6.90V for `0x14`/`0x17`), and `ninjarobot_pi5_agent` (onboarding hardware profile selection and embedded speaker flow, `2026-10-25`),
18. Runtime remediation and Multi-HAT hardware refinement (`2026-11-02`): Web startup `proxy_headers=False` for loopback proxy pairing inspection; distinct `battery_undervoltage` reason keeping measured voltage and cutoff in persisted fault details with non-finite reading safeguards; sysfs-informed SunFounder preset selecting `0x17` without probing or assigning legacy charging GPIO23; transient full stop local gate cleanup upon completion; embedded audio using Fusion kernel speaker node without raw I2C `0x31` write; ALSA/PipeWire audio health alignment; 2-byte register stride for Fusion PWM/timers at `0x17`; config import preserving explicit servo roles without companion fabrication; and route-persisting local/cloud Ollama catalog discovery and selection,
19. SunFounder Fusion HAT+ kernel driver integration and calibration draft staging (`2026-11-03-04`): Standardized SunFounder support on Fusion HAT+ backed exclusively by reviewed kernel driver `1.1.0-ninja1` via sysfs (`hat_pwm0`..`hat_pwm11` at fixed 50 Hz across 3 shared timer groups), removing userspace I2C bus contention, address probing, and reset pulsing; `scripts/fusion_hat_setup.py` prepare/preview/install tool with persistent cache recovery (`$HOME/.cache/ninjarobot/fusion-source`); non-moving onboarding prerequisite validation halting gracefully on missing driver/sysfs paths without tracebacks; in-memory servo calibration draft staging (stage Min/Max/Center in any order with Enter/Space, atomic commit with F requiring `500 <= Min < Center < Max <= 2500` microseconds, discard with Q, clean exit without centering); kernel `voltage_now` battery telemetry with distinct `battery_undervoltage` cutoff (6.90 V); and orderly web OS shutdown, and
20. Fusion agent integration remediation and documentation reconciliation (`2026-11-04-03`): Remediated four post-onboarding Fusion HAT+ agent integration issues: (1) safety latch timestamping (`(persisted safety latch recorded at <timestamp>)`), `ServoDevice.status` motion latch exposure, Level 1 motion-only `/resume` dispatch, `/arm` and `/disarm` chat commands, signed `-90`..`90` single-servo routing, and camera/mic health retry; (2) live `speech_output` prompt context, automated Piper TTS provisioning, and `memory-notice` turn filtering; (3) standalone `install-poweroff` helper and LAN session authorization; (4) browser microphone session retention until `onend`, HTTP push-to-talk fallback, 48 kHz chunk scaling, `PaErrorCode -9985` retry, ALSA overflow tolerance, Whisper `[BLANK_AUDIO]` re-arming, and audio child process stdin closure cleanup.[^src-20261104-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20261104-developmentguide]: DevelopmentGuide.md, source version `fusion-agent-remediation-261104`; registered source `src-20261104-developmentguide`.
