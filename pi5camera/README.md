# pi5camera

<div align="center">

**Standalone-First Camera Tools and Local Face Recognition for Raspberry Pi 5**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Raspberry Pi 5](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/)

Standalone Raspberry Pi 5 library — see [Installation](#installation) and
[Getting Started](#getting-started) below.

</div>

---

A standalone-first camera library for Raspberry Pi 5.

`pi5camera` helps a Raspberry Pi 5 take photos, save them into a predictable
folder, recognize known faces locally, and enroll new faces for later
recognition. It can work by itself as a local camera tool, or it can be reused
by `ninjaclawbot` and the OpenClaw plugin inside the larger NinjaClawBot
project.

This package is designed for normal Raspberry Pi users, not only developers.
The safest first path is the standalone workflow. After that works, you can
reuse the same `camera.json`, `photo/`, and `camera_data/` folders from the
full NinjaClawBot workspace.

Main functions available today:

- guide first-time setup with `pi5camera setup`
- provide a beginner-friendly menu with `pi5camera camera-tool`
- run camera readiness checks with `pi5camera doctor`
- show the current config and storage paths with `pi5camera status`
- take one still photo with `pi5camera capture`
- recognize faces from a live capture or an existing image with
  `pi5camera recognize`
- optionally prompt for unknown-face names during the same recognition flow
- enroll a face later from a saved pending recognition with `pi5camera enroll`
- list and remove saved identities with `pi5camera manage-faces`
- reuse the same camera flow through `ninjaclawbot` and OpenClaw later

This is a standalone library. You do not need NinjaRobotPi5 or NinjaClawBot
after you have obtained a complete copy of this `pi5camera` folder.

---

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Dependencies](#dependencies)
- [Installation](#installation)
- [Getting Started](#getting-started)
- [Face Recognition Workflow](#face-recognition-workflow)
- [Full Command-Line Reference](#full-command-line-reference)
- [Testing](#testing)
- [Appendix](#appendix)

---

## Features

| Feature | Description |
|---|---|
| **Standalone-first workflow** | Install and test `pi5camera` by itself before connecting it to `ninjaclawbot` or OpenClaw |
| **Guided setup** | `pi5camera setup` creates or updates `camera.json` with beginner-friendly prompts |
| **Interactive tool** | `camera-tool` menu for setup, capture, recognition, and face management |
| **Normal photo capture** | Saves one still image into the configured photo directory |
| **Root-aware default storage** | Uses `<active_root>/photo` and `<active_root>/camera_data` by default |
| **Local face recognition** | Uses **MediaPipe** (face detection) + **OpenCV DNN** (face embeddings) — no cloud API required |
| **dlib-free** | No C++ compilation required; uses pre-built ARM64 wheels for all dependencies |
| **Stub camera backend** | `StubCameraBackend` for macOS development and test automation without hardware |
| **Second-step enrollment** | Unknown faces can be named later using saved pending recognition data |
| **Known-face management** | Can list and remove saved identities from the local database |
| **Lazy loading** | Heavy dependencies (Pillow, OpenCV, MediaPipe) are only imported when needed |

---

## Architecture

```text
pi5camera/
├── README.md
├── pyproject.toml
├── uv.lock
├── scripts/
│   └── bootstrap-rpi-standalone.sh
├── src/pi5camera/
│   ├── __init__.py              # Lazy package re-exports
│   ├── __main__.py              # CLI entry point (LazyGroup)
│   ├── driver.py                # Compatibility re-exports
│   ├── errors.py                # Shared pi5camera exceptions
│   ├── models.py                # Shared capture and face dataclasses
│   ├── environment.py           # System probe (is_raspberry_pi, check backends)
│   ├── cli/
│   │   ├── _common.py           # Shared CLI helpers
│   │   ├── camera_tool.py       # Beginner-friendly interactive menu
│   │   ├── capture_cmd.py       # One-shot photo capture
│   │   ├── doctor.py            # Readiness and directory checks
│   │   ├── enroll_cmd.py        # Face enrollment commands
│   │   ├── manage_faces_cmd.py  # Known-face list and removal
│   │   ├── recognize_cmd.py     # Face recognition workflow
│   │   ├── setup_cmd.py         # Guided setup wizard
│   │   └── status.py            # Config and readiness summary
│   ├── config/
│   │   └── config_manager.py    # camera.json defaults and load/save
│   ├── core/
│   │   ├── camera_backend.py    # CameraBackend protocol, Picamera2 + Stub
│   │   ├── capture.py           # Still-photo helpers
│   │   ├── enrollment.py        # Known-face enrollment helpers
│   │   └── recognition.py       # Face matching workflow
│   ├── recognition/
│   │   ├── base.py              # RecognitionBackend protocol
│   │   └── mediapipe_opencv_backend.py  # MediaPipe + OpenCV DNN backend
│   └── storage/
│       ├── photo_storage.py     # Photo output with microsecond timestamps
│       ├── face_index.py        # Known-face CRUD (encodings.json)
│       └── pending_records.py   # Pending-recognition lifecycle with TTL
└── tests/
    ├── test_config_manager.py
    ├── test_photo_storage.py
    ├── test_face_index.py
    ├── test_pending_records.py
    ├── test_camera_backend.py
    ├── test_recognition_flow.py
    └── test_cli_startup.py
```

Storage layout created by setup and normal use:

```text
<active_root>/
├── camera.json
├── photo/
│   ├── photo-20260324-101500-123456.jpg
│   └── recognize-20260324-101640-789012.jpg
└── camera_data/
    ├── index/
    │   └── encodings.json
    ├── known_faces/
    │   └── Alice/
    └── pending/
        └── <recognition_id>/
            ├── record.json
            └── face-1.jpg
```

---

## Dependencies

### Runtime dependencies

| Package | Purpose | Required | ARM64 wheel |
|---|---|---|---|
| `click` | CLI framework | ✅ Yes | ✅ |
| `Pillow` | Image processing (crop, resize) | ✅ Yes | ✅ |
| `opencv-python-headless` | Face detection (Haar cascade), face embedding (DNN), image I/O | ✅ Yes | ✅ |
| `numpy` | Array operations (used by OpenCV) | ✅ Yes | ✅ |
| `mediapipe` | Higher-accuracy face detection (Google) | ❌ Optional | ❌ No ARM64 Linux wheel |

### Raspberry Pi system packages

| Package | Purpose |
|---|---|
| `python3-picamera2` | Camera hardware interface |
| `python3-libcamera` | Low-level camera control |

### How face detection works

- **On x86_64 / macOS** (where MediaPipe can install): uses MediaPipe for
  higher-accuracy face detection.
- **On ARM64 / Raspberry Pi** (where MediaPipe cannot install): automatically
  falls back to **OpenCV Haar cascade**, which is always shipped with
  `opencv-python-headless`. No extra installation needed.

The `doctor` and `status` commands show which detector is active:

```text
Detection:   opencv_haar    ← ARM64 fallback (Raspberry Pi)
Detection:   mediapipe      ← primary detector (x86_64 / macOS)
```

> **Note:** `dlib` and `face-recognition` are **not used**. The recognition
> backend uses OpenCV (required) + MediaPipe (optional), which does not
> require C++ compilation.

### Development dependencies

| Package | Purpose |
|---|---|
| `pytest` | Test runner |
| `ruff` | Linting and formatting |

---

## Installation

### Prerequisites

1. A **Raspberry Pi 5** with Raspberry Pi OS Bookworm or newer
2. A **Raspberry Pi camera module** connected correctly
3. An **internet connection** for the first installation
4. A terminal with permission to run `sudo`

### Step 1. Obtain and enter the standalone folder

Ask the project owner for a complete `pi5camera` source folder or source
archive, copy or extract it anywhere you control, then enter that folder:

```bash
cd /path/to/pi5camera
```

This README does not require or assume a Git repository URL or a parent
NinjaRobotPi5/NinjaClawBot checkout.

### Step 2. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

After installation, confirm with `uv --version`.

> [!NOTE]
> Later examples may show `cd ~/pi5camera`. Replace that path with the actual
> standalone folder you chose in Step 1.

### Step 3. Run the Raspberry Pi bootstrap installer

```bash
cd ~/pi5camera
./scripts/bootstrap-rpi-standalone.sh
```

What this does:

- installs the Raspberry Pi camera packages (`python3-picamera2`,
  `python3-libcamera`) with `apt`
- creates `.venv` with `/usr/bin/python3 -m venv --system-site-packages`
- runs `uv sync --active --frozen --extra dev`
- runs `uv run pi5camera doctor` to verify readiness

If you already have the apt packages installed, skip that step:

```bash
./scripts/bootstrap-rpi-standalone.sh --skip-apt
```

### Step 4. Confirm the CLI is available

```bash
cd ~/pi5camera
uv run pi5camera --help
```

Expected: a help screen listing `camera-tool`, `setup`, `doctor`, `status`,
`capture`, `recognize`, `enroll`, and `manage-faces`.

### Step 5. Confirm the camera hardware is detected

```bash
rpicam-hello --list-cameras
```

Expected: at least one detected camera is listed. If none are listed, check
the ribbon cable connection before continuing.

### macOS development

On macOS, the camera backend is not available. Set the backend to `stub` in
`camera.json` for development and test automation:

```json
{
  "camera": {
    "backend": "stub"
  }
}
```

The `StubCameraBackend` generates placeholder JPEG images so all workflows
(capture, recognition, enrollment) can be tested without hardware.

---

## Getting Started

### Step 1. Open `camera-tool`

```bash
cd ~/pi5camera
uv run pi5camera camera-tool
```

This opens the interactive camera menu with options for setup, readiness
checks, capture, recognition, and face management.

### Step 2. Run the setup wizard

Inside `camera-tool`, choose `1. Run setup wizard`.

Recommended first choices:

- **Photo directory**: keep the suggested path
- **Camera data directory**: keep the suggested path
- **Image width / height**: `1280` × `720`
- **Camera warm-up time**: `1.0`
- **Use camera preview**: `n`
- **Autofocus mode**: `continuous`
- **Recognition tolerance**: `0.6` (lower = stricter)
- **Save crops for unknown faces**: `y`
- **Pending-recognition expiry**: `86400` (24 hours)

This saves `camera.json` and creates `photo/` and `camera_data/` directories.

### Step 3. Run `doctor`

```bash
cd ~/pi5camera
uv run pi5camera doctor
```

This verifies:

- the config file is valid
- storage directories are writable
- `Picamera2` and `MediaPipe`/`OpenCV` are importable

Expected: `pi5camera doctor passed.` or `pi5camera doctor passed with
warnings.`

### Step 4. Capture the first photo

```bash
cd ~/pi5camera
uv run pi5camera capture
```

Expected: a JPEG file is saved under `photo/` and the path is printed.

Optional output path:

```bash
uv run pi5camera capture --output ~/Pictures
```

### Step 5. Run the first recognition cycle

```bash
cd ~/pi5camera
uv run pi5camera camera-tool
```

Choose `5. Recognize faces`. This captures a fresh photo, checks it against
the saved face database, and asks for a name if the face is unknown.

### Step 6. Check current status

```bash
cd ~/pi5camera
uv run pi5camera status
```

Shows the active config, storage paths, resolution, and backend readiness
including whether MediaPipe and OpenCV are available.

---

## Face Recognition Workflow

### Interactive flow from `camera-tool`

1. Run `uv run pi5camera camera-tool`
2. Choose `Recognize faces`
3. If the face is known, the saved name is shown
4. If the face is unknown, enter a name to enroll it

### Direct CLI recognition

```bash
# Live capture + recognition with name prompting
uv run pi5camera recognize --prompt-for-names

# Recognize from an existing image
uv run pi5camera recognize --image-file ~/Pictures/group_photo.jpg
```

### Second-step enrollment

When `recognize` runs without `--prompt-for-names`, unknown faces are saved as
pending records. Enroll them later:

```bash
uv run pi5camera enroll \
  --name Alice \
  --recognition-id <recognition_id> \
  --face-id face-1
```

### Enroll directly from an image

```bash
uv run pi5camera enroll --name Alice --image-file ~/Pictures/alice.jpg
```

### Manage saved identities

```bash
uv run pi5camera manage-faces list
uv run pi5camera manage-faces remove Alice
```

---

## Full Command-Line Reference

### Global option

```bash
uv run pi5camera --config-file /path/to/camera.json <command>
```

### Setup and status

| Command | Purpose |
|---|---|
| `pi5camera setup` | Guided first-run wizard |
| `pi5camera doctor` | Config, directory, and backend readiness check |
| `pi5camera status` | Current config and readiness summary |
| `pi5camera camera-tool` | Beginner-friendly interactive menu |

### Photo capture and recognition

| Command | Purpose |
|---|---|
| `pi5camera capture` | One-shot still photo |
| `pi5camera capture --output <path> --prefix <name>` | Custom output path and filename prefix |
| `pi5camera recognize` | Live or file-based face recognition |
| `pi5camera recognize --prompt-for-names` | Interactive naming for unknown faces |
| `pi5camera recognize --image-file <path>` | Recognize from existing image |

### Enrollment and face management

| Command | Purpose |
|---|---|
| `pi5camera enroll --name <name> --image-file <path>` | Enroll from image |
| `pi5camera enroll --name <name> --recognition-id <id> --face-id <id>` | Enroll from pending result |
| `pi5camera manage-faces list` | Show saved identities |
| `pi5camera manage-faces remove <name>` | Delete one saved identity |

---

## Testing

### Run the full test suite

```bash
cd ~/pi5camera
uv run --extra dev pytest tests -q
```

Expected: all tests pass. The test suite uses `StubCameraBackend` and
monkeypatched recognition backends, so no hardware or heavy dependencies are
required to run tests.

### Quality gate commands

```bash
cd ~/pi5camera
uv run --extra dev python -m compileall src tests
uv run --extra dev ruff check src tests
uv run --extra dev ruff format --check src tests
uv run --extra dev pytest -q tests
```

All four commands must pass before changes are considered ready.

---

## Appendix

### Problem Solving

#### `Picamera2 is not importable`

This usually means `python3-picamera2` is not installed, or the venv was
created without `--system-site-packages`.

Fix:

```bash
sudo apt install -y python3-picamera2 python3-libcamera
cd ~/pi5camera
./scripts/bootstrap-rpi-standalone.sh
```

Or manually:

```bash
cd ~/pi5camera
rm -rf .venv
/usr/bin/python3 -m venv --system-site-packages .venv
source .venv/bin/activate
uv sync --active --frozen --extra dev
```

> **Important:** Always use `uv sync --active --frozen` (not plain `uv sync`)
> after creating a venv with `--system-site-packages`. `--active` preserves
> access to the OS-provided Picamera2/libcamera ABI, and `--frozen` prevents
> dependency drift from rewriting the validated lockfile.

#### `MediaPipe is not installed`

```bash
cd ~/pi5camera
uv run pip install mediapipe
```

Or reinstall the full environment:

```bash
cd ~/pi5camera
./scripts/bootstrap-rpi-standalone.sh --skip-apt
```

#### `OpenCV is not installed`

```bash
cd ~/pi5camera
uv run pip install opencv-python-headless
```

#### `No faces were found`

The image did not contain a clear detectable face. Try:

1. Move into better lighting
2. Keep only one face in the frame
3. Face the camera more directly
4. Rerun: `uv run pi5camera recognize`

#### `Unknown pending recognition`

The pending record expired or the id was incorrect. Rerun recognition to
generate a fresh `recognition_id` and `face_id`.

### Successful Standalone Checklist

Your standalone `pi5camera` setup is healthy when all of these pass:

- `uv run pi5camera doctor` passes with no blocking errors
- `uv run pi5camera status` shows the expected `camera.json`
- `uv run pi5camera capture` saves a photo into `photo/`
- `uv run pi5camera recognize --prompt-for-names` works on a fresh photo
- `uv run pi5camera manage-faces list` shows the saved name
- Rerunning `recognize` returns the saved name for the same person

### How the Default Save Folders Work

Standalone default:

- config: `~/pi5camera/camera.json`
- photos: `~/pi5camera/photo`
- face data: `~/pi5camera/camera_data`

NinjaClawBot workspace default:

- config: `~/NinjaClawBot/camera.json`
- photos: `~/NinjaClawBot/photo`
- face data: `~/NinjaClawBot/camera_data`

Override during setup with absolute paths for a different layout.
