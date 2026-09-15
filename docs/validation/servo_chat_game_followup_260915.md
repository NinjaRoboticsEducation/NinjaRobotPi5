# Servo, chat, and distance-game follow-up audit

Update after owner approval: the follow-up is implemented. See the
[walkthrough and validation results](servo_sensor_recovery_walkthrough_260915.md)
for the changed behavior, 906 passing root tests and one existing wiki-checkpoint
failure, the 457 passing driver tests, and remaining physical acceptance.
The audit below records the pre-repair findings; its approval request has been
satisfied. Wiki ingestion and review remain deferred.

This report records the defects reproduced on 15 September 2026 and the proposed
repair plan. The reviewed checkout was `6796531`. No runtime code, private
configuration, saved safety state, or managed driver has been changed by this
audit. No physical movement was performed.

The implementation plan requires owner approval under the repository's
[development instructions](../../AGENTS.md). In particular, the distinction
between an operator Emergency Stop and protection against genuine equipment
faults needs to be agreed before changing movement policy.

## Evidence and findings

The review used Serena symbol inspection, targeted source reads, wiki search,
the current development log, and the
[previous repair report](servo_chat_game_fixes_260915.md).

### 1. A temporary obstacle stop becomes a persistent movement stop

In `MotionController.drive`, a driver result with `interrupted = true`
unconditionally invokes `stop_motion("driver_interrupted", latch=True)`.
A latch is a saved stop that blocks another movement until recovery.

However, the controller itself can deliberately interrupt that driver when an
obstacle is detected. The resulting driver return value describes the expected
interruption, not a new hardware failure. The code overwrites the original
`front_obstacle` reason and creates a persistent stop.

A hardware-free reproduction used the existing controller test fixtures, a
40 mm distance reading, and a simulated ramp that returns `interrupted = true`
when stopped. The observed sequence was:

1. Distance monitor: obstacle inside 50 mm; stop without a latch.
2. Ramp returns interrupted.
3. Controller changes reason to `driver_interrupted` and sets the latch.

The final result was `stop_reason = driver_interrupted`, `latched = true`.
The existing safety test substitute always returns `interrupted = false`, so
its obstacle tests do not cover this sequence.

This confirms a software defect. It does not establish that this is the cause
of every reported stop on the physical Pi. Real undervoltage, driver errors,
and missed control-loop updates must remain distinguishable in diagnostics.

### 2. Normal servo stopping bypasses controller stop intent

`ServoStopAdapter.execute` calls `ServoDevice.stop` directly. It does not tell
the motion controller that this is an intentional, ordinary stop. This leaves
another path by which a driver interruption can be mistaken for a fault.

The web controller cancels its previous movement and invokes the normal servo
stop before starting a new direction. The repair must cover cancellation,
button release, direction changes, and stops during device preparation as well
as obstacle interruption. Changing the stop capability's risk label alone does
not repair these lifecycle paths.

### 3. Healthy distance hardware can remain marked unavailable

The distance adapter keeps ownership of a background read after cancellation.
This is necessary: cancelling an asynchronous caller does not stop its device
thread, and another read must not overlap it.

The problem is the recovery lifecycle. Cancellation sets `_recovery_required`.
Even when the background read has finished and the sensor is healthy,
`health()` returns unavailable and ordinary `start()` rejects recovery.
Only `start(recover=True)` checks the device and clears that state.

Movement cleanup cancels its distance monitor. The distance game also imposes
a 250 ms sample deadline, which can cancel a read. Game startup checks device
health without recovering this completed, abandoned work.

A hardware-free reproduction cancelled a read, let its thread finish, and
used a sensor whose identity check always succeeds. Results:

- Health after the cancelled read drained: `unavailable`.
- Ordinary start: `distance recovery must be explicitly requested`.
- Explicit recovery followed by health: `ready`.

The game enablement change is present. Requiring another configuration setting
would not fix this sensor ownership/recovery defect. Other causes of game
unavailability, including display or buzzer failure and invalid measurements,
must continue to be reported accurately.

### 4. Obstacle feedback is inconsistent across movement paths

Behavior execution supplies a user message and a bounded `scary` face for a
`front_obstacle` result. The requested expression is `confusing`.
Direct endpoint movement returns interruption status without the same cause,
recovery guidance, or presentation handling.

Some existing behavior definitions use `warn_only`, including backward motion
and celebration. The requested policy covers servo-related movements generally,
so the implementation must review those exceptions explicitly rather than
quietly leave unprotected paths. A front sensor cannot detect hazards behind
the robot; documentation must not claim otherwise.

### 5. The chat-history budget repair is present and passes its tests

`AgentLoop._bounded_request` first tries the complete conversation. If it is too
large, it selects recent complete user turns that fit the configured serialized
request budget, retaining required prompts and tool definitions. It repairs
tool-call/result pairing and adds an omission notice. Stored history is not
deleted. An oversized current turn is rejected before provider/tool execution.

The targeted tests pass for long conversations, preserving the transcript,
keeping tool exchanges together, and rejecting an oversized request. No
regression in that repair was demonstrated during this audit.

Limits: this is a character budget, not an exact model token count (the number
of text pieces processed by a model). It does not prove that every provider's
smaller context window will accept every locally allowed request. The separate
20,000-character per-message limit also remains. Tool output has its own
bounded serialization guard. Neither limit should simply be increased.

## Proposed implementation phases

### Phase A: Correct stop ownership and user feedback

Objective: ordinary stops and obstacles do not become an Emergency Stop or
require Resume; intentional Emergency Stop remains effective.

Primary files: IDE `safety.py`, `servo.py`, `robot.py`, behavior coordination,
and their tests; Agent web/IDE-tool presentation only where required.

Implementation steps:

1. Preserve the first authoritative stop cause when a ramp returns interrupted.
   Do not treat an already-requested stop as an independent driver fault.
2. Route integrated normal servo stopping through the motion controller while
   preserving the public `servo.stop` response contract and standalone use.
3. Ensure interrupted behavior sequences cannot continue into later movement
   stages. Cover cancellation and concurrent explicit Emergency Stop.
4. Apply the agreed 50 mm obstacle policy consistently. Prevent repeated
   commands from driving through a known nearby obstacle. Use fresh readings;
   do not claim a stale or failed reading proves the path is clear.
5. Stop the servo movement, show the confusing face, and return clear obstacle
   guidance through direct endpoint, behavior, IDE-tool, and web paths.
6. Clearing an obstacle allows a new command without Resume. Never replay the
   old movement automatically. Preserve unrelated working functions.
7. Reserve the operator Emergency Stop wording for an explicit operator action.
   Retain protective stopping for actual driver failures, undervoltage, and a
   stalled control loop, with the actual cause and recovery guidance. Do not
   bypass hardware fault protection or automatically clear an operator stop.

Compatibility: preserve capability names, managed drivers, calibration, saved
state format, and the Agent-to-IDE hardware boundary. Add response information
only where contracts permit it. Do not automatically erase existing stop state.

Risk: motor-facing; validation uses substitutes first. Gate: regression tests
for an obstacle during a ramp, ordinary stop during a ramp, direction changes,
endpoint feedback, repeated movement after clearance, and Emergency Stop races.
Fault tests must prove that genuine failures still stop unsafe motion.

### Phase B: Recover distance access without overlapping device work

Objective: game and movement requests can reuse a healthy sensor after normal
cancellation without a manual configuration change or system Resume.

Primary files: IDE `distance.py`, `distance_game.py`, preparation/cleanup in
`safety.py` and `robot.py`, and ownership/game tests.

Implementation steps:

1. Keep exclusive ownership of an unfinished background device call.
2. Add bounded preparation/recovery for the next legitimate operation after
   abandoned work drains; check health before clearing recovery state.
3. Prepare shared devices before game health admission, respecting the
   foreground output owner and explicit system stops.
4. Handle sample deadlines without permanently poisoning a healthy adapter or
   accepting a late sample as current. Avoid retry loops or queued reads that
   outlive the game.
5. Report which required device is unavailable and why. A stuck worker or failed
   health check remains unavailable with a useful explanation.

Compatibility: retain existing game commands, automatic enablement, volume and
duration limits, and no wheel movement during the game. No managed-driver edit
or private configuration migration is planned.

Risk: sensor ownership and shared output coordination. Gate: cancellation during
read, late completion, stuck read, failed recovery, movement-to-game transition,
game restart, and explicit Emergency Stop tests with no device overlap.

### Phase C: Complete chat audit, validation, and documentation

Objective: demonstrate regression coverage and provide a usable manual test
guide before declaring the repair complete.

Extend chat checks if necessary for recovery on the next short turn after an
oversized turn and boundary cases with required context. Preserve full stored
history and avoid live provider calls in automated tests.

Run the repository gates: immutable-driver verification, workspace-driver-source
verification, compileall, Ruff lint and format checks, mypy, pytest, and
`git diff --check`. Run relevant web/interface tests if those files change.
Do not hide unrelated baseline failures or refresh knowledge hashes to make
tests pass. Driver tests are separate processes if a driver change becomes
necessary; such a change would require its own approval.

After implementation, update README and new versions of the installation and
development manuals and development log in one documentation pass. Record the
stop policy, automatic sensor recovery, limitations, and exact test results.
Wiki search currently returns draft/unverified pages; installation guidance
still describes manual game enablement and conflicts with current code.
Do not treat those pages as evidence that hardware acceptance has passed.
Wiki ingestion and semantic publication remain deferred; do not mutate
registered source originals or claim an unperformed review.

## Validation performed during this audit

From the repository root, the following hardware-free command passed:

```bash
uv run --frozen --no-sync pytest -q \
  ninjarobot_pi5_ide/tests/test_safety.py \
  ninjarobot_pi5_ide/tests/test_servo.py \
  ninjarobot_pi5_ide/tests/test_distance.py \
  ninjarobot_pi5_ide/tests/test_distance_game.py \
  ninjarobot_pi5_agent/tests/test_agent_loop.py \
  ninjarobot_pi5_agent/tests/test_game_controls.py
```

Result: **107 passed in 4.76 seconds**. These passing existing tests do not cover
all reproduced defects. The separate targeted reproductions above demonstrate
the missing cases.

`uv run --frozen --no-sync python scripts/verify_immutable_drivers.py` passed:
222 tracked files across six drivers, with the existing 56 authorized repairs.
No full lint/type/test gate or physical acceptance is claimed for this audit.

## Manual acceptance required after implementation

- Safe smoke: confirm imports, configuration, and reported stop reasons without
  moving hardware. Expected: existing setup works and no user data is changed.
- Device communication: read distance, cancel a read, then start the game after
  completion. Expected: healthy sensor recovers without manual enablement;
  genuinely unavailable hardware gets an accurate explanation.
- Actuator-moving: raise wheels and keep an operator ready to remove power.
  Test IDE movement, web direction/release, and an obstacle within 50 mm.
  Expected: servos stop, confusing face and guidance appear, and a fresh command
  works after clearance without Resume. The old command never restarts itself.
- Explicit Emergency Stop: use the button during a controlled movement.
  Expected: stop persists until deliberate recovery; obstacle clearance alone
  must not clear it.
- Power-risk: no live undervoltage, forced control-loop stall, or shutdown test
  is authorized by this audit. Exercise those paths with substitutes only.
- Rollback: stop using motion controls, shut down the Agent normally, and restore
  only the eventual repair files from the prior revision after preserving any
  user edits. Keep private configuration and safety-state data intact. No
  rollback is needed for this documentation-only audit.

The final walkthrough must provide exact commands and observed outcomes once
the implementation and software gates are complete.
