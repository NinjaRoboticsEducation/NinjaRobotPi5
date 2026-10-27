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
- id: src-20261027-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20261027-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:6a1b6e3538d38533ad9b9a254877f7d966df732225a0d3d432b168ffc7fdf2df
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-10-27T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 25 October multi-HAT expansion and SunFounder
    hardware audit evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:a7bc2ecf7b3f249c1657cf7cd08bf64bcbdaf2b747459be6f814c334d66872b2
---

# MCP and Agent Skills tutorial

The tutorial explains external tools, configuration, read-only Tavily and Calendar examples, and reusable Agent Skills. It describes restrictions for the robot Agent, not a development wiki server.[^src-20261027-ninjarobot-mcp-skill]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Multi-HAT servo and behavior capabilities

The 25 October 2026 source (`2026-10-25`) documents transparent robot movement and servo tools (`servo.move`, `servo.status`, `servo.stop`,
and behavior `drive` stages) across all three supported Expansion HAT profiles (DFR0566, SunFounder Robot HAT, and PCA9685). Auxiliary servo
roles (`head_pan`, `head_tilt`, `arm`, `gripper`) can be targeted independently in behavior definitions without requiring simultaneous wheel
motion. External MCP server configuration and Agent Skill schemas remain unchanged, alongside 23 September 2026 refined external MCP configuration
via `ninjarobot onboard --step mcp`, including Google Cloud project/API setup instructions, Desktop OAuth client creation, credential placement,
Mac SSH port forwarding (`ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765 YOUR_PI_USER@YOUR_PI_HOST`), periodic waiting
status, callback receipt acknowledgment, and end-to-end validation via an isolated bounded read-only `list_today_events` call through the external
MCP server. Failed attempts clean up candidate credentials and preserve working configuration. Read-only allowlists cover Tavily Search
(`tavily_search`), Google Calendar (`list_today_events` stdio MCP), and Notion (`notion-search`, `notion-fetch` OAuth on loopback 8766), with
tool discovery validation and inspection commands (`ninjarobot mcp list`, `mcp inspect SERVER`, `mcp health SERVER`), alongside 18 September
web interface navigation, 17 September Google Calendar tools (`calendar.list`, `calendar.events.preview_create/update/delete`) with chat `CONFIRM` /
`CANCEL` authorization, public project help tools backed by `project_documents.py`, Tavily research, local notes/briefings, bundled `distance-game`
skill v1, and bundled `project-help` skill v2. External MCP extensions retain no direct device or hardware access.[^src-20261027-ninjarobot-mcp-skill]


[^src-20261027-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-ninjarobot-mcp-skill`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
