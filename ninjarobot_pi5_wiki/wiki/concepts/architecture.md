---
type: Concept
title: Architecture and hardware ownership
description: Agent, IDE, device drivers, safety policy, resource ownership, and code
  boundaries.
status: draft
tags:
- architecture
- hardware
- ownership
- agent
- ide
- drivers
- safety
- speech
- bluetooth
- information
- distance-game
- calendar
- web-controller
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260918-developmentguide
  resource: urn:llmwiki:source:src-20260918-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:a4295e369acd972b74b34383683623b37ef8a1a4cf1d2e066c50d7d4fc6ec649
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-18T16:50:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 18 September UI refinement, modular web
    frontend, and terminal menu consolidation evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair, monetary spending cap, and physical mobile Wi-Fi
    checks.
  target_hash: sha256:62ff7b9619e0d0477c493ae6fa25324d06f90ae31d2bf2d59b64529524c108e9
---

# Architecture and hardware ownership

The documented hardware path is user or model → ninjarobot_pi5_agent →
ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
interaction, model-provider translation, policy, sessions, memory, information services,
and tool proposals. It should not import a pi5 library or access a device directly.[^src-20260918-developmentguide]

The IDE (the project's device-coordination layer) owns shared resource scheduling,
action execution, safety state, behaviors, distance game loops, and hardware ownership.
Individual managed libraries own their device and standalone setup interface. The six
managed libraries cover servo motors, display, buzzer, distance sensing, camera,
and microphone.[^src-20260918-developmentguide]

This is the documented architecture contract. Compare affected code and tests
with it before implementation; this page does not certify that every failure or
physical safety condition has been tested.[^src-20260918-developmentguide]

[Read the development manual](/references/development-guide.md).

## Web controller and modular frontend architecture

The Agent layer exposes an HTTPS web controller (`web_app.py`, `web_control.py`) partitioned into two dedicated views:
- Game Pad (`/gamepad`, `gamepad.html`): Direct manual teleoperation with responsive touch D-pad, action triggers (Greeting, AI Camera preview, Emergency Stop, Resume), and a user-created behavior selector.
- Agent Interface (`/agent`, `agent.html`): Dialogue and planning viewport with conversation history, "Clear Message" UI clearing, special robot control toggles (A/B/X/Y), and audio/speech controls.[^src-20260918-developmentguide]

Frontend logic is modularized into `app-shared.js` (shared state, websocket communication, modal lifecycle, i18n localization), `app-gamepad.js` (game pad inputs and user behavior dropdown dispatch), and `app-agent.js` (chat stream handling and control button toggle states). The backend exposes `list_user_behaviors` and `run_user_behavior` hooked to IDE `_BehaviorListAdapter(source="user")`, ensuring that user behaviors with motion actions require explicit modal confirmation before execution.[^src-20260918-developmentguide]

## Refinement Phase 5 and hardware boundaries

Refinement Phase 5 introduces `ninjarobot_pi5_ide/distance_game.py`, owning strict
requests, fresh-reading validation, three-band tone feedback, admission, finite
execution, and independent stop/status. The game never reserves `servo_bus`; it reserves
shared display, buzzer, and distance resources, including the I2C bus lock. The distance
adapter shields and retains the underlying worker across cancellation, preventing
close/reopen overlap (`start(recover=True)`). Distance preparation waits within a bound
and checks health before automatic reuse. Repeated games silently re-initialize the buzzer
backend before health checks rather than treating earlier stopped states as permanent faults.
`expression_variants.py` selects a bounded silent palette once per conversational opportunity.
In the motion controller, `servo.stop` receives priority dispatch from an interrupt allowlist
with LOW risk rating rather than EMERGENCY, safely interrupting active pulses without false
Level 2 stops. Stop causes are preserved across ramp transitions, obstacles are checked before
and during ramps, and the motion watchdog continues heartbeats during responsive device cleanup.
Proposed hardware changes (movable head, edge sensing, touch input) remain unpurchased, uninstalled
evaluation proposals.[^src-20260918-developmentguide]

## Agent information architecture and local tasks

The Agent owns local speech synthesis, reminders, recipe execution, rolling chat context,
and Phase 4 information management in `ninjarobot_pi5_agent`. `AgentLoop` retains the complete
local transcript while selecting the largest recent suffix of complete user turns that fits
character limits, adding a trusted notice when earlier turns are omitted. `InformationStore`
manages user-scoped SQLite transactions (migration 7). `NotesService` commits notes and consumed
approvals together. `CalendarService` manages exact approvals, Google OAuth desktop browser
loopback (port 8765), primary-calendar auto-discovery, and remote verification via HTTPX.
`calendar_chat.py` processes standalone `CONFIRM` / `CANCEL` chat replies and alone provides
internal confirmation authority for calendar writes, rejecting direct command bypasses.
`project_documents.py` and `project_help.py` provide hash-checked runtime retrieval of bounded
published manual sections. `ResearchService` binds allowlisted Tavily snippet results to saved
runs. `BriefingService` generates deterministic bundles on request.[^src-20260918-developmentguide]

All state-modifying actions (calendar writes, note edits) require an exact preview and same-session
direct user confirmation. Models and recipes cannot confirm changes or bypass deterministic policy.
Audio playback routes through IDE PipeWire ownership with lead-in silence buffering
(`bluetooth_lead_in_seconds`, default 0.5s) and independent reconnection daemon support.[^src-20260918-developmentguide]


[^src-20260918-developmentguide]: DevelopmentGuide.md, source version `ui-refinement-260918`; registered source `src-20260918-developmentguide`.
