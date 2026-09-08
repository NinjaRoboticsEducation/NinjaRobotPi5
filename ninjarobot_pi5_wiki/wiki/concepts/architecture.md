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
- id: src-20260908-developmentguide
  resource: urn:llmwiki:source:src-20260908-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:640cb37251c7d9c7d41a23a4998aa0b25dcbfa8bba952435adeda61f821fd6e6
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-08T15:25:18.461989+00:00'
  target_hash: sha256:0ea2a69d72f6230216447ff5e95ec0a3244215e7db3378114f37a6f781afd2b2
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

# Architecture and hardware ownership

The documented hardware path is user or model → ninjarobot_pi5_agent →
ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
interaction, model-provider translation, policy, sessions, and tool proposals.
It should not import a pi5 library or access a device directly.[^src-20260908-developmentguide]

The IDE (the project's device-coordination layer) owns shared resource scheduling,
action execution, safety state, behaviors, and hardware ownership. Individual
managed libraries own their device and standalone setup interface. The six
managed libraries cover servo motors, display, buzzer, distance sensing, camera,
and microphone.[^src-20260908-developmentguide]

This is the documented architecture contract. Compare affected code and tests
with it before implementation; this page does not certify that every failure or
physical safety condition has been tested.[^src-20260908-developmentguide]

[Read the development manual](/references/development-guide.md).


## Local task and safety integration

The Agent owns reminder scheduling and scoped request records in its existing
private database. Deterministic controls confirm exact notification effects;
physical delivery uses the existing IDE expression capability. Models cannot
confirm reminders or open drivers. Interrupted work is uncertain rather than
silently replayed.[^src-20260908-developmentguide]

Trusted stop dispatch is independent of the ordinary queue. Retained real-device
builders share IDE ownership, disabled devices skip initialization/recovery, and
integrated raw movement uses the existing safety controller and bounded cleanup.
A blocked native driver call cannot be forcibly ended by Python cancellation;
physical stopping time remains a manual validation question.[^src-20260908-developmentguide]


[^src-20260908-developmentguide]: DevelopmentGuide.md, source version `refinement-phase2-260909`; registered source `src-20260908-developmentguide`.
