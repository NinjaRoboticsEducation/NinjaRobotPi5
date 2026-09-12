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
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260912-developmentguide
  resource: urn:llmwiki:source:src-20260912-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:9843060f7eb54f90846eb51f4dac8ab23e1a3d5dae78211a1d2dae4cd198d376
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-12T09:37:00Z'
  target_hash: sha256:829bbb86987a8f3e95fd0cc3adfd476e65879321ccdf30a9c90771cbebae2d3c
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

# Architecture and hardware ownership

The documented hardware path is user or model → ninjarobot_pi5_agent →
ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
interaction, model-provider translation, policy, sessions, and tool proposals.
It should not import a pi5 library or access a device directly.[^src-20260912-developmentguide]

The IDE (the project's device-coordination layer) owns shared resource scheduling,
action execution, safety state, behaviors, and hardware ownership. Individual
managed libraries own their device and standalone setup interface. The six
managed libraries cover servo motors, display, buzzer, distance sensing, camera,
and microphone.[^src-20260912-developmentguide]

This is the documented architecture contract. Compare affected code and tests
with it before implementation; this page does not certify that every failure or
physical safety condition has been tested.[^src-20260912-developmentguide]

[Read the development manual](/references/development-guide.md).

## Local task, audio, and safety integration

The Agent owns reminder scheduling, request records, and bounded local speech
synthesis in `ninjarobot_pi5_agent/speech.py` (maximum four active or queued jobs).
`ninjarobot_pi5_ide/audio_output.py` and `ninjarobot_pi5_ide/bluetooth_speaker.py`
own device audio playback via PipeWire and Bluetooth speaker lifecycle. Models
cannot confirm reminders, open drivers, or access audio hardware directly.[^src-20260912-developmentguide]

An independent reconnect daemon (`ninjarobot-bluetooth-reconnect.service` /
`scripts/ninjarobot_bluetooth_reconnect.py`) monitors connection health and
reconnects without restarting the Agent. Audio playback prepends bounded
lead-in silence (`bluetooth_lead_in_ms`, default 350ms) to prevent Bluetooth
speaker power-on latency from clipping initial speech syllables. Retained real-device
builders share IDE ownership, disabled devices skip initialization/recovery, and
integrated raw movement uses the existing safety controller and bounded cleanup.
Trusted stop and speech cancel dispatch promptly interrupt audio and repair
turn context without silent replay.[^src-20260912-developmentguide]


[^src-20260912-developmentguide]: DevelopmentGuide.md, source version `refinement-phase3-followup-260912`; registered source `src-20260912-developmentguide`.
