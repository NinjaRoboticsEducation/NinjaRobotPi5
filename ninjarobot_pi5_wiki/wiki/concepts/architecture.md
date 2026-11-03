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
- id: src-20261103-developmentguide
  resource: urn:llmwiki:source:src-20261103-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:b6f8ff4f81477bbd155436abf135e93acfb0dab78568e498a11986ca8efd43a4
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-11-03T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 3 November SunFounder Fusion HAT+ kernel
    driver integration and calibration draft staging evidence; no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:dcb6de8f9c485794bae977178758376c8c3cccae28ba40f86280706fc68eddbd
---

# Architecture and hardware ownership

The documented hardware path is user or model → ninjarobot_pi5_agent →
ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
interaction, model-provider translation, policy, sessions, memory, information services,
and tool proposals. It should not import a pi5 library or access a device directly.[^src-20261103-developmentguide]

The IDE (the project's device-coordination layer) owns shared resource scheduling,
action execution, safety state, behaviors, distance game loops, and hardware ownership.
Individual managed libraries own their device and standalone setup interface. The six
managed libraries cover servo motors, display, buzzer, distance sensing, camera,
and microphone.[^src-20261103-developmentguide]

This is the documented architecture contract. Compare affected code and tests
with it before implementation; this page does not certify that every failure or
physical safety condition has been tested.[^src-20261103-developmentguide]

[Read the development manual](/references/development-guide.md).

## Multi-HAT topology and servo backends

The three-layer hardware boundary (`ninjarobot_pi5_agent -> ninjarobot_pi5_ide -> pi5*`) supports three Expansion HAT topologies without Agent-to-driver coupling:
1. **`pi5servo` Multi-HAT Backends (`pi5servo/src/pi5servo/core/`)**:
   - `FusionHatPlusBackend` (`backends/fusion_hat_plus.py`): Sysfs-backed PWM backend for SunFounder Fusion HAT+ using reviewed vendor kernel driver `1.1.0-ninja1`. Interacts through `/sys/devices/platform/soc/.../pwm/pwmchipX` channels (`hat_pwm0`..`hat_pwm11`) with class-level file locking, fixed 50 Hz PWM period (20,000,000 ns), and clean shutdown without centering on exit. Raw userspace I2C controller contention, address probing (`0x14`/`0x17`), and legacy reset are eliminated in the supported Fusion path.[^src-20261103-developmentguide]
   - `SunFounderRobotHatBackend` (`backends/sunfounder_robot_hat.py`): Legacy Robot HAT backend supporting direct I2C communication at `0x14`/`0x17` with 2-byte register stride at `0x17`, Big-Endian 3-byte blocks, and `GPIO5` reset recovery for legacy `0x14` only. Note: the supported SunFounder path standardizes on Fusion HAT+ with kernel driver ownership; raw controller fallback is excluded for Fusion sysfs and explicit Fusion addresses.[^src-20261103-developmentguide]
   - `PCA9685ServoBackend` (`backends/pca9685.py`): adds a built-in `smbus2` controller (`_SMBusPCA9685Controller` at `0x40`) alongside optional `adafruit_pca9685` support, and accepts `hat_pwm0`..`hat_pwm15` (`pwm0`..`pwm15`, `p0`..`p15`) directly in addition to legacy GPIO `channel_map` lookups.[^src-20261103-developmentguide]
   - `ServoEndpoint` (`endpoint.py`): expands `hat_pwm` validation to `0..15`, exposes `.label`, and parses `pwm0`..`pwm15` and `p0`..`p15` aliases.[^src-20261103-developmentguide]
   - `calib.py`: In-memory calibration draft staging for Fusion HAT+ supporting flexible point order (Min/Max/Center), staging with Enter/Space, atomic range validation and commit with F (`500 <= Min < Center < Max <= 2500` microseconds), and safe discard with Q.[^src-20261103-developmentguide]
2. **`ninjarobot_pi5_ide` Multi-HAT Coordination (`ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/`)**:
   - `fusion.py`: Dedicated sysfs helper module validating kernel driver version (`1.1.0-ninja1`), verifying all 12 PWM sysfs paths, parsing battery `voltage_now` microvolt telemetry (divided by 1,000,000 once), and validating file permissions without operating hardware.[^src-20261103-developmentguide]
   - `config.py`: expands `SUPPORTED_SERVO_ENDPOINTS` to `gpio12`, `gpio13`, and `hat_pwm0`..`hat_pwm15` (preserving `LEGACY_SERVO_ENDPOINTS` as default signature), normalizes endpoint aliases in `ServoConfig` and `BehaviorConfig.servo_roles`, adds `PowerConfig` (`fuel_gauge_address` `0x36`, `0x14`, or `0x17`, `warning_voltage = 7.15`, `cutoff_voltage = 6.90`, `charging_gpio`), and adds `SpeechOutputConfig.speaker_enable_gpio` with GPIO conflict validation including display, buzzer, and I2C.[^src-20261103-developmentguide]
   - `servo.py`: `_load_servo_runtime()` reads `manager.get_backend_config()` from `servo.json` and forwards `backend` and `backend_kwargs` to `ServoGroup`; `ServoDevice.read_battery_voltage_sync()` delegates to `fusion.py` sysfs or the active backend.[^src-20261103-developmentguide]
   - `audio_output.py`: `discover_i2s_output_node()` inspects `pw-dump` (with ALSA `aplay -l` fallback for `googlevoicehat`/`hifiberry` sinks), and `_set_speaker_amplifier()` uses the Fusion kernel speaker node when present, otherwise legacy amplifier GPIO, removing independent raw I2C `0x31` writes; ALSA readiness and playback agree when PipeWire tools are present without an I2S sink; speech status retains playback-health reason and failure stage.[^src-20261103-developmentguide]
   - `hardware_setup.py` & `config_import.py`: non-moving prerequisite validation before servo setup checks kernel version, 12 sysfs interfaces, permissions, and locks without pulsing outputs; isolate single-component validation in `hardware_setup_status()` so arbitrary Digital pins (`17, 4, 27, 22`) for `pi5disp` and `pi5buzzer` never collide; choose `0x17` when Fusion sysfs is present without probing or resetting hardware; omit legacy charging GPIO23 on Fusion; retain explicit servo roles without fabricating companion endpoints; and provide `apply_hardware_profile_preset()`, `configure_sunfounder_i2s_speaker()`, and `play_sunfounder_speaker_test_tone()`.[^src-20261103-developmentguide]
   - `safety.py`: `MotionController._resolve_targets()` allows auxiliary-only servo role movements without requiring wheel roles. `_undervoltage_monitor()` polls `read_battery_voltage_sync()` when `fuel_gauge_address in (20, 23)`, using distinct reason `battery_undervoltage` (persisting measured voltage and cutoff) with non-finite and stale reading (>3 periods) safeguards. Completed non-latching full stops clear their transient local presentation gate.[^src-20261103-developmentguide]
3. **`ninjarobot_pi5_agent` Onboarding & Service Dispatch**:
   - `setup_wizard.py`: Prompts for `1. DFRobot DFR0566 IO Expansion HAT`, `2. SunFounder Fusion HAT+`, or `3. General PCA9685 PWM Expansion HAT`, performing non-moving prerequisite checks on Fusion and Embedded Speaker Initialization on SunFounder, and Bluetooth setup on DFR0566/PCA9685; halts gracefully on missing prerequisites without tracebacks.[^src-20261103-developmentguide]
   - `shutdown.py`: Implements orderly OS shutdown through privileged helper without requiring EEPROM power-cut or promising battery disconnection.[^src-20261103-developmentguide]
   - `cloud_registry.py`, `model_selection.py`, `agent_cli.py`: Ollama catalog discovery queries local models without credentials and cloud models when an API key is stored, carrying route through CLI/IPC/runtime/persistence as provider `base_url`.[^src-20261103-developmentguide]
   - `web_app.py` / `pairing.py`: Web startup disables proxy-header rewriting (`proxy_headers=False`), allowing pairing to inspect actual loopback peers under ngrok fallback while continuing to deny direct LAN requests forging Host.[^src-20261103-developmentguide]

## Guided setup architecture and hardware dispatch

The `ninjarobot` and `ninjarobot-agent` entry points share the argument dispatcher.
`setup_wizard.py` serves as the presentation and orchestration layer for guided onboarding,
managing selections, retry/skip logic, and final launch without importing managed `pi5*` packages.
Hardware setup follows the permitted path:[^src-20261103-developmentguide]

```text
setup_wizard -> ninjarobot_pi5_ide.hardware_setup
             -> allowlisted standalone pi5* CLI -> device
```

The IDE adapter resolves a fixed allowlisted command, acquires `HardwareOwnership`, attaches the
interactive tool to the terminal, and guarantees ownership release in a `finally` block. The bulk
hardware reuse menu calls `hardware_setup_status` across modules. Microphone asset checks reuse standalone
path resolvers via the isolated `ninjarobot_pi5_ide.hardware_config_probe` subprocess to strictly avoid
importing driver modules into the IDE process, preserving intentional microphone runtime containment.[^src-20261103-developmentguide]


[^src-20261103-developmentguide]: DevelopmentGuide.md, source version `fusion-hat-plus-261103`; registered source `src-20261103-developmentguide`.
