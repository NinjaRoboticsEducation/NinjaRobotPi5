# NinjaRobotPi5 Installation Guide

> [!WARNING]
> **Alpha release.** Complete all simulation and raised-wheel tests before allowing the robot to move freely on the floor.

This guide takes you from a blank Raspberry Pi to a fully calibrated, running robot. Follow the numbered steps in order. The testing, troubleshooting, and extension sections at the end are available whenever you need them.

---

## 📋 Before You Begin

### Hardware You Need

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

### Safety Rules — Read These First

> [!CAUTION]
> Follow these rules every time you work with the robot.
>
> 1. **Raise the wheels before any movement test.** The robot currently has no accessible physical servo cutoff.
> 2. **Never change wiring while power is on.**
> 3. **Obtain consent from everyone nearby before any camera or microphone test.**
> 4. **Never expose port 8443 to the internet** or configure router port forwarding.
> 5. **Stop the agent service before opening standalone hardware tools.**

---

## 📁 Project File Layout

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
~/.local/share/ninjarobot_pi5/     Retained camera and microphone files
~/.local/state/ninjarobot_pi5/     Safety state, service logs, and transcripts
```

`~` means your Linux home directory, for example `/home/rogerchang`.

---

## 🛠️ Installation Steps

### Step 1 — Install Raspberry Pi OS on Your Pi

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

### Step 2 — Configure the Operating System

**Update the OS:**

```bash
sudo apt update
sudo apt full-upgrade -y
```

**Install system tools:**

```bash
sudo apt install -y \
  build-essential \
  cmake \
  git \
  curl \
  i2c-tools \
  alsa-utils \
  libportaudio2 \
  portaudio19-dev
```

**Enable I2C and SPI:**

I2C (two-wire bus) is used by the distance sensor and expansion board. SPI (Serial Peripheral Interface) is used by the display.

```bash
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
```

**Enable hardware PWM on GPIO12 and GPIO13:**

PWM (pulse-width modulation) is the electrical signal that controls the servo speed and direction.

```bash
sudo nano /boot/firmware/config.txt
```

Inside the editor:

1. Find `dtparam=audio=on` and change it to `dtparam=audio=off`. If the line is absent, add `dtparam=audio=off` under the `[all]` section.
2. Add this line in the same section:

```ini
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

3. Press `Ctrl+O`, Enter, then `Ctrl+X` to save and exit.

**Reboot:**

```bash
sudo reboot
```

Wait about one minute, then reconnect:

```bash
ssh YOUR_USERNAME@ninjarobotpi5.local
```

**Install `uv` (Python package manager):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

Expected result: a `uv` version number is printed. The installer also adds `uv` to future SSH sessions automatically.

---

### Step 3 — Download and Install NinjaRobotPi5

**Clone the project:**

```bash
git clone -b alpha01 https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git
cd NinjaRobotPi5
```

**Install Python dependencies:**

```bash
uv sync --frozen --extra hardware
```

`uv` creates the `.venv` virtual environment automatically. You never need to run `source .venv/bin/activate` — all commands in this guide use `uv run`.

**Set up the camera bridge:**

```bash
./scripts/bootstrap-rpi-camera-workspace.sh
```

This installs the Raspberry Pi OS camera packages (Picamera2 and libcamera), keeps your normal project environment separate, and verifies the bridge without taking a photograph.

> [!NOTE]
> It is normal for `python -c "import picamera2"` inside the project `.venv` to fail. NinjaRobotPi5 routes real camera calls through `/usr/bin/python3` on purpose. The required check is `/usr/bin/python3 -s -c "import libcamera, picamera2"`.

**Install Ollama and the local AI model:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull qwen3:4b
ollama list
```

The model is approximately 2.3 GB and takes 10–20 minutes to download on typical home broadband. Qwen3:4B is a candidate model; it becomes accepted only after passing the benchmark in Step 7.

**Build local speech-to-text (whisper.cpp):**

```bash
cd "$HOME"
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp

cmake -B build \
  -DWHISPER_BUILD_TESTS=OFF \
  -DWHISPER_BUILD_EXAMPLES=ON
cmake --build build --config Release -j2
bash models/download-ggml-model.sh base

test -x "$HOME/whisper.cpp/build/bin/whisper-cli"
test -f "$HOME/whisper.cpp/models/ggml-base.bin"
cd "$HOME/NinjaRobotPi5"
```

`-j2` uses two build jobs to limit heat. The multilingual `base` model handles both English and Japanese. Temporary audio is deleted after transcription; recognized text may remain in the seven-day conversation history.

**Verify the driver sources:**

```bash
uv run --frozen --extra hardware python \
  scripts/verify_workspace_driver_sources.py

uv run --frozen python scripts/verify_immutable_drivers.py
```

Expected result: all six `pi5*` packages resolve into this checkout and all driver file checksums match their approved records.

---

### Step 4 — Initialize and Calibrate Each Hardware Module

> [!IMPORTANT]
> This step creates configuration files in `~/.config`. Always include the configuration path options shown below — some tools create their files in the current directory if you omit them.

**Create configuration folders:**

```bash
mkdir -p \
  "$HOME/.config/pi5buzzer" \
  "$HOME/.config/pi5camera" \
  "$HOME/.config/pi5disp" \
  "$HOME/.config/pi5mic" \
  "$HOME/.config/pi5servo" \
  "$HOME/.config/pi5vl53l0x" \
  "$HOME/.config/ninjarobot_pi5"
```

> [!CAUTION]
> Raise both wheels off the work surface before any step that may activate the servos. Keep hair, hands, cables, and loose objects clear.

---

#### 4.1 — Buzzer (GPIO27)

```bash
uv run --frozen --extra hardware pi5buzzer \
  -C "$HOME/.config/pi5buzzer/buzzer.json" init 27

uv run --frozen --extra hardware pi5buzzer \
  -C "$HOME/.config/pi5buzzer/buzzer.json" buzzer-tool
```

Use the menu to play a short tone or melody. Exit after confirming the buzzer sounds and becomes silent.

---

#### 4.2 — Display (ST7789V)

```bash
PI5DISP_CONFIG="$HOME/.config/pi5disp/display.json" \
  uv run --frozen --extra hardware pi5disp display-tool
```

Choose **Init** and enter the following values:

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
uv run --frozen --extra hardware pi5vl53l0x sensor-tool \
  -c "$HOME/.config/pi5vl53l0x/vl53l0x.json"
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
uv run --frozen --extra hardware pi5servo servo-tool \
  -c "$HOME/.config/pi5servo/servo.json"
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
uv run --frozen --extra hardware pi5servo calib --show \
  --config "$HOME/.config/pi5servo/servo.json"
```

Expected result: both `gpio12` and `gpio13` are listed. If the result says `No calibrations stored`, see [Servo calibration saved to wrong file](#-servo-calibration-saved-to-the-wrong-file).

---

#### 4.5 — Camera (Raspberry Pi CSI)

> [!CAUTION]
> Tell everyone nearby before taking or retaining a photograph. Obtain their consent first.

```bash
uv run --frozen --extra hardware pi5camera \
  -C "$HOME/.config/pi5camera/camera.json" camera-tool
```

Choose **Run setup wizard**. For the current OV5647 camera, enter:

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
uv run --frozen --extra hardware pi5mic \
  -C "$HOME/.config/pi5mic/mic.json" mic-tool
```

Choose **Run setup wizard**, select your USB microphone, and accept a supported sample rate. Then choose **Run doctor** and **Show status**. Recording and speech-to-text tests are in [Microphone test](#-microphone-test) because they require consent.

> [!NOTE]
> If the tool selects 44.1 kHz when you configured 16 kHz, this is normal. Some USB microphones do not support 16 kHz. The robot software handles this fallback automatically.

---

### Step 5 — Import Settings into the Integrated Robot Configuration

The NinjaRobotPi5 IDE reads its own unified configuration file, separate from the individual module JSON files. This step copies the relevant settings from Steps 4.1–4.6 into that unified file.

> [!IMPORTANT]
> The import is one-way and read-only. The IDE never rewrites the standalone `pi5*` JSON files, and the standalone tools never rewrite the integrated `config.toml`.

**Set a short variable for the integrated configuration path:**

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
```

**Check which standalone files the IDE finds:**

```bash
uv run --frozen ninjarobot-ide-tool config discover
```

Expected result: all six entries show the canonical files created in Step 4.

**Preview the import (nothing is written yet):**

```bash
uv run --frozen ninjarobot-ide-tool config import \
  --destination "$NINJAROBOT_CONFIG"
```

The preview intentionally shows `"applied": false`. This is not an error — it means the file has not been written yet. Confirm the preview shows:

- Buzzer on GPIO27
- Display with DC GPIO4, RST GPIO5, BL GPIO6, rotation 90, brightness 75
- Servo calibration path: `/home/YOUR_USERNAME/.config/pi5servo/servo.json`
- Camera profile (1280×720, autofocus `none`)
- Microphone profile (USB device, sample rate)

**Apply the reviewed settings:**

```bash
uv run --frozen ninjarobot-ide-tool config import \
  --destination "$NINJAROBOT_CONFIG" \
  --apply

chmod 600 "$NINJAROBOT_CONFIG"
```

> [!NOTE]
> The first import does not overwrite an existing file. If the destination already exists, use the synchronization procedure in the [Appendix](#-synchronize-changed-module-settings-with-the-ide).

**Enable integrated wheel movement:**

```bash
nano "$NINJAROBOT_CONFIG"
```

Confirm these sections contain the following values (add or edit as needed):

```toml
[hardware.servos]
enabled = true
endpoints = ["gpio12", "gpio13"]
calibration_file = "~/.config/pi5servo/servo.json"
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

Save with `Ctrl+O`, Enter, then `Ctrl+X`.

**Validate the merged configuration:**

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$NINJAROBOT_CONFIG"

uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status
```

Expected result: validation succeeds, both servo endpoints are listed, and the calibration file exists.

---

### Step 6 — Test the Installed Robot

**Start with simulation — no hardware is opened:**

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" behavior list

uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" behavior health

uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" behavior simulate greeting

uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" behavior simulate move_forward \
  --duration 2
```

Expected result: all commands finish without opening physical devices. The simulation output describes the face, tone, and motion that would run.

**Run non-moving hardware health checks:**

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status --real
```

**Open the interactive robot tool:**

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG"
```

Normal behavior selections in this menu execute real hardware. Choose **Simulation** for a hardware-free preview. Test in this order:

1. **Hardware Configurations** — verify the connected profile
2. **Simulation** — preview any behavior without hardware
3. A face expression — confirm the display updates
4. **Greeting** — confirm the full greeting sequence
5. **Emergency Stop** — confirm the emergency stop sign appears
6. **Resume Robot Movement** — confirm the robot returns to Idle
7. A wheel movement — with **both wheels raised**

> [!CAUTION]
> Before any wheel movement test, prepare an emergency stop in a second SSH terminal. Navigate there and run:
> ```bash
> cd "$HOME/NinjaRobotPi5"
> export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
> uv run --frozen --extra hardware ninjarobot-ide-tool \
>   --config "$NINJAROBOT_CONFIG" behavior stop
> ```
> Do not press Enter yet. Start the movement in the first terminal, then press Enter in the second terminal if you need to stop it.

---

### Step 7 — Set Up and Verify NinjaRobotAgent

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

uv run --frozen ninjarobot-agent benchmark ollama \
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

**Select the model:**

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model list

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model select qwen3:4b

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model current
```

**Start the agent in simulation:**

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start

uv run --frozen ninjarobot-agent status
uv run --frozen ninjarobot-agent chat \
  "Reply with one short greeting and do not use a tool."
```

**Start the HTTPS web interface:**

```bash
uv run --frozen ninjarobot-agent web certificate-status
uv run --frozen ninjarobot-agent web export-ca \
  --output "$HOME/ninjarobotpi5-local-ca.pem"
uv run --frozen ninjarobot-agent web start
```

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

**Test the web controller in simulation:**

1. ✅ Chat sends a message and streams a response
2. ✅ Live Activity tab shows service and tool events
3. ✅ D-pad buttons simulate movement and stop when released
4. ✅ **X** performs simulated Emergency Stop
5. ✅ **Y** asks for confirmation before Resume
6. ✅ **A** runs Greeting, **B** runs Celebrate
7. ✅ Camera button shows a simulated preview
8. ✅ USB Microphone returns simulated recognized text
9. ✅ Web Microphone fills the message box with recognized text (sent only when you press **Send**)

**Stop the services:**

```bash
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent service stop
```

**Start with real hardware (after all Phase 4 physical tests pass):**

```bash
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start --real

uv run --frozen ninjarobot-agent web start
```

In real mode, startup runs the **Greeting** behavior once, then loops a silent **Idle** face between interactions. The normal conversation flow is:

```text
Idle → Thinking → Speaking (or emotion) → robot action → Idle
```

---

## 🤖 Using the AI Agent

### Chat Commands

Once the service is running, open a chat session:

```bash
uv run --frozen ninjarobot-agent
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
| `/confirm <request>` | Approve a sensitive one-off action |
| `/clear` | Clear the current conversation history |
| `/exit` | Disconnect this terminal (service keeps running) |

### Enabling AI Motion (Physical Movement)

To let the AI move the robot's wheels, raise the wheels first, then:

```bash
# Inside the chat:
/arm
# Type ARM when prompted
```

Motion authorization is session-lived. It stays active while a local model is reasoning and ends only on `/disarm`, Emergency Stop, browser disconnect, model change, or service stop.

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
/confirm Save the successful behavior as my_exciting_move.
```

### Recovering from Emergency Stop

If the Emergency Stop is triggered (Level 2), enter `/resume` in the terminal or web chat box and type `RESUME` when asked. The agent runs all-module health checks directly — it does not ask the AI model. On success, the Emergency Stop clears and Idle returns. AI motion stays disarmed; use `/arm` separately before asking for another servo movement.

### Enabling an AI-Controlled Photo

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

## 🧪 Testing and Troubleshooting

### Recommended Validation Order

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

### 🔬 Software and Simulation Test

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen pytest -q
```

Expected result: driver verification passes and all tests pass. These tests use simulation only.

### 🔊 Buzzer Test

```bash
uv run --frozen --extra hardware pi5buzzer \
  -C "$HOME/.config/pi5buzzer/buzzer.json" buzzer-tool
```

Expected result: a short tone or melody plays through GPIO27 and the buzzer is silent afterward.
Full checklist: [Phase 3.1 buzzer validation](docs/validation/phase-3-1-buzzer-validation-2026-07-26.md)

### 🖥️ Display Test

```bash
PI5DISP_CONFIG="$HOME/.config/pi5disp/display.json" \
  uv run --frozen --extra hardware pi5disp display-tool
```

Expected result: text and colors are correctly oriented at 320×240 after the 90° rotation, and brightness changes take effect.
Full checklist: [Phase 3.2 display validation](docs/validation/phase-3-2-display-validation-2026-07-26.md)

### 📡 Distance Sensor Test

```bash
uv run --frozen --extra hardware pi5vl53l0x sensor-tool \
  -c "$HOME/.config/pi5vl53l0x/vl53l0x.json"
```

Expected result: a target within range produces changing millimetre readings. Open space may produce the raw value `8191`, which means no target is measurable.
Full checklist: [Phase 2 distance validation](docs/validation/phase-2-validation-2026-07-26.md)

### ⚙️ Servo Test

> [!CAUTION]
> Raise the wheels and keep an operator ready to remove power.

```bash
uv run --frozen --extra hardware pi5servo servo-tool \
  -c "$HOME/.config/pi5servo/servo.json"
```

Expected result: each motor turns in both directions and stops at its calibrated center. Recalibrate if a motor creeps at center.
Full checklist: [Phase 3.3 servo validation](docs/validation/phase-3-3-servo-validation-2026-07-26.md)

### 📷 Camera Test

> [!CAUTION]
> Tell everyone nearby and obtain consent before capturing.

```bash
/usr/bin/python3 -s -c \
  "import libcamera, picamera2; print('Picamera2:', picamera2.__file__)"

rpicam-hello --list-cameras

uv run --frozen --extra hardware pi5camera \
  -C "$HOME/.config/pi5camera/camera.json" camera-tool
```

Full checklist: [Phase 3.4 camera validation](docs/validation/phase-3-4-camera-validation-2026-07-26.md)

### 🎙️ Microphone Test

> [!CAUTION]
> Tell everyone nearby and obtain consent before recording.

```bash
arecord -l

uv run --frozen --extra hardware pi5mic \
  -C "$HOME/.config/pi5mic/mic.json" mic-tool
```

Choose **Run one capture cycle**. If the sample rate falls back to 44.1 kHz, that is normal when the device reports ready.
Full checklist: [Phase 3.5 microphone validation](docs/validation/phase-3-5-microphone-validation-2026-07-26.md)

### 🤖 Integrated Behavior Test

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml"
```

Use **Simulation** first. During real wheel movement, note:

- Movement starts without waiting for clear sensor readings
- The value `8191` means clear (no target in range), not an error
- Three consecutive valid readings at or below 50 mm stop forward and turning movement (Level 1)
- `null`, invalid, missing, and stale readings do not stop movement
- Backward movement continues with a warning because the sensor faces forward

Full checklists:
- [Phase 4 integrated behavior validation](docs/validation/phase-4-integrated-behavior-validation-2026-07-26.md)
- [Phase 4 animated-face and interactive-tool validation](docs/validation/phase-4-refinement-validation-2026-07-27.md)

---

### Common Problems and Fixes

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
uv run --frozen ninjarobot-ide-tool config import \
  --destination "$HOME/.config/ninjarobot_pi5/config.toml" \
  --apply
```

If the destination already exists, use the synchronization procedure in the [Appendix](#-synchronize-changed-module-settings-with-the-ide).

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
uv run --frozen --extra hardware pi5servo calib --show \
  --config "$HOME/.config/pi5servo/servo.json"

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" hardware status --real
```

Both calibrations must exist, both motion flags must be `true`, and no safety latch must be active.

If a Level 1 motion latch is active:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  motion resume --confirm
```

If a driver-failure Level 2 latch is active:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  system resume --confirm
```

If the IDE says the hardware is already owned by the agent service, use the agent instead:

```bash
uv run --frozen ninjarobot-agent
# Then type: /resume
# Then type: RESUME
```

---

#### 🤖 Agent Service Is Unavailable

```bash
systemctl status ollama --no-pager
ollama list
uv run --frozen ninjarobot-agent service status
tail -n 100 "$HOME/.local/state/ninjarobot_pi5/agent-service.log"
```

---

#### 🔒 Web Interface Shows `423 Locked`

Another browser holds the one controller lease. Close that browser and wait about 10 seconds, or restart the web interface:

```bash
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent web start
```

---

#### 🔐 Browser Rejects the HTTPS Certificate

Restart the web interface to upgrade older certificates:

```bash
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent web start
grep -c 'BEGIN CERTIFICATE' \
  "$HOME/.config/ninjarobot_pi5/tls/agent-cert.pem"
```

The count should be `2`. If Chrome offers **Advanced → Proceed**, accept it and reload. For Safari and reliable browser microphone access, install the public CA:

```bash
uv run --frozen ninjarobot-agent web export-ca \
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
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  --whisper-command /absolute/path/to/whisper-cli \
  --whisper-model /absolute/path/to/ggml-model.bin \
  service start --real
```

---

#### ⚡ Raspberry Pi Reports Undervoltage

```bash
vcgencmd get_throttled
```

`throttled=0x0` means no current or recorded power issue. Any other value needs investigation. Stop servo motion, check the official supply, X1208 board, connectors, and wiring. Do not continue movement tests until power is stable.

---

## 📎 Appendix

### 🔧 Using Optional Cloud AI Providers

You can skip this section and keep using Ollama. Cloud providers require an internet connection, send your conversation and tool descriptions to the provider, and may charge your account. Robot tools still run locally — the cloud adapter cannot access the Pi hardware directly.

All three providers use API keys only. Browser logins, Google OAuth, and Anthropic `ant` logins are not used.

**OpenAI:**

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider set-api-key openai

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider health openai

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model list --provider openai
```

**Google Gemini:**

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider set-api-key gemini

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider health gemini
```

**Anthropic:**

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider set-api-key anthropic

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider health anthropic
```

Select a model once you see the available list:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  model select MODEL_ID --provider PROVIDER_ID
```

Do not copy a model name from an old guide — provider catalogs change over time.

---

### 🔄 Synchronize Changed Module Settings with the IDE

Use this procedure after changing buzzer, display, camera, or microphone settings in the standalone tools.

1. Exit any running `ninjarobot-ide-tool` process.
2. Save the new settings using the standalone tool with its canonical path.
3. Set the integrated path:

```bash
cd "$HOME/NinjaRobotPi5"
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
```

4. Confirm discovery finds the updated files:

```bash
uv run --frozen ninjarobot-ide-tool config discover
```

5. Preview the update (uses the current integrated file as base):

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" \
  config import \
  --destination "$NINJAROBOT_CONFIG"
```

6. Review the preview carefully — confirm safety values, servo roles, and AI settings are still correct.

7. Apply:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" \
  config import \
  --destination "$NINJAROBOT_CONFIG" \
  --apply \
  --overwrite

chmod 600 "$NINJAROBOT_CONFIG"
```

8. Validate and verify hardware:

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$NINJAROBOT_CONFIG"

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status --real
```

`--overwrite` is required because the destination already exists. It does not overwrite any standalone `pi5*` JSON file.

---

### 🌐 Set Up Tavily Web Search (Optional)

Tavily lets the AI search the internet for current information. It is optional — the robot works fully without it.

> [!IMPORTANT]
> Tavily may provide a free allowance. Check [current API credit documentation](https://docs.tavily.com/documentation/api-credits) before registering, because price, quota, and terms can change.

1. Create a free account at [app.tavily.com](https://app.tavily.com/) and copy your API key.

2. Store the key securely (the prompt hides what you type):

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen ninjarobot-agent secret set TAVILY_API_KEY
```

3. Install the bundled Tavily preset:

```bash
uv run --frozen ninjarobot-agent mcp add --preset tavily --id tavily
```

4. Verify the connection:

```bash
uv run --frozen ninjarobot-agent mcp health tavily
uv run --frozen ninjarobot-agent mcp tools tavily
```

Expected result: the server is healthy and the API key shows as redacted (not visible).

5. Run a test search:

```bash
uv run --frozen ninjarobot-agent \
  mcp test tavily --tool tavily-search \
  --arguments '{"query":"Raspberry Pi official news","max_results":3}'
```

6. Restart the agent service so it picks up the new MCP catalog, then ask:

```text
Search the web for the latest official Raspberry Pi news and show your sources.
```

Expected result: the answer includes source links. If internet access or quota is unavailable, the agent should say it cannot verify a current answer.

---

### 🛠️ Standalone `pi5*` Library Reference

| Library | Canonical config file | What the IDE copies |
|---|---|---|
| `pi5buzzer` | `~/.config/pi5buzzer/buzzer.json` | GPIO pin number |
| `pi5disp` | `~/.config/pi5disp/display.json` | Wiring, dimensions, rotation, brightness, SPI speed |
| `pi5servo` | `~/.config/pi5servo/servo.json` | Reference path (IDE reads calibration directly) |
| `pi5vl53l0x` | `~/.config/pi5vl53l0x/vl53l0x.json` | Detected but not copied; IDE uses its own I2C settings |
| `pi5camera` | `~/.config/pi5camera/camera.json` | Width, height, warm-up time, autofocus mode |
| `pi5mic` | `~/.config/pi5mic/mic.json` | Input device, sample rate, channel count |

Always run each library from the root NinjaRobotPi5 environment:

```bash
cd "$HOME/NinjaRobotPi5"
uv sync --frozen --extra hardware
```

Stop the agent and integrated IDE before opening any standalone hardware tool.

**Quick links to library guides:**

- [pi5buzzer README](pi5buzzer/README.md)
- [pi5camera README](pi5camera/README.md)
- [pi5disp README](pi5disp/README.md)
- [pi5mic README](pi5mic/README.md)
- [pi5servo README](pi5servo/README.md)
- [pi5vl53l0x README](pi5vl53l0x/README.md)

---

### 📦 Updating NinjaRobotPi5

Stop all tools and services before updating:

```bash
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent service stop

cd "$HOME/NinjaRobotPi5"
git status --short
git pull --ff-only
uv sync --frozen --extra hardware
./scripts/bootstrap-rpi-camera-workspace.sh --skip-apt

uv run --frozen --extra hardware python \
  scripts/verify_workspace_driver_sources.py
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen pytest -q
```

`git pull --ff-only` refuses to combine unexpected local source changes with the downloaded update. Your personal configuration under `~/.config` and retained media under `~/.local` remain outside the Git checkout and are never affected by updates.
