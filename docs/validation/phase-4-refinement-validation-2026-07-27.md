# Phase 4 Refinement Raspberry Pi Validation

Status: software PASS; refined physical validation pending

## 1. What this checklist tests

This checklist tests the 2026-07-27 Phase 4 refinements:

- all 20 embedded animated faces
- matching buzzer melodies
- the four normal wheel movements without buzzer sound
- Greeting, Celebrate, Error Warning, Emergency Stop, and Resume
- the redesigned direct-control `ninjarobot-ide-tool`
- private behavior creation, simulation, running, and deletion
- the VL53L0X clear-space rule for exact raw `8191` samples
- the red Emergency Stop display and module reconstruction on Resume

The expected robot has:

- left MG90D 360-degree continuous-rotation servo on GPIO12
- right MG90D 360-degree continuous-rotation servo on GPIO13
- forward-facing VL53L0X distance sensor at I2C address `0x29`
- passive buzzer on GPIO27
- ST7789V 320×240 display on SPI0 device 0, DC GPIO4, reset GPIO5,
  backlight GPIO6, rotation 90°, and brightness 75%

GPIO means general-purpose input/output. PWM means pulse-width modulation, the
timed electrical signal used to control a servo. I2C is the two-wire sensor
bus. SPI is the clocked display connection.

No photograph or microphone recording is taken by this checklist.

## 2. Safety before you begin

Complete Sections 3 through 5 before enabling wheel movement.

For every actuator-moving test:

1. Raise the robot so both wheels can spin without touching the floor.
2. Keep hair, fingers, clothing, tools, and cables away from both wheels.
3. Keep a second terminal open at the project root.
4. Be ready to press `E` in the interactive tool or run this in Terminal B:

   ```bash
   uv run --frozen --extra hardware ninjarobot-ide-tool \
     --config "$PHASE4_CONFIG" behavior stop
   ```

The reported robot has no accessible physical servo-power cutoff. That is a
known residual risk. Software stop cannot recover from every electrical,
operating-system, or hardware failure.

Do not deliberately create undervoltage, freeze the Raspberry Pi, disconnect a
powered sensor, or cause a driver failure. Automated tests cover those paths.

## 3. Safe smoke tests — no hardware activity

### Step 1: Install the locked workspace

From the project root:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen --extra hardware

uv run --frozen --extra hardware python \
  scripts/verify_workspace_driver_sources.py
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen pytest -q
```

Expected:

- all six managed libraries resolve inside this checkout
- immutable-driver verification reports 222 tracked files and 25 authorized
  repairs
- the root test result is `213 passed`

Stop if any package resolves to a copied file under `.venv`, any immutable
hash fails, or any test fails.

### Step 2: Select the private robot configuration

Use the private file that passed the original Phase 4 validation:

```bash
export PHASE4_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
test -f "$PHASE4_CONFIG"
chmod 600 "$PHASE4_CONFIG"

uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$PHASE4_CONFIG"
```

Expected: `test` produces no output, and configuration validation succeeds.

For Sections 3 through 5, keep these two values `false`:

```toml
motion_enabled = false
group_motion_enabled = false
```

### Step 3: Inspect the complete bundled catalog

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior list

uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior show greeting

uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior show celebrate
```

Expected:

- the 20 face names are present: `idle`, `happy`, `laughing`, `sad`, `cry`,
  `angry`, `surprising`, `sleepy`, `speaking`, `shy`, `scary`, `exciting`,
  `confusing`, `greeting`, `listening`, `thinking`, `curious`, `success`,
  `warning`, and `error`
- `move_forward`, `move_backward`, `turn_left`, and `turn_right` are present
- `celebrate` and `error_warning` are present
- extra private names are allowed
- `emergency_stop` is not an asset
- Greeting starts its greeting face and Happy melody together, then shows
  `Nice to meet you`
- Celebrate contains a short guarded movement and therefore requires real
  movement confirmation

### Step 4: Simulate every bundled action

```bash
BUNDLED_ACTIONS="\
angry confusing cry curious error error_warning exciting greeting happy idle \
laughing listening sad scary shy sleepy speaking success surprising thinking \
warning celebrate move_backward move_forward turn_left turn_right"

for action in $BUNDLED_ACTIONS; do
  uv run --frozen ninjarobot-ide-tool \
    --config "$PHASE4_CONFIG" behavior simulate "$action" \
    --duration 0.2
done
```

Expected:

- every command succeeds and reports `"simulated": true`
- no physical display, buzzer, servo, or sensor reacts
- every continuous simulated movement ends with
  `"stop_reason": "movement_duration_complete"`
- normal movements contain no melody operation

Test the new scriptable face loop in bounded simulation:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run happy \
  --loop --duration 0.5
```

Expected: the result completes, reports multiple face frames, and remains
simulated.

## 4. Interactive menu test — still no hardware activity

Launch without the hardware extra for this section:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG"
```

Check these items without selecting a real behavior:

1. Choose **Hardware Configurations**.
2. Choose **Show Current Configuration**.
3. Confirm GPIO12/GPIO13, GPIO27, the display pins, calibration file, logical
   roles, and 100 mm obstacle threshold.
4. Press Enter, then choose **Back**.
5. Choose **Run Robot Behaviors** and inspect Face Expressions, Robot
   Movements, and Special Behaviors.
6. Confirm each submenu has **Back** and the red **E. EMERGENCY STOP** hint.
7. Return to the main menu.
8. Enter **Create Robot Behavior** and read its example.
9. Choose **Back** without creating anything.
10. Enter **Simulation**, select `happy`, wait for its result, then choose
    **Back**.
11. Choose **Quit**.

Expected:

- the seven approved main choices are shown
- all descriptions are understandable
- selections execute instead of printing commands to copy
- no physical module reacts during the Simulation selection
- Back always returns to the previous menu
- Quit exits cleanly without `Error: 0` or a Python traceback

## 5. Create, simulate, and delete a private behavior

Launch the interactive tool again and choose **Create Robot Behavior**. Use
this example:

1. Behavior name: `validation_happy`
2. Description: `Validate the guided creator.`
3. Display output: `face`
4. Face expression: `happy`
5. Add a buzzer melody: `yes`
6. Melody: `happy`
7. Volume: `40`
8. Add wheel-servo movement: `no`
9. Review the hardware-free preview.
10. Save the private behavior: `yes`

Return to the main menu and:

1. Choose **Simulation**.
2. Select `validation_happy`.
3. Confirm the preview succeeds without physical output.
4. Return and choose **Delete User-Created Behaviors**.
5. Select `validation_happy`.
6. Confirm deletion.

Expected:

- the preview happens before the save question
- the file is owner-private under
  `~/.config/ninjarobot_pi5/behaviors/`
- the behavior appears in the user-created lists
- deletion never offers or removes a bundled behavior

## 6. Non-moving real device tests

### Step 1: Review calibration without moving

```bash
env -u VIRTUAL_ENV uv run --directory pi5servo --frozen --extra pi \
  pi5servo calib --show \
  --config "$HOME/.config/pi5servo/servo.json"
```

`env -u VIRTUAL_ENV` removes only the inherited environment marker for this
command. It prevents `uv` from warning that the root environment differs from
the standalone `pi5servo` environment.

Expected: both `gpio12` and `gpio13` have explicit calibration records and
verified neutral centers. If the command says `No calibrations stored`, stop
and calibrate those exact endpoints with:

```bash
env -u VIRTUAL_ENV uv run --directory pi5servo --frozen --extra pi \
  pi5servo servo-tool \
  --config "$HOME/.config/pi5servo/servo.json"
```

### Step 2: Check interfaces

```bash
ls -l /dev/i2c-1 /dev/spidev0.0
sudo i2cdetect -y 1
pinctrl get 12
pinctrl get 13
```

Expected:

- I2C bus 1 and SPI0 device 0 exist
- I2C addresses `0x10` and `0x29` appear
- GPIO12 and GPIO13 report the configured hardware-PWM alternate functions

### Step 3: Run safe health probes

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" hardware status --real

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior health --real
```

Expected: configured components report ready. The display may initialize. No
wheel moves, no melody plays, and no media is captured.

## 7. Real animated faces and direct menu control

Keep movement disabled. Launch:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG"
```

Choose **Run Robot Behaviors → Face Expressions**.

Test the faces one by one. At minimum, observe each for two animation cycles:

1. Happy
2. Idle
3. Laughing
4. Sad
5. Cry
6. Angry
7. Surprising
8. Sleepy
9. Speaking
10. Shy
11. Scary
12. Exciting
13. Confusing
14. Thinking
15. Curious

Expected for every choice:

- the selected face starts immediately
- the related melody plays once
- the face keeps animating while the menu waits
- choosing another face replaces the current face
- no wheel moves

Choose Back twice, then Quit. Expected: active animation and sound stop, all
opened devices close, and no traceback appears.

The other five embedded faces—Greeting, Listening, Success, Warning, and
Error—remain available through scriptable catalog actions and special
combinations. Safely test them one at a time:

```bash
for face in greeting listening success warning error; do
  uv run --frozen --extra hardware ninjarobot-ide-tool \
    --config "$PHASE4_CONFIG" behavior run "$face" --real
done
```

## 8. Emergency Stop sign and Resume

Launch the interactive tool and press `E` at the main menu.

Expected:

- Level 2 cleanup reports no cleanup errors
- both servo outputs are stopped
- distance, camera, and microphone boundaries close
- the buzzer is silent
- the display shows a red octagonal STOP sign, `SYSTEM STOPPED`, and the
  Resume instruction
- the sign remains while the menu is waiting

Choose **Run Robot Behaviors → Special Behaviors → Resume Robot Movement** and
confirm the health checks.

Expected:

- stopped device boundaries are reconstructed
- all required configured health checks pass
- both safety levels clear
- Idle begins animating
- no previous behavior or wheel movement restarts

If any health check fails, the resume must refuse, the system remains stopped,
and the Emergency Stop sign remains. Fix that device before trying again.

## 9. Actuator-moving tests

Continue only with both wheels raised and Terminal B ready.

### Step 1: Enable only the approved wheel pair

Edit the private configuration:

```bash
nano "$PHASE4_CONFIG"
```

Confirm:

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

Validate:

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$PHASE4_CONFIG"
```

### Step 2: Test forward startup in clear space

Launch the interactive tool, then choose:

**Run Robot Behaviors → Robot Movements → Move Forward**

Confirm real movement only after checking the raised wheels.

Expected:

- three measured samples above 100 mm permit startup
- three exact out-of-range samples represented internally by raw `8191` also
  permit startup without a display warning
- a generic null caused by I2C communication failure, timeout, disconnect, or
  stale data does not permit startup
- the Happy face animates
- no buzzer melody plays
- GPIO12 receives `+45` and GPIO13 receives `-45`

Do not unplug the sensor to manufacture a null result. Automated tests are the
acceptance evidence for that unsafe fault path.

Choose Back. Expected: both wheel outputs return to neutral/zero and the
movement stops.

### Step 3: Test the three-reading front obstacle stop

Start Move Forward again. After it starts, place a flat target closer than
100 mm in front of the sensor without touching the robot.

Expected:

- one or two low readings do not stop movement
- the third consecutive measured reading at or below 100 mm produces a Level
  1 stop
- both wheels stop
- another movement is refused while motion remains latched

Remove the target. Choose:

**Back → Special Behaviors → Resume Robot Movement**

Expected: the Level 1 latch clears after confirmation, Idle appears, and the
stopped forward movement does not restart.

### Step 4: Test the remaining direction maps

Return to Robot Movements and test one at a time:

- Move Backward: GPIO12 `-30`, GPIO13 `+30`, Warning face
- Turn Left: GPIO12 `-45`, GPIO13 `-45`, Curious face
- Turn Right: GPIO12 `+45`, GPIO13 `+45`, Curious face

Expected:

- no movement behavior plays a buzzer melody
- backward warns that the rear is unprotected
- turns warn that the side and rear are unprotected
- choosing Back stops both outputs every time

If either wheel turns in the wrong direction, press `E` immediately. Do not
edit bundled assets. Recheck the private logical-role mapping and physical
connections after powering down.

### Step 5: Test Celebrate

Choose **Special Behaviors → Celebrate** and confirm its short movement.

Expected:

- Exciting and Success faces animate
- the Exciting melody plays
- the short left/right wheel dance completes
- front monitoring remains active
- both outputs stop at completion

### Step 6: Test Emergency Stop during movement

Start any raised-wheel movement, then press `E` from its menu.

Expected:

- motion stops immediately
- sensors close
- the buzzer is silent
- the Emergency Stop sign stays visible
- Resume performs health checks and does not restart that movement

## 10. Cross-terminal stop test

In Terminal A:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior run happy \
  --real --loop
```

While the face is animating, run in Terminal B:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior stop
```

Expected:

- Terminal B reports `"stop_requested": true`
- Terminal A reports Level 2 cleanup with `"reason": "ctrl_c"`
- no `Exception ignored`, `TypeError`, or Python traceback appears
- sound stops, sensors close, and servo outputs are zero

`Aborted!` in Terminal A is normal because Terminal B intentionally sends
Ctrl+C to the registered process.

## 11. Power-risk tests

Do not intentionally test undervoltage, a frozen event loop, sensor
disconnection, or a real driver crash. The deterministic automated tests are
the acceptance evidence.

During ordinary physical tests, any naturally reported undervoltage or
software-watchdog stop must:

- stop both servo movements
- latch Level 1 motion safety
- require an explicit Resume before another movement

Stop the checklist and investigate the power path if either condition occurs.

## 12. Pass/fail record

- [ ] Locked hardware environment installs
- [ ] All six managed packages resolve into this checkout
- [ ] Immutable-driver verification passes before testing
- [ ] Root suite reports 213 passed
- [ ] Private configuration validates
- [ ] Complete catalog inspection passes
- [ ] All bundled actions simulate without physical activity
- [ ] Scriptable loop is bounded in simulation
- [ ] Main menu and every Back path work
- [ ] Guided create, preview, save, simulation, and delete work
- [ ] Both GPIO servo calibrations exist
- [ ] I2C, SPI, GPIO12 PWM, and GPIO13 PWM checks pass
- [ ] Safe real health probes pass without motion or recording
- [ ] All 15 interactive face choices animate and replace one another
- [ ] Five additional embedded faces run scriptably
- [ ] Emergency Stop sign and cleanup pass
- [ ] Resume reconstructs modules and never restarts prior motion
- [ ] Clear measured distance permits forward startup
- [ ] Exact `8191` clear space permits startup without warning
- [ ] Three low readings produce Level 1 stop
- [ ] Forward, backward, left, and right maps pass with no movement melody
- [ ] Celebrate completes and stops both outputs
- [ ] Emergency Stop during motion passes
- [ ] Cross-terminal stop produces no traceback
- [ ] No photograph or audio file is created
- [ ] Immutable-driver verification passes after testing

Overall result: **PENDING**

## 13. Rollback

First request Level 2 stop:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior stop
```

Disable future physical movement in the private configuration:

```toml
motion_enabled = false
group_motion_enabled = false
```

If a private validation behavior remains, remove it through the CLI:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$PHASE4_CONFIG" behavior delete validation_happy --confirm
```

Power down before touching wiring:

```bash
sudo poweroff
```

After the Pi is fully off, inspect power, common ground, signal routing, sensor
alignment, and mechanical clearance.

Finally, return to the project root and run:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
```
