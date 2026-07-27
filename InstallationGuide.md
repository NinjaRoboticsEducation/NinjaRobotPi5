# NinjaRobotPi5V4 Installation Guide

This guide takes you from a blank microSD card to a configured and tested
NinjaRobotPi5. Follow the numbered installation steps in order. Testing,
troubleshooting, and advanced configuration are collected later so the main
installation remains easy to follow.

The recommended operating system is **Raspberry Pi OS Lite 64-bit**. Lite does
not install a graphical desktop. This leaves more memory and processing power
available for robot control and future local AI models.

## 1. Project overview

### What NinjaRobotPi5 is

NinjaRobotPi5 is Python software for a Raspberry Pi 5 robot. It brings the
display, buzzer, wheel servos, distance sensor, camera, and microphone together
behind one consistent robot interface.

Each `pi5*` library can still configure and test its own hardware independently.
The NinjaRobotPi5 IDE then uses selected settings from those standalone
configuration files. IDE means integrated development environment; in this
project it is the safe software boundary that coordinates all robot devices.

### Current hardware profile

The installation steps use this confirmed robot configuration:

| Part | Current connection or setting |
|---|---|
| Computer | Raspberry Pi 5, 64-bit operating system |
| Storage | microSD card or NVMe solid-state storage |
| Expansion board | DFRobot DFR0566 |
| Left wheel servo | MG90D 360-degree servo, signal on GPIO12 |
| Right wheel servo | MG90D 360-degree servo, signal on GPIO13 |
| Buzzer | Passive buzzer on GPIO27 |
| Distance sensor | Forward-facing VL53L0X on I2C bus 1, address `0x29` |
| Display | ST7789V, 240×320, SPI0, DC GPIO4, reset GPIO5, backlight GPIO6 |
| Display presentation | Rotation 90 degrees, brightness 75% |
| Camera | Raspberry Pi CSI camera; current camera is OV5647 |
| Microphone | USB audio-input device |
| Power | Official 27 W supply through the Geekworm X1208 power chain |

GPIO means general-purpose input/output, the numbered electrical connections
on the Raspberry Pi. I2C is a two-wire connection used by sensors and expansion
boards. SPI is a fast connection used by the display. CSI is the Raspberry Pi
flat-ribbon camera connection. PWM means pulse-width modulation, the electrical
signal that controls the servos.

The MG90D motors are continuous-rotation servos. A command such as `45` controls
direction and speed around the calibrated neutral point; it does not request a
physical 45-degree position.

### Software used

- Raspberry Pi OS Lite 64-bit
- Git, which downloads and updates the project
- `uv`, which installs Python and the project's locked Python packages
- Raspberry Pi camera packages
- PortAudio and ALSA audio tools for the USB microphone
- NinjaRobotPi5 and its six managed `pi5*` hardware libraries

### Project file structure

After installation, the important project folders are:

```text
NinjaRobotPi5/
├── ninjarobot_pi5_ide/       Coordinates robot hardware and behaviors
├── ninjarobot_pi5_agent/     Future AI-agent integration
├── pi5buzzer/                Standalone buzzer library
├── pi5camera/                Standalone camera library
├── pi5disp/                  Standalone display library
├── pi5mic/                   Standalone microphone library
├── pi5servo/                 Standalone servo library
├── pi5vl53l0x/               Standalone distance-sensor library
├── config/                   Safe example robot configuration
├── scripts/                  Installation and validation helpers
└── docs/validation/          Detailed hardware test checklists
```

Personal settings and captured media are intentionally stored outside the
project folder:

```text
~/.config/pi5*/                    Standalone module settings
~/.config/ninjarobot_pi5/          Integrated robot settings and behaviors
~/.local/share/ninjarobot_pi5/     Retained camera and microphone files
~/.local/state/ninjarobot_pi5/     Safety state
```

`~` means your Linux home directory, such as `/home/rogerchang`. Keeping
personal data outside the downloaded source folder makes Git updates and
project reinstallation safer.

## 2. Step-by-step installation guide

### Step 1 — Install Raspberry Pi OS Lite 64-bit

You need another Windows, macOS, or Linux computer and a microSD card reader.

1. Install and open
   [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Select **Raspberry Pi 5** as the device.
3. Select **Raspberry Pi OS (other)** and then
   **Raspberry Pi OS Lite (64-bit)**.
4. Select the microSD card.
5. Open the operating-system customisation screen and set:
   - a hostname, such as `ninjarobotpi5`
   - your username and a strong password
   - your Wi-Fi name, password, and wireless country
   - your time zone and keyboard layout
   - SSH access
6. For SSH, use public-key authentication if you know how to use it.
   Password authentication is easier for a first installation but needs a
   strong password. SSH means secure shell, a protected remote terminal.
7. Write the image. This erases everything already on the selected card.
8. With the Raspberry Pi powered off, insert the card and check all wiring.
9. Apply power and allow several minutes for the first boot.

From another computer on the same network, connect with:

```bash
ssh YOUR_USERNAME@ninjarobotpi5.local
```

Replace `YOUR_USERNAME` with the username selected in Raspberry Pi Imager. If
`.local` name discovery does not work, find the Raspberry Pi's IP address in
your router and use:

```bash
ssh YOUR_USERNAME@RASPBERRY_PI_IP_ADDRESS
```

All remaining commands in this guide run in this SSH terminal.

### Step 2 — Configure Raspberry Pi OS and install system software

Update the operating system:

```bash
sudo apt update
sudo apt full-upgrade -y
```

Install the tools required by NinjaRobotPi5:

```bash
sudo apt install -y \
  git \
  curl \
  i2c-tools \
  alsa-utils \
  libportaudio2 \
  portaudio19-dev
```

Enable I2C for the expansion board and distance sensor, and SPI for the
display:

```bash
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
```

Enable the two Raspberry Pi hardware-PWM channels used by GPIO12 and GPIO13:

```bash
sudo nano /boot/firmware/config.txt
```

In the editor:

1. Find `dtparam=audio=on` and change it to `dtparam=audio=off`. If the line
   does not exist, add `dtparam=audio=off` under the active `[all]` section.
2. Add this line under the same active section:

```ini
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

3. Press `Ctrl+O`, press Enter, and then press `Ctrl+X`.

This provides two PWM channels: PWM0 on GPIO12 and PWM1 on GPIO13. GPIO18 and
GPIO19 are alternative routes for those same two channels, not two additional
channels.

Reboot:

```bash
sudo reboot
```

Wait about one minute and reconnect over SSH:

```bash
ssh YOUR_USERNAME@ninjarobotpi5.local
```

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

Expected result: the last command prints a `uv` version. The installer normally
adds `uv` to future terminal sessions automatically.

### Step 3 — Download and install NinjaRobotPi5

Download the project into your home directory:

```bash
cd "$HOME"
git clone https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git
cd NinjaRobotPi5
```

Install the locked project environment and all hardware libraries:

```bash
uv sync --frozen --extra hardware
```

`uv` creates the `.venv` virtual environment automatically. A virtual
environment is an isolated set of Python packages for this project. You do not
need to run `source .venv/bin/activate`; all commands in this guide use
`uv run`.

`--frozen` tells `uv` to install the versions already recorded in `uv.lock`
without changing that file. `--extra hardware` adds the Raspberry Pi hardware
packages that simulation alone does not need.

Prepare the Raspberry Pi camera bridge:

```bash
./scripts/bootstrap-rpi-camera-workspace.sh
```

This installs the matching Raspberry Pi OS Picamera2 and libcamera packages,
keeps the normal project environment, and verifies the camera bridge without
taking a photograph. Picamera2 is Raspberry Pi's Python camera interface.

Verify that Python is using all six libraries from this downloaded project:

```bash
uv run --frozen --extra hardware python \
  scripts/verify_workspace_driver_sources.py

uv run --frozen python scripts/verify_immutable_drivers.py
```

Expected result: the first command resolves all six `pi5*` packages into this
checkout. The second command reports that all managed driver files match their
approved records.

### Step 4 — Initialize and calibrate each hardware module

This step deliberately saves every standalone configuration under
`~/.config`. Do not omit the configuration options from these commands.
Otherwise some tools create files such as `servo.json` or `buzzer.json` in the
project root, which is not the preferred integrated configuration location.

Create the configuration folders:

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

Keep the wheels raised so they cannot drive the robot off the work surface.
Never connect, disconnect, or change wiring while power is on.

#### 4.1 Buzzer on GPIO27

Create the buzzer configuration and open its guided tool:

```bash
uv run --frozen --extra hardware pi5buzzer \
  -C "$HOME/.config/pi5buzzer/buzzer.json" init 27

uv run --frozen --extra hardware pi5buzzer \
  -C "$HOME/.config/pi5buzzer/buzzer.json" buzzer-tool
```

Use the menu to run a short beep or melody. Exit after confirming the buzzer
sounds and becomes silent again.

#### 4.2 ST7789V display

Open the display tool with an explicit configuration location:

```bash
PI5DISP_CONFIG="$HOME/.config/pi5disp/display.json" \
  uv run --frozen --extra hardware pi5disp display-tool
```

Choose **Init** and enter:

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

Then use **Show Text**, **Brightness**, and **Clear** to confirm the screen
works. MHz means megahertz, or one million signal cycles per second.

#### 4.3 VL53L0X distance sensor

Open the sensor tool:

```bash
uv run --frozen --extra hardware pi5vl53l0x sensor-tool \
  -c "$HOME/.config/pi5vl53l0x/vl53l0x.json"
```

Use the menu to check status and take several readings. Place a flat object in
front of the sensor when checking distance accuracy.

The raw value `8191` means that no target is measurable in range. It proves the
sensor communicated, but it is not a real distance. A `null` result indicates
a communication error, timeout, disconnect, or stale reading and should be
investigated.

Only calibrate after ordinary readings work. Place a flat target at an
accurately measured distance and follow the calibration prompts.

#### 4.4 GPIO12 and GPIO13 wheel servos

> [!CAUTION]
> Servo calibration moves the motors. Raise the wheels, keep hair, hands,
> cables, and loose objects clear, and be ready to remove robot power. This
> robot currently has no separate physical servo cutoff, so software stop
> cannot remove every electrical risk.

Open the servo tool with the canonical calibration file:

```bash
uv run --frozen --extra hardware pi5servo servo-tool \
  -c "$HOME/.config/pi5servo/servo.json"
```

In the menu:

1. Choose **Calibrate**.
2. Enter `gpio12`.
3. Find and save the neutral point at which the left wheel stops.
4. Repeat for `gpio13`.
5. Use **Status** to confirm that both records are stored.
6. Use a low-speed **Quick Move** or **Single Move** test.
7. Return both motors to neutral and exit.

For these continuous-rotation servos, the calibrated center is the stop
position. Pulse limits and center values can differ between two motors of the
same model.

Confirm the saved records without moving:

```bash
uv run --frozen --extra hardware pi5servo calib --show \
  --config "$HOME/.config/pi5servo/servo.json"
```

Expected result: `gpio12` and `gpio13` are both listed. If the result says
`No calibrations stored`, see
[Servo calibration exists in the wrong file](#servo-calibration-exists-in-the-wrong-file).

#### 4.5 Raspberry Pi camera

Tell everyone nearby before taking or retaining a photograph.

```bash
uv run --frozen --extra hardware pi5camera \
  -C "$HOME/.config/pi5camera/camera.json" camera-tool
```

Choose **Run setup wizard**. For the current OV5647 camera, use:

- width `1280`
- height `720`
- warm-up time `1.0`
- autofocus mode `none`
- no preview on the headless Lite system

Then choose **Run doctor** and **Show status**. Capture a test photograph only
after everyone nearby agrees.

#### 4.6 USB microphone

Check that Linux sees the USB microphone:

```bash
arecord -l
```

Then open the microphone tool:

```bash
uv run --frozen --extra hardware pi5mic \
  -C "$HOME/.config/pi5mic/mic.json" mic-tool
```

Choose **Run setup wizard**, select the USB microphone, and accept a supported
sample rate. Then choose **Run doctor** and **Show status**. Recording and
speech-to-text testing belong in
[Microphone test](#microphone-test) because they require consent and may
create an audio file.

### Step 5 — Set up and initialize the NinjaRobotPi5 IDE

The IDE import is read-only with respect to every standalone JSON file. It
copies only the settings that the integrated robot understands.

Set a short variable for the integrated configuration path:

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
```

Check which standalone files the IDE finds:

```bash
uv run --frozen ninjarobot-ide-tool config discover
```

Expected result: all six entries show the canonical files created in Step 4.

Preview the import:

```bash
uv run --frozen ninjarobot-ide-tool config import \
  --destination "$NINJAROBOT_CONFIG"
```

The preview intentionally reports `"applied": false`. This means nothing has
been written yet; it is not an error. Check that the preview includes:

- buzzer GPIO27
- display GPIO4, GPIO5, GPIO6, rotation 90, and brightness 75
- servo calibration path
  `/home/YOUR_USERNAME/.config/pi5servo/servo.json`
- camera profile
- microphone profile

Apply the reviewed settings:

```bash
uv run --frozen ninjarobot-ide-tool config import \
  --destination "$NINJAROBOT_CONFIG" \
  --apply

chmod 600 "$NINJAROBOT_CONFIG"
```

The first import does not overwrite an existing file. If the destination
already exists, use the synchronization procedure in
[Synchronize changed module settings with the IDE](#synchronize-changed-module-settings-with-the-ide).

Enable integrated wheel movement:

```bash
nano "$NINJAROBOT_CONFIG"
```

Confirm these sections contain the following values:

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
obstacle_threshold_mm = 100
obstacle_consecutive_readings = 3
clear_readings_before_motion = 3

[behaviors.servo_roles]
left_motor = "gpio12"
right_motor = "gpio13"
```

Save with `Ctrl+O`, Enter, and `Ctrl+X`.

Check the integrated configuration and hardware record:

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$NINJAROBOT_CONFIG"

uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status
```

Expected result: validation succeeds, both servo endpoints are listed, and the
servo calibration file exists.

### Step 6 — Test and verify the installed robot

Start with simulation. Simulation does not open GPIO, PWM, I2C, SPI, camera, or
microphone hardware:

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

Expected result: all commands finish without opening physical devices. The
simulation result describes the face, tone, and motion that would run.

Run non-moving physical health checks:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status --real
```

Now open the interactive robot tool:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG"
```

Normal behavior selections in this menu execute real configured hardware.
Choose **Simulation** for a hardware-free preview. Test in this order:

1. **Hardware Configurations**
2. **Simulation**
3. A face expression
4. **Greeting**
5. **Emergency Stop**
6. **Resume Robot Movement**
7. Wheel movement, with both wheels raised

Before a real movement test, open a second SSH terminal and prepare:

```bash
cd "$HOME/NinjaRobotPi5"
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" behavior stop
```

Do not press Enter yet. Start a short movement from the first terminal, then
press Enter in the second terminal to request the Level 2 stop.

For complete device-by-device checks, expected results, and rollback steps,
continue with [Simulation, testing, and troubleshooting](#3-simulation-testing-and-troubleshooting).

## 3. Simulation, testing, and troubleshooting

### Recommended validation order

Use this order after the main installation:

1. Software-only simulation
2. Configuration discovery and validation
3. Non-moving device health checks
4. Buzzer and display tests
5. Distance readings
6. Camera and microphone tests with consent
7. Servo tests with raised wheels
8. Integrated robot behaviors

Never change wiring while the robot is powered.

### Software and simulation test

Run the complete software test suite:

```bash
cd "$HOME/NinjaRobotPi5"

uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen pytest -q
```

Expected result: managed-driver verification passes and all tests pass. These
tests use simulation and do not move the robot.

### Buzzer test

```bash
uv run --frozen --extra hardware pi5buzzer \
  -C "$HOME/.config/pi5buzzer/buzzer.json" buzzer-tool
```

Expected result: a selected short tone or melody plays through GPIO27 and the
buzzer is silent afterward.

Detailed checklist:
[Phase 3.1 buzzer validation](docs/validation/phase-3-1-buzzer-validation-2026-07-26.md).

### Display test

```bash
PI5DISP_CONFIG="$HOME/.config/pi5disp/display.json" \
  uv run --frozen --extra hardware pi5disp display-tool
```

Expected result: text and colors are correctly oriented at 320×240 after the
configured 90-degree rotation, and brightness changes work.

Detailed checklist:
[Phase 3.2 display validation](docs/validation/phase-3-2-display-validation-2026-07-26.md).

### Distance-sensor test

```bash
uv run --frozen --extra hardware pi5vl53l0x sensor-tool \
  -c "$HOME/.config/pi5vl53l0x/vl53l0x.json"
```

Expected result: a target within range produces changing millimetre readings.
Open space may produce raw `8191`, meaning no target is measurable.

Detailed checklist:
[Phase 2 distance validation](docs/validation/phase-2-validation-2026-07-26.md).

### Servo test

> [!CAUTION]
> Raise the wheels and keep an operator ready to remove power.

```bash
uv run --frozen --extra hardware pi5servo servo-tool \
  -c "$HOME/.config/pi5servo/servo.json"
```

Expected result: each motor turns in both directions and stops at its calibrated
center. Stop and recalibrate if a motor creeps while commanded to center.

Detailed checklist:
[Phase 3.3 servo validation](docs/validation/phase-3-3-servo-validation-2026-07-26.md).

### Camera test

Check the Raspberry Pi OS camera bindings and connected camera:

```bash
/usr/bin/python3 -s -c \
  "import libcamera, picamera2; print('Picamera2:', picamera2.__file__)"

rpicam-hello --list-cameras
```

Then run:

```bash
uv run --frozen --extra hardware pi5camera \
  -C "$HOME/.config/pi5camera/camera.json" camera-tool
```

Tell everyone nearby before choosing **Capture photo**. The standalone camera
tool uses the directories selected during its setup wizard.

Detailed checklist:
[Phase 3.4 camera validation](docs/validation/phase-3-4-camera-validation-2026-07-26.md).

### Microphone test

Tell everyone nearby and obtain consent before recording:

```bash
arecord -l

uv run --frozen --extra hardware pi5mic \
  -C "$HOME/.config/pi5mic/mic.json" mic-tool
```

Choose **Run one capture cycle**. If the microphone rejects the requested
sample rate but selects a supported rate such as 44.1 kHz, that fallback is
normal when status remains ready. Hz means samples per second for audio.

Detailed checklist:
[Phase 3.5 microphone validation](docs/validation/phase-3-5-microphone-validation-2026-07-26.md).

### Integrated behavior test

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml"
```

Use **Simulation** first. During real wheel movement:

- three clear front-distance results are required before movement starts
- readings above 100 mm permit movement
- the exact out-of-range value `8191` also permits movement
- three consecutive valid readings below 100 mm cause a Level 1 motion stop
- `null` is treated as a communication problem, not clear space
- backward and turning movement cannot protect unseen rear or side areas

Detailed checklists:

- [Phase 4 integrated behavior validation](docs/validation/phase-4-integrated-behavior-validation-2026-07-26.md)
- [Phase 4 animated-face and interactive-tool validation](docs/validation/phase-4-refinement-validation-2026-07-27.md)

### Common installation problems

#### `uv: command not found`

Run:

```bash
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

If that works, reconnect over SSH so the shell loads the installer changes.
If it still fails, reinstall:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### A warning says `VIRTUAL_ENV ... does not match`

This happens when a different virtual environment is active while `uv` is
running a nested `pi5*` project. Leave the active environment and use the
root commands from this guide:

```bash
deactivate 2>/dev/null || true
cd "$HOME/NinjaRobotPi5"
uv sync --frozen --extra hardware
```

Do not manually activate `.venv`; use `uv run`.

#### Servo calibration exists in the wrong file

If `servo-tool` was run without `-c`, it may have created
`$HOME/NinjaRobotPi5/servo.json`. Check both locations:

```bash
ls -l \
  "$HOME/NinjaRobotPi5/servo.json" \
  "$HOME/.config/pi5servo/servo.json" 2>/dev/null
```

If the project-root file contains the correct calibrations and the canonical
file does not yet exist, copy it:

```bash
mkdir -p "$HOME/.config/pi5servo"
cp "$HOME/NinjaRobotPi5/servo.json" \
  "$HOME/.config/pi5servo/servo.json"
chmod 600 "$HOME/.config/pi5servo/servo.json"
```

Then always use:

```bash
uv run --frozen --extra hardware pi5servo servo-tool \
  -c "$HOME/.config/pi5servo/servo.json"
```

Do not delete the old file until the canonical copy has been displayed and
tested successfully.

#### `config import` reports `"applied": false`

That is the expected preview. Apply it only after checking the values:

```bash
uv run --frozen ninjarobot-ide-tool config import \
  --destination "$HOME/.config/ninjarobot_pi5/config.toml" \
  --apply
```

If the destination already exists, follow the synchronization procedure in
the appendix so your existing robot-specific settings form the import base.

#### The IDE imports default or old module settings

Run discovery:

```bash
uv run --frozen ninjarobot-ide-tool config discover
```

The IDE checks canonical files under `~/.config` before most project-root
fallback files. Reopen each standalone tool with the explicit path documented
in Step 4, save its settings, then synchronize again.

There is no continuous two-way synchronization. The standalone tools never
rewrite the NinjaRobotPi5 TOML file, and the IDE never rewrites the standalone
JSON files.

#### Camera reports `No module named 'picamera2'` or `libcamera`

Run:

```bash
cd "$HOME/NinjaRobotPi5"
./scripts/bootstrap-rpi-camera-workspace.sh

/usr/bin/python3 -s -c \
  "import libcamera, picamera2; print('Picamera2:', picamera2.__file__)"
```

It is normal for the project `.venv` itself to be unable to import Picamera2.
NinjaRobotPi5 sends real camera work to the matching Raspberry Pi OS Python
environment through its camera bridge.

#### Microphone reports that PortAudio is missing

```bash
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev alsa-utils
uv sync --frozen --extra hardware
arecord -l
```

#### Display stays blank

Check that SPI is enabled and the device exists:

```bash
ls -l /dev/spidev0.0
```

Then confirm DC GPIO4, reset GPIO5, and backlight GPIO6. Do not rewire while
powered. Reopen `pi5disp display-tool` using `PI5DISP_CONFIG` and review its
saved settings.

#### Distance sensor always returns `8191`

`8191` is the sensor's out-of-range marker, not a measured distance. Aim the
forward-facing sensor at a large, light-coloured, flat target within its useful
range. If raw `8191` changes to a real millimetre value, the library is
communicating correctly.

If results are `null`, check I2C and the device address:

```bash
ls -l /dev/i2c-1
sudo i2cdetect -y 1
```

Expected addresses include `29` for the VL53L0X and `10` for the DFR0566.

#### Movement does not start

Check:

```bash
uv run --frozen --extra hardware pi5servo calib --show \
  --config "$HOME/.config/pi5servo/servo.json"

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" hardware status --real
```

Both calibrations must exist, both motion flags must be `true`, the safety
state must not be latched, and the front sensor must provide three clear
results. If a previous Level 1 stop is latched:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  motion resume --confirm
```

For a driver-failure Level 2 latch, use:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  system resume --confirm
```

Resume only after correcting the cause and making sure the robot is safe.

#### Raspberry Pi reports undervoltage

Check:

```bash
vcgencmd get_throttled
```

`throttled=0x0` means no current or recorded power warning. Any other value
needs investigation. Stop servo motion, check the official supply, X1208,
connectors, and wiring, and do not continue movement tests until power is
stable.

## 4. Appendix

### Best practice for standalone `pi5*` libraries

Use the root NinjaRobotPi5 environment when the libraries are part of this
project:

```bash
cd "$HOME/NinjaRobotPi5"
uv sync --frozen --extra hardware
```

Then run each library from the root with `uv run --frozen --extra hardware`.
Do not run `uv sync` separately inside every managed `pi5*` folder for normal
NinjaRobotPi5 use. Package-local environments are useful only when developing
or validating a library as a standalone project.

Always specify the configuration file:

| Library | Canonical file | How the IDE uses it |
|---|---|---|
| `pi5buzzer` | `~/.config/pi5buzzer/buzzer.json` | Copies the GPIO pin |
| `pi5disp` | `~/.config/pi5disp/display.json` | Copies wiring, dimensions, rotation, brightness, and SPI speed |
| `pi5servo` | `~/.config/pi5servo/servo.json` | Stores a reference to this calibration file |
| `pi5vl53l0x` | `~/.config/pi5vl53l0x/vl53l0x.json` | Detects the file; standalone calibration remains driver-owned |
| `pi5camera` | `~/.config/pi5camera/camera.json` | Copies width, height, warm-up time, and autofocus mode |
| `pi5mic` | `~/.config/pi5mic/mic.json` | Copies input device, sample rate, and channel count |
| NinjaRobotPi5 IDE | `~/.config/ninjarobot_pi5/config.toml` | Owns integrated wiring, safety, behavior, and agent settings |

The V4 distance adapter currently takes the I2C bus and VL53L0X address from
the integrated TOML file. It does not copy the standalone sensor calibration
into the TOML file.

### Synchronize changed module settings with the IDE

Use this procedure after changing buzzer, display, camera, or microphone
settings. It is also safe after servo recalibration, although the servo
calibration contents are read directly from the referenced JSON file when a
new IDE tool process starts.

1. Exit every running `ninjarobot-ide-tool` process.
2. Save the new settings using the standalone tool and its canonical path.
3. Set the integrated path:

```bash
cd "$HOME/NinjaRobotPi5"
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
```

4. Confirm discovery:

```bash
uv run --frozen ninjarobot-ide-tool config discover
```

5. Preview the update, using the current integrated configuration as the base:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" \
  config import \
  --destination "$NINJAROBOT_CONFIG"
```

6. Compare the preview carefully. Confirm that custom safety values, servo
   role mappings, and AI-provider settings remain correct.
7. Apply the update:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" \
  config import \
  --destination "$NINJAROBOT_CONFIG" \
  --apply \
  --overwrite

chmod 600 "$NINJAROBOT_CONFIG"
```

8. Validate and restart:

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$NINJAROBOT_CONFIG"

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status --real
```

`--overwrite` is required because the destination already exists. It does not
overwrite any standalone `pi5*` JSON file.

### Quick links to standalone library guides

- [pi5buzzer README](pi5buzzer/README.md)
- [pi5camera README](pi5camera/README.md)
- [pi5disp README](pi5disp/README.md)
- [pi5mic README](pi5mic/README.md)
- [pi5servo README](pi5servo/README.md)
- [pi5vl53l0x README](pi5vl53l0x/README.md)

### Updating NinjaRobotPi5 later

Stop the robot and exit all tools before updating:

```bash
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

`git pull --ff-only` refuses to combine unexpected local source changes with
the downloaded update. Personal configuration under `~/.config` and retained
media under `~/.local` remain outside the Git checkout.

### Uninstalling the project

First stop the robot and all running tools. To remove only the downloaded
program while keeping personal configuration and media:

```bash
cd "$HOME"
mv "$HOME/NinjaRobotPi5" "$HOME/NinjaRobotPi5-backup"
```

Moving it to a backup is recoverable. After confirming the installation is no
longer needed, you may remove that backup manually.

The following personal folders are not removed automatically:

```text
~/.config/pi5*/
~/.config/ninjarobot_pi5/
~/.local/share/ninjarobot_pi5/
~/.local/state/ninjarobot_pi5/
```

Keep them if you may reinstall. Delete them only after backing up calibration,
configuration, photos, recordings, and user-created behaviors that you want to
preserve.
