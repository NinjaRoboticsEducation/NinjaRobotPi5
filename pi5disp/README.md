# pi5disp

<div align="center">

**ST7789V Display Driver and Guided Display Tools for Raspberry Pi 5**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Raspberry Pi 5](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/)

Standalone Raspberry Pi 5 library — see [Installation](#installation) and
[Raspberry Pi 5 Validation Checklist](#raspberry-pi-5-validation-checklist) below.

</div>

---

A standalone ST7789V display driver for Raspberry Pi 5.

`pi5disp` helps a Raspberry Pi 5 control an ST7789V screen (a small SPI display
module often used for robot faces, status panels, and test screens). It is the
Pi 5 version of the old `pi0disp` library.

This driver keeps the same main features as the legacy version:

- screen setup with a saved `display.json` file
- image display and text display
- scrolling text
- brightness control
- rotation control
- an interactive display tool for guided testing

This is a standalone library. You do not need NinjaRobotPi5 or NinjaClawBot
after you have obtained a complete copy of this `pi5disp` folder.

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
| **Pi 5 ready display backend** | Uses `spidev` for SPI (the Linux SPI device interface) and an `RPi.GPIO` compatible layer intended for `rpi-lgpio` for display pins and backlight control |
| **Reliable full-frame rendering** | `display()` always writes the full frame for predictable behavior on Raspberry Pi 5 |
| **Partial region rendering** | `display_region()` still supports drawing only one part of the screen when needed |
| **Brightness control** | Lets you change backlight brightness from 0 to 100 |
| **Rotation support** | Supports `0`, `90`, `180`, and `270` degree rotation |
| **Text ticker effect** | Includes a scrolling text effect with bundled fonts |
| **Bundled multilingual fonts** | Includes Noto fonts for English, Japanese, and Traditional Chinese |
| **CLI commands** | Includes setup, image, text, demo, brightness, info, clear, config, and `display-tool` commands |
| **Settings manager** | Saves settings in a JSON (simple text settings file) file |
| **Unit tested** | Includes 59 tests with mocked Raspberry Pi 5 backend behavior |

---

## Architecture

```text
pi5disp/
├── pyproject.toml
├── README.md
├── display.json
├── src/pi5disp/
│   ├── __init__.py              # Exports: ST7789V, ConfigManager
│   ├── __main__.py              # CLI entry point
│   ├── core/
│   │   ├── driver.py            # ST7789V driver and Pi 5 backend adapter
│   │   └── renderer.py          # ColorConverter and RegionOptimizer
│   ├── config/
│   │   └── config_manager.py    # display.json setup and load/save helpers
│   ├── effects/
│   │   └── text_ticker.py       # Scrolling text effect
│   ├── fonts/
│   │   ├── NotoSans-Regular.ttf
│   │   ├── NotoSansJP-Regular.otf
│   │   └── NotoSansTC-Regular.otf
│   └── cli/
│       ├── _common.py           # Shared CLI display creation helper
│       ├── init_cmd.py          # Setup wizard
│       ├── image_cmd.py         # Show image
│       ├── text_cmd.py          # Show text or scrolling text
│       ├── demo_cmd.py          # Bouncing ball demo
│       ├── info_cmd.py          # Display info and health
│       └── display_tool.py      # Interactive menu
└── tests/
    ├── conftest.py
    ├── test_driver.py
    ├── test_renderer.py
    ├── test_config.py
    ├── test_text_ticker.py
    └── test_cli.py
```

---

## Installation

### Prerequisites

Before you start, make sure you have:

1. A **Raspberry Pi 5** with Raspberry Pi OS Bookworm or newer
2. An **ST7789V display module**
3. **Python 3.9 to 3.13** with **Python 3.11** recommended on Raspberry Pi OS Bookworm
4. An internet connection for the first installation

Default control pins used by this driver:

- `DC` uses `GPIO 14`
- `RST` uses `GPIO 15`
- `BLK` (backlight) uses `GPIO 16`

Default SPI connection used by this driver:

- `MOSI` on `GPIO 10`
- `SCLK` on `GPIO 11`
- `CE0` on `GPIO 8`

Important note:

- display module power wiring is not identical on every ST7789V board
- many boards label power as `VCC`, `VIN`, `5V`, or `3V3`
- check your display board label before connecting power
- GPIO signal pins on the Raspberry Pi 5 are still **3.3V logic**

### Step 1: Obtain and enter the standalone folder

This downloads the project to your Raspberry Pi 5.

```bash
cd /path/to/pi5disp
```

Ask the project owner for a complete `pi5disp` source folder or source archive.
This README does not require or assume a Git repository URL.

If you already have the repository, just move into the `pi5disp` folder.

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

### Step 3: Enable SPI on the Raspberry Pi 5

The display uses SPI (a fast serial hardware bus used by many screens and
sensors). The Raspberry Pi must have SPI enabled before the driver can talk to
the screen.

Open the Raspberry Pi configuration tool:

```bash
sudo raspi-config
```

Then:

1. Open `Interface Options`
2. Open `SPI`
3. Choose `Yes`
4. Exit the tool
5. Reboot the Raspberry Pi

After reboot, check that the default SPI device exists:

```bash
ls /dev/spidev0.0
```

Expected result:

- `/dev/spidev0.0` is shown

### Step 4: Install pi5disp and its test tools

This creates the local environment, installs `pi5disp`, installs the Pi 5
hardware libraries, and installs the test tools.

```bash
uv sync --frozen --extra pi --extra dev
```

What this command installs:

- the main `pi5disp` package
- `spidev` for Raspberry Pi 5 SPI communication
- `rpi-lgpio` for display control pins and backlight control
- `pytest` for automated tests
- `ruff` for code style and lint checks

### Step 5: Verify that the driver is installed

This checks that the command-line tool is available.

```bash
uv run --frozen pi5disp --help
uv run --frozen pi5disp config show
```

Expected result:

- a help screen appears
- you can see commands such as `init`, `image`, `text`, `demo`, `info`, `clear`, `brightness`, `config`, and `display-tool`
- the config command prints the current display settings

---

## Getting Started

### 1. Initialize the display settings

This creates or updates the writable user configuration with your display
profile, pin numbers, rotation, and brightness settings. The default path is
`~/.config/pi5disp/display.json` (or
`$XDG_CONFIG_HOME/pi5disp/display.json`).

```bash
# Guided setup
uv run pi5disp init

# Quick setup with defaults
uv run pi5disp init --defaults
```

What this command does:

- selects the display profile
- saves the `DC`, `RST`, and `BLK` pins
- saves the rotation and brightness settings

Use `init` when:

- you are setting up the display for the first time
- you changed the wiring
- you want to change the saved rotation or brightness defaults

### 2. Check the saved settings

This shows the current display config file values.

```bash
uv run pi5disp config show
```

What this command does:

- loads the per-user `display.json`
- prints the saved display profile and pin values

Use this when:

- you want to confirm the saved wiring
- you want to check the current rotation and brightness values

### 3. Clear the display

This fills the screen with black.

```bash
uv run pi5disp clear
```

What this command does:

- opens the display
- draws a full black frame
- closes the display cleanly

Use this when:

- you want a quick connection test
- you want to clear old content from the screen

### 4. Change the brightness

This changes the backlight brightness from `0` to `100`.

```bash
uv run pi5disp brightness 50
```

What this command does:

- changes the backlight output level
- updates the saved `brightness` value in the per-user `display.json`
- applies that saved brightness when the next display session starts

Use this when:

- the screen is too bright or too dim
- you want to confirm that the backlight control pin is wired correctly

### 5. Show an image

This displays an image file on the screen.

```bash
uv run pi5disp image ./example.png
```

What this command does:

- opens the image
- converts it to RGB if needed
- resizes it to the display size if needed
- sends it to the screen

Use this when:

- you want to test the full display area
- you want to show a robot face, logo, or status screen

### 6. Show text

This displays text in the center of the screen.

```bash
uv run pi5disp text "Hello NinjaClawBot"
```

What this command does:

- loads a font
- draws the text on an image
- sends the result to the display

Use this when:

- you want a simple display check
- you want to show a short status message

### 7. Show scrolling text

This scrolls text across the screen.

```bash
uv run pi5disp text "Welcome to NinjaClawBot" --scroll --duration 10
```

What this command does:

- starts the scrolling text effect
- keeps drawing frames for the selected time

Useful options:

- `--lang ja` for Japanese text
- `--lang zh-tw` for Traditional Chinese text
- `--speed 3` to scroll faster
- `--duration 15` to scroll longer

### 8. Run the demo animation

This runs a bouncing ball animation.

```bash
uv run pi5disp demo --num-balls 3 --duration 10
```

What this command does:

- draws moving colored balls
- updates the display repeatedly
- helps expose SPI or display stability problems

Use this when:

- you want a simple motion test
- you want to check repeated frame updates

### 9. Show display information

This prints the display settings and a simple hardware health result.

```bash
uv run pi5disp info
```

What this command does:

- shows the saved display profile
- shows the saved pin numbers
- shows brightness, rotation, and SPI speed
- opens the display and runs a basic health check

### 10. Use the interactive display tool

This opens a guided menu for non-script testing.

```bash
uv run pi5disp display-tool
```

What this tool does:

- shows a menu for setup, image display, text, demo, brightness, info, clear, and config
- keeps one live display session open until you exit the tool
- lets you test features without remembering every command

Use this when:

- you want guided testing
- you want to check several features in one session

### 11. Export or import the config

This backs up or restores the `display.json` settings file.

```bash
# Export a backup
uv run pi5disp config export backup_display.json

# Import a saved config
uv run pi5disp config import backup_display.json
```

What this is useful for:

- backing up a working display setup
- moving the same settings to another Raspberry Pi
- restoring a known-good configuration after testing

Set `PI5DISP_CONFIG` when a command needs a different runtime file:

```bash
PI5DISP_CONFIG=/tmp/test-display.json uv run pi5disp config show
```

---

## Python Usage

### 1. Create the display and clear it

```python
from pi5disp import ST7789V

with ST7789V() as lcd:
    lcd.clear()
```

### 2. Show an image

```python
from PIL import Image
from pi5disp import ST7789V

with ST7789V() as lcd:
    image = Image.open("face.png").convert("RGB")
    lcd.display(image)
```

### 3. Change brightness and rotation

```python
from pi5disp import ST7789V

with ST7789V() as lcd:
    lcd.set_brightness(60)
    lcd.set_rotation(180)
```

### 4. Use the text ticker

```python
import time

from pi5disp import ST7789V
from pi5disp.effects import TextTicker

with ST7789V() as lcd:
    ticker = TextTicker(lcd, "NinjaClawBot Ready", speed=2.0)
    ticker.start()
    time.sleep(5)
    ticker.stop()
```

### 5. Check health or turn the display off

```python
from pi5disp import ST7789V

lcd = ST7789V()

print(lcd.health_check())
lcd.off()
lcd.close()
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

- `59 passed`

---

## Raspberry Pi 5 Validation Checklist

### Safe smoke tests

```bash
ls /dev/spidev0.0
uv run pi5disp --help
uv run pi5disp init --defaults
uv run pi5disp config show
uv run pi5disp info
```

Expected result:

- `/dev/spidev0.0` exists
- the CLI help loads
- the default config is created or updated
- the saved display profile and pins print correctly
- `info` reports working hardware status

### Device communication tests

```bash
uv run pi5disp clear
uv run pi5disp brightness 50
uv run pi5disp image ./example.png
uv run pi5disp text "Hello"
```

Expected result:

- the screen clears correctly
- the backlight changes brightness
- the saved brightness stays in effect when you start the next display action
- the image renders
- text appears clearly on screen

### Display behavior tests

```bash
uv run pi5disp text "Scrolling text" --scroll --duration 10
uv run pi5disp demo --num-balls 3 --duration 10
uv run pi5disp display-tool
```

Expected result:

- scrolling text moves smoothly
- the demo animation updates without screen corruption
- the interactive tool can complete several actions in one session
- a demo, then brightness change, then another demo should work without needing a manual clear in between

### Power and wiring safety notes

- power the Raspberry Pi down before changing display wiring
- check the display board power label before connecting `VCC` or `VIN`
- avoid hot-plugging the SPI display while commands are running
- if the screen stays blank, recheck `DC`, `RST`, `BLK`, `MOSI`, `SCLK`, and `CE0`

### Rollback steps

- stop the running command with `Ctrl+C`
- power the Raspberry Pi down before rewiring the display
- remove the saved config if you want a clean software reset:

```bash
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/pi5disp/display.json"
```

---

## Troubleshooting

### `/dev/spidev0.0` is missing

What it means:

- SPI is not enabled

What to do:

- run `sudo raspi-config`
- enable `SPI`
- reboot
- check `ls /dev/spidev0.0`

### The screen stays blank

What it means:

- the display has power or wiring problems
- or the control pins do not match the saved config

What to do:

- check the display power pin label
- check `DC`, `RST`, and `BLK`
- check `MOSI`, `SCLK`, and `CE0`
- rerun `uv run pi5disp init`

### The screen is rotated the wrong way

What it means:

- the saved rotation is not correct for your mount position

What to do:

- rerun `uv run pi5disp init`
- or change the saved value with `uv run pi5disp config set rotation 180`

### Brightness does not change

What it means:

- the backlight control pin may be wrong

What to do:

- confirm the `BLK` pin in the per-user `display.json`
- rerun `uv run pi5disp brightness 100`
- rerun `uv run pi5disp brightness 10`
- if needed, rerun `uv run pi5disp init`
