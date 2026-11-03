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
- id: src-20261103-developmentguide
  resource: urn:llmwiki:source:src-20261103-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:b6f8ff4f81477bbd155436abf135e93acfb0dab78568e498a11986ca8efd43a4
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
  performed_at: '2026-11-03T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 3 November SunFounder Fusion HAT+ kernel
    driver integration and calibration draft staging evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:7ddfb42239b6a30c898b0770da9c883794681d3cb9de85bb7413aeafe3cce545
---

# Features, MCP tools, and Agent Skills

The development guide describes conversational and web interfaces, model
providers, behaviors, memory, device capabilities, recipes, information services,
and local audio output. These are documented implementation areas; use current code
and tests to verify a specific feature or failure case before changing it.[^src-20261103-developmentguide]

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

Robot movement and servo tools (`servo.move`, `servo.status`, `servo.stop`, and coordinated `drive` stages in behaviors) operate transparently across all three supported Expansion HAT profiles (`1. DFRobot DFR0566 IO Expansion HAT`, `2. SunFounder Fusion HAT+`, and `3. General PCA9685 PWM Expansion HAT`). When a SunFounder Fusion HAT+ (`hat_pwm0`..`hat_pwm11`) or General PCA9685 HAT (`hat_pwm0`..`hat_pwm15`) is configured via `ninjarobot onboard`, auxiliary servo roles such as `head_pan`, `head_tilt`, `arm`, and `gripper` can be targeted independently in behavior definitions without requiring simultaneous wheel motion. External MCP server configuration and Agent Skill schemas remain unchanged.[^src-20261027-ninjarobot-mcp-skill]

On SunFounder Fusion HAT+, `FusionHatPlusBackend` provides direct sysfs-backed hardware PWM control across 12 ports (`hat_pwm0`..`hat_pwm11`) with class-level locking and fixed 50 Hz PWM period. In-memory calibration draft staging allows operators to adjust Min (V), Max (X), and Center (C) in any order, staging points with Enter/Space without immediate file writes, saving atomically with F (`500 <= Min < Center < Max <= 2500` microseconds) to `servo.json`, or discarding with Q, exiting cleanly without centering servos.[^src-20261103-developmentguide]

Embedded I2S speaker initialization on SunFounder Fusion HAT+ provides verified audio output via ALSA/PipeWire sinks (`googlevoicehat-soundcard` or `hifiberry-dac`) with GPIO12 amplifier enabling and Fusion kernel speaker node control (eliminating independent raw I2C `0x31` writes), and verification chime playback (`play_sunfounder_speaker_test_tone()`), eliminating Bluetooth speaker dependency on Profile 2. In Agent chat, `/speech status` and `/speech outputs` inspect synthesis and playback separately; ALSA readiness and playback agree when PipeWire tools are present without an I2S sink; and Bluetooth never falls back to an arbitrary local speaker.[^src-20261103-developmentguide]

Ollama catalog discovery queries local models without credentials and cloud models when an API key is stored. Interactive selection and CLI selection (`ninjarobot model select MODEL --provider ollama --route local|cloud`) persist provider `base_url` route without downloading weights during listing. Completed non-latching full stops release their local presentation gate after cleanup, while battery voltage monitoring enforces `battery_undervoltage` cutoff (6.90 V) with persisted fault details and stale telemetry rejection.[^src-20261103-developmentguide]

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
and edit without escape sequence artifacts, Enter submits, Shift+Enter or Alt/Option+Enter inserts a newline,
and Esc then Enter provides a fallback. The chat loop trims rolling context safely and displays truncation
notices when provider token caps approach.[^src-20261103-developmentguide]


[^src-20261103-developmentguide]: DevelopmentGuide.md, source version `fusion-hat-plus-261103`; registered source `src-20261103-developmentguide`.
[^src-20261027-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-ninjarobot-mcp-skill`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
