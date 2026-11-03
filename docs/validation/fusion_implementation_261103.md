# Fusion HAT+ implementation and manual acceptance

The approved Fusion-only implementation and vendor safety patch are present in
this checkout. Software validation passes as recorded below. Installation and
physical acceptance are **not complete**: read-only preflight on this host finds
no installed Fusion driver/card. No module was loaded, live boot/service files
changed, microphone/camera recorded, servo moved, or shutdown executed during this
work. Do not interpret this report as hardware certification.

Date: 3 November 2026. Baseline: `c53ff21`, branch `sunfounder_v01`.
The original unrelated state was preserved; no commit or push was performed.

## Scope and approval

The owner approved the [Fusion plan](../project-history/NinjaFusionHATImplementationPlan_261103.md),
scoped pi5servo changes, and then the additional kernel-driver repair described
by the [Phase 0 report](fusion_phase0_contract_261103.md). Older Robot HAT variants
are no longer offered. DFR0566/X1208 and PCA9685 public commands and existing
hardware paths remain. All other managed pi5 libraries and the immutable baseline
are unchanged. GPIO means the Pi's general-purpose electrical pins; PWM means
pulse-width modulation, the timed servo signal.

## Seven-issue acceptance table

| Issue | Implemented behavior and principal files | Software evidence | Physical status |
| --- | --- | --- | --- |
| PWM1–11 inaccessible | Explicit `fusion_hat_plus` kernel backend, twelve ports, shared 50 Hz, exclusive session lock; factory, config manager and servo CLI | All twelve independent duty files; invalid ports; competing session; cleanup failure; no startup centering | Pending every port, timer boundaries and signal measurement |
| Calibration rejected | Atomic validated save, named bad endpoint/range; one populated Fusion servo allowed; explicit profile migration and backup | Invalid PWM1 `1500/1500/2200` rejected without replacing good file; config persistence and profile-switch tests | Pending onboarding through next step |
| Embedded audio onboarding absent | Explicit Fusion profile; embedded input/output defaults with independent USB/Bluetooth choices; IDE `fusion.py`, hardware setup, wizard | Missing card never saves fabricated sink; input enumeration never captures; no GPIO fallback | Pending actual card, permissions, microphone and tone |
| Welcome/interaction face stuck | IDE idle allowed under motion-only latch; full system stop preserved; speech completion checks current expression generation | Motion/system distinction plus existing greeting, idle, speech and stop lifecycle suites | Pending display in web and chat |
| AI motion blocked by power | Pi warning stays distinct; fresh kernel microvolt telemetry required before motion/recovery and during motion; `safety.py`, `robot.py` | Missing/low/non-finite data blocks; healthy sample does not clear latch; pinned C freshness/error/recovery checks | Pending meter comparison, healthy-load test and actual Pi-warning diagnosis |
| Speech unavailable | Actual stable output identity, matched health/playback route, kernel amplifier lifecycle, cancellation joins enable before disable; IDE audio modules | Audio/speech suites and cancellation ordering; missing output fails explicitly | Pending TTS assets, audible response, interruption and service audio session |
| Power-off disabled | Readiness refresh, fixed privileged helper checks, paired/control-gated UI; Fusion requires orderly OS shutdown but not EEPROM full-power-cut mode | Helper validation, command construction, UI/deployment tests; narrow Fusion service write exceptions | Pending explicit deployment enablement and one supervised shutdown |

These changes address verified software causes. They do not establish that the
owner's previous Pi undervoltage was false, that the battery is suitable under
load, or that a missing TTS engine is repaired merely by selecting a speaker.
No unsafe threshold reduction or AI-permission bypass was introduced.

## Phases and validation checkpoints

| Phase | Outcome | Gate/evidence |
| --- | --- | --- |
| 0: baseline and contract | Pinned upstream had unsafe disable/cache behavior; paused for owner approval, then repaired | Baseline 1,104 root tests; original C reproducer and patched C contract checks |
| 1: identity and persistence | Explicit profile, backup/atomic preset, valid populated endpoints, clear calibration failures | Checkpoint 1,106 root tests; focused setup tests |
| 2–3: installation, PWM and power | Pinned source helper, root-only explicit apply, rollback, kernel backend and telemetry checks | Checkpoint 1,109 root tests; standalone servo suite; kernel build and mocked C contracts |
| 4: embedded audio | Detected devices, optional external selection, safe amplifier lifecycle | Checkpoint 1,112 root tests; focused audio/setup tests |
| 5–6: faces and shutdown | Silent idle versus movement stop, expression ordering, orderly Fusion shutdown and service access | Focused lifecycle/shutdown/deployment suites, followed by combined full gate |
| 7: final regression and documentation | New raw manuals, notices, acceptance/rollback guide | Final gates below; physical and wiki workflow gates pending |

The interrupted work was resumed by checking the dirty tree and prior evidence.
The full regression caught missing TOML serialization of the new profile and
required-telemetry flag, and an overbroad explicit-stop idle restart. Both were
repaired; save/reload is now tested and explicit-stop presentation preserved.
Cold recovery starts the Fusion servo session at zero output before reading its
battery, so a persisted latch can be checked before the first movement.
The last two phases used focused tests and a combined complete gate; do not read
this table as a claim that a separate full gate ran after every individual edit.

### Final software gate

Commands run from the repository root:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python scripts/verify_workspace_driver_sources.py
uv run --frozen python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
git diff --check
```

| Gate | Result |
| --- | --- |
| Immutable verifier | PASS: 225 tracked files, six drivers, baseline plus 65 authorized repairs |
| Workspace sources | PASS: all six libraries execute from this checkout |
| Compileall, Ruff lint/format | PASS |
| Mypy | PASS: 122 source files |
| Root pytest | PASS: 1,120 tests in 54.75 seconds; one existing warning |
| pi5servo | PASS: 145 tests, separate process |
| pi5buzzer | PASS: 68 tests, separate process |
| pi5camera | PASS: 27 tests, separate process |
| pi5disp | PASS: 65 tests, separate process |
| pi5mic | PASS: 92 tests, separate process |
| pi5vl53l0x | PASS: 71 tests, separate process |
| Driver archive/source verification and installer preview | PASS; no privileged apply |
| Patched C contract reproducer | PASS: battery validity/expiry/recovery, all twelve PWM stop errors and zero re-enable |
| Kernel module | Builds against `6.12.109+rpt-rpi-2712`; not loaded |
| Audio device-tree overlay | `dtc` compilation succeeds; not installed |
| Wiki check and lint | BLOCKED: wiki environment missing; no setup/install performed |

Existing warnings: Starlette TestClient/httpx deprecation in root tests and
Python `audioop` deprecation in the microphone suite. The vendor Makefile emits
`grep: main.h: No such file or directory` while evaluated by Kbuild; direct module
compilation still succeeds, and the runtime version comes from the included
header. No vendor install target is invoked.

Build/check reproduction (scratch files only):

```bash
uv run --frozen python scripts/fusion_hat_setup.py prepare --source /tmp/ninjarobot-fusion-source
uv run --frozen python scripts/fusion_hat_setup.py install --source /tmp/ninjarobot-fusion-source
uv run --frozen python scripts/reproduce_fusion_vendor_contract.py /tmp/ninjarobot-fusion-source --patched
make -C /lib/modules/$(uname -r)/build M=/tmp/ninjarobot-fusion-source/driver modules
dtc -@ -I dts -O dtb -o /tmp/ninjarobot-fusion-source/hat.dtbo /tmp/ninjarobot-fusion-source/driver/sunfounder-fusionhat-overlay.dts
```

## Installation, provenance and remaining limits

The pin is SunFounder commit `4bd1018ad5a70ee113160536f969cdadd9f22918`, archive
SHA-256 `37ea53b9b72b6431a4a2ee8b752804ad74f0f10071c416f856991814347d9c2d`.
See [manifest](../../vendor/fusion-hat/manifest.json),
[patch notes](../../vendor/fusion-hat/README.md) and
[license](../../vendor/fusion-hat/COPYING). The derived kernel patch is GPL-3.0.
The battery worker's integer calculation turns raw count 3100 into 7,494,000
microvolts, approximately 7.494 V. The application divides once by one million.
The standard power-supply file is a converted value, not an ADC count.

Kernel errors invalidate battery data; cache also expires after three worker
periods. Required-reading failure currently stops and latches immediately. This
conservative behavior differs from the plan's preferred tolerance for an isolated
poll error. Measured polling behavior is still needed before adding any grace
period; the implementation does not weaken protection to hide intermittent faults.
Shared servo timers remain fixed at 50 Hz. Arbitrary third-party programs can
ignore the advisory lock: do not operate another controller stack concurrently.
A failed bus write cannot guarantee physical zero output; remove actuator power
if cleanup reports uncertainty.

The installer stores a recoverable transaction before live writes and rollback
checks for later edits and backup corruption. Partial-transaction rollback is
covered with temporary paths. It builds only the running kernel and does not
provide automatic DKMS rebuilding. Missing headers, conflicting sound overlays,
already loaded drivers and existing transactions require operator maintenance.
Installed root files, group membership, udev timing, service namespace paths,
module precedence and real battery/audio devices still require Pi acceptance.
No claim is made that arbitrary operating systems or future kernels are supported.

## Manual Raspberry Pi acceptance

Follow the full
[installation guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-03/InstallationGuide.md#fusion-installation-and-onboarding)
first. `ninjarobot-agent` is the main end-to-end test entry, but cannot replace
kernel installation, electrical checks or per-port calibration. Keep real tests
separate from automated suites. Use only sanitized results when reporting errors;
do not share tokens, private configurations, captured media or conversation stores.

### Safe smoke tests — no device operation

1. Run `uv run --frozen python scripts/fusion_hat_setup.py check` as the normal
   service user. Expected after manual installation/reboot: reviewed version,
   twelve interfaces, writable PWM/speaker/lock, detected sound card and readable
   battery. Before installation, `ready: false` is expected and is not repaired
   by running onboarding repeatedly.
2. Run `uv run --frozen python scripts/verify_workspace_driver_sources.py`.
   Expected: six checkout source paths. Confirm the generated service uses the
   same environment after deployment upgrade.
3. Review the install preview and configuration backups. No preview may modify
   `/boot`, services or audio defaults. Rollback: none needed for read-only checks.
4. Select local and cloud Ollama entries and inspect the saved route through the
   existing model menu. Expected: existing selections and ngrok pairing behavior
   remain. No new key, download or remote exposure is needed for this check.

### Device communication and audio — no servo movement

1. Keep servo power disconnected. Complete explicit kernel installation and
   manual reboot using the guide; inspect preflight again. Do not enable both
   kernel and raw-controller access. Failure: stop here and use installer rollback.
2. Select Fusion in onboarding and confirm embedded speaker/input choices appear.
   Explicitly approve the speaker tone. Expected: sound from embedded speaker,
   not Bluetooth. Select USB/Bluetooth separately and rerun setup: selections
   persist. Missing cards should report a prerequisite failure, not success.
3. With everyone's consent, use the microphone test and wake input. Avoid saving
   recordings. Expected: selected input receives speech and existing speech-to-text
   assets initialize. Enumeration alone must not start a recording.
4. Start Agent, pair web controller and observe greeting → idle → thinking →
   speaking → idle. Run `/speech status`, `/speech outputs`, `/speech on`; request
   a short response. Interrupt speech and observe amplifier cleanup and idle
   recovery. Stop or disconnect an output: text remains available and output
   failure is explicit. Restore the same device, not an arbitrary replacement.
5. Read battery voltage and compare to an independent meter while stationary.
   Read `vcgencmd get_throttled` separately: bit 0 is current undervoltage, bit 16
   records a historical event. A historical bit is not permission to dismiss
   an active warning. Do not deliberately brown out the Pi.

Rollback: stop the Agent, restore the previous selected input/output through
setup, and restore compatible backed-up settings if a profile migration fails.
A full system stop should retain its stop display; a movement-only stop should
not freeze ordinary silent expressions.

### Actuator-moving tests — operator present, wheels raised

Use one known compatible servo first, with safe electrical power and linkage
clearance. Be ready to disconnect actuator power. Do not test bare DC motors.

1. Stop the Agent. Open `pi5servo servo-tool`; select and calibrate a populated
   Fusion port. Opening the tool alone should not center it. Explicit calibration
   commands move it. Save safe min/center/max values and exit cleanly.
2. Repeat each physical port below, especially 3/4 and 7/8. Observe that selecting
   one channel does not move a neighboring servo. Record independent signal and
   mechanical results; a PWM0 pass does not qualify the other eleven ports.
3. Rerun onboarding; valid one-port settings should proceed, while an invalid
   range should identify its endpoint and preserve the last good file.
4. Start Agent only after standalone exit. Enable AI motion separately; request
   a safe calibrated action on each configured endpoint. Unconfigured endpoints
   must remain inaccessible. Do not assume a continuous-rotation servo interprets
   90 degrees as a physical position.
5. Check stop/cancel and healthy explicit `/resume`. A persisted latch must survive
   restart, and recovery must not replay old movement or grant AI authorization.
6. With no active motion, attempt a second servo session: it must report ownership
   contention. Do not force-unlock or bypass the kernel driver.

| Port | Standalone calibrated movement | Agent action | Independent neighbor / stop | Result |
| --- | --- | --- | --- | --- |
| PWM0 | Pending | Pending | Pending | Unqualified |
| PWM1 | Pending | Pending | Pending | Unqualified |
| PWM2 | Pending | Pending | Pending | Unqualified |
| PWM3 | Pending | Pending | Pending | Unqualified |
| PWM4 | Pending | Pending | Pending | Unqualified |
| PWM5 | Pending | Pending | Pending | Unqualified |
| PWM6 | Pending | Pending | Pending | Unqualified |
| PWM7 | Pending | Pending | Pending | Unqualified |
| PWM8 | Pending | Pending | Pending | Unqualified |
| PWM9 | Pending | Pending | Pending | Unqualified |
| PWM10 | Pending | Pending | Pending | Unqualified |
| PWM11 | Pending | Pending | Pending | Unqualified |

Rollback: stop motion, remove actuator power if stopping is uncertain, exit both
tools and restore matching configuration/backend versions. Never swap back to a
raw controller while the Fusion kernel module is bound.

### Power-risk test — separate supervised session

1. Save work; disconnect or safely park actuators. Enable power-off through
   deployment setup, install/verify the fixed helper and update the service unit.
2. Pair the browser and acquire control. Expected: Power off becomes available
   only when deployment and helper readiness pass. A missing prerequisite should
   explain why it is disabled. Fusion must not require an EEPROM battery-cut mode.
3. Explicitly request one web shutdown. Expected: services clean up and the OS
   halts normally. Do not treat remaining HAT power as failed OS shutdown.
4. Restart manually and confirm service/configuration/calibration persist.

Rollback: if readiness is wrong, disable power-off in deployment settings and
repair the helper. Do not experiment with raw power commands. Once shutdown is
accepted there is no software undo; restart manually after halt.

### Cross-profile regression checklist

Repeat the existing baseline routines on DFR0566/X1208 and PCA9685: setup and saved
calibration, role-based movement/stop/recovery, buzzer/display, distance safety,
camera privacy, USB microphone, Bluetooth speech, behaviors, web pairing/ngrok,
local/cloud models and fixed-helper shutdown. Physical results are pending for
both profiles. Pure software compatibility passing is not a wiring certification.

## Documentation and wiki impact

New complete source successors, preserving the registered originals:

- [InstallationGuide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-03/InstallationGuide.md)
- [DevelopmentGuide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-03/DevelopmentGuide.md)
- [DevelopmentLog](../../ninjarobot_pi5_wiki/raw/notes/ninjarobotpi5/2026-11-03/DevelopmentLog.md)

Both READMEs link to the successors with an unregistered/unreviewed label. Third
party notices cover the kernel patch. No MCP tool contract changed, so the MCP
skills manual is unchanged. No ingestion, plan apply, semantic review or fingerprint
refresh was run. Wiki check/lint report a missing environment; the direct knowledge
verifier additionally reports expected implementation drift and the new IDE
`fusion.py` needing classification. The owner must reconcile these during the
requested ingestion/review workflow, including affected architecture, installation,
features/tools, workflow and knowledge-limitations pages.

## Final checkpoint

The final complete root suite passed **1,120 tests in 54.75 seconds**. The final
lint, format (474 files), type check (122 files), compileall and immutable gates
passed. The additional governance/knowledge/installer selection passed 21 tests.
All links in the new validation report and three raw manual successors resolve.
Prepared source verification is idempotent; `modinfo` reports compiled module
version `1.1.0-ninja1`. No unauthorized driver, immutable-baseline or registered
2 November manual changes are present. The direct knowledge verifier reports
only expected changed implementation fingerprints and new-file classification;
these are deliberately left for the owner's ingestion/review workflow.

Next safe action: read the installation preview and manual prerequisite guide,
then schedule Fusion driver installation with actuator power disconnected. Do not
start real Agent movement until the per-device checks and calibration pass.
