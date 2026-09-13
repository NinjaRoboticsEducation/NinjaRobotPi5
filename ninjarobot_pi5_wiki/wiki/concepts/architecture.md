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
- speech
- bluetooth
- information
- distance-game
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260913-developmentguide
  resource: urn:llmwiki:source:src-20260913-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:f6ae6ee1dfe85488f3db13c1d6cc927802d92610860605bd42229d6a3a1d53bf
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-13T14:15:00Z'
  target_hash: sha256:7b5c581b0a51dac7f5cbdd95ad3390cefb3a09489330ed02dcb5b7909dc98222
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered Phase 4 information evidence; no human verification
    is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
---

# Architecture and hardware ownership

The documented hardware path is user or model → ninjarobot_pi5_agent →
ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
interaction, model-provider translation, policy, sessions, memory, information services,
and tool proposals. It should not import a pi5 library or access a device directly.[^src-20260913-developmentguide]

The IDE (the project's device-coordination layer) owns shared resource scheduling,
action execution, safety state, behaviors, distance game loops, and hardware ownership.
Individual managed libraries own their device and standalone setup interface. The six
managed libraries cover servo motors, display, buzzer, distance sensing, camera,
and microphone.[^src-20260913-developmentguide]

This is the documented architecture contract. Compare affected code and tests
with it before implementation; this page does not certify that every failure or
physical safety condition has been tested.[^src-20260913-developmentguide]

[Read the development manual](/references/development-guide.md).

## Refinement Phase 5 and hardware boundaries

Refinement Phase 5 introduces `ninjarobot_pi5_ide/distance_game.py`, owning strict
requests, fresh-reading validation, three-band tone feedback, admission, finite
execution, and independent stop/status. The game never reserves `servo_bus`; it reserves
shared display, buzzer, and distance resources, including the I2C bus lock. The distance
adapter shields and retains the underlying worker across cancellation, preventing
close/reopen overlap (`start(recover=True)`). `expression_variants.py` selects a bounded
silent palette once per conversational opportunity. Proposed hardware changes (movable head,
edge sensing, touch input) remain unpurchased, uninstalled evaluation proposals.[^src-20260913-developmentguide]

## Agent information architecture and local tasks

The Agent owns local speech synthesis, reminders, recipe execution, and Phase 4
information management in `ninjarobot_pi5_agent`. `InformationStore` manages user-scoped
SQLite transactions (migration 7). `NotesService` commits notes and consumed approvals
together. `CalendarService` manages exact approvals, Google OAuth desktop browser loopback,
and remote verification via HTTPX. `ResearchService` binds allowlisted Tavily snippet
results to saved runs. `BriefingService` generates deterministic bundles on request.[^src-20260913-developmentguide]

All state-modifying actions (calendar writes, note edits) require a five-minute exact preview
and same-session direct user confirmation. Models and recipes cannot confirm changes or
bypass deterministic policy. Audio playback routes through IDE PipeWire ownership with
lead-in silence buffering (`bluetooth_lead_in_seconds`, default 0.5s) and independent
reconnection daemon support.[^src-20260913-developmentguide]


[^src-20260913-developmentguide]: DevelopmentGuide.md, source version `refinement-phase4-information-260913`; registered source `src-20260913-developmentguide`.
