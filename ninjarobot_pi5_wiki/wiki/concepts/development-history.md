---
type: Concept
title: Development history and decisions
description: Find dated rationale and distinguish historical evidence from current
  implementation.
status: draft
tags:
- history
- decisions
- rationale
- development
- log
- phase4
- phase5
- clock
- calendar
- ui-refinement
- onboarding
- expansion-hat
- sunfounder
- pca9685
- reconnection
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20261109-developmentlog
  resource: urn:llmwiki:source:src-20261109-developmentlog
  title: DevelopmentLog.md
  content_hash: sha256:c4a0fab292e729b1edafcd2a8039a65cdd63c1bdd8e18970a4d6c370afed2214
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-11-09T00:00:00Z'
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered 9 November browser reconnection, controller
    handoff, and connected welcome/idle refinement evidence (development history);
    no human verification is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending physical acceptance, live third-party accounts, and monetary
    spending caps.
  target_hash: sha256:5cf147f6ecadd58871a2c82327162f67f38c8378e04ea4bdafbef6c2f2632284
---

# Development history and decisions

The development log retains dated records of implementation work, design
choices, repairs, validation, and remaining work. Use a relevant dated entry
when answering why a change was made. Read surrounding entries to determine
whether a later decision superseded it.[^src-20261109-developmentlog]

Historical success reports refer to the recorded work and environment. They do
not prove that today's checkout passes the same checks, or that a physical
device was tested during a later documentation task. Cite the entry and state
which current checks were actually run.[^src-20261109-developmentlog]

[Complete development log](/references/development-log.md).

## Recent milestones (12 September – 9 November 2026)

- **System clock access (12 September 2026)**: Added `/time` chat command and read-only `system.time.get` tool, providing fresh OS clock and timezone context for model turns and relative reminders.[^src-20261109-developmentlog]
- **Refinement Phase 5 software and hardware evaluation (13 September 2026)**: Implemented software foundations for the bounded distance game (`ninjarobot_pi5_ide/distance_game.py`, 3-band tone feedback) and silent expression variations (`expression_variants.py`). Evaluated proposed hardware additions (desk-edge sensing, movable head, touch input, speaker output) without purchase or physical installation.[^src-20261109-developmentlog]
- **Narrowed Phase 4 foundations (13 September 2026)**: Implemented M03 memory ranking, M04 read-only recipes, X01 version-2 skills, and X05 public project help with database migration 6.[^src-20261109-developmentlog]
- **Phase 4 information assistant completion (13 September 2026)**: Implemented T04 Google Calendar planning, T05 research service, and T06 notes/checklists/requested briefings with database migration 7 and 7-day preview cleanup.[^src-20261109-developmentlog]
- **Servo stop, rolling chat context, and default games (15 September 2026)**: Assigned `servo.stop` priority dispatch from an engine allowlist with LOW risk level instead of EMERGENCY stop. Added rolling transcript window in `AgentLoop` fitting character limits with trusted truncation notices. Default-enabled the distance game configuration (`[distance_game]`).[^src-20261109-developmentlog]
- **Approved servo and sensor recovery repair (15 September 2026)**: Preserved intentional stop causes across ramp transitions through the motion owner, added pre-ramp and active ramp obstacle checks, and bounded distance sensor preparation/recovery.[^src-20261109-developmentlog]
- **Web controller and repeated-game follow-up (15 September 2026)**: Removed redundant action-admission game check blocking web movement, added visible web error banners, re-initialized the buzzer on repeated games, and preserved watchdog heartbeats during cleanup.[^src-20261109-developmentlog]
- **Distance game hand-placement correction (16 September 2026)**: Addressed game start timing so play begins before the final chat response with immediate web chat guidance. Out-of-range sensor readings wait silently for hand presence, completing with `no_target_detected` and recording rejection metrics.[^src-20261109-developmentlog]
- **Google Calendar guided setup & discovery (17 September 2026)**: Added primary-calendar auto-discovery, user-scoped registration reusing connection ID on reauthorization, loopback SSH port 8765 helper, and default credentials storage.[^src-20261109-developmentlog]
- **Calendar preview validation & CONFIRM (17 September 2026)**: Added field-specific validation errors (e.g. required timezone `Asia/Tokyo`, title, ISO timestamps) and plain `CONFIRM` / `CANCEL` chat confirmation for event create previews.[^src-20261109-developmentlog]
- **Unified confirmation flow for all event changes (17 September 2026)**: Extended standalone single-word `CONFIRM` / `CANCEL` flow across create, update, and delete operations via `CalendarChat`, rejecting command bypasses and version conflicts.[^src-20261109-developmentlog]
- **Hash-checked public project help (17 September 2026)**: Replaced static 4-page retrieval with hash-checked published manual sections and continuation tokens (`project_documents.py`, `project_help_sources.json`).[^src-20261109-developmentlog]
- **Web interface refinement & terminal menu consolidation (18 September 2026)**: Partitioned web controller into dedicated Game Pad (`/gamepad`) and Agent Interface (`/agent`) pages with hamburger menu navigation; modularized frontend scripts (`app-shared.js`, `app-gamepad.js`, `app-agent.js`); added user-created behaviors execution from the web UI with motion confirmation modals; refined button styling and toggle states (A/B/X/Y and audio controls); maintained 146 translation keys across 4 locales; streamlined IDE interactive menu to options 1–5 and Q (Bluetooth speaker connection is option 5) and removed single-key 'e' emergency stop injection.[^src-20261109-developmentlog]
- **Guided onboarding, curl bootstrap, and editable chat (22 September 2026)**: Added unified `ninjarobot` CLI entry point with resumable onboarding wizard (`setup_wizard.py`) orchestrating 5 mandatory hardware checks through IDE locking and standalone CLIs (raised wheels for servo; camera/mic privacy consent), optional Bluetooth/whisper.cpp mic setup, 4 model providers, 3 read-only external MCP presets (Tavily Search, Google Calendar stdio MCP, Notion OAuth on loopback 8766), remote access (ngrok / authenticated same-Wi-Fi HTTPS), and simulation/real launch into chat. Upgraded interactive terminal chat to prompt-toolkit with arrow navigation, Enter submit, multiline bindings (Shift+Enter, Alt/Option+Enter, Esc then Enter fallback). Added standalone curl streaming bootstrap to `install.sh` with commit ID verification and idempotent `~/.local/bin/ninjarobot` user launcher symlink. All 1,021 repository tests and 457 driver tests passed without physical actuator movement.[^src-20261109-developmentlog]
- **Curl installation repair and custom installation directories (23 September 2026)**: Resolved non-default branches through explicit remote references before detached checkout, disambiguating branch/tag names; added `--install-dir` custom installation path support; confirmation now reads controlling terminal `/dev/tty` so curl piping does not hide answers; 1,034 repository tests and 457 driver tests passed.[^src-20261109-developmentlog]
- **Onboarding interface, reuse, and OAuth repair (23 September 2026)**: Added ASCII welcome, numeric menus, bulk settings reuse ("2) Apply existing settings for all modules"), automatic configuration checks, Enter-to-continue summaries, and removed redundant typed YES/APPLY phrases; added Mac SSH forwarding instructions (`-L 127.0.0.1:8765:127.0.0.1:8765`), waiting updates, callback receipt acknowledgment, and end-to-end read-only Calendar MCP validation; staged candidate credentials before replacement with rollback on save failure; isolated microphone asset checking via `ninjarobot_pi5_ide.hardware_config_probe` subprocess to preserve runtime import containment; 1,065 full-suite tests passed.[^src-20261109-developmentlog]
- **Multi-HAT expansion upgrade and physical SunFounder hardware audit (25 October 2026)**: Implemented multi-HAT hardware support across `install.sh` (`INSTALL_REF=HEAD`), `pi5servo` (dual `0x14`/`0x17` SunFounder MCU backend with automatic fallback, PCA9685 smbus2 controller at `0x40` accepting `hat_pwm0`..`15`, 8 authorized driver changes recorded in `docs/validation/authorized_driver_changes.json`), `ninjarobot_pi5_ide` (pin collision fix for display/buzzer, flexible PWM calibration, embedded I2S speaker with GPIO12 amp enable and `0x17` register `0x31`, auxiliary-only servo roles in behaviors, battery undervoltage monitoring at 7.15V/6.90V for `0x14`/`0x17`), and `ninjarobot_pi5_agent` (onboarding hardware profile selection and embedded speaker flow). 1,087 root/IDE/Agent tests and 139 `pi5servo` tests passed without physical actuator movement.[^src-20261109-developmentlog]
- **Runtime remediation and Multi-HAT hardware refinement (2 November 2026)**: Web startup disables proxy-header rewriting (`proxy_headers=False`) allowing loopback proxy pairing inspection without accepting forged LAN host headers; distinct `battery_undervoltage` reason keeps measured voltage and cutoff in persisted fault details with non-finite reading safeguards; SunFounder preset chooses `0x17` when Fusion sysfs is present without probing or resetting hardware; completed non-latching full stop clears transient local presentation gate; embedded audio uses Fusion kernel speaker node when present, removing raw I2C `0x31` write; ALSA readiness and playback agree when PipeWire tools are present without an I2S sink; 2-byte register stride for Fusion PWM/timers at `0x17`; config import preserves explicit servo roles without companion fabrication; and route-persisting local/cloud Ollama catalog discovery and selection. All 1,104 root tests and 464 driver tests passed without live actuator movement.[^src-20261109-developmentlog]
- **SunFounder Fusion HAT+ kernel driver integration and calibration draft staging (3 November 2026)**: Standardized SunFounder support strictly on Fusion HAT+ backed by reviewed vendor kernel driver `1.1.0-ninja1` via sysfs (`hat_pwm0`..`hat_pwm11` across 3 shared timer groups at fixed 50 Hz), removing userspace I2C address probing, legacy reset, and bus contention; added `scripts/fusion_hat_setup.py` (check, prepare, preview, install, rollback) with persistent cache recovery (`$HOME/.cache/ninjarobot/fusion-source`); implemented non-moving onboarding prerequisite validation halting cleanly on missing driver/sysfs nodes without tracebacks; added in-memory servo calibration draft staging (stage Min/Max/Center in any order with Enter/Space, atomic commit with F requiring `500 <= Min < Center < Max <= 2500` microseconds, discard with Q, clean exit without centering); and refined battery telemetry dividing kernel `voltage_now` by 1,000,000 once with distinct `battery_undervoltage` cutoff (6.90 V). Passed 1,132 repository unit tests, 159 `pi5servo` tests (including all draft entry orders), and driver suites across separate processes without live actuator movement.[^src-20261109-developmentlog]
- **Fusion agent integration remediation (4 November 2026)**: Remediated post-onboarding Fusion HAT+ agent integration issues: safety latch timestamping in `safety.py`, `ServoDevice.status` motion latch exposure, Level 1 `/resume` dispatch in `runtime.py`, `/arm` and `/disarm` chat commands, signed `-90`..`90` single-servo routing in `prompts.py` and `service_main.py`, live `speech_output` state in prompts, automated Piper TTS provisioning in `prepare_speech_voice.py`, `memory-notice` turn filtering in `agent_loop.py`, standalone `install-poweroff` helper in `deployment.py`, LAN controller pairing in `web_app.py`, browser microphone lifecycle awaiting `onend` in `app-agent.js`, and 48 kHz voice input stability in `microphone.py` and `voice_input.py`.[^src-20261109-developmentlog]
- **Web microphone lifecycle repair (4 November 2026)**: Browser dictation retains recognition session until `onend`, queuing one restart on stop-click and cancelling on repeat click, Send, or hide; falls back to robot push-to-talk when speech recognition is unavailable; and audio child-process cleanup awaits stdin closure with broken-pipe tolerance (`app-agent.js`, `audio_process.py`). 1,141 main tests and driver suites passed.[^src-20261109-developmentlog]
- **Documentation reconciliation (4 November 2026)**: Reconciled README and raw manuals (`2026-11-04-03`) with current Fusion implementation: added complete driver sequence, first-use acceptance checklist, and corrected cloud-only Ollama instructions, persistent cache path, and wiring tables.[^src-20261109-developmentlog]
- **Browser reconnection and controller handoff (9 November 2026)**: Implemented serialized lease cleanup, attachment generations, immediate revocation, automatic pairing QR redisplay, durable waiting display reservation, endpoint invalidation, and browser departure/Back-Forward recovery across all supported Expansion HAT profiles. Commands from lost connections are rejected; active requests, movement, speech, and capture are cancelled. Clean disconnect reserves lease for up to 10 seconds (or heartbeat deadline) for same-browser reconnect without action replay; unannounced loss detected by 15s heartbeat deadline and watchdog polling. Passed 1,152 root tests and managed driver suites across separate processes without live actuator movement.[^src-20261109-developmentlog]
- **Welcome and connected Idle refinement (9 November 2026 follow-up)**: Changed per-service Greeting suppression to per-controller-lease welcome coordinator. Lease and heartbeat processing continue during tracked cancellable welcome task; normal actions wait for completion. Delayed remote events check endpoint generation before revoking a live browser. Interrupted welcome does not suppress first successful startup completion. Same-lease grace reconnect restores Idle. Passed 1,157 root tests and all six managed suites without live actuator movement.[^src-20261109-developmentlog]

The software test gates pass across agent and IDE test suites. Physical Bluetooth speaker
audibility, live actuator movement, sensor timing on real hardware, and monetary spending
cap enforcement remain unverified gaps.[^src-20261109-developmentlog]


[^src-20261109-developmentlog]: DevelopmentLog.md; registered source `src-20261109-developmentlog`.
