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
- reminders
- tasks
- memory
- phase2
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260908-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20260908-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:f4ad853bb46a8dd3caa961c2e6337ea316a75889e1c6c049d2960b60507603e0
- id: src-20260908-developmentguide
  resource: urn:llmwiki:source:src-20260908-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:640cb37251c7d9c7d41a23a4998aa0b25dcbfa8bba952435adeda61f821fd6e6
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-08T15:25:18.461989+00:00'
  target_hash: sha256:79e9260a1e363c78e47af7130924231b68d4b1e6532fbce01b288f362d33897f
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

# Features, MCP tools, and Agent Skills

The development guide describes conversational and web interfaces, model
providers, behaviors, memory, and device capabilities. These are documented
implementation areas; use the current code and tests to verify a specific
feature or failure case before changing it.[^src-20260908-developmentguide]

MCP (Model Context Protocol) lets an application discover and call external tools.
The robot tutorial describes allowlisted read-only tools, bounded results,
timeouts, and untrusted external content. Its examples include Tavily search
and a read-only Google Calendar server. Agent Skills package reusable workflows;
they do not grant extra hardware permissions.[^src-20260908-ninjarobot-mcp-skill]

Development wiki skills are a separate coding-tool workflow. This local knowledge
integration does not install a robot MCP provider or change runtime interfaces.
Use the existing robot tutorial for robot extensions and the wiki maintenance
guide for developer knowledge updates.[^src-20260907-knowledgeintegration]

[MCP and skills tutorial](/references/mcp-skills-guide.md).


## Local reminders, task progress and memory

In existing chat, `/remind 120 Practice` creates a silent draft. `/tasks confirm ID`
explicitly schedules the reviewed time and effect. `/tasks`, cancel and snooze
controls also appear in the browser Local tasks panel. Snooze needs fresh review.
Exact dated reminders support daily/weekly repeat and optional reviewed display
text plus a buzzer tone. They do not request wheel movement.[^src-20260908-developmentguide]

The Pi and Agent must stay running. Once saved, reminders need no cloud model.
Late reminders become missed; interrupted delivery becomes uncertain without
automatic replay. A silent reminder's completion means its local inbox result was
saved, not that the user read it. Request completion means response processing
ended; tool evidence determines what is known about external effects.[^src-20260908-developmentguide]

Task progress requires refresh. General requests do not autonomously resume after
restart. Model calls, actual tool attempts including retries, input size, requested
output and time are bounded; this is not a currency-denominated spending cap.
`/memory review`, confirm, edit and forget expose source/confidence and correction.
Confirmed structured preferences resist contradictory inference; arbitrary
natural-language contradiction resolution is not comprehensive.[^src-20260908-developmentguide]

Custom MCP servers require local read-only and retry-safe allowlists. Discovery,
schemas and results are bounded and checked; external output remains untrusted.
The local task tools can list or preview, but have no model confirmation tool.
Calendar writes and later refinement phases are outside this checkpoint.[^src-20260908-ninjarobot-mcp-skill]


[^src-20260908-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `refinement-phase2-260909`; registered source `src-20260908-ninjarobot-mcp-skill`.
[^src-20260908-developmentguide]: DevelopmentGuide.md, source version `refinement-phase2-260909`; registered source `src-20260908-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
