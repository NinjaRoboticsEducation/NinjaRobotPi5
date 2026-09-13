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
- id: src-20260913-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20260913-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:893fd4a9ceb771012ad2c009bfd5d0ded89959a28341fcb301eee361c318b697
- id: src-20260913-developmentguide
  resource: urn:llmwiki:source:src-20260913-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:f6ae6ee1dfe85488f3db13c1d6cc927802d92610860605bd42229d6a3a1d53bf
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-13T14:15:00Z'
  target_hash: sha256:dc5423cfe29313fe39fe5091bfee22258e23bea18d0a13bcf295e19f7ff9bc85
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered Phase 4 information evidence; no human verification
    is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
---

# Features, MCP tools, and Agent Skills

The development guide describes conversational and web interfaces, model
providers, behaviors, memory, device capabilities, recipes, information services,
and local audio output. These are documented implementation areas; use current code
and tests to verify a specific feature or failure case before changing it.[^src-20260913-developmentguide]

MCP (Model Context Protocol) lets an application discover and call external tools.
The robot tutorial describes allowlisted read-only tools, bounded results,
timeouts, and untrusted external content. Examples include Tavily search and Google
Calendar access. Agent Skills package reusable workflows; they do not grant extra
hardware permissions.[^src-20260913-ninjarobot-mcp-skill]

Development wiki skills are a separate coding-tool workflow. This local knowledge
integration does not install a robot MCP provider or change runtime interfaces.
Use the existing robot tutorial for robot extensions and the wiki maintenance
guide for developer knowledge updates.[^src-20260907-knowledgeintegration]

[MCP and skills tutorial](/references/mcp-skills-guide.md).

## System clock, distance game, and command guidance

The Agent reads the Raspberry Pi OS clock for each turn. The read-only `system.time.get`
tool and `/time` chat command provide fresh date, time, timezone, and offset without
requiring model calls. Relative reminders use this reference.[^src-20260913-developmentguide]

The optional Refinement Phase 5 distance game (`/game start [seconds]`, `/game stop`,
`/game status`, and tools `robot.game.distance.run/stop/status`) provides interactive
distance-based audio feedback using the VL53L0X sensor (5–60 cm range) and buzzer (440/660/880 Hz
tones). It is bundled in the version-1 `distance-game` skill. The bundled `robot-command-help`
skill resolves natural-language questions to deterministic `/help <topic>` and `/guide 1..5`
commands.[^src-20260913-ninjarobot-mcp-skill][^src-20260913-developmentguide]

## Recipes, memory, and information assistant

Phase 4 delivers M03 memory ranking and M04 reviewed local read-only recipes (`/recipes list`,
`show`, `run`, `disable`, and CLI preview/save/rollback). Recipes are owned multi-step
read workflows; they cannot move hardware or schedule reminders. X05 public project help
provides `/project <question>` and the version-2 `project-help` bundled skill.[^src-20260913-developmentguide]

Phase 4 information-assistant tools and commands (`/info`) cover:
- **Calendar planning (T04)**: Google Calendar connect via SSH tunnel loopback, read-only by default, explicit `--write` flag, five-minute exact preview and same-session direct confirmation for writes. Calendar events never silently create local reminders.[^src-20260913-developmentguide][^src-20260913-ninjarobot-mcp-skill]
- **Research service (T05)**: Allowlisted Tavily search with bounded snippets, three questions within 30 seconds, real source citations, and explicit save-to-note actions.[^src-20260913-ninjarobot-mcp-skill]
- **Notes, checklists, and briefings (T06)**: Local SQLite storage (migration 7), atomic note commit with consumed approval, on-request briefings using fixed local dates, and optional speech summary. Stale previews (>7 days) are cleaned on service startup; notes persist up to 1,000 records per kind.[^src-20260913-developmentguide]


[^src-20260913-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `refinement-phase4-information-260913`; registered source `src-20260913-ninjarobot-mcp-skill`.
[^src-20260913-developmentguide]: DevelopmentGuide.md, source version `refinement-phase4-information-260913`; registered source `src-20260913-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
