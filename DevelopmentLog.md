# NinjaRobotPi5V4 Development Log

## 2026-07-29 — Local model, expressive-agent, Tavily, and controller refinement

### Summary

Completed the approved post-test refinement in five independently validated
implementation phases:

- corrected the Tavily preset to allow current raw server tool
  `tavily_search`, preserved public name `mcp.tavily.tavily-search`, and added
  in-memory migration for an older owner configuration
- repaired browser-microphone state and label handling while preserving the
  rule that recognized text waits in the input until the user presses Send
- added provider-neutral installed-model discovery, numbered interactive
  selection, scriptable `model list|current|select`, atomic persistence, and
  idle-only hot switching
- closed the old provider after a successful switch, disarmed previous AI
  motion sessions, and blocked natural-language physical motion until the
  selected exact model has an accepted benchmark report
- serialized conversations and added the IDE-owned Idle, Thinking,
  Speaking/emotion, tool-action, and return-to-Idle presentation lifecycle
- added a strict display-only emotion directive that is removed before
  streaming or transcript persistence and cannot grant tool or motion access
- refined the portrait controller to match `templates/webinterface_02.jpg`,
  removed redundant labels, consolidated AI motion state into its button,
  protected the chat form from the Live Activity tab, and added the
  fullscreen/start gesture with a mobile Safari standalone fallback
- made `load_robot_config` consistently expand a leading home-directory
  shortcut so default CLI paths work for new commands

### Architecture and safety

The agent still reaches robot presentation and actions only through
`RobotIDEClient`. Ambient faces yield to foreground IDE behaviors and do not
overwrite Level 1, Level 2, driver-failure, or shutdown presentation. Model
emotion is a bounded display choice, not an action or permission.

No managed `pi5*` driver file changed. The immutable-driver report continues
to match 222 tracked files and 25 previously authorized repairs.

### Validation

Each implementation phase passed compile checks, Ruff lint and format checks,
strict MyPy, pytest, JavaScript syntax, diff checks, and immutable-driver
verification. The last pre-documentation gate reported 278 passing tests with
one known Starlette test-client deprecation warning. The complete
post-documentation gate repeated the same 278-test result, built both agent and
IDE source/wheel distributions, and confirmed the packaged web assets. Live
read-only checks confirmed local Ollama model discovery and current Tavily
health/tool discovery.

### Raspberry Pi status

Software implementation is complete. Physical and browser acceptance remains
an operator task. Follow
`docs/validation/phase-5-agent-model-ui-refinement-validation-2026-07-29.md`
in order, beginning with simulation and read-only checks before display,
privacy, network-loss, or raised-wheel motion tests.

## 2026-07-29 — Phase 5 agent and mobile web refinement

### Summary

Refined the completed Phase 5 agent and controller after Raspberry Pi testing:

- replaced the single short model timeout with a 600-second complete-request
  limit and a 120-second inactivity limit that resets on visible or private
  model activity
- kept private model thinking out of chat, transcripts, and user-facing logs
- added one real startup Greeting followed by a service-owned, silent,
  continuously looping Idle face
- restored Idle after normal behavior completion or Resume without overwriting
  Level 1, Level 2, driver-failure, or shutdown safety displays
- removed the distance-clear startup gate, changed the obstacle threshold to
  50 mm, and applied three-reading Level 1 stops to Forward and both turns
- retained backward movement as warning-only and treated exact raw `8191` as
  clear space; null, invalid, missing, and stale readings do not stop motion
- replaced the generated self-signed leaf certificate with a persistent local
  certificate authority and `.local` server certificate
- added public-CA status/export commands while keeping both private keys
  owner-only
- changed the printed controller URL to
  `https://ninjarobotpi5.local:8443/`
- rebuilt the controller as a fixed portrait layout for mobile Chrome and
  Safari, with a rotate-back landscape overlay and hidden Live Activity drawer
- hardened D-pad pointer/touch behavior against text selection, touch callouts,
  lost releases, page hiding, and focus loss
- changed browser speech recognition to fill the chat input for review; only
  Send transmits it

### Main files changed

- `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py`
- `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/ollama.py`
- `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service_main.py`
- `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_app.py`
- `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/`
- `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/robot.py`
- `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config.py`
- the related agent and IDE tests
- `README.md`, `InstallationGuide.md`, `DevelopmentGuide.md`,
  `NinjaRobotPi5V4_ImplementationPlan.md`, and the new Raspberry Pi validation
  checklist

No managed `pi5*` hardware-driver file was changed. Cross-device behavior
remains inside `ninjarobot_pi5_ide`, and the agent still accesses hardware
only through the IDE boundary.

### Why

Physical testing showed that local model thinking could outlast the previous
timeout, the old distance preflight could prevent valid movement, and an
untrusted leaf certificate was difficult to use with mobile Safari. The
controller also needed a reliable portrait touch layout and a review step
between speech recognition and sending a prompt.

### Validation

Each implementation phase passed immutable-driver verification and its full
Python gate. Before the documentation pass, the final software suite reported
268 passing tests. JavaScript syntax validation also passed. The complete
post-documentation gate and packaged-static-asset check are recorded in the
final task handoff.

### Raspberry Pi status

Operator validation is still required for the refreshed Qwen3:4B timeout
behavior, startup Greeting/Idle lifecycle, 50 mm obstacle stops, certificate
trust in both mobile Safari and Chrome, portrait touch controls, heartbeat
loss, camera preview, USB microphone cleanup, and raised-wheel movement.

Follow
`docs/validation/phase-5-agent-refinement-validation-2026-07-29.md` from top
to bottom.

### Follow-up

Record the completed device checklist and benchmark report. Keep the web
controller local to the trusted LAN; authentication and internet exposure
remain outside this phase.

## 2026-07-28 — Phase 5.0–5.7 agent implementation

### Summary

Implemented the bounded NinjaRobotAgent through the complete approved Phase 5
software scope. The result is one reconnectable owner service shared by the
conversational CLI and optional FastAPI HTTPS web interface. Robot operations
remain confined to the NinjaRobotPi5 IDE; no agent module imports a managed
`pi5*` driver.

Implemented:

- owner-only process lock, Unix-domain IPC socket, bounded event broker, and
  SQLite transcripts with seven-day retention
- provider-neutral model, message, tool, policy, recovery, and cancellation
  contracts
- IDE tool discovery under `robot.*`, collision-safe MCP tools under
  `mcp.<server-id>.*`, and non-bypassable risk evaluation
- official MCP SDK connections over `stdio` and Streamable HTTP, owner-only
  secret storage, result limits, optional-provider degradation, and the
  search-only Tavily preset
- strict non-executable skills with `skill.json`, `instructions.md`, optional
  `examples.json`, prompt-order protection, atomic installation, simulation,
  and explicit approval for AI-proposed skills
- loopback-only Ollama adapter, Qwen3:4B candidate profile, streaming,
  normalized tool calls, bounded turns/tools/time, and a hardware-free model
  benchmark that never executes tools
- reconnectable `ninjarobot-agent` chat, interactive menu, service lifecycle,
  session, motion-arm, MCP, skill, and benchmark commands
- FastAPI HTTPS web UI with one exclusive controller lease, `423 Locked`
  second-client rejection, heartbeat stop, short refresh reconnection, direct
  D-pad control, Emergency Stop, confirmed Resume, Greeting, Celebrate, AI
  chat, and live events
- temporary IDE camera previews and local whisper.cpp USB-microphone
  transcription, with media cleanup on success, failure, and cancellation
- browser speech recognition for English and Japanese; recognized text is sent
  to the agent, while spoken robot responses remain outside Phase 5

### Safety and privacy decisions

- The first browser on the LAN wins the unauthenticated controller lease, as
  explicitly accepted by the owner. The web interface is HTTPS-only and must
  never be internet-exposed or port-forwarded.
- Direct controls use fixed server mappings. The browser cannot submit an
  arbitrary tool name.
- Direct D-pad and approved buttons use the controller session arm. Natural
  language motion uses a separate, explicitly confirmed chat-session arm.
- Emergency Stop remains model-independent. Lost heartbeats and controller
  shutdown cancel active movement and request zero servo pulse.
- Camera preview has a five-megabyte bound, is not retained on disk, and is
  redacted from the durable action ledger.
- USB audio and whisper.cpp transcript staging are removed after the text is
  produced or the operation is interrupted.
- External MCP metadata and results remain untrusted and cannot grant robot
  authority.

### Validation

- Managed-driver verification passed: 222 tracked files across six drivers
  match the import baseline plus 25 authorized repairs.
- Python compilation passed.
- Ruff lint and format checks passed.
- Strict mypy passed for 55 V4 source files.
- Automated suite passed: 259 tests.
- JavaScript syntax validation passed for the packaged web application.
- Wheel build inspection confirmed `index.html`, `styles.css`, and `app.js`
  are included.
- A real simulated-service smoke test started the owner process, started HTTPS
  on `127.0.0.1:18443`, returned ready health, stopped the web server, stopped
  the service, removed the IPC socket, and left no service process.
- A live Qwen3:4B greeting attempt streamed output but exceeded the 90-second
  development timeout. This is not an acceptance result; the model remains a
  candidate until the documented Pi benchmark passes.

No GPIO, PWM, I2C, SPI, camera, microphone, actuator, or live Tavily check was
performed during the local implementation gate.

### Files changed

- `ninjarobot_pi5_agent/`: agent loop, providers, tools, policy, MCP, skills,
  persistence, service, CLI, web server, web controller, TLS generation, static
  interface, tests, and package dependencies
- `ninjarobot_pi5_ide/`: integrated agent client plus temporary camera-preview
  and local microphone-transcription capabilities
- `README.md`, `DevelopmentGuide.md`, `InstallationGuide.md`,
  `NinjaRobotPi5V4_ImplementationPlan.md`: implemented behavior and workflows
- `docs/validation/phase-5-agent-validation-2026-07-28.md`: operator checklist
- `pyproject.toml`: exact strict-mypy discovery scope for V4 sources
- `uv.lock`: locked FastAPI and direct Phase 5 dependencies

### Next step

Run the Phase 5 Raspberry Pi checklist in order. Accept Qwen3:4B only if its
saved benchmark meets every threshold. Complete network and privacy tests
before raised-wheel motion, then report results so Phase 5 can be marked
operator-validated.

## 2026-07-28 — Phase 5 MCP, Tavily search, and agent-skill plan

### Summary

Refined the approved Phase 5 architecture so NinjaRobotAgent can gain new MCP
tools and validated agent skills without rebuilding its core. MCP means Model
Context Protocol, the client-server connection used to discover and call tools
from separate programs or hosted services.

The revised plan now includes:

- one single-owner agent service shared by reconnectable CLI and FastAPI web
  clients
- the new planned `ninjarobot-agent` conversational and interactive command
  while preserving `ninjarobot_pi5_cli` and `ninjarobot-ide-tool`
- a provider-neutral tool registry for IDE and MCP tool providers
- local `stdio` and remote Streamable HTTP MCP connections
- the official hosted Tavily MCP server as the default real-time search
  integration
- a strict search-only Tavily allowlist with environment-based secret loading,
  bounded output, citations, and explicit network/quota failures
- confined `skill.json`, `instructions.md`, and optional `examples.json` agent
  skill packages
- immutable safety-prompt ordering and rejection of executable-code skills
- the previously approved benchmark-first Qwen3:4B policy, seven-day
  transcript retention, exclusive browser lease, mobile web controls, camera,
  USB microphone, and English/Japanese browser speech requirements

### Files changed

- `NinjaRobotPi5V4_ImplementationPlan.md`
  - reconciled older CLI-only and no-HTTP statements with the approved
    single-owner FastAPI service
  - added MCP, tool-provider, Tavily, skill, prompt-composition, secret, and
    namespace requirements
  - divided Phase 5 into independently validated subphases with files,
    validation, hardware risk, and documentation gates
- `InstallationGuide.md`
  - added a clearly marked future Phase 5 extension appendix
  - documented default Tavily enrollment, secret handling, health, discovery,
    and harmless search testing
  - documented generic remote and local MCP server formats and management
  - documented the complete agent-skill directory, JSON manifest,
    instructions, examples, validation, simulation, installation, removal, and
    troubleshooting workflow
- `DevelopmentGuide.md`
  - added the planned tool-provider contract, MCP trust boundary, skill
    confinement, prompt ordering, and required test suites
- `README.md`
  - clarified that Phase 5 is planned rather than currently implemented
  - summarized the approved Ollama, Tavily, MCP, skill, CLI, and web direction

### Rationale

The existing provider-neutral `ToolDefinition` and planned tool registry are a
sound base, but the older plan assumed only IDE-generated tools and no first
release HTTP service. Adding explicit tool-provider, MCP lifecycle, namespace,
trust, secret, and skill contracts now prevents future web search or Maps tools
from forcing a new agent loop or bypassing the IDE boundary.

Tavily was selected over the community DuckDuckGo MCP server because Tavily
maintains an official hosted MCP server designed for real-time agent search and
currently offers 1,000 free monthly API credits without requiring a credit
card. The project will not bundle a shared key, and external service terms or
quotas are not treated as project guarantees.

### Validation

- managed-driver verification: passed; 222 tracked files across six drivers
  match the import baseline plus 25 authorized repairs
- Python compilation: passed
- Ruff lint: passed
- Ruff format check: passed; 61 files already formatted
- strict mypy: passed for 34 source files
- pytest: passed; 213 tests
- documentation contradiction search: passed after removing old no-HTTP and
  pending-Phase-4 statements
- `git diff --check`: passed before the log update and will be repeated in the
  final documentation gate

### Raspberry Pi status

No GPIO, PWM, I2C, SPI, servo, sensor, display, buzzer, camera, microphone,
Ollama, web server, or external MCP tool was opened or executed. This task
changes approved plans and future setup documentation only. Tavily and the
documented `ninjarobot-agent` commands require Phase 5 implementation and
Raspberry Pi validation before the guide's planned-feature notice can be
removed.

### Follow-up

Review and approve the fully revised Phase 5 plan, then implement Phase 5.0
through Phase 5.7 in order. After each subphase, pass the complete quality gate
and immutable-driver verification before continuing.

## 2026-07-28 — Beginner installation and configuration-sync guide

### Summary

Reorganized the installation documentation into one complete workflow for a
new Raspberry Pi 5. Raspberry Pi OS Lite 64-bit is now the default
recommendation because the command-line-only system avoids desktop overhead
and leaves more memory and processing capacity for robot control and future
local AI models.

The guide now proceeds in this order:

1. install and preconfigure Raspberry Pi OS Lite 64-bit
2. configure I2C, SPI, GPIO12/GPIO13 hardware PWM, and system packages
3. clone and install NinjaRobotPi5 with the locked hardware environment
4. initialize and calibrate all six standalone `pi5*` modules
5. preview, apply, validate, and maintain the private IDE configuration
6. run simulation, safe health checks, and progressively riskier physical tests

### Files changed

- `InstallationGuide.md`
  - added the project, hardware, software, and directory overview
  - added copy-paste-ready headless Raspberry Pi OS Lite installation
  - documented explicit canonical configuration paths for every standalone
    hardware tool
  - separated the streamlined installation from testing and troubleshooting
  - added configuration ownership, resynchronization, update, and uninstall
    references
- `README.md`
  - made the complete installation guide the entry point for new Pi users
  - recorded why Lite 64-bit is preferred for the local-AI target
- `DevelopmentGuide.md`
  - documented preview-first import, explicit destinations, overwrite
    behavior, configuration ownership, and the fields imported from each
    standalone module

### Rationale

Some standalone tools default to JSON files in the current working directory,
while the integrated IDE prefers the corresponding files under
`~/.config/pi5*`. That difference allowed a correctly calibrated
project-root `servo.json` or configured `buzzer.json` to be missed in normal
IDE discovery. The installation now passes every standalone configuration
path explicitly and explains that standalone JSON and integrated TOML files
are not continuously synchronized.

### Validation

- managed-driver verification: passed; 222 tracked files match the baseline
  plus 25 authorized repairs
- Python compilation: passed
- Ruff lint: passed
- Ruff format check: passed; 61 files already formatted
- mypy strict type check: passed for 34 source files
- pytest: passed; 213 tests
- documentation whitespace and local-link checks: passed
- `git diff --check`: passed

### Raspberry Pi status

No hardware was opened or moved because this was a documentation-only change.
The documented commands were checked against the current command help and
configuration-import implementation. A clean-device walkthrough on Raspberry
Pi OS Lite 64-bit remains the recommended final operator validation.

### Follow-up

Perform the new guide from a freshly imaged card, record any prompts that
differ on the current Raspberry Pi OS release, and keep all module JSON files
at the documented canonical paths.

## 2026-07-27 — Phase 4 animated-face, distance, and IDE-tool refinement

### Summary

- Changed integrated movement safety so a measured value above 100 mm or the
  exact VL53L0X raw `8191` out-of-range sentinel counts as silent clear space.
  The public distance capability still reports `DEVICE_OUT_OF_RANGE` instead
  of publishing `8191` as a real millimetre measurement. Generic null values,
  I2C communication errors, timeouts, disconnects, and stale samples continue
  to block guarded startup.
- Independently implemented 20 scalable animated face renderers inside
  `ninjarobot_pi5_ide`: Idle, Happy, Laughing, Sad, Cry, Angry, Surprising,
  Sleepy, Speaking, Shy, Scary, Exciting, Confusing, Greeting, Listening,
  Thinking, Curious, Success, Warning, and Error. The immutable historical
  checkout remains unmodified and is neither imported nor packaged.
- Expanded the read-only behavior catalog. Every face has a semantically
  matched existing buzzer melody; normal movements combine face and drive
  without buzzer sound. Added guarded Celebrate and non-moving Error Warning
  combinations.
- Made face rendering frame-based for its whole active lifetime. Interactive
  faces loop until replaced, stopped, or the tool exits. Scriptable behavior
  stays finite unless `--loop` is selected, and simulation always applies a
  time bound.
- Added a persistent red octagonal Emergency Stop screen. Level 2 still stops
  servos and sensors and silences the buzzer. Interactive Resume reconstructs
  stopped device boundaries, runs health checks, clears safety state only on
  success, shows Idle, and never restarts the previous movement.
- Replaced the original prompt-only IDE menu with a Blessed-style direct
  control interface. It now has the approved seven main choices, nested face,
  movement, and special menus, clear explanations, Back in every submenu, and
  an Emergency Stop shortcut throughout.
- Added guided creation, private behavior listing/running/deletion, and a
  hardware-free simulation browser. Existing scriptable commands remain
  available; `behavior delete --confirm` and final-face `behavior run --loop`
  were added.
- Fixed the friendly Click command group so a normal `--help` exit no longer
  appears as `Error: 0`.

### Hardware impact

The implementation and automated validation did not initialize GPIO
(general-purpose input/output), PWM (pulse-width modulation), I2C, SPI, motors,
sensors, camera, microphone, display, or buzzer hardware. Physical behavior
changes affect the next Raspberry Pi test: open-space `8191` samples can now
complete the forward startup gate, faces animate continuously, interactive
selections execute directly, and Emergency Stop displays the new sign.

### Validation

- Focused distance, safety, face, asset, runtime, and CLI tests pass.
- The complete root suite passes with 213 tests.
- Compilation, Ruff lint, Ruff format checking, strict mypy, dependency-lock
  validation, and `git diff --check` pass.
- Immutable-driver verification passes before and after every phase: 222
  tracked files across six libraries match the baseline plus 25 authorized
  repairs.
- No managed `pi5*` file changed. Reference hashes for the inspected
  historical expression files remained unchanged.
- The 320×240 Emergency Stop frame was visually inspected.

### Raspberry Pi status

The operator previously reported the original Phase 4 checklist passed. The
new behavior refinements are software-complete and await the ordered physical
checklist in
`docs/validation/phase-4-refinement-validation-2026-07-27.md`. Begin with
simulation and non-moving checks. Keep both wheels raised and a second terminal
ready before any actuator-moving test. Do not intentionally induce
undervoltage, disconnect a powered sensor, or freeze the operating system.

### Recommended next step

Run the refinement checklist one section at a time, record the pass/fail boxes,
and stop at the first unexpected movement, traceback, failed health probe, or
managed-driver verification error.

## 2026-07-27 — Editable managed-driver installation repair

### Summary

- Changed all six root `pi5*` path dependencies from copied directory installs
  to editable installs.
- Added `scripts/verify_workspace_driver_sources.py`, which safely confirms
  that Python resolves each managed package into this checkout without
  importing or initializing hardware.
- Added regression tests for both `pyproject.toml` and `uv.lock` so a managed
  driver cannot silently return to non-editable installation.
- Added the source-origin check to the Raspberry Pi camera bootstrap and the
  Phase 4 installation gate.

### Cause

The repaired buzzer source was present in the Raspberry Pi test checkout, but
its virtual environment still contained the previous non-editable wheel.
Because the package version and package metadata were unchanged, an ordinary
frozen synchronization did not rebuild the local dependency after only its
Python source changed. Physical testing therefore executed the old global
GPIO-cleanup implementation.

### Hardware impact

None. This repair changes only how the root environment links local packages.
It does not initialize GPIO, PWM, I2C, SPI, motors, sensors, camera, microphone,
display, or buzzer hardware.

### Validation

- Root compilation, Ruff lint, Ruff formatting, strict mypy, lock validation,
  shell syntax validation, and all 156 tests pass.
- Immutable-driver verification passes for 222 tracked files and 25 authorized
  repairs.
- The runtime-source verifier passes for all six managed libraries.
- A clean temporary workspace created a new virtual environment from the
  frozen lock, resolved every managed library into that copied checkout, and
  executed the repaired pin-scoped buzzer source.

### Raspberry Pi status

Repeat the non-moving greeting cross-terminal stop only after the runtime-source
verifier confirms that all six managed packages resolve into the fresh
checkout. Do not resume motor tests until no destructor traceback appears.

## 2026-07-26 — Deterministic shared-GPIO shutdown repair

### Summary

- Repaired the managed `pi5buzzer` Raspberry Pi backend so cleanup releases
  only the buzzer's configured GPIO pin instead of closing the process-wide
  `rpi-lgpio` chip handle shared with the display.
- Made tone waiting interruptible so Ctrl+C and cross-terminal behavior stop
  finish the buzzer worker before releasing its PWM object.
- Preserved all existing CLI commands, melodies, tone behavior, servo
  functions, display functions, and two-level stop results.
- Recorded both managed-driver changes in the authorized repair manifest.
- Clarified the Phase 4 calibration path and cross-terminal stop expectations.

### Cause

The physical Phase 4 test stopped the robot successfully, but the buzzer PWM
object's destructor ran after an unscoped `GPIO.cleanup()` had set the shared
`rpi-lgpio` handle to `None`. Its second defensive stop then printed an ignored
`TypeError`. The repair uses pin-scoped cleanup, which releases GPIO27 without
invalidating other GPIO-backed devices.

### Validation

- Standalone buzzer driver tests: 31 passed.
- Integrated buzzer, behavior-runtime, and safety tests: 22 passed.
- Ruff lint and formatting pass for the repaired driver and regression tests.
- Immutable-driver verification passes with 222 tracked files and 25
  authorized repairs.
- Root compile validation, Ruff lint, Ruff formatting, strict mypy, and all 154
  root tests pass.
- All 66 standalone `pi5buzzer` tests pass with its Ruff lint and formatting
  checks.

### Raspberry Pi status

The reported cross-terminal stop reached Level 2 with no cleanup errors, but
the destructor traceback makes that original run a documentation-level fail.
Repeat the updated non-moving and raised-wheel stop checks with no traceback.

### Follow-up

Run the updated Phase 4 cross-terminal stop test and confirm Terminal A contains
the Level 2 result and `Aborted!` but no `Exception ignored` or `TypeError`.

## 2026-07-26 — Phase 4.4 integrated IDE tool and Phase 4 completion

### Summary

- Added the `ninjarobot-ide-tool` console entry point with both an interactive
  menu and scriptable subcommands.
- Added configuration-only and safe real hardware status, behavior catalog
  list/show/health, simulation, real execution, validation, private action
  creation, full stop, Level 1 resume, and health-gated Level 2 resume.
- Added read-only discovery and preview-first import of known standalone
  `pi5*` JSON settings. Applying an import creates an owner-private V4 TOML
  file and never rewrites a standalone source configuration.
- Added hardware-free display, buzzer, servo, and distance simulation drivers.
  Continuous simulated movement is always time-bounded.
- Added preview and explicit save confirmation for user-created actions.
  Private files are schema-validated, atomic, owner-only, confined to their
  directory, and cannot silently overwrite bundled or existing actions.
- Added active real-behavior registration with PID and Linux process-start
  token validation. A second `behavior stop` process requests Ctrl+C from the
  correct foreground behavior rather than trusting a reused PID.
- Added concise CLI error conversion so expected validation and safety failures
  do not print Python tracebacks.
- Updated README, installation guide, developer guide, implementation plan,
  and the Phase 4 Raspberry Pi validation procedure.

### Validation

- Added CLI tests for catalog inspection, simulation, physical confirmation
  gates, private action creation, friendly failures, interactive exit, latch
  resume, and TOML round-trip.
- Added configuration import tests proving supported field mapping, unchanged
  source JSON, valid private output, mode `0600`, and no silent overwrite.
- Added active-process registry permission and ownership tests.
- The complete V4 suite passes with 154 tests.
- Root compilation, Ruff lint, Ruff formatting, strict mypy, dependency lock,
  and diff validation pass.
- Managed-driver provenance remains 222 tracked files and 23 authorized
  repairs. No `pi5*` file changed during Phase 4.

### Raspberry Pi status

All Phase 4 implementation validation used deterministic simulation. Physical
expressions and wheel movement are deliberately deferred to the ordered
operator checklist. The first real motor checks must use raised wheels and a
second terminal prepared with `behavior stop`.

### Follow-up

Run and record the Phase 4 Raspberry Pi checklist. After physical approval,
begin Phase 5 bounded agent-core work without giving the agent direct driver
access.

## 2026-07-26 — Phase 4.3 guarded continuous movement and two-level stop

### Summary

- Added coordinated GPIO12/GPIO13 movement through the existing
  calibration-gated `ServoDevice` boundary. No integrated code imports or
  bypasses the managed servo driver.
- Added logical `left_motor` and `right_motor` resolution for the approved
  forward, backward, left-turn, and right-turn targets.
- Added three valid clear readings before front-guarded movement can start.
- Added a 100 mm front obstacle rule that requires three consecutive low
  readings before a Level 1 motion stop. The threshold remains configurable
  but cannot be lower than 50 mm.
- Preserved the owner's selected policy that invalid, missing, or stale
  distance samples produce warnings and do not stop a movement already in
  progress. A guarded movement still cannot start without valid clear samples.
- Added rear-coverage warnings for backward movement and side/rear-coverage
  warnings for turns.
- Added Level 1 stops for front obstacles, current undervoltage, and a
  thread-backed software watchdog. The watchdog directly requests zero pulse
  even when the asyncio event loop is frozen.
- Added Level 2 cleanup for Ctrl+C/shutdown/operator-stop integration and
  latched driver failure: stop servos, stop ranging, close camera and
  microphone devices, silence the buzzer, and show `SYSTEM STOPPED`.
- Added owner-private atomic safety state. Motion resumes through explicit
  confirmation; a driver-failure system latch requires confirmation plus
  healthy device probes.
- Kept every managed `pi5*` source file unchanged.

### Validation

- Added tests for group-motion gates and calibrations, exact approved motor
  targets, clear-start checks, obstacle debounce, warning-only invalid samples,
  undervoltage, watchdog event-loop freeze, long asynchronous servo ramps,
  Level 1 resume, Level 2 cleanup, system latching, health-gated resume, state
  corruption, atomic storage, and owner-only permissions.

### Follow-up

Implement Phase 4.4 `ninjarobot-ide-tool`, including interactive and scriptable
behavior, status, safe import, action creation, stop, and resume workflows.

## 2026-07-26 — Phase 4.2 coordinated expressions and robot assembly

### Summary

- Added a V4 `RobotAssembly` that owns and shares one configured display and
  buzzer instance.
- Added procedural Pillow face rendering for the approved idle, happy,
  thinking, success, warning, and error expressions.
- Added sequential behavior stages whose operations run concurrently within
  each stage. This makes the greeting text and existing happy melody begin
  together after the initial happy-face stage.
- Added a narrowly scoped melody loader that reads the existing
  `pi5buzzer.notes` definitions without importing its command-line or runtime
  layers.
- Added expression cancellation, buzzer cleanup after cancellation or device
  failure, health reporting, and idempotent assembly cleanup.
- Added an image-frame method to the shared display device so integrated
  behavior never creates a second SPI display instance.
- Kept movement execution closed until the Phase 4.3 safety controller is
  active.

### Validation

- Added tests for every procedural face, sequential/concurrent stages,
  cancellation, forced display failure, shared assembly health, cleanup, and
  movement rejection before the safety layer.

### Follow-up

Implement Phase 4.3 continuous-rotation drive execution, obstacle monitoring,
watchdog and undervoltage motion stops, and full-system cleanup/latching.

## 2026-07-26 — Phase 4.1 behavior contracts and secure catalog

### Summary

- Added strict, immutable schemas for expression and movement behaviors,
  sequential stages, concurrent stage operations, colors, text, faces,
  existing buzzer melodies, waits, logical servo roles, and bounded targets.
- Added read-only bundled behaviors for `idle`, `greeting`, `happy`,
  `thinking`, `success`, `warning`, `error`, `move_forward`,
  `move_backward`, `turn_right`, and `turn_left`.
- Preserved `stop` as a safety command instead of treating it as an ordinary
  behavior asset.
- Added a confined user behavior repository with validated names, symbolic-link
  rejection, owner-only files, atomic writes, and no silent overwrite.
- Changed the default robot servo topology to GPIO12 and GPIO13 while retaining
  explicit support for the four DFR0566 PWM endpoints in custom configurations.
- Mapped `left_motor` to GPIO12 and `right_motor` to GPIO13 in V4 configuration,
  rather than embedding hardware endpoints in behavior assets.
- Normalized the VL53L0X and DFR0566 shared I2C resource name to `i2c1`.
- Kept every managed `pi5*` file unchanged.

### Validation

- Added catalog, path traversal, symbolic-link, filename mismatch, schema,
  motion-map, permissions, and no-overwrite tests.
- Updated configuration and servo compatibility coverage for the two-endpoint
  default and optional custom topology.

### Follow-up

Implement Phase 4.2 robot assembly, procedural faces, and concurrent display
and buzzer expression execution.

## 2026-07-26 — Phase 3 physical validation closed

### Summary

- Recorded the operator's confirmation that every Phase 3.5 microphone test
  passed.
- Marked all Phase 3 device integrations and their physical validation
  complete.
- Cleared the Phase 4 entry gate without changing any runtime or managed
  driver file.

### Validation

- Managed-driver provenance passed with 222 tracked files and 23 authorized
  repairs.
- No physical hardware was accessed during this documentation-only close-out.

### Follow-up

Implement the approved Phase 4 integrated behavior system one validated
subphase at a time.

## 2026-07-26 — Phase 3.5 privacy-bounded microphone adapter

### Summary

- Added `microphone.status`, a read-only capability that discovers and
  validates the selected USB input without recording audio.
- Added `microphone.capture`, a confirmation-required privacy capability for
  one bounded mono WAV recording.
- Kept simulation as the default and required both `--real` and
  `--confirm-microphone` for physical recording.
- Enforced default non-retention. Explicit retention saves only owner-readable
  files inside the configured private microphone directory.
- Added duration bounds, safe filename validation, directory confinement,
  no-overwrite behavior, secure staging, SHA-256 metadata, and cleanup after
  success, failure, timeout, or cancellation.
- Serialized the `microphone` resource and preserved durable non-idempotent
  action replay.
- Added the managed `pi5mic` package to the root hardware dependency group
  without changing any managed driver file.
- Added a V4-owned device-only loader that bypasses `pi5mic` package exports
  and loads only errors, models, audio backend, device discovery, and recorder
  modules.
- Kept transcription, Gemini, wake-word detection, listener state, transport,
  presence, and OpenClaw outside the Phase 3.5 runtime.
- Recorded the operator-reported Phase 3.4 camera checklist as PASS.

### Files and documentation

- Added `ninjarobot_pi5_ide/.../microphone.py` and its focused tests.
- Extended the unified CLI, V4 configuration, root hardware dependency lock,
  capability listing, and CLI tests.
- Updated README, InstallationGuide, DevelopmentGuide, this log, hardware
  profile, and managed-driver containment matrix.
- Added the Phase 3.5 Raspberry Pi validation report with separate simulation,
  interface, privacy-sensitive recording, expected-result, checklist, and
  rollback sections.

### Validation

- All 109 V4 tests passed.
- All 36 focused microphone, configuration, and CLI tests passed.
- Strict mypy passed for 23 V4 source files.
- Root compilation, Ruff lint, Ruff formatting, dependency lock, and diff
  validation passed.
- All 449 managed-library tests passed. The only warning was the inherited
  Python `audioop` deprecation in `pi5mic`.
- Root and all six managed libraries passed Ruff lint and format checks.
- Driver provenance remained at 222 tracked files and 23 authorized repairs.
- Runtime containment loaded exactly seven approved `pi5mic` namespace/module
  names and no historical or voice-processing module.

### Raspberry Pi status

Safe interface validation is PASS. ALSA identifies `USB PnP Sound Device` at
card 0/device 0. Real V4 health reports both microphone capabilities ready,
and status selects that device without recording. The device rejects the
requested 16 kHz input and the managed driver safely selects 44.1 kHz; V4
reports both values and the fallback warning.

No real recording was made during implementation. The physical transient and
retained WAV checklist remains pending because it requires consent from
everyone nearby.

### Follow-up

Run and review the Phase 3.5 Raspberry Pi checklist. Do not begin Phase 4
integrated robot behaviors until the microphone result is reviewed.

## 2026-07-26 — Phase 3.4 camera interpreter-bridge correction

### Summary

- Reproduced the operator's `ModuleNotFoundError` for `picamera2` and
  `libcamera`.
- Confirmed that the first bootstrap created a system-Python environment but
  `uv sync` replaced it with the project-pinned Python 3.11 environment.
- Kept the normal locked project environment and added a V4-only bridge that
  probes and runs managed `pi5camera` through Raspberry Pi OS
  `/usr/bin/python3`.
- Restricted the bridge to the exact local `pi5camera/src` directory. This
  prevents Python 3.13 from loading compiled Python 3.11 packages such as
  NumPy from `.venv`.
- Replaced the bootstrap workflow so it never moves, deletes, or recreates
  `.venv`.
- Kept every managed `pi5*` source file unchanged.

### Validation

- Driver provenance passed before implementation: 222 tracked files and 23
  authorized repairs.
- Twelve focused camera adapter tests pass, including the exact missing
  Picamera2 fallback, bounded subprocess environment, dual-interpreter error,
  and bootstrap no-replacement regression.
- Raspberry Pi OS `/usr/bin/python3` imports `libcamera` and `picamera2`.
- Safe real camera health reports `camera.capture` and `camera.status` ready.
  Health does not open the camera or take a photograph.
- All 96 V4 tests and all 35 focused camera, configuration, and CLI tests
  pass.
- Strict mypy passes for 22 source files. Root and all six managed libraries
  pass Ruff lint and format checks.
- All 449 managed-library tests pass. The only warning is the inherited
  `audioop` deprecation from `pi5mic`.
- The physical capture checklist remains pending because implementation
  validation intentionally did not take a photograph.

### Operator note

The failed capture action stored in the old ledger is durable. Retesting must
use a fresh ledger or new action and idempotency identifiers. Idempotency means
that replaying the same identifier returns the stored result rather than
performing the operation again.

## 2026-07-26 — Phase 3.4 privacy-bounded camera adapter

### Summary

- Added `camera.status`, a read-only readiness and retention-policy capability
  that never takes a photograph.
- Added `camera.capture`, a confirmation-required privacy capability for one
  1280×720 JPEG through the managed `pi5camera` capture path.
- Kept simulation as the default and required both `--real` and
  `--confirm-camera` for physical capture.
- Enforced default non-retention through V4 configuration. Explicit
  `--retain` saves only owner-readable files inside the configured private
  camera directory.
- Added filename validation, directory confinement, no-overwrite behavior,
  secure staging, SHA-256 metadata, and cleanup after success, failure,
  timeout, or cancellation.
- Serialized camera ownership and waited for worker-thread cleanup before
  returning a timeout or cancellation.
- Added the managed `pi5camera` package to the root hardware dependency group
  without changing any managed driver file.
- Added the initial Raspberry Pi workspace bootstrap for the system-provided
  Picamera2/libcamera Python environment. The correction above replaces its
  environment-replacement design with the permanent interpreter bridge.

### Validation

- All 92 V4 tests passed.
- The 31 focused camera, configuration, and CLI tests passed.
- Camera tests cover simulated status/capture, default non-retention, explicit
  private retention, no overwrite, path traversal rejection, dependency
  failure, failure cleanup, timeout cleanup, cancellation cleanup, and
  serialized access.
- All 449 managed-library tests passed. The only warning was the inherited
  Python `audioop` deprecation in `pi5mic`.
- Root compilation, Ruff lint, Ruff format, strict mypy for 22 source files,
  dependency lock, CLI smoke, bootstrap syntax, and `git diff --check` passed.
- Driver provenance remained at 222 files and 23 authorized repairs.

### Raspberry Pi status

No real camera capture was run during implementation. The Raspberry Pi OS
system Python imports Picamera2, while the root Python 3.11 environment does
not. The correction above now handles that verified environment boundary
without altering `pi5camera`.

The operator reports that every physical Phase 3.4 checklist item passed,
including transient and retained capture, owner-only file permissions,
no-overwrite behavior, visual inspection, cleanup, and device isolation.

### Follow-up

Proceed to the approved Phase 3.5 microphone integration.

## 2026-07-26 — Phase 3.3 six-servo mixed-backend adapter

### Summary

- Expanded V4 configuration to the fixed `gpio12`, `gpio13`, and
  `hat_pwm1`–`hat_pwm4` topology.
- Added a calibration-file reference, a default-off real-motion gate, and a
  permanently disabled Phase 3.3 group-motion gate.
- Added one shared servo service that lazily selects `pi5servo`'s mixed
  hardware-PWM/DFR0566 backend without changing the managed library.
- Added read-only `servo.status`, confirmation-required single-endpoint
  `servo.move`, and lock-free emergency `servo.stop` capabilities.
- Required valid explicit endpoint calibration before real movement and
  checked endpoint-specific angle limits before sending a center pulse.
- Added cancellation and emergency shutdown that abort movement and sets all
  six outputs to zero.
- Added simulation-first and explicit-real CLI paths. Real movement also
  requires `--confirm-motion`; `--hold` is bounded to five seconds.
- Added `pi5servo[pi]` to the root hardware dependency group.

### Validation

- All 81 V4 tests passed, including topology validation, disabled-motion and
  missing-calibration gates, endpoint limits, center-first movement,
  cancellation, emergency stop, unavailable backends, CLI confirmation, and
  action-result semantics.
- The 30 focused servo/configuration/CLI tests passed.
- All 449 managed-library tests and every package-local Ruff gate passed. The
  only warning was the inherited Python `audioop` deprecation in `pi5mic`.
- Root compilation, Ruff lint, Ruff format, strict mypy for 21 source files,
  dependency lock, CLI smoke, and `git diff --check` passed.
- Driver provenance remained at 222 files and 23 authorized repairs.

### Raspberry Pi status

No PWM, I2C, servo pulse, calibration, or movement command was run during
implementation. The operator subsequently reported that all Phase 3.3 manual
tests passed. No command transcript, electrical table, or measured values were
attached to that report, so the validation document records an
operator-reported pass without inventing detailed evidence.

### Follow-up

The Phase 3.3 operator review is complete. Proceed with Phase 3.4 camera
integration.

## 2026-07-26 — Phase 3.2 ST7789V display adapter

### Summary

- Added one shared, SPI-serialized display service with lazy `pi5disp` loading.
- Added idempotent `display.show_text`, `display.clear`, and
  `display.set_brightness` capabilities.
- Passed SPI0 device 0, DC GPIO4, reset GPIO5, backlight GPIO6, 32 MHz,
  240×320 dimensions, rotation 90°, and initial brightness 75% from V4-owned
  configuration.
- Added Pillow-based RGB text rendering with bounded text length, font size,
  hexadecimal colors, fit checking, and centered multiline placement.
- Added simulated and explicit-real CLI health, text, clear, and brightness
  commands. The optional `--hold` value keeps a real visual test visible before
  deterministic cleanup.
- Added `pi5disp[pi]` to the root hardware dependency group without changing
  the managed library.
- Hardened partial startup cleanup so a constructed driver is closed if
  backlight initialization fails.

### Validation

- All 66 V4 tests passed, including exact driver settings, RGB-frame size,
  shared lifecycle, SPI resource declarations, bounded arguments, partial
  startup failure, write failure, CLI simulation, and CLI hold bounds.
- The 19 focused display/CLI tests passed.
- All 449 managed-library tests and every package-local Ruff gate passed. The
  only warning was the inherited Python `audioop` deprecation in `pi5mic`.
- Root compilation, Ruff lint, Ruff format, strict mypy for 20 source files,
  dependency lock, CLI smoke, and `git diff --check` passed.
- Driver provenance remained at 222 files and 23 authorized repairs.

### Raspberry Pi status

No SPI or physical display command was run during implementation. The operator
subsequently reported the complete checklist as passing. Attached output
confirms real red and blue frames, centered 320×240 text at rotation 90,
25%/75% brightness changes, safe retry classification, and real rather than
simulated execution. Green was visually confirmed by the operator, although
its JSON output was not included in the transcript.

### Follow-up

The Phase 3.2 Pi checklist is complete and passed. Phase 3.3 may proceed.

## 2026-07-26 — Phase 3.1 GPIO27 buzzer adapter

### Summary

- Added a shared buzzer device service with lazy `pi5buzzer` loading.
- Added bounded `buzzer.play_tone` and emergency `buzzer.stop` capability
  descriptors.
- Limited tones to 20–20,000 hertz, 0.05–2 seconds, and volume 1–128.
- Added cancellation-safe shutdown and an emergency stop path that does not
  wait for the normal playback resource lock.
- Added simulated and explicit-real CLI health, play, and stop commands.
- Added `pi5buzzer[pi]` to the root hardware dependency group without changing
  the managed library.
- Corrected successful non-idempotent action results to report retry safety
  `unsafe`.

### Validation

- All 56 V4 tests passed, including bounded arguments, unavailable GPIO,
  cancellation, concurrent emergency stop, CLI simulation, and action-result
  semantics.
- All 449 managed-library tests and every package-local Ruff gate passed.
- Root compilation, Ruff lint, Ruff format, strict mypy, CLI smoke, dependency
  lock, and `git diff --check` passed.
- Driver provenance remained at 222 files and 23 authorized repairs.

### Raspberry Pi status

No real GPIO or audible command was run during implementation. The operator
subsequently reported the complete Phase 3.1 checklist as passing, including
the electrical prerequisite, real GPIO27 health, quiet 440 Hz and 660 Hz
tones, emergency silence, duplicate protection, and GPIO release.

### Follow-up

The Phase 3.1 Pi checklist is complete and passed. Phase 3.2 may proceed.

## 2026-07-26 — Phase 2 IDE core and VL53L0X reference adapter

### Summary

- Added capability registration, explicit adapter lifecycle, bounded
  scheduling, deterministic resource locks, and a durable SQLite action
  ledger.
- Added an execution engine that prevents duplicate action execution and
  records deadlines, queue rejection, timeout, cancellation, unexpected
  failures, and restart-time unknown outcomes.
- Added the read-only `distance.read` adapter. It lazily loads the unchanged
  `pi5vl53l0x` package only for real execution and normalizes its output into
  the Phase 1 action-result contract.
- Added an explicit guard that reports `8191 mm` as
  `DEVICE_INVALID_READING`; it can no longer look like a successful distance.
- Added hardware-free capability, health, simulated distance, idempotency, and
  action-ledger CLI paths. Real I2C use requires `--real`.
- Added the root `hardware` extra so the local managed VL53L0X package can be
  installed without changing that package.

### Validation

- Registry rollback, ledger persistence, resource races, bounded queues,
  cancellation, deadlines, idempotency, timeouts, unknown outcomes, restart
  recovery, adapter lifecycle, invalid readings, and CLI persistence are
  covered by automated tests.
- Compilation, Ruff lint, Ruff formatting, strict mypy, root pytest, all
  package-local managed-driver tests, and immutable-driver verification passed.
- Driver provenance remained at 222 files and 23 authorized repairs. No
  `pi5*` file changed.

### Raspberry Pi status

No physical hardware command was run during implementation. Operator
validation subsequently passed on I2C bus 1 at address `0x29`: all 10 requested
actions succeeded, distances ranged from 48 mm to 149 mm, each raw value
matched its normalized value, and no `8191 mm` sentinel appeared. The earlier
physical failure is cleared, although its hardware root cause was not
established.

### Follow-up

Run the Phase 2 Raspberry Pi checklist. Begin Phase 3 with the buzzer adapter
only after Phase 2 review and separate approval.

## 2026-07-26 — Phase 1 contracts and package skeletons

### Summary

- Added installable `ninjarobot_pi5_ide` and `ninjarobot_pi5_agent` workspace
  packages plus the unified `ninjarobot_pi5_cli`.
- Added strict, serializable capability, action, result, error, provider, tool,
  session, memory, health, and configuration contracts.
- Added deterministic fake IDE/provider/clock/ID helpers that cannot access
  hardware.
- Added V4-owned hardware configuration with GPIO12/GPIO13 servos, GPIO27
  buzzer, ST7789V DC4/RST5/BL6, rotation 90°, and brightness 75%.
- Accepted ADRs for Pydantic v2 boundary validation and strict mypy typing.
- Added import-boundary tests preventing agent imports of `pi5*`, OpenClaw, or
  the historical runtime.

### Validation

- Phase 1 compilation, Ruff lint, Ruff format, and strict mypy passed.
- All 30 V4/root tests passed in the final full regression gate.
- All 447 managed-library tests and every package-local Ruff gate passed after
  Phase 1, confirming no driver regression.
- CLI version, help, configuration validation, module execution, schema, and
  simulated dry-run paths passed.
- Driver provenance remained at 222 files and 23 authorized repairs.

### Raspberry Pi status

Phase 1 contains contracts and fakes only. No GPIO, PWM, I2C, SPI, camera,
microphone, buzzer, display, sensor, or servo operation was performed.

### Follow-up

Phase 2 may implement the IDE registry, execution engine, action ledger,
resource locks, and the first read-only adapter after separate approval.

## 2026-07-26 — Phase 0 exit reconciliation

### Summary

- Revalidated all managed libraries without changing their current functions.
- Corrected the V4-owned hardware record to GPIO12/GPIO13 servos, GPIO27
  buzzer, and the 240×320 ST7789V display on DC4/RST5/BL6 with rotation 90°
  and brightness 75%.
- Excluded private runtime configuration, captured photos, and recognition data
  from the V4 Git repository.
- Reconciled the historical Phase 0 baseline with the current authorized-driver
  state.

### Validation

- All 447 managed-library tests passed.
- All 7 root governance tests passed.
- Compilation, Ruff lint, Ruff format, immutable-driver provenance, and
  `git diff --check` passed.
- The driver verifier reported 222 files and 23 authorized repairs.

### Raspberry Pi status

No hardware command was executed during this reconciliation. GPIO27 buzzer and
DC4/RST5/BL6 display wiring are recorded but remain pending adapter-phase
hardware validation.

### Follow-up

Proceed with Phase 1 contracts, fakes, configuration, packages, and the unified
CLI without importing or editing any managed driver.

## 2026-07-26 — Correct native Pi PWM channel routing

### Summary

- Corrected `pi5servo` so GPIO12/GPIO18 map to hardware PWM0 and GPIO13/GPIO19
  map to hardware PWM1.
- Added a guard that rejects selecting both alternate pins for one PWM channel.
- Corrected the `pi5servo` setup documentation: the standard `pwm-2chan`
  overlay provides two independent servo signals, not four.
- Preserved local servo calibration and VL53L0X offset files as runtime data in
  the driver-provenance verifier; they are not library source files.

### Validation

- Automated tests validate the alternate-pin mapping and duplicate-route guard.
- The Raspberry Pi validation remains non-moving until an operator supplies
  correctly rated external servo power and has an accessible power disconnect.

### Follow-up

For four independently controlled servos, use DFR0566 PWM0–PWM3 with a
properly rated external servo supply.

## 2026-07-25 — standalone Pi5 library documentation and runtime-data policy

### Summary

- Updated all six managed-library README files to describe standalone source
  folders rather than requiring NinjaRobotPi5 or NinjaClawBot.
- Added frozen-environment guidance, CLI-first test paths, and servo lockfile
  safety guidance.
- Narrowed the provenance script so normal buzzer configuration and camera
  photos/face data are treated as runtime data, not immutable driver source.

### Validation

- Driver provenance passed after the change.
- Root Ruff lint and formatting checks passed.
- Repository governance tests passed.

### Raspberry Pi status

Documentation changes do not energize hardware. Manual CLI testing remains
subject to the existing buzzer/display confirmation, servo emergency-disconnect,
and VL53L0X invalid-reading limits.

## 2026-07-25 — pi5mic PortAudio and local STT repair

### Summary

- Installed PortAudio runtime/development packages.
- Built current whisper.cpp for Raspberry Pi 5 and downloaded the multilingual
  `ggml-base.bin` model.
- Registered the executable and model in
  `~/.config/pi5mic/mic.json`, keeping OpenClaw out of the validation path.

### Root cause

ALSA could capture from the USB microphone, but the Python `sounddevice`
backend could not load because the native PortAudio library was absent.
Local STT also lacked both the `whisper-cli` executable and a configured model.
No `pi5mic` source defect was reproduced.

### Validation

- Package compile, Ruff lint, Ruff format, and all 90 tests passed with one
  inherited Python 3.11 `audioop` deprecation warning.
- `pi5mic devices` listed four inputs including the USB PnP device.
- Library recording produced a five-second, 44.1 kHz, mono, 16-bit WAV with
  220,500 frames and no overflow; the temporary file was deleted.
- Doctor passed with only the expected automatic two-thread warning.
- Offline transcription of the whisper.cpp JFK sample returned the expected
  sentence using `ggml-base.bin`.

### Raspberry Pi status

Microphone capture and local speech-to-text are PASS. Automated recording was
very quiet because no operator speech was supplied during its fixed window.

### Follow-up

Proceed to the VL53L0X timing and calibration repair.

## 2026-07-25 — pi5camera Picamera2 environment and error repair

### Summary

- Installed Raspberry Pi OS `python3-picamera2` 0.3.36 and
  `python3-libcamera` 0.7.1.
- Created the camera environment with system Python 3.13 and
  `--system-site-packages`, then synced the frozen package lock.
- Changed capture, recognize, and enrollment commands to translate every
  package-level `CameraError` into a concise Click error.
- Added a regression proving a missing backend produces no traceback.

### Root cause

Native `rpicam-still` used the OS camera stack successfully, but the earlier
isolated Python 3.11 environment could not import ABI-specific Picamera2 and
libcamera modules installed for Raspberry Pi OS Python 3.13. In addition,
`capture_cmd` caught `CaptureError` but not its sibling
`BackendNotAvailableError`, allowing a traceback to escape.

### Validation

- Picamera2 enumerated one OV5647 camera.
- Camera compile, Ruff lint, Ruff format, and all 24 tests passed.
- `pi5camera doctor` passed with camera and recognition readiness.
- `pi5camera capture` saved a valid RGB 1280×720 JPEG with camera metadata; the
  temporary image was deleted afterward.
- Bootstrap shell syntax passed; ShellCheck is not installed.

### Raspberry Pi status

Camera capture is now a hardware PASS. Face enrollment was intentionally
skipped, as requested.

### Follow-up

Proceed to the USB microphone, PortAudio, and local whisper.cpp phase.

## 2026-07-25 — pi5disp runtime configuration repair

### Summary

- Moved the default writable configuration from the package directory to
  `~/.config/pi5disp/display.json`.
- Added `XDG_CONFIG_HOME` support, a `PI5DISP_CONFIG` override, automatic parent
  directory creation, and regression tests.
- Migrated the known-good rotation-0 configuration into the user runtime path
  without changing the tracked `pi5disp/display.json`.

### Root cause

`ConfigManager` calculated its default by walking four directories upward from
`config_manager.py`. In this source layout that path was the package root, so
`init`, `brightness`, and config writes modified source-controlled
`display.json`.

### Validation

- Package compile, Ruff lint, and Ruff format passed.
- All 65 tests passed, including two new path-selection regressions.
- Clear, 25% brightness, static text, scrolling text, image, and two-second
  animation commands completed on the ST7789V.
- The tracked display config retained SHA-256
  `374f1619c9ccb1c7a8d8aff8b6ded447a250893b9a099b8af6e33cf7639f1b16`.

### Raspberry Pi status

The display was cleared and its backlight set to 0% after validation. Command
execution passed; an operator still needs to confirm orientation, color, text,
and animation visually.

### Follow-up

Proceed to the Picamera2 environment and camera error-handling repair.

## 2026-07-25 — pi5servo DFR0566 GPIO/PWM correction

### Summary

- Confirmed the two test servos use the DFR0566 digital GPIO12/GPIO13
  breakouts, which route to native Raspberry Pi PWM channels 0 and 1.
- Verified the separate DFR0566 I2C controller identity at `0x10`, but did not
  treat that as validation of the digital servo signal path.
- Added the persistent `pwm-2chan` overlay and disabled conflicting analog PWM
  audio in `/boot/firmware/config.txt`; saved a dated backup beside it.
- Corrected the servo and root setup documentation.

### Root cause

The Pi exposed a PWM controller, but GPIO12 and GPIO13 were not muxed to PWM
because the required boot overlay was missing. Earlier status checks therefore
proved only that a PWM controller existed. A temporary runtime overlay changed
both pins to `PWM0_CHAN0`/`PWM0_CHAN1`, and a claim-only probe exported both
channels with `enable=0`, `duty_cycle=0`, and no pulse.

The backend intentionally leaves healthy sysfs PWM channels exported for reuse;
its tests cover that behavior. Attempting to hot-remove the temporary overlay
after export was not a supported validation path and left `dtoverlay -r`
waiting in the kernel. A reboot is required to clear that process and apply the
persistent configuration cleanly.

### Validation

- All 132 package tests passed.
- Package compile, Ruff lint, and Ruff format passed.
- DFR0566 identity registers returned PID `0xDF` and VID `0x10`.
- Native GPIO12/GPIO13 claim-only checks remained disabled at zero duty.
- Driver provenance passed with the documented README repair.

### Raspberry Pi status

No servo pulse, angle, movement, or calibration command was issued. Final
post-reboot pin-mux and claim-only validation remains pending. Actuator movement
continues to be blocked by the missing emergency disconnect.

### Rollback

Restore `/boot/firmware/config.txt.ninjarobotpi5-20260725.bak` over
`/boot/firmware/config.txt` and reboot.

### Follow-up

Continue with `pi5disp`; perform the servo post-reboot check before any future
movement test.

## 2026-07-25 — pi5buzzer reproducible validation repair

### Summary

- Pinned Ruff 0.15.5 and declared the package lint rules explicitly.
- Added a package lockfile and corrected one import-order violation exposed by
  the explicit rule set.
- Updated the package and root developer documentation.

### Root cause

`pi5buzzer` declared an unbounded Ruff development dependency and had no
lockfile. A fresh package-local sync selected Ruff 0.16.0 with a materially
different effective rule set, producing 23 errors even though the validated
Ruff 0.15.5 workflow passed. The runtime driver itself had no reproduced
functional failure.

### Validation

- Fresh frozen environment resolved Ruff 0.15.5.
- Compile, Ruff lint, and Ruff format passed.
- All 65 package tests passed.
- Driver provenance passed with four authorized `pi5buzzer` files.

### Raspberry Pi status

GPIO17 initialization and health checks passed. A 440 Hz tone and all 14
predefined emotion commands completed without exceptions, and GPIO17 returned
to input mode. Audible confirmation remains an operator observation.

### Follow-up

Proceed to `pi5servo` using DFR0566 digital GPIO12/GPIO13 and native hardware
PWM, without issuing an actuator-moving pulse.

## 2026-07-25 — Managed-driver repair authorization

### Summary

- Confirmed the attached expansion HAT is DFR0566.
- Confirmed that the temporary servos remain on DFR0566 digital GPIO12/GPIO13
  breakouts. They use native Raspberry Pi hardware PWM, not the HAT's dedicated
  I2C PWM0/PWM1 sockets.
- Replaced the copied-driver immutability rule with an audited managed-driver
  repair workflow while preserving the historical import hashes.
- Added a separate authorized-change manifest and provenance validation.

### Rationale

The project owner explicitly authorized fixing each standalone Pi5 library
after README review, Serena audit, failure reproduction, linting, tests, and
hardware validation. Keeping original and repaired hashes in separate manifests
preserves historical provenance without blocking validated repairs.

### Validation

The original 221-file import manifest matched with zero authorized repairs.
Compilation, Ruff lint, Ruff format, `git diff --check`, and all six root
governance tests passed.

### Raspberry Pi status

No actuator-moving command is authorized because the continuous-rotation
servos have no accessible emergency disconnect. DFR0566 communication and
non-moving checks may proceed.

### Follow-up

Repair and validate the six libraries one at a time, beginning with
`pi5buzzer`.

## 2026-07-25 — Phase 0 repository foundation

### Summary

- Confirmed the V4 architecture and phase ordering.
- Confirmed `/home/rogerchang/NinjaRobotPi5` as the new repository root.
- Classified nested `NinjaClawBot/` as an ignored, read-only code reference.
- Exported the six tracked Pi5 library trees without changing their contents.
- Added root project governance, documentation, validation, hardware, and ADR
  scaffolding.

### Rationale

The clean root prevents the OpenClaw runtime from becoming an accidental V4
dependency. Immutable driver copies preserve the already-tested hardware
contracts while all integration and containment work moves into V4-owned
middleware.

### Validation

The root gate passed with three governance tests. All six copied-driver suites
passed with 435 tests, and their native Ruff lint and format checks passed.
The 221-file immutable manifest matched before and after validation. Ruff is
pinned to 0.15.5 because 0.16 changes inherited package-configuration behavior;
upgrading it requires a separate review and must not trigger driver rewrites.
Full command output and the one inherited `audioop` deprecation warning are
summarized in `docs/validation/phase-0-baseline.md`.

### Raspberry Pi status

No physical hardware was accessed. Powered servo validation remains blocked
until the supply, current, protection, grounding, and emergency-disconnect
record is complete.

### Follow-up

After Phase 0 review, Phase 1 will add strict shared contracts and the initial
`ninjarobot_pi5_ide` and `ninjarobot_pi5_agent` package skeletons.

## 2026-07-25 — Pre-Phase-1 Raspberry Pi hardware validation

### Summary

- Exercised public standalone hardware paths for all six copied Pi5 libraries.
- Excluded OpenClaw integrations and face enrollment as requested.
- Used temporary configurations and deleted captured camera/audio media.
- Kept servo testing non-moving because no emergency disconnect is available.

### Results

- Buzzer GPIO health, tones, and all 14 predefined sounds completed.
- Display clear, brightness, text, image, and animation commands completed;
  visual confirmation remains pending.
- Direct GPIO and DFR0566 servo backend probes completed without movement.
- Native OV5647 capture passed, but `pi5camera capture` failed because
  Picamera2 is unavailable to its Python environment.
- Native USB microphone capture passed at 44.1 kHz, but `pi5mic` recording
  failed because PortAudio is missing; local Whisper is also unconfigured.
- VL53L0X identity reads passed, but driver initialization timed out during
  reference calibration.
- `pi5disp init --defaults` and brightness commands attempted to rewrite the
  immutable driver config. The manifest caught the changes and the original
  file was restored after the hardware backlight was turned off.

### Safety and rollback

No servo pulse or movement command was issued. The display was cleared with its
backlight set to 0%, relevant GPIO returned to safe states, the Pi remained
unthrottled, all temporary media was deleted, and all 221 immutable files
matched the Phase 0 baseline.

### Follow-up

Resolve the camera Python dependency, microphone runtime/STT setup, and VL53L0X
initialization failure. Add an accessible servo emergency disconnect before
movement validation. Full evidence is recorded in
`docs/validation/raspberry-pi-hardware-validation-2026-07-25.md`.

## 2026-07-25 — pi5vl53l0x timing and validation repair

### Summary

- Replaced incomplete measurement-timing calculations with the Pololu/ST
  sequence-step algorithm.
- Decoded VCSEL period registers before macro-period conversion.
- Added deterministic calibration cleanup and one bounded recovery attempt.
- Prevented CLI commands from reporting success for invalid range samples.
- Prevented calibration from saving an offset derived from sentinel data.

### Root cause

The driver passed raw VCSEL register encodings directly into macro-period
calculations, omitted TCC and DSS/MSRC timing stages, and used incorrect fixed
overheads. A timed-out calibration also left ranging state uncleared. After
those fixes, the live revision-`0x10` sensor consistently required one bounded
retry of phase calibration. The retry succeeds, but the connected module still
returns the `8191 mm` out-of-range sentinel at the reported 100 mm target.

### Validation

- Package compilation, Ruff lint, and Ruff format passed.
- All 71 package tests passed, including timing, VCSEL decoding, timeout
  cleanup/retry, invalid CLI status, and calibration rejection tests.
- I2C address `0x29` and identity `0xEE/0xAA/0x10` passed.
- Live initialization and health checks passed after bounded recovery.
- Live status, quick test, and repeated-read commands correctly returned
  non-zero status for invalid `8191 mm` samples.
- Six repaired files were recorded in the authorized-driver manifest.

### Raspberry Pi status

This phase is a software pass and a partial hardware pass. No actuator was
involved. Valid 100 mm distance measurement remains blocked on a physical
optical/alignment, wiring, power, or sensor-module issue. Calibration remains
intentionally blocked until valid samples are observed.

### Follow-up

With Pi power disconnected, inspect the sensor window for film or obstruction,
verify target alignment and the `3.3V/GND/SDA/SCL` path through DFR0566, then
cold-power-cycle and rerun `pi5vl53l0x status` and `pi5vl53l0x test`.
