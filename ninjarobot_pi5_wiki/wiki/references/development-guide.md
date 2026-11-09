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
- id: src-20261109-developmentguide
  resource: urn:llmwiki:source:src-20261109-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:075a560ad59fcc46cbed6118928c0d1a342f86eda4464221beafde76138ca221
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-11-09T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 9 November browser reconnection, controller
    handoff, and connected welcome/idle refinement evidence (development guide); no
    human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:05b202de605256c6eb35af924cd14a0e7e359766d8a431ad1fede83b21ba3aa7
---

# Development guide

The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20261109-developmentguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Browser reconnection, controller handoff, and welcome/idle refinement

The 9 November 2026 revision (`2026-11-09-02`) documents browser disconnect, reconnect, and controller handoff architecture along with connected welcome and idle refinement: serialized lease cleanup, attachment generations, immediate revocation, automatic non-revoking pairing QR redisplay, durable waiting display reservation, endpoint invalidation, and browser departure/Back-Forward recovery across `onboarding.py`, `remote_access.py`, `runtime.py`, `service_main.py`, `web_app.py`, `web_control.py`, `app-shared.js`, `app-agent.js`, `display.py`, `integrated.py`, and `behavior_runtime.py`. On connection loss, active commands, movement, speech, and capture are cancelled; browser-enabled robot voice listening stops without changing saved preferences; and saved conversations, reminders, and future tasks are retained without replaying interrupted actions. Clean disconnect reserves the lease for up to 10 seconds or until heartbeat deadline, allowing same-browser reconnect with existing token and chat identity while locking others. Unannounced loss is detected via 15-second heartbeat deadline and watchdog polling (<= 1s) with a 5-second cancellation budget. Each newly acquired exclusive browser controller lease runs Greeting through the IDE and transitions to repeating silent Idle; reconnecting the same lease during grace restores Idle without replaying Greeting; lease delivery and heartbeats continue during the cancellable welcome task while normal interactions wait for completion; and delayed ngrok ready events check endpoint generation before revoking live controllers. Consolidates 4 November safety latch timestamp diagnostics and Level 1 motion-only resume (`safety.py`, `servo.py`, `robot.py`, `runtime.py`, `service_main.py`, `prompts.py`), live `speech_output` state, automated Piper TTS provisioning, standalone power-off helper installation, and web microphone lifecycle retention until `onend`, alongside 3 November Fusion HAT+ sysfs PWM ownership (`1.1.0-ninja1`, fixed 50 Hz, class-level lock), in-memory calibration draft staging, and earlier checkpoints.[^src-20261109-developmentguide]


[^src-20261109-developmentguide]: DevelopmentGuide.md; registered source `src-20261109-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
