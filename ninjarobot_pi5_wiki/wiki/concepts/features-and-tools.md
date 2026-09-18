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
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260918-developmentguide
  resource: urn:llmwiki:source:src-20260918-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:a4295e369acd972b74b34383683623b37ef8a1a4cf1d2e066c50d7d4fc6ec649
- id: src-20260918-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20260918-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:f12a0d70b9fc6b5be50e53b4a1278ac50d7c66054934239883803530fde7242d
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
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
  target_hash: sha256:6721838c43610854691cd41f6eabd1a6ec2109cf76f61899202550e49abf455a
---

# Features, MCP tools, and Agent Skills

The development guide describes conversational and web interfaces, model
providers, behaviors, memory, device capabilities, recipes, information services,
and local audio output. These are documented implementation areas; use current code
and tests to verify a specific feature or failure case before changing it.[^src-20260918-developmentguide]

MCP (Model Context Protocol) lets an application discover and call external tools.
The robot tutorial describes allowlisted read-only tools, bounded results,
timeouts, and untrusted external content. Examples include Tavily search and Google
Calendar access. Agent Skills package reusable workflows; they do not grant extra
hardware permissions.[^src-20260918-ninjarobot-mcp-skill]

Development wiki skills are a separate coding-tool workflow. This local knowledge
integration does not install a robot MCP provider or change runtime interfaces.
Use the existing robot tutorial for robot extensions and the wiki maintenance
guide for developer knowledge updates.[^src-20260907-knowledgeintegration]

[MCP and skills tutorial](/references/mcp-skills-guide.md).

## Web controller dual-view interface and user behaviors

The HTTPS web controller provides two purpose-built views switched via the hamburger menu:
- **Game Pad View** (`/gamepad`): Focuses on teleoperation with responsive touch D-pad, action triggers (Greeting, AI Camera preview, Emergency Stop, Resume), and a user-created behaviors selector. User-saved behaviors containing actuator movements prompt an explicit confirmation modal before executing via `run_user_behavior`.
- **Agent View** (`/agent`): Provides a dedicated conversation pane, chat composer, a "Clear Message" action to clear visible chat items without resetting the backend session, special robot control toggles (A / B / X / Y) with high-contrast active/inactive styling, and audio control toggles (Web Mic, Voice Input, Speech ON).[^src-20260918-developmentguide]

All interface strings support full 4-language localization (English, Japanese, Traditional Chinese, Simplified Chinese) with 146 translation keys each.[^src-20260918-developmentguide]

## System clock, distance game, and command guidance

The Agent reads the Raspberry Pi OS clock for each turn. The read-only `system.time.get`
tool and `/time` chat command provide fresh date, time, timezone, and offset without
requiring model calls. Relative reminders use this reference.[^src-20260918-developmentguide]

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
`/help <topic>` and `/guide 1..5` commands.[^src-20260918-ninjarobot-mcp-skill][^src-20260918-developmentguide]

On the web controller, movement failures surface as visible UI notifications in addition to
activity messages, preventing silent background task failures.[^src-20260918-developmentguide]

## Recipes, memory, and information assistant

Phase 4 delivers M03 memory ranking and M04 reviewed local read-only recipes (`/recipes list`,
`show`, `run`, `disable`, and CLI preview/save/rollback). Recipes are owned multi-step
read workflows; they cannot move hardware or schedule reminders. X05 public project help
provides `/project <question>` and the version-2 `project-help` bundled skill, reading hash-checked
bounded manual sections (`project_documents.py`).[^src-20260918-developmentguide]

Phase 4 information-assistant tools and commands (`/info`) cover:
- **Calendar planning (T04)**: Google Calendar connect via port 8765 loopback SSH tunnel, primary-calendar auto-discovery, read-only by default, and explicit `--write` flag. Event creation, updating, and deletion (`calendar.events.preview_create/update/delete`) generate an exact 5-minute preview with field-specific validation errors (e.g. required timezone `Asia/Tokyo`, non-empty title, ISO timestamp range). Authorizing the exact preview requires a standalone single-word `CONFIRM` reply in chat; `CANCEL` discards it. Direct command bypasses are rejected. Updates and deletions are bounded to events created by the connection.[^src-20260918-developmentguide][^src-20260918-ninjarobot-mcp-skill]
- **Research service (T05)**: Allowlisted Tavily search with bounded snippets, three questions within 30 seconds, real source citations, and explicit save-to-note actions.[^src-20260918-ninjarobot-mcp-skill]
- **Notes, checklists, and briefings (T06)**: Local SQLite storage (migration 7), atomic note commit with consumed approval, on-request briefings using fixed local dates, and optional speech summary. Stale previews (>7 days) are cleaned on service startup; notes persist up to 1,000 records per kind.[^src-20260918-developmentguide]


[^src-20260918-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `ui-refinement-260918`; registered source `src-20260918-ninjarobot-mcp-skill`.
[^src-20260918-developmentguide]: DevelopmentGuide.md, source version `ui-refinement-260918`; registered source `src-20260918-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
