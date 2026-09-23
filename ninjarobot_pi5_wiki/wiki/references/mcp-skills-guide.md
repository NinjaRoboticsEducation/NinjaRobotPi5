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
- id: src-20260923-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20260923-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:4f6a311d94749cca99cc31fc12a6a02f90157cee7420a9f923a47290ecf9d1e2
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
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
  target_hash: sha256:db81214c7a9d11745149cbb1577a884f5dc96511078e8f7bca8de4290ce34686
---

# MCP and Agent Skills tutorial

The tutorial explains external tools, configuration, read-only Tavily and Calendar examples, and reusable Agent Skills. It describes restrictions for the robot Agent, not a development wiki server.[^src-20260923-ninjarobot-mcp-skill]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Refined onboarding and Google Calendar MCP OAuth

The 23 September 2026 source (`2026-09-23-02`) details refined external MCP configuration via `ninjarobot onboard --step mcp`,
including Google Cloud project/API setup instructions, Desktop OAuth client creation, credential placement, Mac SSH port forwarding
(`ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765 YOUR_PI_USER@YOUR_PI_HOST`), periodic waiting status, callback
receipt acknowledgment, and end-to-end validation via an isolated bounded read-only `list_today_events` call through the external MCP server.
Failed attempts clean up candidate credentials and preserve working configuration. Read-only allowlists cover Tavily Search (`tavily_search`),
Google Calendar (`list_today_events` stdio MCP), and Notion (`notion-search`, `notion-fetch` OAuth on loopback 8766), with tool discovery
validation and inspection commands (`ninjarobot mcp list`, `mcp inspect SERVER`, `mcp health SERVER`), alongside 18 September web interface
navigation, 17 September Google Calendar tools (`calendar.list`, `calendar.events.preview_create/update/delete`) with chat `CONFIRM` / `CANCEL`
authorization, public project help tools backed by `project_documents.py`, Tavily research, local notes/briefings, bundled `distance-game`
skill v1, and bundled `project-help` skill v2. External MCP extensions retain no direct device or hardware access.[^src-20260923-ninjarobot-mcp-skill]


[^src-20260923-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `onboarding-refinement-260923`; registered source `src-20260923-ninjarobot-mcp-skill`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
