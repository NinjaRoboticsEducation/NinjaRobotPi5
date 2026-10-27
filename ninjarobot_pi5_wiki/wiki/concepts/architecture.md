---
type: Concept
title: Architecture and hardware ownership
description: The Agent/IDE/device boundary, hardware ownership, and cross-device coordination.
status: draft
tags:
- architecture
- hardware
- safety
- boundaries
- ownership
- phase4
- information
- distance-game
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
- id: src-20261027-developmentguide
  resource: urn:llmwiki:source:src-20261027-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:3ab4adc6f8052f7975b17a7ebcdd893df425e47b9f16e2127a2751f71d9e73c7
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-10-27T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 25 October multi-HAT expansion and SunFounder
    hardware audit evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:e3878789077b7b0235eae47133c2a7c3c4397709231502b783b4e66ca69b2dd2
---

# Architecture and hardware ownership

The documented hardware path is user or model → ninjarobot_pi5_agent →
ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
interaction, model-provider translation, policy, sessions, memory, information services,
and tool proposals. It should not import a pi5 library or access a device directly.[^src-20261027-developmentguide]

The IDE (the project's device-coordination layer) owns shared resource scheduling,
action execution, safety state, behaviors, distance game loops, and hardware ownership.
Individual managed libraries own their device and standalone setup interface. The six
managed libraries cover servo motors, display, buzzer, distance sensing, camera,
and microphone.[^src-20261027-developmentguide]

This is the documented architecture contract. Compare affected code and tests
with it before implementation; this page does not certify that every failure or
physical safety condition has been tested.[^src-20261027-developmentguide]

[Read the development manual](/references/development-guide.md).

## Multi-HAT topology and servo backends

The three-layer hardware boundary (`ninjarobot_pi5_agent -> ninjarobot_pi5_ide -> pi5*`) supports three Expansion HAT topologies without Agent-to-driver coupling:
1. **`pi5servo` Multi-HAT Backends (`pi5servo/src/pi5servo/core/`)**:
   - `SunFounderRobotHatBackend` (`backends/sunfounder_robot_hat.py`): drives both the SunFounder Robot HAT v4 MCU at I2C `0x14` and the SunFounder Fusion HAT / Robot HAT v5 MCU at I2C `0x17` (`P0`..`P11` / `hat_pwm0`..`hat_pwm11`) using Big-Endian 3-byte `write_i2c_block_data` transactions serialized by a class-level `threading.RLock()`. Automatically falls back between `0x14` and `0x17` on `[Errno 121] Remote I/O error` during `_initialize_timers()`, dispatches register offsets (`0x44`/`0x20`/`0x13` on `0x14` vs `0x50`/`0x60`/`0x18` on `0x17`), and provides `reset_sunfounder_mcu()` on `GPIO5` via `lgpio`.[^src-20261027-developmentguide]
   - `PCA9685ServoBackend` (`backends/pca9685.py`): adds a built-in `smbus2` controller (`_SMBusPCA9685Controller` at `0x40`) alongside optional `adafruit_pca9685` support, and accepts `hat_pwm0`..`hat_pwm15` (`pwm0`..`pwm15`, `p0`..`p15`) directly in addition to legacy GPIO `channel_map` lookups.[^src-20261027-developmentguide]
   - `ServoEndpoint` (`endpoint.py`): expands `hat_pwm` validation to `0..15`, exposes `.label`, and parses `pwm0`..`pwm15` and `p0`..`p15` aliases.[^src-20261027-developmentguide]
2. **`ninjarobot_pi5_ide` Multi-HAT Coordination (`ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/`)**:
   - `config.py`: expands `SUPPORTED_SERVO_ENDPOINTS` to `gpio12`, `gpio13`, and `hat_pwm0`..`hat_pwm15` (preserving `LEGACY_SERVO_ENDPOINTS` as default signature), normalizes endpoint aliases in `ServoConfig` and `BehaviorConfig.servo_roles`, adds `PowerConfig` (`fuel_gauge_address` `0x36`, `0x14`, or `0x17`, `warning_voltage = 7.15`, `cutoff_voltage = 6.90`, `charging_gpio`), and adds `SpeechOutputConfig.speaker_enable_gpio` with GPIO conflict validation.[^src-20261027-developmentguide]
   - `servo.py`: `_load_servo_runtime()` reads `manager.get_backend_config()` from `servo.json` and forwards `backend` and `backend_kwargs` to `ServoGroup`; `ServoDevice.read_battery_voltage_sync()` delegates to the active backend.[^src-20261027-developmentguide]
   - `audio_output.py`: `discover_i2s_output_node()` inspects `pw-dump` (with ALSA `aplay -l` fallback for `googlevoicehat`/`hifiberry` sinks), and `_set_speaker_amplifier()` drives `GPIO12` (`pinctrl` + `lgpio`) and `0x17` register `0x31` before playback and pulls it low on `close()`.[^src-20261027-developmentguide]
   - `hardware_setup.py` & `config_import.py`: isolate single-component validation in `hardware_setup_status()` so arbitrary Digital pins (`17, 4, 27, 22`) for `pi5disp` (`dc_pin`, `rst_pin`) and `pi5buzzer` (`pin`) never collide with unconfigured default pins; accept any calibrated `hat_pwm0`..`hat_pwm11` channels on SunFounder Robot HAT (`hat_pwm0`..`hat_pwm15` on PCA9685); and provide `apply_hardware_profile_preset()`, `configure_sunfounder_i2s_speaker()`, and `play_sunfounder_speaker_test_tone()`.[^src-20261027-developmentguide]
   - `safety.py`: `MotionController._resolve_targets()` allows auxiliary-only servo role movements (`head_pan`, `head_tilt`, `gripper`, etc.) without requiring wheel roles, and `_undervoltage_monitor()` polls `read_battery_voltage_sync()` when `fuel_gauge_address in (20, 23)`.[^src-20261027-developmentguide]
3. **`ninjarobot_pi5_agent` Onboarding Wizard (`setup_wizard.py`)**:
   - Prompts for `1. DFRobot DFR0566 IO Expansion HAT`, `2. SunFounder Robot HAT`, or `3. General PCA9685 PWM Expansion HAT`, storing the choice in `progress.selections["hardware_profile"]` (and inferring it from `servo.json` when resuming or bulk-applying), running the Embedded Speaker Initialization flow when SunFounder Robot HAT is active, and running Bluetooth speaker setup when DFR0566 or PCA9685 is active.[^src-20261027-developmentguide]

## Guided setup architecture and hardware dispatch

The `ninjarobot` and `ninjarobot-agent` entry points share the argument dispatcher.
`setup_wizard.py` serves as the presentation and orchestration layer for guided onboarding,
managing selections, retry/skip logic, and final launch without importing managed `pi5*` packages.
Hardware setup follows the permitted path:[^src-20261027-developmentguide]

```text
setup_wizard -> ninjarobot_pi5_ide.hardware_setup
             -> allowlisted standalone pi5* CLI -> device
```

The IDE adapter resolves a fixed allowlisted command, acquires `HardwareOwnership`, attaches the
interactive tool to the terminal, and guarantees ownership release in a `finally` block. The bulk
hardware reuse menu calls `hardware_setup_status` across modules. Microphone asset checks reuse standalone
path resolvers via the isolated `ninjarobot_pi5_ide.hardware_config_probe` subprocess to strictly avoid
importing driver modules into the IDE process, preserving intentional microphone runtime containment.
Managed driver implementations and immutable baselines remain protected. Configuration import reuses
`discover_pi5_configs`, `import_pi5_configs`, and saves the consolidated robot configuration once after
hardware steps.[^src-20261027-developmentguide]

Onboarding state is stored as a versioned JSON object at `~/.local/state/ninjarobot_pi5/setup-progress.json`.
The store enforces nonblocking owner locks, bounded inputs, schema validation, symlink refusal, mode `0600`,
and atomic file replacement without storing secrets or media. `--simulation` prints an offline rehearsal without
modifying real progress; `--resume` re-checks saved settings and rejects simulated records for real-hardware readiness.
Candidate API keys stay in memory until validated, and candidate files roll back on configuration save failure.
Terminal chat uses prompt-toolkit (`terminal_input.py`) with multiline input handling (Enter submits, Shift+Enter or
Alt/Option+Enter adds newlines, Esc then Enter fallback) and portable navigation.[^src-20261027-developmentguide]

## Web controller and modular frontend architecture

The Agent layer exposes an HTTPS web controller (`web_app.py`, `web_control.py`) partitioned into two dedicated views:
- Game Pad (`/gamepad`, `gamepad.html`): Direct manual teleoperation with responsive touch D-pad, action triggers (Greeting, AI Camera preview, Emergency Stop, Resume), and a user-created behavior selector.
- Agent Interface (`/agent`, `agent.html`): Dialogue and planning viewport with conversation history, "Clear Message" UI clearing, special robot control toggles (A/B/X/Y), and audio/speech controls.[^src-20261027-developmentguide]

Frontend logic is modularized into `app-shared.js` (shared state, websocket communication, modal lifecycle, i18n localization), `app-gamepad.js` (game pad inputs and user behavior dropdown dispatch), and `app-agent.js` (chat stream handling and control button toggle states). The backend exposes `list_user_behaviors` and `run_user_behavior` hooked to IDE `_BehaviorListAdapter(source="user")`, ensuring that user behaviors with motion actions require explicit modal confirmation before execution.[^src-20261027-developmentguide]

## Refinement Phase 5 and hardware boundaries

Refinement Phase 5 introduces `ninjarobot_pi5_ide/distance_game.py`, owning strict
target distance tracking (5–60 cm), 3-band tone feedback (440/660/880 Hz via PipeWire),
and `expression_variants.py` for silent OLED eye/face animation presets without extra hardware.[^src-20261027-developmentguide]

Emergency stop priority is clarified: `servo.stop` is dispatched from an engine allowlist
with LOW risk rating rather than EMERGENCY, safely interrupting active pulses without unneeded
Level 2 stops. Stop causes are preserved across ramp transitions, obstacles are checked before
and during ramps, and the motion watchdog continues heartbeats during responsive device cleanup.
Proposed hardware changes (movable head, edge sensing, touch input) remain unpurchased, uninstalled
evaluation proposals.[^src-20261027-developmentguide]

## Agent information architecture and local tasks

Phase 4 introduces local and external information assistant capabilities. External Google Calendar
synchronization reuses `GoogleCalendarBackend` with local desktop-browser OAuth consent over an SSH
loopback (port 8765), primary-calendar auto-discovery, and remote verification via SSH. `CalendarChat` enforces
internal confirmation authority for calendar writes, rejecting direct command bypasses.
`project_documents.py` and `project_help.py` provide hash-checked runtime retrieval of bounded
published manual sections. `ResearchService` binds allowlisted Tavily snippet results to saved
runs. `BriefingService` generates deterministic bundles on request.[^src-20261027-developmentguide]

All state-modifying actions (calendar writes, note edits) require an exact preview and same-session
direct user confirmation. Models and recipes cannot confirm changes or bypass deterministic policy.
Audio playback routes through IDE PipeWire ownership with lead-in silence buffering
(`bluetooth_lead_in_seconds`, default 0.5s) and independent reconnection daemon support.[^src-20261027-developmentguide]


[^src-20261027-developmentguide]: DevelopmentGuide.md, source version `multi-hat-expansion-261025`; registered source `src-20261027-developmentguide`.
