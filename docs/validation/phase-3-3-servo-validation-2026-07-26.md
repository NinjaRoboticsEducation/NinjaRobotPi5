# Phase 3.3 six-servo validation report

Date: 2026-07-26

Hardware accessed during implementation: No

Physical Raspberry Pi result: **PENDING OPERATOR TEST**

## 1. Scope of validation

This report covers the fixed six-servo topology, mixed `pi5servo` backend,
calibration gate, real-motion configuration gate, one-endpoint movement,
cancellation, emergency all-servo stop, action-ledger behavior, and cleanup.

The fixed topology is:

- `gpio12`: Raspberry Pi RP1 hardware PWM channel 0
- `gpio13`: Raspberry Pi RP1 hardware PWM channel 1
- `hat_pwm1`: DFR0566 physical PWM0
- `hat_pwm2`: DFR0566 physical PWM1
- `hat_pwm3`: DFR0566 physical PWM2
- `hat_pwm4`: DFR0566 physical PWM3

PWM means pulse-width modulation, the timed electrical signal used to control
a servo. RP1 is the Raspberry Pi 5 input/output controller. The DFR0566 is
controlled through I2C bus 1 at address `0x10`; I2C is the board's two-wire
communication bus.

Automated result: **PASS**

- Root/V4 tests: 81 passed.
- Focused servo, configuration, and CLI tests: 30 passed.
- Managed-library tests: 449 passed, with one inherited `audioop` deprecation
  warning from `pi5mic`.
- Every managed-library Ruff lint and formatting check passed.
- Strict mypy type checking: passed for 21 source files.
- Compilation, Ruff lint, Ruff formatting, dependency lock, CLI smoke, and
  `git diff --check`: passed.
- Driver provenance: 222 tracked files and 23 authorized repairs, unchanged.

## 2. Safety notes

Simulation is the default. Real movement requires all of the following:

1. `--real`
2. `--confirm-motion`
3. `motion_enabled = true` in a private V4 TOML configuration
4. a complete calibration for the selected endpoint in
   `~/.config/pi5servo/servo.json`
5. an approved electrical and mechanical safety record

The checked-in example keeps `motion_enabled = false`. Group motion is not
implemented and `group_motion_enabled` must remain false.

Before any powered movement, record:

| Item | Required value |
| --- | --- |
| `gpio12` exact servo model | |
| `gpio12` rated voltage and stall current | |
| `gpio13` exact servo model | |
| `gpio13` rated voltage and stall current | |
| `hat_pwm1` exact servo model | |
| `hat_pwm1` rated voltage and stall current | |
| `hat_pwm2` exact servo model | |
| `hat_pwm2` rated voltage and stall current | |
| `hat_pwm3` exact servo model | |
| `hat_pwm3` rated voltage and stall current | |
| `hat_pwm4` exact servo model | |
| `hat_pwm4` rated voltage and stall current | |
| Selected supply voltage | |
| Supply continuous and peak current | |
| Fuse or current-limiting arrangement | |
| Common-ground connection | |
| Accessible emergency power disconnect | |
| Mechanical workspace and load check | |

Stall current is the highest current a servo can draw when it cannot move.
Do not power a servo from a voltage outside its rating. The DFR0566 external
VP input is documented as 6–12 V and feeds the HAT servo-power rail; never
connect a lower-voltage servo until the complete power path is confirmed safe.

Continuous-rotation servos do not treat an angle as a physical position. The
calibrated center is neutral/stop, while values on either side normally select
direction and speed. Disconnect linkages or lift wheels before the first test.
Keep the power cutoff in reach. Never change wiring while powered.

## 3. Safe smoke tests

These commands are fully simulated:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen

PHASE33_LEDGER="$(mktemp /tmp/ninjarobot-phase33-XXXXXX.sqlite3)"
echo "$PHASE33_LEDGER"

uv run --frozen ninjarobot_pi5_cli capabilities
uv run --frozen ninjarobot_pi5_cli servo health \
  --ledger "$PHASE33_LEDGER"
uv run --frozen ninjarobot_pi5_cli servo status \
  --ledger "$PHASE33_LEDGER"
uv run --frozen ninjarobot_pi5_cli servo move \
  --ledger "$PHASE33_LEDGER" \
  --endpoint gpio12 \
  --angle 10 \
  --speed S \
  --action-id phase33-sim-move-1 \
  --idempotency-key phase33-sim-move-key-1
uv run --frozen ninjarobot_pi5_cli servo stop \
  --ledger "$PHASE33_LEDGER"
```

Expected:

- capabilities include `servo.status`, `servo.move`, and `servo.stop`
- `servo.move` has risk `motion` and requires confirmation
- `servo.stop` has risk `emergency`
- health is `ready`
- status lists all six endpoints and says group motion is false
- every result says `"simulated": true`
- simulated move succeeds with `retry_safety: unsafe`
- stop succeeds with `retry_safety: safe`
- no GPIO, PWM, I2C, or physical servo is accessed

## 4. Communication/interface tests

These tests access interfaces but must not send a servo pulse. Disconnect
external servo power before starting.

Confirm the boot settings in `/boot/firmware/config.txt`:

```ini
dtparam=audio=off
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

Reboot after changing that file. Then run:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen --extra hardware

PHASE33_LEDGER="${PHASE33_LEDGER:-$(mktemp /tmp/ninjarobot-phase33-XXXXXX.sqlite3)}"
echo "$PHASE33_LEDGER"

uv run --frozen ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example
pinctrl get 12
pinctrl get 13
i2cdetect -y 1
```

Expected:

- GPIO12 and GPIO13 report their PWM alternate functions
- I2C address `10` is visible
- the configuration lists all six endpoints
- the example configuration says motion is disabled

Run the non-moving real health and status checks:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli servo health \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE33_LEDGER"

uv run --frozen --extra hardware ninjarobot_pi5_cli servo status \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE33_LEDGER"
```

Expected: health reports `ready`, `driver_available` is true, group motion is
false, and `motion_enabled` is false. Startup claims the two native PWM
channels at zero output, verifies the DFR0566 identity, disables its PWM, and
sets all four HAT duties to zero. No servo should move.

Test both software motion gates while external servo power remains disconnected:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli servo move \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE33_LEDGER" \
  --endpoint gpio12 \
  --angle 0
```

Expected: the CLI exits with an error saying `--confirm-motion` is required.
No pulse is sent.

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli servo move \
  --real \
  --confirm-motion \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE33_LEDGER" \
  --endpoint gpio12 \
  --angle 0
```

Expected: the action fails with `SERVO_MOTION_DISABLED`. No pulse is sent.

## 5. Actuator-moving tests

**Do not run this section until every blank in Section 2 is completed,
reviewed, and approved.**

Calibrate only one endpoint at a time using the standalone library. Calibration
itself sends live pulses and can move the servo:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv run --directory pi5servo --frozen --extra pi pi5servo calib gpio12
```

Replace `gpio12` with the endpoint actually being calibrated. Confirm that the
result is stored in `~/.config/pi5servo/servo.json`. For a
continuous-rotation servo, find a reliable neutral center before testing either
direction.

Create a private V4 configuration:

```bash
mkdir -p "$HOME/.config/ninjarobot_pi5"
cp config/ninjarobot_pi5.toml.example \
  "$HOME/.config/ninjarobot_pi5/ninjarobot_pi5.toml"
nano "$HOME/.config/ninjarobot_pi5/ninjarobot_pi5.toml"
```

Change only:

```toml
motion_enabled = true
```

Keep `group_motion_enabled = false`.

Verify that the selected endpoint reports calibrated:

```bash
SERVO_CONFIG="$HOME/.config/ninjarobot_pi5/ninjarobot_pi5.toml"

uv run --frozen --extra hardware ninjarobot_pi5_cli servo status \
  --real \
  --config "$SERVO_CONFIG" \
  --ledger "$PHASE33_LEDGER"
```

Start with the calibrated center and no mechanical load:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli servo move \
  --real \
  --confirm-motion \
  --config "$SERVO_CONFIG" \
  --ledger "$PHASE33_LEDGER" \
  --endpoint gpio12 \
  --angle 0 \
  --speed S \
  --hold 1 \
  --action-id phase33-real-gpio12-center-1 \
  --idempotency-key phase33-real-gpio12-center-key-1
```

Expected: only `gpio12` receives a pulse, the servo reaches its calibrated
center/neutral state, the result says `"simulated": false`, and cleanup sets
all outputs to zero after one second.

Only if center is correct, test one very small target:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli servo move \
  --real \
  --confirm-motion \
  --config "$SERVO_CONFIG" \
  --ledger "$PHASE33_LEDGER" \
  --endpoint gpio12 \
  --angle 5 \
  --speed S \
  --hold 1 \
  --action-id phase33-real-gpio12-small-1 \
  --idempotency-key phase33-real-gpio12-small-key-1

uv run --frozen --extra hardware ninjarobot_pi5_cli servo stop \
  --real \
  --config "$SERVO_CONFIG" \
  --ledger "$PHASE33_LEDGER"
```

Expected: movement is small and controlled. For continuous rotation, the wheel
may turn slowly instead of moving to a position. Stop and engine cleanup set
all six pulse outputs to zero.

Return the endpoint to center with a new action ID. Repeat the complete
center/small-target/stop sequence separately for each remaining endpoint. Do
not test two servos together.

## 6. Expected outcomes

- Simulation never imports or opens `pi5servo` hardware backends.
- Real health opens GPIO12/GPIO13 hardware PWM and DFR0566 at zero duty only.
- Status reports calibration and safety gates without sending a center pulse.
- Real movement requires two explicit software gates and a valid calibration.
- A move always sends the selected calibrated center before its target.
- Only one endpoint moves in each action.
- There is no group-motion capability.
- Invalid endpoint, angle, speed, calibration, or configuration never sends a
  pulse.
- Repeating an action ID returns its stored result without moving twice.
- Cancellation and emergency stop abort movement and set all outputs to zero.
- Engine close releases both PWM channels and the DFR0566 I2C handle.
- No buzzer, display, distance sensor, camera, or microphone is operated.

## 7. Pass/fail checklist

- [ ] Six-servo electrical record in Section 2 is complete and approved.
- [ ] Emergency power disconnect is accessible and tested.
- [ ] Simulation health, status, move, and stop pass.
- [ ] Hardware dependency installs.
- [ ] GPIO12/GPIO13 report the correct PWM alternate functions.
- [ ] DFR0566 appears at I2C address `0x10`.
- [ ] Real health passes with external servo power disconnected.
- [ ] Real status reports all six endpoints and group motion false.
- [ ] Missing `--confirm-motion` blocks movement.
- [ ] Example configuration blocks movement.
- [ ] Every endpoint has a reviewed explicit calibration.
- [ ] `gpio12` center, small move, return, stop, and cleanup pass.
- [ ] `gpio13` center, small move, return, stop, and cleanup pass.
- [ ] `hat_pwm1` center, small move, return, stop, and cleanup pass.
- [ ] `hat_pwm2` center, small move, return, stop, and cleanup pass.
- [ ] `hat_pwm3` center, small move, return, stop, and cleanup pass.
- [ ] `hat_pwm4` center, small move, return, stop, and cleanup pass.
- [ ] Only the selected servo moves during every test.
- [ ] Cancellation or `servo stop` sets every output to zero.
- [ ] No heat, smell, severe jitter, undervoltage, or unexpected movement occurs.
- [ ] No group movement was attempted.

## 8. Rollback steps

1. Run the emergency command if the CLI is still responsive:

   ```bash
   uv run --frozen --extra hardware ninjarobot_pi5_cli servo stop \
     --real \
     --config "$SERVO_CONFIG" \
     --ledger "$PHASE33_LEDGER"
   ```

2. If motion continues, use the physical servo-power disconnect immediately.
3. Shut down with `sudo poweroff` before touching wiring.
4. Restore `motion_enabled = false` in the private V4 configuration.
5. Inspect the selected endpoint's calibration and power rating before retrying.
6. After reboot, confirm GPIO12/GPIO13, I2C `0x10`, and zero-output health.
7. Recheck managed-driver integrity:

   ```bash
   uv run --frozen python scripts/verify_immutable_drivers.py
   ```

Do not continue to camera Phase 3.4 until this checklist is reviewed.
