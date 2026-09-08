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
- id: src-20260908-developmentguide
  resource: urn:llmwiki:source:src-20260908-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:640cb37251c7d9c7d41a23a4998aa0b25dcbfa8bba952435adeda61f821fd6e6
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-08T15:25:18.461989+00:00'
  target_hash: sha256:872ba8ad84d8801b976e4dbfc5c56ce45440107854fd5bcb7e7f06bfdae1c297
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against its registered manual checkpoint and retained source
    text; no human verification is claimed.
  - New checkpoint claims distinguish software tests from physical acceptance, pending
    managed changes and the monetary-budget gap; retained navigation claims remain
    source-supported.
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20260908-developmentguide]

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


## Phase 2 checkpoint

The local task assistant now has reviewed reminders, durable request records and
preference correction. Development pauses before Phase 3 for owner testing.
The Agent/IDE/driver boundary remains. Two managed-driver repairs are pending,
and bounded model usage is not a currency-denominated spending cap. Read
[local tasks and memory](concepts/features-and-tools.md) before treating a saved
request as a delivered notification.[^src-20260908-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260908-developmentguide]: DevelopmentGuide.md, source version `refinement-phase2-260909`; registered source `src-20260908-developmentguide`.
