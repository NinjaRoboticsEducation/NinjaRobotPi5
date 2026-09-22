---
type: Reference
title: Development log
description: Find the complete versioned development log.
status: draft
tags:
- ninjarobotpi5
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260922-developmentlog
  resource: urn:llmwiki:source:src-20260922-developmentlog
  title: DevelopmentLog.md
  content_hash: sha256:74a18d92c47c614d3bfeef9e4c8e99bb8f4e1e0f135c58efc103760a785a76b6
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
  target_hash: sha256:b074a47777f6ba795087defb678499a4c81282804eed001faaf1f2f9b66fb987
---

# Development log

The complete log preserves dated implementation decisions and validation reports. Historical test results describe their recorded checkout and date; they are not fresh verification.[^src-20260922-developmentlog]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Guided onboarding, curl bootstrap, and editable chat

The 22 September 2026 entries record the unified `ninjarobot` entry point and resumable onboarding
orchestrator, prompt-toolkit multiline chat REPL with arrow key editing, root installer curl streaming
bootstrap with exact commit ID checks, idempotent `~/.local/bin/ninjarobot` user launcher, 5 mandatory
hardware checks through IDE locks, model provider setup, 3 read-only external MCP presets (Tavily, Calendar, Notion),
and successful passage of 1,021 repository tests and 457 managed-driver tests without live hardware motion,
alongside 18 September web controller dual views, 17 September Google Calendar guided OAuth setup with primary-calendar
discovery, port 8765 loopback SSH tunnel, field validation error handling, unified `CONFIRM` / `CANCEL`
chat authorization across create, update, and delete, runtime project help hash checking, 16 September distance game hand-placement timing, 15 September repairs, Phase 4 information assistant completion, narrowed Phase 4 foundations, Phase 5 evaluation, and system clock access.[^src-20260922-developmentlog]


[^src-20260922-developmentlog]: DevelopmentLog.md, source version `onboarding-install-chat-260922`; registered source `src-20260922-developmentlog`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
