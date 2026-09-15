# Servo, chat context, and game validation — 15 September 2026

This record separates completed software validation from Raspberry Pi checks that
can communicate with devices or move the wheel servos.

## Scope

- Classify `servo.stop` as a normal priority interrupt while preserving genuine
  Level 1 and Level 2 safety stops.
- Keep long Ninja Chat transcripts usable by bounding each model request without
  deleting stored history or splitting tool-call/result pairs.
- Make the supported distance game available by default while preserving module
  health, admission, runtime, stop, and system-safety restrictions.
- Preserve the Agent to IDE to managed-driver hardware boundary and all existing
  public request/result shapes.

## Evidence received

The operator supplied a safety snapshot with `fault_detail`, `reason`, and both
latches clear, followed by Raspberry Pi throttling state `0x0`. A later
`ninjarobot-agent status` attempt returned `AgentIPCError: agent service is not
running`. This evidence does not show a persistent power, motion, or system fault,
and the stopped service could not provide live event or tool traces.

## Root causes

1. `servo.stop` used the `EMERGENCY` risk label to obtain the execution engine's
   lock-free priority path. The same stop is expected during movement transitions,
   disarm, cancellation, and browser lease loss, so discovery and event consumers
   could see ordinary servo lifecycle work as emergency-class work.
2. `AgentLoop` passed the entire retained transcript on every model turn. It
   measured the fully serialized request and raised the reported error above
   128,000 characters, but had no rolling selection strategy.
3. Refinement Phase 5 deliberately defaulted `distance_game.enabled` to false.
   IDE admission, health, and bundled skill instructions all enforced or reported
   that gate, even though the game is a supported built-in capability.

## Implemented behavior

- The engine now recognizes priority interrupts through its closed capability
  allowlist. `servo.stop` is `LOW` risk but remains immediate; `behavior.stop`
  remains the explicit Level 2 operation.
- The Agent retains the full local transcript and uses a logarithmic search for
  the largest recent suffix of complete user turns that fits each request. A
  trusted omission notice is inserted, and tool history is repaired atomically.
- Distance-game availability no longer depends on an enable flag. Existing
  private configurations containing `enabled = false` still parse, but module
  health and safety remain authoritative.

## Automated validation result

Status: software implementation checks pass, with one pre-existing public-help
checkpoint failure and the explicitly deferred wiki publication work recorded
below. Automated tests use fake devices and do not start the Agent service, access
GPIO/I2C/SPI/PWM, capture media, move servos, play physical audio, expose a network
port, or invoke power control.

- Immutable managed drivers: pass; 222 tracked files and 56 authorized repairs.
- Workspace driver source resolution: pass for all six managed libraries.
- Python compilation: pass for IDE, Agent, scripts, and tests.
- Ruff lint: pass.
- Ruff format: pass; 447 files already formatted.
- MyPy: pass; 112 source files.
- Full repository pytest: 889 passed and one failed. The failing
  `test_real_public_checkpoint_and_missing_checkout` is reproducible from
  unchanged `HEAD` public pages and manifest: all four curated page hashes already
  differ from the fixed 12 September public-help manifest, while the cited source
  hashes still match. This change did not modify those pages or that manifest.
  The manifest was not refreshed because doing so would attest changed curated
  content without the owner's deferred semantic review.
- Repository pytest excluding that one independently identified checkpoint test:
  889 passed, one deselected, with the existing Starlette `httpx` deprecation
  warning.
- Separate managed-driver pytest processes: `pi5buzzer` 68, `pi5camera` 27,
  `pi5disp` 65, `pi5mic` 92, `pi5servo` 134, and `pi5vl53l0x` 71 passed. The mic
  suite reports the existing Python `audioop` deprecation warning.
- Web static validation: `node --check` passed and all four locale JSON files
  parsed. The optional Playwright viewport script was not run because Playwright
  is absent from the frozen repository environment; no dependency was installed.
- Documentation: all local links resolve in the seven changed/new documents.
- Wiki lint: 27 pre-existing `missing-derived-manifest` errors plus four expected
  `unregistered-source` suggestions for the new 15 September sources. Wiki check
  reports the 14 changed implementation fingerprints as needing knowledge review,
  which is expected because the owner deferred registration and semantic review.
- `git diff --check`: pass.

## Safe smoke checks

Risk: no intentional device output or movement. Run these on the Raspberry Pi from
the repository root after installing the tested revision. Do not start a second
Agent if the managed service already owns the robot.

```bash
uv run --frozen --no-sync ninjarobot-agent service status
uv run --frozen --no-sync ninjarobot-agent game status
```

Expected result: the service is running once, and game status reports
`enabled: true` with `state: idle`. The game status command does not sample the
sensor. If the service is stopped, start it with the project's existing service
manager only when the robot is in a safe location.

Open a terminal chat and continue an existing long transcript with several short
turns. Expected result: replies continue after old history exceeds the former
request budget, recent conversational continuity remains, and the visible stored
transcript is not erased. A single extremely large new message should receive the
new message-specific bounded error.

Pass/fail: pending operator execution.

## Device communication checks

Risk: service startup can initialize configured devices. The game check reads the
distance sensor and uses the display and buzzer, but never commands wheels. Keep
the robot stable, keep hands clear of wiring, and stop on undervoltage or heat.

Before the game, recheck the platform and safety state with the same read-only
commands used to produce the supplied evidence. Expected result: throttling is
`0x0`, `motion_latched` and `system_latched` are false, and there is no fault.

```bash
uv run --frozen --no-sync ninjarobot-agent game start --seconds 5
uv run --frozen --no-sync ninjarobot-agent game status
```

Expected result: the sensor, display, and buzzer produce one bounded five-second
game without any enablement edit. Missing/unhealthy modules return a truthful
availability error; those legitimate restrictions are not bypassed.

Pass/fail: pending operator execution.

## Actuator-moving checks

Risk: wheel servos move. Raise and secure both wheels, provide stable external
servo power with common ground, keep an operator at an accessible physical power
disconnect, and keep the robot away from edges. Do not continue after unexpected
motion, undervoltage, heat, or a safety fault.

1. Use the IDE movement control for one brief command, then its normal stop.
2. Use each web D-pad direction briefly and release it before selecting another.
3. Arm one Agent session and request one short servo behavior, then disarm it.
4. After each path, inspect the safety snapshot.

Expected result: release, transition, cancellation, and disarm stop wheel pulses
immediately, while `system_latched` remains false and no Level 2 screen appears.
A genuine undervoltage, watchdog, or servo interruption must still create the
documented fail-safe state.

Finally, press the web Emergency Stop control once. Expected result: all relevant
devices stop or suspend, the persistent Level 2 indication appears, and ordinary
movement remains blocked until the operator corrects any fault and confirms
Resume. This proves the fix did not weaken the intended emergency path.

Pass/fail: pending operator execution.

## Power-risk checks

Risk: shutting down the Raspberry Pi can interrupt filesystems and device power.
No power command changed, and this implementation does not require a live power-off
test. Verify only that the existing power-control capability and confirmation
policy remain present in service status or the non-executing validation workflow.

Expected result: power-off remains unavailable unless explicitly configured and
confirmed. Do not invoke it for this fix.

Pass/fail: pending operator execution; command execution is not required.

## Rollback and failure response

If a wheel does not stop immediately, use Emergency Stop, remove servo power with
the prepared physical disconnect, and stop the managed Agent service. Preserve the
safety snapshot and service journal before changing configuration or restarting.

Roll back by stopping the service, reinstalling the previously known-good project
revision through the established deployment workflow, and starting only one
hardware owner. Do not edit managed driver sources or regenerate their immutable
baseline. A private `distance_game.enabled` value is compatibility data, not a
rollback switch in this revision.

## Documentation status

New complete raw versions of the Installation Guide, Development Guide, MCP/Skill
Guide, and Development Log exist under the dated `2026-09-15` directories.
Registered originals were not edited. Per owner instruction, the new sources have
not been registered, ingested, normalized, prepared, or semantically reviewed;
`project-knowledge.json` and curated wiki pages remain unchanged for later manual
review.
