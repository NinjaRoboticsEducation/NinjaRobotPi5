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
- id: src-20261102-developmentguide
  resource: urn:llmwiki:source:src-20261102-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:d106f1e107b08da8a11f85ef97a4195e2483dcda7753aaa167f762457ee3eeb4
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-11-02T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 2 November runtime remediation and Multi-HAT
    hardware refinement evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:76b1487450a91571f3b4f597a5cbdc3c272136544893a417cf456e7471f40f43
---

# Development guide

The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20261102-developmentguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint: Runtime remediation and Multi-HAT hardware refinement

The 2 November 2026 revision (`2026-11-02`) documents web startup `proxy_headers=False` for loopback proxy pairing inspection; distinct `battery_undervoltage` cutoff with persisted measured voltage and cutoff details; non-finite telemetry safeguards; SunFounder sysfs-informed `0x17` preset avoiding probing and legacy charging GPIO23; completed transient full stop clears local presentation gate; embedded audio uses Fusion kernel speaker node, removing raw I2C `0x31` write; ALSA/PipeWire readiness aligned; Fusion PWM/timer registers advance by two bytes at `0x17`; config import preserves explicit servo roles; Ollama catalog discovery queries local models without credentials and cloud models when an API key is stored, carrying route as provider `base_url`, alongside 25 October 2026 `SunFounderRobotHatBackend` (`0x14`/`0x17` dual MCU with automatic fallback, 3-byte Big-Endian transactions, class-level `RLock`), `PCA9685ServoBackend` with built-in `smbus2` controller, `ServoEndpoint` (0..15), IDE `SUPPORTED_SERVO_ENDPOINTS`, `PowerConfig`, `SpeechOutputConfig.speaker_enable_gpio`, `audio_output.py` I2S sink discovery and GPIO12 amp enable, single-component pin collision fix in `hardware_setup.py`, flexible PWM channels, auxiliary-only servo roles in `safety.py`, and onboarding wizard profile selection, alongside 23 September onboarding wizard refinements, Mac Calendar SSH forwarding, 22 September guided onboarding, 18 September web controller dual views, 17 September calendar setup and unified `CONFIRM` / `CANCEL` flow, 15–16 September distance game and servo repairs, Phase 4 information services, Phase 4 foundations, and system clock access.[^src-20261102-developmentguide]


[^src-20261102-developmentguide]: DevelopmentGuide.md, source version `runtime-remediation-261102`; registered source `src-20261102-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
