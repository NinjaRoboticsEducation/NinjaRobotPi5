# Phase 8 Public-Release Contract

Status: approved for implementation on `public_v01`  
Target release: `v1.0.0`  
Decision date: 2026-08-13

## Supported platform

The first public release targets Raspberry Pi 5 with Raspberry Pi OS Lite
64-bit, Python 3.11, active cooling, an owner-controlled local account, and the
documented NinjaRobot hardware topology. Simulation remains the required first
test path. Physical acceptance is recorded separately and is not implied by a
passing workstation test suite.

## Single-owner runtime boundary

One non-root NinjaRobotAgent service owns the IDE, hardware, web server, voice
listener, QR onboarding, pairing sessions, and optional pyngrok lifecycle. No
second microphone, ngrok, IDE, or hardware-owner daemon may run concurrently.
Language models can propose actions only through the existing policy and IDE
contracts.

## Voice contract

- The official wake phrase is **Hey Ninja**.
- The exact approved custom ONNX asset is identified in
  `docs/validation/phase-8-wake-model.json`.
- Wake audio remains bounded in memory. Command audio is retained only long
  enough for local transcription and is then deleted.
- One request lasts at most 15 seconds and may finish early after validated
  silence.
- The owner/default profile has an independent voice conversation session.
- Voice is input-only in `v1.0.0`; no text-to-speech or speaker is required.
- Voice requests enter the normal AgentRuntime, policy, tools, IDE,
  presentation, and memory paths. Voice is never a second robot-control path.
- The existing confirmed `/arm` and browser motion button can also authorize
  voice motion; every existing stop/revoke boundary remains fail-closed.

## Remote-access contract

ngrok is optional. Its authtoken authenticates the Pi to ngrok and never
authenticates a browser. A short-lived high-entropy QR pairing token establishes
an application session. Anonymous HTTP, asset, WebSocket, camera, microphone,
movement, and power-off access must be rejected.

The QR never contains the ngrok authtoken or a reusable password. Anyone who
can physically scan an unexpired pairing QR can pair a browser, so QR display
is a deliberate physical-presence authorization. Pairing can be revoked by the
local owner.

## Boot and shutdown contract

Installation never enables auto-start silently. An explicit command or
Interactive Tool confirmation enables the systemd unit. Service boot starts
the IDE and web server, resolves remote/local onboarding, displays the pairing
QR, and waits for the first paired WebSocket controller before running Greeting
exactly once. Only a successful Greeting transitions to Idle.

Power-off requires the paired active controller, a Power Off/Cancel modal, and
a single-use server nonce. Cleanup stops motion and voice, closes tunnel/web
work, flushes durable state, closes IDE resources, and then uses a narrowly
authorized operating-system helper. The web process never receives unrestricted
passwordless `sudo`.

## Network and dependency contract

The installed release performs no package, model, inference-asset, or ngrok
binary download during unattended boot. Setup installs and validates them in
advance. The core robot and local web service remain recoverable without
internet. A healthy ngrok QR waits for a controller indefinitely; local mDNS
appears only after a real tunnel/configuration/network failure.

## Upgrade, backup, and rollback contract

Phase 7 profiles, faces, preferences, conversations, behavior memories,
catalog entries, calibration, model choice, configuration, secrets, and safety
state must survive upgrade. Disable/uninstall preserves them by default.
Rollback stops and disables the Phase 8 unit, revokes pairing and motion,
disconnects ngrok, restores the previous locked environment and copied data,
verifies managed-driver provenance, and returns to documented manual startup.

## Release blockers

`v1.0.0` cannot be published with an anonymous remote-control path, unresolved
model/license provenance, retained raw wake/command audio, an unbounded or
duplicate hardware owner, a service enabled without confirmation, an uncertain
power-off cleanup path, a failed managed-driver check, or an unresolved
safety-critical Raspberry Pi validation result.
