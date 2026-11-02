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
  target_hash: sha256:43b62602b8752a2c577de252ea50325c95e1da035820983fc3deb971909d9f10
---

# Development and documentation workflow

Before significant development, consult the local wiki and current full
manuals, inspect relevant code, and identify missing or conflicting evidence.
The root project policy requires an approved phased plan and preservation of
robot interfaces and managed-driver rules.[^src-20261102-developmentguide]

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

The active manuals are versioned under `raw/articles/ninjarobotpi5/2026-11-02/`
and `raw/notes/ninjarobotpi5/2026-11-02/`. This version consolidates:
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
17. Multi-HAT expansion upgrade and physical SunFounder hardware audit across `install.sh` (`INSTALL_REF=HEAD`), `pi5servo` (dual `0x14`/`0x17` SunFounder MCU backend with automatic fallback, PCA9685 smbus2 controller at `0x40` accepting `hat_pwm0`..`15`, 8 authorized changes recorded in `docs/validation/authorized_driver_changes.json`), `ninjarobot_pi5_ide` (pin collision fix for arbitrary Digital pins for display/buzzer, flexible PWM calibration, embedded I2S speaker with GPIO12 amp enable and `0x17` register `0x31`, auxiliary-only servo roles in behaviors, battery undervoltage monitoring at 7.15V/6.90V for `0x14`/`0x17`), and `ninjarobot_pi5_agent` (onboarding hardware profile selection and embedded speaker flow, `2026-10-25`), and
18. Runtime remediation and Multi-HAT hardware refinement (`2026-11-02`): Web startup `proxy_headers=False` for loopback proxy pairing inspection; distinct `battery_undervoltage` reason keeping measured voltage and cutoff in persisted fault details with non-finite reading safeguards; sysfs-informed SunFounder preset selecting `0x17` without probing or assigning legacy charging GPIO23; transient full stop local gate cleanup upon completion; embedded audio using Fusion kernel speaker node without raw I2C `0x31` write; ALSA/PipeWire audio health alignment; 2-byte register stride for Fusion PWM/timers at `0x17`; config import preserving explicit servo roles without companion fabrication; and route-persisting local/cloud Ollama catalog discovery and selection.[^src-20261102-developmentguide]

Automated validation covers extensive unit tests (1,104 root/IDE/Agent tests, 464 driver tests across 6 separate processes), compilation, linting, formatting, mypy typing, and immutable driver verification. Software validation does not replace physical hardware acceptance or live power testing.[^src-20261102-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20261102-developmentguide]: DevelopmentGuide.md, source version `runtime-remediation-261102`; registered source `src-20261102-developmentguide`.
