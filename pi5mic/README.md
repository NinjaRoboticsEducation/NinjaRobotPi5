# pi5mic

<div align="center">

**Standalone-First Microphone Tools and Always-On Voice Input for Raspberry Pi 5**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Raspberry Pi 5](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/)

Standalone Raspberry Pi 5 library — see [Installation](#installation) and
[Getting Started](#getting-started) below.

</div>

---

A standalone-first microphone library for Raspberry Pi 5.

`pi5mic` helps a Raspberry Pi 5 record voice, transcribe speech, and optionally
run an always-on wake-word listener. It can work by itself as a local
microphone tool, or it can hand voice requests to an OpenClaw agent inside the
larger NinjaClawBot project.

This package is designed for normal Raspberry Pi users, not only developers.
The safest first path is the standalone workflow. After that works, you can
switch the same microphone setup into OpenClaw mode.

Main functions available today:

- find available microphone devices
- record a WAV audio file
- transcribe speech locally with `whisper.cpp`
- optionally transcribe with Gemini instead
- guide first-time setup with `pi5mic setup`
- provide a beginner-friendly menu with `pi5mic mic-tool`
- run one full record-and-transcribe cycle with `pi5mic run --once`
- register a custom `openWakeWord` model for always-on listening
- start, stop, inspect, and debug the always-on listener with `voiceinput-tool`
- hand transcripts to OpenClaw and optionally mirror replies to Telegram
- show Raspberry Pi microphone, power, and thermal warnings in `pi5mic doctor`

Current project status:

- one-time recording and transcription are ready for standalone and OpenClaw use
- the always-on listener is ready for guided testing and real-device tuning
- long-run Raspberry Pi validation is still recommended before treating the
  always-on path as fully production-ready

This is a standalone library. You do not need NinjaRobotPi5 or NinjaClawBot
after you have obtained a complete copy of this `pi5mic` folder.

---

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Getting Started](#getting-started)
- [Always-On Voice Input](#always-on-voice-input)
- [OpenClaw Mode Testing](#openclaw-mode-testing)
- [Gemini Backend](#gemini-backend)
- [Full Command-Line Reference](#full-command-line-reference)
- [Appendix](#appendix)

---

## Features

| Feature | Description |
|---|---|
| **Standalone-first workflow** | You can install and test `pi5mic` by itself before connecting it to OpenClaw or NinjaClawBot |
| **Microphone discovery** | Lists audio input devices and helps choose a working sample rate |
| **Guided setup** | `pi5mic setup` creates or updates `mic.json` with beginner-friendly prompts |
| **Interactive tools** | Includes `mic-tool` for first-time setup/testing and `voiceinput-tool` for always-on control |
| **Local speech-to-text** | Uses `whisper.cpp` as the default offline transcription backend |
| **Cloud speech-to-text** | Can use Gemini when you prefer cloud transcription and have an API key |
| **Always-on wake-word mode** | Supports a custom `openWakeWord` model for manual start/stop voice listening |
| **OpenClaw handoff** | Can send transcripts into an OpenClaw agent and reuse the main agent conversation |
| **Telegram reply mirroring** | Can ask OpenClaw to reply both locally and in Telegram when Telegram routing is configured |
| **Pi health checks** | `doctor` reports microphone readiness plus Raspberry Pi thermal or power warnings when available |

---

## Architecture

```text
pi5mic/
├── LICENSE
├── pyproject.toml
├── README.md
├── voiceinput/
│   ├── hey_Ninja.onnx           # Example custom wake-word model
│   └── hey_Ninja.tflite         # Example custom wake-word model
├── src/pi5mic/
│   ├── __init__.py
│   ├── __main__.py              # CLI entry point
│   ├── driver.py                # Compatibility re-exports
│   ├── errors.py                # Shared pi5mic exceptions
│   ├── models.py                # Shared config/runtime models
│   ├── cli/
│   │   ├── _common.py           # Shared CLI helpers
│   │   ├── config_cmd.py        # mic.json import/export/show commands
│   │   ├── doctor.py            # Readiness and health checks
│   │   ├── install_cmd.py       # Backend and model registration commands
│   │   ├── mic_tool.py          # Beginner-friendly interactive menu
│   │   ├── run_cmd.py           # One-shot recording/transcription workflow
│   │   ├── setup_cmd.py         # Guided setup wizard
│   │   ├── status.py            # Current config and local readiness summary
│   │   └── voiceinput_tool.py   # Always-on listener controls
│   ├── config/
│   │   └── config_manager.py    # mic.json defaults, load/save, migration
│   ├── core/
│   │   ├── audio_backend.py     # PortAudio/sounddevice loader
│   │   ├── devices.py           # Microphone discovery helpers
│   │   ├── listener.py          # Single-flight conversation state machine
│   │   ├── recorder.py          # WAV capture helpers
│   │   ├── session.py           # Temporary file/session helpers
│   │   ├── system_info.py       # Raspberry Pi health reporting
│   │   └── voiceinput.py        # Always-on wake-word loop
│   ├── install/
│   │   ├── openwakeword.py      # openWakeWord model registration helpers
│   │   └── whisper_cpp.py       # whisper.cpp discovery helpers
│   ├── integration/
│   │   ├── delivery.py          # Reply-target selection helpers
│   │   ├── openclaw_session.py  # OpenClaw session strategy helpers
│   │   ├── openclaw_setup.py    # OpenClaw autodiscovery and readiness checks
│   │   └── presence.py          # Optional OpenClaw presence updates
│   ├── stt/
│   │   ├── base.py              # Speech-to-text interface
│   │   ├── gemini.py            # Gemini backend
│   │   └── whisper_cpp.py       # whisper.cpp backend
│   ├── transport/
│   │   ├── base.py              # Agent transport interface
│   │   └── openclaw_cli.py      # OpenClaw CLI transport
│   ├── vad/
│   │   ├── base.py              # Voice activity interface
│   │   └── silence.py           # Silence-stop detector
│   └── wakeword/
│       ├── base.py              # Wake-word interface
│       └── openwakeword.py      # openWakeWord backend
└── tests/
    ├── test_cli.py
    ├── test_config.py
    ├── test_devices.py
    ├── test_doctor.py
    ├── test_listener.py
    ├── test_mic_tool.py
    ├── test_mic_tool_setup.py
    ├── test_openclaw_session.py
    ├── test_openclaw_setup.py
    ├── test_recorder.py
    ├── test_stt_gemini.py
    ├── test_stt_whisper_cpp.py
    ├── test_system_info.py
    ├── test_transport_openclaw.py
    ├── test_vad.py
    ├── test_voiceinput.py
    ├── test_voiceinput_tool.py
    └── test_wakeword.py
```

---

## Installation

This section is the complete standalone installation path for Raspberry Pi 5.
All standalone examples below assume your working folder is `~/pi5mic`.

If your copy lives somewhere else, replace `~/pi5mic` with your real folder
path in each command.

### Prerequisites

Before you start, make sure you have:

1. A **Raspberry Pi 5** with Raspberry Pi OS Bookworm or newer
2. A **USB microphone or microphone module** that already appears in the system
3. An **internet connection** for the first installation
4. A terminal window with permission to run `sudo`

### Step 1. Obtain and enter the standalone `pi5mic` folder

Ask the project owner for a complete `pi5mic` source folder or source archive,
copy or extract it anywhere you control, then enter that folder:

```bash
cd /path/to/pi5mic
```

What this does:

- starts from one complete standalone `pi5mic` folder
- keeps your microphone config and virtual environment in that folder

What you should expect:

- your terminal ends inside `~/pi5mic`
- later commands create `mic.json` and `.venv` in this standalone folder

This README does not require or assume a Git repository URL or a parent
NinjaRobotPi5/NinjaClawBot checkout.

### Step 2. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

What this does:

- installs `uv`, the tool this project uses to create a virtual environment,
  install Python packages, and run commands

What you should expect:

- the installer finishes without errors
- `uv --version` works in a new shell

> [!NOTE]
> Later examples may show `cd ~/pi5mic`. Replace that path with the actual
> standalone folder you chose in Step 1.

If your shell is not `zsh`, open a new terminal window or load the correct
shell profile for your shell.

### Step 3. Install Raspberry Pi system packages

```bash
sudo apt update
sudo apt install -y \
  git \
  build-essential \
  cmake \
  pkg-config \
  curl \
  ca-certificates \
  libportaudio2 \
  portaudio19-dev \
  python3-dev
```

What this does:

- installs build tools needed for `whisper.cpp`
- installs PortAudio so Python can open your microphone
- installs common system packages used during setup

What you should expect:

- the install finishes without errors
- the common microphone error `PortAudio library not found` should no longer
  appear

Need more detail?

- See [Problem Solving](#problem-solving) if you still get audio-library or
  sample-rate errors later

### Step 4. Install the Python environment

For the full `pi5mic` feature set, including always-on wake-word listening, use:

```bash
cd ~/pi5mic
uv sync --frozen --extra dev --extra voiceinput
```

What this does:

- creates the local `.venv` environment
- installs `pi5mic`
- installs the Gemini SDK used by the optional Gemini backend
- installs `openWakeWord` and its local runtime packages for always-on voice
  input

What you should expect:

- the command finishes successfully
- `uv run pi5mic --help` works afterward

### Step 5. Confirm the command-line tools are available

```bash
cd ~/pi5mic
uv run pi5mic --help
```

What this does:

- confirms that the package installed correctly

What you should expect:

- a help screen that lists commands such as `mic-tool`, `voiceinput-tool`,
  `setup`, `doctor`, `run`, `record`, and `transcribe`

### Step 6. Install the default speech-to-text backend: `whisper.cpp`

```bash
cd ~
git clone https://github.com/ggml-org/whisper.cpp.git
cd ~/whisper.cpp
sh ./models/download-ggml-model.sh base
cmake -B build
cmake --build build -j
```

What this does:

- downloads `whisper.cpp`
- downloads the multilingual `base` model
- builds the `whisper-cli` program used by `pi5mic`

What you should expect:

- a command path like `~/whisper.cpp/build/bin/whisper-cli`
- a model path like `~/whisper.cpp/models/ggml-base.bin`

Need more detail?

- See [What Does `whisper.cpp` Do?](#what-does-whispercpp-do)

### Step 7. Register `whisper.cpp` with `pi5mic`

```bash
cd ~/pi5mic
uv run pi5mic install whispercpp \
  --command ~/whisper.cpp/build/bin/whisper-cli \
  --model-path ~/whisper.cpp/models/ggml-base.bin
```

What this does:

- tells `pi5mic` where `whisper-cli` lives
- tells `pi5mic` where the `ggml-base.bin` model lives
- saves those paths into `mic.json`

What you should expect:

- the resolved command and model paths are printed
- `pi5mic` confirms the settings were saved

Need more detail?

- See [What Does `whisper.cpp` Do?](#what-does-whispercpp-do)

### Step 8. Optional: prepare a Gemini API key

You only need this step if you want to use Gemini instead of `whisper.cpp`.

What a Gemini API key is:

- a private secret, similar to a password
- it allows `pi5mic` to send audio to Google’s Gemini API for transcription
- if you do not want cloud transcription, you can skip this section

How to get one:

1. Open [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Open the API Keys page
4. Create a new Gemini API key or copy an existing one

How to make it available in your current shell:

```bash
export GEMINI_API_KEY="your_key_here"
```

What you should expect:

- there is usually no output
- `pi5mic doctor` can then detect the key

Security note:

- never paste your Gemini API key into Git, GitHub, or `mic.json`
- keep it in your shell environment only

Need more detail?

- See [What Is a Gemini API Key?](#what-is-a-gemini-api-key)

### Step 9. Optional: prepare a custom wake-word model for always-on voice input

You only need this step if you want the always-on listener.

What the wake-word model is:

- a small local AI model file that recognizes the wake phrase, such as
  `hey Ninja`
- this model does **not** transcribe the full command
- it only decides when `pi5mic` should start recording the real voice request

How to get one:

1. Open the official [openWakeWord repository](https://github.com/dscripka/openWakeWord)
2. Go to the `Training New Models` section
3. Use the simple Google Colab notebook if you want the easiest starting path
4. Train or export a custom model for the phrase `hey Ninja`
5. Save the exported file as either `.onnx` or `.tflite`

Recommended standalone folder:

```bash
mkdir -p ~/pi5mic/voiceinput
```

Recommended saved model path:

- `~/pi5mic/voiceinput/hey_Ninja.onnx`
- or `~/pi5mic/voiceinput/hey_Ninja.tflite`

What `.onnx` and `.tflite` mean:

- `.onnx`: a portable AI model format commonly used with ONNX Runtime
- `.tflite`: a portable AI model format commonly used with LiteRT / TensorFlow Lite
- `pi5mic` can use either one
- if you are not sure which to choose, use whichever format your export step
  already created

Need more detail?

- See [What Is the `openWakeWord` API?](#what-is-the-openwakeword-api)
- See [What Are `.onnx` and `.tflite` Files?](#what-are-onnx-and-tflite-files)
- See [How to Create a Custom `hey Ninja` Wake-Word Model](#how-to-create-a-custom-hey-ninja-wake-word-model)

### Step 10. Register the wake-word model with `pi5mic`

Example with `.onnx`:

```bash
cd ~/pi5mic
uv run pi5mic install openwakeword \
  --model-path ~/pi5mic/voiceinput/hey_Ninja.onnx \
  --keyword "hey Ninja"
```

Example with `.tflite`:

```bash
cd ~/pi5mic
uv run pi5mic install openwakeword \
  --model-path ~/pi5mic/voiceinput/hey_Ninja.tflite \
  --keyword "hey Ninja"
```

What this does:

- saves the wake-word model path into `mic.json`
- saves the friendly wake-word label shown in `status` output
- downloads shared `openWakeWord` runtime assets if needed

What you should expect:

- `pi5mic` prints the chosen model path
- `pi5mic` prints which inference framework will be used

Need more detail?

- See [What Are `.onnx` and `.tflite` Files?](#what-are-onnx-and-tflite-files)
- See [How to Create a Custom `hey Ninja` Wake-Word Model](#how-to-create-a-custom-hey-ninja-wake-word-model)

## Getting Started

This section gives the shortest beginner-friendly test path. Use `mic-tool`
first, then move into `voiceinput-tool` after the one-shot recording test
works.

### Step 1. Open `mic-tool`

```bash
cd ~/pi5mic
uv run pi5mic mic-tool
```

What this does:

- opens the guided `pi5mic` menu
- helps you configure and test `pi5mic` without remembering command names

What you should expect:

- a menu with options such as:
  - `Run setup wizard`
  - `Register whisper.cpp`
  - `Run doctor`
  - `Show status`
  - `Run one capture cycle`
  - `Open voiceinput-tool`

### Step 2. Run the setup wizard from `mic-tool`

Choose:

- `1. Run setup wizard`

Recommended choices for the first standalone test:

- `Profile`: `standalone`
- `Input device`: your USB microphone or `default`
- `Sample rate (Hz)`: accept the recommended value
- `STT backend`: `whisper_cpp`
- `whisper.cpp command path`: your `whisper-cli` path
- `whisper.cpp model path`: your `ggml-base.bin` path
- `Maximum clip length`: start with `8`, `10`, or `12`

If you also want to prepare the always-on listener during setup:

- `Prepare always-on voice input now?`: `y`
- `Wake word`: `hey Ninja`
- `openWakeWord model path`: your real `.onnx` or `.tflite` model path
- `Wake-word detection threshold`: `0.5`
- `Wake-word VAD threshold`: `0`
- `Enable openWakeWord noise suppression?`: `n` for the first test
- `openWakeWord inference framework`: `auto`
- `Silence stop timeout`: `3`
- `Maximum recorded command length`: `10`
- `Cooldown`: `1.5`

What this does:

- creates or updates `mic.json`
- saves your microphone, backend, and optional always-on settings

What you should expect:

- `Configured STT backend looks ready.`
- if always-on is enabled, setup reminds you to run `doctor` before starting
  `voiceinput-tool`

Need more detail?

- See [What Does `whisper.cpp` Do?](#what-does-whispercpp-do)
- See [What Is the `openWakeWord` API?](#what-is-the-openwakeword-api)
- See [What Are `.onnx` and `.tflite` Files?](#what-are-onnx-and-tflite-files)

### Step 3. Run `doctor`

Choose:

- `3. Run doctor`

What this does:

- checks your config
- checks microphone access
- checks `whisper.cpp` or Gemini readiness
- checks always-on wake-word readiness if you enabled it

What you should expect:

- many lines starting with `OK`
- then either:
  - `pi5mic doctor passed.`
  - or `pi5mic doctor passed with warnings.`

If you see warnings:

- read them carefully
- common warnings are usually sample-rate suggestions or Raspberry Pi power and
  thermal notes

### Step 4. Run one capture cycle

Choose:

- `5. Run one capture cycle`

What this does:

- records one short clip
- transcribes it
- prints the recognized text

What you should expect:

- `Recording...`
- `Recorded ...`
- `Transcript:`
- your spoken sentence

This is the first proof that your microphone, backend, and config all work
together.

### Step 5. Check the current status

Choose:

- `4. Show status`

What this does:

- shows the current profile, device, sample rate, backend, and service state

What you should expect:

- a short status summary
- if always-on mode is enabled, you should also see the wake word and listener
  service paths

### Step 6. Open `voiceinput-tool`

Choose:

- `6. Open voiceinput-tool`

What this does:

- opens the always-on voice input control menu

What you should expect:

- options to show status, start the background listener, stop it, run it in the
  foreground, and view recent logs

### Step 7. Test always-on voice input safely in foreground mode

Inside `voiceinput-tool`, choose:

- `4. Run listener in foreground`

What this does:

- starts the wake-word listener in the current terminal
- waits for the wake phrase
- after wake-word detection, records one spoken command
- stops recording after 3 seconds of silence or the maximum command length

What you should expect:

- `Starting always-on voice input loop.`
- `Voice input armed ...`
- after you say `hey Ninja`, the terminal should show:
  - `Wake word detected; recording voice command.`
  - `Wake-word capture complete; starting transcription.`
  - `Transcript: ...`

This is the safest first always-on test because you can see the live messages
and stop it with `Ctrl+C`.

Need more detail?

- See [How `pi5mic` Processes a Voice Request](#how-pi5mic-processes-a-voice-request)
- See [Problem Solving](#problem-solving) if foreground mode shows overflow,
  missing transcripts, or model-path errors

### Step 8. Test the background listener

Inside `voiceinput-tool`, choose these in order:

1. `2. Start background listener`
2. `1. Show voice input status`
3. `5. Show recent voice input logs`
4. `3. Stop background listener`

What this does:

- starts the listener in the background
- confirms it is running
- shows the recent log lines
- stops it cleanly when you are done

What you should expect:

- the background listener reports `running`
- the logs show wake-word and transcription events
- the stop action shuts it down cleanly

## Always-On Voice Input

The always-on listener is optional and manual by design.

Important safety and privacy rule:

- `pi5mic` never starts the microphone automatically
- you must start it yourself
- you can stop it yourself at any time

How the always-on loop works:

1. it waits quietly for the wake phrase, such as `hey Ninja`
2. when it hears the wake phrase, it starts recording the command
3. it stops recording after 3 seconds of silence or the maximum command length
4. it transcribes the command with `whisper.cpp` or Gemini
5. in OpenClaw mode, it sends the original-language transcript to the agent
6. it waits for the reply, cools down briefly, and re-arms itself

### Foreground mode

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool foreground
```

What this does:

- starts the always-on listener in the current terminal
- shows live wake-word, recording, transcription, and recovery messages

What you should expect:

- the listener waits for `hey Ninja`
- after detection, it records one command and prints `Transcript: ...`
- you can stop it with `Ctrl+C`

Need more detail?

- See [How `pi5mic` Processes a Voice Request](#how-pi5mic-processes-a-voice-request)

### Background mode

Start it:

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool start
```

Check status:

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool status
```

Show recent logs:

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool logs
```

Stop it:

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool stop
```

What this does:

- starts and stops the manual always-on service
- lets you inspect whether it is armed and where the log file lives

What you should expect:

- the service reports `running` or `stopped`
- the log command shows recent wake-word and transcription events

## OpenClaw Mode Testing

Use this section only after the standalone path already works.

### Step 1. Move to the NinjaClawBot workspace

```bash
cd ~/NinjaClawBot
```

What this does:

- makes `mic.json` live inside the NinjaClawBot project folder
- lets `pi5mic` reuse the same Python environment and local OpenClaw install

### Step 2. Install the Python environment with voice input support

```bash
uv sync --extra dev --extra voiceinput
```

What this does:

- installs `pi5mic`, Gemini support, and `openWakeWord` inside the full
  NinjaClawBot workspace

### Step 3. Make sure OpenClaw is running

Start the OpenClaw services you normally use, especially the gateway.

What you should expect:

- the OpenClaw CLI works
- the gateway is reachable from the same user account that runs `pi5mic`

### Step 4. Run the guided setup in OpenClaw mode

```bash
uv run pi5mic mic-tool
```

Then choose:

- `1. Run setup wizard`

Recommended choices:

- `Profile`: `openclaw`
- `Input device`: your USB microphone or `default`
- `Sample rate (Hz)`: accept the recommended value
- `STT backend`: `whisper_cpp` or `gemini`
- `Voice-input OpenClaw session strategy`: `agent_main`
- `Prepare always-on voice input now?`: `y` if you want the wake-word listener

Why `agent_main` is recommended:

- it sends voice requests into the agent’s normal conversation
- it usually gives the most natural OpenClaw behavior for everyday use

What `pi5mic` now tries to do automatically in OpenClaw mode:

- find the local OpenClaw CLI
- read the local OpenClaw config file
- fill in the gateway URL, agent id, and session details
- detect whether Telegram delivery is configured
- suggest local plus Telegram reply delivery when a Telegram target is known
- repair older session-id values automatically
- run a readiness check after saving the config

Need more detail?

- See [How `pi5mic` Processes a Voice Request](#how-pi5mic-processes-a-voice-request)
- See [Problem Solving](#problem-solving) if OpenClaw later reports pairing,
  session-id, or Telegram delivery problems

### Step 5. If `pi5mic` asks about pairing approval

Sometimes OpenClaw may say `pairing required`.

What this means:

- the microphone setup may already be correct
- OpenClaw created a local device request that still needs approval

What to do:

- answer `y` if you trust this local Raspberry Pi session
- `pi5mic` then tries to approve the newest local request automatically

### Step 6. Run the OpenClaw health test

```bash
uv run pi5mic doctor
```

What this does:

- checks the microphone and STT path
- checks the OpenClaw command and config path
- checks whether replies are local only or local plus Telegram

What you should expect:

- `OK` lines for the OpenClaw command and config
- `OK` or `INFO` lines for Telegram routing if available
- sometimes a warning about degraded presence support; that warning does not
  always mean voice handoff is broken

Need more detail?

- See [Problem Solving](#problem-solving)

### Step 7. Test one OpenClaw voice turn

```bash
uv run pi5mic run --once
```

What this does:

- records one clip
- transcribes it
- sends it to the OpenClaw agent

What you should expect:

- the recognized transcript is printed
- the OpenClaw reply is printed
- if Telegram mirroring is enabled, the same reply should also appear in the
  configured Telegram chat or topic

### Step 8. Test always-on OpenClaw listening

```bash
uv run pi5mic voiceinput-tool foreground
```

What this does:

- starts the wake-word listener while still using the OpenClaw profile
- after `hey Ninja`, it records and sends the spoken request to OpenClaw

What you should expect:

- one request is processed at a time
- while OpenClaw is still replying, new wake-word hits are ignored on purpose
- after the reply finishes, the listener re-arms itself for the next wake word

Need more detail?

- See [How `pi5mic` Processes a Voice Request](#how-pi5mic-processes-a-voice-request)
- See [Problem Solving](#problem-solving)

## Gemini Backend

Gemini is the optional cloud speech-to-text backend.

Use Gemini when:

- you want cloud transcription instead of `whisper.cpp`
- you already have a Gemini API key
- your network connection is stable

Keep `whisper.cpp` when:

- you want local offline transcription
- you do not want to depend on a cloud API
- you want the simplest Raspberry Pi setup

### Switch `pi5mic` to Gemini

```bash
cd ~/pi5mic
export GEMINI_API_KEY="your_key_here"
uv run pi5mic setup
```

Choose:

- `STT backend`: `gemini`
- `Gemini model id`: keep the suggested default unless you have a reason to change it
- `Gemini timeout` and `retry limit`: keep the suggested defaults for the first test

Need more detail?

- See [What Is a Gemini API Key?](#what-is-a-gemini-api-key)

### Verify the Gemini path

```bash
cd ~/pi5mic
uv run pi5mic doctor
```

What you should expect:

- `INFO active STT backend: gemini`
- `OK   Gemini credentials found in environment (...)`

## Full Command-Line Reference

This section shows the direct command-line version of each main function.

### Setup and status

```bash
cd ~/pi5mic
uv run pi5mic setup
```

Runs the guided setup wizard and writes `mic.json`.

```bash
cd ~/pi5mic
uv run pi5mic mic-tool
```

Opens the beginner-friendly menu for setup and first testing.

```bash
cd ~/pi5mic
uv run pi5mic status
```

Shows the current profile, device, backend, and always-on service state.

```bash
cd ~/pi5mic
uv run pi5mic doctor
```

Checks microphone readiness, backend readiness, and optional OpenClaw readiness.

### Device discovery and recording

```bash
cd ~/pi5mic
uv run pi5mic devices
```

Lists the available microphone devices.

```bash
cd ~/pi5mic
uv run pi5mic record --duration 3 --output mic-test.wav
```

Records a 3-second WAV file without transcription.

```bash
cd ~/pi5mic
uv run pi5mic run --once
```

Runs one full live capture and transcription cycle.

```bash
cd ~/pi5mic
uv run pi5mic run --once --keep-audio
```

Runs one full live capture and keeps the temporary WAV file for debugging.

```bash
cd ~/pi5mic
uv run pi5mic run --once --audio-file ./mic-test.wav
```

Skips the microphone and transcribes an existing WAV file instead.

### Speech-to-text backends

```bash
cd ~/pi5mic
uv run pi5mic transcribe mic-test.wav
```

Transcribes an existing WAV file through the configured backend.

```bash
cd ~/pi5mic
uv run pi5mic transcribe --backend whisper_cpp mic-test.wav
```

Forces `whisper.cpp` for this transcription only.

```bash
cd ~/pi5mic
uv run pi5mic transcribe --backend gemini mic-test.wav
```

Forces Gemini for this transcription only.

### Install or register backend assets

```bash
cd ~/pi5mic
uv run pi5mic install whispercpp \
  --command ~/whisper.cpp/build/bin/whisper-cli \
  --model-path ~/whisper.cpp/models/ggml-base.bin
```

Registers the local `whisper.cpp` command and model.

```bash
cd ~/pi5mic
uv run pi5mic install openwakeword \
  --model-path ~/pi5mic/voiceinput/hey_Ninja.onnx \
  --keyword "hey Ninja"
```

Registers the wake-word model and optional runtime assets.

### Config file management

```bash
cd ~/pi5mic
uv run pi5mic config show
```

Prints the current `mic.json`.

```bash
cd ~/pi5mic
uv run pi5mic config export ./mic-backup.json
```

Saves a backup copy of the current config.

```bash
cd ~/pi5mic
uv run pi5mic config import ./mic-backup.json
```

Loads a saved config file back into the active config path.

### Always-on voice input control

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool foreground
```

Runs the always-on listener in the current terminal for debugging.

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool start
```

Starts the always-on listener in the background.

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool status
```

Shows whether the background listener is running and where its files live.

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool logs
```

Shows recent log lines from the background listener.

```bash
cd ~/pi5mic
uv run pi5mic voiceinput-tool stop
```

Stops the background listener.

## Appendix

Use this appendix when you want more detail behind the setup steps above.

### Appendix Contents

- Use these links when you want more explanation while following the setup and
  testing steps above.

- [Problem Solving](#problem-solving) - use this when a setup or test step shows an error
- [Successful Standalone Checklist](#successful-standalone-checklist)
- [Successful Standalone Checklist](#successful-standalone-checklist) - use this after the first standalone test flow
- [What Is a Gemini API Key?](#what-is-a-gemini-api-key) - supports Installation Step 8 and Gemini Backend
- [What Is the `openWakeWord` API?](#what-is-the-openwakeword-api) - supports Installation Steps 9-10 and always-on setup
- [What Does `whisper.cpp` Do?](#what-does-whispercpp-do) - supports Installation Steps 6-7 and one-shot transcription
- [What Are `.onnx` and `.tflite` Files?](#what-are-onnx-and-tflite-files) - supports Installation Steps 9-10 and wake-word model setup
- [How to Create a Custom `hey Ninja` Wake-Word Model](#how-to-create-a-custom-hey-ninja-wake-word-model) - supports Installation Steps 9-10
- [How `pi5mic` Processes a Voice Request](#how-pi5mic-processes-a-voice-request) - supports always-on testing and OpenClaw mode
- [Developer Validation Commands](#developer-validation-commands) - for contributors and local package verification

### Problem Solving

#### `PortAudio library not found`

Cause:

- the Raspberry Pi system audio libraries are missing

Fix:

```bash
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev python3-dev
```

#### `Invalid sample rate`

Cause:

- your microphone does not accept the saved sample rate

Fix:

```bash
cd ~/pi5mic
uv run pi5mic setup
```

Then keep the same microphone and accept the sample rate recommended by the
wizard.

#### `openWakeWord model file not found`

Cause:

- the saved wake-word model path is wrong
- or the file was moved or deleted

Fix:

```bash
cd ~/pi5mic
uv run pi5mic install openwakeword \
  --model-path ~/pi5mic/voiceinput/hey_Ninja.onnx \
  --keyword "hey Ninja"
```

Use the full real file path. Do not enter only `.onnx` or `.tflite`.

#### `Gemini credentials are not configured`

Cause:

- the Gemini API key is missing from the current shell

Fix:

```bash
export GEMINI_API_KEY="your_key_here"
cd ~/pi5mic
uv run pi5mic doctor
```

#### `pairing required` in OpenClaw mode

Cause:

- OpenClaw created a local device request that still needs approval

Fix:

- rerun `pi5mic setup` or `pi5mic mic-tool`
- approve the newest local request if `pi5mic` asks

#### OpenClaw replies stay local instead of Telegram

Cause:

- OpenClaw voice handoff is working, but no usable Telegram reply target is
  saved yet

Fix:

```bash
cd ~/NinjaClawBot
uv run pi5mic setup
```

Then:

- choose `Profile: openclaw`
- send one short message to your OpenClaw bot in the Telegram chat or topic you
  want to use
- answer `y` if setup asks whether it should reply both locally and in Telegram

#### `Invalid session ID` in OpenClaw mode

Cause:

- an older config or older OpenClaw session value is being used

What `pi5mic` does now:

- it repairs older session values automatically during setup and config save paths

What to do:

```bash
cd ~/NinjaClawBot
uv run pi5mic setup
uv run pi5mic doctor
```

Then rerun your OpenClaw test.

#### Raspberry Pi powers off or reboots during local Whisper transcription

Cause:

- the Raspberry Pi may be hitting a power, temperature, or memory limit

What to do:

```bash
cd ~/pi5mic
uv run pi5mic doctor
vcgencmd get_throttled
vcgencmd measure_temp
```

Then:

- use a known-good Raspberry Pi 5 power supply
- improve cooling
- shorten the maximum clip length
- lower `whisper.cpp` thread count
- or switch to Gemini if local transcription is too heavy for your hardware

#### audio overflow warnings during foreground listening

What it means:

- the microphone stream fell behind briefly

What `pi5mic` does now:

- it tries to recover automatically
- if overflow repeats, it recreates the monitoring stream and keeps listening

What you can still do:

- keep the first test command short
- raise the wake-word threshold slightly if false triggers are common
- use foreground mode first when tuning a new microphone

### Successful Standalone Checklist

Your standalone setup is in good shape if all of these work:

1. `uv run pi5mic --help`
2. `uv run pi5mic devices`
3. `uv run pi5mic doctor`
4. `uv run pi5mic record --duration 3 --output mic-test.wav`
5. `uv run pi5mic transcribe mic-test.wav`
6. `uv run pi5mic run --once`
7. `uv run pi5mic voiceinput-tool foreground`

### What Is a Gemini API Key?

Related setup step:

- [Installation > Step 8](#step-8-optional-prepare-a-gemini-api-key)

A Gemini API key is a secret string that allows your Raspberry Pi to call the
Gemini Developer API. `pi5mic` only needs it when you choose the Gemini backend.

Think of it like this:

- `whisper.cpp` works with local files on your Raspberry Pi
- Gemini works by sending audio to Google’s cloud API
- the API key proves that your request belongs to your Google account

### What Is the `openWakeWord` API?

Related setup step:

- [Installation > Step 9](#step-9-optional-prepare-a-custom-wake-word-model-for-always-on-voice-input)

`openWakeWord` is the wake-word engine used by the current `pi5mic` always-on
listener.

In simple terms:

- it listens to short pieces of microphone audio
- it compares those short audio pieces against a wake-word model
- when the score is high enough, it tells `pi5mic` that the wake phrase was detected

In the Python API, the main object is the `Model` class. `pi5mic` loads your
custom model file and feeds it `16 kHz` audio frames until it detects the wake
phrase.

Important difference:

- `openWakeWord` decides **when to start recording**
- it does **not** turn the full spoken command into text
- `whisper.cpp` or Gemini still do the real transcription afterward

### What Does `whisper.cpp` Do?

Related setup steps:

- [Installation > Step 6](#step-6-install-the-default-speech-to-text-backend-whispercpp)
- [Installation > Step 7](#step-7-register-whispercpp-with-pi5mic)

`whisper.cpp` is the default local speech-to-text engine used by `pi5mic`.

In simple terms:

- `pi5mic` records your speech into a WAV file
- `whisper.cpp` reads that WAV file
- it returns the recognized text

Why it is the default:

- it works offline
- it does not require a cloud API key
- it is practical on Raspberry Pi 5 with the `base` model

### What Are `.onnx` and `.tflite` Files?

Related setup step:

- [Installation > Step 9](#step-9-optional-prepare-a-custom-wake-word-model-for-always-on-voice-input)

These are both file formats for local AI models.

Simple explanation:

- `.onnx` is a common model format often used with ONNX Runtime
- `.tflite` is a common model format often used with LiteRT / TensorFlow Lite

For `pi5mic`, the practical rule is:

- use the real file that your `openWakeWord` training or export step gave you
- keep the `openWakeWord inference framework` option at `auto` unless you are
  troubleshooting a runtime problem

### How to Create a Custom `hey Ninja` Wake-Word Model

Related setup steps:

- [Installation > Step 9](#step-9-optional-prepare-a-custom-wake-word-model-for-always-on-voice-input)
- [Installation > Step 10](#step-10-register-the-wake-word-model-with-pi5mic)

Recommended beginner path:

1. Open the official [openWakeWord repository](https://github.com/dscripka/openWakeWord)
2. Open the `Training New Models` section
3. Launch the recommended Google Colab notebook
4. Set the target phrase to `hey Ninja`
5. Run the notebook until it exports a model file
6. Download the exported `.onnx` or `.tflite` file
7. Copy that file into `~/pi5mic/voiceinput/`
8. Register it with:

```bash
cd ~/pi5mic
uv run pi5mic install openwakeword \
  --model-path ~/pi5mic/voiceinput/hey_Ninja.onnx \
  --keyword "hey Ninja"
```

After that, run:

```bash
cd ~/pi5mic
uv run pi5mic doctor
uv run pi5mic voiceinput-tool foreground
```

### How `pi5mic` Processes a Voice Request

There are two main flows:

#### One-time recording

1. you start `run --once` or choose `Run one capture cycle`
2. `pi5mic` records one short clip
3. `whisper.cpp` or Gemini transcribes it
4. the text is printed locally
5. in OpenClaw mode, the text is also sent to the OpenClaw agent

#### Always-on listening

1. you start `voiceinput-tool`
2. `openWakeWord` watches for `hey Ninja`
3. once detected, `pi5mic` records the spoken command
4. silence detection decides when the command ends
5. `whisper.cpp` or Gemini transcribes the command
6. if the profile is `openclaw`, `pi5mic` sends the original-language text to OpenClaw
7. `pi5mic` waits for the reply, cools down briefly, and re-arms itself

### Developer Validation Commands

These commands are mainly for contributors, but they are also useful when you
want to confirm the package still passes its local checks after an update.

```bash
cd ~/pi5mic
uv run --extra dev python -m compileall src tests
uv run --extra dev ruff check src tests
uv run --extra dev ruff format --check src tests
uv run --extra dev pytest -q tests -c pyproject.toml
```
