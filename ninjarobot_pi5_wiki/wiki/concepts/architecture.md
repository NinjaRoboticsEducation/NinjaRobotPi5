---
type: Concept
title: Architecture and hardware ownership
description: The Agent/IDE/device boundary, hardware ownership, and cross-device coordination.
status: draft
tags:
- architecture
- hardware
- safety
- boundaries
- ownership
- phase4
- information
- distance-game
- calendar
- web-controller
- onboarding
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260923-developmentguide-2
  resource: urn:llmwiki:source:src-20260923-developmentguide-2
  title: DevelopmentGuide.md
  content_hash: sha256:17ba019c024248a5273bf2de3124d7fd62421e82ec2554cd3f756248ebd7ace5
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-23T00:30:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 23 September onboarding refinement, bulk
    settings reuse, Mac Calendar OAuth SSH tunnel, and installer repair evidence; no human
    verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:fa9aacdc76a8e23daa4add161dd5594c17327892e110d646b2443824db8ef8c3
---

# Architecture and hardware ownership

The documented hardware path is user or model → ninjarobot_pi5_agent →
ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
interaction, model-provider translation, policy, sessions, memory, information services,
and tool proposals. It should not import a pi5 library or access a device directly.[^src-20260923-developmentguide-2]

The IDE (the project's device-coordination layer) owns shared resource scheduling,
action execution, safety state, behaviors, distance game loops, and hardware ownership.
Individual managed libraries own their device and standalone setup interface. The six
managed libraries cover servo motors, display, buzzer, distance sensing, camera,
and microphone.[^src-20260923-developmentguide-2]

This is the documented architecture contract. Compare affected code and tests
with it before implementation; this page does not certify that every failure or
physical safety condition has been tested.[^src-20260923-developmentguide-2]

[Read the development manual](/references/development-guide.md).

## Guided setup architecture and hardware dispatch

The `ninjarobot` and `ninjarobot-agent` entry points share the argument dispatcher.
`setup_wizard.py` serves as the presentation and orchestration layer for guided onboarding,
managing selections, retry/skip logic, and final launch without importing managed `pi5*` packages.
Hardware setup follows the permitted path:[^src-20260923-developmentguide-2]

```text
setup_wizard -> ninjarobot_pi5_ide.hardware_setup
             -> allowlisted standalone pi5* CLI -> device
```

The IDE adapter resolves a fixed allowlisted command, acquires `HardwareOwnership`, attaches the
interactive tool to the terminal, and guarantees ownership release in a `finally` block. The bulk
hardware reuse menu calls `hardware_setup_status` across modules. Microphone asset checks reuse standalone
path resolvers via the isolated `ninjarobot_pi5_ide.hardware_config_probe` subprocess to strictly avoid
importing driver modules into the IDE process, preserving intentional microphone runtime containment.
Managed driver implementations and immutable baselines remain unchanged. Configuration import reuses
`discover_pi5_configs`, `import_pi5_configs`, and saves the consolidated robot configuration once after
hardware steps.[^src-20260923-developmentguide-2]

Onboarding state is stored as a versioned JSON object at `~/.local/state/ninjarobot_pi5/setup-progress.json`.
The store enforces nonblocking owner locks, bounded inputs, schema validation, symlink refusal, mode `0600`,
and atomic file replacement without storing secrets or media. `--simulation` prints an offline rehearsal without
modifying real progress; `--resume` re-checks saved settings and rejects simulated records for real-hardware readiness.
Candidate API keys stay in memory until validated, and candidate files roll back on configuration save failure.
Terminal chat uses prompt-toolkit (`terminal_input.py`) with multiline input handling (Enter submits, Shift+Enter or
Alt/Option+Enter adds newlines, Esc then Enter fallback) and portable navigation.[^src-20260923-developmentguide-2]

## Web controller and modular frontend architecture

The Agent layer exposes an HTTPS web controller (`web_app.py`, `web_control.py`) partitioned into two dedicated views:
- Game Pad (`/gamepad`, `gamepad.html`): Direct manual teleoperation with responsive touch D-pad, action triggers (Greeting, AI Camera preview, Emergency Stop, Resume), and a user-created behavior selector.
- Agent Interface (`/agent`, `agent.html`): Dialogue and planning viewport with conversation history, "Clear Message" UI clearing, special robot control toggles (A/B/X/Y), and audio/speech controls.[^src-20260923-developmentguide-2]

Frontend logic is modularized into `app-shared.js` (shared state, websocket communication, modal lifecycle, i18n localization), `app-gamepad.js` (game pad inputs and user behavior dropdown dispatch), and `app-agent.js` (chat stream handling and control button toggle states). The backend exposes `list_user_behaviors` and `run_user_behavior` hooked to IDE `_BehaviorListAdapter(source="user")`, ensuring that user behaviors with motion actions require explicit modal confirmation before execution.[^src-20260923-developmentguide-2]

## Refinement Phase 5 and hardware boundaries

Refinement Phase 5 introduces `ninjarobot_pi5_ide/distance_game.py`, owning strict
target distance tracking (5–60 cm), 3-band tone feedback (440/660/880 Hz via PipeWire),
and `expression_variants.py` for silent OLED eye/face animation presets without extra hardware.[^src-20260923-developmentguide-2]

Emergency stop priority is clarified: `servo.stop` is dispatched from an engine allowlist
with LOW risk rating rather than EMERGENCY, safely interrupting active pulses without unneeded
Level 2 stops. Stop causes are preserved across ramp transitions, obstacles are checked before
and during ramps, and the motion watchdog continues heartbeats during responsive device cleanup.
Proposed hardware changes (movable head, edge sensing, touch input) remain unpurchased, uninstalled
evaluation proposals.[^src-20260923-developmentguide-2]

## Agent information architecture and local tasks

Phase 4 introduces local and external information assistant capabilities. External Google Calendar
synchronization reuses `GoogleCalendarBackend` with local desktop-browser OAuth consent over an SSH
loopback (port 8765), primary-calendar auto-discovery, and remote verification via SSH. `CalendarChat` enforces
internal confirmation authority for calendar writes, rejecting direct command bypasses.
`project_documents.py` and `project_help.py` provide hash-checked runtime retrieval of bounded
published manual sections. `ResearchService` binds allowlisted Tavily snippet results to saved
runs. `BriefingService` generates deterministic bundles on request.[^src-20260923-developmentguide-2]

All state-modifying actions (calendar writes, note edits) require an exact preview and same-session
direct user confirmation. Models and recipes cannot confirm changes or bypass deterministic policy.
Audio playback routes through IDE PipeWire ownership with lead-in silence buffering
(`bluetooth_lead_in_seconds`, default 0.5s) and independent reconnection daemon support.[^src-20260923-developmentguide-2]


[^src-20260923-developmentguide-2]: DevelopmentGuide.md, source version `onboarding-refinement-260923`; registered source `src-20260923-developmentguide-2`.
