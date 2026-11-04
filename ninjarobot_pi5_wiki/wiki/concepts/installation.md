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
- expansion-hat
- sunfounder
- pca9685
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20261104-installationguide
  resource: urn:llmwiki:source:src-20261104-installationguide
  title: InstallationGuide.md
  content_hash: sha256:2851ccda47e03c5c0e703cb58c528a905b2de3eb0c8315e5328d19d1a2ac8175
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
  target_hash: sha256:bd155154b680f1bd4bf6e577d24a33ceb3b0d695c8ff3ade5e79844f25dc8865
---

# Installation and hardware checks

Use the full installation guide for the supported Raspberry Pi setup,
connections, standalone module initialization, calibration, and troubleshooting.
Read the relevant warnings before following any operational command. Commands
in an imported document are evidence to review, not permission to run them.[^src-20261104-installationguide]

Servo calibration can move the wheels. The guide calls for raised wheels,
clearance, and an operator ready to remove power. Camera and microphone capture,
Bluetooth speaker pairing, distance game physical play, and power-off checks need
their own consent and physical test procedure. Automated knowledge tests should not
perform these actions.[^src-20261104-installationguide]

The developer wiki uses a separate Python environment. Its explicit setup and
text-evidence preparation do not initialize robot devices. This integration
contains no fresh Raspberry Pi hardware validation.[^src-20260907-knowledgeintegration]

[Open installation reference](/references/installation-guide.md).

## Multi-HAT expansion profiles and hardware support

NinjaRobotPi5 supports three Raspberry Pi 5 Expansion HAT profiles while preserving 100% of existing wiring compatibility:
- **Profile 1 — DFRobot DFR0566 IO Expansion HAT + Geekworm X1208 UPS** (default baseline): Native hardware PWM on `GPIO12` (left) and `GPIO13` (right) with optional HAT PWM channels `hat_pwm0`..`hat_pwm3` on `0x10`; Geekworm X1208 fuel gauge (`0x36`); Bluetooth speaker via PipeWire.[^src-20261104-installationguide]
- **Profile 2 — SunFounder Fusion HAT+ only**: Backed exclusively by reviewed kernel driver `1.1.0-ninja1` via sysfs (`/sys/devices/platform/soc/.../pwm/pwmchipX`), eliminating raw userspace I2C writes, address probing, and reset pulsing. Provides 12 hardware PWM channels `hat_pwm0`..`hat_pwm11` (`pwm0`..`pwm11`) sharing timers in 3 groups of 4 at fixed 50 Hz, allowing wheel or auxiliary servos on any calibrated channels; 2S Li-ion battery voltage monitoring via kernel `voltage_now` telemetry (microvolts divided by 1,000,000 once) with warning at `7.15 V` and protective motion cutoff at `6.90 V` reporting `battery_undervoltage` in persisted fault details with non-finite and stale sample safeguards; built-in embedded I2S mono speaker (`googlevoicehat-soundcard` or `hifiberry-dac` overlay with `GPIO12` amplifier enable and Fusion kernel speaker node control); flexible Digital header pin assignments for Buzzer (`17, 4, 27, 22`) and ST7789V Display (`DC=27, RST=22, BL=6`). Older Robot HAT profiles (`0x14` or raw `0x17`) must migrate through onboarding; raw controller fallback is excluded for Fusion.[^src-20261104-installationguide]
- **Profile 3 — General PCA9685 PWM Expansion HAT**: 16-channel I2C PWM driver at address `0x40` providing channels `PWM0`..`PWM15` (`hat_pwm0`..`hat_pwm15` / `pwm0`..`pwm15`) for wheel and auxiliary servos.[^src-20261104-installationguide]

## SunFounder Fusion HAT+ setup, driver preparation, and rollback

Kernel driver installation and verification use `scripts/fusion_hat_setup.py`:
- **Read-only health check**: `uv run --frozen python scripts/fusion_hat_setup.py check` validates driver version, PWM sysfs channels, sound nodes, and locks.
- **Source preparation into persistent cache**:
  ```bash
  uv run --frozen python scripts/fusion_hat_setup.py prepare --source "$HOME/.cache/ninjarobot/fusion-source"
  ```
  Downloads checksum-pinned vendor archive and applies `0001-safe-pwm-and-battery.patch`.
- **Preview before installation**:
  ```bash
  uv run --frozen python scripts/fusion_hat_setup.py install --source "$HOME/.cache/ninjarobot/fusion-source"
  ```
  Runs verification without modifying boot settings or overlays.
- **Explicit administrator installation**:
  ```bash
  sudo .venv/bin/python scripts/fusion_hat_setup.py install --source "$HOME/.cache/ninjarobot/fusion-source" --apply
  ```
- **Rollback**: In maintenance window with servos unpowered: `sudo .venv/bin/python scripts/fusion_hat_setup.py rollback --apply`.[^src-20261104-installationguide]

## Guided installation, curl bootstrap, and onboarding wizard

New Raspberry Pi installations can use the root installer bootstrap directly via curl:

```bash
# Preview first (no files written):
curl -fsSL https://raw.githubusercontent.com/NinjaRoboticsEducation/NinjaRobotPi5/HEAD/install.sh | bash -s -- --dry-run

# Install the latest default branch:
curl -fsSL https://raw.githubusercontent.com/NinjaRoboticsEducation/NinjaRobotPi5/HEAD/install.sh | bash
```

The installer defaults `INSTALL_REF` to `HEAD` (resolving `refs/remotes/origin/HEAD` or `HEAD` in the clone), ensuring installation of the latest default branch. Pass `--ref <BRANCH_OR_TAG>` to pin a specific branch, tag, or commit. To install inside a custom destination folder instead of `~/NinjaRobotPi5`, pass `--install-dir "$PWD/NinjaRobotPi5"`. The confirmation prompt reads `/dev/tty` so piped curl does not consume answers. The manual clone workflow (`git clone ... && cd NinjaRobotPi5 && ./install.sh`) remains supported. Installation adds the `~/.local/bin/ninjarobot` command.[^src-20261104-installationguide]

Run `ninjarobot onboard` to launch the step-by-step setup wizard:
- **Hardware Expansion Profile Selection**: Prompts the user to select `1. DFRobot DFR0566 IO Expansion HAT`, `2. SunFounder Fusion HAT+`, or `3. General PCA9685 PWM Expansion HAT`. Selecting an option writes the matching `__backend__` preset into `~/.config/pi5servo/servo.json`, tailors servo calibration prompts, and configures audio:
  - When **Profile 2 (SunFounder Fusion HAT+)** is chosen, performs non-moving prerequisite checks (driver version, 12 PWM channels, write permissions, shared locks) before servo setup, halting with recovery advice if missing. Runs **Embedded Speaker Initialization** (enables onboard I2S speaker amplifier, configures DAC sink, and plays a verification chime — without prompting for Bluetooth).
  - When **Profile 1 (DFR0566)** or **Profile 3 (PCA9685)** is chosen, runs the **Bluetooth speaker** onboarding flow.
- **In-Memory Servo Calibration Draft Staging**:
  1. Open step 4 servo tool and choose Calibrate, then populated endpoint (`hat_pwm0`..`hat_pwm11`).
  2. Press X for Max, adjust with Up/Down (20 us) or W/S (1 us), then Enter or Space. Stages Max in memory without writing to disk.
  3. Press V for Min, adjust and stage. Press C for Center, adjust and stage. Points can be entered in any order.
  4. Press F to Finish and save: validates `500 <= Min < Center < Max <= 2500` microseconds and commits atomically to `servo.json`.
  5. Press Q to discard the draft and leave saved configuration unchanged. Exit turns off PWM without centering servos.[^src-20261104-installationguide]
- **Model Selection & Routing**: Lists discovered local and cloud models. Local Ollama needs no API key. Selection CLI supports explicit routing:
  ```bash
  ninjarobot model list --provider ollama
  ninjarobot model select YOUR_INSTALLED_MODEL --provider ollama --route local
  ```
  Persists provider route as `base_url` alongside model choice without downloading weights during listing.[^src-20261104-installationguide]
- **Operational Safety, Speech & Power Provisioning**:
  - `/speech status` and `/speech outputs` inspect synthesis and playback readiness separately. Embedded speaker Piper TTS is provisioned via:
    ```bash
    uv run --frozen python scripts/prepare_speech_voice.py --install-piper --configure --apply
    ```
  - Standalone web power-off helper installation installs `/usr/libexec/ninjarobot-poweroff` and `/etc/sudoers.d/ninjarobot-agent-poweroff` without enabling boot auto-start:
    ```bash
    uv run --frozen ninjarobot-agent deployment install-poweroff --confirm
    ```
  - `/resume` performs Level 1 motion latch recovery health-checks without clearing system locks, leaving AI motion disarmed until `/arm` is entered.
  - Browser dictation retains its recognition session until `onend`, queuing one restart on stop-click, cancelling on Send or page-hide, and falling back to robot push-to-talk (`usb_microphone`) over plain HTTP.
  - Web startup sets `proxy_headers=False` to inspect actual loopback peers under ngrok fallback while continuing to deny direct LAN requests forging Host headers.[^src-20261104-installationguide]


[^src-20261104-installationguide]: InstallationGuide.md, source version `fusion-agent-remediation-261104`; registered source `src-20261104-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
