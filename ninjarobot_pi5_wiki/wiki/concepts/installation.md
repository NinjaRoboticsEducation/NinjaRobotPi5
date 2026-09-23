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
- web-controller
- onboarding
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260923-installationguide-2
  resource: urn:llmwiki:source:src-20260923-installationguide-2
  title: InstallationGuide.md
  content_hash: sha256:d08eb44241ce1a46f5e9e0e9df149cd293fb817c0bd4fe0a4c43dde47ee5d6ca
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-23T00:30:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 23 September onboarding refinement, bulk
    settings reuse, Mac Calendar OAuth SSH tunnel, and installer repair evidence; no human
    verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:bafcdd98c04dc27817a940baf789ab30fd2fc9e1f5f688a94acf398536d166b4
---

# Installation and hardware checks

Use the full installation guide for the supported Raspberry Pi setup,
connections, standalone module initialization, calibration, and troubleshooting.
Read the relevant warnings before following any operational command. Commands
in an imported document are evidence to review, not permission to run them.[^src-20260923-installationguide-2]

Servo calibration can move the wheels. The guide calls for raised wheels,
clearance, and an operator ready to remove power. Camera and microphone capture,
Bluetooth speaker pairing, distance game physical play, and power-off checks need
their own consent and physical test procedure. Automated knowledge tests should not
perform these actions.[^src-20260923-installationguide-2]

The developer wiki uses a separate Python environment. Its explicit setup and
text-evidence preparation do not initialize robot devices. This integration
contains no fresh Raspberry Pi hardware validation.[^src-20260907-knowledgeintegration]

[Open installation reference](/references/installation-guide.md).

## Guided installation, curl bootstrap, and onboarding wizard

New Raspberry Pi installations can use the root installer bootstrap directly via curl:

```bash
curl -fsSL https://raw.githubusercontent.com/NinjaRoboticsEducation/NinjaRobotPi5/public_v07/install.sh | bash -s -- --ref public_v07
```

To install inside a custom destination folder instead of the default `~/NinjaRobotPi5`, pass `--install-dir "$PWD/NinjaRobotPi5"`. The destination must be an absolute path that does not already exist, and its parent directory must exist. Add `--dry-run` to preview actions safely. When changing releases, use the same published revision in both the raw URL and `--ref`; if a branch and tag share a name, disambiguate with `refs/heads/NAME` or `refs/tags/NAME`. The confirmation prompt reads `/dev/tty` so piped curl does not consume answers. The manual clone workflow (`git clone ... && cd NinjaRobotPi5 && ./install.sh`) remains supported. Installation adds the `~/.local/bin/ninjarobot` command.[^src-20260923-installationguide-2]

Run `ninjarobot onboard` to launch the step-by-step setup wizard:
- **Welcome and navigation**: Displays an ASCII NINJAROBOT banner with numbered menu options (1) Open setup tool, Q) Save and exit).
- **Bulk settings reuse**: When standalone settings exist, menu option 2 ("Apply existing settings for all modules") validates all saved hardware configurations in one action, reusing valid modules and only launching tools for missing or invalid required components.
- **Summary and confirmation**: After tool completion, saved settings are displayed with an Enter-to-continue summary. Redundant typed YES, APPLY, and media consent prompts are removed; standalone tools still require operator consent before media capture tests, and servo calibration strictly requires raised wheels.
- **Mandatory components**: Checks `pi5buzzer`, `pi5disp`, `pi5vl53l0x`, `pi5servo`, and `pi5camera`.
- **Optional components**: Audio configuration for Bluetooth speaker, `pi5mic` with whisper.cpp and bundled `hey_Ninja.onnx` wake model.
- **Model providers**: Guides setup for Ollama, Google Gemini, OpenAI, or Anthropic.
- **External MCP tools**: Guides setup of Tavily Search, Google Calendar, and Notion.
- **Remote access**: Configures ngrok tunnel or same-Wi-Fi HTTPS access.[^src-20260923-installationguide-2]

## Web controller access and interface views

The web controller provides phone-friendly HTTPS access on port 8443:
- Navigate to `https://ninjarobotpi5.local:8443/` or `/agent` for the Agent Interface (chat, speech/audio toggles, robot control shortcuts).
- Navigate to `/gamepad` for the Game Pad view (touch D-pad, action triggers, user behavior execution).
- Use the hamburger menu to switch between views and select language (English, Japanese, Traditional Chinese, Simplified Chinese). User preferences are persisted in browser storage.[^src-20260923-installationguide-2]

## Headless Lite setup, audio, and Bluetooth wizard

The default operating system is Raspberry Pi OS Lite (64-bit, headless, without a
graphical desktop). Interaction uses SSH or a local keyboard. Graphical desktop
audio menus are not available on Lite.[^src-20260923-installationguide-2]

Lite audio prerequisites require installing system packages `pipewire`, `wireplumber`,
`libspa-0.2-bluetooth`, `alsa-utils`, and `jq`. User session lingering via
`loginctl enable-linger $USER` keeps the user's audio manager active across logouts
and headless reboots. Headless WirePlumber seat policy must allow Bluetooth audio
ownership without a seat login. Installed system services access user audio via drop-in
`/etc/systemd/system/ninjarobot-agent.service.d/20-local-audio.conf`. IDE menu option
**5 — Bluetooth Speaker Connection** provides an interactive pairing and test wizard.[^src-20260923-installationguide-2]

## Distance game and information assistant setup

The supported distance game is default-enabled in configuration (`volume = 16` under
`[distance_game]` in `config/ninjarobot_pi5.toml`). The former `enabled` flag remains
accepted for backwards compatibility but has no gating effect. When playing the game,
place your hand 5–60 cm in front of the sensor upon requesting to play without waiting
for the final chat response. During first physical acceptance, wheels must remain raised
and clear of desk edges. The game never commands wheel movement.[^src-20260923-installationguide-2]

Information-assistant features require database migration 7, which applies automatically
to the private database. Google Calendar authorization uses a local loopback web server
via an SSH tunnel (`ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765 <user>@<robot-ip>`)
when running the browser on a Mac, delivering approval to the Pi without exposing the robot.
Onboarding displays periodic waiting updates, acknowledges callback receipt, and validates a bounded
read-only events request. Failed authorization attempts clean up candidate credential files. The setup
CLI command (`calendar-setup`) automatically discovers the primary calendar, registers the connection
in private user storage, and reuses existing connection IDs on reauthorization. Default credentials live under
`~/.config/ninjarobot_pi5/google-calendar/credentials.json`. Write operations require the
`--write` flag during setup. Notes, checklists, and local briefings operate entirely locally
without external account setup.[^src-20260923-installationguide-2]


[^src-20260923-installationguide-2]: InstallationGuide.md, source version `onboarding-refinement-260923`; registered source `src-20260923-installationguide-2`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
