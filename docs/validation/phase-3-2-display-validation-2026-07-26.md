# Phase 3.2 ST7789V display validation report

Date: 2026-07-26

Hardware accessed during implementation: No

Physical Raspberry Pi result: **PASS** (operator reported)

## 1. Scope of validation

This report covers `display.show_text`, `display.clear`, and
`display.set_brightness`; their shared lifecycle and SPI serialization;
simulation; explicit real access; bounded arguments; durable action results;
and backlight/SPI cleanup.

The target is the 240×320 ST7789V display on Raspberry Pi SPI0 device 0:

- CE0/CS: GPIO8
- MOSI/SDA: GPIO10
- SCLK/SCL: GPIO11
- DC: GPIO4
- reset: GPIO5
- backlight/BLK: GPIO6
- rotation: 90°
- initial brightness: 75%

CE0 means chip enable 0, which selects the display. MOSI means
controller-to-display data. SCLK means serial clock. DC selects whether a byte
is a display command or display data.

Automated result: **PASS**

- Root/V4 tests: 66 passed.
- Strict mypy type checking: passed for 20 source files.
- Focused display and CLI tests: 19 passed.
- Managed-library tests: 449 passed, with one inherited `audioop` deprecation
  warning from `pi5mic`.
- Every managed-library Ruff lint and formatting check passed.
- Compilation, Ruff lint, Ruff formatting, dependency lock, CLI smoke, and
  `git diff --check`: passed.
- Driver provenance: 222 tracked files and 23 authorized repairs, unchanged.

The operator subsequently reported that the complete checklist passed. The
provided transcript confirms successful real red and blue clears, centered
multiline text at 320×240 with rotation 90 and brightness 75, and backlight
changes to 25% and 75%. Every attached action reported `simulated: false`,
`status: succeeded`, and `retry_safety: safe`. The transcript contains the red
command twice and does not contain the green command's JSON result; green is
therefore recorded as an operator-confirmed visual pass rather than an attached
machine-output result.

## 2. Safety notes

Commands do not touch the real display unless `--real` is present. A real
command resets the panel and may energize the backlight. Even `display health
--real` constructs the driver, sets 75% brightness, and may briefly light the
screen before cleanup.

Before powering the Pi:

1. Identify the exact display-board revision.
2. Check its printed or manufacturer-specified supply and logic voltage. Do
   not guess whether its VCC input accepts 3.3 V or 5 V.
3. Confirm VCC, ground, CE0/CS, MOSI/SDA, SCLK/SCL, DC, reset, and backlight
   wires one by one.
4. Confirm the Pi and display share ground.
5. Keep a safe way to disconnect display power within reach.

Do not connect, remove, or move wires while the Raspberry Pi is powered.

## 3. Safe smoke tests

Start at the project root. These commands use simulation only:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen

PHASE32_LEDGER="$(mktemp /tmp/ninjarobot-phase32-XXXXXX.sqlite3)"
echo "$PHASE32_LEDGER"

uv run --frozen ninjarobot_pi5_cli capabilities
uv run --frozen ninjarobot_pi5_cli display health \
  --ledger "$PHASE32_LEDGER"
uv run --frozen ninjarobot_pi5_cli display text \
  --ledger "$PHASE32_LEDGER" \
  --text "NinjaRobot Phase 3.2" \
  --font-size 24 \
  --foreground "#FFFFFF" \
  --background "#000040" \
  --action-id phase32-sim-text-1 \
  --idempotency-key phase32-sim-text-key-1
uv run --frozen ninjarobot_pi5_cli display brightness \
  --ledger "$PHASE32_LEDGER" \
  --percent 25 \
  --action-id phase32-sim-brightness-1 \
  --idempotency-key phase32-sim-brightness-key-1
uv run --frozen ninjarobot_pi5_cli display clear \
  --ledger "$PHASE32_LEDGER" \
  --color "#000000" \
  --action-id phase32-sim-clear-1 \
  --idempotency-key phase32-sim-clear-key-1
```

Expected:

- capabilities include all three `display.*` entries
- overall health is `ready`
- all three actions have status `succeeded`
- each action reports `"simulated": true`
- text reports width 320, height 240, rotation 90, and brightness 75
- every successful action reports `retry_safety: safe`
- the physical screen does not change

## 4. Communication/interface tests

Only continue after the wiring and voltage checks in Section 2 are complete.

Enable SPI through Raspberry Pi configuration if it is not already enabled:

```bash
sudo raspi-config
```

Choose **Interface Options**, then **SPI**, then enable it. Reboot if the tool
asks you to. SPI is the clocked data interface used by this display.

After reboot:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen --extra hardware
PHASE32_LEDGER="${PHASE32_LEDGER:-$(mktemp /tmp/ninjarobot-phase32-XXXXXX.sqlite3)}"
echo "$PHASE32_LEDGER"

uv run --frozen ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example
ls -l /dev/spidev0.0
pinctrl get 4
pinctrl get 5
pinctrl get 6
pinctrl get 8
pinctrl get 10
pinctrl get 11
```

Expected: configuration reports `display=DC4/RST5/BL6`, rotation 90, and
brightness 75%. `/dev/spidev0.0` exists. GPIO8/GPIO10/GPIO11 should have the
SPI0 pin function; GPIO4/GPIO5/GPIO6 must not be owned by an unexpected
process or conflicting function.

Run the real readiness check:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli display health \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE32_LEDGER"
```

Expected: every display component and overall health report `ready`. The panel
may reset or briefly light at 75%. The command does not intentionally write a
test frame, and cleanup turns the backlight off when the command exits.

## 5. Actuator-moving and power-risk tests

There is no moving actuator in this subphase. The following visual tests do
energize the display and backlight. Stop immediately if the board becomes hot,
smells unusual, flickers severely, or the Pi reports undervoltage.

Show red, green, and blue frames one at a time:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli display clear \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE32_LEDGER" \
  --color "#FF0000" \
  --hold 3

uv run --frozen --extra hardware ninjarobot_pi5_cli display clear \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE32_LEDGER" \
  --color "#00FF00" \
  --hold 3

uv run --frozen --extra hardware ninjarobot_pi5_cli display clear \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE32_LEDGER" \
  --color "#0000FF" \
  --hold 3
```

Expected: each color fills the display evenly for about three seconds. The
backlight turns off after each command because the CLI closes the driver.

Show the orientation and text frame:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli display text \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE32_LEDGER" \
  --text $'NinjaRobot\nTOP' \
  --font-size 32 \
  --foreground "#FFFFFF" \
  --background "#000040" \
  --hold 5 \
  --action-id phase32-real-text-1 \
  --idempotency-key phase32-real-text-key-1
```

Expected: white centered text appears on a dark-blue background, the word
`TOP` is readable in the intended landscape orientation, status is
`succeeded`, and data reports `"simulated": false`.

Check backlight levels:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli display brightness \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE32_LEDGER" \
  --percent 25 \
  --hold 3

uv run --frozen --extra hardware ninjarobot_pi5_cli display brightness \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE32_LEDGER" \
  --percent 75 \
  --hold 3
```

Expected: 25% is visibly dimmer than 75%. The driver turns the backlight off
after each command exits.

## 6. Expected outcomes

- Simulation imports no `pi5disp` hardware backend and opens no GPIO or SPI.
- Real construction uses SPI0 device 0 and the exact configured control pins.
- Rotation 90 changes the drawable area from 240×320 to 320×240.
- Text, colors, font size, and brightness are validated before display writes.
- Oversized text is rejected instead of being silently clipped.
- All display operations share the same resource locks and cannot overlap.
- Repeating the same action ID returns the stored result without writing twice.
- Each CLI command closes SPI and turns off the backlight.
- No buzzer, servo, distance sensor, camera, or microphone is operated.

## 7. Pass/fail checklist

- [x] Display-board voltage and wiring record is complete.
- [x] Hardware-free capability listing passes.
- [x] Simulated health reports ready.
- [x] Simulated text, brightness, and clear report `simulated: true`.
- [x] Hardware dependency installs.
- [x] SPI is enabled and `/dev/spidev0.0` exists.
- [x] Configuration reports DC4/RST5/BL6, rotation 90, and brightness 75%.
- [x] Real health reports ready.
- [x] Red frame is even and correctly colored.
- [x] Green frame is even and correctly colored (operator reported).
- [x] Blue frame is even and correctly colored.
- [x] Text is centered, readable, and in the intended orientation.
- [x] 25% brightness is dimmer than 75%.
- [x] Backlight turns off after every CLI command.
- [x] No GPIO conflict, heat, smell, severe flicker, or undervoltage occurs.
- [x] No buzzer, servo, sensor, camera, or microphone is operated.

## 8. Rollback steps

1. Stop the current command with `Ctrl+C`.
2. If the backlight remains on, run:

   ```bash
   uv run --frozen --extra hardware ninjarobot_pi5_cli display brightness \
     --real \
     --config config/ninjarobot_pi5.toml.example \
     --ledger "$PHASE32_LEDGER" \
     --percent 0
   ```

3. If software cannot turn the backlight off, use the prepared display-power
   disconnect.
4. Shut down with `sudo poweroff` before inspecting or changing wiring.
5. After restart, verify `/dev/spidev0.0` and the six GPIO assignments again.
6. Recheck managed-driver integrity:

   ```bash
   uv run --frozen python scripts/verify_immutable_drivers.py
   ```

Do not continue to servo Phase 3.3 until this checklist is run and reviewed.
