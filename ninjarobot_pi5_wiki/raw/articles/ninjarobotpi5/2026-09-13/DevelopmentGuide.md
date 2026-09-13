# NinjaRobotPi5 Development Guide

## Current refinement checkpoint — Phase 5, 13 September 2026

The owner approved implementing refinement Phase 5 before Phase 4. Optional silent
expression variations and the bounded distance game are implemented in software.
Both settings default to disabled. Phase 4 remains unimplemented. Physical Phase 5
acceptance is still required; automated tests are not hardware certification.
Historical phase numbers elsewhere in this manual describe earlier development.

Use the [Phase 5 walkthrough](../../../../../docs/validation/refinement_phase5_walkthrough_260912.md)
for exact Lite terminal commands, configuration, independent stopping, expected
results and rollback. See the [handoff](../../../../../docs/validation/refinement_phase5_handoff_260913.md)
for validation evidence and the [hardware evaluation](../../../../../DevelopmentPlanDoc/hardware/HardwareOptions_260912.md)
for proposals that have not been purchased, installed or physically tested.

This new source preserves the previous manual. Wiki ingestion and semantic review
are deferred at the owner's request; curated pages still describe their registered
checkpoint. Read this source directly for Phase 5 behavior.

### Phase 5 architecture and extension points

`ninjarobot_pi5_ide/distance_game.py` owns strict requests, fresh-reading validation,
three-band feedback, admission, finite execution and independent stop/status.
`expression_variants.py` selects a bounded palette once per conversational
expression opportunity, preserving canonical named definitions and managed assets.

The existing execution engine accepts an optional asynchronous admission context
before scheduler resources are acquired. The integrated client uses it to reject
busy game starts and cancel a game before incoming ordinary work acquires locks.
Existing IDE error codes/statuses and the trusted emergency-stop lane are preserved.
Game stop/status bypass ordinary workers without interrupting unrelated resources.
The game never reserves `servo_bus`; it reserves shared display, buzzer and distance
resources, including the existing I2C identifiers needed to exclude raw reads.

The shared distance adapter shields and retains one underlying worker across caller
cancellation, observes its completion and blocks close/reopen/read overlap. Normal
`start()` does not silently clear a cancelled-work fault; full recovery uses
`start(recover=True)`. Public `distance.read` arguments and result fields remain
unchanged. Non-finite timestamps are rejected. Unresolved sensor close retains the
assembly's hardware ownership. No managed driver was changed.

The feedback loop uses a 200 ms sampling target, 250 ms read budget, three-sample
median and 20 mm boundary margin. It rejects cached/backward/future timestamps and
inconsistent clocks. Pulses are 60 ms at 440/660/880 Hz, no more than three per
second and at most ten seconds cumulatively. Short owned pulses avoid a detached
melody or sensor task backlog. Physical timing must still be measured on the Pi.

Agent `game_control` uses existing deterministic policy, IDE tool records and
local request receipts. CLI, IPC (the local controller/service channel) and web
share it; web stop/status remain available during busy chat. The bundled
`distance-game` skill uses version 1 and needs no Phase 4 database or skill upgrade.
External model output never chooses pins, volume, arbitrary code or sensor loops.

Run `test_phase5_foundations.py`, `test_distance_game.py` and `test_game_controls.py`
for focused fake-device coverage, then the full repository gate. The existing
`scripts/validate_phase3_web_layout.py` also checks game controls under a pending
start in four languages and four viewport sizes. It uses fake browser messages,
not a real robot. See the handoff for exact completed checks and limitations.


## System clock access — 12 September 2026

The Agent now reads the Raspberry Pi OS clock for each model turn. The read-only
`system.time.get` tool provides a fresh date/time, timezone and offset, and `/time`
shows the same information in terminal or web chat without a model call. Relative
reminder requests use the fresh time reference and the Pi timezone unless the user
specifies another zone. Exact reminder previews and user confirmation are unchanged.
This reads OS time; it does not change clock settings or certify network time sync.

See the [clock fix and manual tests](../../../../../docs/validation/system_time_fix_260912.md).
This is a new source revision awaiting ingestion; the owner's previously reviewed
12 September sources are preserved unchanged. No new packages or hardware changes
are required. Restart an existing Agent to load the fix.

## Phase 3 follow-up — 12 September 2026

The current follow-up adds IDE menu **8 — Bluetooth Speaker Connection**, saved
speaker selection and an independent optional reconnect user service. It works
without the Agent running after the operator enables it; boot/logout operation
also requires user lingering. No robot startup is added by that service.

Use the [follow-up walkthrough and manual tests](../../../../../docs/validation/refinement_phase3_followup_walkthrough_260912.md)
for the current wizard, reconnection, first-word checks and rollback. The manual
Bluetooth commands below remain an alternative for diagnosing missing OS audio
prerequisites. They are no longer the normal multi-command pairing workflow.

Web shortcuts are now **A — Speech ON** and **B — Speech OFF**. The speech dropdown
is removed; use `/speech stop` in chat for stop-only behavior, or B to stop and
keep future replies silent. Guided Checks are available through `/guide 1` through
`/guide 5`, not the hamburger menu. Greeting and Celebrate remain robot behaviors.
Use `/help speech` or ask a natural-language command-help question for instructions.

Model task queries return compact owned pages with IDs, contents and scheduling
details. They omit internal execution evidence, and scheduled filtering excludes
drafts. The default page size is ten, maximum twenty; JSON size can reduce a page
further. Follow `next_after` with the same filters when more records are needed.
Full local records and the existing confirmation commands are preserved.

Bluetooth output uses a bounded same-stream startup buffer, configured by
`[speech_output].bluetooth_lead_in_seconds` (default 0.5, range 0 through 2 seconds).
Every original audio sample is retained; duration and size limits include the
buffer. Physical cold/warm listening acceptance remains required, especially for
speakers that suppress silence. A playback success is not proof of audibility.

These full sources are updated once at the implementation handoff. Wiki ingestion
and semantic review are deliberately skipped at the owner's request; the curated
wiki and document map may still describe the earlier checkpoint.

## Raspberry Pi OS Lite correction — 9 September 2026

The default OS is **Raspberry Pi OS Lite (64-bit), without a graphical desktop**.
Use SSH (a remote terminal) or a local keyboard. The previous Phase 3 walkthrough
incorrectly depended on desktop audio menus. This revision replaces that assumption
with explicit CLI (command-line interface) setup. No runtime code, OS settings or
hardware were changed by this documentation correction. Wiki ingestion/review
remains deferred; this is a complete new manual source, not a rewritten original.

### Deployment contract for local audio

Piper installation and Bluetooth pairing are distinct prerequisites. On Lite,
install `bluez`, `pipewire`, `pipewire-bin`, `wireplumber`,
`libspa-0.2-bluetooth` and `dbus-user-session` with the distribution package manager.
The [ordered installation commands](InstallationGuide.md#pair-and-select-the-bluetooth-speaker)
include preview, actual installation, account checks and expected results.
Do not install `pipewire-pulse` or replace the default ALSA route just for this
native `pw-play` path. The optional engine remains in its separate pinned environment.

PipeWire and WirePlumber run as the same **normal user** that owns the Agent.
Headless operation needs the correct user runtime directory and a user manager
that survives logout. The guide explicitly enables lingering (user services at
boot and after logout). Bluetooth seat policy is version-sensitive: WirePlumber
0.5 uses `monitor.bluez.seat-monitoring = disabled` in a `.conf` fragment;
0.4 uses `bluez_monitor.properties["with-logind"] = false` in a Lua fragment.
Configure only the actual installed version, for the robot account, not globally
for every user. This changes that account's audio ownership policy; it is an
operator setup action, never a runtime auto-repair.

The repository's existing system-service template supplies `User=` and hardware
groups, but not `XDG_RUNTIME_DIR`. The guide's optional `20-local-audio.conf`
drop-in adds the matching `/run/user/UID` environment and `user@UID.service`
startup dependency. It preserves the main unit and its security restrictions.
`DBUS_SESSION_BUS_ADDRESS` points at that same user's bus. Manual Agent startup
inherits these values from the shell instead. Do not add a second robot service,
run the Agent as root, or grant model tools permission to rewrite OS policy.

Read-only terminal checks, run as the Agent user:

```bash
id -un
id -u
wireplumber --version
loginctl show-user "$(id -un)" -p Linger
systemctl --user is-active pipewire.service wireplumber.service
systemctl show ninjarobot-agent.service -p User -p DropInPaths
wpctl status
```

Expected: matching user ownership, active audio services and an available speaker.
Then query `/speech outputs` and `/speech status` from interactive Agent chat:
those execute in the actual Agent environment. A successful SSH `pw-dump` alone
does not validate an installed system service. No audio is played by these queries.
The [configuration/start commands](InstallationGuide.md#configure-spoken-output)
include a private backup, strict configuration validation, the service override,
safe startup and a two-terminal Stop Speech test.

Bluetooth MAC addresses identify pairing targets. Stable PipeWire `node.name`
values identify persisted speech routes. Transient numeric sink/device/profile
IDs are only for `wpctl`/`pw-cli` diagnostics and must not be stored as `output_node`.
Pairing/trust does not guarantee reconnect after boot; the guide supplies an
explicit `bluetoothctl connect` and requires new requests after interrupted speech.
Actual speaker audibility, latency and post-logout/boot behavior remain manual tests.


## Phase 3 checkpoint — 9 September 2026

Spoken replies and coordinated output are implemented and software-tested.
The earlier Phase 3 checkpoint paused before Phase 4; the owner subsequently approved Phase 5 first. The owner
reports completing the Phase 2 manual tests and wiki maintenance; this is an
owner report, not a physical test performed by the coding agent.

The Phase 3 software gate passes 772 tests, lint, formatting, type checks,
compilation, JavaScript syntax and both driver verifiers. No managed driver
changed: 222 files across six drivers retain the baseline plus 56 authorized
repairs. Face cleanup was approved and implemented previously; the separate
Traditional Chinese font proposal and monetary-cap decision remain pending.

Use the [Phase 3 walkthrough](../../../../../docs/validation/refinement_phase3_walkthrough_260909.md)
for setup, expected results, privacy, safety and rollback. This source version
supersedes the checkpoint wording below. It is prepared for later wiki ingestion;
the owner asked to skip ingestion and review workflows during this task.
The existing hardware ownership boundary remains intact; IDE-owned OS audio is
an optional output, not a new Agent hardware-access path.

### Spoken-output architecture and compatibility

`ninjarobot_pi5_agent/speech.py` owns bounded text cleanup, local Piper synthesis,
a maximum of four active/queued jobs, and runtime on/off/language controls. Each
utterance uses a private temporary directory; subprocess completion and cleanup
precede deletion. Simulation generates synthetic PCM (uncompressed audio samples)
without invoking Piper or opening audio devices. The root Python dependencies and
six managed device libraries are unchanged; optional Piper dependencies use a
separate pinned requirements file and environment.

`ninjarobot_pi5_ide/audio_output.py` owns selected-node PipeWire playback,
validated WAV (an audio file format), microphone reservations and presentation.
`audio_process.py` bounds subprocess time and output, uses no shell, and terminates
its process group during cancellation. An output generation number invalidates
stale synthesis after safety or explicit device work. The existing RobotAssembly
speaking face is scoped to playback; foreground behavior, capture and safety win.
Buzzer fallback uses the existing reviewed expression compiler, with no new wheel
commands or behavior assets. This is minimal H02/B01 coordination, not lip sync
or a new timeline editor.

VoiceInputController.pause(for_output=True) refuses active capture, rolls back
failed reservations, and leaves persisted enablement untouched. MicrophoneDevice
coordinates manual access versus output. Stop Speech cancels active and queued
speech independently of the text task; web speech controls bypass the connection's
normal operation lock. Normal model replies are spoken only after text completion;
local management commands remain text-only. Failure retains the written answer.

Task notification adds `speech` and `notification_language` (`en`/`zh`, default
`en`) to the existing serialized record. Older records load without migration;
new speech records are not promised readable by older binaries. Reviewed speech
failure permits the existing display/buzzer fallback, but explicit cancellation
does not play fallback or replay later. No monetary spending cap was added.
Follow the walkthrough for the exact configuration and operator acceptance tests.

### Local tasks and memory architecture

The Agent's `task_models.py`, `task_service.py`, `task_controls.py` and
`task_tools.py` extend the existing runtime rather than creating a second robot
controller. Additive database migrations 4 and 5 store local reminders and request
records in the existing private conversation database. SQLite (the local database
engine) transactions claim each due reminder before notification. Startup marks
interrupted running work uncertain and never silently replays an unknown effect.
The existing exclusive Agent service owner must start the task worker.

A model can list scoped tasks and propose a reminder draft through
`tasks.list` and `tasks.reminder.preview`. Only direct user controls confirm its
exact time, repeat rule and effect. Confirmed notifications use deterministic
Agent policy and existing IDE expression execution; the Agent never imports a
hardware driver. Silent reminders simply save their delivery result in the task
inbox. Physical reminders use display text then a short buzzer tone, never motion.
Queued reminders need the running Pi/service, not a cloud model.

Requests save a bounded public step record and tool evidence, not private model
reasoning. Completion of response processing is separate from verification of an
external goal. Existing recovery retries only known-safe, definitely unexecuted
idempotent actions (actions safe to repeat). Retries consume the same request tool
budget. Model calls, input size, requested output tokens and time are bounded;
there is no currency-denominated spending cap or provider billing guarantee.
General tasks are not resumed autonomously after a restart.

`memory_controls.py` exposes direct review, confirmation, editing and forgetting
of preferences. Source/confidence/reason/confirmation metadata is visible.
Confirmed structured preferences survive contradictory inference; new conflicting
values become unconfirmed suggestions. Forgetting also removes the corresponding
effective structured preference. Technical execution outcomes cannot be edited
into successes. Existing profile scope and retention remain; task delivery pauses
during profile deletion/reset so callbacks cannot recreate deleted records.

### Earlier refinement foundations included in this checkpoint

Trusted stop commands have an independent dispatch lane. Integrated raw servo
moves use IDE safety checks, bounded ramps and final output-off cleanup. All
retained real-device builders use IDE hardware ownership. Disabled devices skip
driver initialization and recovery; configuration rejects conflicting enabled
pin assignments. Python cancellation cannot forcibly terminate a blocked native
driver call, and software tests do not prove physical stopping time.

Capability health includes status, reason, dependencies, recovery advice and
execution-block hints; the old aggregate fields remain. Optional guided checks
reuse read-only environment diagnosis. Lifecycle logs carry fixed phase/reason
values and opaque correlation identifiers, not conversation contents. Browser
zoom, visible focus and movement key release are supported; real browser and
assistive-technology testing remains outstanding.

MCP discovery has bounded pages/catalogs, schema checks, explicit read-only and
retry-safe allowlists, stale-catalog retirement and a minimal subprocess
environment. External output remains untrusted. Backup uses SQLite snapshots,
verified archive entries and rollback-aware staged restore; active owners and
unresolved restore journals block unsafe restoration. A backup is not a globally
atomic snapshot of all independently written files; stop writers for consistency.

### Current validation gate

Run the root AGENTS.md gate with `uv run --frozen --no-sync` in the existing
hardware environment. Root tests require separate explicit `--run-hardware` and
`--run-provider-live` opt-ins; never add them to routine automated checks. Run each
managed driver's suite in its own process. Do not change the immutable baseline
or record an authorization that the owner has not given.

The latest owner instruction consolidates documentation and wiki ingestion once
after Phase 2 code implementation, followed by a pause. The old F02-only wiki
proposal is stale and must not be applied. Wiki publication still follows the
reviewable semantic-plan procedure; AI review is not human verification.

This guide is the developer reference for NinjaRobotPi5. Historical phase
decisions remain in the
[implementation plan](../../../../../docs/project-history/NinjaRobotPi5V4_ImplementationPlan.md),
while current contribution guardrails are defined in [AGENTS.md](../../../../../AGENTS.md).

---

## Architecture overview

### The Three-Layer Boundary Model

NinjaRobotPi5 enforces a strict, one-directional dependency boundary:

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 3 — ninjarobot_pi5_agent                                  │
│                                                                  │
│  • User interaction: conversational CLI, HTTPS web controller    │
│  • AI providers: Ollama, OpenAI, Gemini, Anthropic               │
│  • Extension: MCP tool protocol, Agent Skills                    │
│  • Policy, prompt composition, session and transcript management │
│                                                                  │
│  ✗ Never imports any pi5* package directly                       │
│  ✗ Never opens GPIO, I2C, SPI, camera, or audio                  │
│  ✓ Calls hardware only through IDE capability contracts          │
├──────────────────────────────────────────────────────────────────┤
│  Layer 2 — ninjarobot_pi5_ide                                    │
│                                                                  │
│  • Capability registry, resource scheduler, action ledger        │
│  • Behavior system: face renderer, stages, safety engine         │
│  • Configuration import from standalone pi5* JSON files          │
│  • Hardware ownership lock (OS file lock)                        │
│                                                                  │
│  ✓ One lazy driver import per adapter module                     │
│  ✗ Never exposes raw driver objects outside the IDE              │
├──────────────────────────────────────────────────────────────────┤
│  Layer 1 — Managed pi5* Driver Libraries                         │
│                                                                  │
│  pi5servo  pi5disp  pi5buzzer  pi5vl53l0x  pi5camera  pi5mic    │
│                                                                  │
│  • Each library is an independently testable project             │
│  • Own pyproject.toml, uv.lock, README, and test suite           │
│  • Standalone CLI tools for hardware setup and calibration        │
└──────────────────────────────────────────────────────────────────┘
```

### Why This Boundary Exists

The boundary has three concrete safety consequences:

1. **The AI model cannot reach hardware.** The agent may propose a robot action; the IDE decides whether to execute it. The IDE may refuse based on safety state, calibration, arming, or resource availability — regardless of what the model says.

2. **Hardware has exactly one owner.** An OS file lock (`~/.local/state/ninjarobot_pi5/hardware-owner.lock`) prevents a second agent or IDE process from opening GPIO, I2C, SPI, PWM, camera, or audio while a first process owns them. Driver failure, crash, or process exit releases the lock automatically.

3. **Cloud providers are translation-only.** OpenAI, Gemini, and Anthropic adapters convert the same provider-neutral `ModelRequest` into each provider's API format and return a `ModelTurn`. They never execute a tool, access a driver, or bypass policy.

---

## Repository layout

```text
NinjaRobotPi5/
├── ninjarobot_pi5_ide/
│   ├── src/ninjarobot_pi5_ide/
│   │   ├── adapters.py         Shared adapter protocols and deterministic fakes
│   │   ├── behavior_assets.py  Bundled and private behavior catalog
│   │   ├── behavior_models.py  Strict immutable stage/operation definitions
│   │   ├── behavior_runtime.py Ordered-stage, concurrent-operation executor
│   │   ├── assets/            Checksummed, licensed wake-model assets
│   │   ├── camera.py           Privacy-bounded camera adapter
│   │   ├── cli.py              ninjarobot-ide-tool entry point
│   │   ├── config.py           V4 configuration schema (TOML)
│   │   ├── config_import.py    Preview-first import from standalone pi5* JSON files
│   │   ├── models.py           Shared data models (capabilities, results, errors)
│   │   ├── face_renderer.py    Procedural Pillow face animations
│   │   ├── interactive_tool.py Blessed-style direct-control menus
│   │   ├── robot.py            Shared RobotAssembly (all devices in one object)
│   │   ├── runtime_control.py  Owner-private active-process registration
│   │   ├── safety.py           Motion guard, watchdog, stop levels, recovery
│   │   └── ledger.py           Durable ActionLedger
│   └── pyproject.toml
│
├── ninjarobot_pi5_agent/
│   ├── src/ninjarobot_pi5_agent/
│   │   ├── providers.py        Provider-neutral LLMProvider protocol
│   │   ├── ollama.py           Ollama provider adapter
│   │   ├── openai_provider.py  OpenAI Responses API adapter
│   │   ├── gemini_provider.py  Gemini API adapter
│   │   ├── anthropic_provider.py Anthropic Messages API adapter
│   │   ├── agent_loop.py       Main AI turn loop, tool routing, camera-intent boundary
│   │   ├── benchmark.py        Ollama performance and safety benchmark
│   │   ├── runtime.py          Shared runtime, session, consent, and tool coordination
│   │   ├── cli.py              ninjarobot-agent entry point
│   │   ├── provider_auth.py    API-key-only cloud provider configuration helpers
│   │   ├── ipc.py              Owner-only Unix-domain socket protocol and server
│   │   ├── mcp_config.py       MCP server catalog loader and validator
│   │   ├── model_selection.py  Provider-neutral model selection and hot-switching
│   │   ├── persistence.py      Bounded local conversation persistence
│   │   ├── policy.py           Tool call policy engine
│   │   ├── prompts.py          PromptComposer — ordered system prompt builder
│   │   ├── robot_control_mcp.py Trusted in-process robot-control MCP façade
│   │   ├── release_foundations.py Phase 8 dependency and lifecycle status
│   │   ├── voice_service.py     Always-on wake/listen/dispatch coordinator
│   │   ├── remote_access.py     ngrok lifecycle and bounded recovery
│   │   ├── pairing.py           One-use local/remote browser pairing
│   │   ├── onboarding.py        QR-to-Greeting exactly-once coordinator
│   │   ├── shutdown.py          Nonce-confirmed orderly power-off
│   │   ├── deployment.py        Explicit systemd install/backup lifecycle
│   │   ├── secrets.py          SecretStore — owner-only, atomic, redacted
│   │   ├── skills.py           Skill validation, confinement, and registry
│   │   └── web_app.py          FastAPI HTTPS controller and WebSocket lease
│   └── pyproject.toml
│
├── pi5buzzer/                  Standalone buzzer library (independent project)
├── pi5camera/                  Standalone camera library (independent project)
├── pi5disp/                    Standalone display library (independent project)
├── pi5mic/                     Standalone microphone library (independent project)
├── pi5servo/                   Standalone servo library (independent project)
├── pi5vl53l0x/                 Standalone distance-sensor library (independent project)
│
├── config/
│   └── ninjarobot_pi5.toml.example   Authoritative V4 configuration example
│
├── docs/
│   ├── architecture/           Architecture and driver-containment records
│   ├── adr/                    Architecture Decision Records
│   ├── hardware/               Hardware mapping, wiring, and electrical records
│   └── validation/             Phase validation checklists and authorized driver changes
│
├── scripts/
│   ├── bootstrap-rpi-camera-workspace.sh   Camera bridge setup
│   ├── configure_rpi_boot.py               Idempotent PWM boot configuration
│   ├── install-rpi.sh                      Raspberry Pi environment installer
│   ├── install-versions.env                Reviewed external tool versions
│   ├── verify_immutable_drivers.py         Driver SHA-256 checksum verification
│   └── verify_workspace_driver_sources.py  Editable-source path verification
│
├── tests/                      Root integration and governance tests
├── pyproject.toml              Root project — orchestrates all packages
├── uv.lock                     Locked dependency graph
└── NinjaClawBot/               ← Ignored historical reference; never imported by V4
```

---

## Development environment setup

### Prerequisites

| Tool | Version | How to install |
|---|---|---|
| Python | 3.11 | `uv python install 3.11` |
| `uv` | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Git | Any recent | `sudo apt install git` |

### First-Time Setup (Simulation — No Hardware)

```bash
git clone https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git
cd NinjaRobotPi5

# Install all Python dependencies (hardware packages excluded)
uv sync --frozen
source .venv/bin/activate

# Create and inspect a simulation-safe private configuration
ninjarobot-ide-tool config import --apply
ninjarobot-ide-tool hardware status
ninjarobot-ide-tool behavior simulate greeting
```

`behavior simulate` never opens GPIO, I2C, SPI, camera, or audio. The result
must include `"simulated": true`.

### First-Time Setup (With Hardware — Raspberry Pi Only)

```bash
# Preview and run the maintained OS/project installer
./install.sh --dry-run
./install.sh
```

The installer is the supported beginner path. It installs the reviewed OS
packages, `uv`, Ollama, and pinned whisper.cpp; manages the GPIO12/GPIO13 PWM
boot block; creates private configuration directories; installs locked hardware
dependencies; and validates the camera bridge and managed-driver provenance.
It intentionally does not choose an Ollama model, initialize hardware, deploy
systemd startup, or start the Agent. See `InstallationGuide.md` for the
operator workflow.

### Running the Test Suite

```bash
uv run --frozen pytest -q
```

Hardware tests are excluded from the default run. They are in a `hardware` pytest marker group and require an explicit include flag on the Raspberry Pi.

---

## Root quality gate

Run this full gate before merging any change. Every check must pass.

```bash
# 1. Driver provenance
uv run --frozen python scripts/verify_immutable_drivers.py

# 2. Syntax
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests

# 3. Lint
uv run --frozen ruff check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests

# 4. Format
uv run --frozen ruff format --check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests

# 5. Static type checking
uv run --frozen mypy \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src

# 6. Tests
uv run --frozen pytest -q

# 7. No trailing whitespace or merge conflicts
git diff --check
```

Strict mypy typing is mandatory for `ninjarobot_pi5_ide` and `ninjarobot_pi5_agent`. It does not apply to the independently maintained `pi5*` libraries.

---

## Development workflow

### Release licensing and binary assets

The repository root [LICENSE](../../../../../LICENSE) is the project MIT license.
[THIRD_PARTY_NOTICES.md](../../../../../THIRD_PARTY_NOTICES.md) records dependencies and
services whose terms remain separate. Adding a dependency requires checking
its current upstream license and updating the notice before release.

Release-owned binary/model assets live inside the package that consumes them,
not inside a managed driver. Each asset requires:

1. an exact path, byte size, SHA-256 checksum, source/provenance, license, and
   owner authorization in `docs/validation`;
2. a package-build test proving that the wheel contains it;
3. a checksum test that fails if either the source or packaged copy changes;
4. a new review and Raspberry Pi result before replacement.

The approved Phase 8 wake-model record is
`docs/validation/phase-8-wake-model.json`. Unattended service boot must never
download or replace this model or its inference assets.

1. **Read** the relevant historical phase in
   `docs/project-history/NinjaRobotPi5V4_ImplementationPlan.md` and any related
   Architecture Decision Records (ADRs) in `docs/adr/`.
2. **Review** the affected code using Serena or your preferred editor.
3. **Present** your plan and obtain explicit approval before writing code.
4. **Implement** only the V4-owned files or the approved driver repair.
5. **Run** focused tests, then the complete root quality gate.
6. **Verify** driver provenance and authorized repair hashes.
7. **Update** `README.md`, this guide, and any relevant documentation.
8. **Prepare** a Raspberry Pi checklist for hardware-facing changes.
9. **Stop** for review before starting the next phase.

---

## Managed driver policy

### What "Managed Driver" Means

The six `pi5*` directories are **managed copies** of historical standalone libraries. They exist in this repository so V4 can:

- Lock their exact source content with SHA-256 checksums
- Run their tests in isolation with their own lockfiles
- Ship them as editable path dependencies — never as copied wheels

They are **not** V4 sub-packages. They remain independent projects with their own `pyproject.toml`, lockfiles, and test suites.

Because the drivers are editable path dependencies, a pulled or locally authorized repair is immediately visible without any stale wheel hiding an old copy.

### Prohibited Operations

| Prohibited action | Why |
|---|---|
| Importing a `pi5*` package in `ninjarobot_pi5_agent` | Breaks the containment boundary; the agent reaches hardware only through IDE capability contracts |
| Exposing a raw `pi5*` driver object outside `ninjarobot_pi5_ide` | Bypasses the IDE's ownership, safety, and serialization boundary; the IDE may use controlled lazy driver imports internally |
| Editing a `pi5*` source file without recording an authorization | The SHA-256 baseline check will fail the quality gate |
| Adding a `pi5*` directory as a `[tool.uv.sources]` workspace member | Drivers are editable path dependencies, not workspace members |
| Running `uv sync` inside a `pi5*` folder for normal NinjaRobotPi5 use | Use the root environment; package-local environments are for standalone driver validation only |
| Importing or running `NinjaClawBot/` code | That directory is strictly read-only historical reference |

### How to Propose a Driver Change

1. Reproduce the failure and document the root cause.
2. File an issue describing the defect and proposed fix.
3. Get maintainer approval **before writing code**.
4. Apply the minimal fix inside the affected `pi5*` directory.
5. Run the driver's own isolated test suite (see [Driver package validation commands](#driver-package-validation-commands)).
6. Record the changed file with the authorized hash tool:

```bash
uv run python scripts/verify_immutable_drivers.py \
  --record-authorized pi5example/path/to/file.py \
  --reason "Concise root cause and validated repair summary"

uv run python scripts/verify_immutable_drivers.py
```

7. Run the root governance test:

```bash
uv run --frozen pytest tests/test_repository_governance.py -q
```

8. Submit the PR with the driver fix, the updated authorization manifest, and the test run output.

> [!CAUTION]
> Never use `--record-authorized` to silence a hash mismatch caused by an accidental edit. The original hashes in `immutable_driver_baseline.json` are permanent and must never be regenerated after repairs. Only `authorized_driver_changes.json` records the approved repaired state.

---

## Configuration system

### Schema Overview

The integrated robot configuration lives in `~/.config/ninjarobot_pi5/config.toml`. The source schema is in `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config.py`.

The example at `config/ninjarobot_pi5.toml.example` is the authoritative reference for the current hardware profile:

- GPIO12/GPIO13 servos (MG90D continuous-rotation, motion disabled by default)
- GPIO27 buzzer
- ST7789V display on DC4/RST5/BL6, rotation 90°, brightness 75%
- Fixed-focus OV5647 camera at 1280×720, retention disabled by default
- USB PnP microphone at 16 kHz (actual rate may fall back to 44.1 kHz)
- Phase 7 memory retention, retrieval bounds, and local face-data directory
- Phase 8 opt-in voice, remote-access, QR onboarding, and deployment controls

Existing Phase 7 configuration files remain valid. Missing `[voice_input]`,
`[remote_access]`, `[onboarding]`, and `[deployment]` sections receive strict,
disabled defaults. The serializer now round-trips all memory and Phase 8
sections, so a configuration import no longer omits persistent-memory settings.

Phase 8 bounds deliberately fix the ONNX runtime, local HTTPS upstream,
owner-private ngrok config path, QR quiet zone/error correction, systemd unit,
and power-off helper. Arbitrary executable paths, tunnel upstreams, inference
formats, or command durations above 15 seconds are rejected.

The `[memory]` section supplies first-run defaults only. After the database is
initialized, confirmed changes made through `ninjarobot-agent memory
set-retention` persist across restart and are not overwritten by the TOML file.

Validate any configuration file:

```bash
ninjarobot-ide-tool --config config/ninjarobot_pi5.toml.example hardware status
```

### How Configuration Flows Between Layers

```
Standalone pi5* JSON files  →  IDE importer (preview-first, read-only)
        ↓                               ↓
~/.config/pi5*/             →  ~/.config/ninjarobot_pi5/config.toml
                                        ↓
                            ninjarobot_pi5_ide reads TOML at startup
                                        ↓
                            IDE adapters use settings to initialize drivers
```

The import is **one-way**. The standalone JSON files never change when you run `config import`. The integrated TOML never changes when you use a standalone tool.

### Canonical Standalone Configuration Paths

| Library | Canonical config file |
|---|---|
| `pi5buzzer` | `~/.config/pi5buzzer/buzzer.json` |
| `pi5camera` | `~/.config/pi5camera/camera.json` |
| `pi5disp` | `~/.config/pi5disp/display.json` |
| `pi5mic` | `~/.config/pi5mic/mic.json` |
| `pi5servo` | `~/.config/pi5servo/servo.json` |
| `pi5vl53l0x` | `~/.config/pi5vl53l0x/vl53l0x.json` |

All six managed tools select these XDG paths by default. An explicit path is
needed only for tests, migration, or a deliberately separate profile. This
keeps fresh-clone calibration state out of the Git worktree.

### IDE Configuration Import and Synchronization

First import (new file):

```bash
ninjarobot-ide-tool config discover
ninjarobot-ide-tool config import            # preview — nothing written
ninjarobot-ide-tool config import --apply    # write the private file
```

After changing a standalone configuration, synchronize with `--overwrite`:

```bash
ninjarobot-ide-tool config import                    # preview first
ninjarobot-ide-tool config import --apply --overwrite
ninjarobot-ide-tool hardware status
```

The preview returns `"applied": false` by design — it is not a failure.

---

## Safety and security architecture

### Hardware Ownership Lock

`RobotAssembly` claims `~/.local/state/ninjarobot_pi5/hardware-owner.lock` with a non-blocking OS file lock at startup. A second agent or real IDE process receives a clear ownership error before opening any device. Process exit releases the lock even after a crash. Standalone `pi5*` tools do not use this lock — stop the agent and IDE before running a standalone hardware tool.

### Policy Engine and Tool Trust

Every tool call passes through `PolicyEngine.evaluate()` before reaching the IDE or any external server. The policy engine checks:

- Tool name against the allowlist
- Session arming state (for motion tools)
- Privacy confirmation (for camera and microphone)
- Input against the tool's JSON Schema

The model's output is an **untrusted proposal**. The policy engine makes the final decision. External MCP tool results are also untrusted — they can never elevate permissions or bypass IDE safety.

### Motion Arming and Session Scope

`MotionArmManager` holds session-lived consent rather than a wall-clock timeout. This prevents a valid arm from expiring while a small local model is reasoning.

Motion authorization is revoked by:
- Explicit `/disarm` command
- Emergency Stop
- Controller browser disconnection
- Model replacement
- Service shutdown

Runtime disarm also cancels any in-flight motion tokens and requests `robot.servo.stop` — it does not merely block the next tool call.

### Safety Stop Levels

**Normal obstacle interruption** — stops the complete current behavior without
creating a persistent safety latch:

- Trigger: three consecutive valid front readings at or below 50 mm during
  `move_forward`, `turn_left`, or `turn_right`
- Result: stop the servos, cancel the behavior's concurrent and later stages,
  show a bounded silent scary face, report the cause and next step, then return
  to Idle
- Recovery: no resume action; clear the path and issue a new command

**Level 1** — stops servo movement and blocks another movement after a genuine
motion-control fault:

- Triggers: Raspberry Pi undervoltage, software watchdog timeout, or a servo
  driver interruption
- Recovery: `ninjarobot-ide-tool motion resume --confirm`

**Level 2 (Emergency Stop)** — stops servos and ranging, suspends the camera and microphone backends, silences the buzzer, and displays a red octagonal Emergency Stop sign. A confirmed resume performs health checks and reconstructs/restarts modules as needed.

- Triggers: explicit emergency-stop behavior or an unrecoverable hardware driver
  failure. An operator `behavior stop` performs the same immediate cleanup
  without writing a persistent driver-failure latch.
- Recovery: `ninjarobot-ide-tool system resume --confirm` (or `/resume` in chat)
- Recovery checks every configured module by health probe — refuses to clear the latch if any probe fails

Every persistent stop returns and logs its stable reason, plain-language cause,
and recovery instruction. NinjaRobotAgent appends that guidance to chat output
deterministically, even if the selected model omits it.

Invalid generated behavior arguments, oversized display text, policy rejections, and configuration mistakes return ordinary action errors and **do not** create a Level 2 latch.

### Secret Storage

`SecretStore` stores API keys and sensitive values in `~/.config/ninjarobot_pi5/secrets.env`:

- Created with mode `0600` (owner-read/write only)
- Written atomically using a unique `tempfile`, `fsync`, and `rename`
- Rejects symbolic-link files/directories and non-regular targets
- Reports presence of a key without revealing its value
- Redacts known file-backed or resolved environment values from nested error diagnostics
- `provider logout` removes only the selected provider's saved key

Phase 8 reserves `NGROK_AUTHTOKEN`, `NINJAROBOT_PAIRING_SECRET`,
`NINJAROBOT_SESSION_SECRET`, and `NINJAROBOT_REMOTE_HEADER_SECRET` in this
same store. The TOML contains only these environment-variable names. It never
contains a token, cookie, transport marker, or signing key.

### Phase 8 Optional Dependencies and Status

The normal `uv sync --frozen` software-only environment remains lightweight,
but includes `qrcode[pil]==8.2` because `ninjarobot_pi5_ide.qr_display` is in
the IDE's unconditional import graph. The historical `display-qr` extra remains
as an empty compatibility marker for existing installers; it is no longer the
owner of the runtime requirement. This prevents a default `uv run
ninjarobot-agent` synchronization from removing qrcode and breaking the CLI
before argument parsing.

On Raspberry Pi, the hardware extra resolves the device, voice, and remote
runtime dependencies:

```bash
uv sync --frozen --extra hardware
```

Pinned release packages are `qrcode[pil]==8.2` in the base IDE, plus
`openwakeword==0.6.0`, `onnxruntime==1.27.0`, and `pyngrok==8.1.2` through the
hardware-selected voice/remote extras.
ONNX Runtime 1.27.0 publishes a CPython 3.11 manylinux aarch64 wheel; the
target-Pi import/model-load check remains a mandatory device validation.

Developers should distinguish `uv sync` from `uv run`: `uv run` first
reconciles the selected project extras unless `--no-sync` is used. Therefore a
real-Pi one-shot command must use `uv run --extra hardware ...`, or preferably
run plain entry points after `source .venv/bin/activate` as documented for
normal users.

`ninjarobot-agent status` now includes `release.voice`,
`release.remote_access`, `release.pairing`, `release.onboarding`, and
`release.shutdown`. Each reports a stable `enabled`, `state`, safe detail code,
and dependency-presence map. Status checks never start a microphone, tunnel,
display action, or shutdown operation. New installations report `disabled`
until an operator explicitly enables the relevant feature.

### IDE-owned always-on voice

`ninjarobot_pi5_ide.voice_input.VoiceInputController` is the only always-on
listener. It owns one bounded raw PCM stream, resamples a USB microphone's
supported native rate to the detector's 16 kHz input, and implements the
disabled/listening/detected/recording/transcribing/dispatching/cooldown state
machine. `MicrophoneDevice.manual_access()` pauses and releases that stream for
manual capture or transcription, then restores it in a `finally` path.

`start()` is readiness-gated: it returns only after the stream publishes
`listening`, or raises a stable failure after the configured bounded startup
timeout. Raw stream construction runs outside the asyncio loop, partial
PortAudio ownership is published early enough for cancellation cleanup, and an
explicit enable is persisted only after readiness. A failed enable rolls the
switch back to disabled.

The IDE loads only the managed pi5mic device and openWakeWord detector modules;
it never imports the historical pi5mic/OpenClaw voice loop. The packaged custom
model plus explicit `melspectrogram.onnx`, `embedding_model.onnx`, and
`silero_vad.onnx` paths make detector startup offline and deterministic. Their
hashes and provenance are in `docs/validation/phase-8-wake-model.json` and
`docs/validation/phase-8-openwakeword-assets.json`.

The agent bridge sends each finalized transcript exactly once through
`AgentRuntime.chat()` using the independent `voice-owner` session. This keeps
terminal and browser user selection unchanged while reusing the default/owner
profile, persistent memory, policy engine, tools, presentation, and events.
The listener stores no continuous audio and deletes the temporary command WAV
after local transcription. Phase 8.2 intentionally has no TTS.

Voice enablement is an explicit persisted operator setting:

```text
/voice input on
/voice input status
/voice input off
```

The terminal `/arm` and web **Arm AI motion** paths grant both the issuing chat
and voice session. Voice disablement, model replacement, emergency/system stop,
service shutdown, and loss of the browser lease that issued the grant revoke
voice motion. A voice request is never retried after an uncertain tool result.

The web interface never accepts provider secrets. The terminal uses hidden, double-entry prompts.

### Remote access and pairing boundary

`ninjarobot_pi5_agent.remote_access.RemoteAccessService` owns one optional
pyngrok endpoint and process. Online activation starts `WebServerManager`'s
shared HTTPS backend without claiming remote readiness, verifies the
already-installed ngrok executable, loads the authtoken
from `SecretStore`, and verifies upstream TLS against the NinjaRobot local CA.
The private ngrok config is mode `0600`; the token is written only for process
startup and immediately removed again so it is not left in the process command
line or ordinary configuration. Service boot never invokes the installer.

The endpoint removes any client-supplied `x-ninjarobot-remote` header and adds
a process-owned random marker using ngrok Traffic Policy `remove-headers` then
`add-headers` actions. `PairingSessionManager` requires that marker,
the exact active HTTPS Host, and exact browser Origin. This prevents a remote
client from spoofing a private-LAN Host header to bypass pairing. Unknown public
hosts receive `421`; unauthenticated remote assets/control receive `401`.

The QR/operator URL uses `#pair=<random>` so the credential is not sent in the
initial HTTP request, server access log, or Referer. A tiny no-store bootstrap
page removes the fragment and exchanges it once. The resulting cookie is
Secure, HttpOnly, SameSite=Strict, path-scoped, expiry-bounded, and tracked by a
keyed hash. Rotation, tunnel replacement/loss, explicit deactivation, or
service shutdown invalidates pending tokens and completed sessions. The normal
controller lease remains exclusive after pairing.

The supervisor validates an HTTPS public origin, changes the access gate to
remote-only only after that origin is ready, uses exponential capped
backoff for transient failures, stops retrying permanent configuration,
credential, executable, and account failures, publishes only stable failure
categories, and keeps local agent/web/
hardware paths alive on executable, token, account, network, configuration, or
tunnel failure. A healthy tunnel waits for a paired WebSocket indefinitely;
lack of a browser is not treated as failure. The pyngrok design follows the
[documented explicit config/process API](https://pyngrok.readthedocs.io/en/stable/)
and ngrok's still-supported [v2 tunnel Traffic Policy fields](https://ngrok.com/docs/agent/config/v2/).
The installed executable is ngrok v3; pyngrok uses its v2 tunnel API here
because that schema exposes the required custom upstream-CA verification. The
removed direct header-module fields are not used.

Local-owner commands are:

```bash
ninjarobot-agent remote configure
ninjarobot-agent remote activate
ninjarobot-agent remote status
ninjarobot-agent remote pairing-url
ninjarobot-agent remote rotate-pairing
ninjarobot-agent remote deactivate
ninjarobot-agent remote remove-credentials --confirm
```

`remove-credentials` preserves the installed ngrok executable but deletes the
three pairing/session/transport secrets, the authtoken, and private ngrok
config. It never deletes profiles, memories, face data, behavior assets, or the
main robot configuration.

The Interactive Tool deliberately separates one-time `remote configure` from
`remote activate`. Configure validates/atomically installs ngrok and privately
saves the token without starting a tunnel. When no Agent is running, activate
validates the token, executable, and required pairing secrets and persists the
enabled state for the next start. The Agent service remains the only tunnel
process owner. Manual deactivation stops remote ownership and does not silently
start a new Local Web session.

`WebAccessState` is shared by the ASGI gate and `WebServerManager`. Its modes
are `none`, `local`, `remote`, and `local_fallback`. In remote mode, direct local
HTTP and WebSocket access is rejected and public Local Web status intentionally
returns `ready=false`, `running=false`, and `url=null`. Configured intent and a
connecting supervisor do not enter this mode. Startup keeps a local-capable
backend until `remote_ready`; `remote_error` or `tunnel_lost` restores
`local_fallback`, and recovery atomically enters `remote` before publishing a
new remote QR. Explicit deactivation clears remote/fallback ownership, so the
user still starts an ordinary Local Web session deliberately.

### QR onboarding and startup liveliness

When onboarding is explicitly enabled, remote access is enabled, or boot
deployment is enabled, service startup initializes the IDE and
HTTPS server without playing Greeting. The IDE renders a plain black-on-white
QR using `qrcode` error correction M, automatic minimum version, integer-sized
square modules, and a four-module quiet border, centered without interpolation
on the physical display. QR input is restricted to one bounded HTTPS origin
plus one URL-fragment pairing token; arbitrary images never cross the agent/IDE
boundary. This follows the Python qrcode project's
[documented `QRCode` configuration](https://github.com/lincolnloop/python-qrcode).

`service_main` computes that effective onboarding condition once and uses it
for the release-status registry, pairing gate, web startup, and coordinator.
Do not initialize any of those components from only the explicit
`[onboarding].enabled` value: persisted configurations may legitimately have
remote access enabled while that older explicit flag is false. Startup failures
after the IPC socket is bound remain inside the service cleanup boundary so the
runtime, web server, remote tunnel, ownership lock, and socket are released.

If remote access is enabled, the display shows **Connecting…** until ngrok is
ready or fails. A ready tunnel displays its remote one-use QR indefinitely and
refreshes it before token expiry. During deployed automatic startup, a real
failure selects a local mDNS QR while remote retry continues; the HTTPS backend
also remains local-capable while the initial tunnel connects. Recovery
withdraws local routes and replaces the QR before any controller connects.
With remote disabled, local QR is immediate.

During onboarding, local and remote HTTP assets and WebSockets require the
same Secure/HttpOnly paired-browser session. Health probes, crawlers, static
requests, failed leases, and unpaired browsers cannot trigger startup. The
first paired exclusive WebSocket lease or authenticated owner-only terminal
chat enters a serialized once-per-process coordinator: it clears the QR, runs
Greeting once through the IDE, then marks Idle ready. Reconnects never replay
Greeting. QR/display/Greeting failure marks
startup degraded, disarms voice and AI motion, attempts a servo stop, and
leaves a stable Error presentation rather than falsely reporting Idle.

After Greeting is complete, the deterministic `remote_show_qr` IPC operation
supports terminal `/show remote access`. It rotates only the pending one-use
token (`invalidate_sessions=False`), so paired browsers remain valid. A browser
that consumes this additional QR clears the display directly to Idle and does
not rerun startup Greeting.

### systemd deployment boundary

`ninjarobot_pi5_agent.deployment` renders the versioned service template with
the installed virtual-environment Python executable and absolute config,
secret, state, socket, TLS, model, and working paths. Boot never calls `uv` or
an interactive shell. One non-root service owns IDE hardware, web, voice, QR,
pairing, and ngrok. The unit uses required device groups, strict filesystem and
kernel hardening compatible with Pi access, private temporary storage,
journald, bounded shutdown, restart throttling, and `Restart=on-failure` so a
clean intentional stop remains stopped. It sets `LG_WD=/run/ninjarobot-agent`
and uses `RuntimeDirectory=ninjarobot-agent` with mode `0700`, giving `lgpio` a
service-owned location for `.lgd-nfy*` notification pipes without making the
repository writable. The behavior follows upstream `lgpio` work-directory and
[notification-pipe handling](https://github.com/joan2937/lg/blob/master/lgNotify.c)
plus systemd's
[`RuntimeDirectory` lifecycle](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#RuntimeDirectory=).

Installation is explicitly confirmed and disabled by default at package
installation time. The normal-user **deployment setup** transaction runs
strict robot/MCP configuration preflight, `systemd-analyze verify`, and
`visudo -cf`, installs all three privileged
artifacts, enables the unit, persists onboarding/web-power settings, and starts
the service immediately. It clears stale systemd failed/start-limit state, then
waits for `ActiveState=active` and an owner-only `startup_status` IPC response
whose `started` and `ready` fields are both exactly true. Onboarding remains
not ready while its release state is only `starting`; it becomes ready after a
QR presentation advances that state to `pairing` (or after startup has fully
completed). `running_now` and `ready` are never inferred from enablement, an
accepted start command, or IPC availability alone. A failed first start invokes
`disable --now`, so the
next boot does not retry a broken deployment. Status reports parsed active,
substate, result, restart, and exit-status fields and checks the unit/helper as
ordinary paths but verifies the protected sudoers authorization through the
exact non-interactive `sudo -n -l /usr/libexec/ninjarobot-poweroff` query; it
never traverses `/etc/sudoers.d` as the unprivileged user. The fixed root-owned helper contains only
`/usr/bin/systemctl poweroff --no-wall`; sudoers permits the service user to
execute only that argument-free helper. The web coordinator calls it as
`/usr/bin/sudo -n /usr/libexec/ninjarobot-poweroff` after resource cleanup.
No general passwordless sudo is installed.

The unit, helper, and sudoers rule use deliberately distinct temporary staging
names. The helper and sudoers destinations both end in
`ninjarobot-poweroff`; deriving both staging paths from that basename would
overwrite the helper with the sudoers line. The staged unit specifically keeps
the canonical `ninjarobot-agent.service` name: `systemd-analyze verify` derives
the unit type from the filename and rejects a generic `.install` suffix before
reading otherwise valid content. Failed deployment commands retain their exit
status and at most 500 normalized printable diagnostic characters.
`validate_poweroff_helper` now
requires the exact packaged bytes, root owner/group, regular non-symlink file,
and mode `0755`. Both deployment status and runtime preflight use this check,
while sudo authorization remains a separate exact `sudo -n -l` probe.

Pi 5 shutdown has a second, platform-level prerequisite. Deployment reads the
active bootloader config and any `/boot/.../pieeprom.upd` image separately. If
full PMIC shutdown is absent, confirmed setup calls only the official
`raspi-config nonint do_power_off_on_halt B1` operation, which schedules
`POWER_OFF_ON_HALT=1` and `WAKE_ON_GPIO=0` without replacing unrelated keys.
`FullPoweroffStatus` distinguishes active, pending-compatible, and
pending-incompatible states. Setup may start the service with a compatible
update pending, but validation remains false until a reboot applies it. The web
coordinator rechecks the active state before issuing its nonce and rejects the
request before any cleanup when the setting is absent, unreadable, or pending.

Deployment commands cover transactional setup, validate/install/upgrade,
enable/disable,
start/stop/restart, status/journal, private backup, verified overlay rollback,
and uninstall. Upgrade preserves enablement. Disable/uninstall and rollback do
not delete profiles, memory, face data, behaviors, secrets, configuration, or
unarchived newer data.

### Prompt Composition Order

`PromptComposer` assembles the system prompt in this fixed order:

1. Immutable safety rules
2. Robot identity
3. Current health, controller lease, and arming state
4. Selected Skill instructions (if any)
5. Conversation context

External text, MCP results, and Skill instructions cannot precede or replace the safety rules.

---

## IDE — core modules and responsibilities

### CapabilityRegistry

Registers one unique adapter per capability and owns startup, health, and close ordering. Prevents two adapters from registering the same capability name.

### ResourceScheduler

Bounds concurrent and waiting work. Locks shared resources in sorted order to prevent deadlock. Example: the display, SPI0, and GPIO4/GPIO5/GPIO6 are claimed together by every display operation.

### ActionLedger

Stores accepted, running, and completed actions in SQLite. Enforces idempotency: repeating the same action ID and idempotency key returns the stored result without re-executing. An action that was running at restart is recorded as unknown outcome; the caller must decide whether to retry.

### ExecutionEngine

Enforces deadlines, timeouts, cancellation, restart recovery, and normalized error codes. Returns structured failures for timeouts, queue full, cancelled, and unknown outcomes.

### DisplayDevice

Owns the single ST7789V backend and serializes every SPI frame, brightness
change, recovery, and close operation. An idempotent frame failure receives one
bounded backend reconstruction and one retry. Reconstruction closes the failed
instance, restores the remembered brightness, checks the replacement, and
writes a black probe frame before retrying. An exhausted recovery becomes an
explicit hardware failure; it never loops indefinitely. Shutdown closes the
behavior admission gate, drains the active frame thread, and only then turns
off the backlight and releases SPI/GPIO.

### BehaviorRuntime

Executes ordered stages with concurrent operations. A stage may contain one display operation, one buzzer operation (existing melody or one bounded tone), one drive operation, and one wait. Tone frequency is limited to 20–20,000 Hz, duration to 0.05–2 seconds, and volume to 1–128.

### FaceRenderer

Procedural Pillow-based face animations. All 20 expressions are independently implemented. Each renderer scales from the configured display dimensions and uses elapsed time to produce successive frames. A finite expression remains bounded; an interactive face loops until replaced or stopped.

### SafetyStateStore

Persists the safety latch in `~/.local/state/ninjarobot_pi5/safety.json`. Uses `threading.Lock` for atomic state access. Returns a full latch on any parse error — fail-closed.

### WatchdogThread

A daemon thread that calls the servo zero-pulse path directly if the main asyncio event loop stops updating within its timeout. Tested with both a frozen event loop and a legitimately slow servo ramp.

---

## Agent — framework design

### AgentIPCServer

Binds an owner-only Unix-domain socket at `~/.local/state/ninjarobot_pi5/agent.sock`. CLI processes connect to the running service; quitting a CLI terminal does not release service resources. The service owns the Ollama connection, the in-process IDE client, the tool registry, MCP sessions, SQLite transcripts, motion arms, and the optional FastAPI web server.

### ToolProvider Protocol

All tool sources — IDE capabilities, the trusted robot-control MCP façade, and external MCP servers — implement the same protocol:

```python
class ToolProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    async def start(self) -> None: ...
    async def list_tools(self) -> tuple[ToolDefinition, ...]: ...
    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult: ...
    async def health(self) -> ProviderHealth: ...
    async def close(self) -> None: ...
```

Required behaviour: deterministic lifecycle, idempotent close, collision-safe names, strict input validation, bounded time and result size, cancellation propagation, declared source and trust level.

### Trusted Robot-Control MCP Façade (`RobotControlMCPProvider`)

A fixed, in-process MCP server owned by the agent service. Unlike external MCP servers, its manifest is project source, its tools are classified from authoritative IDE descriptors, and its trust level is `TRUSTED`.

| Agent tool | IDE capability | Purpose |
|---|---|---|
| `robot.behavior.catalog` | `behavior.list` | List validated behaviors |
| `robot.behavior.preview` | `behavior.preview` | Compile to canonical IDE format without hardware |
| `robot.behavior.execute_expression` | same (no `robot.` prefix) | Run face/text/buzzer stages |
| `robot.behavior.execute_movement` | same (no `robot.` prefix) | Run motion combinations after session arming |
| `robot.behavior.stop` | `behavior.stop` | Request the existing Level 2 stop |

The façade validates each call against the IDE JSON Schema, creates an `ActionRequest`, and returns the IDE's authoritative normalized result. It does not own or close the IDE — the primary IDE provider owns that lifecycle.

### LLMProvider Protocol and Cloud Adapters

All model providers implement the same `LLMProvider` protocol. The common boundary:

```
PromptComposer + selected Skill
      |
ToolRegistry: robot.* + allowlisted mcp.*
      |
  ModelRequest
      |
selected LLMProvider adapter
      |
   ModelTurn
      |
PolicyEngine → ToolRegistry → IDE, robot MCP, or external MCP
```

Cloud adapters use documented HTTPS JSON and Server-Sent Events endpoints:

- **OpenAI**: Responses API with `store=false`, manual function calls, streamed text deltas, `GET /v1/models`
- **Gemini**: `generateContent`/`streamGenerateContent`, function declarations without callable Python functions, filtered model list. Gemini-native tool calls persist their exact call ID and opaque thought signature; when replayed, the signature is a sibling field of the `functionCall` part and the matching function response replays that exact ID. Older or non-Gemini tool traces are supplied only as bounded historical reference text after provider switching, never forged as Gemini function calls.
- **Anthropic**: Messages API, streamed content blocks and `tool_use` JSON, paginated Models API

Cloud adapters can **propose** tools but cannot **execute** them. The existing policy and registry remain the only execution path.

Gemini retries an HTTP `429` at most twice, before text is streamed and before
the agent can execute a proposed tool. It honors a bounded numeric
`Retry-After` value when supplied, otherwise using a short exponential delay.
This retry resubmits only the pending model request; it cannot replay a robot
tool. Gemini HTTP 400 responses expose only the provider error category (for
example `INVALID_ARGUMENT`), not a response body, and model failover reports
the safe failure reason for each attempted provider rather than an ambiguous
“every configured provider failed” message.

### MCP Client Configuration

The IDE provider, trusted robot-control MCP façade, and read-only memory MCP
provider are built in and load independently of this file. The Agent
Interactive Tool reports their live health and loaded tools under **MCP Tools
(Built-in and External)**. `~/.config/ninjarobot_pi5/mcp.toml` contains only
optional external servers and may validly be absent/empty. The format for a
remote (Streamable HTTP) server:

```toml
schema_version = 1

[[servers]]
id = "example"
enabled = false
transport = "streamable_http"
url = "https://mcp.example.com/mcp"
authentication = "bearer_environment"
token_environment = "EXAMPLE_MCP_TOKEN"
allowed_tools = ["search"]
timeout_seconds = 20.0
max_result_bytes = 131072
```

For a local `stdio` server:

```toml
schema_version = 1

[[servers]]
id = "example-local"
enabled = false
transport = "stdio"
command = "/absolute/path/to/example-mcp-server"
args = []
allowed_tools = ["lookup"]
timeout_seconds = 20.0
max_result_bytes = 131072
```

Rules:
- `schema_version = 1` is canonical; legacy files without it load as version 1,
  while unsupported future versions fail during deployment preflight
- Remote bearer credentials name an environment secret — never the secret itself
- `stdio` commands use absolute paths; no shell pipelines, redirection, or command substitution
- A failed server degrades only its own tools and never stops the IDE or agent service
- MCP tool descriptions, annotations, resources, prompts, and results are **untrusted**

Restart the agent service after changing the MCP catalog.

### Agent-Skill Package

A skill is a confined directory of data and instructions — not executable code:

```text
skill-id/
├── skill.json          Schema version, ID, version, tools, limits, safety metadata
├── instructions.md     Plain-language task guidance only
└── examples.json       Optional simulation examples
```

The prompt composer inserts selected Skill instructions **after** the immutable safety rules. External text and Skill instructions cannot precede or replace safety rules.

Skill validation rejects: unknown fields, executable code, symlinks, absolute paths, parent traversal (`../`), oversized files, excessive directory depth, unknown tools, and attempts to weaken safety. A skill can only **reduce** the allowlisted tools and execution budget — it cannot add a permission.

Built-in skills are read-only package assets. User skills live under `~/.config/ninjarobot_pi5/skills/`.

### BehaviorDraftCompiler

The single compatibility boundary between variable model output and the strict Phase 4 behavior schema. Accepts both the full canonical saved format and a smaller transient draft:

```json
{
  "name": "exciting_forward",
  "description": "Move briefly while looking excited.",
  "stages": [
    {
      "face": "exciting",
      "melody": "exciting",
      "movement": "move_forward",
      "duration_seconds": 1
    }
  ]
}
```

The compiler:
- Assigns missing stage names
- Resolves named movement assets through configured logical servo roles
- Converts note names (e.g., `C5`) to frequency
- Recognizes documented melody aliases
- Supplies a default one-second duration for transient movements
- Separates display or buzzer conflicts into ordered stages

Invalid model output raises `BEHAVIOR_DRAFT_INVALID` with field-specific correction guidance and `definitely_not_executed: true`. The agent can repair the JSON without guessing whether hardware moved.

### Deterministic Camera-Intent Boundary

`AgentLoop` intercepts explicit English and Japanese capture requests before the first model turn. A recognized request is resolved directly through the trusted `robot.camera.preview` tool — the AI model is not consulted. This prevents model refusals from overriding a valid current camera grant.

The matching is conservative: it recognizes explicit requests to take a photo and rejects camera questions and negated requests. Any new language form needs positive, negative, no-grant, failure, and redaction tests before merging.

### Phase 7 Persistent Multi-User Memory

Phase 7 extends the existing owner-only conversation SQLite database. It does
not add a vector database or a second hardware owner. SQLite runs in WAL mode,
uses idempotent numbered migrations, and remains mode `0600` under an owner-only
directory.

Core modules:

| Module | Responsibility |
|---|---|
| `memory_migrations.py` | Transactional schema creation and legacy transcript backfill |
| `memory_models.py` | Strict profile, face, memory, attempt, and settings contracts |
| `memory_store.py` | Deterministic mutations, user-scoped reads, FTS5 fallback, pruning, audit events |
| `memory_services.py` | Conservative capture policy and bounded automatic retrieval |
| `memory_mcp.py` | Fixed in-process FastMCP catalog with four trusted read-only tools scoped from the invocation session |
| `identity.py` (IDE) | Countdown capture, existing `pi5camera` API, full-frame deletion, face-data permissions |

Important tables are `users`, `face_profiles`, `preferences`, `memory_items`,
`behavior_attempts`, `pending_memory_confirmations`, `memory_settings`, and
`memory_audit_events`. `messages.user_id` is backfilled during migration so one
session can switch users without reassigning or exposing earlier messages.

Identity workflow:

1. The first chat asks for a name and creates `local-user` as owner/default.
2. The IDE shows its existing `3 → 2 → 1` camera animation.
3. `FaceIdentityDevice` takes a temporary retained frame through `CameraDevice`.
4. The existing `pi5camera` recognition/enrollment API must find exactly one face.
5. Only the cropped known-face image and encoding/index metadata remain; the
   full frame is removed in `finally`.
6. `/identify` switches only when exactly one known identity maps to one profile.
   Unknown, no-face, multiple-face, error, or ambiguous results do not switch.
7. `/switch user` first resolves a selected profile, then runs the same visible
   recognition workflow. The session changes only when the returned opaque
   identity exactly matches that profile's face index. A mismatch, unavailable
   camera, unknown/no/multiple face, or missing enrollment keeps the original
   user and revokes that session's motion and camera grants.
8. Every enrollment/identification path restores silent Idle in a
   cancellation-safe IDE `finally` path, so an error cannot strand the display
   on the camera icon.
9. `/update profile` reports the active name and face status. The exact
   `register user face` action retries pending enrollment or adds a refreshed
   sample for that same identity; `name=<new name>` changes only the user name.
10. An inactive profile with missing or stale face data can be recovered only
    through deterministic **Manage Memory → Register or Replace User Face** or
    `memory register-face USER_ID --confirm`; recovery never performs an
    unverified switch.

The agent never imports `pi5camera`. `RobotIDEClient` exposes only deterministic
identity methods, and normal AI camera preview consent remains a separate path.
Face identity is personalization, not authentication.

Capture policy:

- Raw conversations retain their active `user_id` and default to seven days.
- New dynamic expression/movement success creates a 15-minute confirmation;
  a bounded leading Yes/No form consumes it without consulting the model.
- An affirmative may include a quoted name, for example
  `Yes, name it "Exciting one step forward"`. The runtime uses the user's reply
  as explicit confirmation, saves the searchable `successful_behavior`, and
  submits the exact IDE-compiled definition to confirmation-gated
  `behavior.save_user`. No second confirmation UI exists or is required.
- The catalog identifier is a safe lowercase ASCII form such as
  `exciting_one_step_forward`; non-ASCII display names remain searchable and
  receive a stable fallback catalog identifier. Catalog collisions never
  overwrite an asset. A failed dual-save rolls back the success memory and
  restores the pending confirmation for retry.
- Technical behavior failure records the authoritative normalized tool result
  automatically as `failed_behavior`; policy denial alone is not a technical
  failure.
- Narrow first-person preference forms and successful named behavior runs may
  create inferred preference/task-recipe memories with a visible notice.
- The assistant defaults to `NinjaAgent`. An explicit ordinary-chat rename is
  persisted in the active user profile before model reasoning and overrides
  older conversation claims. `/update profile` does not accept `robot_name`.
- Explicit conversational identity capture recognizes both a requested robot
  name and a requested form of address. A compound request updates the profile
  and the structured `preferred_form_of_address` preference in one SQLite
  transaction, so validation or write failure cannot persist only half of it.
- A successful-behavior confirmation with one quoted label uses that label even
  when surrounding natural wording contains a minor typo. The quoted-label
  fallback stays inactive when the reply contains multiple ambiguous labels.
- Memory capture and retrieval failures publish an error event but never change
  the authoritative robot result or interrupt a successful hardware action.

Retrieval policy:

- Automatic context is restricted to the active user, six items by default,
  and 4,000 characters including profile/preference context.
- Within that cap, recent successful behaviors and a recent task recipe are
  included even for generic prompts; query-relevant results are merged and
  deduplicated. This makes retrieval consistent across local/cloud providers
  instead of depending on a model to choose the read-only memory tool.
- The active user's canonical robot name and structured preferred form of
  address are always injected as trusted bounded data. They are queried by user
  ID on every turn, independently of transcript, interface, or model provider.
  The form of address is a label only and cannot supply instructions or roles.
- Retrieved text is inserted after safety/runtime state as reference data, not
  authorization or instructions.
- `memory.profile.get`, `memory.search`, `memory.behavior.successful`, and
  `memory.behavior.failed` accept no user identifier. The provider resolves the
  user from out-of-band trusted session context and executes every read through
  the fixed FastMCP server.
- No model-facing memory mutation tool exists. Mutations are available only by
  deterministic service/IPC/CLI operations.

Retention defaults are seven days for messages and 180 days/1,000 entries per
user for failed behaviors. Profiles, preferences, recipes, and confirmed
successes persist until an administrator deletes them. Deleting a profile is
limited to inactive non-owners and removes its transcript, structured memory,
face index, and cropped image. Transfer ownership before deleting an owner.

The distinct `memory reset-all --confirm` operation can remove the owner. The
interactive menu additionally requires the exact phrase
`DELETE ALL ROBOT MEMORY`. The IDE first atomically quarantines its dedicated
face-data directory; SQLite then deletes all users, messages, preferences,
behavior attempts/memories, pending confirmations, audit events, and retrieval
index entries in one transaction and restores configured retention defaults.
The quarantine is restored if the database transaction fails and permanently
removed only after it commits. Runtime user state and all motion/camera grants
are cleared. Reset fails closed if the configured identity directory contains
entries outside the dedicated face-data layout, preventing an incorrect path
from moving or deleting unrelated files. API keys, model/provider
configuration, saved IDE behavior files,
hardware calibration, and service logs are deliberately outside this reset.
The next chat sees no owner and begins first-user registration.

Run the synthetic retrieval benchmark without hardware:

```bash
uv run python scripts/benchmark_agent_memory.py --entries 1000 --queries 50
```

The script uses a temporary database and fails if p95 retrieval exceeds 100 ms
or if 1,000 synthetic entries exceed 16 MiB. These are software guardrails,
not a substitute for the Raspberry Pi checklist.

Face recognition uses the OpenCV 4 `CascadeClassifier` fallback when MediaPipe
is unavailable. `pi5camera` constrains `opencv-python-headless>=4.8,<5` because
the current OpenCV 5 wheel does not expose that API. Validate a deployment
without using the camera:

```bash
uv run --frozen python scripts/validate_face_recognition_backend.py
```

If the command reports an incompatible `cv2`, run
`uv sync --frozen --extra hardware` and restart the service. Install only one
OpenCV wheel variant in the environment.

Raspberry Pi OS owns Picamera2/libcamera through apt. Both the standalone
`pi5camera` backend and integrated IDE first try an in-process import; an
isolated root `uv` environment falls back to a bounded `/usr/bin/python3 -s`
subprocess with the managed `pi5camera/src` path. Only capture parameters and
the explicit output path cross that boundary. This avoids unsupported
`--system-site-packages` environments while keeping face recognition in the
locked project OpenCV environment.

### HTTPS Web Controller

`web start` is an IPC request to the already-running Agent service; it never
creates another runtime or hardware owner. Its response contains `ready`, the
LAN/mDNS URL, a loopback diagnostic URL, certificate/CA paths, and the next
trust step. WebSocket activation permission/runtime failures release the lease
and close with a bounded controller error rather than escaping the ASGI task.

The Phase 8 dashboard loads key-identical JSON dictionaries for `en`, `ja`,
`zh-TW`, and `zh-CN`. It chooses a supported browser locale on first use,
stores an explicit choice in `localStorage`, updates the document language and
accessibility labels together, and falls back to English. Tool names, slash
commands, capability identifiers, and safety values remain unambiguous.

The top-right hamburger opens a full-screen, safe-area-aware menu containing
language, connection/pairing status, and system power. Always-on voice and
manual USB recording are main-surface controls below Camera and Web
Microphone. The connection badge stores a semantic connection key rather than
translated display text, so locale changes cannot reset a live connection to
“offline.” Focus is contained while the menu or power confirmation is open;
Escape and the menu backdrop close safely. Emergency Stop remains on the main
controller surface.

Web power-off is a deterministic service operation, never a model tool. Only a
paired browser holding the exclusive controller lease receives access. The
server first verifies the fixed helper, its narrow passwordless sudo rule, and
the active Pi 5 full-power-off EEPROM state; an incomplete or pending
deployment is rejected before the Agent stops. It then issues a
30-second, one-use, lease-bound nonce; explicit confirmation
consumes it before stopping hardware and voice. The service then closes the
tunnel, web server, durable stores, IDE, and ownership lock before invoking the
fixed `/usr/libexec/ninjarobot-poweroff` helper with fixed argv and no shell. A
rare helper failure after cleanup leaves the robot stopped and logs its exit
status plus at most 500 printable diagnostic characters, followed by
`sudo systemctl poweroff` as the local recovery action.

- Started and stopped through IPC — cannot create a second IDE or hardware owner
- Generated local CA + `.local` server certificate stored under `~/.config/ninjarobot_pi5/tls/`
- One exclusive WebSocket controller lease — a second browser receives HTTP `423 Locked`
- Each browser stores a random, non-secret chat identifier in `localStorage`;
  the server hashes it into a stable session ID across lease renewal/reconnect
- Browser/terminal sessions never silently switch each other. Interfaces that
  independently select the same user read the same user-scoped long-term memory
- A missed heartbeat revokes the lease and requests `robot.servo.stop`
- D-pad controls, Emergency Stop, Resume, Speech ON/OFF, AI camera, USB speech transcription, and browser speech recognition

The D-pad rows use the height allocated by the parent grid, preventing overlap with camera and microphone controls in short non-fullscreen viewports. iPhone/iPad users should use **Add to Home Screen** for the most reliable standalone portrait view.

---

## Behavior system

### Behavior Format

A behavior contains one or more ordered stages. Operations within a stage begin concurrently. Each stage may contain:

| Field | Limits |
|---|---|
| `face` | One of the 20 embedded animated expressions |
| `text` | Display text (cannot be combined with `face` in the same stage) |
| `melody` | One named Pi5 buzzer melody |
| `tone` | Frequency 20–20,000 Hz, duration 0.05–2 s, volume 1–128 |
| `movement` | Named movement or logical servo targets |
| `duration_seconds` | How long the stage remains active |
| `wait_seconds` | Optional quiet delay after the stage |

### The 20 Animated Faces

`idle`, `happy`, `laughing`, `sad`, `cry`, `angry`, `surprising`, `sleepy`, `speaking`, `shy`, `scary`, `exciting`, `confusing`, `greeting`, `listening`, `thinking`, `curious`, `success`, `warning`, `error`

### Default Motor and Obstacle Policy

Logical roles map to servo endpoints:

```toml
[behaviors.servo_roles]
left_motor = "gpio12"
right_motor = "gpio13"
```

Default movement targets for MG90D continuous-rotation motors:

| Behavior | Left motor | Right motor |
|---|---:|---:|
| `move_forward` | +45 | −45 |
| `move_backward` | −30 | +30 |
| `turn_right` | +45 | +45 |
| `turn_left` | −45 | −45 |

Zero (or the calibrated center) represents neutral for these motors. Emergency Stop uses zero PWM pulse through the driver's `off()` path — not a motion target.

### Obstacle Detection Rules

- Movement starts without waiting for clear-distance readings
- The exact VL53L0X raw sentinel `8191` = clear space (no target in range)
- `null`, invalid, missing, and stale samples do not stop movement
- Three consecutive valid readings ≤ 50 mm → non-latching behavior interruption
  (forward, turn_left, turn_right only)
- The current drive, concurrent face/audio operations, and all later stages are
  cancelled; the behavior is never resumed or replayed automatically
- A silent scary face appears for two seconds, then supervised Idle resumes
- The tool result uses `completed=false`, `interrupted=true`, identifies
  `front_obstacle`, and tells the user that no `/resume` is required
- Backward movement: warning only (the sensor faces forward)
- The schema refuses obstacle thresholds below 50 mm

### Private Behaviors

Private behaviors are stored under `~/.config/ninjarobot_pi5/behaviors`. Write rules:

- Names cannot contain a directory path
- Symbolic links are rejected
- Files use mode `0600`
- Writes are atomic
- Existing assets are never overwritten silently

After a new dynamic behavior succeeds, an affirmative recording reply installs
the exact definition compiled and executed by the IDE. The entry is therefore
both a searchable per-user successful-behavior memory and a runnable private
catalog behavior. The runtime, not the model, carries the confirmation through
the normal policy boundary with `confirmed=True`; catalog saving never
re-executes the robot action.

`stop` and `resume` are safety commands, not behavior assets — they cannot be embedded or redefined.

---

## Extension points

### Adding a New Hardware Capability

1. Create a new adapter module inside `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/adapters/`.
2. The adapter must lazily import the relevant `pi5*` library — only when explicit `--real` use is confirmed.
3. Register the capability descriptor in `CapabilityRegistry`.
4. Add the capability to the IDE contracts schema.
5. Add simulation and real-device tests.
6. Add the capability to the Phase validation checklist.

### Adding a New MCP Server

See the [MCP and Agent Skills Tutorial](../2026-09-09-02/NinjaRobot_MCP_Skill.md) for the
operator-facing Tavily setup, strict external-server configuration schema,
read-only Google Calendar example, and custom MCP walkthrough. For development:

1. Never pass raw GPIO fields or hardware-library objects through the MCP surface.
2. Sandbox the server — a failed server must degrade only its own tools.
3. Add tests for: prompt injection, malicious schemas, name collisions, oversized content, timeouts, cancellation, secret redaction, authentication failure, and connection loss.

### Adding a New Agent Skill

See the [MCP and Agent Skills Tutorial](../2026-09-09-02/NinjaRobot_MCP_Skill.md) for the exact
Skill package format and a complete validation, simulation, installation, and
invocation example. For development:

- Do not add SDK calls or provider credentials to a Skill
- Skills are declarative Markdown plus strict JSON metadata
- A skill can only restrict the active tool allowlist — it cannot expand it
- AI-proposed skills require validation, simulation, and explicit approval before saving

### Adding a New Cloud Provider Adapter

1. Implement the `LLMProvider` protocol.
2. Register in `ConfiguredProviderRegistry`.
3. Use `auth_method = "api_key"` only — no OAuth, browser login, or external auth command.
4. The adapter URL must be validated against the official host — reject any configuration that would forward credentials to another server.
5. Add fake-provider and recorded-response contract tests.

---

## Testing and validation

### Test Categories

| Category | Scope | Markers |
|---|---|---|
| Unit | Single module, simulation only | (default) |
| Integration | Multi-module, simulation | (default) |
| Hardware | Real device communication | `@pytest.mark.hardware` |
| Provider (live) | Real cloud API | `@pytest.mark.provider_live` |

### Phase Validation Flow

Each development phase follows this sequence before merging:

1. Safe smoke tests that do not move actuators
2. Device communication tests (GPIO, I2C, SPI, camera, USB audio)
3. Actuator-moving tests with an accessible emergency stop
4. Power-risk tests requiring a completed electrical record

Record: expected outcomes, actual results, rollback steps, operator name, Pi model, OS version, and wiring revision.

### Current Test Suites

- Driver provenance and governance (`test_repository_governance.py`)
- IDE contracts and execution engine
- Fake-device simulation for all hardware adapters
- Behavior model validation and draft compiler
- Fake MCP server contract and transport tests
- Skill confinement and schema tests
- System-prompt ordering and override-resistance tests
- Tool policy and unknown-outcome recovery tests
- FastAPI and exclusive WebSocket lease tests
- Fake-provider and Ollama contract tests
- Model discovery, persistence, hot-switch, informational benchmark, and explicit motion-arm tests
- Presentation-directive filtering and IDE face-lifecycle tests
- Restartable Level 2 device lifecycle and one-shot camera redaction tests
- Cancellation-safe SPI serialization, repeated display/buzzer reconstruction, and rapid Idle-restart stress tests

### Running the Full Gate with JavaScript Check

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen ruff format --check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen mypy \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
node --check \
  ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js
git diff --check
```

---

## Driver package validation commands

Each `pi5*` package has its own isolated test environment. Run tests using the package-local layout:

```bash
# Each driver in its own directory, frozen and isolated
(cd pi5servo && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5disp && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5vl53l0x && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5camera && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5mic && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5buzzer && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)
```

Run driver Ruff checks using the root's pinned Ruff version:

```bash
for package in \
  pi5buzzer pi5servo pi5disp pi5vl53l0x pi5camera pi5mic
do
  (cd "$package" && uv run --project .. --isolated --locked --python 3.11 \
    ruff check --no-cache src tests)
  (cd "$package" && uv run --project .. --isolated --locked --python 3.11 \
    ruff format --check src tests)
done
```

### Standalone Driver README Standard

Each `pi5*` README must work for a user who has only that library folder. Requirements:

- Do not require NinjaRobotPi5, NinjaClawBot, or an invented Git URL
- Tell the user to obtain a copied source folder from the project owner
- Use `uv sync --frozen` and the library's own CLI
- Explain every abbreviation and specialist term in plain language
- Clearly separate safe checks from commands that energize hardware or move an actuator

---

## Authentication boundary reference

All three cloud providers use API-key-only authentication:

| Setting | Behaviour |
|---|---|
| `auth_method = "api_key"` | Resolves `api_key_env` from process environment, then `~/.config/ninjarobot_pi5/secrets.env` |
| Legacy `auth_method = "oauth"` | Loaded as `api_key` and rewritten without `oauth_profile` — no old bearer or refresh credential consumed |
| `provider login` command | Compatibility-only; raises a migration message pointing to `provider set-api-key`; never starts a browser |
| `provider logout PROVIDER_ID` | Removes only that provider's saved API key |

Cloud adapter URL validators accept only HTTPS and the official host for each provider:
- OpenAI: `api.openai.com`
- Gemini: `generativelanguage.googleapis.com`
- Anthropic: `api.anthropic.com`

A configuration change that points to another host is rejected — preventing credential forwarding.

---

## Developer troubleshooting

| Symptom | Cause and fix |
|---|---|
| Root `pytest` imports the wrong driver package | Use the package-local commands shown above; drivers are independent projects |
| `ruff: command not found` | Run through `uv run --frozen ruff ...` |
| Ruff upgrade reports new driver errors | Reproduce the Phase 0 gate with pinned Ruff 0.15.5 before deciding whether it is code or tool-version drift |
| Driver checksum changes unexpectedly | Stop immediately. Revert an unintended change or, for an approved repair, record the new hash with `--record-authorized` |
| A test accesses hardware | Ensure it is explicitly marked `hardware` and excluded from the default gate |
| `distance read` returns 250 mm without opening I2C | Expected simulation result. Add `--real` only on the Pi when you intend to open the sensor |
| Real command reports `DEVICE_OUT_OF_RANGE` and raw `8191` | The middleware is working correctly. In open space, no target is measurable. Integrated movement treats this exact result as clear space |
| Real command reports `DEVICE_UNAVAILABLE` | Install with `uv sync --frozen --extra hardware`, confirm I2C is enabled, and confirm address `0x29` appears on bus 1 |
| A repeated action does not re-read the sensor | Intentional when the same action ID or idempotency key is reused. Generate new IDs for a new physical reading |
| Real servo health is unavailable | Verify the `pwm-2chan` overlay in `/boot/firmware/config.txt`, confirm I2C address `0x10`, install the hardware extra, confirm the user can access `/sys/class/pwm` and `/dev/i2c-1` |
| Real move returns `SERVO_MOTION_DISABLED` | Regenerate/synchronize the private config or confirm `motion_enabled` and `group_motion_enabled` are true. Agent movement still separately requires `/arm` |
| Real move returns `SERVO_NOT_CALIBRATED` | Calibrate that endpoint with the standalone `pi5servo` tool. Do not substitute another servo's calibration |
| Display shows `simulated: true` | A scriptable simulation command was selected. The interactive IDE tool runs physical hardware directly after installation |
| Screen goes dark when a command exits | Intentional cleanup. Add `--hold 5` to a real manual test to keep the backlight active for inspection |
| Text is sideways on the display | Authoritative V4 rotation is 90°. Confirm `--config` points to the correct TOML file |
| Hardware already owned by another process | Use the existing agent interface, or run `uv run --frozen --extra hardware ninjarobot-agent service stop`, then retry. Also stop both integrated tools before opening a standalone `pi5*` tool |
| `uv run ninjarobot-agent` reports `No module named 'qrcode'` | Pull the dependency fix and run `uv sync --frozen --extra hardware`. qrcode 8.2 is now an unconditional IDE dependency; do not install an unrelated QR package manually |
| Agent boot fails because `schema_version` is an extra MCP field | Pull the MCP schema/deployment repair. The canonical `mcp.toml` begins with `schema_version = 1`; rerun **Install and deploy automatic startup Agent** so preflight validates it and clears the old systemd failed limit |
| Deployment status says `enabled: true` but `running: false` | Enablement only means systemd will attempt boot. Inspect the structured `systemd` result/exit status and Agent log, repair the reported configuration, then rerun the confirmed deployment setup; success requires `ready: true` |
| Boot Agent runs but the display shows no QR; journal contains `xCreatePipe`, `.lgd-nfy`, or `Read-only file system` | The installed unit predates the private `lgpio` runtime-directory repair. Pull the current checkout, synchronize dependencies, and rerun confirmed deployment setup so `/etc/systemd/system/ninjarobot-agent.service` receives `RuntimeDirectory=ninjarobot-agent` and `LG_WD=/run/ninjarobot-agent`; then reboot with wheels raised. Do not make the repository writable. |
| Web Power Off stops the Agent but the Pi boots again | The Pi 5 bootloader is not using full PMIC shutdown. Pull this repair, rerun **Startup Agent Deployment → Install and deploy automatic startup Agent**, reboot once when `poweroff_reboot_required` is true, then require `full_poweroff.ready: true` before retesting. |
| Web Power Off says an EEPROM update is pending | Setup successfully queued the official full-power-off setting, but it is not active yet. Keep wheels raised, reboot once, and recheck Startup Agent status. Do not keep retrying Power Off before that reboot. |
| Startup Agent status reports `poweroff_helper: false` | The fixed helper is missing or its bytes, root ownership, non-symlink identity, or `0755` mode are wrong. Rerun **Install and deploy automatic startup Agent**. Older affected installations may contain the sudoers rule at `/usr/libexec/ninjarobot-poweroff`; do not edit it manually. |
| X1208 stays on after a confirmed OS shutdown | First require `poweroff_helper: true` and `full_poweroff.ready: true`. Then disconnect power and verify the X1208 pogo pin contacts the Pi 5 `PSW` through-hole, power enters only through the X1208 USB-C input, and the 40-pin connection is fully seated. |
| A repaired `pi5*` source file is present but Python runs an older copy | Run `uv sync --frozen --extra hardware`, then `scripts/verify_workspace_driver_sources.py`. Editable dependencies must resolve into this checkout |
| Camera reports unavailable while `/usr/bin/python3` imports Picamera2 | Run `./scripts/bootstrap-rpi-camera-workspace.sh`; both standalone and integrated capture should then use the bounded system-Python bridge. Do not recreate `.venv` with `--system-site-packages` |
| `pi5mic` reports PortAudio missing | Install `libportaudio2` and `portaudio19-dev`, then run `pi5mic devices`. Local transcription also requires a built `whisper-cli` and `ggml-base.bin` |
| V4 microphone status reports 44.1 kHz instead of 16 kHz | Expected. The USB device rejected 16 kHz; the managed driver selected its supported native rate. Check both `requested_sample_rate_hz` and `actual_sample_rate_hz` in the status output |
| Voice input reports `transcriber_unavailable` | Build/configure `whisper-cli` and its local model, then disable and re-enable voice input. Terminal and web text chat remain available |
| Voice input reports `microphone_unavailable` or `audio_overflow` | Stop standalone audio programs, verify the USB device and PortAudio packages, use `/voice input off`, then re-enable after the device is free |
| Voice input reports `microphone_busy`, `microphone_permission_denied`, or `microphone_format_unsupported` | Close other recording programs, verify group/device permissions, or select a supported USB format in the standalone `pi5mic` setup; then re-enable voice |
| Voice input reports `listener_start_timeout` | The model loaded but the USB stream did not become ready within the bounded startup window. Disconnect/reconnect the microphone, close competing ALSA/PortAudio clients, and enable voice again |
| Voice input reports `detector_unavailable` | Run the packaged-asset checksum tests and the hardware-extra model-load check. The service never downloads a missing model during boot |
| Remote access reports `executable_unavailable` | Run `ninjarobot-agent remote configure` locally. Unattended boot intentionally refuses to download ngrok |
| Remote access reports `authtoken_unavailable` or `authentication_failed` | Replace the token through the local Remote Access menu; do not paste it into web chat, TOML, logs, or issue reports |
| Remote access reports `account_rejected` | Inspect the ngrok dashboard for account/endpoint/plan limits. Local fallback is restored while remote access is unavailable; explicit deactivation does not start a new Local Web session. Robot control remains available |
| Remote access reports `configuration_invalid` | Correct/reconfigure ngrok locally. Permanent configuration failures deliberately stop retrying so a broken endpoint cannot leave a process continuously restarting |
| Pairing URL reports `tunnel_not_ready` | Use Remote Access Status, correct the reported tunnel failure, and activate again. A pairing fragment exists only after a public HTTPS endpoint is ready |
| Pairing link is expired or already used | Run `ninjarobot-agent remote rotate-pairing`; this deliberately revokes existing remote browser sessions |
| Remote request returns `401` or `421` | Use the exact current pairing URL through the ngrok endpoint. Do not override Host/Origin headers or expose port 8443 directly |
| Agent startup reports a controlled connection-closed error | The background service exited while the CLI was polling it. Inspect `~/.local/state/ninjarobot_pi5/agent-service.log` for the primary exception. IPC peer resets, including resets during `wait_closed()`, must never escape as a raw traceback or overwrite an already received response |
| VL53L0X reference calibration retries once | This is the bounded recovery path on the live revision-`0x10` device. A second timeout is a hard initialization failure — do not bypass calibration |
| Clean checkout reports `recovery_required` | Inspect `robot.safety.reason` and `robot.safety.fault_detail`, close any standalone `pi5*` programs, and use the confirmed recovery path. Never remove `safety.json` as a repair |

---

## Phase and feature status

| Phase | Status | Description |
|---|---|---|
| Phase 0 | ✅ Complete | Project governance, driver hash baseline, quality gate |
| Phase 1 | ✅ Complete | IDE and agent contracts, deterministic fakes, unified CLI |
| Phase 2 | ✅ Complete | IDE capability registry, scheduler, action ledger, distance adapter |
| Phase 3.1 | ✅ Complete | GPIO27 buzzer adapter |
| Phase 3.2 | ✅ Complete | ST7789V display adapter |
| Phase 3.3 | ✅ Complete | Six-servo mixed-backend adapter |
| Phase 3.4 | ✅ Complete | Privacy-bounded camera adapter |
| Phase 3.5 | ✅ Complete | USB microphone adapter |
| Phase 4 | ✅ Complete | Integrated behaviors, 20 faces, IDE tool, safety engine |
| Phase 5 | ✅ Complete | NinjaRobotAgent, Ollama, HTTPS web controller, MCP, Skills |
| Phase 6 | ✅ Complete | OpenAI, Gemini, Anthropic cloud provider adapters |
| Phase 7 | Complete | Multi-user memory, face identity, capture, bounded retrieval, management |
| Phase 8.2 | Complete | IDE-owned always-on Hey Ninja input and four transcription locales |
| Phase 8.3 | Complete | Optional ngrok lifecycle and passwordless pairing |
| Phase 8.4 | Complete | Four-locale dashboard and nonce-confirmed orderly power-off |
| Phase 8.5 | Complete | QR onboarding and connection-triggered Greeting |
| Phase 8.6 | Complete | Explicit systemd deployment, boot lifecycle, and power-off helper |
| Pi acceptance | Complete | Phase 8 manually validated by the project owner on the reference robot |

The historical implementation plan in
`docs/project-history/NinjaRobotPi5V4_ImplementationPlan.md` records the design
decisions that produced v1.0.0. Current work follows `AGENTS.md`, this guide,
and applicable ADRs.

## Local project knowledge workflow

Use the [wiki maintenance guide](../../../../../ninjarobot_pi5_wiki/docs/PROJECT_WORKFLOW.md)
for AI coding tool setup, retrieval before development, versioned manual updates,
source review, and documentation completion checks. This guide is a versioned
source; edit a new version rather than this registered original.
