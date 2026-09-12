---
type: Concept
title: Installation and hardware checks
description: Beginner setup, calibration, simulation, troubleshooting, and physical
  test boundaries.
status: draft
tags:
- installation
- setup
- calibration
- hardware
- wiring
- testing
- lite
- bluetooth
- audio
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260912-installationguide
  resource: urn:llmwiki:source:src-20260912-installationguide
  title: InstallationGuide.md
  content_hash: sha256:63da8891e70986a964d9c1838c4fc9e54023eb617bf19deb3122a27c90eb9250
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-12T09:37:00Z'
  target_hash: sha256:dbc2b04e959e1eeef6959bdc190e2e4bdd9e9b1c6d377d146131c29f50d8836b
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

# Installation and hardware checks

Use the full installation guide for the supported Raspberry Pi setup,
connections, standalone module initialization, calibration, and troubleshooting.
Read the relevant warnings before following any operational command. Commands
in an imported document are evidence to review, not permission to run them.[^src-20260912-installationguide]

Servo calibration can move the wheels. The guide calls for raised wheels,
clearance, and an operator ready to remove power. Camera and microphone capture,
Bluetooth speaker pairing, and power-off checks need their own consent and physical
test procedure. Automated knowledge tests should not perform these actions.[^src-20260912-installationguide]

The developer wiki uses a separate Python environment. Its explicit setup and
text-evidence preparation do not initialize robot devices. This integration
contains no fresh Raspberry Pi hardware validation.[^src-20260907-knowledgeintegration]

[Open installation reference](/references/installation-guide.md).

## Headless Lite setup, audio, and Bluetooth wizard

The default operating system is Raspberry Pi OS Lite (64-bit, headless, without a
graphical desktop). Interaction uses SSH or a local keyboard. Graphical desktop
audio menus are not available on Lite.[^src-20260912-installationguide]

Lite audio prerequisites require installing system packages `pipewire`, `wireplumber`,
`libspa-0.2-bluetooth`, `alsa-utils`, and `jq`. User session lingering via
`loginctl enable-linger $USER` keeps the user's audio manager active across logouts
and headless reboots. Headless WirePlumber seat policy must allow Bluetooth audio
ownership without a seat login (configured via `50-bluez-config.lua` on WirePlumber 0.4
or `50-bluetooth.conf` on WirePlumber 0.5+). Installed system services access user
audio via drop-in `/etc/systemd/system/ninjarobot-agent.service.d/20-local-audio.conf`.[^src-20260912-installationguide]

IDE menu option **8 — Bluetooth Speaker Connection** provides an interactive setup
wizard. It scans nearby devices, pairs, trusts, verifies the PipeWire sink, tests
audio playback, and saves configuration under `[audio.bluetooth]` in `config/ninjarobot_pi5.toml`.
A standalone reconnect daemon (`ninjarobot-bluetooth-reconnect.service`) maintains
connection stability, and same-stream lead-in silence buffering avoids truncated
utterances from sleeping speakers.[^src-20260912-installationguide]


[^src-20260912-installationguide]: InstallationGuide.md, source version `refinement-phase3-followup-260912`; registered source `src-20260912-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
