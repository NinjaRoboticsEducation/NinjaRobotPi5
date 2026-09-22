---
type: Reference
title: Development guide
description: Find the complete versioned development guide.
status: draft
tags:
- ninjarobotpi5
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260922-developmentguide
  resource: urn:llmwiki:source:src-20260922-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:d3e8a50fe808614a7affbaa221fd457f8e981931d43bc5c17a8bc89be89d1a31
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
  target_hash: sha256:00a00a15cde7f85cecd865e188422ba86cd483a779988c3765453e59a767f227
---

# Development guide

The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20260922-developmentguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Guided onboarding, curl bootstrap, and editable chat

The 22 September 2026 revision (`2026-09-22`) documents the `ninjarobot` CLI entry point,
the `setup_wizard.py` orchestration layer, the IDE hardware setup adapter (`ninjarobot_pi5_ide.hardware_setup`)
with hardware locking, owner-only progress storage (`~/.local/state/ninjarobot_pi5/setup-progress.json`),
read-only external MCP presets (Tavily Search, Google Calendar stdio MCP, Notion SDK OAuth on port 8766),
`terminal_input.py` prompt-toolkit interactive chat, and standalone curl streaming bootstrap in `install.sh`,
alongside 18 September web controller dual-view architecture, 17 September calendar setup and unified `CONFIRM` / `CANCEL`
flow, 15–16 September distance game and servo repairs, Phase 4 information services (T04 calendar,
T05 research, T06 notes/checklists/briefings, migration 7), Phase 4 foundations, and system clock access.[^src-20260922-developmentguide]


[^src-20260922-developmentguide]: DevelopmentGuide.md, source version `onboarding-install-chat-260922`; registered source `src-20260922-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
