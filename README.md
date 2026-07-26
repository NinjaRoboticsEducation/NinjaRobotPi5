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

Phase 0, Phase 1, and Phase 2 are complete. Phase 0 established project
governance and preserved the original import hashes for the six existing Pi5
hardware libraries. Phase 1 added strict IDE and agent contracts,
deterministic fakes, V4-owned configuration, and the unified
`ninjarobot_pi5_cli`. Phase 2 adds the IDE capability registry, adapter
lifecycle, bounded scheduler, resource locks, durable SQLite action ledger, and
the first read-only adapter: `distance.read` through `pi5vl53l0x`. SQLite is
Python's built-in local database format.

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
2. **NinjaRobotPi5 IDE** — owns capability registration, hardware
   initialization, resource scheduling, standardized results, action history,
   and the manual CLI.
3. **NinjaRobotPi5 Agent** — will own user interaction, bounded planning, model
   providers, memory, policy, and IDE tool calls. It will never import hardware
   drivers directly.

## Implemented CLI functions

The current CLI provides:

- `config validate` strictly validates V4-owned TOML configuration.
- `contracts schema` prints JSON Schema, a machine-readable description of
  valid contract data.
- `dry-run` executes against a deterministic fake IDE and labels the result
  `"simulated": true`.
- `capabilities` lists the read-only distance capability without opening I2C.
  I2C means the two-wire hardware communication bus used by the sensor.
- `health` checks a simulated sensor unless `--real` is supplied.
- `distance read` returns simulated data unless `--real` is supplied.
- `actions show` reads the durable result for one action from the SQLite
  ledger.
- `--version` reports the installed V4 package version.

The contracts reject unknown fields and unsafe type conversion. They cover
capabilities, actions, results, errors, provider turns, tool calls, sessions,
memory candidates, health, and configuration. Strict mypy checking—the static
analysis of type hints without running the program—is mandatory for new V4
source.

Phase 2 accepts an action ID only once. Repeating the same action ID and request
returns the stored result without reading the sensor again. Timeouts,
cancellation, full queues, expired deadlines, startup interruption, and
unknown outcomes are recorded as structured failures. A reading of `8191 mm`
is explicitly rejected because it is the VL53L0X out-of-range sentinel
(special invalid value), not a real distance.

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

Python 3.11 is the project baseline. Install the locked, hardware-free root
development environment:

```bash
uv sync --frozen
```

Validate Phase 2 manually without hardware:

```bash
uv run --frozen ninjarobot_pi5_cli --version
uv run --frozen ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example
uv run --frozen ninjarobot_pi5_cli dry-run \
  --capability system.echo \
  --json '{"message":"hello"}'
uv run --frozen ninjarobot_pi5_cli capabilities
uv run --frozen ninjarobot_pi5_cli health \
  --ledger /tmp/ninjarobot-phase2-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli distance read \
  --ledger /tmp/ninjarobot-phase2-smoke.sqlite3 \
  --action-id phase2-smoke-1 \
  --idempotency-key phase2-smoke-key-1
```

On the Raspberry Pi, install the optional managed sensor package without
changing its source:

```bash
uv sync --frozen --extra hardware
```

Then follow
[`docs/validation/phase-2-validation-2026-07-26.md`](docs/validation/phase-2-validation-2026-07-26.md).
Real sensor access occurs only when the command includes `--real`.

Run the complete root gate:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen ruff format --check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen mypy \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
git diff --check
```

Each copied driver retains its own package-local commands. See
[`DevelopmentGuide.md`](DevelopmentGuide.md) for the exact baseline procedure.

## Safety

Default tests and commands without `--real` never access physical hardware.
The Phase 2 real path reads only the VL53L0X on I2C bus 1 at address `0x29`; it
does not move a servo, sound the buzzer, change the display, use the camera, or
record audio. Later actuator commands will require a separate Raspberry Pi
checklist and operator approval. Model output will be treated as an untrusted
proposal; the deterministic IDE control plane retains final authority over
robot actions.
