# pi5vl53l0x

<div align="center">

**VL53L0X Distance Sensor Driver and Guided Sensor Tools for Raspberry Pi 5**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Raspberry Pi 5](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/)

Standalone Raspberry Pi 5 library — see [Installation](#installation) and
[Raspberry Pi 5 Validation Checklist](#raspberry-pi-5-validation-checklist) below.

</div>

---

A standalone VL53L0X distance sensor driver for Raspberry Pi 5.

`pi5vl53l0x` helps a Raspberry Pi 5 read distance from a VL53L0X
Time-of-Flight sensor (a laser distance sensor that measures how long light
takes to bounce back). It is the Pi 5 version of the old `pi0vl53l0x`
library.

This driver keeps the same main features as the legacy version:

- single distance reads and repeated reads
- calibration with saved offset values
- health checks and reinitialize recovery
- a text-based tool for guided testing
- a simple `vl53l0x.json` settings file

This is a standalone library. You do not need NinjaRobotPi5 or NinjaClawBot
after you have obtained a complete copy of this `pi5vl53l0x` folder.

---

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Getting Started](#getting-started)
- [Python Usage](#python-usage)
- [Automated Testing](#automated-testing)
- [Raspberry Pi 5 Validation Checklist](#raspberry-pi-5-validation-checklist)
- [Troubleshooting](#troubleshooting)

---

## Features

| Feature | Description |
|---|---|
| **Pi 5 ready I2C backend** | Uses `smbus2` (a Python wrapper for Linux I2C devices) with the standard Raspberry Pi 5 `/dev/i2c-*` interface |
| **Legacy function parity** | Keeps the main `VL53L0X` class behavior from the old `pi0vl53l0x` library |
| **Retry and recovery** | Retries failed I2C operations and one failed reference-calibration attempt, with deterministic cleanup |
| **Big-endian register support** | Preserves the byte-order handling required by the VL53L0X sensor |
| **Calibration support** | Calculates and stores `offset_mm`, but rejects invalid or out-of-range samples |
| **Health and recovery tools** | Includes `health_check()` and `reinitialize()` for runtime recovery |
| **Interactive tool** | Includes `sensor-tool`, a menu for guided sensor testing |
| **CLI commands** | Includes command-line tools for reading, calibration, status, config, and testing |
| **Settings manager** | Saves settings in a JSON (simple text settings file) file |
| **Unit tested** | Includes 71 tests with mocked Pi 5 I2C behavior |

---

## Architecture

```text
pi5vl53l0x/
├── pyproject.toml
├── README.md
├── src/pi5vl53l0x/
│   ├── __init__.py              # Exports: VL53L0X
│   ├── __main__.py              # CLI (command-line interface) entry point
│   ├── driver.py                # Compatibility re-export
│   ├── registers.py             # VL53L0X register constants
│   ├── core/
│   │   ├── i2c.py               # Thread-safe Pi 5 I2C wrapper using smbus2
│   │   └── sensor.py            # VL53L0X driver logic
│   ├── config/
│   │   └── config_manager.py    # ConfigManager and vl53l0x.json helpers
│   └── cli/
│       └── sensor_tool.py       # CLI and interactive text menu
└── tests/
    ├── test_i2c.py
    ├── test_sensor.py
    ├── test_config.py
    └── test_cli.py
```

---

## Installation

### Prerequisites

Before you start, make sure you have:

1. A **Raspberry Pi 5** with Raspberry Pi OS Bookworm or newer
2. A **VL53L0X sensor module** connected for **3.3V logic** (the Raspberry Pi 5 GPIO header also uses 3.3V logic)
3. **Python 3.9 to 3.13** with **Python 3.11** recommended on Raspberry Pi OS Bookworm
4. An internet connection for the first installation

Typical VL53L0X wiring:

- `VIN` or `3V3` to Raspberry Pi `3.3V`
- `GND` to Raspberry Pi `GND`
- `SDA` to Raspberry Pi `GPIO 2 / SDA`
- `SCL` to Raspberry Pi `GPIO 3 / SCL`

### Step 1: Obtain and enter the standalone folder

This downloads the project to your Raspberry Pi 5.

```bash
cd /path/to/pi5vl53l0x
```

Ask the project owner for a complete `pi5vl53l0x` source folder or source
archive. This README does not require or assume a Git repository URL.

If you already have the repository, just move into the `pi5vl53l0x` folder.

This folder includes a `.python-version` file set to `3.11`.
That helps `uv` choose a stable Python version for Raspberry Pi work.

### Step 2: Install uv

`uv` is the tool used in this project to install packages, create the local
environment, and run commands.

For Raspberry Pi OS, Linux, or macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Check that `uv` is ready:

```bash
uv --help
```

### Step 3: Enable I2C on the Raspberry Pi 5

The VL53L0X sensor uses I2C (a two-wire control bus used by many small sensor
boards). The Raspberry Pi must have I2C enabled before the driver can talk to
the sensor.

Open the Raspberry Pi configuration tool:

```bash
sudo raspi-config
```

Then:

1. Open `Interface Options`
2. Open `I2C`
3. Choose `Yes`
4. Exit the tool
5. Reboot the Raspberry Pi

After reboot, check that the bus exists:

```bash
ls /dev/i2c-1
```

Expected result:

- `/dev/i2c-1` is shown

### Step 4: Install I2C test tools

This step installs a simple diagnostic tool that helps confirm the sensor is
visible on the bus.

```bash
sudo apt update
sudo apt install -y i2c-tools
```

### Step 5: Install pi5vl53l0x and its test tools

This creates the local environment, installs `pi5vl53l0x`, and installs the
test tools used by this project.

```bash
uv sync --frozen --extra pi --extra dev
```

What this command installs:

- the main `pi5vl53l0x` package
- `smbus2` for Raspberry Pi 5 I2C control
- `blessed` for the interactive text tool
- `pytest` for automated tests
- `ruff` for code style and lint checks

### Step 6: Verify that the driver is installed

This checks that the command-line tool is available.

```bash
uv run --frozen pi5vl53l0x --help
uv run --frozen pi5vl53l0x config show
```

Expected result:

- a help screen appears
- you can see commands such as `get`, `performance`, `calibrate`, `status`, `config`, `test`, and `sensor-tool`
- the config command prints the config file path even if the file does not exist yet

---

## Getting Started

### 1. Confirm that the sensor is visible on the I2C bus

This checks whether the Raspberry Pi can see the sensor hardware.

```bash
sudo i2cdetect -y 1
```

What this command does:

- scans I2C bus `1`
- prints a grid of detected device addresses

What to look for:

- `29` should appear in the output

If `29` does not appear:

- check `3.3V`, `GND`, `SDA`, and `SCL` wiring
- confirm I2C is enabled
- confirm the sensor board is powered correctly

### 2. Run the quick sensor test

This is the easiest way to check that the driver can open the sensor and take a
few readings.

```bash
uv run pi5vl53l0x test
```

What this command does:

- opens the sensor
- prints the saved offset value
- takes five test readings

What should happen:

- you see five distance values in millimeters
- every line has a `✓` valid marker
- the command ends with `✓ Test passed`

The command returns a non-zero exit status if any sample is invalid. In
particular, `8191 mm` is the VL53L0X out-of-range sentinel and is a failed test,
not a usable distance.

### 3. Take one reading or several readings

This command is useful when you want simple distance output for scripts or
manual checks.

```bash
# One reading
uv run pi5vl53l0x get

# Five readings, half a second apart
uv run pi5vl53l0x get --count 5 --interval 0.5
```

What the values mean:

- `count` is how many readings to take
- `interval` is the wait time between readings in seconds

What the output shows:

- a distance value in millimeters
- the raw sensor value
- a simple valid or warning marker

The command returns a non-zero exit status if any requested reading is invalid,
which makes it suitable for shell validation.

### 4. Show full sensor status

This command prints a simple health and configuration report.

```bash
uv run pi5vl53l0x status
```

What this command does:

- runs a health check
- shows the saved offset value
- attempts one reading
- shows the current config values

I2C health and range validity are reported separately. A connected sensor that
returns `8191 mm` fails diagnostics even when its identity register is readable.

Use this when:

- you want a quick summary of the sensor state
- you want to confirm that calibration was saved

### 5. Run the performance test

This command measures how quickly the sensor can produce readings.

```bash
uv run pi5vl53l0x performance --count 50
```

What this command does:

- runs repeated measurements
- counts read errors
- shows average speed in Hz (hertz, readings per second)

Use this when:

- you want to compare sensor stability before and after code changes
- you want to check if the sensor is timing out under repeated reads

### 6. Calibrate the distance offset

This command helps correct small distance errors.

```bash
uv run pi5vl53l0x calibrate --distance 200 --count 10
```

What this command does:

- assumes the target is really `200 mm` away
- takes `10` readings
- calculates the sensor offset
- saves the result to `vl53l0x.json`

Before you run it:

- place a flat target at a known distance
- keep the sensor and target still during measurement
- first confirm `test` produces valid readings

Calibration aborts without saving a new offset if any sample is invalid.

### 7. Use the interactive sensor tool

This is the guided menu for non-script testing.

```bash
uv run pi5vl53l0x sensor-tool
```

What this tool does:

- shows a text menu
- lets you take single reads or repeated reads
- lets you run performance tests
- lets you calibrate, check status, and reinitialize the sensor

Use this when:

- you want guided testing without remembering command names
- you want to calibrate and inspect settings interactively

### 8. Work with the config file

The driver stores its settings in `vl53l0x.json`.

```bash
# Show current config
uv run pi5vl53l0x config show

# Export a backup copy
uv run pi5vl53l0x config export backup.json

# Import a saved config
uv run pi5vl53l0x config import backup.json
```

What this is useful for:

- backing up calibration
- moving the same settings to another Raspberry Pi
- checking whether the saved offset is what you expect

---

## Python Usage

### 1. Create the sensor and take one reading

```python
from pi5vl53l0x import VL53L0X

with VL53L0X() as sensor:
    distance_mm = sensor.get_range()
    print(f"Distance: {distance_mm} mm")
```

### 2. Get structured sensor data

```python
from pi5vl53l0x import VL53L0X

with VL53L0X() as sensor:
    data = sensor.get_data()
    print(data)
```

This returns keys such as:

- `distance_mm`
- `is_valid`
- `raw_value`
- `timestamp`

### 3. Run a health check or recovery

```python
from pi5vl53l0x import VL53L0X

sensor = VL53L0X()

if not sensor.health_check():
    sensor.reinitialize()

sensor.close()
```

### 4. Run calibration in Python

```python
from pi5vl53l0x import VL53L0X

with VL53L0X() as sensor:
    offset = sensor.calibrate(target_distance_mm=200, num_samples=10)
    sensor.set_offset(offset)
    print(f"Suggested offset: {offset} mm")
```

---

## Automated Testing

Run the package checks with:

```bash
uv run python -m compileall src tests
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

What these commands do:

- `compileall` checks that Python files can be compiled
- `ruff check` checks code quality rules
- `ruff format --check` checks code formatting
- `pytest` runs the automated tests

Current automated result for this package:

- `71 passed`

---

## Raspberry Pi 5 Validation Checklist

### Safe smoke tests

```bash
uv run pi5vl53l0x --help
uv run pi5vl53l0x config show
ls /dev/i2c-1
sudo i2cdetect -y 1
```

Expected result:

- the CLI help loads
- the config command works
- `/dev/i2c-1` exists
- `29` appears in the `i2cdetect` grid

### Device communication tests

```bash
uv run pi5vl53l0x test
uv run pi5vl53l0x get --count 5 --interval 0.5
uv run pi5vl53l0x status
```

Expected result:

- the sensor initializes without an I2C error
- distance values print consistently with valid markers
- `status` reports both healthy communication and a valid distance
- none of the commands returns the `8191 mm` out-of-range sentinel

### Sensor behavior tests

```bash
uv run pi5vl53l0x performance --count 50
uv run pi5vl53l0x calibrate --distance 200 --count 10
uv run pi5vl53l0x sensor-tool
```

Expected result:

- performance test completes without repeated timeouts
- calibration calculates and saves `offset_mm`
- the interactive tool can read, calibrate, show config, and reinitialize

### Power and wiring safety notes

- do not hot-plug the sensor while a read command is running
- use `3.3V` logic wiring, not `5V` logic on GPIO signal pins
- if readings are unstable, power off the Pi before changing wiring

### Rollback steps

- stop the running command with `Ctrl+C`
- disconnect Raspberry Pi power before rewiring the sensor
- remove the config file if you want a clean software reset:

```bash
rm -f src/pi5vl53l0x/config/vl53l0x.json
```

---

## Troubleshooting

### `I2C bus device not found`

What it means:

- I2C is not enabled
- or the expected bus device was not created

What to do:

- run `sudo raspi-config`
- enable `I2C`
- reboot
- check `ls /dev/i2c-1`

### `i2cdetect` does not show `29`

What it means:

- the sensor is not visible on the bus

What to do:

- check wiring
- confirm the sensor board is powered
- confirm you are using the correct I2C pins

### Read timeouts or invalid values

What it means:

- the sensor can be connected but not reading reliably

What to do:

- keep the target steady and within normal range
- remove any protective film and clean the sensor window
- confirm the emitter and receiver have an unobstructed view of a flat,
  non-reflective target
- rerun `uv run pi5vl53l0x status`
- cold-power-cycle the sensor if a previous initialization was interrupted
- use `uv run pi5vl53l0x sensor-tool` and try `Reinitialize`

Do not calibrate while readings are invalid. The CLI rejects `8191 mm` and
other invalid samples so that a bad measurement cannot be saved as an offset.
