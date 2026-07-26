# pi5buzzer

<div align="center">

**Passive Buzzer Driver and Guided Test Tools for Raspberry Pi 5**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Raspberry Pi 5](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/)

Standalone Raspberry Pi 5 library — see [Installation](#installation) and
[Testing](#testing) below.

</div>

---

A passive buzzer driver for Raspberry Pi 5 with simple sound, music, and test tools.

`pi5buzzer` helps a Raspberry Pi 5 play short beeps, notes, and simple melodies
through a passive buzzer (a small speaker that changes pitch when the signal
frequency changes). It is the Pi 5 version of the old `pi0buzzer` library.

This driver keeps the same main features as the legacy version:

- background playback, so the rest of your program can keep running
- named notes such as `C4` and `A5`
- built-in emotion sounds such as `happy` and `sad`
- a text-based tool for testing
- a simple `buzzer.json` settings file

This is a standalone library. You do not need NinjaRobotPi5 or NinjaClawBot
after you have obtained a complete copy of this `pi5buzzer` folder.

---

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Getting Started](#getting-started)
- [Configuration Management](#configuration-management)
- [Python API (code interface)](#python-api-code-interface)
- [Testing](#testing)

---

## Features

| Feature | Description |
|---|---|
| **Background playback** | Sounds play in the background, so your main program does not have to wait |
| **Pi 5 ready GPIO backend** | Uses `rpi-lgpio` (a Raspberry Pi 5 compatible GPIO library) through an `RPi.GPIO` compatible interface (the same command style used by a common Raspberry Pi GPIO library) |
| **Musical notes** | Includes note frequencies from C3 to B7 |
| **14 emotion sounds** | Includes sounds such as `happy`, `sad`, `exciting`, and `sleepy` |
| **Volume control** | Lets you change the buzzer output level from 0 to 255 |
| **Interactive tool** | Includes `buzzer-tool`, a menu you can use for guided testing |
| **Keyboard piano** | Lets you press keyboard keys to play notes |
| **Settings manager** | Saves settings in a JSON (simple text settings file) file |
| **CLI (command-line) commands** | Includes command-line tools for setup, sound playback, and settings work |
| **Unit tested** | Includes 65 tests with mocked Pi 5 backend behavior |

---

## Architecture

```text
pi5buzzer/
├── pyproject.toml
├── README.md
├── src/pi5buzzer/
│   ├── __init__.py              # Exports: Buzzer, MusicBuzzer
│   ├── __main__.py              # CLI (command-line interface) entry point
│   ├── driver.py                # Compatibility re-exports
│   ├── notes.py                 # Note frequencies, emotion sounds, keyboard map
│   ├── core/
│   │   ├── driver.py            # Buzzer and Pi 5 GPIO backend adapter
│   │   └── music.py             # MusicBuzzer: notes, songs, emotions, piano
│   ├── config/
│   │   └── config_manager.py    # BuzzerConfigManager
│   └── cli/
│       └── buzzer_tool.py       # Interactive text menu
└── tests/
    ├── conftest.py
    ├── test_driver.py
    ├── test_music.py
    └── test_config.py
```

---

## Installation

### Prerequisites

Before you start, make sure you have:

1. A **Raspberry Pi 5** with Raspberry Pi OS Bookworm or newer
2. A **passive buzzer** connected to one GPIO (general-purpose input/output) pin and one GND (ground) pin
3. **Python 3.9 to 3.12** with **Python 3.11** recommended on Raspberry Pi OS Bookworm
4. An internet connection for the first installation

### Step 1: Obtain and enter the standalone folder

Ask the project owner for a complete `pi5buzzer` source folder or source
archive, copy or extract it anywhere you control, then enter that folder. This
README intentionally does not assume a Git repository URL.

```bash
cd /path/to/pi5buzzer
```

If you already have the repository, just move into the `pi5buzzer` folder.

This folder now includes a `.python-version` file set to `3.11`.
That helps `uv` choose a Python version that works with the current
`lgpio` wheels on Raspberry Pi.

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

### Step 3: Install pi5buzzer and its test tools

This creates the local environment, installs `pi5buzzer`, installs the Pi 5
GPIO library, and installs the test tools.

```bash
uv sync --frozen --extra pi --extra dev
```

What this command installs:

- the main `pi5buzzer` package
- `rpi-lgpio` for Raspberry Pi 5 GPIO control
- `pytest` for automated tests
- the project-pinned Ruff release for reproducible code style and lint checks

Important note:

- `pi5buzzer` currently uses Python 3.11 by default in this folder
- this avoids a known `lgpio` build problem on Python 3.13

### Step 4: Verify that the driver is installed

This checks that the command-line tool is available.

```bash
uv run --frozen pi5buzzer --help
```

Expected result:

- a help screen appears
- you can see commands such as `init`, `beep`, `play`, `info`, `config`, and `buzzer-tool`

### If installation fails with `Failed to build lgpio`

You may see an error like this:

```text
Failed to build lgpio
error: command 'swig' failed: No such file or directory
```

What this usually means:

- `uv` created an environment with Python 3.13
- `lgpio` currently provides Raspberry Pi Linux wheels for Python 3.9, 3.10,
  3.11, and 3.12
- when Python 3.13 is used, `uv` falls back to a source build
- that source build needs `swig`, so installation stops

Recommended fix:

```bash
# Check the Python version uv should use in this folder
cat .python-version

# Remove the failed environment if it already exists
rm -rf .venv

# Sync again with the pinned project Python
uv sync --extra pi --extra dev
```

If you want to force the install with a supported Python directly:

```bash
rm -rf .venv
uv sync --python 3.11 --extra pi --extra dev
```

If you must build `lgpio` from source instead of using a wheel:

```bash
sudo apt update
sudo apt install -y swig python3-dev build-essential
uv sync --extra pi --extra dev
```

That source-build path is a manual fallback only. The recommended install path
for Raspberry Pi 5 is still Python 3.11 with the normal wheel install.

---

## Getting Started

### 1. Initialize the buzzer

This saves the GPIO pin number in `buzzer.json` and tries a short test beep.

Example: use GPIO 17.

```bash
uv run pi5buzzer init 17
```

What should happen:

- a `buzzer.json` file is created
- the selected pin is saved
- the buzzer plays a short test sound

### 2. Play a single tone

This plays one simple beep. It is the easiest way to confirm the buzzer is wired correctly.

```bash
# Default test tone: 440 Hz for 0.5 seconds
uv run pi5buzzer beep

# Custom tone: 880 Hz for 1 second
uv run pi5buzzer beep 880 1.0
```

What the values mean:

- `440` or `880` is the sound frequency in Hz (hertz, the tone pitch)
- `0.5` or `1.0` is the time in seconds

### 3. Play an emotion sound

This plays a short built-in sound pattern, such as a happy or sad robot sound.

```bash
uv run pi5buzzer play happy
uv run pi5buzzer play sad
uv run pi5buzzer play exciting
```

Available emotion names:

`angry`, `confusing`, `cry`, `embarrassing`, `exciting`, `happy`, `idle`, `laughing`, `sad`, `scary`, `shy`, `sleepy`, `speaking`, `surprising`

### 4. Show the current status

This shows the saved buzzer settings. It can also run a simple hardware check.

```bash
# Show the saved settings
uv run pi5buzzer info

# Show settings and run a quick hardware test
uv run pi5buzzer info --health-check
```

What the health check does:

- loads the saved pin number
- connects to the Pi 5 GPIO library
- tries a short test beep

### 5. Launch the interactive test tool

This opens a text menu so you can test the buzzer without remembering commands.

```bash
uv run pi5buzzer buzzer-tool
```

This tool lets you:

- initialize the buzzer
- play a single beep
- play an emotion sound
- play notes from the keyboard
- play the demo song
- change volume
- view or import/export settings

Expected exit result:

- when you choose `9. Exit`, the tool should return to the shell cleanly
- you should not see a PWM cleanup traceback after `Goodbye!`

---

## Configuration Management

### Show, export, and import the settings file

These commands help you view, back up, or restore the buzzer settings.

```bash
# Show the current settings
uv run pi5buzzer config show

# Save a backup copy
uv run pi5buzzer config export ~/buzzer_backup.json

# Restore settings from a backup copy
uv run pi5buzzer config import ~/buzzer_backup.json
```

### Settings file format (`buzzer.json`)

```json
{
  "pin": 17,
  "volume": 128
}
```

| Key | Type | Range | Default | Description |
|---|---|---|---|---|
| `pin` | int | 0-27 | 17 | Raspberry Pi GPIO pin number |
| `volume` | int | 0-255 | 128 | Output level used by the buzzer driver |

---

## Python API (code interface)

### Standalone usage

This is the easiest way to use the driver in your own Python program.

```python
from pi5buzzer import MusicBuzzer

with MusicBuzzer(pin=17) as buzzer:
    buzzer.play_sound(440, 0.5)
    buzzer.play_note("C5", 0.3)
    buzzer.play_emotion("happy")
    buzzer.play_song([
        ("C4", 0.3),
        ("E4", 0.3),
        ("G4", 0.3),
        ("C5", 0.6),
    ])
    buzzer.volume = 64
```

### Manual lifecycle

Use this style if you want to manage setup and shutdown yourself.

```python
from pi5buzzer import MusicBuzzer
from pi5buzzer.core.driver import create_default_backend

pi = create_default_backend()
buzzer = MusicBuzzer(pin=17, pi=pi, volume=128)

try:
    buzzer.initialize()
    buzzer.play_emotion("exciting")
finally:
    buzzer.off()
    pi.stop()
```

### Key classes

| Class | Module | Description |
|---|---|---|
| `Buzzer` | `pi5buzzer.core.driver` | Plays queued tones with background playback |
| `MusicBuzzer` | `pi5buzzer.core.music` | Adds notes, songs, emotion sounds, and keyboard piano mode |
| `BuzzerConfigManager` | `pi5buzzer.config.config_manager` | Loads, saves, exports, and imports `buzzer.json` |

---

## Testing

### Run the automated tests

This checks that the Python logic still matches the expected behavior.

```bash
uv run pytest -q
```

Expected result:

- all tests pass
- the command ends with a short summary such as `65 passed`

### Run the lint and format checks

These commands check code style and common mistakes.

```bash
uv run ruff check .
uv run ruff format --check .
```

The development dependency pins Ruff and the package declares its enabled rule
families explicitly, so these commands produce the same result after a fresh
`uv sync`.

### Real Raspberry Pi 5 function test

This is the recommended order for a manual hardware test.

1. Power off the Raspberry Pi 5 and connect the passive buzzer.
2. Start the Raspberry Pi 5 and move into the `pi5buzzer` folder.
3. Run `uv sync --frozen --extra pi --extra dev`.
4. Run `uv run --frozen pi5buzzer init 17`.
5. Run `uv run --frozen pi5buzzer beep 440 0.3`.
6. Run `uv run --frozen pi5buzzer play happy`.
7. Run `uv run --frozen pi5buzzer info --health-check`.

Expected result:

- the buzzer plays short sounds clearly
- the command line reports no backend errors
- the buzzer becomes silent again after each test
