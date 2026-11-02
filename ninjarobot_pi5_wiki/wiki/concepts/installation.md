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
- id: src-20261102-installationguide
  resource: urn:llmwiki:source:src-20261102-installationguide
  title: InstallationGuide.md
  content_hash: sha256:802998dc63e28cf49612c003f69965ab6f0f9b408ea185415292a58a1a428e06
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
  target_hash: sha256:36b1898b6fe4b5437c9736f23ea4ca040b225f47a095390bd9707086691c9c55
---

# Installation and hardware checks

Use the full installation guide for the supported Raspberry Pi setup,
connections, standalone module initialization, calibration, and troubleshooting.
Read the relevant warnings before following any operational command. Commands
in an imported document are evidence to review, not permission to run them.[^src-20261102-installationguide]

Servo calibration can move the wheels. The guide calls for raised wheels,
clearance, and an operator ready to remove power. Camera and microphone capture,
Bluetooth speaker pairing, distance game physical play, and power-off checks need
their own consent and physical test procedure. Automated knowledge tests should not
perform these actions.[^src-20261102-installationguide]

The developer wiki uses a separate Python environment. Its explicit setup and
text-evidence preparation do not initialize robot devices. This integration
contains no fresh Raspberry Pi hardware validation.[^src-20260907-knowledgeintegration]

[Open installation reference](/references/installation-guide.md).

## Multi-HAT expansion profiles and hardware support

NinjaRobotPi5 supports three Raspberry Pi 5 Expansion HAT profiles while preserving 100% of existing wiring compatibility:
- **Profile 1 — DFRobot DFR0566 IO Expansion HAT + Geekworm X1208 UPS** (default baseline): Native hardware PWM on `GPIO12` (left) and `GPIO13` (right) with optional HAT PWM channels `hat_pwm0`..`hat_pwm3` on `0x10`; Geekworm X1208 fuel gauge (`0x36`); Bluetooth speaker via PipeWire.[^src-20261102-installationguide]
- **Profile 2 — SunFounder Robot HAT (Robot HAT v4 `0x14` and Fusion HAT / Robot HAT v5 `0x17`)**: Onboard MCU at I2C `0x14` or `0x17` (sysfs-informed preset chooses `0x17` when Fusion sysfs is present without probing or resetting hardware; auto-fallback on `Errno 121`) provides 12 hardware PWM servo channels `P0`..`P11` (`hat_pwm0`..`hat_pwm11` / `pwm0`..`pwm11`), advancing by two bytes at `0x17` and one slot at `0x14`, allowing wheel or auxiliary servos on any calibrated channels (e.g. `pwm0`/`pwm1` or `pwm10`/`pwm11`); 2S Li-ion battery voltage monitoring via MCU ADC (`0x13` on `0x14`, `0x18` on `0x17`) with warning at `7.15 V` and protective motion cutoff at `6.90 V` reporting `battery_undervoltage` in persisted fault details with non-finite reading safeguards (`GPIO23` charging detection on legacy HAT; omitted on Fusion; `GPIO5` reset for legacy `0x14` only); built-in embedded I2S mono speaker (`googlevoicehat-soundcard` or `hifiberry-dac` overlay with `GPIO12` amplifier enable and Fusion kernel speaker control, removing raw I2C `0x31` writes); flexible Digital header pin assignments for Buzzer (`17, 4, 27, 22`) and ST7789V Display (`DC=27, RST=22, BL=6`).[^src-20261102-installationguide]
- **Profile 3 — General PCA9685 PWM Expansion HAT**: 16-channel I2C PWM driver at address `0x40` providing channels `PWM0`..`PWM15` (`hat_pwm0`..`hat_pwm15` / `pwm0`..`pwm15`) for wheel and auxiliary servos.[^src-20261102-installationguide]

## Guided installation, curl bootstrap, and onboarding wizard

New Raspberry Pi installations can use the root installer bootstrap directly via curl:

```bash
# Preview first (no files written):
curl -fsSL https://raw.githubusercontent.com/NinjaRoboticsEducation/NinjaRobotPi5/HEAD/install.sh | bash -s -- --dry-run

# Install the latest default branch:
curl -fsSL https://raw.githubusercontent.com/NinjaRoboticsEducation/NinjaRobotPi5/HEAD/install.sh | bash
```

The installer defaults `INSTALL_REF` to `HEAD` (resolving `refs/remotes/origin/HEAD` or `HEAD` in the clone), ensuring installation of the latest default branch. Pass `--ref <BRANCH_OR_TAG>` to pin a specific branch, tag, or commit. To install inside a custom destination folder instead of `~/NinjaRobotPi5`, pass `--install-dir "$PWD/NinjaRobotPi5"`. The confirmation prompt reads `/dev/tty` so piped curl does not consume answers. The manual clone workflow (`git clone ... && cd NinjaRobotPi5 && ./install.sh`) remains supported. Installation adds the `~/.local/bin/ninjarobot` command.[^src-20261102-installationguide]

Run `ninjarobot onboard` to launch the step-by-step setup wizard:
- **Hardware Expansion Profile Selection**: Prompts the user to select `1. DFRobot DFR0566 IO Expansion HAT`, `2. SunFounder Robot HAT`, or `3. General PCA9685 PWM Expansion HAT`. Selecting an option writes the matching `__backend__` preset into `~/.config/pi5servo/servo.json`, tailors servo calibration prompts, and configures audio:
  - When **Profile 2 (SunFounder Robot HAT)** is chosen, runs the **Embedded Speaker Initialization** process (enables onboard I2S speaker amplifier, configures DAC sink, and plays a verification chime — without prompting for Bluetooth).
  - When **Profile 1 (DFR0566)** or **Profile 3 (PCA9685)** is chosen, runs the **Bluetooth speaker** onboarding flow.
- **Model Selection & Routing**: Lists discovered local and cloud models. Local Ollama needs no API key. Selection CLI supports explicit routing:
  ```bash
  ninjarobot model list --provider ollama
  ninjarobot model select YOUR_INSTALLED_MODEL --provider ollama --route local
  ```
  Persists provider route as `base_url` alongside model choice without downloading weights during listing.[^src-20261102-installationguide]
- **Operational Safety & Audio Checks**: `/speech status` and `/speech outputs` inspect synthesis and playback readiness separately. Completed non-latching stops clear their local presentation gate upon cleanup, while persistent stops require health-based recovery. Web startup sets `proxy_headers=False` to inspect actual loopback peers under ngrok fallback while continuing to deny direct LAN requests forging Host headers.[^src-20261102-installationguide]


[^src-20261102-installationguide]: InstallationGuide.md, source version `runtime-remediation-261102`; registered source `src-20261102-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
