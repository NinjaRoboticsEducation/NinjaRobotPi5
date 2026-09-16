---
type: Concept
title: Features, MCP tools, and Agent Skills
description: Documented Agent features, external read-only tools, and reusable skills.
status: draft
tags:
- features
- mcp
- skills
- calendar
- tools
- agent
- reminders
- tasks
- memory
- speech
- command-help
- recipes
- information
- distance-game
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260916-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20260916-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:9271738a97134820483f2bb692380896bc8327a71abfde198776a19d9892e43f
- id: src-20260916-developmentguide
  resource: urn:llmwiki:source:src-20260916-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:3630ca96f9314ad2d253476a2131e1160f87fe3c0bdae3f10ed5c89f85ae21e0
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-16T00:26:00Z'
  target_hash: sha256:34b8e2f65029f503fa8efe51d5e2520f8bb3d03adb7d037a4fee3ccad685f567
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 16 September distance game and follow-up
    evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
---

# Features, MCP tools, and Agent Skills

The development guide describes conversational and web interfaces, model
providers, behaviors, memory, device capabilities, recipes, information services,
and local audio output. These are documented implementation areas; use current code
and tests to verify a specific feature or failure case before changing it.[^src-20260916-developmentguide]

MCP (Model Context Protocol) lets an application discover and call external tools.
The robot tutorial describes allowlisted read-only tools, bounded results,
timeouts, and untrusted external content. Examples include Tavily search and Google
Calendar access. Agent Skills package reusable workflows; they do not grant extra
hardware permissions.[^src-20260916-ninjarobot-mcp-skill]

Development wiki skills are a separate coding-tool workflow. This local knowledge
integration does not install a robot MCP provider or change runtime interfaces.
Use the existing robot tutorial for robot extensions and the wiki maintenance
guide for developer knowledge updates.[^src-20260907-knowledgeintegration]

[MCP and skills tutorial](/references/mcp-skills-guide.md).

## System clock, distance game, and command guidance

The Agent reads the Raspberry Pi OS clock for each turn. The read-only `system.time.get`
tool and `/time` chat command provide fresh date, time, timezone, and offset without
requiring model calls. Relative reminders use this reference.[^src-20260916-developmentguide]

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
`/help <topic>` and `/guide 1..5` commands.[^src-20260916-ninjarobot-mcp-skill][^src-20260916-developmentguide]

On the web controller, movement failures surface as visible UI notifications in addition to
activity messages, preventing silent background task failures.[^src-20260916-developmentguide]

## Recipes, memory, and information assistant

Phase 4 delivers M03 memory ranking and M04 reviewed local read-only recipes (`/recipes list`,
`show`, `run`, `disable`, and CLI preview/save/rollback). Recipes are owned multi-step
read workflows; they cannot move hardware or schedule reminders. X05 public project help
provides `/project <question>` and the version-2 `project-help` bundled skill.[^src-20260916-developmentguide]

Phase 4 information-assistant tools and commands (`/info`) cover:
- **Calendar planning (T04)**: Google Calendar connect via SSH tunnel loopback, read-only by default, explicit `--write` flag, five-minute exact preview and same-session direct confirmation for writes. Calendar events never silently create local reminders.[^src-20260916-developmentguide][^src-20260916-ninjarobot-mcp-skill]
- **Research service (T05)**: Allowlisted Tavily search with bounded snippets, three questions within 30 seconds, real source citations, and explicit save-to-note actions.[^src-20260916-ninjarobot-mcp-skill]
- **Notes, checklists, and briefings (T06)**: Local SQLite storage (migration 7), atomic note commit with consumed approval, on-request briefings using fixed local dates, and optional speech summary. Stale previews (>7 days) are cleaned on service startup; notes persist up to 1,000 records per kind.[^src-20260916-developmentguide]


[^src-20260916-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `distance-game-hand-placement-260916`; registered source `src-20260916-ninjarobot-mcp-skill`.
[^src-20260916-developmentguide]: DevelopmentGuide.md, source version `distance-game-hand-placement-260916`; registered source `src-20260916-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
