# NinjaRobotPi5 project audit — 6 September 2026

This report explains what the project currently does, where its documents
match the code, and what should be addressed before further development.
It records an audit, not a new release or an approval to operate hardware.

**Overall assessment:** NinjaRobotPi5 has a substantial working foundation,
with 1,038 passing automated tests and successful builds of both application
packages. However, important safety and data-recovery guarantees are not
consistently enforced across every entry point. The next development work
should address those gaps before adding features.

Contents:

- [Scope and evidence](#scope-and-evidence)
- [What exists today](#what-exists-today)
- [Findings and priorities](#findings-and-priorities)
- [Documents checked against the implementation](#documents-checked-against-the-implementation)
- [Validation results](#validation-results)
- [Suggested refinement phases](#suggested-refinement-phases)
- [Remaining Raspberry Pi checks](#remaining-raspberry-pi-checks)
- [Evidence and terminology](#evidence-and-terminology)
- [File-by-file inventory](#file-by-file-inventory)

## Scope and evidence

The audited branch is `public_v02`, at commit (saved Git revision)
`3854f807df94d368de8806f148b2b50b679e2749`, dated 22 August 2026. Its
description is “refine the Emergency Stop function and fix display shut down.”
The installed development interpreter is Python 3.11.15; `uv`, the project’s
environment and dependency tool, is version 0.12.5.

The checkout initially contained an existing edit to `.gitignore` and an
untracked `ninjarobot_pi5_wiki/` directory. Both were preserved. The wiki is a
separate local project and is outside this robot audit. Its presence affects
the root formatting and code-style commands, as explained below.

The five requested documents were read through: `README.md`,
`DevelopmentGuide.md`, `InstallationGuide.md`, `DevelopmentLog.md`, and
`NinjaRobot_MCP_Skill.md`. Together they contain 8,436 lines. Their descriptions
were compared with the implementation, tests, configuration, packaging, and
relevant architecture and validation records.

The tracked-file inventory contains:

| Item | Count |
| --- | ---: |
| Files before adding this report | 509 |
| Python files, including drivers and tests | 344 |
| Python source lines, including comments and tests | 81,109 |
| Main Agent modules | 47 |
| Main IDE modules | 34 |
| Markdown documents | 69 |
| Other text/configuration/setup files | 88 |
| Binary model and font files | 8 |
| Managed driver files covered by the immutable baseline | 222 |
| Recorded authorized driver changes | 55 |

Serena, a tool that follows code definitions and references, was used to
inventory symbols in all 344 Python files and to inspect important functions
and their callers. Whole-file Python parsing and the project’s automated
checks supplemented that work. Text searches and direct file reads were used
for shell scripts, browser code, documents, and configuration.

The file inventory is complete for the tracked checkout. Review depth is
explicit: every Python file received structural inspection; detailed execution
tracing concentrated on hardware access, safety, consent, storage, model tools,
startup, remote access, and deployment. This is not a claim that every one of
the 81,109 lines has been independently proved correct. The inventory records
the method used, rather than giving every file an unsupported “safe” verdict.

No motor, physical sensor, camera, microphone, tunnel, boot setting, live
service, or power-off action was operated during this audit. Synthetic checks
used temporary directories and simulated devices. Private configuration,
credentials, databases, and captured media were not inspected. The ignored
`NinjaClawBot/` historical runtime was not edited, imported, or copied.

Only this report is added to the repository. The five source documents remain
unchanged so that their discrepancies can be reviewed before correction.

## What exists today

### The intended control path

The intended arrangement is:

```text
Person or language model
    → Agent: understands requests and applies permission rules
    → IDE: coordinates devices and executes validated actions
    → One of the six pi5 drivers
    → Physical device
```

Here, IDE means the project’s hardware integration layer, as well as its
interactive development tool. A driver is the small software component that
communicates with a particular device. A model proposes a tool call, meaning
a structured request to perform an action; it does not directly run Python or
operate a GPIO pin (a general-purpose electrical connection).

The principal Agent runtime follows this division. Its model providers,
memory, terminal interface, browser interface, and MCP connections share one
service. MCP means Model Context Protocol, a common format for discovering
and calling tools. The IDE supplies device ownership, coordinated behaviors,
action records, and safety state. The exceptions in findings A01–A04 matter
because they weaken an otherwise sensible architecture.

### Main functions

| Area | What is implemented | Important boundary |
| --- | --- | --- |
| Conversation | Local Ollama and OpenAI, Anthropic, and Gemini provider adapters | A provider adapter translates each service’s messages into the project’s common format; account access was not tested live. |
| Robot behaviors | Bundled expressions and movements; validation, preview, execution, and saving of user behaviors | A behavior is a finite sequence of robot actions. The normal movement path has more safeguards than the low-level servo tool. |
| Display and sound | Animated faces, text, brightness, melodies, greeting, and idle presentation | Shared display ownership and cleanup exist, but direct display calls can bypass the presentation stop gate. |
| Camera | Bounded still capture, temporary previews, and explicit face enrollment/recognition | Temporary full images are cleaned up; enrolled face information intentionally persists. |
| Microphone | Bounded recording and local transcription; optional “Hey Ninja” wake listening | Voice input is opt-in. The release does not provide spoken robot replies. |
| Memory | Local user profiles, preferences, conversation history, and remembered behavior outcomes | Profiles scope memory retrieval; a shared behavior catalog is a separate storage area. |
| Browser | Four interface languages, chat, direct controls, media controls, motion consent, and power confirmation | A controller lease gives one browser temporary control ownership. Direct controls and AI consent are different workflows. |
| Remote access | Optional ngrok tunnel with short-lived browser pairing | An ngrok account token opens the tunnel; a separate pairing token authorizes a browser. |
| Deployment | Explicit service installation/startup, readiness checks, restricted power helper, backup and rollback | Setup and power changes require separate operational authorization. Backup correctness needs repair. |
| Development protection | Strict data contracts, type checking, managed-driver hashes, simulation, and many tests | Passing tests demonstrate covered scenarios, not all physical failure conditions. |

The OpenAI adapter uses the Responses API (OpenAI’s request-and-response
interface), requests `store=False`, and retains reasoning continuity data for
tool exchanges. The application remains responsible for deciding whether a
proposed tool may run. That overall arrangement matches the official
[OpenAI function-calling guidance](https://developers.openai.com/api/docs/guides/function-calling).
Live provider authentication, account model availability, billing, and network
failure behavior were not certified by this audit.

### Hardware assumptions

The recorded profile uses a Raspberry Pi 5, GPIO12/GPIO13 wheel servos,
GPIO27 buzzer, VL53L0X distance sensor on I2C bus 1 at `0x29`, and ST7789V
display on SPI0 with control pins 4, 5, and 6. I2C and SPI are two ways for
the Pi to communicate with attached electronics. The display is configured
as 240 × 320 pixels with 90-degree rotation. The camera is an OV5647, and
the microphone is a USB PnP Sound Device.

The default wheels use continuous-rotation MG90D servos. For these devices,
the control signal determines rotation rather than a reliably measured wheel
angle. That makes the low-level angle-oriented command especially important
to restrict or adapt.

The [recorded hardware profile](../docs/hardware/hardware-profile.md) states
that the owner accepted operation without an accessible physical emergency
power disconnect. That is an existing, explicitly documented residual risk,
not a new approval established by this audit. Software stop behavior must not
be described as a physical power cutoff. Added actuators or a changed power
supply would require a new hardware review.

### Safety behavior as implemented now

The recent implementation distinguishes three cases:

1. An obstacle interrupts the current guarded forward/turning movement. It
   does not create a persistent fault latch (a stored “remain stopped” flag).
2. An operator Emergency Stop performs a full stop and suppresses the current
   presentation without writing a new persistent operator-stop latch.
3. Certain hardware failures create a persistent system latch. Recovery
   checks device health before clearing it.

The normal motion path includes bounded duration, distance checks, cancellation
cleanup, and a software watchdog (a monitor that stops motion when progress
signals cease). Invalid or stale distance readings do not stop movement under
the current configured contract; backward motion also has a different obstacle
response. These are documented policy choices, not guarantees of collision
avoidance. A single forward sensor cannot establish that the surroundings are
safe.

### Privacy and stored information

The project deliberately stores conversations, profiles, preferences, behavior
outcomes, saved behavior definitions, face records, and configuration. Memory
and conversation storage use SQLite, a database contained in local files.
Retrieval is bounded and user-scoped. Default conversation retention is seven
days; memory settings separately limit failed outcomes and retrieval size.

The ordinary camera/audio paths use private temporary files and default
cleanup. Face enrollment deliberately retains a face crop and matching data.
Face recognition is a convenience for identifying a profile, not strong
authentication or proof of physical identity. Browser speech recognition may
depend on the browser vendor’s service; it is distinct from the Pi’s local
microphone transcription path.

Cloud chat and external search send the relevant request content to their
configured services. Choosing local transcription does not make an entire
cloud-backed conversation local. Secret values are stored separately from
public configuration, but locally launched external MCP programs inherit the
Agent process’s environment; see A08.

## Findings and priorities

“High” means address before relying on the affected safety or recovery
guarantee. “Medium” means a meaningful reliability, trust, or operational gap.
“Low” means maintainability work that can follow correctness repairs.
“Reproduced” means a safe synthetic experiment demonstrated the behavior.
“Source-confirmed” means the relevant execution path was traced in code;
physical consequences were not tested.

| ID | Priority | Finding | Evidence |
| --- | --- | --- | --- |
| A01 | High | Low-level servo movement bypasses persistent system-stop checks | Reproduced in simulation |
| A02 | High | Emergency stop waits in the ordinary work queue | Reproduced with a blocked simulated adapter |
| A03 | High | Older command-line builders bypass integrated hardware ownership | Source-confirmed |
| A04 | High | Several device `enabled` switches are not enforced | Servo case reproduced; wiring traced |
| A05 | High | Configuration accepts overlapping servo and other GPIO assignments | Reproduced by validation only |
| A06 | High | Backup and restore do not provide a complete, consistent recovery point | Database and partial-restore cases reproduced |
| A07 | Medium | External MCP tool errors can be recorded as successful calls | Reproduced with a fake server |
| A08 | Medium | External MCP “read-only” and isolation claims exceed enforcement | Source-confirmed |
| A09 | Medium | Boot checker can approve a Pi 4-only PWM setting on Pi 5 | Reproduced with text input |
| A10 | Medium | Current user instructions contain safety and workflow contradictions | Document-to-code comparison |
| A11 | Medium | Installer inputs are only partly fixed and verified | Source-confirmed |
| A12 | Medium | Full-checkout quality gate fails; future hardware-test exclusion is not enforced | Reproduced gate failure and configuration review |
| A13 | Medium | Face-recognition backend cleanup remains incomplete | Source-confirmed |
| A14 | Low | Large central modules and aging evidence make future changes harder to review | Inventory and documentation review |
| A15 | Medium | Packaged Traditional Chinese font is an HTML error page | Reproduced by loading the font |

### A01 — Some servo commands can ignore the system-stop flag

**What happens:** after writing a persistent `driver_failure` system latch in
a temporary simulated setup, `behavior.run` failed with `SYSTEM_STOPPED`, as
expected. The same IDE accepted `servo.move` on `gpio12` and returned
`succeeded`. The stop flag had not authorized recovery.

**Why it matters:** the safety check is attached to the coordinated behavior
path rather than every hardware action. Once Agent motion permission is
granted, policy does not independently check the IDE’s system latch. This is
not a claim that an unarmed model can move the robot; it is a missing second
barrier after permission has been granted.

The direct servo path also lacks the behavior controller’s distance monitor
and watchdog. Its successful completion clears the task reference without
explicitly switching the servo output off. On the recorded continuous-rotation
wheel hardware, that creates a credible continued-output risk. Physical pulse
duration was not measured, so that consequence remains a source-based risk.
Direct display calls likewise do not consult the assembly’s stopped-state
presentation gate.

**Evidence:** [integrated.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/integrated.py),
`build_robot_ide_client`, line 688; [servo.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/servo.py),
`ServoDevice.move`, line 199, and `ServoMoveAdapter`, line 617;
[policy.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/policy.py),
`PolicyEngine.evaluate`, line 204.

**Recommended correction:** enforce system and motion safety at a common IDE
execution boundary. Route wheel movement through the guarded motion
controller, or exclude raw servo movement from ordinary Agent tools. Preserve
explicit calibration utilities behind a separately defined maintenance
contract. Add regression tests proving that every movement entry point rejects
a persistent latch and that completed wheel actions leave outputs safe.

### A02 — Emergency stop shares the queue it needs to interrupt

**What happens:** `ExecutionEngine` sends all actions through the same
`ResourceScheduler`. The integrated client uses its default single worker.
The stop capability also requests the display, buzzer, and servo resources.
It has no separate priority route.

A synthetic display adapter was held waiting on an in-memory event. A
`behavior.stop` request remained pending after 100 milliseconds and completed
only after the display operation was released. This demonstrates queue
dependence, not a measurement of real motor stopping distance. If the queue
is full, its normal admission rule can reject an action before execution.
The adapter’s five-second timeout starts after scheduling, so it does not
bound time spent waiting for a worker.

The browser stop flow cancels its direct movement task first. That mitigation
does not make the common IDE queue priority-aware, particularly when another
session or a non-motion action occupies it. Browser disarming of chat and
voice occurs after the stop request returns.

**Evidence:** [scheduler.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/scheduler.py),
`ResourceScheduler.run`, line 47; [engine.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/engine.py),
`_execute_reserved`; [integrated.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/integrated.py),
`_BehaviorStopAdapter`, line 374; [web_control.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_control.py),
`emergency_stop`, line 304.

**Recommended correction:** make IDE stop admission independent of ordinary
queue capacity, revoke relevant permissions promptly, cancel conflicting work,
and use a bounded cleanup path. Test a full queue, blocked display, active
voice/chat motion, and simultaneous stop requests with fake devices.

### A03 — The older CLI can create another hardware owner

CLI means command-line interface. The older Agent `cli.py` builds separate
device engines for real servo, display, buzzer, camera, and microphone commands.
For example, `_build_servo_engine(real=True)` creates a `ServoDevice` and its
own execution engine without constructing `RobotAssembly` or acquiring
`HardwareOwnership`.

Serena references show that the integrated ownership lock is acquired through
`RobotAssembly`. These older builders do not take that route. They still reach
drivers through IDE classes, so a test that only forbids direct `pi5*` imports
does not catch the coordination problem.

**Impact:** an operator can use a retained real-device command alongside the
integrated service without the shared ownership barrier consistently rejecting
it. No concurrent physical access was attempted during this audit.

**Evidence:** [cli.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cli.py),
`_build_servo_engine`, line 856; [robot.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/robot.py),
ownership acquisition near line 195; [hardware_ownership.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/hardware_ownership.py).

**Recommended correction:** keep public command names compatible while routing
real operations through the established IDE owner, or explicitly reject them
when another owner exists. Test every public real-device builder with a
synthetic competing lock.

### A04 — `enabled = false` does not consistently disable a device

The configuration exposes `enabled` for servos, display, and buzzer.
`RobotAssembly` passes their wiring and motion options to device objects but
does not pass or otherwise enforce those three `enabled` values. Camera and
microphone do receive their corresponding flags.

In a temporary simulated configuration, setting servo, display, and buzzer
`enabled=False` still allowed `servo.move` to succeed. This is a different
problem from `motion_enabled=False`, which the servo movement code does check.
The shared behavior startup also starts display and buzzer unconditionally.

**Evidence:** [config.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config.py),
device configuration classes starting at line 42;
[robot.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/robot.py), constructor;
[behavior_runtime.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_runtime.py),
`BehaviorRunner.start`.

**Recommended correction:** define one consistent disabled-device contract:
no driver initialization, clear unavailable status, and rejection of dependent
actions. Validate combinations such as onboarding with no display and movement
with no servos. Do not silently reinterpret existing user settings.

### A05 — Pin validation misses collisions with the wheel pins

`HardwareConfig` rejects a buzzer pin that overlaps a display control pin,
and checks exist for duplicate display controls and I2C addresses. It does
not reject a buzzer on GPIO12 while GPIO12 remains a servo endpoint.
Constructing `HardwareConfig(buzzer=BuzzerConfig(gpio=12))` succeeds.

**Impact:** a configuration can direct two device drivers to the same
electrical pin. The default wiring is not conflicting; the problem affects
accepted custom configurations.

**Evidence:** [config.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config.py),
`HardwareConfig.top_level_gpio_assignments_must_not_conflict`, line 201.

**Recommended correction:** validate all enabled-device pin assignments
together, including the fixed SPI pins and native servo endpoints. Keep
HAT channels (connections controlled by the expansion board) distinct from
native Pi pins. Add table-driven configuration tests without opening hardware.

### A06 — Backup and restore need a reliable recovery contract

There are three separate problems in
[deployment.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment.py),
`create_backup`, line 554, and `restore_backup`, line 584.

**Incomplete contents.** The backup selects configuration, MCP configuration,
secrets, conversation database, action ledger, skills, and benchmark records.
It does not include the configured face-data directory, private IDE behavior
directory, servo calibration, persistent safety file, or web certificate/key
paths. The release contract promises preservation of several of those areas.

**An inconsistent database copy.** SQLite can keep newly committed changes in
a WAL (write-ahead log, a companion file containing database changes).
Backup copies the main database file without SQLite’s consistent-backup
mechanism or a service-stop/checkpoint requirement. The CLI’s backup branch
calls the function directly while a service may still be running.

The synthetic reproduction created a table and committed one record in WAL
mode, kept the database connection open, and ran `create_backup`. The copied
database reported `no such table: audit_rows`. No real database was opened.
SQLite documents the dedicated approach in its
[online backup interface](https://www.sqlite.org/backup.html).

**Restore changes files before validating the entire archive.** A synthetic
archive contained a valid first destination followed by an invalid member.
Restore rejected the archive, but the first file had already been replaced.
The function validates the restored robot configuration only after extraction.
This is not an all-or-nothing restore.

Additional source-level concerns are that an existing backup destination can
be overwritten, permissions are tightened after archive creation, and recursive
backup can include links that restore later rejects. These need explicit
policy and tests rather than a general “data-preserving” label.

**Recommended correction:** define a versioned inventory of all persistent
data, use consistent database snapshots, validate the complete archive before
changing destinations, and stage replacements with a rollback plan. Create
private archives from the outset and reject unsafe or ambiguous destinations.
Test failure at each restore stage using only temporary data.

### A07 — An MCP error can look like success

An MCP server can return a completed response with `isError: true` to report a
tool execution failure. The external provider currently wraps a bounded
response as `SUCCEEDED` without interpreting that field. A fake connection
returning `isError: true` reproduced `status: succeeded`.

The payload is retained under an untrusted-content label, so the model may see
the error text. Nevertheless, the authoritative execution status and retry
classification are wrong. This can mislead history, recovery, and later
reasoning about what worked.

**Evidence:** [mcp_client.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/mcp_client.py),
`MCPToolProvider.call`, line 278. The distinction between protocol failures
and tool errors is defined in the official
[MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

**Recommended correction:** normalize `isError` into a failed result with
bounded, safe diagnostics and a justified retry classification. Keep transport
errors (communication failures) distinct from tool-reported failures.

### A08 — External tools are trusted to be read-only

The allowlist limits tool names, but `MCPToolProvider.start` assigns every
allowed external tool `READ_ONLY`, `idempotent=True`, and no confirmation.
Idempotent means repeating an operation does not create additional effects.
The code does not establish that an arbitrary configured tool meets those
claims.

The documentation does instruct operators to allow only read-only external
tools. That makes this partly a trust-contract clarification: the software
restricts names and treats returned text as untrusted, but it does not provide
an operating-system sandbox (a boundary limiting what a program can access).
A locally launched server receives `os.environ.copy()`, which can include
credentials for unrelated providers.

External discovery also lacks a global page-count bound, and `refresh()`
checks for missing names without replacing old tool definitions. A changed
server schema (the expected argument format) can therefore remain stale.
These are secondary reliability concerns, not demonstrated account attacks.

**Evidence:** [mcp_client.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/mcp_client.py),
`SDKMCPConnection.start`, line 105; `MCPToolProvider.start`, line 224;
`refresh`, line 269. The MCP specification explicitly cautions against trusting
tool annotations from untrusted servers; an annotation alone would not repair
this boundary.

**Recommended correction:** use reviewed server/tool configuration that states
allowed effects and retry policy, minimize subprocess environment variables,
bound discovery, and refresh schemas atomically. Describe local MCP programs
as trusted installed software unless a real process sandbox is supplied.

### A09 — The boot configuration checker ignores conditional sections

The renderer searches for the exact PWM overlay anywhere in the input.
PWM means pulse-width modulation, the electrical signal used here to control
servos. If the overlay already exists under `[pi4]`, the renderer omits it
from the new `[all]` block and the validator reports success.

A text-only reproduction returned a successful GPIO12/GPIO13 configuration
result even though the overlay was still exclusively under `[pi4]`. Raspberry
Pi’s official [conditional-filter documentation](https://www.raspberrypi.com/documentation/computers/config_txt.html#conditional-filters)
states that `[pi4]` applies to Pi 4-family boards, while `[all]` resets filters.
The consequence for Pi 5 follows from that documented behavior.

**Evidence:** [configure_rpi_boot.py](../scripts/configure_rpi_boot.py),
`render_boot_config`, line 37, and `validate_boot_config`, line 60.

**Recommended correction:** inspect effective Pi 5 settings or always ensure
the approved entry exists in the controlled `[all]` block. Test model filters,
`[none]`, includes, duplicate overlays, and conflicting values entirely with
temporary text fixtures before any manual boot-file change.

### A10 — User instructions do not always describe the current behavior

Several current documents combine older phase guidance with newer behavior.
The most important examples are listed in the document comparison below.
An operator should not need to infer whether a menu is live, whether a stop
persists, or what a memory reset removes.

This finding is about accuracy, not a request to revert the recent stop design.
The intended stop contract should be agreed explicitly, then code, tool
descriptions, help text, and manuals should say the same thing.

### A11 — Installer reproducibility has gaps

The root dependency lock and managed source checks provide good protection.
The installer also names fixed uv/Ollama versions and a fixed whisper.cpp
commit in [install-versions.env](../scripts/install-versions.env).

However, [install-rpi.sh](../scripts/install-rpi.sh) downloads executable
installer scripts without recording/verifying their exact content hashes.
The Ollama installer URL is mutable, even when a version is supplied through
its environment. The whisper model download is checked for existence rather
than an approved content hash. ngrok setup validates its major version but
does not establish the same fixed-artifact contract as the packaged wake
models.

**Impact:** two installations can depend on different upstream installer
content or model files while appearing to use the same project revision.
This is not evidence that any downloaded file was malicious.

**Recommended correction:** document and verify exact installer/model
artifacts where supported; record the remaining operating-system package
variability explicitly. Preserve rerunnable setup, preview mode, privilege
visibility, and the prohibition on silently starting the Agent or hardware.

### A12 — The root quality gate is currently red

`ruff check .` reports 182 errors in 29 files, all inside the pre-existing,
untracked wiki. `ruff format --check .` reports 24 files that would be
reformatted, also in the wiki. The tracked robot project passes scoped checks.

These failures were present before the report and were not introduced by it.
They were reproduced and attributed, not silently treated as passes. Repairing
the separate wiki is outside the authorized robot audit. The next approved
workflow change should decide whether that project has its own check boundary
or is part of this repository’s root gate.

Separately, `pyproject.toml` declares `hardware` and `provider_live` test markers
(labels attached to tests), but the default test command does not automatically
exclude them. Current reviewed tests use fakes, and no live hardware test was
run. The configuration nevertheless does not enforce the documentation’s
promise for future tests. Add an explicit opt-in mechanism before introducing
any such tests.

### A13 — Face-recognition cleanup is still incomplete

The IDE’s face backend calls managed `pi5camera.recognize_faces`. That function
constructs a recognition backend but does not close it in a `finally` block
(cleanup guaranteed after success or failure). The IDE wrapper receives the
result, not the backend object, so it cannot close that instance afterward.

The [driver containment matrix](../docs/architecture/driver-containment-matrix.md)
already identifies this historical problem and says a later integration must
own cleanup. Face recognition is now integrated, but that obligation remains
unfulfilled on the traced path. Repeated resource growth or a real Pi failure
was not measured; the confirmed issue is missing deterministic cleanup.

**Evidence:** [identity.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/identity.py),
`Pi5CameraFaceIdentityBackend`; [recognition.py](../pi5camera/src/pi5camera/core/recognition.py),
`recognize_faces`, line 45.

**Recommended correction:** add an explicit ownership/cleanup boundary and
failure-path tests. If a managed driver file must change, obtain the required
owner approval, run that driver’s independent suite, and record the authorized
hash. Do not regenerate the immutable baseline.

### A14 — Maintenance is becoming concentrated in large files

The largest application files include `agent_cli.py` at 2,230 lines,
`runtime.py` at 1,717, the older `cli.py` at 1,617, `memory_store.py` at 1,440,
and IDE `microphone.py` at 1,330. Size alone is not a bug. Here it increases
the effort needed to keep command paths, consent, cancellation, and state
changes consistent.

After correctness fixes, extract focused responsibilities while preserving
public command names and data formats. Avoid introducing another runtime or
another hardware manager. Strengthen tests around architectural obligations,
not just forbidden import names. No tracked GitHub workflow was found, so the
repository does not currently show an automatically enforced remote gate;
external account settings were not inspected.

### A15 — A bundled font is actually a failed download

The file [NotoSansTC-Regular.otf](../pi5disp/src/pi5disp/fonts/NotoSansTC-Regular.otf)
contains an HTML “404 Not Found” page rather than font data. Loading it with
Pillow, the image library used by the project, fails with `unknown file format`.
The English and Japanese font files load successfully in the same check.

The standalone display text ticker selects this file for `zh-tw` and falls
back when loading fails. That fallback does not establish the promised
Traditional Chinese character coverage. This does not prove that every
integrated display message or browser translation is broken: those can use
different rendering paths.

The managed hash verifier passes because it confirms that the historical file
has not changed; it does not prove that its original contents are a valid
font. This is a useful distinction between integrity and correctness.

**Evidence:** the font file itself and
[text_ticker.py](../pi5disp/src/pi5disp/effects/text_ticker.py), font selection
and fallback near line 17.

**Recommended correction:** obtain approval for replacing this managed asset
with an appropriately licensed, verified font. Record its provenance and
authorized hash, add an actual font-load test, and check representative Chinese
text. Do not silently replace the immutable baseline.

## Documents checked against the implementation

The development log is useful historical evidence. An old log entry is not
wrong merely because the system later changed. The problem is an old assertion
remaining in a current operating guide or being presented as current release
evidence.

| Document | What is supported by the code | Corrections or clarifications needed |
| --- | --- | --- |
| [README.md](../README.md) | Broad feature list, main package split, supported hardware, memory, voice, web, and remote-access features exist. | Line 122 says all commands simulate unless `--real`; the interactive IDE runs real controls. Line 105’s “every … learned behavior” reset wording should distinguish memory records from saved IDE behavior files. Safety claims need the exceptions A01–A05. |
| [DevelopmentGuide.md](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07/DevelopmentGuide.md) | Detailed architecture, policy, provider, memory, and current obstacle behavior mostly map to real modules and tests. | Line 1296 tells developers to create an `adapters/` directory although the current layout uses flat device modules and `adapters.py`. Test exclusion and universal ownership claims need enforcement. |
| [InstallationGuide.md](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07/InstallationGuide.md) | Installer, calibration, camera bridge, service, voice, remote access, and shutdown workflows exist. | Lines 652–653 expect simulated camera/microphone output after the real-service workflow. Line 1096 calls obstacle interruption “Level 1” despite the non-latching implementation. The benchmark section implies an operational acceptance barrier that current selection/arming does not enforce. |
| [DevelopmentLog.md](../ninjarobot_pi5_wiki/raw/notes/ninjarobotpi5/2026-09-07-02/DevelopmentLog.md) | Records explain the staged implementation and later repairs, including the August stop refinements. | Keep chronology and historical counts explicit. A reference to results “in the task handoff” is weaker than saved, revision-specific evidence. Do not present an earlier hardware acceptance as validation of every later commit. |
| [NinjaRobot_MCP_Skill.md](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07/NinjaRobot_MCP_Skill.md) | Built-in robot and memory tool providers, external configuration, and non-executable skill packages exist. | Distinguish trusted in-process robot MCP from external MCP. “Read-only” for arbitrary external servers is an operator trust requirement, not an enforced sandbox. Raw server names and normalized public names should remain clearly separated. |
| [Support matrix](../docs/architecture/v1.0.0-support-matrix.md) | The supported platform and feature boundaries are useful. | It still cites 28 authorized changes; current verification reports 55. |
| [Release manifest](../docs/validation/v1.0.0-release-manifest.json) | Records an earlier release-candidate snapshot. | It names `public_v01`, 28 repairs, 511 tests, and `publication_approved: false`; it is not the current `public_v02` audit result. Preserve it as history or explicitly supersede it. |
| [Final Pi checklist](../docs/validation/phase-8-final-interactive-pi-validation-2026-08-14.md) | Provides useful operator workflows. | It is a prepared sequence with blank device/evidence fields, not a fresh completed result for this commit. Reconcile persistent-stop expectations with later August changes. |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | Records important dependency and model provenance (where files came from and their terms). | The wake-model path omits `src/ninjarobot_pi5_ide`. It says all six drivers have a local root license file, but `pi5camera` refers to the repository-root license instead. This is a documentation mismatch, not a finding that the camera code is unlicensed. |
| Managed driver READMEs | Describe their standalone tools and historical capabilities. | Some counts are stale: buzzer says 66 versus 68 now; display says 59 versus 65. Historical OpenClaw features must not be mistaken for the integrated Agent’s permitted runtime. |

A local-link scan checked 71 Markdown links with relative file targets and
found two missing targets in historical documents:

- `docs/project-history/AuditReport_260731.md` links to `InstallationGuide.md`
  as if it were in the same directory.
- `docs/project-history/Pi5LibrariesAudit.md` links to
  `docs/validation/raspberry-pi-hardware-validation-2026-07-25.md` from inside
  `docs/project-history/`.

These are file-target checks, not a claim that every external URL or heading
anchor has been verified. Historical documents should be corrected minimally
or annotated without rewriting their original conclusions.

## Validation results

All results below were obtained during this audit. “Pass” applies to the
named check, not to every claim made about the whole robot.

### Required project gate

Commands were run from the repository root unless otherwise stated.

| Command | Result |
| --- | --- |
| `uv run --frozen python scripts/verify_immutable_drivers.py` | Pass: 222 managed files, six drivers, 55 authorized changes. |
| `uv run --frozen python scripts/verify_workspace_driver_sources.py` | Pass: all six managed imports resolve to this checkout’s editable sources. |
| `uv run --frozen python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests` | Pass: Python compilation check. |
| `uv run --frozen ruff check .` | Fail: 182 pre-existing wiki errors; zero were attributed to the tracked robot files. |
| `uv run --frozen ruff format --check .` | Fail: 24 pre-existing wiki files would change. |
| `uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src` | Pass: all 81 main source modules. Mypy checks consistency of declared data types. |
| `uv run --frozen pytest -q` | Pass: 581 tests; one Starlette test-client deprecation warning. |
| `git diff --check` | Pass at final report verification; checks whitespace defects in tracked changes. The new report was also checked separately. |

The scoped Ruff checks below both passed. Ruff checks code style and common
programming mistakes; its formatter checks layout.

```bash
uv run --frozen ruff check ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests pi5buzzer pi5camera pi5disp pi5mic pi5servo pi5vl53l0x
uv run --frozen ruff format --check ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests pi5buzzer pi5camera pi5disp pi5mic pi5servo pi5vl53l0x
```

Expected and observed result: all checks passed; 344 files were already
formatted. These scoped passes do not change the two full-checkout failures.

### Independent managed-driver tests

Each driver was tested in a separate process from its own directory, using:

```bash
uv run --isolated --frozen --extra dev --python 3.11 python -B -m pytest -q -p no:cacheprovider
```

Expected result: fake-device tests pass without accessing physical hardware.
Separate processes avoid collisions between deliberately reused test filenames.

| Driver | Passed tests |
| --- | ---: |
| `pi5buzzer` | 68 |
| `pi5camera` | 27 |
| `pi5disp` | 65 |
| `pi5mic` | 92 |
| `pi5servo` | 134 |
| `pi5vl53l0x` | 71 |
| Driver total | 457 |
| Main project plus drivers | **1,038** |

The microphone suite reported an `audioop` deprecation warning. The package
already declares `audioop-lts` for Python 3.13 and later; the warning is not
evidence of a missing compatibility dependency. Python versions other than
3.11 were not tested here.

### Additional checks

| Check | Result and limits |
| --- | --- |
| `bash ./install.sh --dry-run` | Pass; displayed the installation plan and made no installation changes. |
| `bash -n` on all four tracked `.sh` files and the packaged power helper | Pass; checked shell syntax only, never executed power operations. |
| `node --check ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js` | Pass; browser JavaScript syntax. No real browser usability or accessibility certification. |
| Parse tracked structured files | Pass: 46 JSON-format files and 16 TOML/lock files. JSON and TOML are structured text formats for data/settings. |
| `uv build --all-packages --out-dir /tmp/ninjarobot-audit-build-260906 --offline` | Pass: source archives and wheels for both Agent and IDE, version 1.0.0. A wheel is an installable Python package. |
| Inspect built wheels | Agent: 74 entries, including 12 skill, 3 deployment, and 8 browser assets. IDE: 70 entries, including 6 model/provenance assets. No unsafe archive paths or `NinjaClawBot` entries. |
| `uv run --frozen python scripts/benchmark_agent_memory.py` | Pass: 1,000 synthetic entries, 50 queries, median 4.762 ms, 95th-percentile 5.496 ms, database 1,257,472 bytes. Limits were 100 ms and 16 MiB. |
| Relative Markdown file links | 71 checked; two historical missing targets listed above. |
| Load three packaged display fonts with Pillow | Two pass; Traditional Chinese font fails because its contents are an HTML error page. See A15. |
| Synthetic safety/recovery/protocol probes | Confirmed A01, A02, A04, A05, A06, A07, and A09. These expose missing regression cases despite the passing existing suite. |

The memory benchmark measures this environment and its temporary synthetic
database. It does not measure model response speed, prolonged thermal behavior,
or a particular user’s real database. Package build success likewise does not
prove a clean Raspberry Pi installation with all operating-system camera and
audio bindings. Dependency vulnerability scanning and exhaustive license
auditing were not performed; no “free of vulnerabilities” claim is made.

## Suggested refinement phases

These are proposed follow-up phases, not implemented changes. Each phase needs
the owner’s explicit implementation approval under `AGENTS.md`. The audit
itself does not authorize a managed-driver repair, deployment, or publication.

| Phase | Objective and likely files | Compatibility and validation gate | Documentation and hardware risk |
| --- | --- | --- | --- |
| 1 | Close safety/ownership gaps A01–A05 in IDE `integrated.py`, `engine.py`, `scheduler.py`, `robot.py`, `servo.py`, `config.py`, plus Agent `cli.py` and stop callers. | Preserve command names and normal behavior formats where possible. Test all motion entries under latches, full queues, disabled devices, conflicting pins, and competing owners. Run the complete project gate and relevant driver suites. | Align README and both guides; append rationale to the development log. High hardware relevance; development tests remain simulated. |
| 2 | Repair complete backup and staged restore in `deployment.py` and its CLI/tests. | Preserve existing data; define archive-version compatibility. Test open databases, malformed archives, interrupted restore, links, and all persistent directories using synthetic data. | Publish an exact backup inventory and recovery procedure. High data-preservation relevance; no live user-data migration in tests. |
| 3 | Correct external MCP status, trust, environment, refresh, and discovery bounds in `mcp_client.py`, `mcp_config.py`, and related tests. | Keep public tool names stable; make changed trust assumptions explicit. Test server-reported errors, stale schemas, cancellation, and credential minimization with fakes. | Update `NinjaRobot_MCP_Skill.md`, guides, and notices if dependencies change. Network/privacy relevance; no real accounts required for tests. |
| 4 | Correct boot rendering and installer artifact verification in `scripts/`; address face-backend cleanup and the invalid font with the smallest approved changes. | Maintain previewable, rerunnable setup and existing private settings. Managed-file edits require independent authorization and recorded hashes. | Update installation, containment, and validation records. Boot/camera/display relevance; text fixtures and fake backends first. |
| 5 | Reconcile active manuals, current evidence, test boundaries, and selected large modules. | Preserve public interfaces and storage formats; avoid broad refactoring while safety repairs are unsettled. | Clarify historical snapshots and obtain fresh Pi results tied to a commit. Documentation work itself has no hardware effect. |

For each implementation phase, run the immutable-driver verifier before and
after, then the applicable compile, style, format, type, test, packaging, and
documentation checks. A failing managed-driver hash must stop that phase; it
must never be made to pass by replacing the baseline.

## Remaining Raspberry Pi checks

No item below is marked completed by this audit. These are separate validation
categories so that a harmless software check is not confused with operating
hardware. Existing manual records remain useful, but they do not replace
new evidence for the audited revision and later repairs.

### Safe smoke checklist — no hardware

- [ ] From the checkout root, run the two driver verifiers and the main test
  command shown above. Expected: hashes and source locations match, and tests
  pass. If a check fails, keep hardware off and resolve the reported cause.
- [ ] Run `bash ./install.sh --dry-run`. Expected: a plan only. No rollback is
  necessary because it should not change the system.
- [ ] After safety repairs, repeat the synthetic latch, queue, disabled-device,
  and backup probes. Expected: unsafe requests are rejected and failed restores
  leave original temporary data intact. Revert the proposed code change if its
  regression gate fails; do not alter real user data to make a test pass.

### Device communication checklist — no intended wheel movement

- [ ] Arrange one hardware owner and use the documented IDE hardware-status
  workflow. Expected: enabled devices communicate; disabled devices are not
  initialized. If unavailable, stop the tool and correct configuration or
  wiring with power safely removed.
- [ ] Verify display and buzzer recovery through the interactive tool with
  motion disarmed. Expected: stable status, controlled presentation, and
  released resources on exit. Rollback: stop the tool and restore the prior
  reviewed software/configuration rather than repeatedly restarting a fault.
- [ ] Only with consent, test one camera preview and one microphone recording.
  Expected: bounded capture and temporary-media cleanup. Rollback: disable
  capture/listening and close the application. Do not retain test media.
- [ ] Test repeated face recognition after A13 is repaired. Expected: resources
  close on both success and failure. Do not equate successful recognition with
  secure authentication.

### Actuator-moving checklist — operator-controlled only

- [ ] Resolve A01–A05 first. Secure the robot with wheels raised, clear the
  movement area, and arrange an operator who can remove power. The current
  hardware record’s missing accessible cutoff must be addressed in this test
  arrangement rather than assumed away.
- [ ] Request one short movement through each supported user interface.
  Expected: explicit applicable permission, bounded operation, and stopped
  outputs afterward. Rollback: Emergency Stop; remove power if software does
  not stop the robot.
- [ ] Exercise stop during ordinary movement and concurrent non-motion work.
  Expected: prompt stopping independent of queue occupancy, revoked AI motion
  permission, and consistent presentation. Record measured stopping behavior;
  do not invent a latency threshold from the 100 ms synthetic probe.
- [ ] Validate obstacle interruption and genuine fault recovery separately.
  Expected: each follows the agreed current contract; interrupted movement
  never restarts by itself. Rollback: stop, disarm, remove the cause, and require
  a fresh command. Do not delete the safety file to bypass recovery.

### Power-risk checklist — manual and last

- [ ] Before any live power test, validate helper content, permissions,
  restricted privilege rules, and the active Pi bootloader power mode using
  the existing documented preflight. Expected: rejection if any requirement
  is missing. Rollback: leave web power-off disabled.
- [ ] With separate explicit operational authorization, use the normal paired
  browser confirmation once. Expected: one-use confirmation, orderly cleanup,
  and actual full power-off. This was not run during the audit.
- [ ] Restore power and check storage and startup behavior. Expected: preserved
  user data, no automatic replay of interrupted motion, and no new ownership
  conflict. If recovery fails, keep automatic startup disabled and follow the
  reviewed recovery procedure. Do not rely on the current backup implementation
  as the sole recovery copy until A06 is repaired.

Remote pairing, two-browser ownership, offline startup, tunnel failure/recovery,
multilingual voice quality, prolonged display/audio operation, and clean-clone
installation also need revision-specific manual evidence. They should be
planned separately, with consent and approved account/network boundaries.

## Evidence and terminology

The synthetic probes used only fake devices and files under temporary
directories. The observed outcomes were:

```text
Persistent driver-failure latch + behavior.run → failed: SYSTEM_STOPPED
Same latch + servo.move                     → succeeded
servos.enabled = false + servo.move         → succeeded
Blocked simulated display + behavior.stop   → pending until display released
Buzzer GPIO12 + default servo GPIO12        → configuration accepted
Open SQLite WAL database copied by backup   → copied database missing table
Invalid archive with an earlier valid file  → rejected after earlier replacement
External MCP response isError = true        → tool status succeeded
PWM overlay only under [pi4]                → boot validator reported success
```

These observations are deliberately narrower than claims about physical
damage, successful attacks, or every possible runtime state. The passing
existing tests did not cover these exact combinations.

Useful terms used in the report or file inventory:

- **Adapter:** code that translates between two interfaces.
- **API:** application programming interface, the defined way programs talk.
- **Artifact:** a built package, model, or other file delivered for use.
- **Atomic:** a change completes as a whole or leaves the previous state intact.
- **Backend:** the implementation doing work behind a common interface.
- **Checksum/hash:** a content fingerprint used to detect changed files.
- **Contract/schema:** rules for accepted requests, data, and results.
- **Coroutine/async:** work that can wait while other work proceeds.
- **IPC:** inter-process communication, messages between local programs.
- **Ledger:** a durable record of actions and their outcomes.
- **Lock:** a mechanism preventing conflicting access at the same time.
- **Migration:** a controlled update to an existing stored-data format.
- **ONNX/TFLite:** formats for packaged machine-learning models.
- **Provider:** a component supplying model responses or tools.
- **Regression test:** a check that a repaired problem does not return.
- **SDK:** software development kit, a library for using a service.
- **Simulation/fake:** software standing in for hardware or an external service.
- **systemd:** Linux’s service startup and supervision manager.
- **TLS/HTTPS:** encryption and identity checks for network connections.
- **Transaction:** related changes handled as one consistent operation.
- **WebSocket:** a persistent browser/server message connection.

Official sources were consulted for external interface details. In addition to
the links alongside findings, the [OpenAI Responses documentation](https://developers.openai.com/api/docs/guides/function-calling)
supports the tool-execution separation, and the
[MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
supports the error-field and untrusted-annotation distinctions. These sources
establish interface expectations, not live acceptance of this robot.

## File-by-file inventory

This appendix accounts for every file tracked at the starting revision.
Paths are relative to the repository root. `S` means Serena symbol inventory
plus whole-file Python parsing; it does not mean every branch was exercised.
`T` adds membership in an executed automated test suite. `D` identifies a
file used in focused document/control-flow review. `P` means structured-data,
shell, browser syntax, or package-content inspection as applicable. `H` means
managed-file hash verification. `I` means inventory/context inspection only.
Several methods can apply to one file.

The purpose column identifies responsibility, not a clean bill of health.
Findings above take precedence over any general description. Historical
documents are records, binary models/fonts were not interpreted as source,
and standalone driver capabilities are not automatically integrated features.
### .agents — 2 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [.agents/skills/pi-validation/SKILL.md](../.agents/skills/pi-validation/SKILL.md) | I | Pi Validation Report. |
| [.agents/skills/project-documentation/SKILL.md](../.agents/skills/project-documentation/SKILL.md) | I | Project Documentation Maintainer. |

### Root files — 13 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [.gitignore](../.gitignore) | I | Git exclusion rules; pre-existing user edit preserved. |
| [.python-version](../.python-version) | I | Preferred Python interpreter version. |
| [AGENTS.md](../AGENTS.md) | D | AGENTS.md. |
| [DevelopmentGuide.md](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07/DevelopmentGuide.md) | D | NinjaRobotPi5 Development Guide. |
| [DevelopmentLog.md](../ninjarobot_pi5_wiki/raw/notes/ninjarobotpi5/2026-09-07-02/DevelopmentLog.md) | D | NinjaRobotPi5V4 Development Log. |
| [InstallationGuide.md](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07/InstallationGuide.md) | D | NinjaRobotPi5 Installation Guide. |
| [LICENSE](../LICENSE) | I | License terms shipped with this project/package. |
| [NinjaRobot_MCP_Skill.md](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07/NinjaRobot_MCP_Skill.md) | D | Extend NinjaRobot with MCP tools and Agent Skills. |
| [README.md](../README.md) | D | NinjaRobotPi5. |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | D | Third-Party Notices. |
| [install.sh](../install.sh) | P | Shell setup/helper program; syntax checked without live deployment. |
| [pyproject.toml](../pyproject.toml) | D, P | Package metadata, dependencies, entry points, and tool configuration. |
| [uv.lock](../uv.lock) | P | Locked dependency versions and download fingerprints; not a security certification. |

### config — 1 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [config/ninjarobot_pi5.toml.example](../config/ninjarobot_pi5.toml.example) | D | Public example configuration; compared with strict configuration models. |

### docs — 54 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [docs/README.md](../docs/README.md) | I | NinjaRobotPi5 documentation. |
| [docs/adr/0000-template.md](../docs/adr/0000-template.md) | I | ADR 0000: Decision title. |
| [docs/adr/0001-pydantic-v2-contract-validation.md](../docs/adr/0001-pydantic-v2-contract-validation.md) | I | ADR 0001: Pydantic v2 for boundary validation. |
| [docs/adr/0002-strict-mypy-for-v4.md](../docs/adr/0002-strict-mypy-for-v4.md) | I | ADR 0002: Strict mypy for new V4 packages. |
| [docs/architecture/README.md](../docs/architecture/README.md) | I | Architecture records. |
| [docs/architecture/driver-containment-matrix.md](../docs/architecture/driver-containment-matrix.md) | D | Managed driver containment matrix. |
| [docs/architecture/phase-1-contracts.md](../docs/architecture/phase-1-contracts.md) | D | Phase 1 contract reference. |
| [docs/architecture/phase-8-release-contract.md](../docs/architecture/phase-8-release-contract.md) | D | Phase 8 Public-Release Contract. |
| [docs/architecture/phase-8-threat-model.md](../docs/architecture/phase-8-threat-model.md) | D | Phase 8 Threat Model. |
| [docs/architecture/v1.0.0-support-matrix.md](../docs/architecture/v1.0.0-support-matrix.md) | D | NinjaRobotPi5 v1.0.0 Support and Known Limitations. |
| [docs/hardware/hardware-profile.md](../docs/hardware/hardware-profile.md) | D | Confirmed hardware profile. |
| [docs/markdown-style-guide.md](../docs/markdown-style-guide.md) | D | NinjaRobotPi5 documentation style guide. |
| [docs/project-history/AuditReport_260731.md](../docs/project-history/AuditReport_260731.md) | I | Historical plan/audit; inventory and context, not fresh acceptance evidence. |
| [docs/project-history/NinjaRobotPi5V4_ImplementationPlan.md](../docs/project-history/NinjaRobotPi5V4_ImplementationPlan.md) | I | Historical plan/audit; inventory and context, not fresh acceptance evidence. |
| [docs/project-history/Pi5LibrariesAudit.md](../docs/project-history/Pi5LibrariesAudit.md) | I | Historical plan/audit; inventory and context, not fresh acceptance evidence. |
| [docs/validation/agent-long-run-hardware-stability-validation-2026-08-01.md](../docs/validation/agent-long-run-hardware-stability-validation-2026-08-01.md) | D | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/agent-startup-readiness-validation-2026-08-01.md](../docs/validation/agent-startup-readiness-validation-2026-08-01.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/authorized_driver_changes.json](../docs/validation/authorized_driver_changes.json) | P | Structured data/manifest; parsed successfully. |
| [docs/validation/boot-autostart-lgpio-runtime-pi-checklist.md](../docs/validation/boot-autostart-lgpio-runtime-pi-checklist.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/hardware-recovery-repair-validation-2026-07-30.md](../docs/validation/hardware-recovery-repair-validation-2026-07-30.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/immutable_driver_baseline.json](../docs/validation/immutable_driver_baseline.json) | P | Structured data/manifest; parsed successfully. |
| [docs/validation/obstacle-display-stability-pi-checklist.md](../docs/validation/obstacle-display-stability-pi-checklist.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-0-baseline.md](../docs/validation/phase-0-baseline.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-1-validation-2026-07-26.md](../docs/validation/phase-1-validation-2026-07-26.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-2-validation-2026-07-26.md](../docs/validation/phase-2-validation-2026-07-26.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-3-1-buzzer-validation-2026-07-26.md](../docs/validation/phase-3-1-buzzer-validation-2026-07-26.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-3-2-display-validation-2026-07-26.md](../docs/validation/phase-3-2-display-validation-2026-07-26.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-3-3-servo-validation-2026-07-26.md](../docs/validation/phase-3-3-servo-validation-2026-07-26.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-3-4-camera-validation-2026-07-26.md](../docs/validation/phase-3-4-camera-validation-2026-07-26.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-3-5-microphone-validation-2026-07-26.md](../docs/validation/phase-3-5-microphone-validation-2026-07-26.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-4-integrated-behavior-validation-2026-07-26.md](../docs/validation/phase-4-integrated-behavior-validation-2026-07-26.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-4-refinement-validation-2026-07-27.md](../docs/validation/phase-4-refinement-validation-2026-07-27.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-5-agent-chat-resume-validation-2026-07-29.md](../docs/validation/phase-5-agent-chat-resume-validation-2026-07-29.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-5-agent-model-ui-refinement-validation-2026-07-29.md](../docs/validation/phase-5-agent-model-ui-refinement-validation-2026-07-29.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-5-agent-refinement-validation-2026-07-29.md](../docs/validation/phase-5-agent-refinement-validation-2026-07-29.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-5-agent-validation-2026-07-28.md](../docs/validation/phase-5-agent-validation-2026-07-28.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-5-behavior-generation-repair-validation-2026-07-29.md](../docs/validation/phase-5-behavior-generation-repair-validation-2026-07-29.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-5-dynamic-behavior-validation-2026-07-29.md](../docs/validation/phase-5-dynamic-behavior-validation-2026-07-29.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-5-recovery-idle-camera-validation-2026-07-30.md](../docs/validation/phase-5-recovery-idle-camera-validation-2026-07-30.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-6-cloud-provider-validation-2026-07-30.md](../docs/validation/phase-6-cloud-provider-validation-2026-07-30.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-7-persistent-memory-validation-2026-08-12.md](../docs/validation/phase-7-persistent-memory-validation-2026-08-12.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-8-2-voice-input-pi-checklist.md](../docs/validation/phase-8-2-voice-input-pi-checklist.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-8-3-remote-access-pi-checklist.md](../docs/validation/phase-8-3-remote-access-pi-checklist.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-8-4-web-poweroff-pi-checklist.md](../docs/validation/phase-8-4-web-poweroff-pi-checklist.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-8-5-onboarding-pi-checklist.md](../docs/validation/phase-8-5-onboarding-pi-checklist.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-8-6-systemd-pi-checklist.md](../docs/validation/phase-8-6-systemd-pi-checklist.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-8-final-interactive-pi-validation-2026-08-14.md](../docs/validation/phase-8-final-interactive-pi-validation-2026-08-14.md) | D | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/phase-8-openwakeword-assets.json](../docs/validation/phase-8-openwakeword-assets.json) | P | Structured data/manifest; parsed successfully. |
| [docs/validation/phase-8-wake-model.json](../docs/validation/phase-8-wake-model.json) | P | Structured data/manifest; parsed successfully. |
| [docs/validation/raspberry-pi-hardware-validation-2026-07-25.md](../docs/validation/raspberry-pi-hardware-validation-2026-07-25.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/robot-control-mcp-validation-2026-08-01.md](../docs/validation/robot-control-mcp-validation-2026-08-01.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/v1.0.0-installation-optimization-pi-checklist.md](../docs/validation/v1.0.0-installation-optimization-pi-checklist.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/v1.0.0-release-candidate-report.md](../docs/validation/v1.0.0-release-candidate-report.md) | I | Validation record or manual checklist; historical claims are not new Pi results. |
| [docs/validation/v1.0.0-release-manifest.json](../docs/validation/v1.0.0-release-manifest.json) | D, P | Structured data/manifest; parsed successfully. |

### ninjarobot_pi5_agent — 111 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [ninjarobot_pi5_agent/pyproject.toml](../ninjarobot_pi5_agent/pyproject.toml) | P | Package metadata, dependencies, entry points, and tool configuration. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/__init__.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/__init__.py) | S | Package exports and initialization (what importing this package makes available). |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/__main__.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/__main__.py) | S | Command entry point when launched as a Python module. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_cli.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_cli.py) | S, D | Conversational agent, provider, MCP, Skill, and web administration CLI. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py) | S, D | Bounded provider/tool loop with durable conversation and deterministic policy. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/anthropic_provider.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/anthropic_provider.py) | S | Anthropic Messages API adapter for the provider-neutral agent boundary. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/benchmark.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/benchmark.py) | S | Raspberry Pi acceptance benchmark for local agent model candidates. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/current-web-answer/examples.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/current-web-answer/examples.json) | P | Bundled non-executable skill data/instructions. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/current-web-answer/instructions.md](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/current-web-answer/instructions.md) | I | Current Web Answer. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/current-web-answer/skill.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/current-web-answer/skill.json) | P | Bundled non-executable skill data/instructions. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/memory-retrieval/examples.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/memory-retrieval/examples.json) | P | Bundled non-executable skill data/instructions. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/memory-retrieval/instructions.md](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/memory-retrieval/instructions.md) | I | Memory Retrieval. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/memory-retrieval/skill.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/memory-retrieval/skill.json) | P | Bundled non-executable skill data/instructions. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/offline-robot-check/examples.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/offline-robot-check/examples.json) | P | Bundled non-executable skill data/instructions. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/offline-robot-check/instructions.md](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/offline-robot-check/instructions.md) | I | Offline Robot Check. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/offline-robot-check/skill.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/offline-robot-check/skill.json) | P | Bundled non-executable skill data/instructions. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/robot-behavior-generation/examples.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/robot-behavior-generation/examples.json) | P | Bundled non-executable skill data/instructions. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/robot-behavior-generation/instructions.md](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/robot-behavior-generation/instructions.md) | I | Robot Behavior Generation. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/robot-behavior-generation/skill.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/robot-behavior-generation/skill.json) | P | Bundled non-executable skill data/instructions. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cli.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cli.py) | S, D | Unified CLI for contracts, simulation, and explicit hardware checks. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cloud_common.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cloud_common.py) | S | Shared cloud-provider authentication, transport, and normalization helpers. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cloud_registry.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cloud_registry.py) | S | Configuration-driven registry for Ollama and supported cloud providers. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment.py) | S, D | Explicit, data-preserving systemd deployment for one real-hardware service. See A06. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment/ninjarobot-agent.service.in](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment/ninjarobot-agent.service.in) | I | Deployment template; reviewed through packaging and deployment tests. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment/ninjarobot-poweroff](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment/ninjarobot-poweroff) | P | Shell setup/helper program; syntax checked without live deployment. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment/ninjarobot-poweroff.sudoers.in](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment/ninjarobot-poweroff.sudoers.in) | I | Deployment template; reviewed through packaging and deployment tests. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/events.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/events.py) | S | Bounded, typed runtime events shared by CLI and web clients. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/gemini_provider.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/gemini_provider.py) | S | Google Gemini generateContent adapter for the provider-neutral agent boundary. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/ipc.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/ipc.py) | S | Owner-only Unix-socket protocol for reconnectable local interfaces. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/mcp_client.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/mcp_client.py) | S, D | MCP connections normalized as isolated read-only tool providers. See A07/A08. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/mcp_config.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/mcp_config.py) | S, D | Strict MCP server configuration and the bundled Tavily preset. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_mcp.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_mcp.py) | S | Trusted, read-only, session-scoped memory tool provider. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_migrations.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_migrations.py) | S, D | Idempotent SQLite schema migrations shared by conversation and memory stores. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_models.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_models.py) | S | Strict contracts for local, user-scoped long-term memory. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_services.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_services.py) | S, D | Bounded retrieval and deterministic memory-capture policy. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_store.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_store.py) | S, D | Deterministic local persistence for user profiles and long-term memory. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/model_selection.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/model_selection.py) | S | Provider-neutral model catalog, acceptance evidence, and active selection. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/models.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/models.py) | S | Strict provider, tool, session, and memory contracts. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/ollama.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/ollama.py) | S | Bounded local Ollama provider adapter for Raspberry Pi 5. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/onboarding.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/onboarding.py) | S | Serialized QR-to-Greeting startup coordination for the public release. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/openai_provider.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/openai_provider.py) | S, D | OpenAI Responses API adapter for the provider-neutral agent boundary. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/pairing.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/pairing.py) | S, D | Short-lived, passwordless browser pairing for optional remote access. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/persistence.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/persistence.py) | S, D | Owner-only SQLite conversation persistence with bounded retention. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/policy.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/policy.py) | S, D | Deterministic confirmation, trust, and motion-arming policy. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/presentation.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/presentation.py) | S | Safe conversational face selection through the IDE-owned robot assembly. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/prompts.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/prompts.py) | S | Ordered system-prompt composition with immutable safety precedence. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/provider_auth.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/provider_auth.py) | S | API-key-only cloud authentication configuration helpers. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/providers.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/providers.py) | S | Provider-neutral model protocol. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/recovery.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/recovery.py) | S | Conservative recovery decisions for failed tool calls. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/release_foundations.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/release_foundations.py) | S | Strict, redaction-safe Phase 8 feature state and dependency reporting. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/remote_access.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/remote_access.py) | S, D | Optional ngrok lifecycle with offline boot, sanitized status, and pairing. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/robot_control_mcp.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/robot_control_mcp.py) | S, D | Trusted in-process MCP façade for deterministic NinjaRobot behaviors. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/runtime.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/runtime.py) | S, D | Single-owner in-process agent application used by CLI and web interfaces. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/secrets.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/secrets.py) | S | Owner-private agent secret storage with environment override support. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service.py) | S | Single-owner agent service lifecycle shared by all interfaces. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service_main.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service_main.py) | S, D | Foreground entry point for the single-owner NinjaRobot agent service. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/shutdown.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/shutdown.py) | S, D | Nonce-confirmed, narrowly privileged Raspberry Pi shutdown coordination. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/skills.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/skills.py) | S, D | Confined, non-executable NinjaRobotAgent skill packages. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/testing.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/testing.py) | S | Deterministic fake model provider for and later scenario tests. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/tools.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/tools.py) | S, D | Unified agent tool registry and the sole robot-to-IDE bridge. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/voice_service.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/voice_service.py) | S | Agent bridge for IDE-owned voice input, owner identity, events, and config. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_app.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_app.py) | S, D | HTTPS FastAPI controller hosted inside the single-owner agent service. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_control.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_control.py) | S, D | Exclusive browser lease and fixed, policy-checked robot controls. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js) | P | Browser interaction code; syntax and control/message paths inspected. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/i18n/en.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/i18n/en.json) | P | Browser language strings; structured data and existing interface tests. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/i18n/ja.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/i18n/ja.json) | P | Browser language strings; structured data and existing interface tests. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/i18n/zh-CN.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/i18n/zh-CN.json) | P | Browser language strings; structured data and existing interface tests. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/i18n/zh-TW.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/i18n/zh-TW.json) | P | Browser language strings; structured data and existing interface tests. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/index.html](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/index.html) | I | Browser page structure; packaged and covered by interface tests. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/manifest.webmanifest](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/manifest.webmanifest) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/styles.css](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/styles.css) | I | Browser appearance rules; packaged, not a visual certification. |
| [ninjarobot_pi5_agent/tests/__init__.py](../ninjarobot_pi5_agent/tests/__init__.py) | S, T | Automated checks/support for   init  . |
| [ninjarobot_pi5_agent/tests/test_agent_cli.py](../ninjarobot_pi5_agent/tests/test_agent_cli.py) | S, T | Automated checks/support for agent cli. |
| [ninjarobot_pi5_agent/tests/test_agent_loop.py](../ninjarobot_pi5_agent/tests/test_agent_loop.py) | S, T | Automated checks/support for agent loop. |
| [ninjarobot_pi5_agent/tests/test_anthropic_provider.py](../ninjarobot_pi5_agent/tests/test_anthropic_provider.py) | S, T | Automated checks/support for anthropic provider. |
| [ninjarobot_pi5_agent/tests/test_benchmark.py](../ninjarobot_pi5_agent/tests/test_benchmark.py) | S, T | Automated checks/support for benchmark. |
| [ninjarobot_pi5_agent/tests/test_cli.py](../ninjarobot_pi5_agent/tests/test_cli.py) | S, T | Automated checks/support for cli. |
| [ninjarobot_pi5_agent/tests/test_cloud_registry.py](../ninjarobot_pi5_agent/tests/test_cloud_registry.py) | S, T | Automated checks/support for cloud registry. |
| [ninjarobot_pi5_agent/tests/test_deployment.py](../ninjarobot_pi5_agent/tests/test_deployment.py) | S, T | Automated checks/support for deployment. |
| [ninjarobot_pi5_agent/tests/test_events.py](../ninjarobot_pi5_agent/tests/test_events.py) | S, T | Automated checks/support for events. |
| [ninjarobot_pi5_agent/tests/test_gemini_provider.py](../ninjarobot_pi5_agent/tests/test_gemini_provider.py) | S, T | Automated checks/support for gemini provider. |
| [ninjarobot_pi5_agent/tests/test_ipc.py](../ninjarobot_pi5_agent/tests/test_ipc.py) | S, T | Automated checks/support for ipc. |
| [ninjarobot_pi5_agent/tests/test_mcp_client.py](../ninjarobot_pi5_agent/tests/test_mcp_client.py) | S, T | Automated checks/support for mcp client. |
| [ninjarobot_pi5_agent/tests/test_mcp_config.py](../ninjarobot_pi5_agent/tests/test_mcp_config.py) | S, T | Automated checks/support for mcp config. |
| [ninjarobot_pi5_agent/tests/test_memory_services.py](../ninjarobot_pi5_agent/tests/test_memory_services.py) | S, T | Automated checks/support for memory services. |
| [ninjarobot_pi5_agent/tests/test_memory_store.py](../ninjarobot_pi5_agent/tests/test_memory_store.py) | S, T | Automated checks/support for memory store. |
| [ninjarobot_pi5_agent/tests/test_model_selection.py](../ninjarobot_pi5_agent/tests/test_model_selection.py) | S, T | Automated checks/support for model selection. |
| [ninjarobot_pi5_agent/tests/test_models.py](../ninjarobot_pi5_agent/tests/test_models.py) | S, T | Automated checks/support for models. |
| [ninjarobot_pi5_agent/tests/test_ollama.py](../ninjarobot_pi5_agent/tests/test_ollama.py) | S, T | Automated checks/support for ollama. |
| [ninjarobot_pi5_agent/tests/test_onboarding.py](../ninjarobot_pi5_agent/tests/test_onboarding.py) | S, T | Automated checks/support for onboarding. |
| [ninjarobot_pi5_agent/tests/test_openai_provider.py](../ninjarobot_pi5_agent/tests/test_openai_provider.py) | S, T | Automated checks/support for openai provider. |
| [ninjarobot_pi5_agent/tests/test_pairing.py](../ninjarobot_pi5_agent/tests/test_pairing.py) | S, T | Automated checks/support for pairing. |
| [ninjarobot_pi5_agent/tests/test_persistence.py](../ninjarobot_pi5_agent/tests/test_persistence.py) | S, T | Automated checks/support for persistence. |
| [ninjarobot_pi5_agent/tests/test_policy.py](../ninjarobot_pi5_agent/tests/test_policy.py) | S, T | Automated checks/support for policy. |
| [ninjarobot_pi5_agent/tests/test_presentation.py](../ninjarobot_pi5_agent/tests/test_presentation.py) | S, T | Automated checks/support for presentation. |
| [ninjarobot_pi5_agent/tests/test_prompts.py](../ninjarobot_pi5_agent/tests/test_prompts.py) | S, T | Automated checks/support for prompts. |
| [ninjarobot_pi5_agent/tests/test_provider.py](../ninjarobot_pi5_agent/tests/test_provider.py) | S, T | Automated checks/support for provider. |
| [ninjarobot_pi5_agent/tests/test_provider_menu.py](../ninjarobot_pi5_agent/tests/test_provider_menu.py) | S, T | Automated checks/support for provider menu. |
| [ninjarobot_pi5_agent/tests/test_recovery.py](../ninjarobot_pi5_agent/tests/test_recovery.py) | S, T | Automated checks/support for recovery. |
| [ninjarobot_pi5_agent/tests/test_release_assets.py](../ninjarobot_pi5_agent/tests/test_release_assets.py) | S, T | Automated checks/support for release assets. |
| [ninjarobot_pi5_agent/tests/test_release_foundations.py](../ninjarobot_pi5_agent/tests/test_release_foundations.py) | S, T | Automated checks/support for release foundations. |
| [ninjarobot_pi5_agent/tests/test_remote_access.py](../ninjarobot_pi5_agent/tests/test_remote_access.py) | S, T | Automated checks/support for remote access. |
| [ninjarobot_pi5_agent/tests/test_robot_control_mcp.py](../ninjarobot_pi5_agent/tests/test_robot_control_mcp.py) | S, T | Automated checks/support for robot control mcp. |
| [ninjarobot_pi5_agent/tests/test_service.py](../ninjarobot_pi5_agent/tests/test_service.py) | S, T | Automated checks/support for service. |
| [ninjarobot_pi5_agent/tests/test_service_main.py](../ninjarobot_pi5_agent/tests/test_service_main.py) | S, T | Automated checks/support for service main. |
| [ninjarobot_pi5_agent/tests/test_shutdown.py](../ninjarobot_pi5_agent/tests/test_shutdown.py) | S, T | Automated checks/support for shutdown. |
| [ninjarobot_pi5_agent/tests/test_skills.py](../ninjarobot_pi5_agent/tests/test_skills.py) | S, T | Automated checks/support for skills. |
| [ninjarobot_pi5_agent/tests/test_tools.py](../ninjarobot_pi5_agent/tests/test_tools.py) | S, T | Automated checks/support for tools. |
| [ninjarobot_pi5_agent/tests/test_user_profiles.py](../ninjarobot_pi5_agent/tests/test_user_profiles.py) | S, T | Automated checks/support for user profiles. |
| [ninjarobot_pi5_agent/tests/test_voice_service.py](../ninjarobot_pi5_agent/tests/test_voice_service.py) | S, T | Automated checks/support for voice service. |
| [ninjarobot_pi5_agent/tests/test_web.py](../ninjarobot_pi5_agent/tests/test_web.py) | S, T | Automated checks/support for web. |

### ninjarobot_pi5_ide — 93 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [ninjarobot_pi5_ide/pyproject.toml](../ninjarobot_pi5_ide/pyproject.toml) | P | Package metadata, dependencies, entry points, and tool configuration. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/__init__.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/__init__.py) | S | Package exports and initialization (what importing this package makes available). |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/adapters.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/adapters.py) | S | Hardware-neutral adapter boundary used by the deterministic IDE. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/api.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/api.py) | S | Provider-neutral client protocol for the deterministic IDE layer. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/MODEL_LICENSE.md](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/MODEL_LICENSE.md) | I | NinjaRobotPi5 “Hey Ninja” Model. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/hey_Ninja.onnx](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/hey_Ninja.onnx) | P | Packaged learning-model asset; inventoried, not live voice recognition validation. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/openwakeword/ASSET_NOTICE](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/openwakeword/ASSET_NOTICE) | I | Packaged model provenance and license notice. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/openwakeword/embedding_model.onnx](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/openwakeword/embedding_model.onnx) | P | Packaged learning-model asset; inventoried, not live voice recognition validation. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/openwakeword/melspectrogram.onnx](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/openwakeword/melspectrogram.onnx) | P | Packaged learning-model asset; inventoried, not live voice recognition validation. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/openwakeword/silero_vad.onnx](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets/openwakeword/silero_vad.onnx) | P | Packaged learning-model asset; inventoried, not live voice recognition validation. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets.py) | S | Secure read-only defaults and private user behavior storage. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/angry.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/angry.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/celebrate.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/celebrate.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/confusing.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/confusing.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/cry.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/cry.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/curious.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/curious.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/error.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/error.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/error_warning.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/error_warning.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/exciting.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/exciting.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/greeting.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/greeting.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/happy.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/happy.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/idle.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/idle.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/laughing.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/laughing.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/listening.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/listening.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/move_backward.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/move_backward.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/move_forward.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/move_forward.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/sad.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/sad.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/scary.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/scary.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/shy.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/shy.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/sleepy.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/sleepy.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/speaking.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/speaking.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/success.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/success.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/surprising.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/surprising.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/thinking.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/thinking.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/turn_left.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/turn_left.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/turn_right.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/turn_right.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/warning.json](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets/warning.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_drafts.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_drafts.py) | S | Model-friendly behavior drafts compiled into strict IDE definitions. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_models.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_models.py) | S | Strict schemas for behavior assets. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_runtime.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_runtime.py) | S, D | Sequential-stage, concurrent-operation behavior execution. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/buzzer.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/buzzer.py) | S | Bounded GPIO27 buzzer capabilities with cancellation-safe silence. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/camera.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/camera.py) | S, D | Privacy-bounded still-camera integration for the managed pi5camera library. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/cli.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/cli.py) | S, D | Interactive and scriptable Phase 4 NinjaRobot IDE tool. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config.py) | S, D | Strict Project-owned configuration; managed-driver files are never rewritten. See A04/A05. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config_import.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config_import.py) | S, D | Read-only Pi5 configuration discovery and safe config writing. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/display.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/display.py) | S | Serialized ST7789V display capabilities with a hardware-free simulation path. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/distance.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/distance.py) | S | Read-only VL53L0X adapter with lazy managed-driver loading. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/engine.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/engine.py) | S, D | Deterministic execution engine for capability adapters. See A02. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/errors.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/errors.py) | S | Exception wrapper for structured IDE errors. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/face_renderer.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/face_renderer.py) | S | Scalable animated Pillow faces embedded in NinjaRobotPi5. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/hardware_ownership.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/hardware_ownership.py) | S, D | Cross-process ownership for the integrated Raspberry Pi hardware assembly. See A03. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/identity.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/identity.py) | S, D | IDE-owned face enrollment and explicit recognition workflows. See A13. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/integrated.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/integrated.py) | S, D | Integrated RobotAssembly capability client for the single-owner agent service. See A01/A02. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/interactive_tool.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/interactive_tool.py) | S | Blessed-style direct-control menus for the NinjaRobot IDE tool. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/ledger.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/ledger.py) | S | Small durable SQLite ledger for authoritative IDE action state. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/microphone.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/microphone.py) | S, D | Privacy-bounded microphone integration for approved pi5mic device APIs. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/models.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/models.py) | S | Strict, serializable contracts shared across the control boundary. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/qr_display.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/qr_display.py) | S | Deterministic, standards-compatible pairing QR rendering for the IDE display. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/registry.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/registry.py) | S | Deterministic capability registration and adapter lifecycle. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/robot.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/robot.py) | S, D | Project-owned robot assembly for coordinated IDE behavior execution. See A01/A03/A04. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/runtime_control.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/runtime_control.py) | S | Owner-private active behavior registration for cross-process stop. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/safety.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/safety.py) | S, D | Persistent two-level safety state and guarded drive execution. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/scheduler.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/scheduler.py) | S, D | Bounded asynchronous scheduling with deterministic resource ownership. See A02. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/servo.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/servo.py) | S, D | Safety-gated mixed-backend servo capabilities for configured endpoints. See A01/A04. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/simulation.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/simulation.py) | S | Hardware-free drivers used only by the IDE tool simulation path. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/testing.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/testing.py) | S | Deterministic fakes for contract and agent tests. |
| [ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/voice_input.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/voice_input.py) | S, D | IDE-owned bounded wake-word, capture, and transcription state machine. |
| [ninjarobot_pi5_ide/tests/fixtures/failed_dynamic_behavior_payloads.json](../ninjarobot_pi5_ide/tests/fixtures/failed_dynamic_behavior_payloads.json) | P | Structured data/manifest; parsed successfully. |
| [ninjarobot_pi5_ide/tests/test_behavior_assets.py](../ninjarobot_pi5_ide/tests/test_behavior_assets.py) | S, T | Automated checks/support for behavior assets. |
| [ninjarobot_pi5_ide/tests/test_behavior_runtime.py](../ninjarobot_pi5_ide/tests/test_behavior_runtime.py) | S, T | Automated checks/support for behavior runtime. |
| [ninjarobot_pi5_ide/tests/test_buzzer.py](../ninjarobot_pi5_ide/tests/test_buzzer.py) | S, T | Automated checks/support for buzzer. |
| [ninjarobot_pi5_ide/tests/test_camera.py](../ninjarobot_pi5_ide/tests/test_camera.py) | S, T | Automated checks/support for camera. |
| [ninjarobot_pi5_ide/tests/test_config.py](../ninjarobot_pi5_ide/tests/test_config.py) | S, T | Automated checks/support for config. |
| [ninjarobot_pi5_ide/tests/test_config_import.py](../ninjarobot_pi5_ide/tests/test_config_import.py) | S, T | Automated checks/support for config import. |
| [ninjarobot_pi5_ide/tests/test_display.py](../ninjarobot_pi5_ide/tests/test_display.py) | S, T | Automated checks/support for display. |
| [ninjarobot_pi5_ide/tests/test_distance.py](../ninjarobot_pi5_ide/tests/test_distance.py) | S, T | Automated checks/support for distance. |
| [ninjarobot_pi5_ide/tests/test_engine.py](../ninjarobot_pi5_ide/tests/test_engine.py) | S, T | Automated checks/support for engine. |
| [ninjarobot_pi5_ide/tests/test_error_classification.py](../ninjarobot_pi5_ide/tests/test_error_classification.py) | S, T | Automated checks/support for error classification. |
| [ninjarobot_pi5_ide/tests/test_face_renderer.py](../ninjarobot_pi5_ide/tests/test_face_renderer.py) | S, T | Automated checks/support for face renderer. |
| [ninjarobot_pi5_ide/tests/test_hardware_ownership.py](../ninjarobot_pi5_ide/tests/test_hardware_ownership.py) | S, T | Automated checks/support for hardware ownership. |
| [ninjarobot_pi5_ide/tests/test_ide_cli.py](../ninjarobot_pi5_ide/tests/test_ide_cli.py) | S, T | Automated checks/support for ide cli. |
| [ninjarobot_pi5_ide/tests/test_identity.py](../ninjarobot_pi5_ide/tests/test_identity.py) | S, T | Automated checks/support for identity. |
| [ninjarobot_pi5_ide/tests/test_identity_presentation.py](../ninjarobot_pi5_ide/tests/test_identity_presentation.py) | S, T | Automated checks/support for identity presentation. |
| [ninjarobot_pi5_ide/tests/test_integrated_agent_ide.py](../ninjarobot_pi5_ide/tests/test_integrated_agent_ide.py) | S, T | Automated checks/support for integrated agent ide. |
| [ninjarobot_pi5_ide/tests/test_microphone.py](../ninjarobot_pi5_ide/tests/test_microphone.py) | S, T | Automated checks/support for microphone. |
| [ninjarobot_pi5_ide/tests/test_models.py](../ninjarobot_pi5_ide/tests/test_models.py) | S, T | Automated checks/support for models. |
| [ninjarobot_pi5_ide/tests/test_phase2_core.py](../ninjarobot_pi5_ide/tests/test_phase2_core.py) | S, T | Automated checks/support for phase2 core. |
| [ninjarobot_pi5_ide/tests/test_qr_display.py](../ninjarobot_pi5_ide/tests/test_qr_display.py) | S, T | Automated checks/support for qr display. |
| [ninjarobot_pi5_ide/tests/test_runtime_control.py](../ninjarobot_pi5_ide/tests/test_runtime_control.py) | S, T | Automated checks/support for runtime control. |
| [ninjarobot_pi5_ide/tests/test_safety.py](../ninjarobot_pi5_ide/tests/test_safety.py) | S, T | Automated checks/support for safety. |
| [ninjarobot_pi5_ide/tests/test_servo.py](../ninjarobot_pi5_ide/tests/test_servo.py) | S, T | Automated checks/support for servo. |
| [ninjarobot_pi5_ide/tests/test_testing.py](../ninjarobot_pi5_ide/tests/test_testing.py) | S, T | Automated checks/support for testing. |
| [ninjarobot_pi5_ide/tests/test_voice_input.py](../ninjarobot_pi5_ide/tests/test_voice_input.py) | S, T | Automated checks/support for voice input. |

### pi5buzzer — 17 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [pi5buzzer/.python-version](../pi5buzzer/.python-version) | H | Preferred Python interpreter version. |
| [pi5buzzer/LICENSE](../pi5buzzer/LICENSE) | H | License terms shipped with this project/package. |
| [pi5buzzer/README.md](../pi5buzzer/README.md) | D, H | Standalone driver guide; historical features are distinct from integrated support. |
| [pi5buzzer/pyproject.toml](../pi5buzzer/pyproject.toml) | P, H | Package metadata, dependencies, entry points, and tool configuration. |
| [pi5buzzer/src/pi5buzzer/__init__.py](../pi5buzzer/src/pi5buzzer/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5buzzer/src/pi5buzzer/__main__.py](../pi5buzzer/src/pi5buzzer/__main__.py) | S, H | Command entry point when launched as a Python module. |
| [pi5buzzer/src/pi5buzzer/cli/buzzer_tool.py](../pi5buzzer/src/pi5buzzer/cli/buzzer_tool.py) | S, H | Interactive TUI for exercising pi5buzzer on Raspberry Pi 5. |
| [pi5buzzer/src/pi5buzzer/config/config_manager.py](../pi5buzzer/src/pi5buzzer/config/config_manager.py) | S, H | JSON configuration management for pi5buzzer. |
| [pi5buzzer/src/pi5buzzer/core/driver.py](../pi5buzzer/src/pi5buzzer/core/driver.py) | S, H | Core driver and Pi 5 GPIO backend adapter for pi5buzzer. |
| [pi5buzzer/src/pi5buzzer/core/music.py](../pi5buzzer/src/pi5buzzer/core/music.py) | S, H | Music helpers layered on top of the pi5buzzer core driver. |
| [pi5buzzer/src/pi5buzzer/driver.py](../pi5buzzer/src/pi5buzzer/driver.py) | S, H | Compatibility shim for optional future integration surfaces. |
| [pi5buzzer/src/pi5buzzer/notes.py](../pi5buzzer/src/pi5buzzer/notes.py) | S, H | Shared note, keyboard, and emotion sound definitions for pi5buzzer. |
| [pi5buzzer/tests/conftest.py](../pi5buzzer/tests/conftest.py) | S, T, H | Automated checks/support for conftest. |
| [pi5buzzer/tests/test_config.py](../pi5buzzer/tests/test_config.py) | S, T, H | Automated checks/support for config. |
| [pi5buzzer/tests/test_driver.py](../pi5buzzer/tests/test_driver.py) | S, T, H | Automated checks/support for driver. |
| [pi5buzzer/tests/test_music.py](../pi5buzzer/tests/test_music.py) | S, T, H | Automated checks/support for music. |
| [pi5buzzer/uv.lock](../pi5buzzer/uv.lock) | P | Locked dependency versions and download fingerprints; not a security certification. |

### pi5camera — 41 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [pi5camera/README.md](../pi5camera/README.md) | D, H | Standalone driver guide; historical features are distinct from integrated support. |
| [pi5camera/pyproject.toml](../pi5camera/pyproject.toml) | P, H | Package metadata, dependencies, entry points, and tool configuration. |
| [pi5camera/scripts/bootstrap-rpi-standalone.sh](../pi5camera/scripts/bootstrap-rpi-standalone.sh) | P, H | Shell setup/helper program; syntax checked without live deployment. |
| [pi5camera/src/pi5camera/__init__.py](../pi5camera/src/pi5camera/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5camera/src/pi5camera/__main__.py](../pi5camera/src/pi5camera/__main__.py) | S, H | Command entry point when launched as a Python module. |
| [pi5camera/src/pi5camera/cli/__init__.py](../pi5camera/src/pi5camera/cli/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5camera/src/pi5camera/cli/_common.py](../pi5camera/src/pi5camera/cli/_common.py) | S, H | Shared CLI helpers for pi5camera. |
| [pi5camera/src/pi5camera/cli/camera_tool.py](../pi5camera/src/pi5camera/cli/camera_tool.py) | S, H | Interactive camera tool for pi5camera. |
| [pi5camera/src/pi5camera/cli/capture_cmd.py](../pi5camera/src/pi5camera/cli/capture_cmd.py) | S, H | One-shot photo capture command for pi5camera. |
| [pi5camera/src/pi5camera/cli/doctor.py](../pi5camera/src/pi5camera/cli/doctor.py) | S, H | Doctor command for pi5camera. |
| [pi5camera/src/pi5camera/cli/enroll_cmd.py](../pi5camera/src/pi5camera/cli/enroll_cmd.py) | S, H | Enrollment command for pi5camera. |
| [pi5camera/src/pi5camera/cli/manage_faces_cmd.py](../pi5camera/src/pi5camera/cli/manage_faces_cmd.py) | S, H | Manage known faces for pi5camera. |
| [pi5camera/src/pi5camera/cli/recognize_cmd.py](../pi5camera/src/pi5camera/cli/recognize_cmd.py) | S, H | Face-recognition command for pi5camera. |
| [pi5camera/src/pi5camera/cli/setup_cmd.py](../pi5camera/src/pi5camera/cli/setup_cmd.py) | S, H | Guided setup wizard for pi5camera. |
| [pi5camera/src/pi5camera/cli/status.py](../pi5camera/src/pi5camera/cli/status.py) | S, H | Status command for pi5camera. |
| [pi5camera/src/pi5camera/config/__init__.py](../pi5camera/src/pi5camera/config/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5camera/src/pi5camera/config/config_manager.py](../pi5camera/src/pi5camera/config/config_manager.py) | S, H | Configuration management for pi5camera. |
| [pi5camera/src/pi5camera/core/__init__.py](../pi5camera/src/pi5camera/core/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5camera/src/pi5camera/core/camera_backend.py](../pi5camera/src/pi5camera/core/camera_backend.py) | S, H | Camera backend helpers for pi5camera. |
| [pi5camera/src/pi5camera/core/capture.py](../pi5camera/src/pi5camera/core/capture.py) | S, H | One-shot still capture helpers for pi5camera. |
| [pi5camera/src/pi5camera/core/enrollment.py](../pi5camera/src/pi5camera/core/enrollment.py) | S, H | Known-face enrollment workflows for pi5camera. |
| [pi5camera/src/pi5camera/core/recognition.py](../pi5camera/src/pi5camera/core/recognition.py) | S, H | Face-recognition workflow for pi5camera. See A13. |
| [pi5camera/src/pi5camera/driver.py](../pi5camera/src/pi5camera/driver.py) | S, H | Compatibility re-exports for standalone pi5camera usage. |
| [pi5camera/src/pi5camera/environment.py](../pi5camera/src/pi5camera/environment.py) | S, H | Environment and dependency probes for pi5camera. |
| [pi5camera/src/pi5camera/errors.py](../pi5camera/src/pi5camera/errors.py) | S, H | Shared exceptions for pi5camera. |
| [pi5camera/src/pi5camera/models.py](../pi5camera/src/pi5camera/models.py) | S, H | Shared dataclasses and helpers for pi5camera. |
| [pi5camera/src/pi5camera/recognition/__init__.py](../pi5camera/src/pi5camera/recognition/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5camera/src/pi5camera/recognition/base.py](../pi5camera/src/pi5camera/recognition/base.py) | S, H | Recognition backend protocol for pi5camera. |
| [pi5camera/src/pi5camera/recognition/mediapipe_opencv_backend.py](../pi5camera/src/pi5camera/recognition/mediapipe_opencv_backend.py) | S, H | Face-recognition backend using OpenCV (required) + MediaPipe (optional). |
| [pi5camera/src/pi5camera/storage/__init__.py](../pi5camera/src/pi5camera/storage/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5camera/src/pi5camera/storage/face_index.py](../pi5camera/src/pi5camera/storage/face_index.py) | S, H | Known-face index management for pi5camera. |
| [pi5camera/src/pi5camera/storage/pending_records.py](../pi5camera/src/pi5camera/storage/pending_records.py) | S, H | Pending-recognition record management for pi5camera. |
| [pi5camera/src/pi5camera/storage/photo_storage.py](../pi5camera/src/pi5camera/storage/photo_storage.py) | S, H | Photo storage helpers for pi5camera. |
| [pi5camera/tests/test_camera_backend.py](../pi5camera/tests/test_camera_backend.py) | S, T, H | Automated checks/support for camera backend. |
| [pi5camera/tests/test_cli_startup.py](../pi5camera/tests/test_cli_startup.py) | S, T, H | Automated checks/support for cli startup. |
| [pi5camera/tests/test_config_manager.py](../pi5camera/tests/test_config_manager.py) | S, T, H | Automated checks/support for config manager. |
| [pi5camera/tests/test_face_index.py](../pi5camera/tests/test_face_index.py) | S, T, H | Automated checks/support for face index. |
| [pi5camera/tests/test_pending_records.py](../pi5camera/tests/test_pending_records.py) | S, T, H | Automated checks/support for pending records. |
| [pi5camera/tests/test_photo_storage.py](../pi5camera/tests/test_photo_storage.py) | S, T, H | Automated checks/support for photo storage. |
| [pi5camera/tests/test_recognition_flow.py](../pi5camera/tests/test_recognition_flow.py) | S, T, H | Automated checks/support for recognition flow. |
| [pi5camera/uv.lock](../pi5camera/uv.lock) | P, H | Locked dependency versions and download fingerprints; not a security certification. |

### pi5disp — 34 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [pi5disp/.python-version](../pi5disp/.python-version) | H | Preferred Python interpreter version. |
| [pi5disp/LICENSE](../pi5disp/LICENSE) | H | License terms shipped with this project/package. |
| [pi5disp/README.md](../pi5disp/README.md) | D, H | Standalone driver guide; historical features are distinct from integrated support. |
| [pi5disp/display.json](../pi5disp/display.json) | P, H | Structured data/manifest; parsed successfully. |
| [pi5disp/pyproject.toml](../pi5disp/pyproject.toml) | P, H | Package metadata, dependencies, entry points, and tool configuration. |
| [pi5disp/src/pi5disp/__init__.py](../pi5disp/src/pi5disp/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5disp/src/pi5disp/__main__.py](../pi5disp/src/pi5disp/__main__.py) | S, H | Command entry point when launched as a Python module. |
| [pi5disp/src/pi5disp/cli/__init__.py](../pi5disp/src/pi5disp/cli/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5disp/src/pi5disp/cli/_common.py](../pi5disp/src/pi5disp/cli/_common.py) | S, H | Shared CLI helpers for pi5disp. |
| [pi5disp/src/pi5disp/cli/demo_cmd.py](../pi5disp/src/pi5disp/cli/demo_cmd.py) | S, H | Demo command — Bouncing ball animation demo. |
| [pi5disp/src/pi5disp/cli/display_tool.py](../pi5disp/src/pi5disp/cli/display_tool.py) | S, H | Interactive display tool — Menu-driven display testing and configuration. |
| [pi5disp/src/pi5disp/cli/image_cmd.py](../pi5disp/src/pi5disp/cli/image_cmd.py) | S, H | Image command — Display an image file on the screen. |
| [pi5disp/src/pi5disp/cli/info_cmd.py](../pi5disp/src/pi5disp/cli/info_cmd.py) | S, H | Info command — Display driver state and configuration. |
| [pi5disp/src/pi5disp/cli/init_cmd.py](../pi5disp/src/pi5disp/cli/init_cmd.py) | S, H | Init command — First-time display setup wizard. |
| [pi5disp/src/pi5disp/cli/text_cmd.py](../pi5disp/src/pi5disp/cli/text_cmd.py) | S, H | Text command — Display or scroll text on the screen. |
| [pi5disp/src/pi5disp/config/__init__.py](../pi5disp/src/pi5disp/config/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5disp/src/pi5disp/config/config_manager.py](../pi5disp/src/pi5disp/config/config_manager.py) | S, H | Configuration manager for pi5disp display settings. |
| [pi5disp/src/pi5disp/core/__init__.py](../pi5disp/src/pi5disp/core/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5disp/src/pi5disp/core/driver.py](../pi5disp/src/pi5disp/core/driver.py) | S, H | ST7789V display driver for Raspberry Pi 5. |
| [pi5disp/src/pi5disp/core/renderer.py](../pi5disp/src/pi5disp/core/renderer.py) | S, H | Renderer helpers for pi5disp. |
| [pi5disp/src/pi5disp/effects/__init__.py](../pi5disp/src/pi5disp/effects/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5disp/src/pi5disp/effects/text_ticker.py](../pi5disp/src/pi5disp/effects/text_ticker.py) | S, H | Text ticker effect for pi5disp. See A15. |
| [pi5disp/src/pi5disp/fonts/NotoSans-Regular.ttf](../pi5disp/src/pi5disp/fonts/NotoSans-Regular.ttf) | P, H | Packaged display font; loaded successfully in the audit. |
| [pi5disp/src/pi5disp/fonts/NotoSansJP-Regular.otf](../pi5disp/src/pi5disp/fonts/NotoSansJP-Regular.otf) | P, H | Packaged display font; loaded successfully in the audit. |
| [pi5disp/src/pi5disp/fonts/NotoSansTC-Regular.otf](../pi5disp/src/pi5disp/fonts/NotoSansTC-Regular.otf) | P, H | Invalid font: contains an HTML 404 error page; see A15. |
| [pi5disp/tests/conftest.py](../pi5disp/tests/conftest.py) | S, T, H | Automated checks/support for conftest. |
| [pi5disp/tests/test_cli.py](../pi5disp/tests/test_cli.py) | S, T, H | Automated checks/support for cli. |
| [pi5disp/tests/test_config.py](../pi5disp/tests/test_config.py) | S, T, H | Automated checks/support for config. |
| [pi5disp/tests/test_display_tool.py](../pi5disp/tests/test_display_tool.py) | S, T, H | Automated checks/support for display tool. |
| [pi5disp/tests/test_driver.py](../pi5disp/tests/test_driver.py) | S, T, H | Automated checks/support for driver. |
| [pi5disp/tests/test_renderer.py](../pi5disp/tests/test_renderer.py) | S, T, H | Automated checks/support for renderer. |
| [pi5disp/tests/test_smoke.py](../pi5disp/tests/test_smoke.py) | S, T, H | Automated checks/support for smoke. |
| [pi5disp/tests/test_text_ticker.py](../pi5disp/tests/test_text_ticker.py) | S, T, H | Automated checks/support for text ticker. |
| [pi5disp/uv.lock](../pi5disp/uv.lock) | P, H | Locked dependency versions and download fingerprints; not a security certification. |

### pi5mic — 70 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [pi5mic/LICENSE](../pi5mic/LICENSE) | H | License terms shipped with this project/package. |
| [pi5mic/README.md](../pi5mic/README.md) | D, H | Standalone driver guide; historical features are distinct from integrated support. |
| [pi5mic/pyproject.toml](../pi5mic/pyproject.toml) | P, H | Package metadata, dependencies, entry points, and tool configuration. |
| [pi5mic/src/pi5mic/__init__.py](../pi5mic/src/pi5mic/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/__main__.py](../pi5mic/src/pi5mic/__main__.py) | S, H | Command entry point when launched as a Python module. |
| [pi5mic/src/pi5mic/cli/__init__.py](../pi5mic/src/pi5mic/cli/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/cli/_common.py](../pi5mic/src/pi5mic/cli/_common.py) | S, H | Shared CLI helpers for pi5mic. |
| [pi5mic/src/pi5mic/cli/config_cmd.py](../pi5mic/src/pi5mic/cli/config_cmd.py) | S, H | Config management CLI for pi5mic. |
| [pi5mic/src/pi5mic/cli/doctor.py](../pi5mic/src/pi5mic/cli/doctor.py) | S, H | Diagnostics for pi5mic. |
| [pi5mic/src/pi5mic/cli/install_cmd.py](../pi5mic/src/pi5mic/cli/install_cmd.py) | S, H | Install and registration helpers for pi5mic. |
| [pi5mic/src/pi5mic/cli/mic_tool.py](../pi5mic/src/pi5mic/cli/mic_tool.py) | S, H | Simple interactive menu for pi5mic. |
| [pi5mic/src/pi5mic/cli/run_cmd.py](../pi5mic/src/pi5mic/cli/run_cmd.py) | S, H | Interactive run flow for pi5mic. |
| [pi5mic/src/pi5mic/cli/setup_cmd.py](../pi5mic/src/pi5mic/cli/setup_cmd.py) | S, H | Interactive setup wizard for pi5mic. |
| [pi5mic/src/pi5mic/cli/status.py](../pi5mic/src/pi5mic/cli/status.py) | S, H | Status reporting for pi5mic. |
| [pi5mic/src/pi5mic/cli/voiceinput_tool.py](../pi5mic/src/pi5mic/cli/voiceinput_tool.py) | S, H | Manual control surface for the always-on pi5mic voice input loop. |
| [pi5mic/src/pi5mic/config/__init__.py](../pi5mic/src/pi5mic/config/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/config/config_manager.py](../pi5mic/src/pi5mic/config/config_manager.py) | S, H | Configuration management for pi5mic. |
| [pi5mic/src/pi5mic/core/__init__.py](../pi5mic/src/pi5mic/core/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/core/audio_backend.py](../pi5mic/src/pi5mic/core/audio_backend.py) | S, H | Shared audio-backend import helpers for pi5mic. |
| [pi5mic/src/pi5mic/core/devices.py](../pi5mic/src/pi5mic/core/devices.py) | S, H | Audio device helpers for pi5mic. |
| [pi5mic/src/pi5mic/core/listener.py](../pi5mic/src/pi5mic/core/listener.py) | S, H | Local voice listener state machine for pi5mic. |
| [pi5mic/src/pi5mic/core/recorder.py](../pi5mic/src/pi5mic/core/recorder.py) | S, H | Bounded WAV recording helpers for pi5mic. |
| [pi5mic/src/pi5mic/core/session.py](../pi5mic/src/pi5mic/core/session.py) | S, H | State snapshots for the pi5mic listener. |
| [pi5mic/src/pi5mic/core/system_info.py](../pi5mic/src/pi5mic/core/system_info.py) | S, H | Host and Raspberry Pi diagnostics helpers. |
| [pi5mic/src/pi5mic/core/voiceinput.py](../pi5mic/src/pi5mic/core/voiceinput.py) | S, H | Always-on voice input loop and service-state helpers for pi5mic. |
| [pi5mic/src/pi5mic/driver.py](../pi5mic/src/pi5mic/driver.py) | S, H | Compatibility re-exports for standalone pi5mic usage. |
| [pi5mic/src/pi5mic/errors.py](../pi5mic/src/pi5mic/errors.py) | S, H | Custom exceptions for pi5mic. |
| [pi5mic/src/pi5mic/install/__init__.py](../pi5mic/src/pi5mic/install/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/install/openwakeword.py](../pi5mic/src/pi5mic/install/openwakeword.py) | S, H | Install and runtime helpers for openWakeWord. |
| [pi5mic/src/pi5mic/install/whisper_cpp.py](../pi5mic/src/pi5mic/install/whisper_cpp.py) | S, H | Helpers for locating and validating whisper.cpp assets. |
| [pi5mic/src/pi5mic/integration/__init__.py](../pi5mic/src/pi5mic/integration/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/integration/delivery.py](../pi5mic/src/pi5mic/integration/delivery.py) | S, H | Delivery-policy helpers for pi5mic. |
| [pi5mic/src/pi5mic/integration/openclaw_session.py](../pi5mic/src/pi5mic/integration/openclaw_session.py) | S, H | Helpers for OpenClaw session-id compatibility in pi5mic. |
| [pi5mic/src/pi5mic/integration/openclaw_setup.py](../pi5mic/src/pi5mic/integration/openclaw_setup.py) | S, H | OpenClaw autodiscovery and readiness helpers for pi5mic. |
| [pi5mic/src/pi5mic/integration/presence.py](../pi5mic/src/pi5mic/integration/presence.py) | S, H | OpenClaw presence-control helpers for pi5mic. |
| [pi5mic/src/pi5mic/models.py](../pi5mic/src/pi5mic/models.py) | S, H | Data models for pi5mic. |
| [pi5mic/src/pi5mic/stt/__init__.py](../pi5mic/src/pi5mic/stt/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/stt/base.py](../pi5mic/src/pi5mic/stt/base.py) | S, H | Speech-to-text backend abstractions. |
| [pi5mic/src/pi5mic/stt/gemini.py](../pi5mic/src/pi5mic/stt/gemini.py) | S, H | Gemini batch speech-to-text backend. |
| [pi5mic/src/pi5mic/stt/whisper_cpp.py](../pi5mic/src/pi5mic/stt/whisper_cpp.py) | S, H | whisper.cpp speech-to-text backend. |
| [pi5mic/src/pi5mic/transport/__init__.py](../pi5mic/src/pi5mic/transport/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/transport/base.py](../pi5mic/src/pi5mic/transport/base.py) | S, H | Text transport abstractions for pi5mic. |
| [pi5mic/src/pi5mic/transport/openclaw_cli.py](../pi5mic/src/pi5mic/transport/openclaw_cli.py) | S, H | OpenClaw CLI-backed transport for pi5mic. |
| [pi5mic/src/pi5mic/vad/__init__.py](../pi5mic/src/pi5mic/vad/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/vad/base.py](../pi5mic/src/pi5mic/vad/base.py) | S, H | Voice activity detection abstractions for pi5mic. |
| [pi5mic/src/pi5mic/vad/silence.py](../pi5mic/src/pi5mic/vad/silence.py) | S, H | Simple silence-stop detector for pi5mic. |
| [pi5mic/src/pi5mic/wakeword/__init__.py](../pi5mic/src/pi5mic/wakeword/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5mic/src/pi5mic/wakeword/base.py](../pi5mic/src/pi5mic/wakeword/base.py) | S, H | Wake-word detector abstractions for pi5mic. |
| [pi5mic/src/pi5mic/wakeword/openwakeword.py](../pi5mic/src/pi5mic/wakeword/openwakeword.py) | S, H | Optional openWakeWord wake-word backend. |
| [pi5mic/tests/test_cli.py](../pi5mic/tests/test_cli.py) | S, T, H | Automated checks/support for cli. |
| [pi5mic/tests/test_config.py](../pi5mic/tests/test_config.py) | S, T, H | Automated checks/support for config. |
| [pi5mic/tests/test_devices.py](../pi5mic/tests/test_devices.py) | S, T, H | Automated checks/support for devices. |
| [pi5mic/tests/test_doctor.py](../pi5mic/tests/test_doctor.py) | S, T, H | Automated checks/support for doctor. |
| [pi5mic/tests/test_listener.py](../pi5mic/tests/test_listener.py) | S, T, H | Automated checks/support for listener. |
| [pi5mic/tests/test_mic_tool.py](../pi5mic/tests/test_mic_tool.py) | S, T, H | Automated checks/support for mic tool. |
| [pi5mic/tests/test_mic_tool_setup.py](../pi5mic/tests/test_mic_tool_setup.py) | S, T, H | Automated checks/support for mic tool setup. |
| [pi5mic/tests/test_openclaw_session.py](../pi5mic/tests/test_openclaw_session.py) | S, T, H | Automated checks/support for openclaw session. |
| [pi5mic/tests/test_openclaw_setup.py](../pi5mic/tests/test_openclaw_setup.py) | S, T, H | Automated checks/support for openclaw setup. |
| [pi5mic/tests/test_recorder.py](../pi5mic/tests/test_recorder.py) | S, T, H | Automated checks/support for recorder. |
| [pi5mic/tests/test_stt_gemini.py](../pi5mic/tests/test_stt_gemini.py) | S, T, H | Automated checks/support for stt gemini. |
| [pi5mic/tests/test_stt_whisper_cpp.py](../pi5mic/tests/test_stt_whisper_cpp.py) | S, T, H | Automated checks/support for stt whisper cpp. |
| [pi5mic/tests/test_system_info.py](../pi5mic/tests/test_system_info.py) | S, T, H | Automated checks/support for system info. |
| [pi5mic/tests/test_transport_openclaw.py](../pi5mic/tests/test_transport_openclaw.py) | S, T, H | Automated checks/support for transport openclaw. |
| [pi5mic/tests/test_vad.py](../pi5mic/tests/test_vad.py) | S, T, H | Automated checks/support for vad. |
| [pi5mic/tests/test_voiceinput.py](../pi5mic/tests/test_voiceinput.py) | S, T, H | Automated checks/support for voiceinput. |
| [pi5mic/tests/test_voiceinput_tool.py](../pi5mic/tests/test_voiceinput_tool.py) | S, T, H | Automated checks/support for voiceinput tool. |
| [pi5mic/tests/test_wakeword.py](../pi5mic/tests/test_wakeword.py) | S, T, H | Automated checks/support for wakeword. |
| [pi5mic/uv.lock](../pi5mic/uv.lock) | P, H | Locked dependency versions and download fingerprints; not a security certification. |
| [pi5mic/voiceinput/hey_Ninja.onnx](../pi5mic/voiceinput/hey_Ninja.onnx) | P, H | Packaged learning-model asset; inventoried, not live voice recognition validation. |
| [pi5mic/voiceinput/hey_Ninja.tflite](../pi5mic/voiceinput/hey_Ninja.tflite) | P, H | Packaged learning-model asset; inventoried, not live voice recognition validation. |

### pi5servo — 43 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [pi5servo/.python-version](../pi5servo/.python-version) | H | Preferred Python interpreter version. |
| [pi5servo/LICENSE](../pi5servo/LICENSE) | H | License terms shipped with this project/package. |
| [pi5servo/README.md](../pi5servo/README.md) | D, H | Standalone driver guide; historical features are distinct from integrated support. |
| [pi5servo/pyproject.toml](../pi5servo/pyproject.toml) | P, H | Package metadata, dependencies, entry points, and tool configuration. |
| [pi5servo/src/pi5servo/__init__.py](../pi5servo/src/pi5servo/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5servo/src/pi5servo/__main__.py](../pi5servo/src/pi5servo/__main__.py) | S, H | Command entry point when launched as a Python module. |
| [pi5servo/src/pi5servo/cli/__init__.py](../pi5servo/src/pi5servo/cli/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5servo/src/pi5servo/cli/_common.py](../pi5servo/src/pi5servo/cli/_common.py) | S, H | Shared CLI helpers for backend-aware standalone servo commands. |
| [pi5servo/src/pi5servo/cli/calib.py](../pi5servo/src/pi5servo/cli/calib.py) | S, H | Interactive servo calibration command. |
| [pi5servo/src/pi5servo/cli/cmd.py](../pi5servo/src/pi5servo/cli/cmd.py) | S, H | CLI command execution for servo command strings. |
| [pi5servo/src/pi5servo/cli/config_cmd.py](../pi5servo/src/pi5servo/cli/config_cmd.py) | S, H | Config management CLI commands. |
| [pi5servo/src/pi5servo/cli/move.py](../pi5servo/src/pi5servo/cli/move.py) | S, H | CLI single-servo movement command. |
| [pi5servo/src/pi5servo/cli/servo_tool.py](../pi5servo/src/pi5servo/cli/servo_tool.py) | S, H | Interactive servo control tool. |
| [pi5servo/src/pi5servo/cli/status.py](../pi5servo/src/pi5servo/cli/status.py) | S, H | CLI status command for servo system configuration and backend readiness. |
| [pi5servo/src/pi5servo/config/__init__.py](../pi5servo/src/pi5servo/config/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5servo/src/pi5servo/config/config_manager.py](../pi5servo/src/pi5servo/config/config_manager.py) | S, H | Configuration manager for servo calibration data and backend settings. |
| [pi5servo/src/pi5servo/core/__init__.py](../pi5servo/src/pi5servo/core/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5servo/src/pi5servo/core/backend.py](../pi5servo/src/pi5servo/core/backend.py) | S, H | Servo pulse backend abstractions for Raspberry Pi 5. |
| [pi5servo/src/pi5servo/core/backend_errors.py](../pi5servo/src/pi5servo/core/backend_errors.py) | S, H | Shared error types for servo pulse backends. |
| [pi5servo/src/pi5servo/core/backends/__init__.py](../pi5servo/src/pi5servo/core/backends/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5servo/src/pi5servo/core/backends/dfr0566.py](../pi5servo/src/pi5servo/core/backends/dfr0566.py) | S, H | DFRobot DFR0566 PWM backend for servo channels 1..4 over I2C. |
| [pi5servo/src/pi5servo/core/backends/hardware_pwm.py](../pi5servo/src/pi5servo/core/backends/hardware_pwm.py) | S, H | RP1 hardware PWM backend for header-connected servos on Raspberry Pi 5. |
| [pi5servo/src/pi5servo/core/backends/pca9685.py](../pi5servo/src/pi5servo/core/backends/pca9685.py) | S, H | Optional PCA9685 backend for advanced external PWM control. |
| [pi5servo/src/pi5servo/core/backends/pwm_pio.py](../pi5servo/src/pi5servo/core/backends/pwm_pio.py) | S, H | Placeholder for a future pwm-pio backend on Raspberry Pi 5. |
| [pi5servo/src/pi5servo/core/endpoint.py](../pi5servo/src/pi5servo/core/endpoint.py) | S, H | Endpoint helpers for native GPIO and external servo transports. |
| [pi5servo/src/pi5servo/core/multi_servos.py](../pi5servo/src/pi5servo/core/multi_servos.py) | S, H | Multi-servo group controller with abort support. |
| [pi5servo/src/pi5servo/core/servo.py](../pi5servo/src/pi5servo/core/servo.py) | S, H | Single servo control with calibration support and pluggable backends. |
| [pi5servo/src/pi5servo/driver.py](../pi5servo/src/pi5servo/driver.py) | S, H | Compatibility re-exports for future integration hooks. |
| [pi5servo/src/pi5servo/motion/__init__.py](../pi5servo/src/pi5servo/motion/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5servo/src/pi5servo/motion/calculator.py](../pi5servo/src/pi5servo/motion/calculator.py) | S, H | Velocity and duration calculations for servo movement. |
| [pi5servo/src/pi5servo/motion/easing.py](../pi5servo/src/pi5servo/motion/easing.py) | S, H | Easing functions for smooth servo movement. |
| [pi5servo/src/pi5servo/parser/__init__.py](../pi5servo/src/pi5servo/parser/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5servo/src/pi5servo/parser/command.py](../pi5servo/src/pi5servo/parser/command.py) | S, H | Command string parser for movement-tool format. |
| [pi5servo/tests/__init__.py](../pi5servo/tests/__init__.py) | S, T, H | Automated checks/support for   init  . |
| [pi5servo/tests/conftest.py](../pi5servo/tests/conftest.py) | S, T, H | Automated checks/support for conftest. |
| [pi5servo/tests/test_backend.py](../pi5servo/tests/test_backend.py) | S, T, H | Automated checks/support for backend. |
| [pi5servo/tests/test_cli.py](../pi5servo/tests/test_cli.py) | S, T, H | Automated checks/support for cli. |
| [pi5servo/tests/test_config.py](../pi5servo/tests/test_config.py) | S, T, H | Automated checks/support for config. |
| [pi5servo/tests/test_core.py](../pi5servo/tests/test_core.py) | S, T, H | Automated checks/support for core. |
| [pi5servo/tests/test_motion.py](../pi5servo/tests/test_motion.py) | S, T, H | Automated checks/support for motion. |
| [pi5servo/tests/test_parser.py](../pi5servo/tests/test_parser.py) | S, T, H | Automated checks/support for parser. |
| [pi5servo/tests/test_servo_tool.py](../pi5servo/tests/test_servo_tool.py) | S, T, H | Automated checks/support for servo tool. |
| [pi5servo/uv.lock](../pi5servo/uv.lock) | P, H | Locked dependency versions and download fingerprints; not a security certification. |

### pi5vl53l0x — 17 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [pi5vl53l0x/.python-version](../pi5vl53l0x/.python-version) | H | Preferred Python interpreter version. |
| [pi5vl53l0x/LICENSE](../pi5vl53l0x/LICENSE) | H | License terms shipped with this project/package. |
| [pi5vl53l0x/README.md](../pi5vl53l0x/README.md) | D, H | Standalone driver guide; historical features are distinct from integrated support. |
| [pi5vl53l0x/pyproject.toml](../pi5vl53l0x/pyproject.toml) | P, H | Package metadata, dependencies, entry points, and tool configuration. |
| [pi5vl53l0x/src/pi5vl53l0x/__init__.py](../pi5vl53l0x/src/pi5vl53l0x/__init__.py) | S, H | Package exports and initialization (what importing this package makes available). |
| [pi5vl53l0x/src/pi5vl53l0x/__main__.py](../pi5vl53l0x/src/pi5vl53l0x/__main__.py) | S, H | Command entry point when launched as a Python module. |
| [pi5vl53l0x/src/pi5vl53l0x/cli/sensor_tool.py](../pi5vl53l0x/src/pi5vl53l0x/cli/sensor_tool.py) | S, H | VL53L0X sensor CLI tool for Raspberry Pi 5 standalone use. |
| [pi5vl53l0x/src/pi5vl53l0x/config/config_manager.py](../pi5vl53l0x/src/pi5vl53l0x/config/config_manager.py) | S, H | Configuration manager for VL53L0X sensor settings. |
| [pi5vl53l0x/src/pi5vl53l0x/core/i2c.py](../pi5vl53l0x/src/pi5vl53l0x/core/i2c.py) | S, H | Thread-safe I2C bus wrapper with retry and recovery for Raspberry Pi 5. |
| [pi5vl53l0x/src/pi5vl53l0x/core/sensor.py](../pi5vl53l0x/src/pi5vl53l0x/core/sensor.py) | S, H | VL53L0X Time-of-Flight distance sensor driver. |
| [pi5vl53l0x/src/pi5vl53l0x/driver.py](../pi5vl53l0x/src/pi5vl53l0x/driver.py) | S, H | Backward-compatibility shim for pi5vl53l0x.driver. |
| [pi5vl53l0x/src/pi5vl53l0x/registers.py](../pi5vl53l0x/src/pi5vl53l0x/registers.py) | S, H | VL53L0X register constants with semantic names. |
| [pi5vl53l0x/tests/test_cli.py](../pi5vl53l0x/tests/test_cli.py) | S, T, H | Automated checks/support for cli. |
| [pi5vl53l0x/tests/test_config.py](../pi5vl53l0x/tests/test_config.py) | S, T, H | Automated checks/support for config. |
| [pi5vl53l0x/tests/test_i2c.py](../pi5vl53l0x/tests/test_i2c.py) | S, T, H | Automated checks/support for i2c. |
| [pi5vl53l0x/tests/test_sensor.py](../pi5vl53l0x/tests/test_sensor.py) | S, T, H | Automated checks/support for sensor. |
| [pi5vl53l0x/uv.lock](../pi5vl53l0x/uv.lock) | P, H | Locked dependency versions and download fingerprints; not a security certification. |

### scripts — 8 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [scripts/benchmark_agent_memory.py](../scripts/benchmark_agent_memory.py) | S, D | Synthetic, non-hardware SQLite retrieval benchmark. |
| [scripts/bootstrap-rpi-camera-workspace.sh](../scripts/bootstrap-rpi-camera-workspace.sh) | D, P | Shell setup/helper program; syntax checked without live deployment. |
| [scripts/configure_rpi_boot.py](../scripts/configure_rpi_boot.py) | S, D | Render and validate the NinjaRobotPi5 Raspberry Pi PWM boot configuration. See A09. |
| [scripts/install-rpi.sh](../scripts/install-rpi.sh) | D, P | Shell setup/helper program; syntax checked without live deployment. |
| [scripts/install-versions.env](../scripts/install-versions.env) | D | Installer version pins; see A11 for verification gaps. |
| [scripts/validate_face_recognition_backend.py](../scripts/validate_face_recognition_backend.py) | S, D | Validate the non-hardware OpenCV API required by pi5camera recognition. |
| [scripts/verify_immutable_drivers.py](../scripts/verify_immutable_drivers.py) | S, D | Verify copied Pi5 libraries against their import and repair manifests. |
| [scripts/verify_workspace_driver_sources.py](../scripts/verify_workspace_driver_sources.py) | S, D | Verify that the root environment executes managed drivers from this checkout. |

### tests — 5 files

| File | Inspection | Responsibility or observation |
| --- | --- | --- |
| [tests/test_architecture_boundaries.py](../tests/test_architecture_boundaries.py) | S, T | Automated checks/support for architecture boundaries. |
| [tests/test_face_recognition_dependency.py](../tests/test_face_recognition_dependency.py) | S, T | Automated checks/support for face recognition dependency. |
| [tests/test_repository_governance.py](../tests/test_repository_governance.py) | S, T | Automated checks/support for repository governance. |
| [tests/test_rpi_installer.py](../tests/test_rpi_installer.py) | S, T | Automated checks/support for rpi installer. |
| [tests/test_workspace_driver_sources.py](../tests/test_workspace_driver_sources.py) | S, T | Automated checks/support for workspace driver sources. |

Inventory total: **509 original tracked files**. This report is the additional
audit deliverable. The untracked wiki and ignored historical runtime are
excluded as described in the scope.

The next safe action is to agree and approve Phase 1’s safety contract and
regression cases, then implement those repairs before further feature work.
