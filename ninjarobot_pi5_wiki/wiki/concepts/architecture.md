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
- id: src-20261102-developmentguide
  resource: urn:llmwiki:source:src-20261102-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:d106f1e107b08da8a11f85ef97a4195e2483dcda7753aaa167f762457ee3eeb4
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
  target_hash: sha256:c7701b51efd16471f53c0d481af2815b5c7635afaa06bbe7ede3cae226711002
---

# Architecture and hardware ownership

The documented hardware path is user or model → ninjarobot_pi5_agent →
ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
interaction, model-provider translation, policy, sessions, memory, information services,
and tool proposals. It should not import a pi5 library or access a device directly.[^src-20261102-developmentguide]

The IDE (the project's device-coordination layer) owns shared resource scheduling,
action execution, safety state, behaviors, distance game loops, and hardware ownership.
Individual managed libraries own their device and standalone setup interface. The six
managed libraries cover servo motors, display, buzzer, distance sensing, camera,
and microphone.[^src-20261102-developmentguide]

This is the documented architecture contract. Compare affected code and tests
with it before implementation; this page does not certify that every failure or
physical safety condition has been tested.[^src-20261102-developmentguide]

[Read the development manual](/references/development-guide.md).

## Multi-HAT topology and servo backends

The three-layer hardware boundary (`ninjarobot_pi5_agent -> ninjarobot_pi5_ide -> pi5*`) supports three Expansion HAT topologies without Agent-to-driver coupling:
1. **`pi5servo` Multi-HAT Backends (`pi5servo/src/pi5servo/core/`)**:
   - `SunFounderRobotHatBackend` (`backends/sunfounder_robot_hat.py`): drives both the SunFounder Robot HAT v4 MCU at I2C `0x14` and the SunFounder Fusion HAT / Robot HAT v5 MCU at I2C `0x17` (`P0`..`P11` / `hat_pwm0`..`hat_pwm11`) using Big-Endian 3-byte `write_i2c_block_data` transactions serialized by a class-level `threading.RLock()`. Automatically falls back between `0x14` and `0x17` on `[Errno 121] Remote I/O error` during `_initialize_timers()`, dispatches register offsets (`0x44`/`0x20`/`0x13` on `0x14` vs `0x50`/`0x60`/`0x18` on `0x17` where PWM and timer registers advance by two bytes at `0x17`), and provides `reset_sunfounder_mcu()` on `GPIO5` for legacy `0x14` only (excluded for explicit Fusion addresses and detected Fusion sysfs).[^src-20261102-developmentguide]
   - `PCA9685ServoBackend` (`backends/pca9685.py`): adds a built-in `smbus2` controller (`_SMBusPCA9685Controller` at `0x40`) alongside optional `adafruit_pca9685` support, and accepts `hat_pwm0`..`hat_pwm15` (`pwm0`..`pwm15`, `p0`..`p15`) directly in addition to legacy GPIO `channel_map` lookups.[^src-20261102-developmentguide]
   - `ServoEndpoint` (`endpoint.py`): expands `hat_pwm` validation to `0..15`, exposes `.label`, and parses `pwm0`..`pwm15` and `p0`..`p15` aliases.[^src-20261102-developmentguide]
2. **`ninjarobot_pi5_ide` Multi-HAT Coordination (`ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/`)**:
   - `config.py`: expands `SUPPORTED_SERVO_ENDPOINTS` to `gpio12`, `gpio13`, and `hat_pwm0`..`hat_pwm15` (preserving `LEGACY_SERVO_ENDPOINTS` as default signature), normalizes endpoint aliases in `ServoConfig` and `BehaviorConfig.servo_roles`, adds `PowerConfig` (`fuel_gauge_address` `0x36`, `0x14`, or `0x17`, `warning_voltage = 7.15`, `cutoff_voltage = 6.90`, `charging_gpio`), and adds `SpeechOutputConfig.speaker_enable_gpio` with GPIO conflict validation including display, buzzer, and I2C.[^src-20261102-developmentguide]
   - `servo.py`: `_load_servo_runtime()` reads `manager.get_backend_config()` from `servo.json` and forwards `backend` and `backend_kwargs` to `ServoGroup`; `ServoDevice.read_battery_voltage_sync()` delegates to the active backend.[^src-20261102-developmentguide]
   - `audio_output.py`: `discover_i2s_output_node()` inspects `pw-dump` (with ALSA `aplay -l` fallback for `googlevoicehat`/`hifiberry` sinks), and `_set_speaker_amplifier()` uses the Fusion kernel speaker node when present, otherwise legacy amplifier GPIO, removing independent raw I2C `0x31` writes; ALSA readiness and playback agree when PipeWire tools are present without an I2S sink; speech status retains playback-health reason and failure stage.[^src-20261102-developmentguide]
   - `hardware_setup.py` & `config_import.py`: isolate single-component validation in `hardware_setup_status()` so arbitrary Digital pins (`17, 4, 27, 22`) for `pi5disp` (`dc_pin`, `rst_pin`) and `pi5buzzer` (`pin`) never collide with unconfigured default pins; choose `0x17` when Fusion sysfs is present without probing or resetting hardware; omit legacy charging GPIO23 on Fusion; retain explicit servo roles without fabricating companion endpoints; and provide `apply_hardware_profile_preset()`, `configure_sunfounder_i2s_speaker()`, and `play_sunfounder_speaker_test_tone()`.[^src-20261102-developmentguide]
   - `safety.py`: `MotionController._resolve_targets()` allows auxiliary-only servo role movements without requiring wheel roles. `_undervoltage_monitor()` polls `read_battery_voltage_sync()` when `fuel_gauge_address in (20, 23)`, using distinct reason `battery_undervoltage` (persisting measured voltage and cutoff) with non-finite reading safeguards. Completed non-latching full stops clear their transient local presentation gate.[^src-20261102-developmentguide]
3. **`ninjarobot_pi5_agent` Onboarding & Service Dispatch**:
   - `setup_wizard.py`: Prompts for `1. DFRobot DFR0566 IO Expansion HAT`, `2. SunFounder Robot HAT`, or `3. General PCA9685 PWM Expansion HAT`, running Embedded Speaker Initialization on SunFounder and Bluetooth setup on DFR0566/PCA9685.[^src-20261102-developmentguide]
   - `cloud_registry.py`, `model_selection.py`, `agent_cli.py`: Ollama catalog discovery queries local models without credentials and cloud models when an API key is stored, carrying route through CLI/IPC/runtime/persistence as provider `base_url`.[^src-20261102-developmentguide]
   - `web_app.py` / `pairing.py`: Web startup disables proxy-header rewriting (`proxy_headers=False`), allowing pairing to inspect actual loopback peers under ngrok fallback while continuing to deny direct LAN requests forging Host.[^src-20261102-developmentguide]

## Guided setup architecture and hardware dispatch

The `ninjarobot` and `ninjarobot-agent` entry points share the argument dispatcher.
`setup_wizard.py` serves as the presentation and orchestration layer for guided onboarding,
managing selections, retry/skip logic, and final launch without importing managed `pi5*` packages.
Hardware setup follows the permitted path:[^src-20261102-developmentguide]

```text
setup_wizard -> ninjarobot_pi5_ide.hardware_setup
             -> allowlisted standalone pi5* CLI -> device
```

The IDE adapter resolves a fixed allowlisted command, acquires `HardwareOwnership`, attaches the
interactive tool to the terminal, and guarantees ownership release in a `finally` block. The bulk
hardware reuse menu calls `hardware_setup_status` across modules. Microphone asset checks reuse standalone
path resolvers via the isolated `ninjarobot_pi5_ide.hardware_config_probe` subprocess to strictly avoid
importing driver modules into the IDE process, preserving intentional microphone runtime containment.[^src-20261102-developmentguide]


[^src-20261102-developmentguide]: DevelopmentGuide.md, source version `runtime-remediation-261102`; registered source `src-20261102-developmentguide`.
