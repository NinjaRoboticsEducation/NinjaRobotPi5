# NinjaRobotPi5V4

NinjaRobotPi5V4 is a clean, modular robot-control platform for Raspberry Pi 5.
It replaces the historical OpenClaw-based orchestration with two project-owned
layers:

- `ninjarobot_pi5_ide`: deterministic middleware that exposes safe, standardized
  robot capabilities.
- `ninjarobot_pi5_agent`: a bounded AI agent that supports interchangeable local
  and cloud model providers, tool calling, and persistent personalization.

The implementation follows
[`NinjaRobotPi5V4_ImplementationPlan.md`](NinjaRobotPi5V4_ImplementationPlan.md),
which is the single source of truth.

## Current status

Phase 0 is complete. It established project governance and preserved the
original import hashes for the six existing Pi5 hardware libraries. The project
owner has authorized focused repairs to those standalone libraries; every
repaired hash is tracked separately from the import baseline. Phase 1 is
approved and will add the first V4 IDE and agent contracts.

The `pi5buzzer` development environment is locked and its 65 tests pass. The
earlier GPIO17 health and sound checks remain historical evidence; the current
V4 wiring uses GPIO27 and will be validated when the buzzer adapter is added.
Non-moving servo backends execute successfully. Display configuration now lives
under the user's config directory rather than inside the package; all display
command paths execute, but visual confirmation with the current DC4/RST5/BL6
wiring is pending. See the
[2026-07-25 hardware report](docs/validation/raspberry-pi-hardware-validation-2026-07-25.md).

`pi5camera` now uses the Raspberry Pi OS Picamera2/libcamera packages through a
system-site-enabled Python 3.13 environment. Doctor, status, and a verified
1280×720 JPEG capture pass.

`pi5mic` now has PortAudio and a local whisper.cpp base model. USB-device
discovery, a five-second library recording, doctor, and offline transcription
all pass without OpenClaw.

`pi5vl53l0x` now uses vendor-correct timing-budget calculations, bounded
reference-calibration recovery, and strict invalid-reading checks. Its 71 tests
pass and the live device initializes with a valid `0xEE/0xAA/0x10` identity.
The connected sensor still returns the `8191 mm` out-of-range sentinel at the
reported 100 mm target, so optical alignment/window, wiring, and cold-power
validation remain open; calibration is intentionally blocked until readings
are valid.

## Three-layer architecture

1. **Managed Pi5 libraries** — `pi5buzzer`, `pi5servo`, `pi5disp`,
   `pi5camera`, `pi5mic`, and `pi5vl53l0x` retain independent hardware-driver
   responsibilities, standalone APIs, and package-level validation.
2. **NinjaRobotPi5 IDE** — will own capability registration, hardware
   initialization, resource scheduling, standardized results, and a manual CLI.
3. **NinjaRobotPi5 Agent** — will own user interaction, bounded planning, model
   providers, memory, policy, and IDE tool calls. It will never import hardware
   drivers directly.

The nested `NinjaClawBot/` checkout is an excluded, read-only historical
reference. It is not part of the V4 product or Git history.

## Hardware foundation

The confirmed target is a Raspberry Pi 5 with 8 GB RAM and a 256 GB NVMe SSD.
The robot uses the DFRobot DFR0566 expansion HAT, six planned servo endpoints,
a passive buzzer, VL53L0X sensor, ST7789V display, USB microphone, and Raspberry
Pi camera. The temporary servos are connected to the DFR0566 digital
GPIO12/GPIO13 breakouts. Those connectors use the Raspberry Pi's native
hardware PWM and require the `pwm-2chan` boot overlay; they are not the HAT's
dedicated I2C-controlled PWM0/PWM1 sockets. Powered servo tests remain blocked
until an accessible emergency disconnect is installed.

The current V4-owned wiring record uses the passive buzzer on GPIO27 and the
ST7789V display on SPI0 with DC GPIO4, reset GPIO5, and backlight GPIO6. The
display is 240×320, rotated 90°, at 75% brightness.

## Developer setup

Python 3.11 is the project baseline. Install the locked root development
environment:

```bash
uv sync --dev
```

Run the Phase 0 root gate:

```bash
uv run python scripts/verify_immutable_drivers.py
uv run python -m compileall -q scripts
uv run ruff check scripts tests
uv run ruff format --check scripts tests
uv run pytest -q
git diff --check
```

Each copied driver retains its own package-local commands. See
[`DevelopmentGuide.md`](DevelopmentGuide.md) for the exact baseline procedure.

## Safety

Default tests never access physical hardware. Commands marked `hardware` require
an explicit Raspberry Pi checklist and operator approval. Model output will be
treated as an untrusted proposal; the deterministic IDE control plane will
retain final authority over robot actions.
