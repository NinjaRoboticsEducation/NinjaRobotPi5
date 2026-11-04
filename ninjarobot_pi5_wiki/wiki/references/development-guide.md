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
- id: src-20261104-developmentguide
  resource: urn:llmwiki:source:src-20261104-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:6d4574560831e69657ce128f16f972a885ba6fbf98c463a433a38a2459b41f4b
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-11-04T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 4 November SunFounder Fusion HAT+ agent
    integration remediation, web microphone lifecycle repair, and documentation reconciliation
    evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:76a5c6fb70a7bcaef0abb818a5ec897a1286500bf216fd830afac3e820db43b5
---

# Development guide

The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20261104-developmentguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Fusion agent integration remediation and documentation reconciliation

The 4 November 2026 revision (`2026-11-04-03`) documents safety latch timestamp diagnostics and Level 1 motion-only resume (`safety.py`, `servo.py`, `robot.py`, `runtime.py`, `service_main.py`, `prompts.py`); live `speech_output` state in LLM turns and Piper TTS provisioning; memory turn filtering in `agent_loop.py`; standalone power-off helper installation and LAN session authorization (`deployment.py`, `agent_cli.py`, `web_app.py`); and web microphone lifecycle retention until `onend` with 48 kHz I2S voice input resilience (`app-agent.js`, `microphone.py`, `voice_input.py`, `audio_process.py`); alongside `FusionHatPlusBackend` sysfs PWM ownership (`1.1.0-ninja1`, fixed 50 Hz across 3 shared timer groups, class-level lock); `fusion.py` sysfs interface validation and telemetry parsing; `calib.py` in-memory draft staging (stage Min/Max/Center in any order with Enter/Space, atomic commit with F requiring `500 <= Min < Center < Max <= 2500` microseconds, discard with Q, clean exit without centering); `hardware_setup.py` non-moving prerequisite readiness; `scripts/fusion_hat_setup.py` prepare/preview/install tool; alongside 2 November runtime remediation (`proxy_headers=False`, distinct `battery_undervoltage` cutoff with persisted measured voltage and cutoff details, non-finite telemetry safeguards, completed transient full stop presentation clearance, embedded audio Fusion kernel speaker node, ALSA/PipeWire readiness aligned, config import explicit servo role preservation, and route-persisting local/cloud Ollama selection), 25 October Multi-HAT expansion backends, 23 September onboarding wizard refinements, Mac Calendar SSH forwarding, 22 September guided onboarding, 18 September web controller dual views, 17 September calendar setup and unified CONFIRM authorization, 15–16 September distance game and servo repairs, Phase 4 information services, Phase 4 foundations, and system clock access.[^src-20261104-developmentguide]


[^src-20261104-developmentguide]: DevelopmentGuide.md, source version `fusion-agent-remediation-261104`; registered source `src-20261104-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
