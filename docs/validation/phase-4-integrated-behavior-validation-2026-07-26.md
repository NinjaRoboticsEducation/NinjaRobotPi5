# Phase 4 Integrated Behavior Raspberry Pi Validation

Status: software PASS; physical Raspberry Pi validation pending

## 1. Scope

This checklist validates the Phase 4 behavior catalog, coordinated display and
buzzer expressions, GPIO12/GPIO13 continuous wheel movement, VL53L0X obstacle
guard, stop levels, private action creation, and `ninjarobot-ide-tool`.

The expected hardware is:

- Raspberry Pi 5
- left MG90D continuous-rotation motor on GPIO12
- right MG90D continuous-rotation motor on GPIO13
- both servo red wires on the DFR0566 D12/D13 `+` terminals
- forward-facing VL53L0X at I2C address `0x29`
- passive buzzer on GPIO27
- ST7789V display on SPI0, DC GPIO4, reset GPIO5, backlight GPIO6, rotation
  90°, brightness 75%

No camera image or microphone audio is captured in this checklist.

## 2. Safety

Do not start with the wheels touching the floor. Raise the robot so both wheels
can rotate freely. Keep hair, cables, fingers, clothing, and tools away from
the wheels.

The reported robot has no accessible physical servo-power disconnect. This is
a known residual risk. Software stop, obstacle monitoring, and the watchdog
cannot guarantee recovery from every electrical, operating-system, or hardware
failure.

Use two terminals. Keep Terminal B ready for:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior stop
```

Never connect, disconnect, or move wiring while power is on. Do not
intentionally create undervoltage, unplug the distance sensor, freeze the
operating system, or cause a driver fault for testing.

## 3. Safe smoke tests

### Step 1: Install and validate the workspace

From the project root:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen --extra hardware

uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen pytest -q
```

Expected: driver verification says PASS and all tests pass.

### Step 2: Create a private configuration

```bash
mkdir -p "$HOME/.config/ninjarobot_pi5"
install -m 600 \
  config/ninjarobot_pi5.toml.example \
  "$HOME/.config/ninjarobot_pi5/config.toml"

export PHASE4_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
```

You can preview existing standalone settings before editing:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" config discover

uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" config import
```

The import command above is preview-only. Do not use `--apply` unless every pin
and path in the preview is correct.

Edit the private file:

```bash
nano "$PHASE4_CONFIG"
```

Keep these movement gates `false` for the smoke tests:

```toml
motion_enabled = false
group_motion_enabled = false
```

Validate it:

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$PHASE4_CONFIG"
```

Expected: the configuration is valid.

### Step 3: Inspect the behavior catalog

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior list

uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior show greeting

uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior health
```

Expected:

- the seven expressions and four movements are listed
- greeting contains a happy-face stage followed by a text-and-melody stage
- simulated display, buzzer, servo, and distance components report `ready`

### Step 4: Simulate every bundled behavior

```bash
for action in idle greeting happy thinking success warning error; do
  uv run --frozen ninjarobot-ide-tool \
    --config "$PHASE4_CONFIG" behavior simulate "$action"
done

for action in move_forward move_backward turn_right turn_left; do
  uv run --frozen ninjarobot-ide-tool \
    --config "$PHASE4_CONFIG" behavior simulate "$action" \
    --duration 1
done
```

Expected:

- every result says `"simulated": true`
- no physical display, buzzer, servo, or sensor reacts
- each movement reports `movement_duration_complete`
- forward resolves to GPIO12 `45` and GPIO13 `-45`
- backward resolves to GPIO12 `-30` and GPIO13 `30`
- right resolves to `45/45`; left resolves to `-45/-45`

### Step 5: Create and inspect a private expression

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior create \
  --name my_success \
  --description "Celebrate a completed task." \
  --face success \
  --melody exciting \
  --confirm-save

uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior show my_success
```

Expected: the action simulates before saving, then appears under
`~/.config/ninjarobot_pi5/behaviors/my_success.json`. Running the create command
again without `--overwrite` must refuse to replace it.

## 4. Communication/interface tests

### Step 1: Verify interfaces and PWM overlay

```bash
ls -l /dev/i2c-1 /dev/spidev0.0
sudo i2cdetect -y 1
pinctrl get 12
pinctrl get 13
```

Expected:

- I2C bus 1 and SPI0 device 0 exist
- `0x10` and `0x29` appear in the I2C scan
- GPIO12 and GPIO13 report their configured hardware-PWM alternate functions

### Step 2: Review both servo calibrations without moving

```bash
uv run --directory pi5servo --frozen --extra pi \
  pi5servo calib --show \
  --config "$HOME/.config/pi5servo/servo.json"
```

Expected: `gpio12` and `gpio13` both have explicit saved calibrations and a
verified neutral center. If either is absent, stop here and use the standalone
calibration tool with the same explicit file:

```bash
uv run --directory pi5servo --frozen --extra pi \
  pi5servo servo-tool \
  --config "$HOME/.config/pi5servo/servo.json"
```

Running `uv run pi5servo servo-tool` without `--config` stores `servo.json` in
the current directory instead. It does not populate the private file above.

### Step 3: Run safe real health probes

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" hardware status --real

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior health --real
```

Expected: display, buzzer, servo, distance, camera, and microphone report ready.
The display may light briefly. No motor moves, no tone plays, and no media is
captured.

### Step 4: Run physical expressions

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run greeting --real

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run warning --real
```

Expected:

- greeting shows a happy face for about two seconds
- `Nice to meet you` and the existing happy melody then begin together
- warning shows the warning face and plays the existing surprising melody
- the wheels do not move

## 5. Actuator-moving tests

Continue only with the wheels raised and Terminal B ready.

### Step 1: Enable only the approved two-wheel group

Edit the private configuration:

```bash
nano "$PHASE4_CONFIG"
```

Set:

```toml
[hardware.servos]
endpoints = ["gpio12", "gpio13"]
calibration_file = "~/.config/pi5servo/servo.json"
motion_enabled = true
group_motion_enabled = true

[behaviors.servo_roles]
left_motor = "gpio12"
right_motor = "gpio13"
```

Validate again:

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$PHASE4_CONFIG"
```

### Step 2: Check the explicit confirmation gate

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run move_forward --real
```

Expected: the tool refuses before movement and says
`real movement requires --confirm-motion`.

### Step 3: Test stop from a second terminal

In Terminal A, keep the front sensor aimed at clear space beyond 100 mm:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run move_forward \
  --real --confirm-motion
```

After one or two seconds, run in Terminal B:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior stop
```

Expected:

- Terminal B reports that stop was requested
- both motors stop
- the buzzer is silent
- ranging, camera, and microphone services close
- the display shows `SYSTEM STOPPED`
- starting the tool again is allowed because operator stop is not a persistent
  driver-failure latch
- Terminal A prints the Level 2 result with `"reason": "ctrl_c"` and
  `"cleanup_errors": []`, followed by `Aborted!`
- neither terminal prints `Exception ignored`, `TypeError`, or another Python
  traceback

`Aborted!` is normal here: it means Terminal B interrupted the foreground
behavior. A PWM (pulse-width modulation) destructor traceback is not normal;
record the complete output and stop physical validation if one appears.

### Step 4: Verify front-obstacle Level 1 stop

Start forward movement again. After it starts, place a flat target closer than
100 mm in front of the sensor without touching the robot:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run move_forward \
  --real --confirm-motion
```

Expected: one or two low samples do not stop motion, but three consecutive low
samples stop both motors. A second movement must report that motion is latched.

Remove the target, verify clear space, and resume:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" motion resume --confirm
```

Expected: the Level 1 latch clears. Display, buzzer, and sensors did not need a
full restart.

### Step 5: Test the other direction maps

Run one command at a time in Terminal A. Stop each from Terminal B after one or
two seconds:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run move_backward \
  --real --confirm-motion

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run turn_right \
  --real --confirm-motion

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run turn_left \
  --real --confirm-motion
```

Expected:

- backward visibly warns that the rear is unprotected
- turns visibly warn that the side and rear are unprotected
- the observed wheel directions match the approved command map
- every stop zeros both servo outputs

If a wheel turns the wrong way, stop immediately. Do not change bundled assets.
Correct the private logical role mapping only after confirming which physical
motor is connected to each GPIO.

## 6. Expected outcomes

Phase 4 physically passes when:

- all safe smoke and real interface probes pass
- greeting timing and concurrent text/sound are visibly correct
- each wheel direction matches the approved map
- forward movement does not begin without three clear valid readings
- three consecutive obstacle readings stop both motors
- Level 1 blocks movement until confirmed resume
- Ctrl+C or `behavior stop` performs full cleanup
- no camera image or microphone recording is produced
- all managed-driver hashes still pass afterward

Do not intentionally validate undervoltage, watchdog freeze, or driver failure
on powered hardware. Their deterministic automated tests are the acceptance
evidence.

## 7. Pass/fail checklist

- [ ] Locked hardware environment installs
- [ ] Immutable-driver verification passes before testing
- [ ] Private configuration validates
- [ ] Behavior list, show, and simulated health pass
- [ ] All seven expressions simulate
- [ ] All four movements simulate with exact endpoint targets
- [ ] Private action preview, save, no-overwrite, and show pass
- [ ] I2C, SPI, GPIO12 PWM, and GPIO13 PWM checks pass
- [ ] GPIO12 and GPIO13 calibrations exist and neutral is verified
- [ ] Safe real hardware status passes without motion or recording
- [ ] Greeting face, text, and melody timing passes
- [ ] Real movement refuses without `--confirm-motion`
- [ ] Cross-terminal full stop passes
- [ ] Cross-terminal stop produces no ignored exception or Python traceback
- [ ] Three-reading front-obstacle stop passes
- [ ] Level 1 confirmed resume passes
- [ ] Backward warning and direction pass
- [ ] Left and right turn warnings and directions pass
- [ ] No unexpected media file is created
- [ ] Immutable-driver verification passes after testing

Overall result: **PENDING**

## 8. Rollback

First request full stop:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior stop
```

If movement is latched and the problem is understood:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" motion resume --confirm
```

If driver failure is latched, do not clear it until the fault is corrected.
Then start a fresh process:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" system resume --confirm
```

To disable further physical integrated motion, edit the private configuration:

```toml
motion_enabled = false
group_motion_enabled = false
```

To remove a private test action:

```bash
rm -- "$HOME/.config/ninjarobot_pi5/behaviors/my_success.json"
```

Power down before touching wiring:

```bash
sudo poweroff
```

After the Pi is fully off, inspect power, common ground, signal routing, sensor
alignment, and mechanical clearance. Finally rerun:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
```
