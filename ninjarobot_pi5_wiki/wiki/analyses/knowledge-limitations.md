---
type: Analysis
title: Knowledge limitations and verification
description: Search gaps, stale evidence, source versions, editor access, and review
  boundaries.
status: draft
tags:
- limitations
- stale
- verification
- search
- known
- issues
- phase4
- phase5
- calendar
- ui-refinement
- onboarding
- expansion-hat
- sunfounder
- pca9685
- reconnection
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
- id: src-20261109-developmentguide
  resource: urn:llmwiki:source:src-20261109-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:075a560ad59fcc46cbed6118928c0d1a342f86eda4464221beafde76138ca221
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
    handoff, and connected welcome/idle refinement evidence (limitations and verification);
    no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:11f386c87f46c233925edc01a2406b66d1d0541ad0472d301f61bf579d617c3e
---

# Knowledge limitations and verification

Keyword search covers curated pages rather than all raw manual text. It does not
follow citations for the caller. Try focused terms, read the overview, and open
full sources. Search expiry flags, source fingerprints, and semantic review
status are separate signals and must be checked together.[^src-20260907-knowledgeintegration]

A missing result is an evidence gap, not proof a feature is absent. A page can be
structually valid while its explanation needs review. Current implementation
fingerprints identify files needing knowledge review but cannot prove that prose
is correct. AI-reviewed pages are not human-verified or hardware-tested pages.
Editor adapters need actual session activation checks; a wiki-only workspace may
not expose parent robot code.[^src-20260907-knowledgeintegration]

The development guide's older quality-gate example uses narrower lint paths than
the current root policy. Follow the root operating policy for the current full
checks, and preserve the source's historical context rather than silently treating
an older example as the complete current gate.[^src-20261109-developmentguide][^src-20260907-knowledgeintegration]

[Project overview](/overview.md).

## Limits of recent checkpoints (Browser Reconnection, Connected Welcome/Idle, Fusion Agent Remediation, Documentation Reconciliation, Fusion HAT+ Integration, Runtime Remediation, Multi-HAT Expansion, Onboarding Refinement, Phase 4, Phase 5, Calendar, and UI refinement)

The current manual checkpoint (`2026-11-09-02`) consolidates browser reconnection, controller handoff, and connected welcome/idle refinement alongside 4 November SunFounder Fusion HAT+ agent integration remediation, web microphone lifecycle repair, and documentation reconciliation, 3 November Fusion HAT+ kernel driver integration and in-memory calibration draft staging, 2 November runtime remediation, 25 October multi-HAT expansion support, system time access, Phase 4 information work, 15–16 September distance game/servo repairs, 17 September Google Calendar setup and unified CONFIRM flow, 18 September UI refinement, 22 September guided onboarding, curl bootstrap, and editable chat, and 23 September onboarding refinements and installer repairs. Software validation is not physical acceptance:[^src-20261109-developmentguide]
- **Browser reconnection, controller handoff & connected welcome/idle (9 November 2026)**: Serialized lease cleanup, attachment generations, immediate revocation, automatic pairing QR redisplay, durable waiting display reservation, endpoint invalidation, browser departure/Back-Forward recovery, and per-controller welcome/idle refinement passed 1,157 main repository tests and managed driver suites. Automated tests validate software contracts, connection state machines, watchdog timeouts, and subprocess mocking; physical browser behavior on mobile devices over real Wi-Fi networks (such as iOS Safari background suspension vs websocket close events), phone camera QR scan readability across lighting conditions, electrical stop latency on real motors, and physical emergency disconnect remain pending manual operator acceptance.[^src-20261109-developmentguide]
- **Fusion agent remediation & web microphone lifecycle (4 November 2026)**: Safety latch diagnostics, Level 1 `/resume` dispatch, Piper TTS provisioning, standalone power-off helper, browser microphone lifecycle, and 48 kHz voice input passed 1,141 main repository tests and managed driver suites. Automated tests validate software contracts, subprocess mocking, and lifecycle states; physical browser microphone audibility across diverse browser engines, physical speaker synthesis clarity, actual OS power-off execution, and hardware emergency-stop recovery under live battery loads remain pending manual operator acceptance.[^src-20261109-developmentguide]
- **Fusion HAT+ kernel integration & calibration drafts (3 November 2026)**: Sysfs PWM interfaces under `1.1.0-ninja1`, non-moving prerequisite checking, `fusion_hat_setup.py` preview tool, in-memory calibration draft state transitions, and battery microvolt telemetry division passed 1,132 repository unit tests and 159 `pi5servo` unit tests. Automated testing validates simulated sysfs nodes, mock drivers, and command construction; physical installation of kernel overlays, actual electrical PWM pulses on real servos, battery load discharge behavior, and physical OS shutdown were not executed during automated tests. Operator precautions (raised wheels, power disconnect readiness) remain essential during manual calibration and hardware deployment.[^src-20261109-developmentguide]
- **Runtime remediation & hardware acceptance (2 November 2026)**: Web startup `proxy_headers=False`, distinct `battery_undervoltage` cutoff, sysfs-informed `0x17` preset, completed transient stop presentation gate clearance, Fusion kernel speaker node audio control, 2-byte register stride at `0x17`, explicit servo role preservation, and route-persisting local/cloud Ollama selection passed 1,104 repository unit tests and 464 driver unit tests. Live tunnel verification, physical audio playback, actuator movement, camera/microphone capture, model downloading, and power-off checks were not run during automated testing. Fusion kernel ownership must be checked on the Raspberry Pi before direct-I2C motion tests to avoid competing userspace and kernel MCU owners. Measured battery conversion and cutoff suitability require live physical measurements.[^src-20261109-developmentguide]
- **Multi-HAT expansion & hardware support**: Dual `0x14`/`0x17` MCU auto-fallback, PCA9685 endpoint mapping, embedded I2S speaker amplifier control, and battery fuel gauge monitoring passed 1,087 synthetic software tests and 139 driver unit tests. Physical validation on a physical SunFounder Robot HAT or PCA9685 HAT requires raised wheels, power precautions, and live acoustic speaker checks.[^src-20261109-developmentguide]
- **Guided onboarding & bulk reuse**: Automatic configuration checks verify saved setting files, but do not certify live physical device operation or motor movement; raised wheels remain mandatory for servo testing; camera/mic privacy consent choices remain manual operator decisions. Google Calendar Mac SSH tunnel (`-L 127.0.0.1:8765:127.0.0.1:8765`) and live account authorization require user browser interaction. Simulated verification records never satisfy real-hardware readiness. External Calendar MCP tests are read-only and separate from the native Calendar feature. Microphone configuration probe subprocess does not record, transcribe, or run inference.[^src-20261109-developmentguide]
- **Web interface refinement & IDE menu**: UI components, websocket event messaging, user-behavior execution modals, and terminal menu consolidation have passed 125 automated unit tests and mock validations; physical acceptance on mobile devices over real Wi-Fi networks and touch-screen D-pad latency require live operator verification.[^src-20261109-developmentguide]
- **Clock**: `system.time.get` reads local OS clock; it does not set the clock or verify NTP synchronization.[^src-20261109-developmentguide]
- **Distance game hand placement**: Tested against unit and mock suites; hand placement timing (5–60 cm immediately at request time, before final chat response) and buzzer audibility require live physical verification. Hardware proposals (movable head, edge sensors, touch) are uninstalled concepts.[^src-20261109-developmentguide]
- **Phase 4 calendar and research**: Google Calendar requires user SSH loopback OAuth (port 8765); read-only default; write operations require `--write` and plain single-word `CONFIRM`. Preparing a create preview does not perform Google write operations; software mock gates do not guarantee Google API acceptance or handle account-level quota issues. Tavily search snippet citations provide evidence links but do not certify external factual truth.[^src-20261109-developmentguide]
- **Project help**: Runtime document section hashes ensure published section integrity, but cannot guarantee factual perfection of upstream documentation.[^src-20261109-developmentguide]
- **Model boundaries**: Rolling transcript suffix truncation preserves safety context and fits provider request character caps, but does not enforce a currency-denominated spending cap. Display font repair and physical acceptance remain open.[^src-20261109-developmentguide]


[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
[^src-20261109-developmentguide]: DevelopmentGuide.md; registered source `src-20261109-developmentguide`.
