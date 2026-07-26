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

Phase 0, Phase 1, Phase 2, and Phase 3.1 through Phase 3.4 are implemented.
Phase 0 established project governance and preserved the
original import hashes for the six existing Pi5 hardware libraries. Phase 1
added strict IDE and agent contracts, deterministic fakes, V4-owned
configuration, and the unified `ninjarobot_pi5_cli`. Phase 2 added the IDE
capability registry, adapter lifecycle, bounded scheduler, resource locks,
durable SQLite action ledger, and the first read-only adapter:
`distance.read` through `pi5vl53l0x`. SQLite is Python's built-in local
database format.

Phase 3.1 adds bounded passive-buzzer control on GPIO27. `buzzer.play_tone`
accepts only a frequency from 20 through 20,000 hertz, a duration from 0.05
through 2 seconds, and volume from 1 through 128. `buzzer.stop` is an
idempotent emergency capability, meaning it is safe to request repeatedly.
Both commands simulate unless `--real` is present.

Phase 3.2 adds `display.show_text`, `display.clear`, and
`display.set_brightness`. They share one serialized ST7789V service, which
means only one display operation can use SPI at a time. SPI (Serial Peripheral
Interface) is the display's clocked data connection. Commands simulate unless
`--real` is present. The real path uses SPI0 device 0, DC GPIO4, reset GPIO5,
backlight GPIO6, rotation 90°, and initial brightness 75%. The operator reports
that the complete Phase 3.2 physical checklist passes.

Phase 3.3 adds the fixed six-servo mixed backend and three capabilities:
`servo.status`, single-endpoint `servo.move`, and emergency `servo.stop`.
GPIO12/GPIO13 use Raspberry Pi hardware PWM, while `hat_pwm1` through
`hat_pwm4` use DFR0566 PWM0 through PWM3 over I2C. Real movement is disabled in
the checked-in configuration and additionally requires `--real`,
`--confirm-motion`, and a valid endpoint calibration. Group motion is not
available. The Phase 3.3 software gate passes. The operator reports that all
Phase 3.3 manual tests pass; detailed command output and electrical values were
not attached to that report, so the validation record preserves that
distinction.

Phase 3.4 adds `camera.status` and `camera.capture` through one serialized
camera service. Status checks configuration and dependency readiness without
taking a photograph. Capture is classified as privacy-sensitive and is
non-idempotent, meaning repeating it would take another photograph. Real
capture requires `--real` and `--confirm-camera`. Images are deleted by
default; `--retain` explicitly saves an owner-only JPEG inside the configured
private media directory. JPEG is the compressed image-file format used here.

The `pi5buzzer` development environment is locked and its 65 tests pass. The
earlier GPIO17 health and sound checks remain historical evidence; the current
V4 GPIO27 validation has now passed every operator checklist item.
Non-moving servo backends execute successfully. Display configuration now lives
under the user's config directory rather than inside the package; all display
command paths and the current DC4/RST5/BL6 visual checklist pass. See the
[2026-07-25 hardware report](docs/validation/raspberry-pi-hardware-validation-2026-07-25.md).

`pi5camera` now uses the Raspberry Pi OS Picamera2/libcamera packages through a
small V4 interpreter bridge. The ordinary project environment remains on its
locked Python version; only real managed-camera checks and capture run through
Raspberry Pi OS `/usr/bin/python3`. Doctor, status, and a verified 1280×720
JPEG capture pass.

`pi5mic` now has PortAudio and a local whisper.cpp base model. USB-device
discovery, a five-second library recording, doctor, and offline transcription
all pass without OpenClaw.

`pi5vl53l0x` now uses vendor-correct timing-budget calculations, bounded
reference-calibration recovery, and strict invalid-reading checks. Its 71 tests
pass and the live device initializes with a valid `0xEE/0xAA/0x10` identity.
Phase 2 Raspberry Pi validation produced 10 valid consecutive readings from
48 mm through 149 mm, with no `8191 mm` sentinel. The IDE adapter therefore
passes initialization, repeated reading, normalization, ledger recording,
close, and restart validation. The earlier physical failure is cleared, though
its hardware root cause was not established.

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
- `capabilities` lists all implemented distance, buzzer, display, servo, and
  camera capabilities without opening hardware.
- `health` checks a simulated sensor unless `--real` is supplied.
- `distance read` returns simulated data unless `--real` is supplied.
- `actions show` reads the durable result for one action from the SQLite
  ledger.
- `buzzer health` checks simulated or real GPIO27 readiness without sounding
  the buzzer.
- `buzzer play` runs one short bounded tone; it is simulated unless `--real`
  is explicitly supplied.
- `buzzer stop` requests immediate silence and releases GPIO27.
- `display health` checks simulated or real ST7789V SPI readiness. Real
  initialization may briefly light the backlight.
- `display text` renders centered text; it is simulated unless `--real` is
  explicitly supplied.
- `display clear` fills the screen with one `#RRGGBB` color. `RRGGBB` is a
  six-digit red/green/blue hexadecimal color value.
- `display brightness` sets the backlight from 0% through 100% for the current
  CLI session.
- `servo health` claims the two native PWM interfaces and verifies the DFR0566
  at zero output. It does not send a servo pulse.
- `servo status` reports the six endpoints, calibration readiness, and motion
  gates without centering a servo.
- `servo move` moves exactly one calibrated endpoint. It is simulated unless
  `--real` is supplied, and real movement requires additional safety gates.
- `servo stop` aborts movement and requests zero pulse for all six endpoints.
- `camera health` checks Picamera2 and private-directory readiness without
  taking a photograph.
- `camera status` reports resolution, focus mode, and the default-off retention
  policy without taking a photograph.
- `camera capture` takes one simulated image unless `--real` and
  `--confirm-camera` are supplied. It retains no image unless `--retain` is
  also supplied.
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
The observed CSI camera is an OV5647 used at 1280×720. CSI is the Raspberry
Pi's flat camera connection. OV5647 is fixed-focus, so V4 uses autofocus mode
`none`.

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
uv run --frozen ninjarobot_pi5_cli buzzer health \
  --ledger /tmp/ninjarobot-phase31-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli buzzer play \
  --ledger /tmp/ninjarobot-phase31-smoke.sqlite3 \
  --frequency 440 \
  --duration 0.05 \
  --volume 16
uv run --frozen ninjarobot_pi5_cli display health \
  --ledger /tmp/ninjarobot-phase32-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli display text \
  --ledger /tmp/ninjarobot-phase32-smoke.sqlite3 \
  --text "NinjaRobot Phase 3.2" \
  --font-size 24
uv run --frozen ninjarobot_pi5_cli display brightness \
  --ledger /tmp/ninjarobot-phase32-smoke.sqlite3 \
  --percent 25
uv run --frozen ninjarobot_pi5_cli display clear \
  --ledger /tmp/ninjarobot-phase32-smoke.sqlite3 \
  --color "#000000"
uv run --frozen ninjarobot_pi5_cli servo health \
  --ledger /tmp/ninjarobot-phase33-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli servo status \
  --ledger /tmp/ninjarobot-phase33-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli servo move \
  --ledger /tmp/ninjarobot-phase33-smoke.sqlite3 \
  --endpoint gpio12 \
  --angle 10 \
  --speed S
uv run --frozen ninjarobot_pi5_cli servo stop \
  --ledger /tmp/ninjarobot-phase33-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli camera health \
  --ledger /tmp/ninjarobot-phase34-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli camera status \
  --ledger /tmp/ninjarobot-phase34-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli camera capture \
  --ledger /tmp/ninjarobot-phase34-smoke.sqlite3
```

On the Raspberry Pi, install the optional managed hardware packages without
changing their source:

```bash
uv sync --frozen --extra hardware
```

Real Picamera2 access additionally requires the Raspberry Pi OS camera
packages. The safe bootstrap installs or checks those packages, keeps the
ordinary project `.venv`, and verifies the interpreter bridge without taking
a photograph:

```bash
./scripts/bootstrap-rpi-camera-workspace.sh
```

It is normal for `python -c "import picamera2"` inside the project `.venv` to
fail. The required check is
`/usr/bin/python3 -s -c "import libcamera, picamera2"`.

Then follow
[`docs/validation/phase-2-validation-2026-07-26.md`](docs/validation/phase-2-validation-2026-07-26.md).
Real sensor access occurs only when the command includes `--real`.
For the buzzer, follow
[`docs/validation/phase-3-1-buzzer-validation-2026-07-26.md`](docs/validation/phase-3-1-buzzer-validation-2026-07-26.md).
The operator reports that checklist as passed. For the display, follow
[`docs/validation/phase-3-2-display-validation-2026-07-26.md`](docs/validation/phase-3-2-display-validation-2026-07-26.md).
The operator reports that checklist as passed. For the servo integration,
follow
[`docs/validation/phase-3-3-servo-validation-2026-07-26.md`](docs/validation/phase-3-3-servo-validation-2026-07-26.md).
The operator reports that checklist as passed, without an attached transcript.
For camera integration, follow
[`docs/validation/phase-3-4-camera-validation-2026-07-26.md`](docs/validation/phase-3-4-camera-validation-2026-07-26.md).
Real capture requires consent from everyone nearby.

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
The Phase 2 real path reads only the VL53L0X on I2C bus 1 at address `0x29`.
The Phase 3.1 real path can sound the GPIO27 buzzer, but only through bounded
arguments and an explicit `--real` flag. The Phase 3.2 real path resets and
writes the ST7789V and can energize its backlight at the configured 75%
brightness.
The Phase 3.3 real health/status path keeps all servo duties at zero. Its
movement path is classified as `motion`, disabled by default, restricted to
one calibrated endpoint, and guarded by explicit confirmation. The Phase 3.4
camera path is classified as `privacy`, requires explicit real-capture
confirmation, and deletes media unless retention is requested. Phase 3.4 does
not perform face recognition, video, streaming, or agent-controlled capture.
Model output is treated as an untrusted proposal; the
deterministic IDE control plane retains final authority over robot actions.
