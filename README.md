# NinjaRobotPi5V4

NinjaRobotPi5V4 is a clean, modular robot-control platform for Raspberry Pi 5.
It replaces the historical OpenClaw-based orchestration with two project-owned
layers:

- `ninjarobot_pi5_ide`: deterministic middleware that exposes safe, standardized
  robot capabilities.
- `ninjarobot_pi5_agent`: provides the bounded local agent service, Ollama
  adapter, conversational CLI, HTTPS web controller, MCP tools, and validated
  non-executable agent skills.

The implementation follows
[`NinjaRobotPi5V4_ImplementationPlan.md`](NinjaRobotPi5V4_ImplementationPlan.md),
which is the single source of truth.

## Current status

Phase 0, Phase 1, Phase 2, Phase 3.1 through Phase 3.5, and Phase 4 are
implemented and the operator reports the complete Phase 4 and installation
workflow passed. Phase 5.0 through Phase 5.7 and the 2026-07-29 agent/web
refinement are implemented and pass the local software gate. Raspberry Pi
acceptance—including the Qwen3:4B
performance benchmark, live Tavily search, LAN browser checks, camera,
microphone, and raised-wheel motion—still requires the operator checklist in
[`docs/validation/phase-5-agent-refinement-validation-2026-07-29.md`](docs/validation/phase-5-agent-refinement-validation-2026-07-29.md).
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

Phase 3.3 added a six-endpoint-capable mixed backend and three capabilities:
`servo.status`, single-endpoint `servo.move`, and emergency `servo.stop`.
GPIO12/GPIO13 use Raspberry Pi hardware PWM, while `hat_pwm1` through
`hat_pwm4` use DFR0566 PWM0 through PWM3 over I2C. Phase 4 changes the default
robot topology to the two installed wheel servos on GPIO12 and GPIO13 while
retaining the four HAT PWM names for user-customized configurations. Real
single-servo movement remains disabled in the checked-in configuration and
requires `--real`, `--confirm-motion`, and a valid endpoint calibration. The
Phase 3.3 software gate passes. The operator reports that all
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
The operator reports that the complete Phase 3.4 physical checklist passes.

Phase 3.5 adds `microphone.status` and `microphone.capture` through one
serialized USB microphone service. Status discovers and validates the selected
input without recording. Capture is privacy-sensitive, bounded to the
configured maximum, and requires `--real --confirm-microphone` for physical
audio. WAV files are deleted by default; `--retain` saves one owner-only file
inside `~/.local/share/ninjarobot_pi5/microphone`. WAV is an uncompressed audio
file format. Transcription, wake-word listening, Gemini, and historical
OpenClaw integrations are not Phase 3.5 features.

Phase 4 adds validated integrated behaviors and the `ninjarobot-ide-tool`.
Behavior stages run in order, while display, buzzer, and motor operations
inside one stage begin together. V4 independently implements 20 animated
faces: `idle`, `happy`, `laughing`, `sad`, `cry`, `angry`, `surprising`,
`sleepy`, `speaking`, `shy`, `scary`, `exciting`, `confusing`, `greeting`,
`listening`, `thinking`, `curious`, `success`, `warning`, and `error`. They
match the intended historical expression meanings without importing, copying,
or packaging the historical runtime. The bundled movements are
`move_forward`, `move_backward`, `turn_left`, and `turn_right`. `celebrate`
and `error_warning` provide special combinations. `stop` is deliberately a
safety command, not a reusable behavior asset.

The default logical mapping is `left_motor` to GPIO12 and `right_motor` to
GPIO13. Movement no longer waits for clear-distance samples before starting.
`move_forward`, `turn_left`, and `turn_right` stop and latch at Level 1 after
three consecutive valid readings at or below 50 mm. The exact raw `8191`
sentinel means clear space. Null, invalid, missing, and stale readings do not
stop movement. `move_backward` is warning-only because the forward-facing
sensor cannot protect the rear. Undervoltage and a frozen control-loop
watchdog also stop both motors.
Ctrl+C, normal tool shutdown, an explicit behavior stop, or a hardware-driver
failure performs Level 2 cleanup: stop servos and ranging, close camera and
microphone devices, silence the buzzer, and show a red Emergency Stop sign.
The interactive Resume operation reconstructs and health-checks stopped
modules, then shows Idle; it never restarts the previous movement. Driver
failure remains latched until an explicitly confirmed healthy resume.

GPIO-backed devices release only the pins they own. This matters on Raspberry
Pi 5 because the buzzer and display share one `rpi-lgpio` process connection;
closing that connection globally while another PWM object still exists can
produce a shutdown traceback even after the hardware has stopped.

The `pi5buzzer` development environment is locked and its 66 tests pass. The
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
3. **NinjaRobotPi5 Agent** — owns user interaction, bounded planning, the local
   model provider, seven-day transcripts, policy, MCP connections, validated
   skills, and IDE tool calls. It never imports hardware drivers directly.

### Implemented Phase 5 agent

Phase 5 keeps Ollama and the selected language model on the Raspberry Pi.
Qwen3:4B is the installed candidate, not an accepted default until it passes
the recorded Raspberry Pi benchmark. The `ninjarobot-agent` command provides
streaming chat, session history, service lifecycle, MCP and skill management,
and an interactive menu. A FastAPI HTTPS interface serves the local network,
and one browser holds the exclusive controller lease at a time.

The agent is also an MCP host. MCP means Model Context Protocol, a standard
connection for separately installed tools. The official hosted Tavily MCP
server is the bundled real-time web-search preset after the owner adds a
personal API key. Search output remains untrusted and cannot bypass the IDE or
robot safety policy.

Validated agent skills are confined data-and-instruction packages, not
executable code. The exact MCP and skill formats are recorded in the
[Phase 5 extension appendix](InstallationGuide.md#phase-5-mcp-and-agent-skill-extension-reference).

The HTTPS controller provides direct D-pad movement, Level 2 Emergency Stop,
confirmed Resume, Greeting, Celebrate, temporary camera preview, local
whisper.cpp USB-microphone transcription, English/Japanese browser speech
recognition, AI chat, and live events. A second browser receives `423 Locked`.
Missed heartbeats revoke the lease and request a motor stop without waiting for
the model. Agent startup runs Greeting once, then the IDE supervises a silent
looping Idle face between normal interactions. The portrait-first controller
supports mobile Chrome and Safari, prevents D-pad text selection, keeps Live
Activity in a bottom drawer, and places browser speech in the message box for
review before Send.

## Implemented CLI functions

The current CLI provides:

- `config validate` strictly validates V4-owned TOML configuration.
- `contracts schema` prints JSON Schema, a machine-readable description of
  valid contract data.
- `dry-run` executes against a deterministic fake IDE and labels the result
  `"simulated": true`.
- `capabilities` lists all implemented distance, buzzer, display, servo,
  camera, and microphone capabilities without opening hardware.
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
- `microphone health` checks PortAudio and input-device readiness without
  recording. PortAudio is the operating-system audio library used by Python.
- `microphone status` lists the selected and available input devices, including
  requested and actually supported sample rates, without recording.
- `microphone capture` records one simulated WAV unless `--real` and
  `--confirm-microphone` are supplied. It retains no audio unless `--retain`
  is also supplied.
- `--version` reports the installed V4 package version.

The integrated `ninjarobot-ide-tool` additionally provides:

- a boxed interactive menu, styled consistently with the standalone Pi5
  tools, when run without a subcommand
- direct execution of selected built-in or private behaviors, a Back choice in
  every submenu, and an Emergency Stop shortcut from every menu
- 15 everyday face choices, four wheel movements, and Greeting, Celebrate,
  Emergency Stop, Resume Robot Movement, and Error Warning special choices
- a guided creator, private behavior runner/deleter, and a hardware-free
  simulation browser with explanations in the interface
- `hardware status` for configuration and optional safe real-device probes
- `config discover` and preview-first `config import`
- `behavior list`, `show`, `health`, `simulate`, `run`, `create`, `validate`,
  `delete`, and `stop`
- `behavior run NAME --loop` for a scriptable final-face loop
- `motion resume --confirm` for a Level 1 latch
- `system resume --confirm` for a driver-failure Level 2 latch

Simulation is always the default. A real movement also requires
`--confirm-motion`. Private behaviors are stored under
`~/.config/ninjarobot_pi5/behaviors`, validated before use, previewed in
simulation before saving, and never overwrite an existing action silently.

The `ninjarobot-agent` additionally provides:

- `service run|start|status|stop` for the single owner process
- streaming `chat`, reconnectable sessions, seven-day transcripts, and
  `/help`, `/exit`, `/clear`, `/status`, `/arm`, and `/disarm`
- `web start|status|stop` for the HTTPS local-network interface
- `motion arm --confirm` for one CLI chat session's physical-motion consent
- `mcp` commands for the Tavily preset and approved `stdio` or Streamable HTTP
  servers
- `skill` validation, simulation, non-overwriting installation, enable,
  disable, inspection, and confirmed removal
- `benchmark ollama` for the required Qwen3:4B Raspberry Pi acceptance report

Simulation remains the service default. Start the physical service only after
all Phase 4 hardware checks pass:

```bash
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  service start --real

uv run --frozen ninjarobot-agent web start
```

Quitting a CLI disconnects only that terminal. Use `web stop` to stop the web
interface and `service stop` to release the model, IDE, hardware, MCP, database,
socket, and web resources.

The contracts reject unknown fields and unsafe type conversion. They cover
capabilities, actions, results, errors, provider turns, tool calls, sessions,
memory candidates, health, and configuration. Strict mypy checking—the static
analysis of type hints without running the program—is mandatory for new V4
source.

Phase 2 accepts an action ID only once. Repeating the same action ID and request
returns the stored result without reading the sensor again. Timeouts,
cancellation, full queues, expired deadlines, startup interruption, and
unknown outcomes are recorded as structured failures. The public
`distance.read` capability never reports `8191 mm` as a real distance: it
returns the structured `DEVICE_OUT_OF_RANGE` result. The integrated movement
safety layer interprets that exact structured result as silent clear space.
Other null or failed readings remain communication faults, but the integrated
movement layer no longer waits for clear-distance samples before starting and
does not treat those faults as obstacle stops.

The nested `NinjaClawBot/` checkout is an excluded, read-only historical
reference. It is not part of the V4 product or Git history.

## Hardware foundation

The confirmed target is a Raspberry Pi 5 with 8 GB RAM and a 256 GB NVMe SSD.
The robot uses the DFRobot DFR0566 expansion HAT, two default wheel-servo endpoints,
a passive buzzer, VL53L0X sensor, ST7789V display, USB microphone, and Raspberry
Pi camera. The temporary servos are connected to the DFR0566 digital
GPIO12/GPIO13 breakouts. Those connectors use the Raspberry Pi's native
hardware PWM and require the `pwm-2chan` boot overlay; they are not the HAT's
dedicated I2C-controlled PWM0/PWM1 sockets. The installed motors are MG90D
360-degree continuous-rotation servos. Their values represent direction and
speed around calibrated neutral, not a requested physical angle.

The owner-confirmed power chain is the official 27 W supply into the Geekworm
X1208, then the Raspberry Pi and DFR0566, with both servo red wires connected
to the D12/D13 `+` terminals. The measured servo voltage is within the stated
4.8–6.6 V range. There is no accessible physical emergency power disconnect.
That is a material residual risk; software stop and watchdog controls reduce
the risk but cannot replace a physical cutoff.

The current V4-owned wiring record uses the passive buzzer on GPIO27 and the
ST7789V display on SPI0 with DC GPIO4, reset GPIO5, and backlight GPIO6. The
display is 240×320, rotated 90°, at 75% brightness.
The observed CSI camera is an OV5647 used at 1280×720. CSI is the Raspberry
Pi's flat camera connection. OV5647 is fixed-focus, so V4 uses autofocus mode
`none`.

## Installation and developer setup

For a new Raspberry Pi 5, follow the complete
[`InstallationGuide.md`](InstallationGuide.md). It starts with Raspberry Pi OS
Lite 64-bit, then covers headless system setup, hardware dependencies,
standalone module initialization and calibration, IDE configuration import,
simulation, physical testing, and troubleshooting in one ordered workflow.
Raspberry Pi OS Lite is the default recommendation because it avoids desktop
overhead and leaves more memory and processing capacity for robot control and
future local AI models.

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
uv run --frozen ninjarobot_pi5_cli microphone health \
  --ledger /tmp/ninjarobot-phase35-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli microphone status \
  --ledger /tmp/ninjarobot-phase35-smoke.sqlite3
uv run --frozen ninjarobot_pi5_cli microphone capture \
  --ledger /tmp/ninjarobot-phase35-smoke.sqlite3 \
  --duration 0.25
```

On the Raspberry Pi, install the optional managed hardware packages without
changing their source:

```bash
uv sync --frozen --extra hardware
uv run --frozen --extra hardware python \
  scripts/verify_workspace_driver_sources.py
```

The six managed `pi5*` libraries are editable path dependencies. Editable means
the virtual environment executes the source in this checkout directly, so a
pulled or locally authorized driver repair cannot be hidden by an older copied
wheel in `.venv`. The verification command must report that all six packages
resolve into this checkout.

Start with integrated hardware-free checks:

```bash
uv run --frozen ninjarobot-ide-tool behavior list
uv run --frozen ninjarobot-ide-tool behavior show greeting
uv run --frozen ninjarobot-ide-tool behavior health
uv run --frozen ninjarobot-ide-tool behavior simulate greeting
uv run --frozen ninjarobot-ide-tool behavior simulate move_forward \
  --duration 2
```

Run the interactive menu with:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml"
```

The interactive tool executes normal selections directly on configured
hardware. Choose its Simulation menu when you want a guaranteed hardware-free
preview. Scriptable commands still simulate unless `--real` is supplied.

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
For microphone integration, follow
[`docs/validation/phase-3-5-microphone-validation-2026-07-26.md`](docs/validation/phase-3-5-microphone-validation-2026-07-26.md).
Real recording also requires consent from everyone nearby.
For Phase 4 integrated behaviors and movements, follow
[`docs/validation/phase-4-integrated-behavior-validation-2026-07-26.md`](docs/validation/phase-4-integrated-behavior-validation-2026-07-26.md).
For the refined 20-face catalog, direct interactive menus, `8191` startup
handling, Emergency Stop sign, and Resume workflow, follow
[`docs/validation/phase-4-refinement-validation-2026-07-27.md`](docs/validation/phase-4-refinement-validation-2026-07-27.md).

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
The Phase 3.5 microphone path is also classified as `privacy`, requires
explicit real-recording confirmation, and deletes audio unless retention is
requested. It performs no transcription, wake-word detection, cloud request,
or agent handoff. Phase 5 adds a separate IDE
`microphone.transcribe` capability: it records a bounded temporary WAV, runs
local whisper.cpp, returns text, and deletes the WAV and transcript staging
files even after cancellation or failure.

Phase 4 never moves physical motors in simulation. Real integrated movement
requires the private configuration to enable both motion gates, valid
calibration for GPIO12 and GPIO13, `--real`, and `--confirm-motion`. A Level 1
stop keeps display, buzzer, and sensors available but blocks another movement
until `motion resume --confirm`. A driver-failure Level 2 stop blocks all
behaviors until `system resume --confirm` completes healthy probes. Invalid,
missing, or stale distance readings may warn but do not stop movement. The
exact `8191` out-of-range sentinel is silent clear space, and there is no
guarded-startup distance gate.
Model output is treated as an untrusted proposal; the
deterministic IDE control plane retains final authority over robot actions.
Browser control is HTTPS but intentionally has no pairing authentication in
Phase 5. The first device on the local network can acquire the only controller
lease. Do not expose port 8443 to the internet or configure router port
forwarding. The generated server certificate is signed by the robot's local
certificate authority. Export and trust its public CA certificate once on
each controlling phone or computer; never copy either private key.
