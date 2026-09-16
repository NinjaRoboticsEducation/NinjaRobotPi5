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
- id: src-20260916-developmentguide
  resource: urn:llmwiki:source:src-20260916-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:3630ca96f9314ad2d253476a2131e1160f87fe3c0bdae3f10ed5c89f85ae21e0
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-16T00:26:00Z'
  target_hash: sha256:7687b443231b72a15a5031b7c97906b00f9abb794738c65be7b8ccc32f018eba
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

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20260916-developmentguide]

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

## Current checkpoint: distance game hand-placement correction and follow-up repairs

The project consolidates the 16 September 2026 hand-placement correction and 15
September follow-up repairs alongside completed Phase 4 information work (T04
calendar planning, T05 research, T06 notes/checklists/briefings), Phase 4
foundations (recipes, memory ranking, v2 skills, project help), and system clock
access. The Agent/IDE/driver boundary remains intact: information services and SQLite
records belong to the Agent layer, while hardware coordination belongs to the IDE.[^src-20260916-developmentguide]

Recent updates establish that the distance game begins before the final chat response;
players place their hand 5–60 cm in front of the sensor when requesting to play, and
web chat emits an immediate starting notice. Sensor readings out-of-range or missing a
target silently wait for a hand rather than exiting after two seconds with a false
sensor-unavailable fault. The 15 September repairs correct `servo.stop` dispatch from the
interrupt allowlist as LOW risk without triggering a false Level 2 stop, preserve ramp
stop causes through the motion owner, ensure bounded distance preparation and sensor
recovery, re-initialize the buzzer on repeated games, keep watchdog heartbeats during
cleanup, and introduce rolling context in `AgentLoop`. Physical acceptance, live accounts,
display font repair, and monetary spending caps remain unverified.[^src-20260916-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260916-developmentguide]: DevelopmentGuide.md, source version `distance-game-hand-placement-260916`; registered source `src-20260916-developmentguide`.
