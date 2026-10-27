---
type: Concept
title: Features, MCP tools, and Agent Skills
description: User features, MCP tool boundaries, Agent Skills, and what local code
  does and does not do.
status: draft
tags:
- features
- mcp
- skills
- tools
- capabilities
- clock
- distance-game
- phase4
- recipes
- memory
- information
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
- id: src-20261027-developmentguide
  resource: urn:llmwiki:source:src-20261027-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:3ab4adc6f8052f7975b17a7ebcdd893df425e47b9f16e2127a2751f71d9e73c7
- id: src-20261027-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20261027-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:6a1b6e3538d38533ad9b9a254877f7d966df732225a0d3d432b168ffc7fdf2df
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
  target_hash: sha256:7a9cb4580f165a4d5866be992bbd5e92f0257f349069d2f9b67fdee8dd6b0514
---

# Features, MCP tools, and Agent Skills

The development guide describes conversational and web interfaces, model
providers, behaviors, memory, device capabilities, recipes, information services,
and local audio output. These are documented implementation areas; use current code
and tests to verify a specific feature or failure case before changing it.[^src-20261027-developmentguide]

MCP (Model Context Protocol) lets an application discover and call external tools.
The robot tutorial describes allowlisted read-only tools, bounded results,
timeouts, and untrusted external content. Examples include Tavily search, Google
Calendar access, and Notion document retrieval. Agent Skills package reusable workflows;
they do not grant extra hardware permissions.[^src-20261027-ninjarobot-mcp-skill]

Development wiki skills are a separate coding-tool workflow. This local knowledge
integration does not install a robot MCP provider or change runtime interfaces.
Use the existing robot tutorial for robot extensions and the wiki maintenance
guide for developer knowledge updates.[^src-20260907-knowledgeintegration]

[MCP and skills tutorial](/references/mcp-skills-guide.md).

## Multi-HAT servo and behavior capabilities

Robot movement and servo tools (`servo.move`, `servo.status`, `servo.stop`, and coordinated `drive` stages in behaviors) operate transparently across all three supported Expansion HAT profiles (`1. DFRobot DFR0566 IO Expansion HAT`, `2. SunFounder Robot HAT`, and `3. General PCA9685 PWM Expansion HAT`). When a SunFounder Robot HAT (`hat_pwm0`..`hat_pwm11`) or General PCA9685 HAT (`hat_pwm0`..`hat_pwm15`) is configured via `ninjarobot onboard`, auxiliary servo roles such as `head_pan`, `head_tilt`, `arm`, and `gripper` can be targeted independently in behavior definitions without requiring simultaneous wheel motion. External MCP server configuration and Agent Skill schemas remain unchanged.[^src-20261027-ninjarobot-mcp-skill]

Embedded I2S speaker initialization on SunFounder Robot HAT provides verified audio output via ALSA/PipeWire sinks (`googlevoicehat-soundcard` or `hifiberry-dac`) with GPIO12 amplifier enabling and chime playback (`play_sunfounder_speaker_test_tone()`), eliminating Bluetooth speaker dependency on Profile 2.[^src-20261027-developmentguide]

## Guided onboarding, interactive chat, and external MCP presets

Guided setup via `ninjarobot onboard` (or `ninjarobot onboard --step mcp`) configures external
MCP servers with read-only allowlists:
- **Tavily Search**: Hosted HTTPS transport using a bearer key from `SecretStore`; provides the `tavily_search` tool for bounded research snippets. Replacement keys are validated prior to saving.[^src-20261027-ninjarobot-mcp-skill]
- **Google Calendar**: Bundled external stdio MCP process reusing `calendar_oauth.authorize` and `GoogleCalendarBackend`; requests read-only event scope and exposes `list_today_events` with bounded title, start, end, and status fields. For Mac browsers, users forward port 8765 (`ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765 USER@ROBOT`). The wizard displays waiting updates, acknowledges the callback, validates an end-to-end bounded read-only events call, and cleans up candidate credential files on failure. It remains separate from native Calendar integration.[^src-20261027-ninjarobot-mcp-skill]
- **Notion**: Official hosted HTTPS transport using SDK OAuth on loopback callback port 8766; exposes `notion-search` and `notion-fetch` for workspace pages. Remote authorization requires SSH port forwarding (`ssh -L 8766:127.0.0.1:8766 USER@ROBOT`). Token refresh fails closed if reauthorization is needed.[^src-20261027-ninjarobot-mcp-skill]

Preset configuration verifies that all allowlisted tool names are discovered before saving. Presets refuse
to overwrite existing custom MCP entries in `mcp.toml`. Secrets never appear in configuration or logs.
Manual management uses `ninjarobot mcp list`, `mcp inspect SERVER`, and `mcp health SERVER`.[^src-20261027-ninjarobot-mcp-skill]

Interactive terminal chat uses prompt-toolkit (`terminal_input.py`): ordinary typing and arrow keys navigate
and edit without escape sequence artifacts, Enter submits, Shift+Enter or Alt/Option+Enter inserts a newline
when distinguished, and Esc then Enter serves as the universal SSH newline fallback. Help hints (`/help`)
and keyboard shortcuts display on startup.[^src-20261027-developmentguide]

## Web controller dual-view interface and user behaviors

The HTTPS web controller provides two purpose-built views switched via the hamburger menu:
- **Game Pad View** (`/gamepad`): Focuses on teleoperation with responsive touch D-pad, action triggers (Greeting, AI Camera preview, Emergency Stop, Resume), and a user-created behaviors selector. User-saved behaviors containing actuator movements prompt an explicit confirmation modal before executing via `run_user_behavior`.
- **Agent View** (`/agent`): Provides a dedicated conversation pane, chat composer, a "Clear Message" action to clear visible chat items without resetting the backend session, special robot control toggles (A / B / X / Y) with high-contrast active/inactive styling, and audio control toggles (Web Mic, Voice Input, Speech ON).[^src-20261027-developmentguide]

All interface strings support full 4-language localization (English, Japanese, Traditional Chinese, Simplified Chinese) with 146 translation keys each.[^src-20261027-developmentguide]

## System clock, distance game, and command guidance

The Agent reads the Raspberry Pi OS clock for each turn. The read-only `system.time.get`
tool and `/time` chat command provide fresh date, time, timezone, and offset without
requiring model calls. Relative reminders use this reference.[^src-20261027-developmentguide]

The distance game (`/game start [seconds]`, `/game stop`, `/game status`, and tools
`robot.game.distance.run/stop/status`) provides interactive audio feedback using the VL53L0X
sensor (5–60 cm range) and buzzer (440/660/880 Hz tones). The game starts before the final chat
answer; players should place their hand in front of the sensor immediately, guided by an
immediate web chat notice. If readings are outside 5–60 cm or no target is detected, the game
waits silently until a hand arrives or the timer expires, returning `no_target_detected` rather
than terminating after two seconds as a device error. Results retain sample metrics including
`no_target_samples`, `rejection_counts`, and `last_sample_issue` (`invalid_samples` counts tone-rejected
samples). The bundled `distance-game` skill v1 distinguishes no-target conditions from real hardware
faults. The bundled `robot-command-help` skill resolves natural-language questions to deterministic
`/help <topic>` and `/guide 1..5` commands.[^src-20261027-ninjarobot-mcp-skill][^src-20261027-developmentguide]

On the web controller, movement failures surface as visible UI notifications in addition to
activity messages, preventing silent background task failures.[^src-20261027-developmentguide]

## Recipes, memory, and information assistant

Phase 4 delivers M03 memory ranking and M04 reviewed local read-only recipes (`/recipes list`,
`show`, `run`, `disable`, and CLI preview/save/rollback). Recipes are owned multi-step
read workflows; they cannot move hardware or schedule reminders. X05 public project help
provides `/project <question>` and the version-2 `project-help` bundled skill, reading hash-checked
bounded manual sections (`project_documents.py`).[^src-20261027-developmentguide]

Phase 4 information-assistant tools and commands (`/info`) cover:
- **Calendar planning (T04)**: Google Calendar connect via port 8765 loopback SSH tunnel, primary-calendar auto-discovery, read-only by default, and explicit `--write` flag. Event creation, updating, and deletion (`calendar.events.preview_create/update/delete`) generate an exact 5-minute preview with field-specific validation errors (e.g. required timezone `Asia/Tokyo`, non-empty title, ISO timestamp range). Authorizing the exact preview requires a standalone single-word `CONFIRM` reply in chat; `CANCEL` discards it. Direct command bypasses are rejected. Updates and deletions are bounded to events created by the connection.[^src-20261027-developmentguide][^src-20261027-ninjarobot-mcp-skill]
- **Research service (T05)**: Allowlisted Tavily search with bounded snippets, three questions within 30 seconds, real source citations, and explicit save-to-note actions.[^src-20261027-ninjarobot-mcp-skill]
- **Notes, checklists, and briefings (T06)**: Local SQLite storage (migration 7), atomic note commit with consumed approval, on-request briefings using fixed local dates, and optional speech summary. Stale previews (>7 days) are cleaned on service startup; notes persist up to 1,000 records per kind.[^src-20261027-developmentguide]


[^src-20261027-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-ninjarobot-mcp-skill`.
[^src-20261027-developmentguide]: DevelopmentGuide.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
