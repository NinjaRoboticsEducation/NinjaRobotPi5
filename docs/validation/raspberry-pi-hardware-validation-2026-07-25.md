# Raspberry Pi hardware validation — 2026-07-25

## 1. Scope of validation

Validation ran on a Raspberry Pi 5 Model B Rev 1.1 with Debian 13 and kernel
6.18.34. It covered public standalone hardware paths in `pi5buzzer`,
`pi5servo`, `pi5disp`, `pi5camera`, `pi5mic`, and `pi5vl53l0x`.

OpenClaw transport, presence, session, and delivery functions were excluded.
Face enrollment was excluded by user request. Servo movement and calibration
were excluded because no accessible emergency disconnect was available.

## 2. Safety notes

- Servo GPIO12/GPIO13 are header GPIO exposed through the DFR0566 board; they
  are not DFR0566 PWM0/PWM1.
- The two temporary MG90D servos use a reported 5 V supply.
- No servo pulse, movement command, or calibration command was issued.
- Display output was cleared and its backlight was set to 0% after testing.
- Camera and microphone media were created under a temporary directory and
  deleted after testing.
- Post-test status was `throttled=0x0` at 51.6°C.

## 3. Safe smoke tests

| Check | Result | Evidence |
| --- | --- | --- |
| Pi model and OS | PASS | Raspberry Pi 5 Model B Rev 1.1; Debian 13 |
| Device permissions | PASS | User belongs to GPIO, I2C, SPI, audio, video, and render groups |
| Managed-driver provenance | PASS | Original import hashes plus explicitly authorized repairs verified |
| CLI discovery | PASS | All six standalone CLIs and public subcommands loaded |
| Temporary config operations | PASS | Buzzer, servo, display API, microphone, and sensor config import/export completed |
| OpenClaw exclusion | PASS | No OpenClaw command or transport was invoked |

## 4. Communication and interface tests

| Interface | Result | Details |
| --- | --- | --- |
| I2C bus 1 | PASS | DFR0566 `0x10`, VL53L0X `0x29`, camera `0x36` |
| VL53L0X identity | PASS | Registers `0xC0..0xC2` returned `0xEE`, `0xAA`, `0x10` |
| SPI0 | PASS | `/dev/spidev0.0` and `.1` present; display driver reported connected |
| Camera hardware | PASS | OV5647 native capture produced a 2592×1944 JPEG, 752,683 bytes |
| USB microphone hardware | PASS | USB PnP Sound Device recorded 5 seconds of non-silent mono PCM |
| PWM sysfs | PASS | `pwmchip0` present; non-moving hardware-PWM backend probe succeeded |
| GPIO cleanup | PASS | GPIO12/13 inactive, GPIO17 input, display backlight GPIO16 low after rollback |

The microphone rejected 16 kHz in direct hardware mode and recorded at its
native 44.1 kHz. The sample had RMS 198 and peak 2063, confirming non-silent
audio.

## 5. Device and actuator results

### `pi5buzzer`

Status: **PROVISIONAL PASS — operator hearing confirmation required**

- Config init/show/export/import passed using temporary files.
- GPIO17 health check passed.
- Direct 440 Hz and 523 Hz tones completed.
- All 14 predefined emotion sounds completed: angry, confusing, cry,
  embarrassing, exciting, happy, idle, laughing, sad, scary, shy, sleepy,
  speaking, and surprising.
- Each command shut down without an exception.
- Phase 1 reran the GPIO17 health check, a 440 Hz tone, and all 14 emotion
  commands from a freshly locked environment. All commands passed and GPIO17
  returned to input mode.

### `pi5servo`

Status: **PARTIAL — movement blocked**

- Config show/export/import passed.
- GPIO12/GPIO13 `hardware_pwm` status and non-moving probe passed.
- DFR0566 `0x10` status and non-moving probe for all four HAT endpoints passed.
- GPIO12/GPIO13 returned to inactive state after the probe.
- `move`, `cmd`, and calibration were not executed because there is no
  accessible emergency disconnect.
- Follow-up audit confirmed the actual test wiring uses DFR0566 digital
  GPIO12/GPIO13, not dedicated PWM0/PWM1. The required boot overlay was absent.
- A temporary overlay correctly muxed GPIO12/GPIO13 to
  `PWM0_CHAN0`/`PWM0_CHAN1`; both claim-only channels reported `enable=0` and
  `duty_cycle=0`.
- `/boot/firmware/config.txt` now disables analog PWM audio and adds the
  two-channel GPIO12/GPIO13 overlay. Post-reboot confirmation remains pending.

### `pi5disp`

Status: **PARTIAL — command paths pass; visual confirmation required**

- Hardware `info` reported connected over SPI0.
- Clear, 25%/100% brightness, text, explicit-90° image, and a two-second
  10 FPS animation completed.
- Rollback clear and 0% backlight completed.
- Public `ConfigManager` save/export/import passed with temporary files.
- CLI `init --defaults` and brightness commands targeted the immutable package
  `display.json`. The manifest detected the mutations and the file was restored
  after the hardware backlight was turned off. The copied config still contains
  rotation 0° and brightness 100%, while V4 must own runtime rotation and
  brightness outside the driver tree.
- Follow-up repair moved writable state to
  `~/.config/pi5disp/display.json`. Static text, scrolling text, a test image,
  clear, brightness, and a 39-frame animation all passed while the tracked
  package config hash remained unchanged.

### `pi5camera`

Status: **PASS — face enrollment intentionally skipped**

- Native Raspberry Pi camera capture passed with the detected OV5647.
- Library doctor and status loaded but reported Picamera2 missing.
- `pi5camera capture` failed with `ModuleNotFoundError: picamera2` and emitted
  an uncaught traceback.
- Recognition of the native test image completed with zero detected faces.
- Face-store listing passed; enrollment was intentionally skipped.
- Follow-up installed the supported OS Picamera2/libcamera packages, rebuilt
  the environment with system site packages, and fixed the CLI error boundary.
- `doctor` passed and `capture` produced a verified RGB 1280×720 JPEG with
  metadata. The temporary image was deleted.

### `pi5mic`

Status: **PASS — OpenClaw integration excluded**

- Native ALSA enumeration and five-second capture passed.
- Config show/export/import and library status passed.
- `devices` and `record` failed because PortAudio is not installed.
- Follow-up installed PortAudio; `devices` listed the USB microphone and
  library recording produced a five-second 44.1 kHz mono WAV with no overflow.
- Current whisper.cpp and the multilingual base model were installed and
  registered in a user config. Doctor passed and offline transcription returned
  the expected JFK sample sentence.
- Doctor also reported that `whisper-cli` is missing.
- Transcription failed because no Whisper model path is configured.
- OpenClaw functions were not invoked.

### `pi5vl53l0x`

Status: **PARTIAL — initialization repaired; live ranging remains invalid**

- I2C address and identification registers were correct.
- Audit found raw VCSEL encodings passed as clock periods, incomplete
  sequence-step timing overheads, and missing cleanup on calibration timeout.
- Timing-budget calculations now follow the Pololu/ST reference algorithm,
  including TCC, DSS/MSRC, pre-range, final-range, and VCSEL decoding.
- A bounded second reference-calibration attempt recovered the observed live
  revision-`0x10` device after deterministic interrupt/ranging cleanup.
- Compile, Ruff lint, Ruff format, and all 71 tests passed.
- Live status, quick test, and repeated reads now initialize successfully and
  correctly fail validation for the `8191 mm` out-of-range sentinel.
- All live samples remained `8191 mm` against the reported 100 mm target.
- Config show/export/import passed independently.
- Calibration was not run and now rejects invalid samples before saving an
  offset.

## 6. Expected outcomes

- Every detected device remains visible after testing.
- No servo moves without an emergency disconnect and approved movement plan.
- Buzzer and display outputs stop on command.
- Camera and microphone temporary media is deleted.
- GPIO outputs return to safe states.
- Driver checksum verification remains unchanged.

All cleanup outcomes passed. Full functional certification remains blocked by
the invalid VL53L0X optical reading, display/buzzer operator confirmation,
servo post-reboot confirmation, and servo movement safety.

## 7. Pass/fail checklist

- [x] Pi health and permissions
- [x] I2C/SPI/GPIO interface enumeration
- [x] DFR0566 communication
- [x] Buzzer command execution
- [x] Display command execution
- [x] Native camera capture
- [x] Native microphone capture
- [x] Non-moving servo backend probes
- [ ] Operator confirms buzzer sounds were audible
- [ ] Operator confirms display text/image/orientation were correct
- [x] `pi5camera capture` succeeds through Picamera2
- [x] `pi5mic record` succeeds through PortAudio
- [x] Local Whisper runtime and model pass transcription
- [x] VL53L0X completes initialization with bounded calibration recovery
- [ ] VL53L0X returns valid readings near the 100 mm target
- [ ] Servo movement and abort tests have an emergency disconnect

## 8. Rollback steps

1. Stopped all short-lived driver processes.
2. Cleared the display and set backlight brightness to 0%.
3. Confirmed GPIO12/13 inactive and GPIO17 input.
4. Confirmed DFR0566, VL53L0X, and camera remained visible on I2C.
5. Deleted the complete temporary validation directory, including camera and
   microphone media.
6. Reverified the original import baseline plus all authorized driver repairs.
