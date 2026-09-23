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
- id: src-20260923-developmentguide-2
  resource: urn:llmwiki:source:src-20260923-developmentguide-2
  title: DevelopmentGuide.md
  content_hash: sha256:17ba019c024248a5273bf2de3124d7fd62421e82ec2554cd3f756248ebd7ace5
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-23T00:30:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 23 September onboarding refinement, bulk
    settings reuse, Mac Calendar OAuth SSH tunnel, and installer repair evidence; no human
    verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:9121b49c40f7039325ecaccd4cde02febf38d2882a654cccd0f4b3767ff38b49
---

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20260923-developmentguide-2]

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

## Current checkpoint: Refined onboarding, bulk settings reuse, and installer repairs

The project consolidates 23 September 2026 onboarding interface refinements, bulk settings reuse,
Mac Calendar OAuth loopback forwarding, and installer branch/directory repairs alongside the 22 September
guided onboarding CLI, prompt-toolkit multiline chat, 18 September web controller refinement, 17 September
Google Calendar setup and unified CONFIRM flow, 16 September distance game hand-placement correction, 15 September
servo/game repairs, Phase 4 information work (T04 calendar planning, T05 research, T06 notes/checklists/briefings),
Phase 4 foundations (recipes, memory ranking, v2 skills, project help), and system clock access. The Agent/IDE/driver
boundary remains intact: setup wizard orchestration belongs to the Agent layer, while hardware locking and dispatch
belong to the IDE.[^src-20260923-developmentguide-2]

Recent updates add an ASCII welcome screen, numeric menus, a bulk hardware reuse option ("2) Apply existing settings
for all modules"), automatic configuration checks, Enter-to-continue summaries, removal of redundant typed YES/APPLY phrases,
Mac SSH forwarding instructions (`-L 127.0.0.1:8765:127.0.0.1:8765`), waiting updates, callback receipt acknowledgment,
read-only Calendar MCP validation, candidate credential cleanup, key rollback on save failure, microphone subprocess import
containment, and simulation isolation. Root installer updates fix branch disambiguation and support custom installation
directories via `--install-dir`. Physical acceptance, live accounts, display font repair, and monetary spending caps
remain unverified.[^src-20260923-developmentguide-2]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260923-developmentguide-2]: DevelopmentGuide.md, source version `onboarding-refinement-260923`; registered source `src-20260923-developmentguide-2`.
