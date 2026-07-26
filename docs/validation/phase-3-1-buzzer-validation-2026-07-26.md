# Phase 3.1 GPIO27 buzzer validation report

Date: 2026-07-26

Hardware accessed during implementation: No

Physical Raspberry Pi result: **PASS** (operator reported)

## 1. Scope of validation

This report covers the shared buzzer lifecycle, bounded tone arguments,
simulation, explicit real access, GPIO27 ownership, cancellation, emergency
silence, durable results, and cleanup.

Automated result: **PASS**

- Root/V4 tests: 56 passed.
- Managed-library tests: 449 passed.
- Strict mypy type checking: passed for 19 source files.
- Compilation, Ruff lint, Ruff formatting, dependency lock, CLI smoke, and
  `git diff --check`: passed.
- Driver provenance: 222 tracked files and 23 authorized repairs, unchanged.

The operator subsequently reported that every checklist item passed, including
the electrical prerequisite, simulated commands, real GPIO27 health, both
short-tone tests, emergency silence, duplicate protection, and GPIO release.
No failed or unexpected result was reported.

## 2. Safety notes

`buzzer play` makes no sound unless `--real` is supplied. A real command drives
GPIO27 and may produce an unexpectedly loud tone.

Before real sound, record:

- the exact buzzer module or component
- its rated voltage and current
- whether GPIO27 drives it through a transistor
- how buzzer power can be disconnected quickly

A transistor is an electronic switch that lets the GPIO control a load without
supplying all of its current directly. Do not connect or rewire the buzzer
while the Raspberry Pi is powered.

## 3. Safe smoke tests

Start at the project root:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen

PHASE31_LEDGER="$(mktemp /tmp/ninjarobot-phase31-XXXXXX.sqlite3)"
echo "$PHASE31_LEDGER"

uv run --frozen ninjarobot_pi5_cli capabilities
uv run --frozen ninjarobot_pi5_cli buzzer health \
  --ledger "$PHASE31_LEDGER"
uv run --frozen ninjarobot_pi5_cli buzzer play \
  --ledger "$PHASE31_LEDGER" \
  --frequency 440 \
  --duration 0.05 \
  --volume 16 \
  --action-id phase31-sim-tone-1 \
  --idempotency-key phase31-sim-tone-key-1
uv run --frozen ninjarobot_pi5_cli buzzer stop \
  --ledger "$PHASE31_LEDGER" \
  --action-id phase31-sim-stop-1 \
  --idempotency-key phase31-sim-stop-key-1
```

Expected:

- capabilities include `buzzer.play_tone` with risk `low`
- capabilities include `buzzer.stop` with risk `emergency`
- health is `ready`
- play succeeds with `retry_safety: unsafe`
- play and stop both report `"simulated": true`
- no real sound or GPIO access occurs

## 4. Communication/interface tests

Only continue after the electrical record above is complete.

Install the Raspberry Pi GPIO dependency:

```bash
uv sync --frozen --extra hardware
uv run --frozen ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example
pinctrl get 27
```

Expected: configuration reports `buzzer=GPIO27`. Before the adapter starts,
GPIO27 should not be owned by an unexpected alternate function.

The following command opens GPIO27 and sets the output silent, but does not
request a tone:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli buzzer health \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE31_LEDGER"
```

Expected: both buzzer capability components and overall health are `ready`.
The buzzer remains silent and GPIO is released when the command exits.

## 5. Actuator-moving tests

The buzzer is not a moving actuator, but this section contains commands that
energize hardware and produce sound.

Keep the power disconnect within reach. Start with a quiet 0.1-second tone:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli buzzer play \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE31_LEDGER" \
  --frequency 440 \
  --duration 0.1 \
  --volume 8 \
  --action-id phase31-real-tone-1 \
  --idempotency-key phase31-real-tone-key-1
```

Expected:

- one short, quiet tone is audible
- status is `succeeded`
- data reports `"simulated": false`
- retry safety is `unsafe`
- the buzzer is silent immediately after the command

Test a second frequency using a new action ID:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli buzzer play \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE31_LEDGER" \
  --frequency 660 \
  --duration 0.1 \
  --volume 8 \
  --action-id phase31-real-tone-2 \
  --idempotency-key phase31-real-tone-key-2

uv run --frozen --extra hardware ninjarobot_pi5_cli buzzer stop \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE31_LEDGER" \
  --action-id phase31-real-stop-1 \
  --idempotency-key phase31-real-stop-key-1
```

Expected: the pitch is higher, the tone stops after 0.1 seconds, and the stop
result reports `stopped: true`.

## 6. Expected outcomes

- Simulation never imports or opens `pi5buzzer`.
- Real health initializes GPIO27 at zero duty and closes it silently.
- Invalid frequency, duration, volume, or extra arguments never reach GPIO.
- Repeating an action ID returns its stored result without playing twice.
- Cancelling a running action calls `off()`.
- Engine close calls `off()` and releases GPIO27.
- Emergency stop is idempotent and confirmation-free.

## 7. Pass/fail checklist

- [x] Electrical voltage/current/transistor record is complete.
- [x] Hardware-free capability listing passes.
- [x] Simulated health passes silently.
- [x] Simulated play and stop report `simulated: true`.
- [x] Hardware dependency installs.
- [x] Configuration reports GPIO27.
- [x] Real health passes without sound.
- [x] 440 Hz test produces one short, quiet tone.
- [x] 660 Hz test is audibly higher.
- [x] Every tone stops at the requested time.
- [x] Emergency stop reports success and leaves the buzzer silent.
- [x] Repeating an action ID does not play twice.
- [x] GPIO27 is released when each command exits.
- [x] No servo, display, camera, or microphone is operated.

## 8. Rollback steps

1. Run the real stop command from Section 5 if GPIO remains available.
2. If sound continues, disconnect buzzer power using the prepared disconnect.
3. Shut down with `sudo poweroff` before inspecting or changing wiring.
4. After restart, check GPIO27 with `pinctrl get 27`.
5. Recheck driver integrity:

   ```bash
   uv run --frozen python scripts/verify_immutable_drivers.py
   ```

Do not continue to the display adapter until the buzzer result is reviewed.
