---
type: Concept
title: NinjaRobotPi5 project overview
description: Start here for architecture, setup, features, development history, and
  current evidence.
status: draft
tags:
- ninjarobotpi5
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20260922-developmentguide
  resource: urn:llmwiki:source:src-20260922-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:d3e8a50fe808614a7affbaa221fd457f8e981931d43bc5c17a8bc89be89d1a31
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-22T13:30:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 22 September guided onboarding, curl bootstrap,
    editable terminal chat, and external MCP preset evidence; no human verification
    is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:ee8ea861c1eff08bb394641ad04d9c3563aee3322bed327c7ce4b8b45881f2a7
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20260922-developmentguide]

The local wiki is the primary developer knowledge collection. Full manuals are
versioned under raw source folders; outer README links and the project knowledge
map identify the current versions. Read source records and limitations, then
compare important claims with the current checkout before coding.[^src-20260907-knowledgeintegration]

## Browse project knowledge

- [Architecture and hardware ownership](concepts/architecture.md)
- [Development and documentation workflow](concepts/development-workflow.md)
- [Installation and hardware checks](concepts/installation.md)
- [Features, MCP tools, and Agent Skills](concepts/features-and-tools.md)
- [Development history](concepts/development-history.md)
- [Known knowledge limitations](analyses/knowledge-limitations.md)
- [Installation manual](references/installation-guide.md)
- [Development manual](references/development-guide.md)
- [Development log](references/development-log.md)
- [MCP and skills tutorial](references/mcp-skills-guide.md)

## Current checkpoint: Guided onboarding, curl bootstrap, and editable chat

The project consolidates 22 September 2026 guided onboarding, curl bootstrap, and editable
terminal chat alongside the 18 September web controller refinement, 17 September Google
Calendar guided setup and unified CONFIRM flow, 16 September distance game hand-placement
correction, 15 September servo/game repairs, Phase 4 information work (T04 calendar planning,
T05 research, T06 notes/checklists/briefings), Phase 4 foundations (recipes, memory ranking,
v2 skills, project help), and system clock access. The Agent/IDE/driver boundary remains
intact: setup wizard orchestration belongs to the Agent layer, while hardware locking and
dispatch belong to the IDE.[^src-20260922-developmentguide]

Recent updates add the `ninjarobot` CLI entry point with resumable onboarding (`ninjarobot onboard`)
covering 5 mandatory hardware components (`pi5buzzer`, `pi5disp`, `pi5vl53l0x`, `pi5servo`, `pi5camera`),
optional Bluetooth/whisper.cpp microphone setup, 4 model providers, 3 read-only external MCP presets
(Tavily Search, Google Calendar stdio MCP, Notion SDK OAuth on loopback port 8766), remote access
(ngrok or same-Wi-Fi HTTPS), and simulation/real launch into chat. Interactive terminal chat uses
prompt-toolkit with multiline keybindings. The root installer supports direct curl streaming bootstrap
with commit verification. Physical acceptance, live accounts, display font repair, and monetary spending
caps remain unverified.[^src-20260922-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260922-developmentguide]: DevelopmentGuide.md, source version `onboarding-install-chat-260922`; registered source `src-20260922-developmentguide`.
