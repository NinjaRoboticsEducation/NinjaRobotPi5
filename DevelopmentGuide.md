# NinjaRobotPi5V4 Development Guide

This guide describes the developer workflow for the clean V4 repository.
`NinjaRobotPi5V4_ImplementationPlan.md` remains authoritative when this guide is
incomplete or conflicts with it.

## Repository layout

- `ninjarobot_pi5_ide/`: deterministic robot contracts and future middleware.
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
DC4/RST5/BL6 with rotation 90° and brightness 75%.

Inspect schemas or exercise the fake IDE:

```bash
uv run --frozen ninjarobot_pi5_cli contracts schema
uv run --frozen ninjarobot_pi5_cli dry-run \
  --capability system.echo \
  --json '{"message":"hello"}'
```

`dry-run` never opens GPIO, I2C, SPI, camera, or audio. Its result must include
`"simulated": true`.

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
- **`pi5camera capture` reports Picamera2 missing:** verify the OS Picamera2
  package is installed, then run the package bootstrap. The environment must
  use `/usr/bin/python3`, `--system-site-packages`, and
  `uv sync --active --frozen`; a separate uv Python cannot import the OS
  libcamera ABI. Native `rpicam-*` success alone does not validate
  `pi5camera`.
- **`pi5mic` reports PortAudio missing:** the ALSA device may still be present,
  but library recording requires `libportaudio2`. Install it and
  `portaudio19-dev`, then verify `pi5mic devices`. Local transcription requires
  a built `whisper-cli`, `ggml-base.bin`, and their paths registered in the
  selected mic config.
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
