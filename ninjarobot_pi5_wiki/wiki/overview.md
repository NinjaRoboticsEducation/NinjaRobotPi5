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
- id: src-20260912-developmentguide
  resource: urn:llmwiki:source:src-20260912-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:9843060f7eb54f90846eb51f4dac8ab23e1a3d5dae78211a1d2dae4cd198d376
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-12T09:37:00Z'
  target_hash: sha256:fddef3685444dbdbb5c1d1d7012dd8fc65388c1271cf0c64907b255da9a0e0fa
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

# NinjaRobotPi5 project overview

NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
for coordinating devices, and managed Pi5 libraries for individual devices.
The development guide describes their permitted ownership boundary.[^src-20260912-developmentguide]

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

## Phase 3 follow-up checkpoint

Spoken replies, coordinated output, and Bluetooth speaker integration are implemented
and software-tested. The existing Agent/IDE/driver boundary remains intact: IDE-owned
OS audio is an optional output, not a new Agent hardware path. English speech uses
optional local Piper synthesis, Mandarin accepts an operator-supplied model, and
Japanese is not implemented. IDE owns PipeWire playback, RobotAssembly speaking
face coordination, independent speech stop controls, and Bluetooth speaker connections.
Raspberry Pi OS Lite headless setup uses session lingering (`loginctl enable-linger`),
WirePlumber headless seat configuration, and an optional systemd audio drop-in.
The Phase 3 follow-up adds IDE menu 8 (Bluetooth Speaker Connection wizard), saved
TOML configuration (`[audio.bluetooth]`), a standalone reconnect helper daemon,
bounded same-stream lead-in silence buffering (`bluetooth_lead_in_ms`), the bundled
`robot-command-help` skill, CLI `/help` and `/guide` commands, and interrupted-turn
context repair. Display font repair and monetary spending cap remain pending. Read
[local tasks and memory](concepts/features-and-tools.md) before treating a saved
request as delivered.[^src-20260912-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20260912-developmentguide]: DevelopmentGuide.md, source version `refinement-phase3-followup-260912`; registered source `src-20260912-developmentguide`.
