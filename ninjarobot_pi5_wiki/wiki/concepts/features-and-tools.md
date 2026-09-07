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
- id: src-20260906-knowledgeintegration
  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-06T22:54:06Z'
  target_hash: sha256:0fd2add29e1e2bb810876e9445514ea215b313c9df2e10dc4aa1e50b70a1b69a
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against its listed manual sections and integration evidence.
  - Claims describe documented contracts and knowledge workflow; current hardware
    operation and interactive editor activation are not certified.
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
guide for developer knowledge updates.[^src-20260906-knowledgeintegration]

[MCP and skills tutorial](/references/mcp-skills-guide.md).


[^src-20260906-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `migration-2026-09-07`; registered source `src-20260906-ninjarobot-mcp-skill`.
[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.
[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
