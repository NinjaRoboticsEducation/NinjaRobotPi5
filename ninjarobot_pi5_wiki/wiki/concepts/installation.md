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
- calendar
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260917-installationguide
  resource: urn:llmwiki:source:src-20260917-installationguide
  title: InstallationGuide.md
  content_hash: sha256:7e50d29d87acf54bcc5dce24f26b8c667acf2b026edfec45e2cc8c286e190029
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-17T15:40:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 17 September calendar CONFIRM flow, guided
    authorization, and project help evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
  target_hash: sha256:e65632cb40a72b81ceb992be9feac0b483a1879b242fcfcb3ae5f356a11f4f1e
---

# Installation and hardware checks

Use the full installation guide for the supported Raspberry Pi setup,
connections, standalone module initialization, calibration, and troubleshooting.
Read the relevant warnings before following any operational command. Commands
in an imported document are evidence to review, not permission to run them.[^src-20260917-installationguide]

Servo calibration can move the wheels. The guide calls for raised wheels,
clearance, and an operator ready to remove power. Camera and microphone capture,
Bluetooth speaker pairing, distance game physical play, and power-off checks need
their own consent and physical test procedure. Automated knowledge tests should not
perform these actions.[^src-20260917-installationguide]

The developer wiki uses a separate Python environment. Its explicit setup and
text-evidence preparation do not initialize robot devices. This integration
contains no fresh Raspberry Pi hardware validation.[^src-20260907-knowledgeintegration]

[Open installation reference](/references/installation-guide.md).

## Headless Lite setup, audio, and Bluetooth wizard

The default operating system is Raspberry Pi OS Lite (64-bit, headless, without a
graphical desktop). Interaction uses SSH or a local keyboard. Graphical desktop
audio menus are not available on Lite.[^src-20260917-installationguide]

Lite audio prerequisites require installing system packages `pipewire`, `wireplumber`,
`libspa-0.2-bluetooth`, `alsa-utils`, and `jq`. User session lingering via
`loginctl enable-linger $USER` keeps the user's audio manager active across logouts
and headless reboots. Headless WirePlumber seat policy must allow Bluetooth audio
ownership without a seat login. Installed system services access user audio via drop-in
`/etc/systemd/system/ninjarobot-agent.service.d/20-local-audio.conf`. IDE menu option
**8 — Bluetooth Speaker Connection** provides an interactive pairing and test wizard.[^src-20260917-installationguide]

## Distance game and information assistant setup

The supported distance game is default-enabled in configuration (`volume = 16` under
`[distance_game]` in `config/ninjarobot_pi5.toml`). The former `enabled` flag remains
accepted for backwards compatibility but has no gating effect. When playing the game,
place your hand 5–60 cm in front of the sensor upon requesting to play without waiting
for the final chat response. During first physical acceptance, wheels must remain raised
and clear of desk edges. The game never commands wheel movement.[^src-20260917-installationguide]

Information-assistant features require database migration 7, which applies automatically
to the private database. Google Calendar authorization uses a local loopback web server
via an SSH tunnel (`ssh -L 8765:127.0.0.1:8765 <user>@<robot-ip>`) to complete OAuth consent
in a desktop browser without exposing the robot. The setup CLI command (`calendar-setup`)
automatically discovers the primary calendar, registers the connection in private user storage,
and reuses existing connection IDs on reauthorization. Default credentials live under
`~/.config/ninjarobot_pi5/google-calendar/credentials.json`. Write operations require the
`--write` flag during setup. Notes, checklists, and local briefings operate entirely locally
without external API requirements.[^src-20260917-installationguide]


[^src-20260917-installationguide]: InstallationGuide.md, source version `calendar-confirm-260917`; registered source `src-20260917-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
