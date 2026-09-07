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
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260906-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20260906-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:df8076ccc2683b24b6752310558ce4e62828d54cee67f1102aae7196c0ee97bb
- id: src-20260906-developmentguide
  resource: urn:llmwiki:source:src-20260906-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-07T00:45:19Z'
  target_hash: sha256:2c8bea92e1d46f8376737f38a42fc20c1eececf180b22e43e92925ccbb696cb2
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Rechecked the navigation-only correction and updated source versions; other cited
    explanations are unchanged.
  - AI evidence review; no human verification or hardware test is claimed.
---

# Features, MCP tools, and Agent Skills

The development guide describes conversational and web interfaces, model
providers, behaviors, memory, and device capabilities. These are documented
implementation areas; use the current code and tests to verify a specific
feature or failure case before changing it.[^src-20260906-developmentguide]

MCP (Model Context Protocol) lets an application discover and call external tools.
The robot tutorial describes allowlisted read-only tools, bounded results,
timeouts, and untrusted external content. Its examples include Tavily search
and a read-only Google Calendar server. Agent Skills package reusable workflows;
they do not grant extra hardware permissions.[^src-20260906-ninjarobot-mcp-skill]

Development wiki skills are a separate coding-tool workflow. This local knowledge
integration does not install a robot MCP provider or change runtime interfaces.
Use the existing robot tutorial for robot extensions and the wiki maintenance
guide for developer knowledge updates.[^src-20260907-knowledgeintegration]

[MCP and skills tutorial](/references/mcp-skills-guide.md).


[^src-20260906-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `migration-2026-09-07`; registered source `src-20260906-ninjarobot-mcp-skill`.
[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
