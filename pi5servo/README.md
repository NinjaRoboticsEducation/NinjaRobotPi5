# pi5servo

<div align="center">

**Velocity-Based Servo Control and Calibration Tools for Raspberry Pi 5**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Raspberry Pi 5](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/)

Standalone Raspberry Pi 5 library — see [Installation](#installation) and
[CLI Commands](#cli-commands) below.

</div>

---

**Velocity-based servo control library for Raspberry Pi 5**

A lightweight, physics-based servo control library for SG90 and MG90S style servos. `pi5servo` keeps the movement model, calibration flow, command format, and interactive tools from `pi0servo`, but replaces the old `pigpio`-only transport with a Raspberry Pi 5 friendly backend system.

The default target is **header-connected servos on Raspberry Pi 5** using hardware-backed PWM. The library also supports the DFRobot Raspberry Pi IO Expansion HAT (DFR0566) for I2C-managed PWM servo channels, plus an optional `pca9685` backend for other advanced external controller setups.

This is a standalone library. You do not need NinjaRobotPi5 or NinjaClawBot
after you have obtained a complete copy of this `pi5servo` folder.

---

## Contents

- [Connection Models](#connection-models)
- [Endpoint Model](#endpoint-model)
- [Key Features](#key-features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Controller Paths](#controller-paths)
- [Quick Start](#quick-start)
- [Command Format](#command-format)
- [CLI Commands](#cli-commands)
- [Python API](#python-api)
- [Configuration File](#configuration-file)
- [Easing Functions](#easing-functions)
- [Hardware Wiring](#hardware-wiring)
- [License](#license)

---

## Connection Models

`pi5servo` needs to distinguish two different servo signal paths when the DFRobot Raspberry Pi IO Expansion HAT (DFR0566) is involved:

1. **Native GPIO servo**
   - the signal wire is driven by the Raspberry Pi itself
   - this includes a servo plugged directly into the Pi header
   - this also includes a servo plugged into a DFR0566 **digital** port, because those ports are still Raspberry Pi GPIO breakouts

2. **DFR0566 HAT PWM servo**
   - the signal wire is driven by one of the HAT's 4 PWM channels
   - this is a separate MCU-managed path over I2C
   - this is not the same thing as a native GPIO servo

> [!IMPORTANT]
> A DFR0566 **digital** port and a DFR0566 **PWM** port are not interchangeable in software. Digital ports follow the native GPIO path. The dedicated PWM ports follow the `dfr0566` backend path.

## Endpoint Model

`pi5servo` now supports both the old native GPIO shorthand and the new explicit endpoint form:

- `12`, `13`, and similar numeric targets still mean native GPIO shorthand
- `gpio12`, `gpio13`, and similar names are the explicit native GPIO form
- `hat_pwm1`, `hat_pwm2`, `hat_pwm3`, and `hat_pwm4` are the DFR0566 PWM channels

Use the explicit form whenever native GPIO servos and DFR0566 PWM servos appear in the same command or config file.

> [!NOTE]
> The current DFR0566 endpoint names are one-based inside `pi5servo`. That means:
> `hat_pwm1` = physical HAT connector `PWM0`, `hat_pwm2` = `PWM1`, `hat_pwm3` = `PWM2`, and `hat_pwm4` = `PWM3`.
> Each servo must use its own PWM connector if you want independent control.

## Key Features

- **Velocity-based Motion** – Physics calculations (degrees/sec) instead of arbitrary durations
- **100Hz Update Rate** – 10ms step interval for smooth, controlled motion
- **Cubic Easing (Default)** – Uses `ease_in_out_cubic` for natural S-curve acceleration
- **Per-Servo Speed Limits** – Individual speed limits (0-100%) reduce mechanical stress
- **Thread-safe Abort** – Immediately stop any running movement
- **Interactive Tools** – Menu-driven `servo-tool` plus calibration TUI
- **Mixed Endpoint Support** – Native GPIO and `hat_pwm` endpoints can run together in one group
- **Pi 5 Standalone Backends** – `auto`, `hardware_pwm`, `dfr0566`, optional `pca9685`, and legacy `pigpio` compatibility

## Requirements

- Raspberry Pi 5
- Python 3.11 or 3.12
- `uv` for installation and testing
- SG90, MG90S, or similar hobby servo motors
- External 5V servo power supply for real hardware testing

### Supported Header Pins

The native `hardware_pwm` backend has **two independent hardware PWM channels**,
not four. Each channel can appear on one of two alternate header pins:

| Hardware PWM channel | Choose one header pin |
|---|---|
| PWM0 | GPIO12 **or** GPIO18 |
| PWM1 | GPIO13 **or** GPIO19 |

For example, GPIO12 plus GPIO13 is a valid two-servo pair. GPIO18 plus GPIO19
is another valid two-servo pair. GPIO12 and GPIO18 are alternate routes for the
same PWM0 signal, so they must not be used as two independent servo outputs.
The same rule applies to GPIO13 and GPIO19 for PWM1.

> [!IMPORTANT]
> The standard `pwm-2chan` firmware overlay enables two independent outputs
> only. Do not try to configure all four pins as four independent servos.

---

## Installation

### Step 1: Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart the shell after installation, or run:

```bash
source "$HOME/.local/bin/env"
```

### Step 2: Enable Raspberry Pi 5 PWM

Edit `/boot/firmware/config.txt` and enable one of these common overlay setups:

```ini
# GPIO12 and GPIO13
dtparam=audio=off
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

or

```ini
# GPIO18 and GPIO19
dtoverlay=pwm-2chan
```

Reboot after saving the file.

GPIO12/GPIO13 hardware PWM shares resources with Raspberry Pi analog audio.
Disable `dtparam=audio` for this mapping. HDMI, USB, and Bluetooth audio do not
use that legacy analog PWM output.

> [!NOTE]
> `pi5servo` maps GPIO12 and GPIO18 to PWM0, and GPIO13 and GPIO19 to PWM1.
> Select only the pair enabled by your overlay. The library rejects an attempt
> to claim both alternate pins for the same channel, such as GPIO12 and GPIO18.

After rebooting, verify the selected pair without connecting or moving a servo:

```bash
# If you configured GPIO12 and GPIO13
pinctrl get 12
pinctrl get 13

# If you configured GPIO18 and GPIO19
pinctrl get 18
pinctrl get 19
```

Each selected pin should report its PWM alternate function. The two pins that
you did not select should not be treated as extra independent PWM channels.

### Step 2b: Enable I2C If You Will Use DFR0566

If you plan to use the DFR0566 PWM channels, make sure Raspberry Pi I2C is enabled and the HAT appears on bus `1`.

```bash
ls /dev/i2c-1
sudo i2cdetect -y 1
```

Expected result: the DFR0566 appears at `0x10` unless you changed its address.

### Step 3: Obtain and enter the standalone folder

```bash
cd /path/to/pi5servo
```

Ask the project owner for a complete `pi5servo` source folder or source
archive. This README does not require or assume a Git repository URL.

### Step 4: Install with `uv`

```bash
# Install the standalone Raspberry Pi runtime
uv python install 3.11
uv sync --frozen --extra pi
```

For development and testing:

```bash
uv sync --frozen --extra pi --extra dev
```

> [!NOTE]
> `uv sync` creates and manages `.venv` automatically. You do not need to run `uv venv` or activate the environment manually.

### Step 5: Verify Installation

```bash
uv run --frozen pi5servo --help
uv run --frozen pi5servo status --pins 12,13 --no-probe
```

If you want to use the DFR0566 or PCA9685 controller paths, install the same `pi` extra and select the backend on the CLI or in `servo.json`.

## Controller Paths

`pi5servo` can drive servos through three practical standalone paths:

1. **Native Raspberry Pi 5 header PWM**
   - best when you only need a small number of servos
   - good when the servo signal wire goes directly to a Pi PWM-capable GPIO pin
   - no extra controller board is needed

2. **DFRobot IO Expansion HAT (DFR0566)**
   - best when the servo signal wire goes to the HAT's dedicated `PWM0` to `PWM3` connectors
   - good when you already use the DFR0566 for I2C sensor expansion
   - the HAT is controlled over I2C, so `pi5servo` uses the `dfr0566` backend

3. **PCA9685 external PWM controller**
   - best when you need more servo channels than the Pi header or DFR0566 can provide
   - good when you want one dedicated PWM controller for multiple servos
   - the board is controlled over I2C, so `pi5servo` uses the `pca9685` backend

### DFR0566 Use Case

Choose the DFR0566 path when:

- the servo is plugged into the HAT's dedicated `PWM0`, `PWM1`, `PWM2`, or `PWM3` connector
- you want servo signal generation handled by the HAT instead of the Pi header PWM pins
- you are already using the HAT for devices such as the VL53L0X on I2C

Important DFR0566 rules:

- the HAT's **digital** ports are not the same as the HAT's **PWM** ports
- the HAT PWM ports should be treated as a separate controller path
- physical `PWM0` currently maps to `hat_pwm1`
- physical `PWM1` currently maps to `hat_pwm2`
- physical `PWM2` currently maps to `hat_pwm3`
- physical `PWM3` currently maps to `hat_pwm4`
- use external servo power with a common ground to the Pi

Example: one servo on DFR0566 physical `PWM0`

```bash
uv run pi5servo move hat_pwm1 center \
  --backend dfr0566 \
  --address 0x10 \
  --bus-id 1
```

Example: save DFR0566 as the default backend in `servo.json`

```json
{
  "__backend__": {
    "name": "dfr0566",
    "kwargs": {
      "address": 16,
      "bus_id": 1
    }
  },
  "hat_pwm1": {
    "pulse_min": 500,
    "pulse_center": 1500,
    "pulse_max": 2500,
    "speed": 70
  }
}
```

After saving that config, you can use shorter commands:

```bash
uv run pi5servo move hat_pwm1 center
uv run pi5servo calib hat_pwm1
uv run pi5servo servo-tool
```

### PCA9685 Use Case

Choose the PCA9685 path when:

- you need more channels than the Pi header or DFR0566 provides
- you want a dedicated multi-channel servo controller over I2C
- you want to keep the servo signal generation off the Pi itself

With PCA9685, `pi5servo` still uses your normal servo ids in commands, but it needs a channel map to know which servo id belongs to which PCA9685 output.

Example: map logical servo `12` to PCA9685 channel `0`

```bash
uv run pi5servo move 12 45 \
  --backend pca9685 \
  --address 0x40 \
  --channel-map 12:0
```

Example: map two logical servos in `servo.json`

```json
{
  "__backend__": {
    "name": "pca9685",
    "kwargs": {
      "address": 64,
      "channel_map": {
        "12": 0,
        "13": 1
      }
    }
  },
  "gpio12": {
    "pulse_min": 500,
    "pulse_center": 1500,
    "pulse_max": 2500,
    "speed": 80
  },
  "gpio13": {
    "pulse_min": 500,
    "pulse_center": 1500,
    "pulse_max": 2500,
    "speed": 80
  }
}
```

After saving that config, you can run:

```bash
uv run pi5servo move 12 45
uv run pi5servo cmd "12:45/13:-30" --pins 12,13
```

### CLI Versus `servo.json`

Use CLI flags when:

- you are testing hardware for the first time
- you want to try a backend without changing saved settings
- you want a one-off command

Use `servo.json` when:

- you always use the same controller board
- you want shorter daily-use commands
- you want `servo-tool`, `move`, `cmd`, and `calib` to reuse the same backend settings automatically

---

## Quick Start

> [!CAUTION]
> **Calibration is REQUIRED before use.** Uncalibrated servos use safe center-only defaults. This prevents unexpected movement, but it also means an uncalibrated servo will not move through its full range.

### 1. Start the Interactive Tool

```bash
uv run pi5servo servo-tool
```

If `servo.json` is empty, the interactive tool now stays neutral at startup. It does not assume `GPIO12` and `GPIO13` anymore. Enter the real endpoint you want to test, such as `gpio12` or `hat_pwm1`.

### 2. Main Menu

```
╔══════════════════════════════════════════════════════════╗
║           pi5servo Interactive Tool                      ║
╠══════════════════════════════════════════════════════════╣
║  1. Quick Move    - Enter commands like 'gpio12:30/hat_pwm1:M' ║
║  2. Single Move   - Move one servo to angle              ║
║  3. Calibrate     - Launch calibration TUI               ║
║  4. Set Speed     - Adjust servo speed limit             ║
║  5. Status        - Show backend and servo configs       ║
║  6. Config        - Show/export/import config            ║
║  q. Exit                                                 ║
╚══════════════════════════════════════════════════════════╝
```

Quick Move is the best way to send direct operator commands like `F_gpio12:0/gpio13:0`. It now forces the requested PWM write, so a return-to-center command is not silently skipped after earlier interactive moves.

### 3. First-Time Setup: Calibrate Your Servos

> [!IMPORTANT]
> **Calibration is required before motion work.** Each servo has different real pulse limits, even when it is the same model.

1. Select option **3. Calibrate**
2. Enter the servo endpoint that carries the servo signal
3. Use the calibration TUI to find the correct pulse widths

After you save calibration data, `servo-tool` now reloads the config and keeps the
same session usable right away. That means you can go straight into Quick Move and
test the calibrated servo without exiting and restarting the tool first.

For native GPIO endpoints that are already part of the live `servo.json` session,
`servo-tool` now reuses the existing live servo for `Single Move` and `Calibrate`
instead of reopening the PWM channel, and quitting that borrowed calibration view
now updates the live group in place instead of rebuilding it. If you enter an
endpoint that is not part of the live session yet, the tool falls back to an
isolated temporary servo, suspends the live group for that temporary session, and
then rebuilds from `servo.json` afterward.

The native RP1 hardware PWM backend now also recovers stale sysfs PWM nodes during
claim, keeps healthy exported PWM channels in place during normal release, and
rolls back already-claimed channels if a later servo in the same startup sequence
fails. That means a bad `pwm1` claim should no longer leave `pwm0` stuck for later
standalone or interactive runs, and healthy channels do not need a fresh export
cycle every time the tool reloads.

For a DFR0566 servo on the HAT's physical `PWM0` connector, enter `hat_pwm1`.
For a DFR0566 servo on the HAT's physical `PWM1` connector, enter `hat_pwm2`.

| Key | Action |
|-----|--------|
| **Tab / Shift+Tab** | Cycle through Min, Center, Max |
| **Up / Down** | Large pulse adjustment (±20μs) |
| **w / s** | Fine adjustment (±1μs) |
| **+ / -** | Adjust speed limit |
| **Enter** | Save calibration |
| **q** | Quit |

---

## Command Format

Commands use the **movement-tool** format:

```text
[GLOBAL_SPEED_]PIN:ANGLE[LOCAL_SPEED][/PIN:ANGLE[LOCAL_SPEED]...]
```

> [!NOTE]
> Numeric targets such as `12:45` still mean native GPIO shorthand. Use explicit forms such as `gpio12:45` and `hat_pwm1:45` for mixed native-GPIO and DFR0566 setups.

### Examples

| Command | Description |
|---------|-------------|
| `12:45` | Move GPIO12 to 45° at medium speed (default) |
| `gpio12:45` | Move explicit native GPIO endpoint `gpio12` to 45° |
| `hat_pwm1:45` | Move DFR0566 PWM channel 1 to 45° |
| `F_12:45` | Move GPIO12 to 45° at **Fast** speed |
| `M_gpio12:45/hat_pwm1:-30` | Move a native GPIO servo and a DFR0566 PWM servo together |
| `S_12:C/13:MF` | Move GPIO12 to Center and GPIO13 to Min with a fast local override |
| `12:45S` | Move GPIO12 to 45° at **Slow** speed |

### Speed Modes

| Prefix | Mode | Description |
|--------|------|-------------|
| `F_` | Fast | Maximum velocity |
| `M_` | Medium | Default balanced speed |
| `S_` | Slow | Gentle movement |

### Special Angles

| Symbol | Meaning |
|--------|---------|
| `C` | Center (0°) |
| `M` | Min (-90°) |
| `X` | Max (90°) |

---

## CLI Commands

> [!CAUTION]
> Use `uv run --frozen` for every `pi5servo` command. The current lockfile
> needs a separately approved repair; frozen mode prevents a test command from
> rewriting it. Run `status --no-probe` before any command that can move a
> servo, and do not run `move`, `cmd`, or `calib` without an accessible external
> servo-power disconnect.

```bash
# Interactive tool (recommended)
uv run pi5servo servo-tool

# Calibration
uv run pi5servo calib 12
uv run pi5servo calib hat_pwm1
uv run pi5servo calib --show

# Single servo
uv run pi5servo move 12 45
uv run pi5servo move hat_pwm1 center
uv run pi5servo move 12 center

# Multi-servo command
uv run pi5servo cmd "F_12:45/13:-30" --pins 12,13
uv run pi5servo cmd "M_gpio12:45/hat_pwm1:-30" --pins gpio12,hat_pwm1

# Status and configuration
uv run pi5servo status --pins 12,13
uv run pi5servo status --pins gpio12,hat_pwm1
uv run pi5servo config show
uv run pi5servo config show --endpoint hat_pwm1
uv run pi5servo config export backup.json
uv run pi5servo config import backup.json
```

> [!NOTE]
> `uv run pi5servo calib ...` only drives the live servo calibration TUI when the optional `blessed` terminal library is installed. If `blessed` is missing, the command falls back to a simple read-only view and the servo will not move.

> [!TIP]
> If an older build showed `Unable to create/write to /sys/class/pwm/pwmchip0/pwm1 (period, duty_cycle, enable)` while calibrating GPIO13 from `servo-tool`, update to the latest `pi5servo`. Configured native endpoints are now calibrated in place on the live session servo, healthy PWM channels stay exported during normal reloads, stale claims are retried once with repair cleanup, and partial multi-servo startup claims are rolled back.
### Advanced Backend Examples

```bash
# Use the DFR0566 PWM channels directly
uv run pi5servo move hat_pwm1 45 \
  --backend dfr0566 \
  --address 0x10 \
  --bus-id 1

# Calibrate the HAT servo on physical PWM0
uv run pi5servo calib hat_pwm1 \
  --backend dfr0566 \
  --address 0x10 \
  --bus-id 1

# Use the optional PCA9685 controller
uv run pi5servo move 12 45 \
  --backend pca9685 \
  --address 0x40 \
  --channel-map 12:0

# Override the Pi 5 hardware PWM mapping
uv run pi5servo status \
  --backend hardware_pwm \
  --pins 12,13 \
  --pin-channel-map 12:0,13:1
```

## Python API

### Basic Standalone Usage

```python
from pi5servo import ConfigManager, ServoGroup

manager = ConfigManager("servo.json")
manager.load()
calibrations = {12: manager.get_calibration(12), 13: manager.get_calibration(13)}

group = ServoGroup(None, pins=[12, 13], calibrations=calibrations)
group.move_all_sync(targets=[45, -30], speed_mode="M")
group.off()
group.close()
```

### Mixed Native GPIO And DFR0566 Usage

```python
from pi5servo import ConfigManager, ServoGroup

manager = ConfigManager("servo.json")
manager.load()
calibrations = {
    "gpio12": manager.get_calibration("gpio12"),
    "hat_pwm1": manager.get_calibration("hat_pwm1"),
}

group = ServoGroup(None, pins=["gpio12", "hat_pwm1"], calibrations=calibrations)
group.move_all_sync(targets=[45, -30], speed_mode="M")
group.close()
```

### Async Usage

```python
await group.move_all_async(targets=[45, -30], speed_mode="M")
group.abort()
```

### Optional External Controller Usage

```python
from pi5servo import ConfigManager, ServoGroup

manager = ConfigManager("servo.json")
manager.load()
calibrations = {12: manager.get_calibration(12)}

group = ServoGroup(
    None,
    pins=[12],
    calibrations=calibrations,
    backend="pca9685",
    backend_kwargs={
        "address": 0x40,
        "channel_map": {12: 0},
    },
)
group.move_all_sync(targets=[45], speed_mode="S")
group.close()
```

### Legacy Compatibility Usage

```python
import pigpio
from pi5servo import ConfigManager, ServoGroup

pi = pigpio.pi()

manager = ConfigManager("servo.json")
manager.load()
calibrations = {12: manager.get_calibration(12)}

group = ServoGroup(pi, pins=[12], calibrations=calibrations)
group.move_all_sync(targets=[45], speed_mode="M")
group.off()
group.close()
pi.stop()
```

---

## Configuration File

Calibration and optional backend settings are stored in `servo.json`:

```json
{
  "__backend__": {
    "name": "auto",
    "kwargs": {
      "address": 16,
      "bus_id": 1
    }
  },
  "gpio12": {
    "pulse_min": 500,
    "pulse_center": 1500,
    "pulse_max": 2500,
    "speed": 80
  },
  "hat_pwm1": {
    "pulse_min": 500,
    "pulse_center": 1500,
    "pulse_max": 2500,
    "speed": 70
  }
}
```

> [!NOTE]
> **Default (uncalibrated) values are all `1500`.** This means an uncalibrated servo stays at the safe center-only state until you calibrate it.

### Endpoint Rule

- native GPIO or DFR0566 digital breakout -> native GPIO endpoint
- DFR0566 PWM connector -> HAT PWM endpoint
- physical DFR0566 `PWM0`/`PWM1`/`PWM2`/`PWM3` currently map to `hat_pwm1`/`hat_pwm2`/`hat_pwm3`/`hat_pwm4`

---

## Easing Functions

| Easing | Behavior |
|--------|----------|
| `ease_in_out_cubic` | Smooth S-curve at both ends **(DEFAULT)** |
| `ease_out_cubic` | Fast start, very slow finish |
| `ease_in_cubic` | Very slow start, fast finish |
| `ease_in_out` | Quadratic S-curve |
| `ease_out` | Fast start, slow finish |
| `ease_in` | Slow start, fast finish |
| `linear` | Constant speed |

> [!TIP]
> `ease_in_out_cubic` with the 100Hz update loop gives the smoothest default motion and keeps the movement profile close to the legacy `pi0servo` behavior.

---

## Hardware Wiring

Connect a hobby servo like this:

| Servo Wire | Raspberry Pi 5 / Power |
|------------|-------------------------|
| **Red** (VCC) | External 5V servo power |
| **Brown/Black** (GND) | External power ground and Raspberry Pi ground |
| **Orange/Yellow** (Signal) | GPIO12, GPIO13, GPIO18, or GPIO19 |

> [!WARNING]
> Do **not** power multiple servos from the Raspberry Pi 5 header alone. Use an external 5V supply and connect the grounds together.

> [!CAUTION]
> Before real motion testing, verify the pulse signal with a logic analyser or oscilloscope. `pi5servo` is designed around hardware-backed PWM, but wiring mistakes and overlay mistakes can still drive the wrong signal.

---

## License

MIT License - See [LICENSE](LICENSE) for details.
