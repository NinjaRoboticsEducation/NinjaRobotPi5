# Phase 2 validation report

Date: 2026-07-26

Phase: IDE core and read-only VL53L0X reference adapter

Hardware accessed during implementation: No

## 1. Scope of validation

This report covers capability discovery, adapter lifecycle, the bounded
scheduler, resource locks, the SQLite action ledger, duplicate protection,
deadlines, timeouts, cancellation, restart recovery, health reporting, the
unified CLI, and the `distance.read` adapter.

The automated implementation result is **PASS**. The operator subsequently
completed the Raspberry Pi checklist and reported **PASS**.

- Root/V4 tests: 49 passed.
- Strict mypy type checking: passed for 18 source files.
- Compilation, Ruff lint, Ruff formatting, and `git diff --check`: passed.
- Managed-library tests: 449 passed.
- Driver provenance: 222 tracked files and 23 authorized repairs, unchanged.

### Operator evidence

Operator: `rogerchang`

Result: **PASS**

The real Phase 2 CLI completed 10 of 10 requested actions successfully on
2026-07-26. Readings were `123`, `48`, `83`, `103`, `55`, `149`, `61`, `134`,
`89`, and `95` mm. Every raw value matched the normalized distance, every
result reported retry safety `safe`, and no `8191 mm` sentinel appeared.
Individual reads completed in approximately 37 milliseconds. Millisecond means
one thousandth of a second.

## 2. Safety notes

Commands in the safe-smoke section do not open I2C or any other hardware.
Simulation is the default. Real sensor access requires the visible `--real`
flag.

The Phase 2 hardware path only reads the VL53L0X distance sensor. It does not
move servos, energize the buzzer, change the display, capture a photograph, or
record audio. Shut the Raspberry Pi down before changing sensor wiring.

The target sensor is on I2C bus 1 at address `0x29`. I2C is the two-wire
communication bus; `0x29` is the sensor's hexadecimal (base-16) address.

## 3. Safe smoke tests

Start at the `NinjaRobotPi5` project root:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen
uv run --frozen ninjarobot_pi5_cli --version
uv run --frozen ninjarobot_pi5_cli --help
uv run --frozen ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example
uv run --frozen ninjarobot_pi5_cli capabilities
```

Expected:

- Configuration reports GPIO27, GPIO12/GPIO13, DC4/RST5/BL6, rotation 90°,
  and brightness 75%.
- Help lists `capabilities`, `health`, `distance`, and `actions`.
- `capabilities` reports `distance.read`, risk `read_only`, resource `i2c-1`,
  and confirmation `false`.
- Nothing on the robot moves, sounds, lights, records, or takes a measurement.

Create a fresh simulated ledger:

```bash
PHASE2_LEDGER=/tmp/ninjarobot-phase2-manual.sqlite3
rm -f /tmp/ninjarobot-phase2-manual.sqlite3

uv run --frozen ninjarobot_pi5_cli health \
  --ledger "$PHASE2_LEDGER"

uv run --frozen ninjarobot_pi5_cli distance read \
  --ledger "$PHASE2_LEDGER" \
  --action-id phase2-manual-1 \
  --idempotency-key phase2-manual-key-1
```

Expected: health is `ready`, the action is `succeeded`, and the explicitly
simulated distance is `250`. The result has the same top-level fields used by
the real adapter: `action_id`, `status`, `data`, `error`, timestamps, and
`retry_safety`.

## 4. Communication and interface tests

### Confirm duplicate protection

Run the exact same simulated read command again:

```bash
uv run --frozen ninjarobot_pi5_cli distance read \
  --ledger "$PHASE2_LEDGER" \
  --action-id phase2-manual-1 \
  --idempotency-key phase2-manual-key-1

uv run --frozen ninjarobot_pi5_cli actions show \
  --ledger "$PHASE2_LEDGER" \
  --action-id phase2-manual-1
```

Expected: both commands show the original result and original timestamps. The
adapter did not execute a second time. This is idempotency, meaning an
accidental repeated request cannot duplicate the operation.

### Prepare the real Raspberry Pi sensor environment

```bash
uv sync --frozen --extra hardware
sudo raspi-config nonint do_i2c 0
sudo apt-get update
sudo apt-get install -y i2c-tools
i2cdetect -y 1
```

Expected: `i2cdetect` shows `29`. It may also show the DFR0566 HAT at `10`.
If `29` is absent, stop. Shut down with `sudo poweroff`, disconnect power, and
check the sensor wiring before continuing.

Check identity and adapter health without taking a distance measurement:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli health \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE2_LEDGER"
```

Expected: overall status is `ready` and `distance.read` is `ready`. If it is
`unavailable`, run one real distance action to obtain structured error detail,
or use the standalone driver status command to investigate I2C access:

```bash
uv run --directory pi5vl53l0x --frozen pi5vl53l0x status
```

### Take one real reading

Place a flat, matte target about 100 to 300 mm in front of the sensor, then run:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli distance read \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE2_LEDGER" \
  --action-id phase2-real-1 \
  --idempotency-key phase2-real-key-1
```

A pass is `status: succeeded`, a positive `distance_mm` below 8190, and a
distance that changes sensibly when the target moves.

If the sensor returns `8191`, the CLI should exit with code 1 and report
`DEVICE_INVALID_READING`. That means the Phase 2 guard is working, but the
physical distance measurement fails. Do not calibrate an invalid stream.

### Repeat, close, and restart

After one valid reading, run:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli distance read \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE2_LEDGER" \
  --count 10 \
  --interval 0.5

uv run --frozen --extra hardware ninjarobot_pi5_cli health \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE2_LEDGER"
```

Expected: ten valid results, then ready health in a new process. Each command
initializes and closes the sensor, so the second command also checks clean
restart after close.

## 5. Actuator-moving tests

None. Phase 2 has no actuator capability. Do not run servo, buzzer, display,
camera, or microphone commands as part of this checklist.

## 6. Power-risk tests

No powered actuator test is authorized by Phase 2. If the VL53L0X must be
rewired, shut down and remove Raspberry Pi power first. Follow the voltage
labels printed on the exact sensor breakout; do not guess whether its input is
3.3 V or 5 V.

## 7. Expected outcomes

- Simulation works without the `hardware` extra.
- Capability listing never imports or opens the sensor driver.
- Real health opens I2C only when `--real` is present.
- A valid driver sample becomes a successful standardized result.
- `8191 mm`, zero, negative, missing, or incorrectly typed data becomes
  `DEVICE_INVALID_READING`.
- The same action ID and request return the stored result without a second
  sensor read.
- The ledger remains readable after the process closes and restarts.
- Every real command releases the I2C handle before exiting.

## 8. Pass/fail checklist

- [x] Root environment installs with `uv sync --frozen`.
- [x] Hardware-free capability listing passes.
- [x] Simulated health reports ready.
- [x] Simulated distance result reports 250 mm and succeeded.
- [x] Repeating the same ID returns the original stored result.
- [x] `actions show` returns the durable record.
- [x] Raspberry Pi hardware extra installs.
- [x] I2C bus 1 shows address `29`.
- [x] Real adapter health reports ready.
- [x] One real distance is positive, below 8190, and physically plausible.
- [x] Ten repeated real distances respond to target movement.
- [x] A new process reinitializes and closes the sensor successfully.
- [x] `8191 mm`, if observed, is rejected rather than reported as success.
- [x] No actuator, display, camera, or microphone is operated.

## 9. Rollback steps

1. Stop running CLI commands with `Ctrl+C`.
2. No actuator cleanup is needed. Each command closes its I2C handle in a
   `finally` block, including after a structured failure.
3. If the sensor or bus is stuck, shut down with `sudo poweroff`, wait until
   activity stops, remove power for 30 seconds, and power on again.
4. Preserve the ledger if investigation is needed. Otherwise remove only the
   explicit test ledger:

   ```bash
   rm -f /tmp/ninjarobot-phase2-manual.sqlite3
   ```

5. Recheck driver integrity:

   ```bash
   uv run --frozen python scripts/verify_immutable_drivers.py
   ```

Do not use `git reset --hard`; it can destroy unrelated local work.
