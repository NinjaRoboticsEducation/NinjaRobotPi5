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
- distance-game
- information
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260913-installationguide
  resource: urn:llmwiki:source:src-20260913-installationguide
  title: InstallationGuide.md
  content_hash: sha256:de52e1ccb7fea5a45497a0babce1648676824783508eb6c37471aa9e662dba27
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-13T14:15:00Z'
  target_hash: sha256:56c7cbb8ee4b2bd78c28e5ae4d1f3c5a965dc530be2a25206b0111f3d78204ba
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

# Installation and hardware checks

Use the full installation guide for the supported Raspberry Pi setup,
connections, standalone module initialization, calibration, and troubleshooting.
Read the relevant warnings before following any operational command. Commands
in an imported document are evidence to review, not permission to run them.[^src-20260913-installationguide]

Servo calibration can move the wheels. The guide calls for raised wheels,
clearance, and an operator ready to remove power. Camera and microphone capture,
Bluetooth speaker pairing, distance game physical play, and power-off checks need
their own consent and physical test procedure. Automated knowledge tests should not
perform these actions.[^src-20260913-installationguide]

The developer wiki uses a separate Python environment. Its explicit setup and
text-evidence preparation do not initialize robot devices. This integration
contains no fresh Raspberry Pi hardware validation.[^src-20260907-knowledgeintegration]

[Open installation reference](/references/installation-guide.md).

## Headless Lite setup, audio, and Bluetooth wizard

The default operating system is Raspberry Pi OS Lite (64-bit, headless, without a
graphical desktop). Interaction uses SSH or a local keyboard. Graphical desktop
audio menus are not available on Lite.[^src-20260913-installationguide]

Lite audio prerequisites require installing system packages `pipewire`, `wireplumber`,
`libspa-0.2-bluetooth`, `alsa-utils`, and `jq`. User session lingering via
`loginctl enable-linger $USER` keeps the user's audio manager active across logouts
and headless reboots. Headless WirePlumber seat policy must allow Bluetooth audio
ownership without a seat login. Installed system services access user audio via drop-in
`/etc/systemd/system/ninjarobot-agent.service.d/20-local-audio.conf`. IDE menu option
**8 — Bluetooth Speaker Connection** provides an interactive pairing and test wizard.[^src-20260913-installationguide]

## Distance game and information assistant setup

The optional distance game is configured by adding `[distance_game]` with `enabled = true`
and `volume = 16` to `config/ninjarobot_pi5.toml` while the service is stopped. During
first physical acceptance, wheels must remain raised and clear of desk edges. The game
never commands wheel movement.[^src-20260913-installationguide]

Information-assistant features require database migration 7, which applies automatically
to the private database. Google Calendar authorization uses a local loopback web server
via an SSH tunnel (`ssh -L 8080:localhost:8080 ...`) to complete the OAuth consent flow
in a desktop browser without exposing the robot. Notes, checklists, and local briefings
operate entirely locally without external API requirements.[^src-20260913-installationguide]


[^src-20260913-installationguide]: InstallationGuide.md, source version `refinement-phase4-information-260913`; registered source `src-20260913-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
