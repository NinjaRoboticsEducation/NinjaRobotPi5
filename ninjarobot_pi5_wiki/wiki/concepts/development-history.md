---
type: Concept
title: Development history and decisions
description: Find dated rationale and distinguish historical evidence from current
  implementation.
status: draft
tags:
- history
- decisions
- rationale
- development
- log
- phase4
- phase5
- clock
- calendar
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260917-developmentlog
  resource: urn:llmwiki:source:src-20260917-developmentlog
  title: DevelopmentLog.md
  content_hash: sha256:2c9e4a8d9702facf8d609b368da4c898d00c8f912dbfe3a9026c78f9849f4fa3
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-17T15:40:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 17 September calendar CONFIRM flow, guided
    authorization, and project help evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
  target_hash: sha256:db4a1e18108c10eb2b604aa7880fd90c6ea135d0fe6105eb0433b946164408c1
---

# Development history and decisions

The development log retains dated records of implementation work, design
choices, repairs, validation, and remaining work. Use a relevant dated entry
when answering why a change was made. Read surrounding entries to determine
whether a later decision superseded it.[^src-20260917-developmentlog]

Historical success reports refer to the recorded work and environment. They do
not prove that today's checkout passes the same checks, or that a physical
device was tested during a later documentation task. Cite the entry and state
which current checks were actually run.[^src-20260917-developmentlog]

[Complete development log](/references/development-log.md).

## Recent milestones (12–17 September 2026)

- **System clock access (12 September 2026)**: Added `/time` chat command and read-only `system.time.get` tool, providing fresh OS clock and timezone context for model turns and relative reminders.[^src-20260917-developmentlog]
- **Refinement Phase 5 software and hardware evaluation (13 September 2026)**: Implemented software foundations for the bounded distance game (`ninjarobot_pi5_ide/distance_game.py`, 3-band tone feedback) and silent expression variations (`expression_variants.py`). Evaluated proposed hardware additions (desk-edge sensing, movable head, touch input, speaker output) without purchase or physical installation.[^src-20260917-developmentlog]
- **Narrowed Phase 4 foundations (13 September 2026)**: Implemented M03 memory ranking, M04 read-only recipes, X01 version-2 skills, and X05 public project help with database migration 6.[^src-20260917-developmentlog]
- **Phase 4 information assistant completion (13 September 2026)**: Implemented T04 Google Calendar planning, T05 research service, and T06 notes/checklists/requested briefings with database migration 7 and 7-day preview cleanup.[^src-20260917-developmentlog]
- **Servo stop, rolling chat context, and default games (15 September 2026)**: Assigned `servo.stop` priority dispatch from an engine allowlist with LOW risk level instead of EMERGENCY stop. Added rolling transcript window in `AgentLoop` fitting character limits with trusted truncation notices. Default-enabled the distance game configuration (`[distance_game]`).[^src-20260917-developmentlog]
- **Approved servo and sensor recovery repair (15 September 2026)**: Preserved intentional stop causes across ramp transitions through the motion owner, added pre-ramp and active ramp obstacle checks, and bounded distance sensor preparation/recovery.[^src-20260917-developmentlog]
- **Web controller and repeated-game follow-up (15 September 2026)**: Removed redundant action-admission game check blocking web movement, added visible web error banners, re-initialized the buzzer on repeated games, and preserved watchdog heartbeats during cleanup.[^src-20260917-developmentlog]
- **Distance game hand-placement correction (16 September 2026)**: Addressed game start timing so play begins before the final chat response with immediate web chat guidance. Out-of-range sensor readings wait silently for hand presence, completing with `no_target_detected` and recording rejection metrics.[^src-20260917-developmentlog]
- **Google Calendar guided setup & discovery (17 September 2026)**: Added primary-calendar auto-discovery, user-scoped registration reusing connection ID on reauthorization, loopback SSH port 8765 helper, and default credentials storage.[^src-20260917-developmentlog]
- **Calendar preview validation & CONFIRM (17 September 2026)**: Added field-specific validation errors (e.g. required timezone `Asia/Tokyo`, title, ISO timestamps) and plain `CONFIRM` / `CANCEL` chat confirmation for event create previews.[^src-20260917-developmentlog]
- **Unified confirmation flow for all event changes (17 September 2026)**: Extended standalone single-word `CONFIRM` / `CANCEL` flow across create, update, and delete operations via `CalendarChat`, rejecting command bypasses and version conflicts.[^src-20260917-developmentlog]
- **Hash-checked public project help (17 September 2026)**: Replaced static 4-page retrieval with hash-checked published manual sections and continuation tokens (`project_documents.py`, `project_help_sources.json`).[^src-20260917-developmentlog]

The software test gates pass across agent and IDE test suites. Physical Bluetooth speaker
audibility, live actuator movement, sensor timing on real hardware, and monetary spending
cap enforcement remain unverified gaps.[^src-20260917-developmentlog]


[^src-20260917-developmentlog]: DevelopmentLog.md, source version `calendar-confirm-260917`; registered source `src-20260917-developmentlog`.
