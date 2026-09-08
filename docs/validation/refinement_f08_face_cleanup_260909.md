# Face-recognition cleanup repair — 9 September 2026

The owner explicitly approved implementing the prepared face-recognition cleanup
and updating the walkthrough. The repair is now applied to
`pi5camera/src/pi5camera/core/recognition.py`. It closes a successfully constructed
recognition backend after a normal return or a failure during image acquisition,
detection, index reading or pending-record storage.

## Scope and compatibility

The managed-file change matches the driver portion of the previously prepared
[proposal](refinement_f08_face_cleanup.patch). The processing block now sits inside
`try/finally` (a construct that runs cleanup when the block exits). If the backend
provides a callable `close` method, it is invoked once. Backends without that
method retain compatibility. Existing matching, enrollment, result fields, camera
capture decisions, stored-face formats and hardware interfaces are preserved.

The actual backend closes its MediaPipe detector when present. Its existing close
implementation handles ordinary detector-close errors internally. This repair
does not promise immediate process-memory reduction, cleanup of an object whose
constructor never returned, or forced termination of a blocked native call.
No other managed-driver file changed. The display-font proposal remains pending.

## Authorization and driver integrity

The repair is recorded in
[authorized driver changes](authorized_driver_changes.json), authorized by
Project owner on 2026-09-09. The import baseline file was not regenerated.

- Original file SHA-256 (content fingerprint): `d9292fc40edd3877b9ed8d5f07c6ae77ee64be4b44607387be50a0ed2ae19c79`.
- Approved file SHA-256: `a2dfc279a824c489546b8b3dd52b53d71ae029a2886e2c07d553f8b492c71a12`.
- Before: 222 managed files across six drivers, 55 existing authorized repairs.
- After: the same 222 files and six drivers, 56 authorized repairs.

## Validation results

Commands ran from the repository root in the existing environment, with
`uv run --frozen --no-sync` to avoid changing installed packages.

| Check | Result |
| --- | --- |
| `pytest -q pi5camera/tests` in its own process | 27 passed |
| `pytest -q ninjarobot_pi5_ide/tests/test_face_backend_cleanup.py` | 8 passed |
| `pytest -q` | 742 passed; one existing Starlette test-client deprecation warning |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed, 402 files |
| `mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src` | Passed, 88 source files |
| `python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src pi5camera/src scripts tests` | Passed |
| Both immutable-driver and workspace-driver-source verifiers | Passed |
| `git diff --check` | Passed |

The focused regression suite uses fake backends, capture and storage functions;
no real camera, personal image, recognition model or user database is accessed.
It covers normal return, missing image, capture failure, generic detection error,
recognition-specific error, index failure, storage failure and five repeated calls.
The independent driver suite retains known/unknown-face and enrollment coverage.

## Documentation and manual acceptance

The [updated walkthrough](refinement_phase2_walkthrough_260909.md#face-recognition-cleanup-tests)
provides copyable commands, expected outcomes, an optional installed-backend test,
privacy boundaries and rollback. The optional test generates a blank image and
uses temporary storage; it does not capture from the camera. It has not been run
against the real installed detector during this implementation.

Device communication, actuator-moving and power-risk tests are not required for
this cleanup. Any separately chosen live camera test still needs operator consent
and the existing single-owner procedure. No service, hardware, capture, deployment
or power action was performed by the coding agent.

README and current planning/progress/handoff notes now identify the repair as
implemented. This record provides the dated development rationale and validation.
Existing full manuals were reviewed for impact: the recognition lifecycle and
pending-repair statements need this update at the consolidated wiki revision;
installation commands, external-tool guidance and dependency notices need no
functional change. No new dependency or license was introduced.

Registered raw manuals remain unchanged. The earlier Phase 2 wiki diff and pointer
patch are historical proposals that still call the face cleanup pending. They
must be refreshed before publication; their previous preview checks are not
current publication approval. This focused repair does not publish the wiki,
apply the font proposal or start Phase 3.

## Rollback

If a regression appears, stop the affected service under operator control before
replacing runtime code. Revert only this driver change and its matching
`authorized_driver_changes.json` entry together, keeping the import baseline,
private data and unrelated checkout edits intact. Then rerun the independent
camera tests and driver verifier. Do not remove face profiles or reset the robot
to diagnose resource cleanup.
