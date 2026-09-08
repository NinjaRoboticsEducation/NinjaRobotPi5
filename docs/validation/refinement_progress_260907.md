# Refinement implementation progress — 7 September 2026

**Later update — face cleanup approved and implemented:** the owner's 9 September
instruction authorized the F08 driver repair. It now passes the independent camera
suite and focused cleanup tests. See the [repair record](refinement_f08_face_cleanup_260909.md)
and [updated walkthrough](refinement_phase2_walkthrough_260909.md#face-recognition-cleanup-tests).
Earlier entries below describe the pre-repair checkpoint. The existing consolidated
wiki proposal still calls face cleanup pending and must be refreshed before approval
or publication; its earlier isolated-preview result is historical. The font repair,
monetary-cap decision and physical acceptance remain separate.

This record tracks the approved refinement. The latest owner instruction defers
all documentation/wiki work during code implementation, then consolidates it
once at the Phase 2 checkpoint and pauses before Phase 3. This replaces the earlier
deferral until all refinement phases. The old F02-only proposals remain historical
and must not be applied to the current checkout.

## Current checkpoint — 9 September 2026

Phase 2 core implementation and the full software gate pass. Development is
paused for the owner's manual tests. Phases 3–5 have not started. Phase 0C face
cleanup and Phase 1 font repair remain pending their separate managed-driver
approvals. T07 usage limits are implemented; a strict currency-denominated spending
cap is **not** implemented and remains an explicit requirement gap.

The final gate passed 734 root tests (one existing Starlette warning), Ruff lint,
format checks (401 files), Mypy (88 source files), compilation, JavaScript syntax,
both driver verifiers and `git diff --check`. Driver integrity still covers 222
managed files, six drivers and 55 pre-existing authorized repairs. No live
hardware, capture, service, deployment or power test ran.

Phase 2 includes durable scoped request/reminder records, exact-time drafts and
confirmation, repeat/snooze/cancel, missed/uncertain recovery, offline direct task
controls, browser task review and safe tool evidence. Memory review exposes source,
confidence and confirmation; editing/forgetting updates effective structured
preferences, and contradictory inference cannot replace a confirmed value.
Notification cleanup pauses during profile deletion/reset. Final regressions
covered recurrence after snooze, clock-change result length, pause/cancel cleanup,
model-input rejection, runtime cleanup failure and the real IDE draft compiler.

Use the [walkthrough and manual tests](refinement_phase2_walkthrough_260909.md)
and [final handoff status](refinement_phase2_handoff_260909.md).
Consolidated dated manuals are prepared under the wiki's `2026-09-09` source
folders. Searchable page publication requires the exact semantic diff review;
existing pages must not be mistaken for documentation of the new checkpoint.
The historical entries below preserve the progression of earlier gates.

## Phase 0A — code validated, physical checks outstanding

| Feature | Implemented behavior | Validation |
| --- | --- | --- |
| F01 — movement safety | Raw integrated servo moves use the existing motion controller, including system/motion stop checks, distance/voltage monitoring, watchdog, a nine-second ramp deadline and final output-off cleanup. A scoped authorization value prevents unrelated tasks from borrowing an active movement's permission. Preparation checks run again after asynchronous startup/centering; cancellation waits for a started centering write before final zero output. Integrated low-level output/capture/ranging actions also respect system stop. | Simulated stopped-state tests for raw and behavior routes, output-off checks, unrelated-task rejection, cancellation/stop during centering, and existing motion/watchdog tests passed. |
| F02 — stop dispatch | Retains the independent trusted stop path. Corrected actual servo/buzzer stop descriptors to include their conflicting resources, so queued work is cancelled too. Interrupted action records now truthfully use the existing `cancelled` status rather than reporting success. | Full/blocked queues, concurrent/duplicate stops, partial lock cleanup, web permission revocation and physical-cleanup dispatch order passed. Updated real-adapter tests verify cancellation and silence. |
| F03 — ownership | All six retained real-device builders acquire the same IDE hardware-owner lock before adapter startup. Ownership releases on startup failure or normal close. The retained real-servo builder uses an IDE-owned guarded servo/distance assembly; it does not start camera, microphone, greetings or the Agent service. | All six builder conflict tests passed with registry startup prohibited; fake successful/failed engine lifecycle verified lock release. Existing CLI tests passed. |
| F04 — disabled devices and wiring | Disabled servo/display/buzzer devices do not initialize or recover their drivers. Dependent behaviors reject before producing output. Resume checks only enabled devices. Configuration rejects collisions involving native servo pins, display controls, SPI0 pins and I2C1 pins; HAT channels remain distinct from GPIO. | Disabled factory calls prohibited; disabled actions/recovery rejected; resume with disabled optional devices passed. Sixteen conflict cases and disabled-pin reuse passed. |

F04's feature gate passed with 611 root tests. F03's focused gate passed 35 tests.
After F01 and the combined phase 0A changes, **631 root tests passed**. The full
phase gate also passed driver integrity, checkout driver-source verification,
compilation, Ruff lint/format checks and Mypy type checks. The baseline Starlette
HTTP test-client deprecation warning remains; no dependency change was made to
silence it. Six managed driver directories and their baseline/authorization records
remain unchanged. No live robot, service, camera, microphone or power command ran.

From the robot root, the gate used the existing environment without changing its
packages:

```bash
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py
uv run --frozen --no-sync python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen --no-sync pytest -q -m 'not hardware and not provider_live'
git diff --check
```

These are software results, not a physical stopping-time guarantee. Hardware calls
that block inside a driver cannot be forcibly terminated safely by Python task
cancellation. Existing watchdog zero-output behavior remains, and device ownership
must be retained until a started write finishes. Existing continuous movement
behaviors retain their stop-driven hold policy; only raw endpoint ramps gain the
explicit bounded lifetime. Existing invalid-distance warning policy is unchanged.

## Documentation work queued for final consolidation

Update the development guide, installation/operation guidance, development log,
architecture/features/history pages and implementation fingerprints for the
movement guards, independent stop path, ownership, disabled-device behavior and
pin validation. Preserve explanations of continuous movement and limitations.
No new dependency or service was introduced in phase 0A, so third-party notices
and service setup currently need no substantive change. Later phases may change
that assessment.

## Manual Pi validation — not performed

| Category | Operator check and expected result | Recovery if it fails |
| --- | --- | --- |
| Safe smoke, no hardware | Run the software gate and validate a copy of the configuration. Conflicting enabled pins must fail with the pin and owners named; disabled-device pin reuse may pass. | Keep the active configuration untouched; correct the copied file before considering deployment. |
| Device communication | With wheels raised and no movement command, inspect existing health. A deliberately disabled device must stay unavailable and must not be initialized by resume. Test a copied configuration under an operator-controlled session. | Keep the robot stopped; restore the prior private configuration and inspect the reported error. |
| Actuator movement | Only with an operator ready to remove power, verify short existing motion and a bounded raw endpoint command, then stop/cancel. Confirm actual zero output and no queued restart. Verify stopped requests refuse movement, and a second real-device process reports ownership conflict. | Remove power on unexpected movement, stop the service under operator control and retain evidence before further tests. |
| Power risk | No power, UPS, boot or shutdown code changed in this phase. No power-off test is required. | Do not introduce a power operation into the automated gate. |

Do not run simultaneous live driver owners to test the lock; keep the second
command at the ownership rejection boundary. No capture is needed for these
checks. Before later deployment, preserve private configuration and data. Rollback
means reverting only the reviewed code patch after the robot is stopped, retaining
unrelated changes and registered source history, then repeating software validation.

## Remaining work

## Phase 0B — installation checks implemented; persistence work next

F05 now adds `ninjarobot_pi5_cli doctor --profile hardware|development`.
It reports the active interpreter and environment, missing packages, enabled-device
requirements, optional checkout provenance and repair guidance without importing
drivers or opening devices. Package discovery is explicitly not a physical health
or native-library compatibility test. Invalid configuration values are not echoed.
The report is reusable from the later H07 guided setup work.

`./install.sh --profile development` installs existing locked development packages
in `.venv-dev`; hardware remains the default installation profile in `.venv`.
Both profiles retain check/preview behavior. The new environment is ignored by Git.
The hardware installer's final integrity command uses `--no-sync`, avoiding an
unnecessary environment synchronization after hardware extras were installed.
The readiness check also runs the doctor. No environment was installed or changed
during this implementation; shell tests used previews only.

Boot-text rendering and validation now account for conditional sections, reject
ambiguous conditional PWM overlays and included files for manual review, reject
malformed/duplicate blocks and duplicate active overlays, and refuse to silently
move later settings ahead of the managed block. An overlay under `[none]` no
longer satisfies readiness. Tests use strings and temporary files, never `/boot`.
The conservative section handling follows the
[Raspberry Pi conditional-filter documentation](https://www.raspberrypi.com/documentation/computers/config_txt.html).
The separate development environment follows
[uv's environment-path documentation](https://docs.astral.sh/uv/concepts/projects/config/#project-environment-path).

Combined gate: **654 tests passed**, Ruff lint/format (385 files), Mypy (82 source
files), compilation, both driver verifiers and `git diff --check` passed. The same
baseline Starlette warning remains. Early new-test failures (default configuration
requirements and frozen configuration fixtures) were repaired before this gate.

F05 still needs the remaining installer download-provenance review; do not mark its
entire checklist complete yet. Queue installation/development guidance and history
updates for final wiki consolidation. Safe smoke: run the doctor and installation
previews; missing modules must have a repair instruction. Communication, movement
and power tests are not needed for these read-only checks. Any later live boot-file
application requires operator review of the generated text and preservation of the
existing installer backup. No live boot application or reboot was performed.

### F06 — backup and restore code validated on 8 September

The existing deployment backup/rollback commands now delegate to `backup.py`.
New archives include the configured face data, private behaviors, servo calibration,
safety state and web certificate/key, alongside the original configuration, secrets,
databases, skills and benchmark files. Empty directories and owner-executable files
are preserved. The archive inventory records missing optional sources explicitly.
Archives are private during creation and published without overwriting an existing
destination. Links, overlapping source roots and unsupported files are rejected.

SQLite uses its supported snapshot operation so committed entries in a write-ahead
log (the database's pending-change file) are included. Each database is consistent;
stop other writers when a single point in time across several files is required.
The snapshot operation has a ten-second progress deadline. Reference:
[Python's SQLite backup interface](https://docs.python.org/3.11/library/sqlite3.html#sqlite3.Connection.backup).

Restore checks the entire bounded archive, paths, duplicate names, new-format file
hashes, configuration and database integrity before replacing any target. It accepts
the older archive structure within these stricter checks. Paths come from current
configuration, not from the archive's declared inventory. If the current configuration
is unreadable, only explicitly selected deployment paths can be restored; optional
paths require repairing the configuration first. A backup cannot silently change
the configured persistent paths when the current configuration is valid.

Restore acquires the existing service and hardware ownership locks, refuses pending
database journal files and preserves an existing safety-state file. It replaces
files atomically one at a time and restores originals on an ordinary failure. If
rollback also fails, private original copies and `recovery.json` remain beside the
configuration; another restore refuses until that recovery is reviewed. Newer files
absent from the archive are retained. The shared service lock now retains its inode
(the underlying file identity), closing an unlink/reacquisition race exposed by this
work. This does not start or stop a live service during tests.

Validation: **671 root tests passed**; 17 focused backup tests cover journal content,
optional sources, empty directories, output privacy/no overwrite, links, late invalid
members, bad configuration, duplicate members, hashes, size limits, current safety,
rollback and rollback failure, existing journals, and competing owners. Ruff lint,
format (387 files), compilation, Mypy (83 files), both driver checks and whitespace
checks passed. The new-test setup/type errors were corrected before the final gate.
All fixture paths and HOME were redirected to temporary directories; no private
operator database, backup, media or live hardware was inspected or restored.

Safe smoke: back up and restore an isolated copied configuration with disposable
data, verify restored rows and a deliberately retained newer file. Communication
and actuator-moving tests are unnecessary. Do not test power loss on a live robot:
the multi-file restore is not one filesystem transaction, and abrupt termination
can require manual recovery from the retained journal. Keep the service stopped
until originals and intended state have been checked. No power-loss test or automatic
crash-recovery claim is made. Final manual/wiki consolidation must include these
limitations, trusted-backup handling, recovery instructions and current-lock behavior.

### F05 installer provenance review completed on 8 September

The installer now checks recorded uv/Ollama script hashes before execution, uses
an immutable Ollama source commit, and retrieves the base Whisper model from a
fixed revision with a verified content hash. An existing mismatched model is
preserved and reported. `zstd`, required by the reviewed Ollama installer, was
added to its OS prerequisites. See the [source and limitation record](refinement_installer_provenance_260908.md).
This does not claim that every downstream OS or binary download is reproducible.
The development installation path was exercised with fake executables in a copied
temporary workspace, confirming separate environment selection without modifying
the hardware environment. Checksum success/failure fixtures also passed.

Combined phase 0B gate: **673 tests passed**, plus both driver checks, compilation,
Ruff lint/format, Mypy and whitespace checks. No real installer ran. The baseline
Starlette warning remains. Phase 0C (F07/F08) and phases 1–5 remain.
The seven deferred refinements remain excluded. Wiki publication and current-manual
link changes remain deferred to the end by the owner's explicit instruction.

## Phase 0C — external tools validated; one managed-driver approval pending

F07 now treats MCP `isError: true` as a failed execution, rejects malformed error
flags and validates supplied structured results. Results remain explicitly untrusted.
Retry evidence stays unknown unless local configuration explicitly lists a tool in
`retry_safe_tools`. Custom allowlisted tools additionally require `read_only_tools`
before being exposed; old configuration still loads, but unreviewed tools are
listed in inspection results and withheld from execution. The existing official
Tavily search preset retains read access. Neither remote annotations nor tool
descriptions grant permission. This intentionally removes the audited assumption
that any allowlisted external tool is read-only and safe to retry.

Subprocesses receive the SDK's minimal default environment plus only explicitly
mapped secret variables. Discovery has page, tool-count, total-size and time limits,
rejects repeated pagination cursors and duplicate tool names, and refuses schemas
that reference remote documents. Refresh replaces schemas and updates the CLI's
registry cache; a failed refresh retires the provider's stale tools. Calls validate
the current arguments, reject cancellation before dispatch and enforce deadlines.
Uncertain failures and timeouts do not claim that nothing happened remotely.
The current SDK still controls transport/process termination; no claim is made that
Python can forcibly terminate arbitrary in-process code that ignores cancellation.
Protocol reference: [MCP tool errors and schemas](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).

F07's full gate passed **689 tests**. F08's independent changes add root pytest
options `--run-hardware` and `--run-provider-live`; marked tests skip by default,
even when selected with `-m`. Synthetic subprocess tests verify both flags without
opening devices or calling a provider. Test modules must still be safe to import;
the execution gate cannot undo side effects in module-level collection code.

The IDE now retains active face-worker ownership through repeated cancellation,
secures its output tree on failure and waits for it during close. Registry startup
rolls back the adapter whose startup failed and continues cleanup when another close
fails. Integrated client close attempts voice, identity, engine and robot cleanup
before reporting the first error. Fake tests verify these failure paths.

Combined gate using the **default `pytest -q` command: 697 tests passed**, plus
Ruff lint/format, Mypy, compilation, driver-source/integrity and whitespace checks.
No marked live test was enabled in the actual project suite. The synthetic opt-in
fixtures only assert booleans. No physical camera or microphone capture occurred.

### Managed face-backend cleanup: exact patch awaiting owner approval

The managed driver constructs its recognition backend without exposing that object
to the IDE wrapper. Its missing final cleanup cannot be corrected by closing the
IDE wrapper alone. [The prepared patch](refinement_f08_face_cleanup.patch) wraps the
existing driver operation in `try/finally`, calls backend close when available and
adds four fake-backend regression cases. It was applied only in a temporary copy
of tracked pi5camera files: **27 existing driver tests plus four new tests passed**.
The proposed driver file passed lint; formatting was corrected in the temporary
copy and the suite rerun. No managed checkout file or authorization hash changed.

An asynchronous approval question was sent for this exact patch because the root
AGENTS.md managed-driver policy requires separate authorization. **Do not apply or
record its authorized hash until the owner replies approving it.** Continue other
approved work meanwhile. After approval, apply the patch, run the driver's tests in
a separate process, record the precise authorized managed-file hash with the actual
approval date and rerun root gates. This is separate from the deferred wiki approval.

Queue the MCP tutorial/configuration migration guidance, test commands, lifecycle
notes and manual validation for final wiki consolidation. F08's managed cleanup
remains pending. The sections below record subsequent progress.

## Resumed scope: pause after phase 2

The owner requested implementation through phase 2, then a pause with a
walkthrough and step-by-step manual tests. Do not implement phases 3–5 yet.
Wiki semantic diffs and manual-link updates remain deferred until the whole
refinement is finished. Existing unrelated edits and registered sources remain
preserved. No service, hardware, capture, power, deployment or Git push was run.

## Phase 1 software progress

- H01: request-correlated lifecycle records go to system logs only. Random request
  references and hashed session references connect voice capture and conversation.
  A fixed vocabulary excludes prompts, transcripts, results, credentials and raw
  exceptions. Existing display and web presentation remain unchanged by H01.
- F09: additive per-capability health reaches Agent status through the IDE provider.
  It includes dependencies, recovery guidance, a timestamp and five-second advisory
  freshness. Probe errors and two-second timeouts do not hide healthy peers.
  Cancellation propagates. Disabled devices and system/motion restrictions are
  explained separately; old aggregate status and component fields remain available.
  These checks describe software state, not physical readiness or action permission.
- H04: fixed conversation guidance asks a short, specific question about ambiguous
  consequential requests, requires exact time-zone/target review and distinguishes
  saved, queued and verified results. Deterministic time review is part of phase 2;
  prompt guidance alone is not an authorization mechanism.
- H07: interactive menu option 15 and the web menu share selectable guided checks.
  They use the running service's configuration and F05 diagnostics. Opening,
  skipping or returning to steps does not call a model, capture, move, deploy or
  change settings. Reminder practice remains pending phase 2. Guide body text is
  English; navigation labels are provided in all four existing interface languages.
- H06: browser zoom is enabled, keyboard focus is visible, diagnostic text wraps,
  and focused direction buttons support holding Space/Enter. Release, focus loss
  and page hiding stop the request. A delayed earlier failure cannot clear a later
  movement's state. Existing voice transcripts remain visible captions; no speaker
  output was added. Real browser, screen reader and Pi checks remain outstanding.

Validation: **712 tests passed**, Ruff lint and format (393 files), Mypy (83 source
files), compilation, immutable-driver and workspace-source checks, JavaScript
syntax and whitespace checks passed. The fake browser test runs actual movement
handlers with Node and checks hold/release, repeat suppression, focus/page loss
and stale failure. The full suite has the existing Starlette/httpx warning.
One old test expected browser zoom to be disabled; its expectation was updated
for the approved accessibility change. No live test flags were enabled.

The [font repair proposal](refinement_h06_font_proposal_260908.md) records a fixed
official source, fingerprints, license and representative rendering validation.
It is staged outside the checkout and awaits separate managed-file approval.
The [F08 patch](refinement_f08_face_cleanup.patch) also still awaits its existing
approval question. Neither managed repair is applied; neither phase is claimed
fully closed while those items remain pending.

## Phase 2 foundation checkpoint

The additive fourth database migration creates local task records in the existing
Agent database. They include trusted owner scope, source session, reviewed
notification effect, due time, steps, approval, occurrence and result evidence.
Profile deletion removes its tasks; memory reset removes all task records.
The initial local reminder worker claims through a database transaction before
delivery, requires confirmation of a fresh preview, and does not replay running
records recovered after restart. More than 60 seconds late means missed and
requires review. Snooze creates a new preview. Daily/weekly repeats preserve the
reviewed wall-clock time; a nonexistent clock-change occurrence pauses for review.

Foundation gate: **721 tests passed**, Ruff lint/format (396 files), Mypy (85
source files), compilation, driver integrity/source and whitespace checks passed.
Nine new tests cover confirmation, duplicate claims, scopes, restart uncertainty,
missed delivery, cancellation during delivery, snooze, repeat, expired previews,
offset mismatch and clock changes. Two migration tests were updated to expect
the new fourth migration; their existing backfill and rollback checks still pass.

Runtime/chat/tool integration is now in progress after that foundation gate.
It has not yet passed its full gate and is not a completed phase 2 handoff.
Remaining work includes integration tests, task progress/controls, general task
outcomes and recovery bounds, M01/M02 memory refinements, and the requested
walkthrough/manual tests. Keep phases 3–5 paused.
