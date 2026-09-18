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
  target_hash: sha256:758ac4afb97d2dbf200b4ef93c20f17af99cfb72140b0977e838299e57883057
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20260918-developmentguide]

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

## Current checkpoint: Web interface refinement, modular frontend, and terminal menu consolidation

The project consolidates 18 September 2026 web interface refinements and terminal menu
reorganization alongside the 17 September Google Calendar guided setup and unified CONFIRM flow,
16 September distance game hand-placement correction, 15 September servo/game repairs, Phase 4
information work (T04 calendar planning, T05 research, T06 notes/checklists/briefings), Phase 4
foundations (recipes, memory ranking, v2 skills, project help), and system clock access.
The Agent/IDE/driver boundary remains intact: web presentation and information services belong
to the Agent layer, while hardware coordination belongs to the IDE.[^src-20260918-developmentguide]

Recent updates partition the web controller into dedicated Game Pad (`/gamepad`) and Agent Interface
(`/agent`) views with persistent user preference and a restructured hamburger menu (Language, Control
Interface, System Power). Frontend code is modularized into `app-shared.js`, `app-gamepad.js`, and
`app-agent.js`. User-created behaviors can be executed from the web UI with motion confirmation modals.
Agent interface button styles feature high-contrast active/inactive state toggles for special robot
controls (A/B/X/Y) and audio controls. Full 4-language i18n parity is maintained across 146 translation
keys per locale. Terminal IDE navigation is streamlined to options 1–5 and Q (Bluetooth connection is
option 5). Physical acceptance, live accounts, display font repair, and monetary spending caps remain
unverified.[^src-20260918-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260918-developmentguide]: DevelopmentGuide.md, source version `ui-refinement-260918`; registered source `src-20260918-developmentguide`.
