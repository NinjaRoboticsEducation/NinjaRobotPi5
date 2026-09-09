# NinjaRobotPi5 Installation Guide

## Phase 3 checkpoint — 9 September 2026

Spoken replies and coordinated output are implemented and software-tested.
Development pauses before Phase 4 for the owner's manual acceptance. The owner
reports completing the Phase 2 manual tests and wiki maintenance; this is an
owner report, not a physical test performed by the coding agent.

The Phase 3 software gate passes 772 tests, lint, formatting, type checks,
compilation, JavaScript syntax and both driver verifiers. No managed driver
changed: 222 files across six drivers retain the baseline plus 56 authorized
repairs. Face cleanup was approved and implemented previously; the separate
Traditional Chinese font proposal and monetary-cap decision remain pending.

Use the [Phase 3 walkthrough](../../../../../docs/validation/refinement_phase3_walkthrough_260909.md)
for setup, expected results, privacy, safety and rollback. This source version
supersedes the checkpoint wording below. It is prepared for later wiki ingestion;
the owner asked to skip ingestion and review workflows during this task.
The existing hardware ownership boundary remains intact; IDE-owned OS audio is
an optional output, not a new Agent hardware-access path.

### Optional local spoken output

Use the walkthrough's ordered steps: create an isolated Python 3.11 Piper
1.8.0 environment from `requirements/local-speech.txt`, preview and explicitly
apply `scripts/prepare_speech_voice.py`, pair the Bluetooth speaker in the OS,
select its exact PipeWire node from `/speech outputs`, and update only the
`[speech_output]` table in private configuration. Restart under the existing
hardware safety conditions. Start disabled; `/speech on` opts into audible replies.
No installation, pairing, service change or audio test was performed automatically.
The English download is explicitly 114 MB. Its source revision and hashes are
pinned, existing files are preserved, and failed downloads can be retried.

Piper processes text locally; conversation-provider costs are unchanged. Mandarin
accepts an operator-supplied compatible model with suitable usage terms; no Chinese
model is installed automatically. Japanese speech is not part of this phase.
A boot service must independently pass the speaker visibility and audibility
checks. Pairing from a desktop does not establish that a headless service can use it.

### Check the environment before starting devices

From the repository root, inspect the installed environment without opening
hardware:

```bash
uv run --frozen --no-sync ninjarobot_pi5_cli doctor --profile hardware --root .
```

Expected: missing modules, wrong checkout origins and optional dependencies are
explained. This is package discovery, not physical health. Use the existing
installation steps to repair missing hardware packages in the correct environment;
do not bypass safety checks when `pi5disp` or another driver is missing.

Hardware installation remains the default profile in `.venv`. The explicit
`./install.sh --profile development` profile uses `.venv-dev` and does not install
hardware prerequisites. A development environment cannot operate the robot merely
because its software tests pass. Installer check/preview remains available; no
installer or deployment was run for this refinement. Pinned installer inputs and
remaining downstream download limits are recorded in
[installer provenance](../../../../../docs/validation/refinement_installer_provenance_260908.md).
Ambiguous boot settings are refused for manual review rather than rewritten by guesswork.

### Try the local task assistant

Use the walkthrough above. In an existing Agent chat, `/remind 120 Practice`
creates a silent draft. Read the returned exact time and effect, then type
`/tasks confirm TASK_ID` using its real identifier. `/tasks` or the browser's
Local tasks panel shows the result. Snooze creates a new draft that requires
confirmation. A saved reminder does not depend on a cloud model, but it does
require the Pi and service to stay running. Normal chat still uses the selected
model and may incur provider charges.

Use `/remind-json` for an exact dated reminder, daily/weekly repeat, or an
explicitly reviewed display-and-buzzer notification. Missing offsets and past or
invalid local times are refused. Reminders more than 60 seconds overdue are
marked missed; interrupted deliveries are uncertain and are not automatically
retried. The default notice is only in the local task inbox, with no sound.

Use `/memory review`, `/memory confirm ID`, `/memory edit ID NEW TEXT` and
`/memory forget ID` to inspect and correct your active profile's preferences.
Do not reset real data to test these commands. Finished tasks follow conversation
retention (seven days by default); active repeating reminders persist until cancelled.

Starting/restarting the real Agent may activate configured devices and voice
input. Raise wheels and obtain capture consent before that manual operation.
The guide menu itself only inspects software; it does not automatically run its
suggested device checks. Traditional Chinese display-font repair remains pending;
an ASCII reminder test does not validate that font.

> [!IMPORTANT]
> **v1.0.0 is validated on the reference Raspberry Pi 5 robot.** Every new
> build still needs its own calibration and raised-wheel acceptance because
> wiring, servo neutral points, microphones, cameras, and power boards vary.

This guide takes you from a blank Raspberry Pi to a fully calibrated, running robot. Follow the numbered steps in order. The testing, troubleshooting, and extension sections at the end are available whenever you need them.

NinjaRobotPi5 combines six Raspberry Pi hardware drivers with a deterministic
robot IDE, a persistent multi-user AI agent, local/cloud model providers,
always-on “Hey Ninja” input, a multilingual HTTPS controller, optional ngrok
access, and opt-in boot startup. This document is the beginner-facing source of
truth for installing all of those parts. Commands marked **one-time setup** are
run once; daily use happens through `ninjarobot-ide-tool` and
`ninjarobot-agent` after activating the project environment.

---

## Before you begin

### Hardware you need

| Item | Notes |
|---|---|
| Raspberry Pi 5 (4 GB or 8 GB) | 8 GB recommended for local AI |
| microSD card (16 GB minimum) or NVMe SSD | 32 GB or larger recommended |
| Active cooler | Required for sustained AI inference |
| DFRobot DFR0566 expansion board | Provides PWM and I2C expansion |
| Two MG90D 360° continuous-rotation servos | GPIO12 (left) and GPIO13 (right) |
| Passive buzzer | GPIO27 |
| VL53L0X distance sensor | I2C bus 1, address 0x29 |
| ST7789V display (240×320) | SPI0, DC GPIO4, RST GPIO5, BL GPIO6 |
| Raspberry Pi CSI camera (OV5647) | Flat-ribbon connection |
| USB microphone | Any USB audio input device |
| Official 27 W USB-C power supply | Plus Geekworm X1208 power chain |
| Another computer | For writing the OS image and SSH access |
| microSD card reader | To write the OS image |

#### Geekworm X1208 power installation

1. Assemble the X1208 with the Pi completely disconnected from power.
2. Install the supplied pogo pin so it makes firm contact with the Raspberry Pi
   5 `PSW` through-hole. This carries the Pi power-button/detection signal.
3. Connect the 27 W, 5 V/5 A supply to the **X1208 USB-C input only**. Do not
   simultaneously power the Raspberry Pi 5 USB-C socket.
4. Confirm the Pi, X1208 40-pin header, spacers, battery, and NVMe cable are
   seated exactly as shown in the [official X1208 guide](https://wiki.geekworm.com/X1208).

The X1208 automatically removes its 5 V output after it detects a completed Pi
5 shutdown. NinjaRobot therefore uses the standard operating-system power-off
path; it does not need an additional UPS-specific power-cut script.

### Safety rules — read these first

> [!CAUTION]
> Follow these rules every time you work with the robot.
>
> 1. **Raise the wheels before any movement test.** The robot currently has no accessible physical servo cutoff.
> 2. **Never change wiring while power is on.**
> 3. **Obtain consent from everyone nearby before any camera or microphone test.**
> 4. **Never expose port 8443 to the internet** or configure router port forwarding.
> 5. **Stop the agent service before opening standalone hardware tools.**

---

## Project file layout

After installation, the important folders are:

```text
NinjaRobotPi5/
├── ninjarobot_pi5_ide/       Robot hardware coordinator and safety layer
├── ninjarobot_pi5_agent/     AI agent, web controller, CLI, MCP, and skills
├── pi5buzzer/                Standalone buzzer library
├── pi5camera/                Standalone camera library
├── pi5disp/                  Standalone display library
├── pi5mic/                   Standalone microphone library
├── pi5servo/                 Standalone servo library
├── pi5vl53l0x/               Standalone distance-sensor library
├── config/                   Safe example robot configuration
├── scripts/                  Setup and validation helpers
└── docs/validation/          Phase-by-phase hardware test checklists
```

Your personal settings and captured media are stored **outside** the project folder, so Git updates never touch them:

```text
~/.config/pi5*/                    Standalone module settings (JSON)
~/.config/ninjarobot_pi5/          Integrated robot settings (TOML) and behaviors
~/.local/share/ninjarobot_pi5/     Retained camera/microphone media, conversation database, and benchmarks
~/.local/state/ninjarobot_pi5/     Safety state, service log, IPC socket, lock, and action ledger
```

`~` means your Linux home directory, for example `/home/rogerchang`.

---

## Installation steps

### Step 1 — Install Raspberry Pi OS on your Pi

You need another computer and a microSD card reader for this step.

1. Download and open [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on your other computer.
2. Select **Raspberry Pi 5** as the device.
3. Select **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)**.

   > [!TIP]
   > The Lite version has no graphical desktop. This leaves more memory and processing power available for robot control and local AI models.

4. Select your microSD card.
5. Open the **OS customisation** screen and set:
   - Hostname — for example, `ninjarobotpi5`
   - Your username and a strong password
   - Your Wi-Fi name, password, and country
   - Your time zone and keyboard layout
   - Enable SSH

6. Write the image. **This erases everything on the selected card.**
7. With the Pi powered off, insert the card and check all wiring.
8. Apply power and wait about two minutes for the first boot.

**Connect from your other computer:**

```bash
ssh YOUR_USERNAME@ninjarobotpi5.local
```

If `.local` name discovery does not work, find the Pi's IP address in your router and use:

```bash
ssh YOUR_USERNAME@RASPBERRY_PI_IP_ADDRESS
```

All remaining commands in this guide run in this SSH terminal.

---

### Step 2 — Update Raspberry Pi OS and enable interfaces

Update the operating system before installing NinjaRobotPi5:

```bash
sudo apt update
sudo apt full-upgrade -y
```

Open the Raspberry Pi configuration tool:

```bash
sudo raspi-config
```

Choose **Interface Options**, enable **I2C**, and then enable **SPI**. I2C is
used by the distance sensor and SPI is used by the display. Finish and return
to the terminal. Do not manually install the remaining system packages or edit
the PWM overlay; the project installer performs those steps consistently.

### Step 3 — Clone and run the project installer

Install Git, clone the current public branch, and enter the repository:

```bash
sudo apt install -y git
git clone https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git
cd NinjaRobotPi5
```

Preview the installation without changing the Raspberry Pi:

```bash
./install.sh --dry-run
```

Review the displayed actions, then run the installer:

```bash
./install.sh
```

The installer asks for confirmation and then:

- installs the required Raspberry Pi OS packages, including Picamera2,
  libcamera, ALSA, PortAudio, build tools, and mDNS support;
- installs the project-tested `uv` and Ollama releases from their official
  installation scripts;
- enables the Ollama system service without downloading an AI model;
- checks out the tested `whisper.cpp` commit in `~/whisper.cpp`, builds
  `whisper-cli`, and downloads the multilingual `base` speech model;
- backs up `/boot/firmware/config.txt`, disables onboard audio, and adds the
  exact two-channel hardware-PWM overlay for GPIO12 and GPIO13;
- creates private NinjaRobotPi5 configuration directories;
- installs the locked Python environment with the Raspberry Pi hardware extra;
- validates the bounded system-Python Picamera2 bridge; and
- verifies the six managed driver source and provenance records.

Pinned installer versions are recorded in `scripts/install-versions.env` for
repeatable maintenance. Existing healthy installations and the managed boot
block are reused, making the installer safe to rerun. It refuses unsupported
platforms or conflicting unmanaged PWM overlays instead of guessing.

> [!IMPORTANT]
> The installer never downloads an Ollama model, starts NinjaRobotAgent,
> deploys boot startup, opens a camera or microphone, or activates a motor.

Reboot so the PWM overlay takes effect:

```bash
sudo reboot
```

Reconnect, enter the repository, and run the read-only readiness check:

```bash
ssh YOUR_USERNAME@ninjarobotpi5.local
cd "$HOME/NinjaRobotPi5"
./install.sh --check
```

Expected result: every prerequisite is reported as ready. If a check fails,
the message identifies the missing package, interface, file, or command. See
[Installer troubleshooting](#installer-troubleshooting) before continuing.

Activate the project environment. Repeat this after each new SSH login:

```bash
source .venv/bin/activate
```

Download at least one local AI model manually. This choice is intentionally not
made by the installer because model size and performance depend on your Pi:

```bash
ollama pull qwen3:4b
ollama list
```

The model download is about 2.3 GB. The model becomes accepted for robot use
only after its benchmark passes in Step 7.

> [!NOTE]
> It is normal for `.venv/bin/python -c "import picamera2"` to fail.
> Apt-managed Picamera2 is isolated from the project environment, and
> NinjaRobotPi5 deliberately accesses it through the bounded `/usr/bin/python3`
> camera bridge.

---

### Step 4 — Initialize and calibrate each hardware module

> [!IMPORTANT]
> This step creates configuration files in `~/.config/pi5*`. The standalone
> tools now choose those paths automatically, so routine commands do not need
> `--config` or `-C` arguments and never dirty the Git checkout.

The installer has already created the private configuration folders and
supplied the Python packages
for every managed library. The OS packages and interfaces each module also
needs are:

| Module | Extra requirement | Why |
|---|---|---|
| `pi5buzzer` | GPIO access; `swig` and `python3-dev` are build fallbacks | Passive PWM tone on GPIO27 |
| `pi5disp` | SPI enabled | ST7789V display on SPI0 |
| `pi5vl53l0x` | I2C enabled; `i2c-tools` | VL53L0X at address `0x29` |
| `pi5servo` | PWM overlay, external servo power, common ground | Continuous servos on GPIO12/13 |
| `pi5camera` | `python3-picamera2`, `python3-libcamera` | CSI capture through Raspberry Pi OS bindings |
| `pi5mic` | ALSA, PortAudio, whisper.cpp | USB capture, local transcription, wake-word listener |

Do not install a second PyPI `picamera2` or `libcamera` into `.venv`. Do not
install multiple OpenCV wheel variants: the project lock supplies the supported
OpenCV 4 face-recognition API.

> [!CAUTION]
> Raise both wheels off the work surface before any step that may activate the servos. Keep hair, hands, cables, and loose objects clear.

---

#### 4.1 — Buzzer (GPIO27)

```bash
pi5buzzer buzzer-tool
```

Choose **Init** and press Enter to keep GPIO27. Use the menu to play a short
tone or melody. Exit after confirming the buzzer sounds and becomes silent.

---

#### 4.2 — Display (ST7789V)

```bash
pi5disp display-tool
```

Choose **Init** and press Enter at each prompt to accept the NinjaRobotPi5
defaults:

| Prompt | Value |
|---|---:|
| Width | `240` |
| Height | `320` |
| DC pin | `4` |
| Reset pin | `5` |
| Backlight pin | `6` |
| Rotation | `90` |
| Brightness | `75` |
| SPI speed | `32` MHz |

Then choose **Show Text**, **Brightness**, and **Clear** to confirm the screen works correctly. After the configured 90° rotation, the visible drawing area is 320×240 (landscape orientation).

---

#### 4.3 — Distance Sensor (VL53L0X)

```bash
pi5vl53l0x sensor-tool
```

Use the menu to check status and take several readings. Place a flat object in front of the sensor to verify distance accuracy.

> [!NOTE]
> The raw value `8191` means no target is measurable in range. This proves the sensor is communicating but does not mean an error. A `null` result indicates a real communication problem (timeout, disconnect, or stale reading) and needs investigation.

Calibrate only after ordinary readings work. Place a flat target at a known distance and follow the calibration prompts.

---

#### 4.4 — Wheel Servos (GPIO12 and GPIO13)

> [!CAUTION]
> Servo calibration moves the motors. Raise both wheels, keep all body parts and loose objects clear, and be ready to remove robot power. This robot has no accessible physical servo cutoff — software stop reduces risk but cannot remove all electrical risk.

```bash
pi5servo servo-tool
```

In the menu:

1. Choose **Calibrate**.
2. Enter `gpio12`.
3. Find and save the neutral point at which the left wheel stops turning.
4. Repeat for `gpio13` (right wheel).
5. Choose **Status** to confirm both calibration records are stored.
6. Run a low-speed **Quick Move** or **Single Move** test.
7. Return both motors to neutral and exit.

For these MG90D continuous-rotation servos, the calibrated center is the stop position. The exact neutral pulse differs between individual motors of the same model.

**Verify the saved calibrations without moving:**

```bash
pi5servo calib --show
```

Expected result: both `gpio12` and `gpio13` are listed. If the result says `No calibrations stored`, see [Servo calibration saved to wrong file](#servo-calibration-saved-to-the-wrong-file).

---

#### 4.5 — Camera (Raspberry Pi CSI)

> [!CAUTION]
> Tell everyone nearby before taking or retaining a photograph. Obtain their consent first.

```bash
pi5camera camera-tool
```

Choose **Run setup wizard**. Press Enter to accept the current OV5647 camera
defaults:

- Width: `1280`
- Height: `720`
- Warm-up time: `1.0`
- Autofocus mode: `none`
- No preview (headless system)

Then choose **Run doctor** and **Show status** to verify the camera is ready. Take a test photograph only after everyone nearby agrees.

---

#### 4.6 — USB Microphone

**Check that Linux sees the microphone:**

```bash
arecord -l
```

Expected result: your USB microphone is listed as a capture device.

**Open the microphone tool:**

```bash
pi5mic mic-tool
```

Choose **Run setup wizard**, select your USB microphone, and accept a supported
sample rate. The wizard detects these installed defaults:

- whisper.cpp command: `~/whisper.cpp/build/bin/whisper-cli`
- whisper.cpp model: `~/whisper.cpp/models/ggml-base.bin`
- wake model: the bundled `pi5mic/voiceinput/hey_Ninja.onnx`
- maximum wake-command duration: `15` seconds, ending early after silence

Then choose **Run doctor** and **Show status**. Recording and speech-to-text
tests are in [Microphone test](#microphone-test) because they require consent.

> [!NOTE]
> If the tool selects 44.1 kHz when you configured 16 kHz, this is normal.
> Some USB microphones do not support 16 kHz, and the robot handles this
> fallback automatically. Do not copy the wake model into the IDE package; the
> approved packaged IDE copy is already installed and checksum-protected.
---

### Step 5 — Import settings into the integrated robot configuration

The NinjaRobotPi5 IDE reads its own unified configuration file, separate from the individual module JSON files. This step copies the relevant settings from Steps 4.1–4.6 into that unified file.

> [!Important]
> The import is one-way and read-only. The IDE never rewrites the standalone `pi5*` JSON files, and the standalone tools never rewrite the integrated `config.toml`.

**Check which standalone files the IDE finds:**

```bash
ninjarobot-ide-tool config discover
```

Expected result: all six entries show the canonical files created in Step 4.

**Preview the import (nothing is written yet):**

```bash
ninjarobot-ide-tool config import
```

The preview intentionally shows `"applied": false`. This is not an error — it means the file has not been written yet. Confirm the preview shows:

- Buzzer on GPIO27
- Display with DC GPIO4, RST GPIO5, BL GPIO6, rotation 90, brightness 75
- Servo calibration path: `/home/YOUR_USERNAME/.config/pi5servo/servo.json`
- Camera profile (1280×720, autofocus `none`)
- Microphone profile (USB device, sample rate)

**Apply the reviewed settings:**

```bash
ninjarobot-ide-tool config import --apply
```

> [!NOTE]
> The first import does not overwrite an existing file. If the destination already exists, use the synchronization procedure in the [Appendix](#synchronize-changed-module-settings-with-the-ide).

The generated configuration enables calibrated direct movement by default and
stores the expanded servo calibration path, for example:

```toml
[hardware.servos]
enabled = true
endpoints = ["gpio12", "gpio13"]
calibration_file = "/home/YOUR_USERNAME/.config/pi5servo/servo.json"
motion_enabled = true
group_motion_enabled = true

[behaviors]
left_motor_role = "left_motor"
right_motor_role = "right_motor"
obstacle_threshold_mm = 50
obstacle_consecutive_readings = 3

[behaviors.servo_roles]
left_motor = "gpio12"
right_motor = "gpio13"
```

The absolute calibration path is correct: it is the exact file discovered at
import time. The wake-word field is also expected to read
`package://ninjarobot_pi5_ide/assets/hey_Ninja.onnx`. This is the packaged copy
of the same approved Ninja model used by `pi5mic`; it is not a missing project
root file and must not be copied into `ninjarobot_pi5_ide/assets/`.

**Validate the merged configuration:**

```bash
ninjarobot-ide-tool hardware status
```

Expected result: validation succeeds, both servo endpoints are listed, and the calibration file exists.

---

### Step 6 — Test the installed robot

**Open the interactive robot tool:**

```bash
ninjarobot-ide-tool
```

No flags are required because the environment already contains hardware
dependencies and the tool automatically loads
`~/.config/ninjarobot_pi5/config.toml`. Normal selections run physical
hardware; **Simulation** remains available as an optional diagnostic. Keep both
wheels raised and test in this order:

1. **Hardware Configurations** — verify the connected profile
2. A face expression — confirm the display updates
3. **Greeting** — confirm the face and sound sequence
4. A short wheel movement — confirm both raised wheels respond and stop
5. While a short guarded movement runs, place a flat target within 50 mm of the
   front sensor—confirm the wheels stop, the scary face appears, Idle returns,
   and a different movement works without Resume
6. **Emergency Stop** — confirm outputs stop, the red stop icon remains, and the
   result identifies the operator stop plus the Resume instruction
7. **Resume Robot Movement** — confirm devices are reinitialized and Idle returns

If you want a no-hardware preview, choose **Simulation** in this same tool; a
separate long command is not necessary.

> [!CAUTION]
> Before any wheel movement test, prepare an emergency stop in a second SSH terminal. Navigate there and run:
> ```bash
> cd "$HOME/NinjaRobotPi5"
> source .venv/bin/activate
> ninjarobot-ide-tool behavior stop
> ```
> Do not press Enter yet. Start the movement in the first terminal, then press Enter in the second terminal if you need to stop it.

---

### Step 7 — Set up and verify NinjaRobotAgent

**Verify Ollama and whisper.cpp are ready:**

```bash
ollama list
test -x "$HOME/whisper.cpp/build/bin/whisper-cli"
test -f "$HOME/whisper.cpp/models/ggml-base.bin"
```

**Run the Qwen3:4B performance benchmark:**

Before using a model for physical robot control, run the benchmark to confirm it meets the performance and safety thresholds for this Raspberry Pi.

```bash
cd "$HOME/NinjaRobotPi5"

ninjarobot-agent benchmark ollama \
  --model qwen3:4b \
  --output "$HOME/.local/share/ninjarobot_pi5/benchmarks/qwen3-4b-latest.json"
```

The benchmark is CPU-, memory-, and heat-intensive but never executes a robot tool. The model is accepted only when all of these thresholds are met:

| Threshold | Limit |
|---|---|
| First-token latency | ≤ 15 seconds |
| Total response latency | ≤ 30 seconds |
| Tool-call correctness | ≥ 90% |
| Peak total memory | < 7 GB |
| Temperature | < 80°C |
| Undervoltage or throttling | None |
| Unsafe or duplicate actions | None |

If the result is `"accepted": false`, keep using simulation and review the report before selecting another model.

**Open the normal-user Agent tool:**

```bash
ninjarobot-agent
```

Use the menus in this order:

1. **Set Agent Model** — select Ollama and `qwen3:4b` (or a configured cloud model).
2. **Start Agent Service** — choose **real hardware**. Only one service owns hardware.
3. **Agent Service Status** — confirm `started`, the selected provider, built-in tool providers, and robot tools are ready.
4. **MCP Tools (Built-in and External)** — confirm IDE, robot-control, and read-only memory tools appear even when `external_servers` is empty.
5. **Start NinjaRobot Chat Interface** — create the first owner profile and complete face enrollment.

The first chat asks for your name, displays a photo countdown, and creates the
owner/default profile. If the camera is unavailable, chat continues with a
clear pending-enrollment message and the display returns to Idle.

Before real-hardware face enrollment, verify the installed OpenCV API without
capturing a photo:

```bash
python scripts/validate_face_recognition_backend.py
```

Expected: `PASS` with OpenCV 4.x and the Haar cascade path. If it fails, run
`uv sync --frozen --extra hardware`, restart the service, and run the check
again. Do not install multiple OpenCV wheel variants because they share the
same `cv2` namespace.

Run the non-hardware memory benchmark:

```bash
python scripts/benchmark_agent_memory.py \
  --entries 1000 --queries 50
```

Expected result: `"passed": true`. The benchmark uses a temporary database and
does not open GPIO, SPI, I2C, PWM, camera, microphone, or the robot action ledger.

**Start the HTTPS web interface:** return to the main Agent menu, select
**Local Web Interface**, and use the exact `url` printed by the tool. The Agent
service must already be running; the web command controls the server owned by
that service and does not start a second Agent. Local Web remains available
when ngrok is disabled, not configured, connecting, or degraded. Only after a
public ngrok endpoint is verified does the result intentionally have
`ready: false`, `running: false`, and `url: null`, directing you to the ngrok
pairing link or display QR instead of opening a competing controller.

For phones or computers that require trusted local HTTPS, export the public CA
certificate with this optional advanced command (it contains no private key):

```bash
ninjarobot-agent web export-ca
```

This writes `~/ninjarobotpi5-local-ca.pem`.

Verify the certificate contains two entries (server certificate + local CA):

```bash
grep -c 'BEGIN CERTIFICATE' \
  "$HOME/.config/ninjarobot_pi5/tls/agent-cert.pem"
```

Expected result: `2`

Open the printed URL from a browser on the same local network. If the hostname does not resolve, use `https://ninjarobotpi5.local:8443/`.

> [!TIP]
> **For Chrome:** Accept the certificate warning with **Advanced → Proceed**, then reload. Installing the CA is recommended but optional for Chrome.
>
> **For Safari / iPhone / iPad:** Install the exported `ninjarobotpi5-local-ca.pem` as a trusted certificate. On iPhone/iPad, open **Settings → General → About → Certificate Trust Settings** and enable full trust for **NinjaRobotPi5 Local CA**. On macOS, import it into the System keychain and set it to Always Trust. Browser microphone access requires a fully trusted HTTPS page.
>
> **Add to Home Screen (iPhone/iPad):** For the most reliable fullscreen controller experience, choose **Share → Add to Home Screen** in Safari, then launch the saved icon.

**Test the web controller:**

1. ✅ Chat sends a message and streams a response
2. ✅ Live Activity tab shows service and tool events
3. ✅ With wheels raised, D-pad movement stops when released
4. ✅ **X** performs Emergency Stop and leaves the red stop icon visible
5. ✅ **Y** asks for confirmation before Resume
6. ✅ **A** runs Greeting, **B** runs Celebrate
7. ✅ Camera button shows a simulated preview
8. ✅ USB Microphone returns simulated recognized text
9. ✅ Web Microphone fills the message box with recognized text (sent only when you press **Send**)

Use **Stop Local Web Interface** or **Stop Agent Service** from the same tool when
needed. With ordinary startup (onboarding disabled), real mode runs Greeting
once and then silent Idle. After remote access or automatic startup is enabled,
startup instead shows the current pairing QR; the first authenticated browser
or terminal chat runs Greeting once and then enters Idle. The normal flow is:

```text
Idle → Thinking → Speaking (or emotion) → robot action → Idle
```

### Step 8 — Configure and test remote access (optional)

For the cleanest first setup, stop any manually running Agent service. Then:

1. Open `ninjarobot-agent` and select **Ngrok Remote Access**.
2. Select **Set ngrok token**. Paste the authtoken twice at the hidden prompts.
   This one-time step installs or validates ngrok and stores the token privately;
   it does not start a tunnel.
3. Select **Activate ngrok remote access service**. Before the Agent is running,
   this validates the saved token and executable and enables Remote Access for
   the next Agent start. The Agent service remains the only process allowed to
   own the tunnel.
4. Return to the main menu and select **Start Agent Service**.
5. Return to **Ngrok Remote Access**, choose **Ngrok service status**, and wait
   for a non-empty `public_url`.
6. Scan the display QR or choose **Show existing pairing URL** and open that
   exact URL in the browser.

The configuration operation downloads/replaces ngrok atomically, preventing
the former `Text file busy` overwrite. The authtoken identifies the local ngrok
agent but is not a browser password. Browser authentication uses the short-lived
pairing fragment in the URL, then a Secure/HttpOnly cookie; the QR contains no
secret that remains in browser history after pairing.

After remote access is enabled, Agent startup follows this sequence:

```text
Agent/web start → ngrok QR on robot display → authenticated browser or terminal
chat connects → Greeting face and sound → silent Idle
```

While ngrok is healthy, direct local Web requests are rejected and the robot
keeps waiting on its remote QR. In ordinary manual operation, stopping Remote
Access does not silently start Local Web; select **Local Web Interface** if you
want it. While a requested tunnel is connecting, Local Web is not withdrawn.
A confirmed tunnel, configuration, or network failure restores the local HTTPS
fallback and replaces the display with a fresh local pairing QR while remote
recovery continues. A recovered verified endpoint returns to remote-only mode.
Never expose port 8443 through router port forwarding.

### Step 9 — Enable and test automatic startup (optional)

Keep both wheels raised. Open `ninjarobot-agent`, select **Startup Agent
Deployment**, then select **Install and deploy automatic startup Agent**. Type
`ENABLE` only after reading the prompt. The Interactive Tool first stops a
manually started Agent cleanly, then this single transaction installs and
validates all three privileged artifacts—the systemd unit, fixed power-off
helper, and narrow sudoers rule—enables boot, and starts the installed service
immediately. If the first systemd start fails, boot enablement is rolled back.
Before privileged installation, setup parses both `config.toml` and the
versioned optional `mcp.toml`. It clears a prior systemd failed/start-limit
state and waits for an active unit, a responding Agent IPC endpoint, and a
successfully presented startup state. For QR onboarding, `ready: true` means
the remote or local pairing QR has been rendered on the robot display; the
earlier **Connecting…** state is not accepted as ready. For ordinary startup,
it means Greeting/Idle startup completed. A successful result therefore
includes `running_now: true` and `ready: true`.

The generated service also creates the private directory
`/run/ninjarobot-agent` and sets `LG_WD` to that location. Raspberry Pi
`lgpio` uses it for `.lgd-nfy*` notification pipes. This is required because
the hardened service intentionally mounts the repository and home directory
read-only. Do not remove `RuntimeDirectory` or point `LG_WD` back into the
checkout.

On Raspberry Pi 5, the same setup also checks the bootloader shutdown mode. If
needed, it schedules Raspberry Pi OS's official **Full power off** setting. The
result then shows:

- `poweroff_reboot_required: true`
- `full_poweroff.pending_configured: true`
- `full_poweroff.ready: false`

This is expected: EEPROM means the small bootloader memory on the Pi board, and
its new setting becomes active only after one reboot. The Agent may run before
that reboot, but the web Power Off action is deliberately unavailable so it
cannot stop the Agent and then let the Pi start again.

Select **Show startup Agent status**. Pass criteria are:

- `installed: true` and `enabled: true`
- `running: true` and `ready: true`
- all `artifacts` values are `true`
- after the required reboot, `full_poweroff.ready: true` and
  `full_poweroff.update_pending: false`
- the unit references the current checkout and `.venv` Python

`poweroff_helper: true` now means more than “a file exists.” It verifies the
approved script content, root ownership, `0755` mode, and that the path is not a
symbolic link. An older installation containing a sudoers line at the helper
path reports `false`; rerun **Install and deploy automatic startup Agent** to
repair it before testing Power Off.

The deployment verifier must complete without a `systemd-analyze` error. The
current installer stages the temporary unit as `ninjarobot-agent.service`,
because systemd derives the unit type from its filename suffix. If an older
checkout reports only `deployment command failed: systemd-analyze`, update the
repository and rerun this deployment action. Current failures include a
bounded verifier explanation and exit status; do not bypass this safety check
or install the unit manually.

Reboot with `sudo reboot`. After reconnecting by SSH, open `ninjarobot-agent`
and check **Agent Service Status** and **Startup Agent Deployment → Show startup
Agent status**. The display should show the current remote pairing QR, or a
local QR only when remote service is unavailable. Scan/open it and confirm
Greeting then Idle.

If this Pi previously installed an older unit, pulling the repository alone is
not enough: the root-owned unit under `/etc/systemd/system` is a deployed copy.
Run **Install and deploy automatic startup Agent** again and enter `ENABLE` to
replace it. A corrected boot log contains `Startup pairing QR is displayed`
and must not contain `xCreatePipe`, `.lgd-nfy`, or `Read-only file system`.
Use **Show startup Agent status** first. If it is not ready, inspect the bounded
logs with:

```bash
ninjarobot-agent deployment logs --lines 200
```

Expected result: the unit is active, the pairing QR message is present, and no
GPIO runtime-directory error appears. The complete safe acceptance and
rollback procedure is in the
[Boot QR runtime validation checklist](../../../../../docs/validation/boot-autostart-lgpio-runtime-pi-checklist.md).

Finally, test **Power off NinjaRobot** in the paired web hamburger menu. Choose
**Cancel** once, then repeat and choose **Power off**. If the deployment helper
or sudo rule is missing, or the EEPROM change still needs a reboot, the request
is rejected before the Agent stops and the web error gives the next step. A
successful confirmation stops robot modules and Raspberry Pi OS, then leaves
the Pi powered off rather than rebooting. Disconnect external power before
touching wiring even when the Pi is shut down.

For an X1208 installation, also confirm:

- power enters only through the X1208 USB-C input
- the supplied pogo pin firmly contacts the Pi 5 `PSW` through-hole
- the X1208 power-status LED changes to its documented standby/off state
- the Pi does not remain reachable by SSH and does not start again by itself

---

## Using the AI agent

### Chat commands

Once the service is running, open a chat session:

```bash
ninjarobot-agent
```

Useful slash commands inside chat:

| Command | What it does |
|---|---|
| `/help` | Show available commands |
| `/status` | Check service, hardware, and provider health |
| `/arm` | Request motion authorization for this session |
| `/disarm` | Revoke motion authorization and stop servos |
| `/camera` | Grant one AI-controlled photo for this session |
| `/resume` | Recover from Emergency Stop |
| `/voice input on` | Enable the global “Hey Ninja” listener |
| `/voice input off` | Disable the global wake-word listener |
| `/voice input status` | Show listener state and the last stable error |
| `/show remote access` | Put a fresh one-use ngrok pairing QR on the robot display |
| `/confirm <request>` | Approve a sensitive one-off action |
| `/new user` | Register another local profile and attempt face enrollment |
| `/switch user` | Name a profile, then switch only after its registered face matches |
| `/identify` | Take one countdown photo and switch only on one unique known face |
| `/update profile` | Show the active name/face status and start a profile update |
| `/clear` | Clear the current conversation history |
| `/exit` | Disconnect this terminal (service keeps running) |

Face enrollment during `/new user` and explicit `/identify` are trusted profile
workflows. They show the IDE-owned `3 → 2 → 1` countdown and do not require the
one-shot `/camera` AI-preview grant. An unavailable camera leaves enrollment
pending. Unknown, uncertain, or multiple faces never switch the active user.
Face recognition identifies a local profile; it is not authentication.

After `/update profile`, enter `name=<new name>` to change the user name or
`register user face` to enroll an unregistered face or refresh the current
profile face. Every attempt returns the display to silent Idle, including
backend failure and cancellation. A failed attempt leaves the profile usable
and can be retried through the same workflow.

The assistant's default conversational name is `NinjaAgent`. `robot_name=...`
is not a profile-update field. Rename the assistant in ordinary chat with an
explicit request such as “Please rename yourself to Ninja.” The active user's
saved name overrides older assistant messages that mention a previous name.
An explicit compound request such as “I want to call you Pocky, and please call
me Master” saves both values together. A visible notice confirms each saved
value. The same user's saved robot name and form of address are available after
changing models and from terminal/web sessions that independently select that
user; transcript-only replies are never treated as persistent preferences.

### Managing persistent memory

Open the interactive tool and choose **Agent Memory Management**:

```bash
ninjarobot-agent
```

The menu can list profiles, transfer the owner role, delete an inactive member
profile, register or replace an existing profile's face, list/delete individual
behavior memories, change retention, or clean all robot memory. Profile
deletion and full reset are intentionally unavailable in terminal/web chat.
The same deterministic operations are scriptable:

```bash
ninjarobot-agent memory profiles
ninjarobot-agent memory settings
ninjarobot-agent memory list local-user \
  --kind successful_behavior
ninjarobot-agent memory set-retention \
  --conversations 7 --failed 180 --failed-cap 1000
ninjarobot-agent memory delete USER_ID MEMORY_ID --confirm
ninjarobot-agent memory transfer-owner USER_ID --confirm
ninjarobot-agent memory delete-profile USER_ID --confirm
ninjarobot-agent memory register-face USER_ID --confirm
ninjarobot-agent memory reset-all --confirm
```

The service must be running. An active profile cannot be deleted. The current
owner must be transferred first. Deleting a profile removes that user's raw
messages, structured memory, face index entry, and cropped profile image.
`reset-all` is the only operation that can delete the owner. In the interactive
menu it requires typing `DELETE ALL ROBOT MEMORY`; it removes every profile,
conversation, learned memory, preference, retrieval index, and face record,
then resets retention to configured defaults. It preserves API keys, provider
selection, saved IDE behaviors, hardware calibration, and service logs. The
next chat starts first-owner registration.

Default retention is 7 days for raw conversations and 180 days for failed
behaviors (maximum 1,000 failed entries per user). Profiles, preferences, task
recipes, and confirmed successful behaviors remain until manually deleted.
Local data is owner-only under `~/.local/share/ninjarobot_pi5/`; Raspberry Pi
administrators can read the cropped profile photos and face-recognition data.

Terminal chat and each browser keep separate transcripts and independently
selected users. Reconnecting the same browser preserves its chat identity while
the service remains active; switching a terminal or another browser never
silently switches it. Once two interfaces independently select the same user,
they share that user's profile, preferences, and long-term behavior memory.
Changing the AI model/provider preserves the current session, active user, and
long-term memory, but intentionally revokes motion authorization.

### Enabling AI motion (physical movement)

To let the AI move the robot's wheels, raise the wheels first, then:

```bash
# Inside the chat:
/arm
# Type ARM when prompted
```

Motion authorization is session-lived. It stays active while a local model is reasoning and ends on `/disarm`, an Emergency Stop, successful `/resume`, browser disconnect, model change, or service stop. Recovery deliberately leaves AI motion disarmed, so `/arm` is required again before another servo movement.

Try a non-moving expression first:

```text
Create a two-stage happy expression. Show a happy face with a short 880 Hz tone,
then show "Hello!" while playing the happy melody.
```

Then try a short movement with both wheels raised:

```text
Create a brief exciting movement. Show the exciting face, play an exciting melody,
and move forward for one second, then stop and return to Idle.
```

Save the result:

```text
Do you want to record this new behavior in long-term memory and the IDE catalog?
Yes, name it "my exciting move"
```

The confirmation is handled deterministically; there is no IDE confirmation
button and `/confirm` is not required. A successful reply creates searchable
long-term memory and a runnable private catalog entry named
`my_exciting_move`. Existing catalog entries are never overwritten; if a name
conflicts, the agent reports the failure and leaves the confirmation retryable
with a different name.
The quoted-name fallback also accepts natural affirmative wording with minor
surrounding typos, for example `Yes and name this behavor "my exciting move"`;
the exact quoted label is retained while the catalog identifier is normalized.

### Recovering from emergency stop

If a persistent safety stop occurs, the Agent chat and service log identify the
reason, explain the likely cause, and give the recovery step. Correct the
reported power, hardware, or service condition first. Then enter
`/resume` in terminal or web chat and type `RESUME` when asked. The Agent runs
all-module health checks directly—it does not ask the AI model. On success, the
Emergency Stop clears and Idle returns. AI motion stays disarmed; use `/arm`
separately before asking for another servo movement.

An ordinary obstacle interruption is different. Three consecutive guarded
distance readings at or below 50 mm stop only the current behavior. The robot
shows a scary face for two seconds, reports that the path must be checked, and
returns to Idle. Do not enter `/resume`: clear the path and issue a new command.
The interrupted behavior never restarts automatically.

### Enabling an AI-controlled photo

Enter `/camera` or press **AI camera** in the web controller, then ask:

```text
Take one photo now.
```

Or in Japanese:

```text
写真を撮ってください。
```

The display counts down `3`, `2`, `1`, then shows a camera icon while capturing. The photo appears in the web preview and is **not** saved to disk. A failed capture keeps the permission active so you can try again after correcting the camera. After a successful photo, enter `/camera` again to grant a new one.

---

## Testing and troubleshooting

### Recommended validation order

1. Software and simulation test
2. Buzzer test
3. Display test
4. Distance sensor test
5. Servo test (wheels raised)
6. Camera test (with consent)
7. Microphone test (with consent)
8. Integrated behavior test
9. NinjaRobotAgent test

Never change wiring while the robot is powered.

### Software and simulation test

```bash
cd "$HOME/NinjaRobotPi5"
python scripts/verify_immutable_drivers.py
pytest -q
```

Expected result: driver verification passes and all tests pass. These tests use simulation only.

### Buzzer test

```bash
pi5buzzer buzzer-tool
```

Expected result: a short tone or melody plays through GPIO27 and the buzzer is silent afterward.
Full checklist: [Phase 3.1 buzzer validation](../../../../../docs/validation/phase-3-1-buzzer-validation-2026-07-26.md)

### Display test

```bash
pi5disp display-tool
```

Expected result: text and colors are correctly oriented at 320×240 after the 90° rotation, and brightness changes take effect.
Full checklist: [Phase 3.2 display validation](../../../../../docs/validation/phase-3-2-display-validation-2026-07-26.md)

### Distance sensor test

```bash
pi5vl53l0x sensor-tool
```

Expected result: a target within range produces changing millimetre readings. Open space may produce the raw value `8191`, which means no target is measurable.
Full checklist: [Phase 2 distance validation](../../../../../docs/validation/phase-2-validation-2026-07-26.md)

### Servo test

> [!CAUTION]
> Raise the wheels and keep an operator ready to remove power.

```bash
pi5servo servo-tool
```

Expected result: each motor turns in both directions and stops at its calibrated center. Recalibrate if a motor creeps at center.
Full checklist: [Phase 3.3 servo validation](../../../../../docs/validation/phase-3-3-servo-validation-2026-07-26.md)

### Camera test

> [!CAUTION]
> Tell everyone nearby and obtain consent before capturing.

```bash
/usr/bin/python3 -s -c \
  "import libcamera, picamera2; print('Picamera2:', picamera2.__file__)"

rpicam-hello --list-cameras

pi5camera camera-tool
```

Full checklist: [Phase 3.4 camera validation](../../../../../docs/validation/phase-3-4-camera-validation-2026-07-26.md)

### Microphone test

> [!CAUTION]
> Tell everyone nearby and obtain consent before recording.

```bash
arecord -l

pi5mic mic-tool
```

Choose **Run one capture cycle**. If the sample rate falls back to 44.1 kHz, that is normal when the device reports ready.
Full checklist: [Phase 3.5 microphone validation](../../../../../docs/validation/phase-3-5-microphone-validation-2026-07-26.md)

### Integrated behavior test

```bash
ninjarobot-ide-tool
```

Use **Simulation** only when you want a hardware-free diagnostic. During the
raised-wheel real movement test, note:

- Movement starts without waiting for clear sensor readings
- The value `8191` means clear (no target in range), not an error
- Three consecutive valid readings at or below 50 mm stop forward and turning movement (Level 1)
- `null`, invalid, missing, and stale readings do not stop movement
- Backward movement continues with a warning because the sensor faces forward

Full checklists:
- [Phase 4 integrated behavior validation](../../../../../docs/validation/phase-4-integrated-behavior-validation-2026-07-26.md)
- [Phase 4 animated-face and interactive-tool validation](../../../../../docs/validation/phase-4-refinement-validation-2026-07-27.md)

---

### Common problems and fixes

#### Installer troubleshooting

Run the installer check again from the repository root:

```bash
./install.sh --check
```

If the check reports an unsupported platform, do not force installation. The
hardware installer supports 64-bit Raspberry Pi OS on Raspberry Pi 5. If it
reports a conflicting PWM overlay, restore the backup named in the message or
remove the old, unmanaged servo overlay after confirming the correct pins.
Rerunning `./install.sh` repairs missing packages and project files without
replacing healthy pinned installations. It never reboots automatically.

#### `uv: command not found`

```bash
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

If that works, reconnect over SSH so the shell loads the installer changes. If it still fails, reinstall:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

#### Agent Reports `No module named 'qrcode'`

This means the environment was created from older dependency metadata or was
not synchronized after updating the checkout. Repair it without changing robot
configuration or memory:

```bash
cd "$HOME/NinjaRobotPi5"
uv sync --frozen --extra hardware
source .venv/bin/activate
python -c "import qrcode; from importlib.metadata import version; print('qrcode:', version('qrcode'))"
ninjarobot-agent
```

Expected result: qrcode version `8.2` is printed and the Interactive Tool opens.
Do not install a separate similarly named QR package with `pip`; the lock file
selects the approved `qrcode[pil]` distribution.

---

<a id="servo-calibration-saved-to-the-wrong-file"></a>

#### ⚙️ Servo Calibration Saved to the Wrong File

If `servo-tool` was run without `-c`, it may have created `$HOME/NinjaRobotPi5/servo.json`. Check both locations:

```bash
ls -l \
  "$HOME/NinjaRobotPi5/servo.json" \
  "$HOME/.config/pi5servo/servo.json" 2>/dev/null
```

If the project-root file contains the correct calibrations and the canonical file does not yet exist, copy it:

```bash
mkdir -p "$HOME/.config/pi5servo"
cp "$HOME/NinjaRobotPi5/servo.json" \
  "$HOME/.config/pi5servo/servo.json"
chmod 600 "$HOME/.config/pi5servo/servo.json"
```

Always use `-c "$HOME/.config/pi5servo/servo.json"` for future `servo-tool` calls.

---

#### `config import` reports `"applied": false`

That is the expected **preview**. Nothing is wrong. Apply it with:

```bash
ninjarobot-ide-tool config import \
  --destination "$HOME/.config/ninjarobot_pi5/config.toml" \
  --apply
```

If the destination already exists, use the synchronization procedure in the [Appendix](#synchronize-changed-module-settings-with-the-ide).

---

#### 📷 Camera Reports `No module named 'picamera2'`

```bash
cd "$HOME/NinjaRobotPi5"
./scripts/bootstrap-rpi-camera-workspace.sh

/usr/bin/python3 -s -c \
  "import libcamera, picamera2; print('Picamera2:', picamera2.__file__)"
```

It is normal for the project `.venv` to be unable to import Picamera2. NinjaRobotPi5 routes real camera work through `/usr/bin/python3` on purpose.

---

#### 🎙️ Microphone Reports PortAudio Missing

```bash
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev alsa-utils
uv sync --frozen --extra hardware
arecord -l
```

---

#### 🖥️ Display Stays Blank

Check that SPI is enabled and the device exists:

```bash
ls -l /dev/spidev0.0
```

Then confirm DC GPIO4, RST GPIO5, and BL GPIO6 are connected correctly. Never rewire while powered. Reopen `pi5disp display-tool` using `PI5DISP_CONFIG` and review its saved settings.

When the Agent owns the hardware, do not open the standalone display tool.
Instead, inspect the recovery log:

```bash
ninjarobot-agent deployment logs --lines 200
```

Expected result after a transient fault: the log reports ST7789V reconstruction
and a successful frame retry, and Idle continues without restarting the Agent.
If it reports that automatic recovery and the single retry both failed, stop
the Agent, power the robot off, inspect the SPI and DC/RST/BL wiring, and then
cold-start it. Do not repeatedly restart against loose or shorted wiring.

---

#### 📡 Distance Sensor Always Returns `8191`

`8191` is the sensor's out-of-range marker, not a measured distance. Aim the forward-facing sensor at a large, flat, light-coloured object within range. If the value changes to a millimetre reading, the sensor is working correctly.

If results are `null`, check I2C:

```bash
ls -l /dev/i2c-1
sudo i2cdetect -y 1
```

Expected addresses: `29` for the VL53L0X, `10` for the DFR0566.

---

#### 🔴 Movement Does Not Start

Check calibration and safety state:

```bash
pi5servo calib --show \
  --config "$HOME/.config/pi5servo/servo.json"

ninjarobot-ide-tool hardware status --real
```

Both calibrations must exist, both motion flags must be `true`, and no safety latch must be active.

If chat says an obstacle interrupted the behavior and `requires_resume` is
`false`, the safety state is intentionally clear. Move the obstacle, verify the
front sensor is unobstructed, and issue a new command. Do not run a resume
command for this normal interruption.

If a Level 1 motion latch is active:

```bash
ninjarobot-ide-tool \
  motion resume --confirm
```

If a driver-failure Level 2 latch is active:

```bash
ninjarobot-ide-tool \
  system resume --confirm
```

If the IDE says the hardware is already owned by the agent service, use the agent instead:

```bash
ninjarobot-agent
# Then type: /resume
# Then type: RESUME
```

---

#### 🤖 Agent Service Is Unavailable

```bash
systemctl status ollama --no-pager
ollama list
ninjarobot-agent service status
tail -n 100 "$HOME/.local/state/ninjarobot_pi5/agent-service.log"
```

If the Interactive Tool says the service connection closed unexpectedly, the
background service exited while its startup status was being checked. The
message is controlled; use the last command above to find the primary error.
Do not delete the socket or lock while a service process is running. Current
releases accept configurations where remote access is enabled even if an older
explicit onboarding setting is false—the effective QR-onboarding state is
derived automatically from remote access, onboarding, and auto-start settings.

---

#### 🔒 Web Interface Shows `423 Locked`

Another browser holds the one controller lease. Close that browser and wait about 10 seconds, or restart the web interface:

```bash
ninjarobot-agent web stop
ninjarobot-agent web start
```

---

#### 🔐 Browser Rejects the HTTPS Certificate

Restart the web interface to upgrade older certificates:

```bash
ninjarobot-agent web stop
ninjarobot-agent web start
grep -c 'BEGIN CERTIFICATE' \
  "$HOME/.config/ninjarobot_pi5/tls/agent-cert.pem"
```

The count should be `2`. If Chrome offers **Advanced → Proceed**, accept it and reload. For Safari and reliable browser microphone access, install the public CA:

```bash
ninjarobot-agent web export-ca \
  --output "$HOME/ninjarobotpi5-local-ca.pem"
```

Copy `ninjarobotpi5-local-ca.pem` to your device and install it as a trusted certificate. Never share `agent-key.pem` or `local-ca-key.pem`.

---

#### 🎙️ USB Microphone Transcription Unavailable

```bash
test -x "$HOME/whisper.cpp/build/bin/whisper-cli"
test -f "$HOME/whisper.cpp/models/ggml-base.bin"
```

If whisper.cpp is installed in a different location, pass the paths explicitly:

```bash
ninjarobot-agent \
  --whisper-command /absolute/path/to/whisper-cli \
  --whisper-model /absolute/path/to/ggml-model.bin \
  service start --real
```

#### 🥷 Enable or Disable “Hey Ninja” Voice Input

Voice input is disabled until you explicitly enable it. Install the hardware
extra, start the real agent service, open terminal chat, and use:

```text
/voice input on
/voice input status
/voice input off
```

The web **VOICE INPUT** button controls the same listener. Say **Hey Ninja**,
then speak a command for at most 15 seconds; silence ends the recording early.
English, Japanese, Traditional Chinese, and Simplified Chinese are supported.
The wake word itself remains English. Audio is processed locally, background
audio is not retained, and each temporary command clip is deleted after local
transcription. Replies are shown through the existing web/display/behavior
flow; this release does not speak replies aloud.

Physical movement still requires the existing `/arm` confirmation or web
**Arm AI motion** button. Turning voice input off, restarting the service,
switching models, emergency stop, or losing the browser lease that granted the
arm revokes voice motion permission.

`/voice input on` now waits for the USB stream to reach `listening`; it no
longer reports a successful enable while the microphone is still opening. A
startup that exceeds `startup_timeout_seconds` (10 seconds by default) closes
partial PortAudio ownership, leaves voice disabled, and reports a stable error
such as `microphone_busy`, `microphone_permission_denied`,
`microphone_format_unsupported`, `microphone_unavailable`, or
`listener_start_timeout`.

#### 🌐 Configure Optional ngrok Remote Access

Remote access is opt-in and requires an ngrok account/authtoken. Free accounts
may show an ngrok-controlled interstitial and have endpoint, request, and data
limits; review [ngrok's current limits](https://ngrok.com/docs/pricing-limits/free-plan-limits)
before relying on the service.

Launch `ninjarobot-agent` before starting the Agent service, select **8. Ngrok
Remote Access**, choose **1. Set ngrok token** once, then choose **2. Activate
ngrok remote access service** whenever remote control is wanted. Activation in
this pre-service state validates and persists the setting; only the later Agent
service owns the tunnel. The simplified menu also provides service status,
the current pairing URL, and deactivation. Pairing rotation and credential
removal remain available as advanced scriptable commands.

Scriptable equivalents are:

```bash
ninjarobot-agent remote configure
ninjarobot-agent remote activate
ninjarobot-agent remote pairing-url
```

The first command prompts twice for the ngrok authtoken and explicitly installs
the ngrok agent. A valid v3 binary is reused; a replacement is downloaded to a
private temporary directory, version-checked, and atomically installed. This
prevents `Text file busy` when an older process still references the previous
inode. It saves configuration but does not activate a tunnel. The token is
never printed. The service will not download or update ngrok on startup. Run
the activation operation, then start the Agent service and open its pairing URL
on the controlling browser. No browser username or password is required: the
one-use URL fragment becomes a short-lived Secure/HttpOnly session cookie.

The tunnel removes any client-supplied transport marker and adds the trusted
marker through ngrok Traffic Policy `remove-headers` and `add-headers` actions.
This follows ngrok's current
[Traffic Policy header actions](https://ngrok.com/docs/traffic-policy/examples/add-and-remove-headers)
while retaining verified TLS to the robot's private local CA.
Permanent authentication/account/configuration failures stop retrying until
the operator corrects them; transient network/tunnel loss continues with
capped backoff. If **Show existing pairing URL** reports
`detail: tunnel_not_ready`, first use **Ngrok service status** and
correct/activate the tunnel.
The “pairing code” is the short-lived URL fragment generated only after a
healthy public HTTPS endpoint exists; it is not a separate number.

Useful management commands:

```bash
ninjarobot-agent remote status
ninjarobot-agent remote rotate-pairing
ninjarobot-agent remote deactivate
ninjarobot-agent remote remove-credentials --confirm
```

Rotation revokes all existing remote browser sessions. Deactivation stops the
exact tunnel and also revokes sessions. Credential removal deletes the private
token/pairing files but retains the ngrok executable for a later reconfiguration.
Manually stopping ngrok does not silently start Local Web. A deployed
automatic-start service does start the local mDNS HTTPS fallback and refresh
the display QR when ngrok is unavailable; terminal chat, robot memory, and
hardware remain available. Never configure router port forwarding to port 8443
as an alternative.

#### 🌏 Use the Multilingual Robot Menu

Open the top-right hamburger menu to select English, Japanese, Traditional
Chinese, or Simplified Chinese. The selection controls interface labels and
the recognition locale for manual USB recording and browser speech, and it
persists in that browser. The live connection badge retains its actual state
when the language changes. **VOICE INPUT** and **RECORD ONCE** are on the main
controller below **CAMERA** and **WEB MICROPHONE**; the hamburger contains the
language selector, connection information, and system power. Press Escape, the
close button, or the menu backdrop to close it; Emergency Stop remains on the
main dashboard.

An Emergency Stop cancels foreground/idle presentation and leaves a persistent
red stop icon until confirmed Resume. If icon rendering fails, the display
attempts a red `EMERGENCY STOP / RESUME REQUIRED` text fallback and records the
display error instead of silently leaving the previous face frozen.

Power-off is disabled unless deployment power control is enabled and the
active browser has completed pairing. Selecting **Power off NinjaRobot**
obtains a short-lived confirmation and then shows separate **Power off** and
**Cancel** actions. Cancel changes nothing. Confirmation first stops hardware
and voice and closes agent resources. Phase 8.6 installs the narrow helper for
the final OS shutdown; the agent never receives general passwordless sudo. If
the helper, sudo rule, or active Raspberry Pi full-power-off EEPROM setting is
missing, preflight rejects the request before the Agent stops. A compatible
pending EEPROM update is also rejected until one reboot applies it. A rare
failure after confirmed cleanup leaves the robot safely stopped; the local
recovery is:

```bash
sudo systemctl poweroff
```

#### 📱 Enable QR Onboarding

Remote activation and automatic-start setup enable onboarding automatically;
beginners should not edit TOML. Startup initializes the robot and web server
without moving, then
shows **Connecting…** while configured ngrok access starts. A healthy remote
endpoint displays its pairing QR and waits; an actual tunnel/configuration/
network failure starts the deployed local fallback and displays the local
`https://ninjarobotpi5.local:8443` pairing QR while remote retries. If remote
access is disabled, the local QR appears immediately.

Scan the displayed code. The one-use fragment creates a Secure/HttpOnly browser
session and removes itself from the address. Only after that paired browser
obtains the exclusive WebSocket controller lease does the QR clear and Greeting
run once. Refreshing or reconnecting does not replay Greeting. If the display
or Greeting fails, the robot shows **Error**, keeps AI/voice motion disarmed,
attempts to stop servos, and requires a local service restart after the fault is
corrected.

After startup has already completed, enter `/show remote access` in terminal
chat to display a new one-use ngrok QR without revoking browsers that are
already paired. The QR clears directly to Idle after that new browser pairs;
Greeting is not replayed.

#### 🚀 Install Opt-In Automatic Startup

Run these commands as the normal non-root Raspberry Pi robot user from the
installed environment. First validate and back up:

```bash
ninjarobot-agent deployment validate
ninjarobot-agent deployment backup --output ~/ninjarobot-backup.tar.gz
ninjarobot-agent deployment setup --confirm
ninjarobot-agent deployment status
```

Setup uses sudo only to place the root-owned unit, fixed power-off helper, and
narrow sudoers rule. It checks that all three artifacts are operational,
enables the next-boot service, persists onboarding and web power-off settings,
and starts the systemd service immediately. On Raspberry Pi 5 it also invokes
the official non-interactive Raspberry Pi OS **Full power off** configuration
when needed. That schedules `POWER_OFF_ON_HALT=1` and `WAKE_ON_GPIO=0`; it does
not edit unrelated EEPROM keys. If setup reports
`poweroff_reboot_required: true`, reboot once and confirm
`full_poweroff.ready: true` in deployment status before testing web Power Off.
Status verifies the exact
helper bytes, root ownership, `0755` mode, non-symlink identity, and passwordless
permission with `sudo -n -l`; it does not try to read the protected
`/etc/sudoers.d` directory. A partial install or failed first start is left
disabled. Test safely with raised wheels:

```bash
ninjarobot-agent deployment status
ninjarobot-agent deployment logs --lines 200
```

Reboot only after the raised-wheel test succeeds:

```bash
sudo reboot
```

Setup also turns on QR onboarding and paired web power-off. Useful
maintenance and recovery commands are:

```bash
ninjarobot-agent deployment disable
ninjarobot-agent deployment upgrade --confirm
ninjarobot-agent deployment rollback --backup ~/ninjarobot-backup.tar.gz --confirm
ninjarobot-agent deployment uninstall --confirm
```

Upgrade preserves current enablement. Rollback stops the unit and overlays only
verified archived user-data paths. Disable and uninstall preserve profiles,
memory, faces, behaviors, secrets, configuration, databases, and backups.

---

#### ⚡ Raspberry Pi Reports Undervoltage

```bash
vcgencmd get_throttled
```

`throttled=0x0` means no current or recorded power issue. Any other value needs investigation. Stop servo motion, check the official supply, X1208 board, connectors, and wiring. Do not continue movement tests until power is stable.

---

## Appendix

### Using optional cloud AI providers

You can skip this section and keep using Ollama. Cloud providers require an internet connection, send your conversation and tool descriptions to the provider, and may charge your account. Robot tools still run locally — the cloud adapter cannot access the Pi hardware directly.

All three providers use API keys only. Browser logins, Google OAuth, and Anthropic `ant` logins are not used.

**OpenAI:**

```bash
ninjarobot-agent provider set-api-key openai

ninjarobot-agent provider health openai

ninjarobot-agent model list --provider openai
```

**Google Gemini:**

```bash
ninjarobot-agent provider set-api-key gemini

ninjarobot-agent provider health gemini
```

**Anthropic:**

```bash
ninjarobot-agent provider set-api-key anthropic

ninjarobot-agent provider health anthropic
```

Select a model once you see the available list:

```bash
ninjarobot-agent model select MODEL_ID --provider PROVIDER_ID
```

Do not copy a model name from an old guide — provider catalogs change over time.

Gemini 3.5/3.6 can use the same local robot and memory tools as the other
providers. NinjaRobot automatically retries a Gemini `429` rate-limit response
up to two times before any streamed reply or tool execution; it never repeats a
completed robot action. If the final message still says that quota was reached,
wait briefly and check the active project limits in Google AI Studio. An
`INVALID_ARGUMENT` message means Gemini rejected the request format, not that
the API key, camera, or hardware is unavailable; update to the current
NinjaRobot release and include the exact error plus the service-log timestamp in
any support report.

---

### Synchronize changed module settings with the IDE

Use this procedure after changing buzzer, display, camera, or microphone settings in the standalone tools.

1. Exit any running `ninjarobot-ide-tool` process.
2. Save the new settings using the standalone tool with its canonical path.
3. Return to the project environment:

```bash
cd "$HOME/NinjaRobotPi5"
source .venv/bin/activate
```

4. Confirm discovery finds the updated files:

```bash
ninjarobot-ide-tool config discover
```

5. Preview the update (uses the current integrated file as base):

```bash
ninjarobot-ide-tool config import
```

6. Review the preview carefully — confirm safety values, servo roles, and AI settings are still correct.

7. Apply:

```bash
ninjarobot-ide-tool config import --apply --overwrite
```

8. Validate and verify hardware:

```bash
ninjarobot-ide-tool hardware status
```

`--overwrite` is required because the destination already exists. It does not overwrite any standalone `pi5*` JSON file.

---

### Set up Tavily web search (optional)

Tavily lets the AI search the internet for current information. It is optional:
the IDE, robot-control, and memory MCP providers load without `mcp.toml`, and
the robot works normally without Tavily.

The Agent writes a canonical versioned catalog beginning with
`schema_version = 1`. Older catalogs without this line remain compatible. Do
not set a different version: deployment preflight intentionally rejects an
unsupported schema before systemd is changed.

> [!IMPORTANT]
> Tavily may provide a free allowance. Check the
> [current Tavily quickstart](https://docs.tavily.com/documentation/quickstart)
> before registering because price, quota, and terms can change. Never paste an
> API key into chat, source code, `config.toml`, screenshots, or issue reports.

1. Open the [Tavily Platform](https://app.tavily.com/), create or sign in to
   your account, open its API Keys area, and copy an active key. Tavily's
   official quickstart identifies the dashboard as the place to obtain the key.

2. If the Agent service is running, stop it from the Interactive Tool with
   **13. Stop Agent Service**. MCP catalog and secret changes take effect on the
   next Agent start; setup never restarts a working robot silently.

3. Store the key in NinjaRobot's private secret file. The prompt hides the
   value and asks for it twice:

```bash
cd "$HOME/NinjaRobotPi5"
ninjarobot-agent secret set TAVILY_API_KEY
```

4. Add the bundled, search-only Tavily preset to the optional external MCP
   catalog:

```bash
ninjarobot-agent mcp add --preset tavily --id tavily
```

5. Verify configuration, health, and the allowlisted tools before starting the
   Agent:

```bash
ninjarobot-agent mcp list
ninjarobot-agent mcp health tavily
ninjarobot-agent mcp tools tavily
```

Expected result: server `tavily` is enabled and ready, and the allowlist exposes
`tavily-search`. Secret values are never printed.

6. Run one read-only test search:

```bash
ninjarobot-agent \
  mcp test tavily --tool tavily-search \
  --arguments '{"query":"Raspberry Pi official news","max_results":3}'
```

7. Open `ninjarobot-agent`, select **2. Start Agent Service**, then select
   **9. MCP Tools (Built-in and External)**. Confirm the Tavily provider and
   `mcp.tavily.tavily-search` appear. Open **4. Start NinjaRobot Chat
   Interface**, then ask:

```text
Search the web for the latest official Raspberry Pi news and show your sources.
```

Expected result: the answer includes source links. If internet access or quota is unavailable, the agent should say it cannot verify a current answer.

If health reports a missing credential, repeat `secret set` and start the Agent
again. If `mcp add` reports that `tavily` already exists, use `mcp list` rather
than adding a duplicate; use `ninjarobot-agent mcp enable tavily` if it is
disabled. For an exposed key, revoke it immediately in the Tavily dashboard,
create a replacement, save it with `secret set`, and restart the Agent. This
matches Tavily's official
[API-key rotation guidance](https://docs.tavily.com/documentation/best-practices/api-key-management).

---

### Standalone `pi5*` library reference

| Library | Canonical config file | What the IDE copies |
|---|---|---|
| `pi5buzzer` | `~/.config/pi5buzzer/buzzer.json` | GPIO pin number |
| `pi5disp` | `~/.config/pi5disp/display.json` | Wiring, dimensions, rotation, brightness, SPI speed |
| `pi5servo` | `~/.config/pi5servo/servo.json` | Reference path (IDE reads calibration directly) |
| `pi5vl53l0x` | `~/.config/pi5vl53l0x/vl53l0x.json` | Detected but not copied; IDE uses its own I2C settings |
| `pi5camera` | `~/.config/pi5camera/camera.json` | Width, height, warm-up time, autofocus mode |
| `pi5mic` | `~/.config/pi5mic/mic.json` | Input device, sample rate, channel count |

The integrated Agent reads the imported microphone settings from
`~/.config/ninjarobot_pi5/config.toml`. A checkout-root `mic.json` is not an
Agent configuration file and a machine-specific absolute model path there
should not be committed as portable project configuration.

Always run each library from the root NinjaRobotPi5 environment:

```bash
cd "$HOME/NinjaRobotPi5"
uv sync --frozen --extra hardware
```

Stop the agent and integrated IDE before opening any standalone hardware tool.

**Quick links to library guides:**

- [pi5buzzer README](../../../../../pi5buzzer/README.md)
- [pi5camera README](../../../../../pi5camera/README.md)
- [pi5disp README](../../../../../pi5disp/README.md)
- [pi5mic README](../../../../../pi5mic/README.md)
- [pi5servo README](../../../../../pi5servo/README.md)
- [pi5vl53l0x README](../../../../../pi5vl53l0x/README.md)

---

### Updating NinjaRobotPi5

Stop all tools and services before updating:

```bash
ninjarobot-agent web stop
ninjarobot-agent service stop

cd "$HOME/NinjaRobotPi5"
git status --short
git pull --ff-only
uv sync --frozen --extra hardware
./scripts/bootstrap-rpi-camera-workspace.sh --skip-apt

python \
  scripts/verify_workspace_driver_sources.py
python scripts/verify_immutable_drivers.py
pytest -q
```

`git pull --ff-only` refuses to combine unexpected local source changes with the downloaded update. Your personal configuration under `~/.config` and retained media under `~/.local` remain outside the Git checkout and are never affected by updates.

For a complete existing-checkout and clean-clone acceptance run using the two
normal interactive tools, follow
[Phase 8 Final Interactive Raspberry Pi Validation](../../../../../docs/validation/phase-8-final-interactive-pi-validation-2026-08-14.md).
