# NinjaRobotPi5V4 Development Guide

This guide describes the developer workflow for the clean V4 repository.
`NinjaRobotPi5V4_ImplementationPlan.md` remains authoritative when this guide is
incomplete or conflicts with it.

## Repository layout

- `ninjarobot_pi5_ide/`: deterministic robot contracts, scheduler, action
  ledger, and managed-driver adapters.
- `ninjarobot_pi5_agent/`: provider-neutral agent contracts and unified CLI.
- `config/`: V4-owned configuration examples; never driver-local runtime state.
- `pi5*/`: independently testable hardware libraries copied from the historical
  project and maintained under the managed-driver policy.
- `tests/`: root integration and governance tests.
- `docs/architecture/`: architecture and driver-containment records.
- `docs/adr/`: architecture decision records.
- `docs/hardware/`: hardware mapping and electrical records.
- `docs/validation/`: phase reports, original driver baseline, and authorized
  repair hashes.
- `scripts/`: root-owned validation utilities.
- `NinjaClawBot/`: ignored historical reference; never imported by V4.

## Managed driver boundary

The following packages may receive focused hardware-library repairs:

- `pi5buzzer/`
- `pi5servo/`
- `pi5disp/`
- `pi5camera/`
- `pi5mic/`
- `pi5vl53l0x/`

Before changing one, read its complete README, audit the relevant symbols with
Serena, reproduce the failure, and document the root cause. Keep each driver
independent from the IDE and agent. After the repair, pass that package's lint,
format, unit, and Raspberry Pi validation gates and record each changed file:

```bash
uv run python scripts/verify_immutable_drivers.py \
  --record-authorized pi5example/path/to/file.py \
  --reason "Concise root cause and validated repair"
uv run python scripts/verify_immutable_drivers.py
```

The original hashes in `immutable_driver_baseline.json` are permanent and must
never be regenerated after repairs. `authorized_driver_changes.json` records
the approved repaired state. The historical `NinjaClawBot/` tree remains
strictly read-only.

## Development workflow

1. Read the implementation-plan phase and relevant ADRs.
2. Review the affected code through Serena.
3. Present the phase plan and obtain approval.
4. Implement V4-owned files or the explicitly approved driver repair.
5. Run focused tests, then the complete phase quality gate.
6. Verify driver provenance and authorized repair hashes.
7. Update `README.md`, this guide, and `DevelopmentLog.md`.
8. Prepare a Raspberry Pi checklist for hardware-facing changes.
9. Stop for review before starting the next phase.

## Root quality gate

Phase 0's historical root gate was:

```bash
uv run python scripts/verify_immutable_drivers.py
uv run python -m compileall -q scripts
uv run ruff check scripts tests
uv run ruff format --check scripts tests
uv run pytest -q
git diff --check
```

Beginning in Phase 1, use this complete gate:

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

Strict mypy typing is mandatory for the two new V4 source packages. It does not
change the independently maintained `pi5*` libraries.

## Phase 1 configuration and CLI

Validate the checked-in example:

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example
```

The example is authoritative V4 configuration, not a driver configuration. It
records GPIO12/GPIO13 servos, GPIO27 buzzer, and the ST7789V display on
DC4/RST5/BL6 with rotation 90° and brightness 75%. It also records the
fixed-focus OV5647 camera at 1280×720 with media retention disabled.

Inspect schemas or exercise the fake IDE:

```bash
uv run --frozen ninjarobot_pi5_cli contracts schema
uv run --frozen ninjarobot_pi5_cli dry-run \
  --capability system.echo \
  --json '{"message":"hello"}'
```

`dry-run` never opens GPIO, I2C, SPI, camera, or audio. Its result must include
`"simulated": true`.

## Phase 2 IDE and distance adapter

Phase 2 keeps every driver import inside the IDE. The agent and its CLI import
only `ninjarobot_pi5_ide`; they never import a `pi5*` package directly.

The main components are:

- `CapabilityRegistry`: registers one unique adapter per capability and owns
  startup, health, and close ordering.
- `ResourceScheduler`: bounds concurrent and waiting work, then locks shared
  resources in sorted order to prevent deadlock. Deadlock means two operations
  wait forever for each other's lock.
- `ActionLedger`: stores accepted, running, and completed actions in SQLite.
  SQLite is the small local database included with Python.
- `ExecutionEngine`: enforces action IDs, idempotency keys, deadlines,
  timeouts, cancellation, restart recovery, and normalized errors. An
  idempotency key is a caller-supplied identifier that prevents an accidental
  duplicate operation.
- `VL53L0XDistanceAdapter`: lazily loads `pi5vl53l0x` only for explicit real
  use and exposes the read-only `distance.read` capability.

Install the ordinary development environment for simulation:

```bash
uv sync --frozen
```

Install the optional local VL53L0X package on the Raspberry Pi:

```bash
uv sync --frozen --extra hardware
```

Run safe simulation and ledger checks:

```bash
uv run --frozen ninjarobot_pi5_cli capabilities
uv run --frozen ninjarobot_pi5_cli health \
  --ledger /tmp/ninjarobot-phase2.sqlite3
uv run --frozen ninjarobot_pi5_cli distance read \
  --ledger /tmp/ninjarobot-phase2.sqlite3 \
  --action-id phase2-test-1 \
  --idempotency-key phase2-test-key-1
uv run --frozen ninjarobot_pi5_cli actions show \
  --ledger /tmp/ninjarobot-phase2.sqlite3 \
  --action-id phase2-test-1
```

These commands are simulated unless `health` or `distance read` includes
`--real`. The real path uses the configured I2C bus 1 and address `0x29`. It
returns exit code 1 for a structured device failure, including the known
`8191 mm` invalid sentinel.

Do not use the same idempotency key for different arguments or capabilities.
That is rejected as a conflicting request. On restart, an action that was only
queued is marked safe to retry. An action that was already running is recorded
with an unknown outcome, so software cannot silently repeat it.

## Phase 3.1 GPIO27 buzzer adapter

`ninjarobot_pi5_ide.buzzer` owns the lazy `pi5buzzer` import and shares one
device service between:

- `buzzer.play_tone`, a low-risk bounded tone
- `buzzer.stop`, an emergency silence action that does not wait for the
  playback resource lock

The play capability is intentionally non-idempotent: repeating a successful
tone would produce sound twice. The action ledger therefore reports
`retry_safety: unsafe` after success and returns the stored result if the same
action ID is repeated. Cancellation and engine shutdown call the driver's
`off()` method, which silences and releases GPIO27.

Simulation is the default:

```bash
uv run --frozen ninjarobot_pi5_cli buzzer health \
  --ledger /tmp/ninjarobot-phase31.sqlite3
uv run --frozen ninjarobot_pi5_cli buzzer play \
  --ledger /tmp/ninjarobot-phase31.sqlite3 \
  --frequency 440 \
  --duration 0.05 \
  --volume 16
uv run --frozen ninjarobot_pi5_cli buzzer stop \
  --ledger /tmp/ninjarobot-phase31.sqlite3
```

Each result must contain `"simulated": true`. Real GPIO is opened only when the
command includes `--real`; install the aggregate hardware extra first:

```bash
uv sync --frozen --extra hardware
```

Do not run a real tone until the buzzer voltage, current, and transistor-driver
arrangement are recorded. Follow the Phase 3.1 validation report.

## Phase 3.2 ST7789V display adapter

`ninjarobot_pi5_ide.display` owns the lazy `pi5disp` import. One
`DisplayDevice` is shared by three low-risk, idempotent capabilities:

- `display.show_text` renders centered, multiline text
- `display.clear` fills the display with one solid color
- `display.set_brightness` controls the backlight from 0% through 100%

Idempotent means that repeating the same completed request produces the same
final display state. All three descriptors claim the same `display`, `spi0`,
and GPIO4/GPIO5/GPIO6 resources. The scheduler and the device's own lock
therefore prevent two SPI writes or a write/backlight change from overlapping.

The device constructor passes the V4 configuration directly to the managed
driver: SPI device 0, DC GPIO4, reset GPIO5, backlight GPIO6, 32 MHz, native
240×320 dimensions, and rotation 90°. After rotation, the drawable frame is
320×240. MHz means megahertz, or one million clock cycles per second.
Initialization sets 75% brightness. Closing the service turns off the
backlight and releases SPI.

Pillow is the Python image-drawing library used to create the same RGB frame
in simulation and real execution. RGB means red, green, and blue. Text length,
font size, color notation, and brightness are checked before a hardware write.
Text that would not fit is rejected instead of silently clipping.

Simulation is the default:

```bash
uv run --frozen ninjarobot_pi5_cli display health \
  --ledger /tmp/ninjarobot-phase32.sqlite3
uv run --frozen ninjarobot_pi5_cli display text \
  --ledger /tmp/ninjarobot-phase32.sqlite3 \
  --text "NinjaRobot Phase 3.2" \
  --font-size 24
uv run --frozen ninjarobot_pi5_cli display brightness \
  --ledger /tmp/ninjarobot-phase32.sqlite3 \
  --percent 25
uv run --frozen ninjarobot_pi5_cli display clear \
  --ledger /tmp/ninjarobot-phase32.sqlite3 \
  --color "#000000"
```

Each result must say `"simulated": true`. Install the aggregate hardware extra
before real Raspberry Pi use:

```bash
uv sync --frozen --extra hardware
```

Real access requires `--real`. The optional `--hold` value keeps the CLI
session open for up to 30 seconds so a person can inspect the screen. The
driver turns the backlight off when that session closes, so a dark screen after
the command exits is expected. A real health command initializes the panel and
may briefly light the backlight at 75%, even though it does not send a test
frame. Follow the Phase 3.2 validation report before using the real commands.

## Phase 3.3 six-servo mixed-backend adapter

`ninjarobot_pi5_ide.servo` owns the lazy `pi5servo` import and creates the
managed library's existing `auto` mixed backend for this fixed topology:

- `gpio12` and `gpio13` use RP1 hardware PWM
- `hat_pwm1` through `hat_pwm4` use DFR0566 physical PWM0 through PWM3
- DFR0566 uses I2C bus 1 at address `0x10`

The V4 configuration must list those six names in that exact order. It also
points to `~/.config/pi5servo/servo.json`, where the standalone calibration
tool stores endpoint calibration. V4 reads that file but never rewrites it.

Three capabilities share one `ServoDevice`:

- `servo.status` is read-only and reports topology, calibration readiness, and
  safety gates without sending a center pulse
- `servo.move` is a non-idempotent motion action for one endpoint
- `servo.stop` is an idempotent emergency action that aborts movement and sets
  all six outputs to zero without waiting for the normal servo resource lock

Non-idempotent means repeating the physical action may repeat motion, so
successful moves report `retry_safety: unsafe`. Reusing the same action ID
returns the stored result instead of moving twice.

The checked-in example has:

```toml
motion_enabled = false
group_motion_enabled = false
```

Group motion has no capability in Phase 3.3 and the configuration schema
rejects enabling it. Real single-servo motion requires:

- `motion_enabled = true` in a private configuration
- an explicit valid calibration for the selected endpoint
- `--real`
- `--confirm-motion`

Before moving, the service sends the selected endpoint's calibrated center.
It then uses the managed driver's cancellable slow/medium/fast movement path.
For a continuous-rotation servo, center means neutral/stop and other values
usually mean direction and speed rather than a physical angle.

Simulation is the default:

```bash
uv run --frozen ninjarobot_pi5_cli servo health \
  --ledger /tmp/ninjarobot-phase33.sqlite3
uv run --frozen ninjarobot_pi5_cli servo status \
  --ledger /tmp/ninjarobot-phase33.sqlite3
uv run --frozen ninjarobot_pi5_cli servo move \
  --ledger /tmp/ninjarobot-phase33.sqlite3 \
  --endpoint gpio12 \
  --angle 10 \
  --speed S
uv run --frozen ninjarobot_pi5_cli servo stop \
  --ledger /tmp/ninjarobot-phase33.sqlite3
```

Every result must say `"simulated": true`. The simulated status intentionally
reports all endpoints calibrated and motion enabled so the motion contract can
be tested without hardware.

Install the aggregate hardware extra before non-moving Raspberry Pi interface
checks:

```bash
uv sync --frozen --extra hardware
```

A real health/status session claims GPIO12/GPIO13 at zero pulse, verifies the
DFR0566 identity, disables its PWM, sets all four HAT duties to zero, and
releases both backends during cleanup. It must not move a servo. Powered
calibration and motion remain blocked until the complete electrical record and
emergency disconnect are approved. Follow the Phase 3.3 validation report.

## Phase 3.4 privacy-bounded camera adapter

`ninjarobot_pi5_ide.camera` is the only V4 module that imports the managed
`pi5camera` capture path. The agent package imports only the IDE classes.
Phase 3.4 intentionally exposes still capture, not face recognition,
enrollment, video, streaming, or autonomous camera use.

Two capabilities share one `CameraDevice` and the `camera` resource:

- `camera.status` is read-only and reports dependency readiness, resolution,
  focus mode, and retention policy without taking a photograph
- `camera.capture` is privacy-classified, confirmation-required,
  non-idempotent, and cancellable

Non-idempotent means that repeating the operation would take a second
photograph. A successful capture therefore reports `retry_safety: unsafe`.
Repeating the same action ID returns the durable first result without opening
the camera again.

The checked-in configuration uses:

```toml
[hardware.camera]
enabled = true
width = 1280
height = 720
warmup_seconds = 1.0
autofocus_mode = "none"
media_directory = "~/.local/share/ninjarobot_pi5/camera"
retain_media_by_default = false
```

The `Literal[False]` configuration type prevents enabling implicit retention.
The CLI can retain one image only through an explicit `--retain`. Retained
names accept letters, numbers, underscores, and hyphens followed by `.jpg`.
They cannot contain a directory path, cannot leave the configured media
directory, and cannot replace an existing file.

Every capture first uses a private `.capture-*` staging directory. The service
hashes the JPEG, moves it into retained storage only when requested, and
removes staging data in a `finally` cleanup. `finally` means cleanup runs
whether the operation succeeds or raises an error. Cancellation and timeout
wait for the worker thread to finish Picamera2 cleanup, then report the
cancelled or unknown outcome without leaving a retained file.

Simulation is the default and does not import Picamera2:

```bash
uv run --frozen ninjarobot_pi5_cli camera health \
  --ledger /tmp/ninjarobot-phase34.sqlite3
uv run --frozen ninjarobot_pi5_cli camera status \
  --ledger /tmp/ninjarobot-phase34.sqlite3
uv run --frozen ninjarobot_pi5_cli camera capture \
  --ledger /tmp/ninjarobot-phase34.sqlite3
```

The Raspberry Pi OS Picamera2 package is tied to its system libcamera ABI. ABI
means the low-level binary interface between compiled components. A downloaded
Python environment normally cannot import it. V4 therefore keeps its normal
locked Python environment and runs only the managed real-camera operation
through Raspberry Pi OS `/usr/bin/python3`. Prepare both sides with:

```bash
./scripts/bootstrap-rpi-camera-workspace.sh
```

The script never moves, deletes, or recreates `.venv`. It installs the
operating-system camera packages, syncs the normal frozen hardware dependency
set, checks Picamera2 with `/usr/bin/python3`, and runs real camera health
without taking a photograph. Use `--skip-apt` only when the Raspberry Pi OS
camera packages are already installed.

The bridge uses a fixed subprocess argument list and the exact managed
`pi5camera/src` directory recorded by the local package installation.
`subprocess` means a separate program launched by V4. It does not expose the
Python 3.11 `.venv` packages to Python 3.13, so compiled packages such as NumPy
cannot cross the incompatible interpreter boundary.

Real status does not take a photograph. Real capture requires informed consent
from everyone nearby plus both `--real` and `--confirm-camera`. Images are
deleted by default. Follow the Phase 3.4 validation report before retaining
one physical test image.

## Phase 3.5 microphone adapter

Phase 3.5 exposes only the approved device-facing portions of `pi5mic`:
input-device discovery, supported-rate resolution, and bounded WAV recording.
It deliberately excludes transcription, Gemini, wake-word detection,
always-on listening, transport, presence, and every OpenClaw module.

The managed package root historically re-exports some excluded components.
The V4 loader therefore locates the managed source and loads only these exact
modules under contained namespace packages:

```text
pi5mic.errors
pi5mic.models
pi5mic.core.audio_backend
pi5mic.core.devices
pi5mic.core.recorder
```

A namespace package here means a package boundary created without executing
the managed package's top-level `__init__.py`. Tests inspect `sys.modules`,
Python's table of loaded modules, and fail if any other `pi5mic` module enters
the V4 process.

Two capabilities share the exclusive `microphone` resource:

- `microphone.status` discovers inputs and validates the selected device and
  rate without recording
- `microphone.capture` records one bounded WAV, requires privacy confirmation
  on real hardware, and is non-idempotent

The checked-in profile is:

```toml
[hardware.microphone]
enabled = true
device_selector = "USB PnP Sound Device"
sample_rate_hz = 16000
channels = 1
max_capture_seconds = 10.0
media_directory = "~/.local/share/ninjarobot_pi5/microphone"
retain_audio_by_default = false
```

The current USB device rejects 16 kHz and accepts 44.1 kHz. The managed driver
selects the supported rate and V4 returns both requested and actual values.
This preserves the intended profile while keeping the physical result honest.

Every recording uses a private `.capture-*` staging directory. Successful
audio is hashed, retained only after an explicit request, and removed in a
`finally` cleanup after success, failure, timeout, or cancellation. Retained
files use permission `600` and cannot escape the configured directory or
replace an existing file.

Simulation never imports `pi5mic` or opens PortAudio:

```bash
uv run --frozen ninjarobot_pi5_cli microphone health \
  --ledger /tmp/ninjarobot-phase35.sqlite3
uv run --frozen ninjarobot_pi5_cli microphone status \
  --ledger /tmp/ninjarobot-phase35.sqlite3
uv run --frozen ninjarobot_pi5_cli microphone capture \
  --ledger /tmp/ninjarobot-phase35.sqlite3 \
  --duration 0.25
```

Real health and status query the USB interface but do not record. Follow the
Phase 3.5 report before adding `--real --confirm-microphone`.

## Phase 4 integrated behavior system

Phase 4 lives entirely inside `ninjarobot_pi5_ide`. Managed hardware libraries
remain device drivers; they do not own behavior schemas, cross-device timing,
safety latches, or action storage.

The main modules are:

- `behavior_models.py`: strict immutable definitions for stages and operations
- `behavior_assets.py`: read-only bundled assets and confined private assets
- `behavior_runtime.py`: ordered stages and concurrent operations
- `face_renderer.py`: procedural Pillow faces; Pillow is the Python image
  library used to draw each frame
- `robot.py`: one shared assembly for display, buzzer, servos, distance,
  camera, and microphone
- `safety.py`: logical motor mapping, distance guard, watchdog, undervoltage,
  two stop levels, and persistent restart gates
- `config_import.py`: preview-first read-only import of standalone Pi5 JSON
  settings
- `runtime_control.py`: owner-private active-process registration so a second
  CLI can request stop
- `cli.py`: the interactive and scriptable `ninjarobot-ide-tool`

### Behavior format

A behavior contains one or more stages. Stages execute in order. Operations
inside a stage begin concurrently. A stage may contain one display operation,
one existing buzzer melody, one drive operation, and one wait. This structure
makes greeting text and sound start together without forcing every robot
behavior into one long serial sequence.

Bundled assets are package data and read-only. Private assets live in
`~/.config/ninjarobot_pi5/behaviors`. Names cannot contain paths, symbolic
links are rejected, files use mode `0600`, writes are atomic, and existing
assets are not overwritten unless the user explicitly requests it.

The bundled catalog is:

- expressions: `idle`, `greeting`, `happy`, `thinking`, `success`, `warning`,
  and `error`
- movements: `move_forward`, `move_backward`, `turn_left`, and `turn_right`

`stop` is not an asset. It is a safety command that cannot be embedded or
redefined by a private action.

### Default motor and obstacle policy

Behavior assets use logical roles, not pins. The example configuration maps:

```toml
[behaviors.servo_roles]
left_motor = "gpio12"
right_motor = "gpio13"
```

The approved continuous-rotation targets are:

| Behavior | Left motor | Right motor |
| --- | ---: | ---: |
| `move_forward` | +45 | -45 |
| `move_backward` | -30 | +30 |
| `turn_right` | +45 | +45 |
| `turn_left` | -45 | -45 |

Zero or the calibrated center represents neutral for these MG90D
continuous-rotation motors. An emergency stop uses zero PWM pulse through the
driver's `off` path rather than leaving a motion target active.

Front-guarded motion requires three valid clear readings above 100 mm before
the motors start. Three consecutive readings at or below 100 mm cause a Level
1 stop. The threshold is configurable but the schema refuses values below
50 mm. Backward movement uses warning-only monitoring because the sensor faces
forward. Turns report that side and rear space is not protected.

The owner explicitly selected warning-only behavior for missing, invalid, and
stale readings during an already-running movement. Those samples break the
three-reading sequence but do not stop the motors. A front-guarded action still
cannot start until it receives the configured number of valid clear readings.

### Stop levels

Level 1 stops only servo movement and blocks another movement:

- three consecutive front-obstacle readings
- current Raspberry Pi undervoltage
- software-watchdog timeout

Resume with:

```bash
uv run --frozen ninjarobot-ide-tool motion resume --confirm
```

Level 2 stops servo movement and ranging, closes camera and microphone devices,
silences the buzzer, and keeps the display long enough to show
`SYSTEM STOPPED`. Ctrl+C, explicit behavior stop, shutdown cleanup, and driver
failure use this path. Driver failure persists a system latch. Start a fresh
CLI process and resume only after all safe health probes pass:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  system resume --confirm
```

The watchdog uses a daemon thread, meaning a small background operating-system
thread, and calls the servo zero-pulse path directly if the main asyncio event
loop stops updating. Asyncio is Python's cooperative asynchronous task system.
The thread is tested both with a frozen event loop and with a legitimately slow
asynchronous servo ramp.

### IDE tool examples

```bash
uv run --frozen ninjarobot-ide-tool
uv run --frozen ninjarobot-ide-tool hardware status
uv run --frozen ninjarobot-ide-tool config discover
uv run --frozen ninjarobot-ide-tool config import
uv run --frozen ninjarobot-ide-tool behavior list
uv run --frozen ninjarobot-ide-tool behavior show greeting
uv run --frozen ninjarobot-ide-tool behavior health
uv run --frozen ninjarobot-ide-tool behavior simulate greeting
uv run --frozen ninjarobot-ide-tool behavior simulate move_forward \
  --duration 2
```

Real expressions need `--real`. Real movement additionally needs valid
calibration, both private configuration gates, and `--confirm-motion`. The
complete ordered manual procedure is in the Phase 4 validation report.

Create a one-stage private expression:

```bash
uv run --frozen ninjarobot-ide-tool behavior create \
  --name my_success \
  --description "Celebrate a completed task." \
  --face success \
  --melody exciting \
  --confirm-save
```

The tool validates and simulates the action before saving it. A complete
multi-stage action can instead be supplied with `--from-file`. Any future
AI-proposed action uses the same preview and confirmation path; it cannot save
or physically run itself without user approval.

## Driver package validation commands

### Standalone README contract

Each `pi5*` README must work for a user who has only that complete library
folder. Do not require NinjaRobotPi5, NinjaClawBot, or an invented Git URL.
Tell the user to obtain a copied or downloaded source folder from the project
owner, use `uv sync --frozen`, and test supported hardware functions through
that library's own CLI. Explain any abbreviation or specialist term in plain
language, and clearly separate safe checks from commands that energize hardware
or move an actuator.

The provenance script deliberately ignores only runtime data created by normal
standalone use: `pi5buzzer/buzzer.json`, `pi5camera/photo/`,
`pi5camera/camera_data/`, `pi5servo/servo.json`, and the generated VL53L0X
offset configuration. It still verifies every managed driver source file,
test, package file, and lockfile.

Run each package in its own directory so its `src` layout and test configuration
remain isolated. Frozen mode prevents the five inherited lockfiles from being
rewritten:

```bash
(cd pi5servo && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)
(cd pi5disp && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)
(cd pi5vl53l0x && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)
(cd pi5camera && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)
(cd pi5mic && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)
```

`pi5buzzer` now has a tracked lockfile and an explicitly pinned Ruff version:

```bash
(cd pi5buzzer && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)
```

Run package-native Ruff checks using the root's pinned Ruff 0.15.5. The working
directory is important because it preserves each package's existing
import classification and configuration:

```bash
for package in \
  pi5buzzer pi5servo pi5disp pi5vl53l0x pi5camera pi5mic
do
  (cd "$package" && uv run --project .. --isolated --locked --python 3.11 \
    ruff check --no-cache src tests)
  (cd "$package" && uv run --project .. --isolated --locked --python 3.11 \
    ruff format --check src tests)
done
```

## Raspberry Pi validation flow

Default development uses fakes. Hardware validation is deferred until a
phase-specific checklist has been reviewed and approved. Every checklist must
separate:

1. Safe smoke tests that do not move actuators.
2. Device communication tests for GPIO, I2C, SPI, camera, or USB audio.
3. Actuator-moving tests with an accessible emergency stop.
4. Power-risk tests that require a completed electrical record.

Record expected outcomes, actual results, rollback steps, operator, Pi model,
OS version, and wiring revision. Phase 0 originally performed no physical-device
test; the separate pre-Phase-1 live-Pi report is stored under `docs/validation/`.

## Troubleshooting

- **A root `pytest` run imports the wrong driver package:** use the documented
  package-local commands; the drivers are independent projects.
- **Ruff is unavailable in the shell:** run it through `uv run`.
- **A Ruff upgrade reports new driver errors:** reproduce the Phase 0 gate with
  pinned Ruff 0.15.5 before deciding whether the issue is code or tool-version
  drift.
- **A driver checksum changes unexpectedly:** stop immediately. Revert an
  unintended change or, for an approved and fully validated repair, record the
  new hash with `--record-authorized`.
- **A test tries to access hardware:** ensure it is explicitly marked
  `hardware` and exclude it from the default gate.
- **`distance read` returns 250 mm without opening I2C:** this is the expected
  simulation. Add `--real` only on the Raspberry Pi when you intend to open the
  sensor.
- **The real command reports `DEVICE_UNAVAILABLE`:** install with
  `uv sync --frozen --extra hardware`, confirm I2C is enabled, and confirm
  address `0x29` appears on bus 1.
- **The real command reports `DEVICE_INVALID_READING` and `8191`:** the
  middleware is working correctly by rejecting the sensor's out-of-range
  sentinel. Check sensor power, SDA/SCL wiring (the I2C data and clock wires),
  optical window, target reflectivity, alignment, and cold power before
  considering calibration.
- **A repeated action does not read again:** this is intentional when the same
  action ID or idempotency key is used. Generate a new ID and key for a new
  physical reading.
- **A buzzer result says `simulated: true` and no sound occurs:** this is the
  safe default. Use `--real` only after the electrical checklist is complete.
- **Real buzzer health says unavailable:** confirm the root environment was
  installed with `--extra hardware`, GPIO27 is not claimed by another process,
  and the user can access GPIO.
- **A tone is interrupted or the CLI is cancelled:** the adapter calls
  `off()` before closing. Run `buzzer stop --real` if GPIO access remains
  available, then disconnect buzzer power if silence cannot be confirmed.
- **A display result says `simulated: true` and the screen does not change:**
  this is the safe default. Add `--real` only on the correctly wired Raspberry
  Pi after completing the Phase 3.2 electrical checks.
- **Real display health says unavailable:** confirm SPI is enabled, confirm
  `/dev/spidev0.0` exists, install with `uv sync --frozen --extra hardware`,
  and make sure no other process owns SPI0 or GPIO4/GPIO5/GPIO6.
- **The display lights but shows no image:** verify CE0/CS is GPIO8, MOSI/SDA
  is GPIO10, SCLK/SCL is GPIO11, DC is GPIO4, reset is GPIO5, and backlight is
  GPIO6. CE means chip enable, MOSI means controller-to-display data, and SCLK
  means serial clock.
- **Text is sideways:** the authoritative V4 rotation is 90°. Validate the
  checked-in TOML file and make sure the command uses that file with
  `--config`.
- **The screen goes dark as soon as a command completes:** this is intentional
  cleanup. Add `--hold 5` to a real manual test so the process keeps the
  backlight active long enough to inspect the frame.
- **Servo status reports `simulated: true`:** this is the safe default. No PWM
  or I2C interface was opened.
- **Real servo health is unavailable:** verify the GPIO12/GPIO13
  `pwm-2chan` overlay, confirm I2C address `0x10`, install the hardware extra,
  and confirm the user can access `/sys/class/pwm` and `/dev/i2c-1`.
- **A real move says `--confirm-motion` is required:** this is the first
  deliberate-motion gate. Do not bypass it until the workspace and power
  cutoff are ready.
- **A real move returns `SERVO_MOTION_DISABLED`:** the checked-in configuration
  intentionally blocks movement. Use a private configuration only after the
  electrical record is approved.
- **A real move returns `SERVO_NOT_CALIBRATED`:** calibrate that exact endpoint
  with the standalone `pi5servo` tool. Do not substitute another servo's
  calibration.
- **A continuous-rotation servo does not move to an angle:** this is expected.
  Its calibrated center is neutral, while either side controls direction and
  speed. Begin with a very small value and no mechanical load.
- **Unexpected motion or jitter occurs:** run `behavior stop`, use a physical
  power disconnect if one is installed, shut down before touching wiring, and
  inspect power, common ground, signal routing, and calibration. The current
  robot has no accessible cutoff, which is a known residual risk.
- **Integrated movement says it did not receive clear readings:** keep the
  front sensor aimed at open space beyond 100 mm and confirm it returns three
  valid readings. The motors have not started.
- **Integrated movement says motion is latched:** remove the obstacle or solve
  the power/watchdog problem, then run
  `ninjarobot-ide-tool motion resume --confirm`.
- **Integrated behavior says the system is stopped:** a driver failure is
  latched. Start a fresh process and run
  `uv run --frozen --extra hardware ninjarobot-ide-tool system resume
  --confirm`. The command refuses to clear the latch when a required health
  probe fails.
- **A second terminal cannot stop a behavior:** first run
  `ninjarobot-ide-tool behavior stop`. It validates the recorded process start
  token before sending Ctrl+C, which avoids signaling an unrelated process
  after a process identifier is reused. If no live behavior is registered, it
  safely initializes the servo and distance boundaries and requests direct
  cleanup.
- **Terminal A prints `Exception ignored` or a `PWM.__del__` TypeError after
  a stop:** this is not an expected successful result. The managed buzzer
  backend must release only its configured GPIO pin and interrupt its playback
  worker before cleanup. Confirm the workspace includes the 2026-07-26
  pin-scoped cleanup repair, run immutable-driver verification, and repeat a
  non-moving expression stop before moving the wheels again. A normal
  cross-terminal stop ends with the Level 2 JSON, no cleanup errors, and
  `Aborted!`, with no Python traceback.
- **Backward or turn output says an area is unprotected:** this is expected.
  The VL53L0X faces forward, so it cannot see behind or fully cover either
  side.
- **Distance readings become invalid during movement:** V4 visibly reports the
  warning and continues, following the owner-approved policy. Use
  `behavior stop` immediately if continuing is not safe. Do not unplug the
  sensor while power is on.
- **DFR0566 digital GPIO12/GPIO13 do not show a PWM alternate function:** add
  `dtparam=audio=off` and
  `dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4` to
  `/boot/firmware/config.txt`, reboot, and verify with `pinctrl get 12` and
  `pinctrl get 13`. GPIO18/GPIO19 are an alternative two-pin route, not two
  extra independent channels: PWM0 is GPIO12 *or* GPIO18, while PWM1 is
  GPIO13 *or* GPIO19. Do not confuse these digital breakouts with the HAT's
  dedicated I2C PWM0–PWM3 sockets.
- **Python 3.11 is missing:** install it through `uv python install 3.11`, then
  rerun `uv sync --dev`.
- **Root camera health reports unavailable while `/usr/bin/python3` imports
  Picamera2:** run `./scripts/bootstrap-rpi-camera-workspace.sh` and retry from
  the project root. Do not recreate `.venv` with
  `--system-site-packages`; V4 handles the interpreter boundary itself.
- **A real camera capture requires `--confirm-camera`:** tell everyone nearby
  and obtain consent before adding the flag. Add `--retain` only when the
  image must remain after the command.
- **A retained camera name is rejected:** use a new name such as
  `phase34-test.jpg`. Paths, spaces, extra dots, and overwriting are blocked.
- **`pi5camera capture` reports Picamera2 missing:** verify the OS Picamera2
  package with
  `/usr/bin/python3 -s -c "import libcamera, picamera2"`, then run the root
  camera bootstrap. The project `.venv` does not need to import Picamera2.
  Native `rpicam-*` success alone does not validate the managed V4 bridge.
- **`pi5mic` reports PortAudio missing:** the ALSA device may still be present,
  but library recording requires `libportaudio2`. Install it and
  `portaudio19-dev`, then verify `pi5mic devices`. Local transcription requires
  a built `whisper-cli`, `ggml-base.bin`, and their paths registered in the
  selected mic config.
- **V4 microphone status reports 44.1 kHz instead of 16 kHz:** the selected USB
  device rejected 16 kHz and the managed driver selected its supported native
  rate. This is expected when status remains ready. Inspect both
  `requested_sample_rate_hz` and `actual_sample_rate_hz`.
- **A real microphone capture requires `--confirm-microphone`:** tell everyone
  nearby and obtain consent before adding the flag. Add `--retain` only when
  the WAV must remain after the command.
- **VL53L0X reference calibration retries once:** this is the bounded recovery
  path observed on the live revision-`0x10` device. A second timeout is a hard
  initialization failure; do not bypass calibration.
- **VL53L0X appears at `0x29` but returns `8191 mm`:** communication is working,
  but ranging is invalid. `get`, `test`, `status`, and `performance` now return
  non-zero status for invalid samples, and calibration refuses to save an
  offset. Remove protective film, clean the optical window, verify target
  alignment and wiring, and cold-power-cycle before retrying.
- **A `pi5disp` setup or brightness command changes source-controlled config:**
  verify that the repaired driver is installed. Runtime state defaults to
  `~/.config/pi5disp/display.json`; set `PI5DISP_CONFIG` for an isolated test.
  Runtime commands must not mutate the installed package or repository.
