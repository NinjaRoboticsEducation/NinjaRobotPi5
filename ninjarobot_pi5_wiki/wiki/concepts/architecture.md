---
type: Concept
title: Architecture and hardware ownership
description: Agent, IDE, device drivers, safety policy, resource ownership, and code
  boundaries.
status: draft
tags:
- architecture
- hardware
- ownership
- agent
- ide
- drivers
- safety
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260906-developmentguide
  resource: urn:llmwiki:source:src-20260906-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-06T22:54:05Z'
  target_hash: sha256:602559c20e4b41b0189ca08bf989fbfb1d0f80c004719516aed6b420d3b027f3
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

# Architecture and hardware ownership

The documented hardware path is user or model → ninjarobot_pi5_agent →
ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
interaction, model-provider translation, policy, sessions, and tool proposals.
It should not import a pi5 library or access a device directly.[^src-20260906-developmentguide]

The IDE (the project's device-coordination layer) owns shared resource scheduling,
action execution, safety state, behaviors, and hardware ownership. Individual
managed libraries own their device and standalone setup interface. The six
managed libraries cover servo motors, display, buzzer, distance sensing, camera,
and microphone.[^src-20260906-developmentguide]

This is the documented architecture contract. Compare affected code and tests
with it before implementation; this page does not certify that every failure or
physical safety condition has been tested.[^src-20260906-developmentguide]

[Read the development manual](/references/development-guide.md).


[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.
