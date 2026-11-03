# Fusion servo setup prerequisite failure and repair

The reported `FileNotFoundError` proves that the Fusion kernel `version` interface
was absent when calibration started. It occurs before PWM writes, and is not an
undervoltage or servo-calibration failure. The previous implementation allowed
onboarding to start the kernel-backed tool without checking OS prerequisites.
Selecting a HAT only persisted a preset; it did not install the driver.

## Evidence and root causes

The pinned [SunFounder driver source](https://github.com/sunfounder/fusion-hat/blob/4bd1018ad5a70ee113160536f969cdadd9f22918/driver/main.c)
creates `version` on its Fusion class device during successful device binding.
The path is correct. A missing file can mean missing installation, reboot pending,
a module built for a different kernel, a missing boot overlay, or failed device
binding. The supplied traceback cannot distinguish these causes. This checkout's
read-only inspection also found no Fusion sysfs interface or installation record;
a filtered current kernel journal returned no entries. No installation or module
loading was attempted. These observations do not prove the HAT itself is defective.

The diagnostic was obscured by three software issues:

1. `run_hardware_setup` launched calibration without checking prerequisites.
2. Onboarding caught failures generically or reported configuration validity after
   tool exit, which could point users toward recalibration instead of OS setup.
   Saved-setting reuse/resume also checked calibration alone.
3. The standalone tool printed a traceback for expected backend failures and
   could return success despite failure.

Additional safety finding: Fusion's standalone exit path attempted to center
all configured servos before disabling them. Opening and exiting a tool should
not cause that movement in the approved Fusion workflow. That exit centering is
removed for Fusion. Original/PCA behavior is retained.

The hexadecimal `+q...` prefix resembles terminal capability-query replies from
the interactive terminal layer. It precedes the exception but is not evidence
of a PWM command or the missing kernel interface's cause. Its exact terminal
source is unverified; no terminal package was changed based on that symptom.

## Changes

| Area | Repair |
| --- | --- |
| IDE `fusion.py` | Safe typed diagnostics distinguish missing interface, unreadable version, incompatible driver, missing PWM channel, permission failure and inaccessible lock; preflight is read-only |
| IDE `hardware_setup.py` | Check saved Fusion backend before launching calibration; expose prerequisite readiness separately from calibration validity |
| Agent `setup_wizard.py` | Display the safe diagnostic and stop at the failed step; reuse/resume cannot bypass prerequisite readiness |
| pi5servo backend | Missing files and permission errors have different corrective guidance; no raw-controller fallback |
| pi5servo CLI | Expected backend errors exit nonzero without traceback; Fusion cleanup disables/closes without centering |
| Installer check | Missing/unreadable version or sound-card files become diagnostic fields rather than crashes |

Scope follows the already approved Fusion preflight and narrowly scoped pi5servo
repair plan. No new dependencies, automatic privileged installation, or hardware
transport are introduced. The immutable baseline is preserved; independently
tested managed edits are recorded in the authorized-change ledger.

## Manual recovery

Run from `~/NinjaRobotPi5` as the normal robot user:

```bash
uv run --frozen python scripts/fusion_hat_setup.py check
uname -r
journalctl -k -b --no-pager --grep='fusion|sunfounder' -n 50
```

These are safe smoke checks: they do not move servos, capture media, load a module
or change boot files. Expect a missing/unready report until installation and
successful binding complete. Permission failures need group/rule repair; running
the whole onboarding tool as root is not the remedy.

If the reviewed driver has not been installed, prepare and preview it:

```bash
uv run --frozen python scripts/fusion_hat_setup.py prepare --source /tmp/ninjarobot-fusion-source
uv run --frozen python scripts/fusion_hat_setup.py install --source /tmp/ninjarobot-fusion-source
```

Expected: verified pinned source and a list of proposed system-file changes.
For explicit administrator installation, reboot, loaded-driver replacement,
conflicting overlays and rollback, follow the
[full installation guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-03-02/InstallationGuide.md#explicit-operating-system-installation).
Stop the Agent/standalone tools and disconnect actuator power before that
maintenance. Existing transactions or loaded drivers must be reviewed; do not
delete records, force bus access or unload an active controller to bypass refusal.

After safe manual installation and reboot, rerun `check`. Expected reviewed
version: `1.1.0-ninja1`, twelve PWM interfaces, usable shared lock, correct normal-user
permissions, sound card and battery telemetry. If the version file is still
missing, inspect the kernel journal and matching module/overlay installation;
recalibrating or repeatedly rebooting without diagnosing binding will not fix it.

Device communication test: with actuator power disconnected, rerun onboarding.
A missing prerequisite should show the corrective reason and preserve saved
calibration. With prerequisites ready, the servo tool should open successfully.

Actuator-moving test: separately raise wheels/unload mechanisms, keep an operator
ready to remove power, and explicitly calibrate one known safe populated port.
Exit without issuing movement: Fusion must disable output without moving to center.
Repeat other populated ports and verify saved settings still validate. Physical
results remain pending; mocks do not qualify electrical signals.

Power-risk tests: none added or run. Existing supervised shutdown acceptance remains
separate. Rollback: stop the Agent, disconnect actuator power, restore matching
repository/configuration backups; use the installer transaction rollback only in
the maintenance conditions documented in the guide.

## Validation and documentation

Focused tests cover missing/wrong driver, missing channel, denied permission,
no subprocess/ownership acquisition on failure, safe Agent diagnostics, nonzero
CLI error, no Fusion entry/exit centering, and unreadable installer-check files.
Results are appended below after the full gate.

New raw manual successors are under `2026-11-03-02`; previous sources are preserved.
Both READMEs link to them. The MCP manual and third-party notices need no change:
public tool contracts and dependencies are unchanged. Compiled wiki pages and
fingerprints remain pending the owner's ingestion/review workflow. Read-only
wiki queries/checks are attempted without installing the missing environment.

### Repair validation results

- Root suite: PASS, 1,126 tests in 54.05 seconds; existing Starlette warning.
- Separate driver suites: servo 147, buzzer 68, camera 27, display 65,
  microphone 92, distance 71 tests passed; existing microphone audioop warning.
- Ruff lint and format (474 files), compileall, Mypy (122 source files): PASS.
- Immutable verifier: PASS, 225 tracked files and 66 authorized repairs;
  workspace verifier: all six libraries execute from checkout. Baseline unchanged.
- `git diff --check` and new report/manual links: PASS.
- Read-only Fusion check: runs successfully and honestly reports missing interface,
  no installed version and `ready: false` on this host.
- Wiki check/lint: unavailable because wiki environment is missing. No setup,
  ingestion, semantic review or fingerprint refresh was performed.
- Physical device, motion and power-risk validation: NOT RUN. No installation,
  module loading, live service changes or live configuration writes were made.
