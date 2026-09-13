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
- id: src-20260913-developmentguide
  resource: urn:llmwiki:source:src-20260913-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:f6ae6ee1dfe85488f3db13c1d6cc927802d92610860605bd42229d6a3a1d53bf
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-13T14:15:00Z'
  target_hash: sha256:c373fc869943e4029960d393aca1e51ef89c421596f63e3308c8b658730d822f
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

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20260913-developmentguide]

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

## Current checkpoint: completed Phase 4 information work

The project implements full Phase 4 information-assistant capabilities alongside
Phase 4 foundations (M03 memory ranking, M04 read-only recipes, X01 version-2
skills, and X05 public project help), Refinement Phase 5 foundations (optional
distance game and silent expression variations), and system clock access.
The Agent/IDE/driver boundary remains intact: information services and SQLite
records belong to the Agent layer, while hardware coordination belongs to the IDE.[^src-20260913-developmentguide]

Information features include T04 Google Calendar planning (read-only default,
explicit `--write` authorization, SSH tunnel OAuth loopback, exact five-minute previews,
and direct confirmation), T05 research service (allowlisted Tavily snippets, bounded
queries, real source citations, and save-to-note), and T06 notes, checklists, and
requested briefings. Migration 7 adds user-scoped information tables with atomic
approval consumption, seven-day preview cleanup on startup, and a 1,000-record cap per
kind. Model calls cannot confirm calendar or note writes. Physical hardware acceptance,
live account verification, display font repair, and monetary spending caps remain
explicitly unverified.[^src-20260913-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260913-developmentguide]: DevelopmentGuide.md, source version `refinement-phase4-information-260913`; registered source `src-20260913-developmentguide`.
