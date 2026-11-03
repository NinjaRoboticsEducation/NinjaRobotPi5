# Fusion prepared-source verification repair

The reported failure is in source verification, before compilation or any
privileged system-file change. `--source /tmp/ninjarobot-fusion-source` did not
contain the required `driver/sunfounder-fusionhat-overlay.dts` at verification time.
That file is a pinned build input in `vendor/fusion-hat/manifest.json`.

## Root cause and investigation

`install` consumes source produced by `prepare`; it deliberately does not download
or repair inputs. The supplied command also omitted `--apply`, so it was a
preview. The printed prerequisites and proposed file list were not proof of a
successful installation. Previous code printed that preview before source
verification, which made the failure confusing.

The code called `read_bytes()` on each expected input without translating missing
files into an actionable setup error. Both `install` and `prepare` on an existing
incomplete directory therefore produced raw tracebacks. Preparation is staged and
verified before publishing its destination; it does not knowingly publish a
partial source directory. The traceback cannot establish whether preparation was
skipped, another source directory was used, files were removed or temporary storage
was cleared. `/tmp` storage is unsuitable for retaining source across maintenance
reboots. In this checkout the reported directory was absent during inspection;
that observation alone does not establish its earlier state on the user's robot.

Project wiki search was attempted but its environment is unavailable. Current raw
manuals, registered source pointers, manifest, installer and tests were read;
Serena located the verification function. The raw successors are unreviewed and
the registered map still describes an older checkpoint. Current code was treated
as authoritative for this failure. No new hardware specification or API dependency
is needed for this local filesystem repair.

## Implemented fixes

1. Classify missing source roots, missing files, unreadable files, changed hashes,
   linked paths and special files before building. Reject a named pipe without
   trying to read it. The same verifier checks prepared and root-staged build inputs.
2. Give actionable preparation instructions. Existing directories and operator
   files are preserved; use a fresh path if an existing directory is incomplete.
3. Print a verified preview only after all source inputs pass. Successful previews
   explicitly report `action: preview`, `source_verified: true`, and no installation.
4. Convert expected filesystem, download, verification, build and setup failures
   into a nonzero command exit and a concise diagnostic without a Python traceback.
5. Reject `--apply` on check/prepare so it cannot silently imply installation.
6. Recommend durable source storage in a new raw manual version and clarify the
   separate preparation, preview, privileged application and reboot steps.

Affected code: `scripts/fusion_hat_setup.py` and
`tests/test_fusion_installation.py`. No managed pi5 drivers, immutable ledger,
source pins, patches, runtime contracts, hardware safety policy or dependencies
changed. Installation still refuses loaded drivers, unresolved conflicting audio
overlays and existing transactions. It never silently downloads during install,
loads a module or reboots. Third-party notices and the MCP manual need no change.

## Recovery instructions

From the repository root, run as your normal user. These commands prepare local
files and preview; they do not operate hardware or change boot/service files:

```bash
uv run --frozen python scripts/fusion_hat_setup.py prepare --source "$HOME/.cache/ninjarobot/fusion-source-recovered"
uv run --frozen python scripts/fusion_hat_setup.py install --source "$HOME/.cache/ninjarobot/fusion-source-recovered"
```

Expected: verified patched source, then a clearly labeled preview. If this chosen
path already exists but is incomplete or changed, keep it and choose another
unused name in both commands. Rerunning prepare on valid source is offline and
idempotent. Do not create an empty overlay file, alter hashes, or reuse unreviewed
source to make verification pass.

After reviewing the preview and meeting the full guide's maintenance conditions,
stop the Agent and standalone tools and disconnect actuator power. Explicit
administrator installation is:

```bash
sudo .venv/bin/python scripts/fusion_hat_setup.py install --source "$HOME/.cache/ninjarobot/fusion-source-recovered" --apply
```

This changes module/boot configuration, unlike preview. It does not reboot.
Reboot manually when safe, then check as the normal robot user:

```bash
uv run --frozen python scripts/fusion_hat_setup.py check
```

Expected after successful binding: version `1.1.0-ninja1` and ready device
prerequisites. Preparation or preview alone will not make this check ready.
For headers, loaded-driver replacement, conflicting overlays, existing installation
records and rollback, follow the
[full installation guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-03-03/InstallationGuide.md#explicit-operating-system-installation).
Do not bypass a refusal by deleting installation records or forcing controller access.

## Validation and manual acceptance

Safe smoke tests: run the installer against a nonexistent source path. Expected:
nonzero exit with `Run prepare --source` guidance and no traceback; no live files
change. Prepare a new source path and preview it twice: expected successful hash
verification and no second download or privileged changes. The focused tests use
fake downloaded archives, absent inputs, linked paths and a FIFO (a named pipe).

Device communication: after separate manual installation/reboot, run `check`
without operating servos. Hardware readiness remains unverified by this repair.

Actuator-moving tests: none added or run. Keep the existing raised-wheel and
operator-supervised per-channel calibration acceptance procedure after prerequisites
pass. This repair does not require servo movement to validate source handling.

Power-risk tests: none run; reboot/shutdown remain supervised maintenance actions.
Rollback: preview needs none; source preparation can use a fresh path without
altering existing data. Live installation rollback must use its recorded transaction
under the guide's stopped/unloaded maintenance conditions, preserving later edits.

Documentation: new complete raw sources under `2026-11-03-03` preserve prior manual
versions. Both READMEs link to the new sources. The registered map, semantic pages
and implementation fingerprints remain for the owner's ingestion/review workflow.
No ingestion or semantic review was run. Exact gate results follow below.

### Final validation results

- Root pytest: PASS, 1,132 tests in 51.52 seconds; existing Starlette warning.
- Focused installer tests: PASS, 11 tests.
- Separate managed suites: servo 147, buzzer 68, camera 27, display 65,
  microphone 92, distance 71 tests passed; existing audioop warning.
- Compileall, Ruff lint/format (474 files), Mypy (122 files): PASS.
- Immutable verifier: PASS, 225 tracked files, unchanged 66 authorized repairs.
- Workspace source verifier: PASS, six checkout libraries.
- Actual pinned download/patch/hash verification: PASS in a fresh scratch path.
  Second preparation reports verified/unchanged, and install preview verifies
  inputs and explicitly says no driver was installed.
- New report/manual links and `git diff --check`: PASS.
- Wiki check/lint: unavailable because the separate wiki environment is missing;
  no dependency setup, ingestion, semantic review or fingerprint refresh was run.
- Live installation, kernel module loading, actuator, recording and power tests:
  NOT RUN. Source scratch preparation and preview changed no live system files.

The next safe action is to prepare the durable source path and review its preview;
privileged installation and manual reboot remain explicit operator steps.
