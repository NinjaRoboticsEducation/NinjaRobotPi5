# Fusion HAT+ Phase 0: baseline and vendor contract gate

Continuation: the owner subsequently approved the scoped vendor patch. The
[implementation report](fusion_implementation_261103.md) records the resumed work
and current validation. The gate below is preserved as the original finding.

Date: 3 November 2026. Baseline checkout: `c53ff21`.
Result: project baseline passes; the candidate vendor kernel driver fails the
approved safety contract. Dependent implementation is gated, not completed.
No runtime code, configuration, installed driver or hardware state was changed.

## Scope and approved boundary

Work follows the [approved Fusion plan](../project-history/NinjaFusionHATImplementationPlan_261103.md).
The plan requires one kernel owner, reliable cleanup and distinguishable stale
battery data. It explicitly says:

> If it cannot meet those contracts, stop the dependent phase and present a concrete revised design;
> do not silently adopt a second runtime or broaden driver changes.

The existing approval covers scoped pi5servo changes and a reviewed driver
installation route. The new proposal below would additionally maintain a patch
to the third-party Linux kernel driver; it is presented for explicit review.
No request to relax safety or support an older Robot HAT is made.

## Baseline validation

| Gate | Result |
| --- | --- |
| Immutable managed drivers | PASS: 223 tracked files, six drivers, existing 63 authorized repairs |
| Workspace driver sources | PASS: all six execute from this checkout |
| Python compileall, IDE/Agent/scripts/tests | PASS |
| Ruff lint | PASS |
| Ruff format | PASS: baseline 466 files |
| Mypy, IDE and Agent | PASS: 121 source files |
| Root pytest | PASS: 1,104 tests, 52.14 seconds |
| Existing warning | Starlette TestClient/httpx deprecation in `test_web.py`; no new failure |

After adding the reproducer, the full root suite passed again: 1,104 tests in
53.64 seconds with the same existing warning. Compilation, lint (467 formatted
files), type checking, both driver verifiers and `git diff --check` also passed.
The modified-source rejection test passed (exit 2), and local document links
resolved.

No managed driver changed, so their independent suites have not been rerun at
this evidence-only checkpoint. The new reproducer compiles its generated C
harness with `-Wall -Wextra -Werror -Wno-unused-parameter` and executes only
simulated I/O. Its result is described below. Initial harness formatting and
compiler-indentation errors were corrected before recording the final result.

Wiki search reported a missing environment. Direct registered documentation was
used without dependency installation or ingestion. The 2 November manuals and
newer owner-approved plan have different support scope; the owner-approved
Fusion-only plan governs implementation. No semantic review was performed.

## Pinned upstream source

Reviewed commit: `4bd1018ad5a70ee113160536f969cdadd9f22918`, from the official
[sunfounder/fusion-hat repository](https://github.com/sunfounder/fusion-hat/tree/4bd1018ad5a70ee113160536f969cdadd9f22918).
Repository license file is GNU GPL version 3. Preserve license/provenance and
review distribution obligations when packaging a patched build.

| File | SHA-256 of reviewed bytes |
| --- | --- |
| `driver/pwm.c` | `4ec8c3c67bdccee98abb80fdc10a80c6fee6af06506c60c6b8a68e2739d7891b` |
| `driver/battery.c` | `4c17947a5e1f376d790db5e96c90eab0f8f10d9d50b9aa9c41e5e20f1168c8df` |
| `driver/adc.c` | `4b555ee530c7f2e3270e968daedd4f7ea474a211f1e0668d0b52a37e5c2b8aba` |
| `driver/main.c` | `5f064b33267c91c6022606918c6ff719ef17a4998694da7f4d9c27e6d5e6ad10` |
| `driver/main.h` | `62af2e8d409af074261e790747a8e3ac346f4014c8ddad94e57a3d72b760e308` |
| `driver/Makefile` | `ddfc66af6aa28f9c4cde8da66863f9381d46984e6cbc52e0c4143059df48ef30` |
| `install.sh` | `6b4a2d6fba82090154a06f1c9a6efbdaf5eda0e6ee88b8cb41f3e5c1449d912d` |
| Audio setup script | `5430deaf10b455e689c858d00b5f86eb6d9827992e68a2253b0fa9602087ed64` |

The host reports kernel `6.12.109+rpt-rpi-2712`; its build Makefile is present.
That establishes a prerequisite only, not successful compilation or compatibility.
No module was built, installed, loaded or unloaded during this checkpoint.

## Confirmed interface and failure behavior

### PWM

The pinned [PWM implementation](https://github.com/sunfounder/fusion-hat/blob/4bd1018ad5a70ee113160536f969cdadd9f22918/driver/pwm.c)
exposes twelve channel directories below the device's `pwm` directory, with
`period`, `duty_cycle` and `enable`. Time values use microseconds. Channels share
timers in groups of four. The recent implementation propagates several period
and duty-write errors, which is useful, but does not meet all cleanup requirements.

1. `enable_store` sets the cached enabled state before the operation completes.
2. Its disable branch ignores the result of the hardware zero-pulse write.
3. It returns the input byte count even when that write fails.
4. It retains the previous cached pulse. A later enable writes that pulse again.
5. Duty writes are rejected while disabled, so an adapter cannot simply clear
   the cached pulse through the duty interface before enabling a disabled channel.

The later pulse restoration is upstream behavior, not proof of a failure on the
owner's board. It conflicts with the required guarantee that opening/recovering
an actuator session does not silently resume old motion. Clearing duty before a
normal close helps only when communication and that prior session both succeed;
it does not resolve every crash or failed-disable case.

### Battery freshness

The pinned [battery implementation](https://github.com/sunfounder/fusion-hat/blob/4bd1018ad5a70ee113160536f969cdadd9f22918/driver/battery.c)
returns early on voltage or charging-status read failure. It retains the old
voltage. `fusion_hat_get_property` returns that cached voltage as a successful
`voltage_now` result without a sample timestamp or validity check.

The periodic worker tries updates, but a userspace file-read timestamp measures
when the cache was read, not when the battery was successfully sampled. A voltage
that remains unchanged may be either healthy or stale. The existing
[ADC interface](https://github.com/sunfounder/fusion-hat/blob/4bd1018ad5a70ee113160536f969cdadd9f22918/driver/adc.c)
provides direct channels 0–3 only, not battery channel 4. It does not offer an
alternative fresh battery reading. Kernel-log parsing is not a dependable
safety interface, and forced direct I2C access would violate single ownership.

The unit correction remains established: ADC counts are scaled by the vendor,
and `voltage_now` reports microvolts. Correct units do not solve stale samples.

### Installer boundaries

The candidate installer is not safe to reuse wholesale for this project:

- Its pinned top-level script downloads a mutable shared installer and clones a
  branch, so pinning only that script does not pin transitive code.
- It removes an existing vendor checkout and changes system Python packages.
- The vendor Makefile can install packages, unload modules, replace prior module
  installations and alter DKMS registrations. A nominal build is not necessarily
  a read-only build when headers are missing.
- Audio setup loads a sound overlay, changes `/etc/asound.conf`, installs packages,
  restarts audio services and can alter a selected user's default audio devices.
- PWM and speaker controls are created world-writable in the candidate source;
  deployment should scope access to the authorized device group.

The eventual installation wrapper must use an explicit manifest, pinned inputs,
controlled build commands, preview/apply separation, backups and rollback. No
vendor installer or Makefile target was executed during review.

## Executable reproduction

The [reproducer](../../scripts/reproduce_fusion_vendor_contract.py) verifies the
SHA-256 values for the two source files, extracts the exact upstream update,
property and enable functions, supplies fake bus operations, then compiles and
runs a temporary C program. It does not compile a kernel module or touch devices.
It accepts a local vendor checkout, never downloads or executes its installer.

From the robot repository root, using the exact reviewed vendor source:

```bash
uv run --frozen python scripts/reproduce_fusion_vendor_contract.py /path/to/fusion-hat
```

Observed result:

```text
successful battery poll: status=0, voltage_now=7494000 uV
failed battery poll: get_property status=0, voltage_now=7500000 uV
failed PWM disable: return=1, cached enabled=0, cached duty=1500 us
subsequent enable: return=1, restored pulse=1500 us
Three upstream contract failures reproduced using extracted functions and simulated I/O.
```

Exit zero means these expected failures were reproduced, **not** that the driver
is acceptable. Different source hashes are rejected. The compiler and harness
have 30-second subprocess timeouts; temporary compilation outputs are cleaned up.

Limitations: mutexes, bus operations and PWM arithmetic helpers are mocked. This
validates control flow and error propagation, not kernel scheduling, timing,
electrical behavior or hardware safety. A complete patched-driver test must add
kernel build and concurrency/error-injection coverage.

## Concrete proposed addition: maintained vendor safety patch

Recommendation: add a small, versioned patch series to the pinned driver, then
continue the approved kernel-owner architecture. Do not switch to competing raw
I2C access or weaken telemetry eligibility.

Proposed repository artifacts:

- `vendor/fusion-hat/patches/`: readable patches, ordered series and license notice;
  no compiled module committed.
- `vendor/fusion-hat/manifest.json`: upstream revision, source/archive hashes,
  patch hashes and a distinct project patch-level identifier.
- Focused simulated contract tests and a kernel build check; integrate with the
  already planned installation wrapper and pi5servo transport after acceptance.

Proposed upstream scope:

| Upstream file | Proposed change | Acceptance |
| --- | --- | --- |
| `driver/pwm.c` | Return disable errors; update cached state only consistently with successful writes; clear stored pulse on successful disable; ensure enable never revives stale pulse; audit partial timer-group failure and report uncertainty | Injected bus failure is visible; subsequent enable starts at zero; other active channels retain their explicit pulse/frequency contracts |
| `driver/battery.c` | Invalidate cached telemetry on refresh failure, record monotonic last-success state, and return an error when required voltage is invalid/expired | Good sample then failed update cannot return old voltage as current; recovery requires a new successful sample |
| `driver/main.h` | Add validity/freshness state and reviewed timeout constants, protected by the existing lock | Concurrent update/read is coherent; initialization starts invalid |
| `driver/main.c` or driver metadata | Expose a verifiable patched-interface version and audit cleanup/periodic worker ordering | NinjaRobot can reject an unpatched or incompatible module before motion |
| PWM/speaker attribute declarations | Limit write permissions to approved deployment users/groups, with installation rules | Ordinary unrelated users cannot write actuator controls |

Choose the precise freshness bound after checking the worker interval and worst
case I2C behavior. Test expiration without using wall-clock changes. Do not
invent a timestamp in Python around a cached read. A first failed refresh or
expired successful sample must be distinguishable from low battery voltage.

The patch-level check belongs in prerequisite validation, not model judgment.
All pi5servo, IDE and Agent public contracts in the approved plan remain intact.
Other managed pi5 libraries remain unchanged. DFRobot/PCA do not depend on this
module and must not load it through their profile setup.

Before installation, require clean patch application, source/hashes verification,
regression tests of success/failure/recovery, a build for the target kernel, and
an installer rollback preview. These changes do not authorize live actuation,
recording, reboot or shutdown during automated validation.

Rollback: preserve the previous module/configuration and uninstall only files in
the installation manifest. A restored unpatched Fusion module must leave the new
Fusion motion capability unavailable with an actionable prerequisite error; it
must not silently fall back to direct bus control.

## Phase status and documentation impact

Phase 0 baseline and initial contract review are complete; its acceptance gate
fails for the pinned driver. Installer manifest completion and the remaining
physical PWM failure trace still belong to Phase 0 follow-up. Phases 1–7 are not
claimed implemented. No previously registered wiki source was changed, and no
wiki ingestion or review was run.

This checkpoint adds an evidence-only reproduction tool, not robot behavior or
an installed dependency. The validation document is its usage guide. Runtime
README/manual successor updates remain scheduled with the approved behavior
implementation; publishing those claims now would be inaccurate.

The next decision is approval to maintain the narrowly scoped vendor kernel
patch described above. The alternative is to wait for an upstream revision
meeting the same contracts and qualify that revision before continuing.
