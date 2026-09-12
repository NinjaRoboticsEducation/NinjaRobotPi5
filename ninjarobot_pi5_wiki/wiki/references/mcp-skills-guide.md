---
type: Reference
title: MCP and Agent Skills tutorial
description: Find the complete versioned mcp and agent skills tutorial.
status: draft
tags:
- ninjarobotpi5
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260912-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20260912-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:a378ca8b20ecbab88c423690017a12a8a44d3f0e1e591c4538b34432777ba810
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-12T09:37:00Z'
  target_hash: sha256:dc4de6c4577e4382c67968908cae206f1d79a0f0242a8ed8e8dec44e2389c552
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered Phase 3 follow-up evidence; no human verification
    is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
---

# MCP and Agent Skills tutorial

The tutorial explains external tools, configuration, read-only Tavily and Calendar examples, and reusable Agent Skills. It describes restrictions for the robot Agent, not a development wiki server.[^src-20260912-ninjarobot-mcp-skill]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint

The 12 September source adds the bundled `robot-command-help` skill, `command_help.search`
tool, and natural language help queries mapped to deterministic `/help <topic>` and
`/guide 1` through `/guide 5` commands. Existing MCP extensions gain no direct device access.[^src-20260912-ninjarobot-mcp-skill]


[^src-20260912-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `refinement-phase3-followup-260912`; registered source `src-20260912-ninjarobot-mcp-skill`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
