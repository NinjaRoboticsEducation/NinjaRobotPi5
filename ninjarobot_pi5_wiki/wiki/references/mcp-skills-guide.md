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
- id: src-20260922-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20260922-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:eaa88222846e1d6a20fd29d564726304013056bbf6a8d4555712a883ad3fcafc
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-22T13:30:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 22 September guided onboarding, curl bootstrap,
    editable terminal chat, and external MCP preset evidence; no human verification
    is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:a0aab187bd46253090e52294781606cdc4f20dc79acd44bcfe0b4a91234af717
---

# MCP and Agent Skills tutorial

The tutorial explains external tools, configuration, read-only Tavily and Calendar examples, and reusable Agent Skills. It describes restrictions for the robot Agent, not a development wiki server.[^src-20260922-ninjarobot-mcp-skill]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Guided onboarding, curl bootstrap, and editable chat

The 22 September 2026 source (`2026-09-22`) details guided external MCP setup via `ninjarobot onboard --step mcp`,
read-only allowlists for Tavily Search (`tavily_search`), Google Calendar (`list_today_events` stdio MCP),
and Notion (`notion-search`, `notion-fetch` OAuth on loopback 8766), tool discovery validation, and MCP inspection
commands (`ninjarobot mcp list`, `mcp inspect SERVER`, `mcp health SERVER`), alongside 18 September web interface navigation
across Game Pad and Agent views, user-created behavior safety confirmation, and retained chat commands (`/guide`,
`/game`, `/tasks`, `/help`), 17 September Google Calendar tools (`calendar.list`, `calendar.events.preview_create/update/delete`)
with field-specific validation errors and chat `CONFIRM` / `CANCEL` authorization, public project help tools backed by
`project_documents.py`, Tavily research, local notes/briefings, bundled `distance-game` skill v1, and bundled `project-help`
skill v2. External MCP extensions retain no direct device or hardware access.[^src-20260922-ninjarobot-mcp-skill]


[^src-20260922-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `onboarding-install-chat-260922`; registered source `src-20260922-ninjarobot-mcp-skill`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
