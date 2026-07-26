# NinjaRobotPi5V4 Installation Guide

NinjaRobotPi5V4 implements the deterministic IDE core, all six device
adapters, and integrated Phase 4 expressions and wheel movements. Default
commands use simulation. A real device is opened only when its command
includes `--real`.

## Requirements

For development and simulation:

- Python 3.11
- `uv`, the Python environment and dependency tool
- Git
- no Raspberry Pi hardware

For the current real-hardware profile:

- Raspberry Pi 5 with Raspberry Pi OS 64-bit
- DFRobot DFR0566 expansion HAT
- I2C and SPI enabled through `sudo raspi-config`
- GPIO12/GPIO13 hardware PWM overlay for the native servo endpoints
- Raspberry Pi CSI camera supported by Picamera2
- USB audio input plus PortAudio

I2C is the two-wire device bus. SPI is the clocked display connection. PWM
means pulse-width modulation, the timed signal used for servo control. CSI is
the Raspberry Pi flat camera connection.

## Developer installation

Clone and enter the project:

```bash
git clone https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git
cd NinjaRobotPi5
```

Install the locked hardware-free environment:

```bash
uv sync --frozen
```

Run the basic validation:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen ninjarobot_pi5_cli --version
uv run --frozen ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example
uv run --frozen ninjarobot_pi5_cli capabilities
uv run --frozen ninjarobot-ide-tool behavior list
uv run --frozen ninjarobot-ide-tool behavior health
uv run --frozen pytest -q
```

`--frozen` means use the existing `uv.lock` dependency record without changing
it.

## Raspberry Pi interface setup

Enable I2C and SPI:

```bash
sudo raspi-config
```

Choose the interface menu, enable I2C and SPI, finish, and reboot.

For the GPIO12/GPIO13 servo endpoints, add these lines to
`/boot/firmware/config.txt`:

```ini
dtparam=audio=off
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

Reboot after changing the file. This enables two native PWM channels. It does
not enable four independent channels: PWM0 can use GPIO12 or GPIO18, and PWM1
can use GPIO13 or GPIO19.

Install the ordinary managed hardware dependencies:

```bash
uv sync --frozen --extra hardware
```

An extra is an optional dependency group. The `hardware` extra installs the
local managed libraries and their Raspberry Pi dependencies.

## Private integrated configuration

The checked-in example is safe and keeps physical movement disabled. Discover
existing standalone Pi5 settings without changing them:

```bash
uv run --frozen ninjarobot-ide-tool config discover
uv run --frozen ninjarobot-ide-tool config import
```

The second command is preview-only. Carefully check every imported pin and
path. Apply it only after the preview matches the robot:

```bash
uv run --frozen ninjarobot-ide-tool config import --apply
chmod 600 ~/.config/ninjarobot_pi5/config.toml
```

The import reads known `pi5*` JSON files but never runs their CLI tools and
never rewrites their settings. Standalone reset or calibration still belongs
to the relevant `pi5*` CLI.

For physical integrated wheel movement, edit
`~/.config/ninjarobot_pi5/config.toml` and verify these values:

```toml
[hardware.servos]
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

Both exact endpoints must have valid standalone calibration records before
real group movement. For a continuous-rotation servo, calibration center is
the neutral stop value.

## Integrated simulation

Run these checks before any real behavior:

```bash
uv run --frozen ninjarobot-ide-tool behavior list
uv run --frozen ninjarobot-ide-tool behavior show greeting
uv run --frozen ninjarobot-ide-tool behavior health
uv run --frozen ninjarobot-ide-tool behavior simulate greeting
uv run --frozen ninjarobot-ide-tool behavior simulate move_forward \
  --duration 2
```

Run `uv run --frozen ninjarobot-ide-tool` for the interactive menu. Simulation
does not open GPIO, PWM, I2C, SPI, camera, or microphone hardware.

## Camera-capable Raspberry Pi environment

Picamera2 is provided by Raspberry Pi OS and is linked to the matching
libcamera components. A downloaded `uv` Python usually cannot import those
system packages. V4 keeps its ordinary locked environment and sends only
managed real-camera work to Raspberry Pi OS `/usr/bin/python3`. Prepare this
bridge with:

```bash
cd /home/rogerchang/NinjaRobotPi5
./scripts/bootstrap-rpi-camera-workspace.sh
```

The script:

1. installs `python3-picamera2` and `python3-libcamera`
2. leaves the existing `.venv` in place
3. syncs the frozen root hardware dependency set
4. verifies Picamera2 with Raspberry Pi OS `/usr/bin/python3`
5. verifies managed-driver hashes
6. runs real camera health without taking a photograph

If the operating-system packages are already installed:

```bash
./scripts/bootstrap-rpi-camera-workspace.sh --skip-apt
```

Confirm the system camera bindings and camera:

```bash
/usr/bin/python3 -s -c \
  "import libcamera, picamera2; print('Picamera2:', picamera2.__file__)"
rpicam-hello --list-cameras
```

Do not use the project command `python -c "import picamera2"` as this check.
The project can stay on Python 3.11 while Raspberry Pi OS provides its camera
bindings for Python 3.13. The V4 adapter joins those two environments only for
the managed camera operation.

The current hardware should list an OV5647 camera. OV5647 is fixed-focus, so
the V4 example uses `autofocus_mode = "none"`.

## Microphone-capable Raspberry Pi environment

Install PortAudio before the locked hardware environment. PortAudio is the
native audio library used by Python's `sounddevice` package:

```bash
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev
uv sync --frozen --extra hardware
```

Confirm that Linux and V4 can see the USB input without recording:

```bash
arecord -l

uv run --frozen --extra hardware ninjarobot_pi5_cli microphone health \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger /tmp/ninjarobot-phase35-install.sqlite3

uv run --frozen --extra hardware ninjarobot_pi5_cli microphone status \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger /tmp/ninjarobot-phase35-install.sqlite3
```

The current USB microphone accepts 44.1 kHz rather than the requested 16 kHz.
V4 reports that fallback explicitly; it is not an error. Hz means samples or
cycles per second in this context.

These commands do not record. Real recording requires informed consent and
both `--real` and `--confirm-microphone`.

## Safe simulation checks

These commands do not access physical hardware:

```bash
PHASE34_LEDGER="$(mktemp /tmp/ninjarobot-phase34-XXXXXX.sqlite3)"

uv run --frozen ninjarobot_pi5_cli camera health \
  --ledger "$PHASE34_LEDGER"
uv run --frozen ninjarobot_pi5_cli camera status \
  --ledger "$PHASE34_LEDGER"
uv run --frozen ninjarobot_pi5_cli camera capture \
  --ledger "$PHASE34_LEDGER"
```

Expected: health is ready, status and capture say `"simulated": true`, and
capture says `"retained": false` with `"path": null`.

## Real camera safety

A photograph can contain private information. Tell everyone nearby and obtain
their consent before a real capture. Real capture requires both:

```text
--real --confirm-camera
```

Images are deleted after capture unless `--retain` is also supplied. Retained
images are limited to:

```text
~/.local/share/ninjarobot_pi5/camera
```

Follow
[`docs/validation/phase-3-4-camera-validation-2026-07-26.md`](docs/validation/phase-3-4-camera-validation-2026-07-26.md)
one step at a time. Do not connect or disconnect the CSI ribbon while the
Raspberry Pi is powered.

## Other hardware validation

Use the phase-specific reports:

- distance:
  [`docs/validation/phase-2-validation-2026-07-26.md`](docs/validation/phase-2-validation-2026-07-26.md)
- buzzer:
  [`docs/validation/phase-3-1-buzzer-validation-2026-07-26.md`](docs/validation/phase-3-1-buzzer-validation-2026-07-26.md)
- display:
  [`docs/validation/phase-3-2-display-validation-2026-07-26.md`](docs/validation/phase-3-2-display-validation-2026-07-26.md)
- servo:
  [`docs/validation/phase-3-3-servo-validation-2026-07-26.md`](docs/validation/phase-3-3-servo-validation-2026-07-26.md)
- camera:
  [`docs/validation/phase-3-4-camera-validation-2026-07-26.md`](docs/validation/phase-3-4-camera-validation-2026-07-26.md)
- microphone:
  [`docs/validation/phase-3-5-microphone-validation-2026-07-26.md`](docs/validation/phase-3-5-microphone-validation-2026-07-26.md)
- integrated Phase 4 behavior:
  [`docs/validation/phase-4-integrated-behavior-validation-2026-07-26.md`](docs/validation/phase-4-integrated-behavior-validation-2026-07-26.md)

Never change wiring while powered. Keep the servo emergency power disconnect
within reach during any actuator-moving test. The currently reported robot
does not have such a disconnect, so real movement retains additional risk.
Keep the wheels raised for initial tests, keep hands and loose items away, and
use a second terminal with `ninjarobot-ide-tool behavior stop`.
