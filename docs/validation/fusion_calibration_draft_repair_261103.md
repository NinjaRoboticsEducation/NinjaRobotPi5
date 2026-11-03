# Fusion servo calibration draft repair

Fusion calibration now supports setting Max, Center and Min in any order from
the safe `1500/1500/1500` initial values. Enter/Space stages a point in memory;
F validates and saves the complete calibration once; Q discards the draft.

## Cause and scope

`CalibApp.set_calibration()` wrote the entire configuration after every confirmed
point. After setting Max first, Min and Center were still both 1500. The strict
Fusion writer correctly rejected that incomplete range, but the exception escaped
the calibration loop. The workflow incorrectly treated an intermediate draft as
a completed calibration. The old Center confirmation also required the other
limits to be valid, preventing arbitrary point order.

The repair changes only the managed `pi5servo/cli/calib.py` calibration UI and adds
independent draft tests. It uses the existing explicit Fusion backend identity
(or the active Fusion backend for CLI overrides). Non-Fusion point-saving behavior
is preserved. No hardware backend, kernel driver, pulse bounds, file schema,
safety thresholds, IDE/Agent commands or dependency changed. The original immutable
baseline is preserved and final managed hashes are independently tested and recorded.

Project knowledge, current raw manuals and configuration writer were checked;
Serena located the failing calibration method. Wiki search was attempted but the
wiki environment is missing. Registered source pointers describe an older
checkpoint, while recent raw manuals remain unreviewed. This repair follows the
owner's explicit request for temporary calibration values and one final save.

## Implementation

- Enter/Space updates only local draft fields, accepting intermediate equality or
  unordered points within the unchanged 500–2500 microsecond hardware bounds.
- Selecting another point retrieves its staged value and performs the existing
  explicit calibration pulse movement. Staging itself adds no movement or file write.
- F requires `500 <= Min < Center < Max <= 2500`, then writes once through the
  existing validated atomic writer. Success exits calibration.
- Invalid final values keep the session open and print corrective guidance.
- A failed write restores the configuration manager's previous entry (or removes
  a new unsaved entry), retaining the draft in the UI for retry. The prior file
  remains protected by the existing atomic writer. Existing angle metadata is retained.
- Q or interruption never commits the draft; ordinary cleanup disables output.
- Fusion prompts/help describe stage, finish and discard. Other backends retain
  their existing confirmation behavior.

Final save still validates other saved Fusion endpoints. If it reports a different
invalid endpoint, that data needs repair; this change does not weaken validation
or silently replace unrelated calibrations. Drafts are not crash-recovery files.

## Validation strategy and results

Standalone tests exercise all six point orders beginning at the neutral defaults,
Enter and Space bindings, one final write, failed final validation followed by
correction, cancellation, false/exception save failures and retry, a new unsaved
endpoint, retained metadata/unrelated entries, and the original point-save path.
Tests use temporary files and fake servos; they never open real devices.
Exact gate results are recorded below after completion.

## Manual Raspberry Pi validation

### Safe smoke checks

Run `uv run --frozen pytest -q pi5servo/tests/test_calibration_draft.py` from the
repository root. Expected: software tests pass without hardware movement or live
configuration changes. Verify the updated Fusion help explains Enter/Space, F and Q.
Do not open real calibration as a non-moving smoke test: its center pulse moves
hardware under the existing calibration contract.

### Device communication

Use the existing read-only Fusion prerequisite check before opening calibration:

```bash
uv run --frozen python scripts/fusion_hat_setup.py check
```

Expected: installed reviewed driver and required device permissions. This repair
does not install/reload a driver or alter kernel state. Stop the Agent before
opening standalone calibration to avoid controller ownership conflicts.

### Actuator-moving acceptance

Raise wheels/unload mechanisms, use a known compatible servo, and keep an operator
ready to disconnect actuator power. Back up `servo.json` before the test.

1. Open onboard step 4 → Calibrate → `hat_pwm0` (or another populated port).
2. Press X, adjust Max safely, and press Enter. Expected: “Staged”, no exception,
   calibration remains open, and the saved file has not changed.
3. Press V, adjust Min, then Space. Press C, verify/adjust Center, then Enter.
   Expected: each staged value survives revisiting its target.
4. Press F. Expected: complete valid range saves once and exits. Onboarding then
   validates the saved calibration and can proceed.
5. In a separate session change a point and press Q. Expected: saved file unchanged.
6. If final values are incomplete or unordered, F should keep the tool open with
   guidance. Correct them and retry. Do not deliberately cause disk or device
   failures during live movement; automated tests cover failure injection.
7. Repeat on other populated ports as needed. DFR0566/PCA9685 should retain the
   existing Enter/Space confirmation workflow.

### Power risks and rollback

No power-risk test is required; no installation, reboot or shutdown was run.
Q discards in-memory drafts; output cleanup remains active. If persistence or
hardware acceptance fails, stop the tool/Agent, remove actuator power if needed,
and restore compatible backed-up settings and repository code. Do not lower
validation requirements or invent mechanical limits to silence an error.

## Documentation impact

New full InstallationGuide, DevelopmentGuide and DevelopmentLog successors live
under raw version `2026-11-03-04`; old versions are preserved. Both READMEs link
to the successors. The MCP manual and third-party notices need no update because
public tool contracts and dependencies are unchanged. Wiki ingestion, semantic
review and fingerprint refresh remain with the owner; none was run here.

## Final validation results

- Managed pi5servo suite: PASS, 159 tests, including all six draft entry orders,
  final-save/cancel/retry behavior and original backend point saves.
- Complete project suite: PASS, 1,132 tests in 52.15 seconds; existing Starlette warning.
- Other managed suites, separate processes: buzzer 68, camera 27, display 65,
  microphone 92, distance 71 passed. Existing microphone audioop warning remains.
- Ruff lint/format (475 files), compileall, Mypy (122 source files): PASS.
- Immutable verifier: PASS, 226 tracked files and 67 authorized repairs. The
  original baseline and all unrelated managed libraries are unchanged.
- Workspace driver-source check: PASS for all six libraries.
- Documentation governance tests: PASS, 10 tests. New report/manual links and
  `git diff --check`: PASS.
- Wiki check/lint: unavailable because the wiki environment is missing. No
  ingestion, semantic review, environment setup or fingerprint refresh was run.
- Physical servo/actuator tests, recordings and power-risk actions: NOT RUN.

An interruption occurred after the core gate passed. The working tree and
immutable hashes were checked on resume; pending driver suites were rerun because
old process handles were unavailable. Their completed results are recorded above.
The next manual action is step 4 calibration: stage points with Enter/Space, then
F to save the complete valid range, or Q to discard. Keep wheels raised and an
operator present. No additional driver installation is required for this UI repair.
