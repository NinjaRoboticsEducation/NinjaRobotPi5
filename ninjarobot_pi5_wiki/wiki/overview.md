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
- id: src-20260917-developmentguide
  resource: urn:llmwiki:source:src-20260917-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:55b061c1a72d4b5f81693f83f2ae39200ff8ed7ea992645e83e661ac5efcd0f0
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-17T15:40:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 17 September calendar CONFIRM flow, guided
    authorization, and project help evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
  target_hash: sha256:784a73c3673e0321f072a331f8272333775f856af4ca2a69cbcafd09c3af5f37
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20260917-developmentguide]

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

## Current checkpoint: Calendar guided setup, unified CONFIRM flow, and project help retrieval

The project consolidates 17 September 2026 calendar authorization and confirmation repairs
alongside the 16 September distance game hand-placement correction, 15 September follow-up
repairs, completed Phase 4 information work (T04 calendar planning, T05 research, T06
notes/checklists/briefings), Phase 4 foundations (recipes, memory ranking, v2 skills, project
help), and system clock access. The Agent/IDE/driver boundary remains intact: information
services and SQLite records belong to the Agent layer, while hardware coordination belongs to
the IDE.[^src-20260917-developmentguide]

Recent updates establish guided Google Calendar OAuth via port 8765 loopback SSH tunnel with
primary-calendar auto-discovery, user-scoped connection reuse, and field-specific preview
validation (requiring title, start, end, and timezone e.g. `Asia/Tokyo`). Calendar event create,
update, and delete operations use a unified chat confirmation contract requiring a standalone
single-word `CONFIRM` or `CANCEL`, explicitly rejecting direct command confirmation bypasses.
Runtime public project help searches bounded sections of current published manuals with hash
validation (`project_documents.py`), rejecting unlisted or private files and attaching clear
draft/limitation notices. Physical acceptance, live accounts, display font repair, and monetary
spending caps remain unverified.[^src-20260917-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260917-developmentguide]: DevelopmentGuide.md, source version `calendar-confirm-260917`; registered source `src-20260917-developmentguide`.
