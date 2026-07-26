# NinjaRobotPi5V4 Development Log

## 2026-07-26 — Phase 3.3 six-servo mixed-backend adapter

### Summary

- Expanded V4 configuration to the fixed `gpio12`, `gpio13`, and
  `hat_pwm1`–`hat_pwm4` topology.
- Added a calibration-file reference, a default-off real-motion gate, and a
  permanently disabled Phase 3.3 group-motion gate.
- Added one shared servo service that lazily selects `pi5servo`'s mixed
  hardware-PWM/DFR0566 backend without changing the managed library.
- Added read-only `servo.status`, confirmation-required single-endpoint
  `servo.move`, and lock-free emergency `servo.stop` capabilities.
- Required valid explicit endpoint calibration before real movement and
  checked endpoint-specific angle limits before sending a center pulse.
- Added cancellation and emergency shutdown that abort movement and sets all
  six outputs to zero.
- Added simulation-first and explicit-real CLI paths. Real movement also
  requires `--confirm-motion`; `--hold` is bounded to five seconds.
- Added `pi5servo[pi]` to the root hardware dependency group.

### Validation

- All 81 V4 tests passed, including topology validation, disabled-motion and
  missing-calibration gates, endpoint limits, center-first movement,
  cancellation, emergency stop, unavailable backends, CLI confirmation, and
  action-result semantics.
- The 30 focused servo/configuration/CLI tests passed.
- All 449 managed-library tests and every package-local Ruff gate passed. The
  only warning was the inherited Python `audioop` deprecation in `pi5mic`.
- Root compilation, Ruff lint, Ruff format, strict mypy for 21 source files,
  dependency lock, CLI smoke, and `git diff --check` passed.
- Driver provenance remained at 222 files and 23 authorized repairs.

### Raspberry Pi status

No PWM, I2C, servo pulse, calibration, or movement command was run during
implementation. Non-moving interface checks may proceed with external servo
power disconnected. Powered calibration and one-at-a-time movement remain
blocked until the six-servo electrical record, calibrations, mechanical
workspace, and emergency power disconnect are approved.

### Follow-up

Run and review the Phase 3.3 Raspberry Pi checklist. Do not begin camera Phase
3.4 until that result is reviewed.

## 2026-07-26 — Phase 3.2 ST7789V display adapter

### Summary

- Added one shared, SPI-serialized display service with lazy `pi5disp` loading.
- Added idempotent `display.show_text`, `display.clear`, and
  `display.set_brightness` capabilities.
- Passed SPI0 device 0, DC GPIO4, reset GPIO5, backlight GPIO6, 32 MHz,
  240×320 dimensions, rotation 90°, and initial brightness 75% from V4-owned
  configuration.
- Added Pillow-based RGB text rendering with bounded text length, font size,
  hexadecimal colors, fit checking, and centered multiline placement.
- Added simulated and explicit-real CLI health, text, clear, and brightness
  commands. The optional `--hold` value keeps a real visual test visible before
  deterministic cleanup.
- Added `pi5disp[pi]` to the root hardware dependency group without changing
  the managed library.
- Hardened partial startup cleanup so a constructed driver is closed if
  backlight initialization fails.

### Validation

- All 66 V4 tests passed, including exact driver settings, RGB-frame size,
  shared lifecycle, SPI resource declarations, bounded arguments, partial
  startup failure, write failure, CLI simulation, and CLI hold bounds.
- The 19 focused display/CLI tests passed.
- All 449 managed-library tests and every package-local Ruff gate passed. The
  only warning was the inherited Python `audioop` deprecation in `pi5mic`.
- Root compilation, Ruff lint, Ruff format, strict mypy for 20 source files,
  dependency lock, CLI smoke, and `git diff --check` passed.
- Driver provenance remained at 222 files and 23 authorized repairs.

### Raspberry Pi status

No SPI or physical display command was run during implementation. The operator
subsequently reported the complete checklist as passing. Attached output
confirms real red and blue frames, centered 320×240 text at rotation 90,
25%/75% brightness changes, safe retry classification, and real rather than
simulated execution. Green was visually confirmed by the operator, although
its JSON output was not included in the transcript.

### Follow-up

The Phase 3.2 Pi checklist is complete and passed. Phase 3.3 may proceed.

## 2026-07-26 — Phase 3.1 GPIO27 buzzer adapter

### Summary

- Added a shared buzzer device service with lazy `pi5buzzer` loading.
- Added bounded `buzzer.play_tone` and emergency `buzzer.stop` capability
  descriptors.
- Limited tones to 20–20,000 hertz, 0.05–2 seconds, and volume 1–128.
- Added cancellation-safe shutdown and an emergency stop path that does not
  wait for the normal playback resource lock.
- Added simulated and explicit-real CLI health, play, and stop commands.
- Added `pi5buzzer[pi]` to the root hardware dependency group without changing
  the managed library.
- Corrected successful non-idempotent action results to report retry safety
  `unsafe`.

### Validation

- All 56 V4 tests passed, including bounded arguments, unavailable GPIO,
  cancellation, concurrent emergency stop, CLI simulation, and action-result
  semantics.
- All 449 managed-library tests and every package-local Ruff gate passed.
- Root compilation, Ruff lint, Ruff format, strict mypy, CLI smoke, dependency
  lock, and `git diff --check` passed.
- Driver provenance remained at 222 files and 23 authorized repairs.

### Raspberry Pi status

No real GPIO or audible command was run during implementation. The operator
subsequently reported the complete Phase 3.1 checklist as passing, including
the electrical prerequisite, real GPIO27 health, quiet 440 Hz and 660 Hz
tones, emergency silence, duplicate protection, and GPIO release.

### Follow-up

The Phase 3.1 Pi checklist is complete and passed. Phase 3.2 may proceed.

## 2026-07-26 — Phase 2 IDE core and VL53L0X reference adapter

### Summary

- Added capability registration, explicit adapter lifecycle, bounded
  scheduling, deterministic resource locks, and a durable SQLite action
  ledger.
- Added an execution engine that prevents duplicate action execution and
  records deadlines, queue rejection, timeout, cancellation, unexpected
  failures, and restart-time unknown outcomes.
- Added the read-only `distance.read` adapter. It lazily loads the unchanged
  `pi5vl53l0x` package only for real execution and normalizes its output into
  the Phase 1 action-result contract.
- Added an explicit guard that reports `8191 mm` as
  `DEVICE_INVALID_READING`; it can no longer look like a successful distance.
- Added hardware-free capability, health, simulated distance, idempotency, and
  action-ledger CLI paths. Real I2C use requires `--real`.
- Added the root `hardware` extra so the local managed VL53L0X package can be
  installed without changing that package.

### Validation

- Registry rollback, ledger persistence, resource races, bounded queues,
  cancellation, deadlines, idempotency, timeouts, unknown outcomes, restart
  recovery, adapter lifecycle, invalid readings, and CLI persistence are
  covered by automated tests.
- Compilation, Ruff lint, Ruff formatting, strict mypy, root pytest, all
  package-local managed-driver tests, and immutable-driver verification passed.
- Driver provenance remained at 222 files and 23 authorized repairs. No
  `pi5*` file changed.

### Raspberry Pi status

No physical hardware command was run during implementation. Operator
validation subsequently passed on I2C bus 1 at address `0x29`: all 10 requested
actions succeeded, distances ranged from 48 mm to 149 mm, each raw value
matched its normalized value, and no `8191 mm` sentinel appeared. The earlier
physical failure is cleared, although its hardware root cause was not
established.

### Follow-up

Run the Phase 2 Raspberry Pi checklist. Begin Phase 3 with the buzzer adapter
only after Phase 2 review and separate approval.

## 2026-07-26 — Phase 1 contracts and package skeletons

### Summary

- Added installable `ninjarobot_pi5_ide` and `ninjarobot_pi5_agent` workspace
  packages plus the unified `ninjarobot_pi5_cli`.
- Added strict, serializable capability, action, result, error, provider, tool,
  session, memory, health, and configuration contracts.
- Added deterministic fake IDE/provider/clock/ID helpers that cannot access
  hardware.
- Added V4-owned hardware configuration with GPIO12/GPIO13 servos, GPIO27
  buzzer, ST7789V DC4/RST5/BL6, rotation 90°, and brightness 75%.
- Accepted ADRs for Pydantic v2 boundary validation and strict mypy typing.
- Added import-boundary tests preventing agent imports of `pi5*`, OpenClaw, or
  the historical runtime.

### Validation

- Phase 1 compilation, Ruff lint, Ruff format, and strict mypy passed.
- All 30 V4/root tests passed in the final full regression gate.
- All 447 managed-library tests and every package-local Ruff gate passed after
  Phase 1, confirming no driver regression.
- CLI version, help, configuration validation, module execution, schema, and
  simulated dry-run paths passed.
- Driver provenance remained at 222 files and 23 authorized repairs.

### Raspberry Pi status

Phase 1 contains contracts and fakes only. No GPIO, PWM, I2C, SPI, camera,
microphone, buzzer, display, sensor, or servo operation was performed.

### Follow-up

Phase 2 may implement the IDE registry, execution engine, action ledger,
resource locks, and the first read-only adapter after separate approval.

## 2026-07-26 — Phase 0 exit reconciliation

### Summary

- Revalidated all managed libraries without changing their current functions.
- Corrected the V4-owned hardware record to GPIO12/GPIO13 servos, GPIO27
  buzzer, and the 240×320 ST7789V display on DC4/RST5/BL6 with rotation 90°
  and brightness 75%.
- Excluded private runtime configuration, captured photos, and recognition data
  from the V4 Git repository.
- Reconciled the historical Phase 0 baseline with the current authorized-driver
  state.

### Validation

- All 447 managed-library tests passed.
- All 7 root governance tests passed.
- Compilation, Ruff lint, Ruff format, immutable-driver provenance, and
  `git diff --check` passed.
- The driver verifier reported 222 files and 23 authorized repairs.

### Raspberry Pi status

No hardware command was executed during this reconciliation. GPIO27 buzzer and
DC4/RST5/BL6 display wiring are recorded but remain pending adapter-phase
hardware validation.

### Follow-up

Proceed with Phase 1 contracts, fakes, configuration, packages, and the unified
CLI without importing or editing any managed driver.

## 2026-07-26 — Correct native Pi PWM channel routing

### Summary

- Corrected `pi5servo` so GPIO12/GPIO18 map to hardware PWM0 and GPIO13/GPIO19
  map to hardware PWM1.
- Added a guard that rejects selecting both alternate pins for one PWM channel.
- Corrected the `pi5servo` setup documentation: the standard `pwm-2chan`
  overlay provides two independent servo signals, not four.
- Preserved local servo calibration and VL53L0X offset files as runtime data in
  the driver-provenance verifier; they are not library source files.

### Validation

- Automated tests validate the alternate-pin mapping and duplicate-route guard.
- The Raspberry Pi validation remains non-moving until an operator supplies
  correctly rated external servo power and has an accessible power disconnect.

### Follow-up

For four independently controlled servos, use DFR0566 PWM0–PWM3 with a
properly rated external servo supply.

## 2026-07-25 — standalone Pi5 library documentation and runtime-data policy

### Summary

- Updated all six managed-library README files to describe standalone source
  folders rather than requiring NinjaRobotPi5 or NinjaClawBot.
- Added frozen-environment guidance, CLI-first test paths, and servo lockfile
  safety guidance.
- Narrowed the provenance script so normal buzzer configuration and camera
  photos/face data are treated as runtime data, not immutable driver source.

### Validation

- Driver provenance passed after the change.
- Root Ruff lint and formatting checks passed.
- Repository governance tests passed.

### Raspberry Pi status

Documentation changes do not energize hardware. Manual CLI testing remains
subject to the existing buzzer/display confirmation, servo emergency-disconnect,
and VL53L0X invalid-reading limits.

## 2026-07-25 — pi5mic PortAudio and local STT repair

### Summary

- Installed PortAudio runtime/development packages.
- Built current whisper.cpp for Raspberry Pi 5 and downloaded the multilingual
  `ggml-base.bin` model.
- Registered the executable and model in
  `~/.config/pi5mic/mic.json`, keeping OpenClaw out of the validation path.

### Root cause

ALSA could capture from the USB microphone, but the Python `sounddevice`
backend could not load because the native PortAudio library was absent.
Local STT also lacked both the `whisper-cli` executable and a configured model.
No `pi5mic` source defect was reproduced.

### Validation

- Package compile, Ruff lint, Ruff format, and all 90 tests passed with one
  inherited Python 3.11 `audioop` deprecation warning.
- `pi5mic devices` listed four inputs including the USB PnP device.
- Library recording produced a five-second, 44.1 kHz, mono, 16-bit WAV with
  220,500 frames and no overflow; the temporary file was deleted.
- Doctor passed with only the expected automatic two-thread warning.
- Offline transcription of the whisper.cpp JFK sample returned the expected
  sentence using `ggml-base.bin`.

### Raspberry Pi status

Microphone capture and local speech-to-text are PASS. Automated recording was
very quiet because no operator speech was supplied during its fixed window.

### Follow-up

Proceed to the VL53L0X timing and calibration repair.

## 2026-07-25 — pi5camera Picamera2 environment and error repair

### Summary

- Installed Raspberry Pi OS `python3-picamera2` 0.3.36 and
  `python3-libcamera` 0.7.1.
- Created the camera environment with system Python 3.13 and
  `--system-site-packages`, then synced the frozen package lock.
- Changed capture, recognize, and enrollment commands to translate every
  package-level `CameraError` into a concise Click error.
- Added a regression proving a missing backend produces no traceback.

### Root cause

Native `rpicam-still` used the OS camera stack successfully, but the earlier
isolated Python 3.11 environment could not import ABI-specific Picamera2 and
libcamera modules installed for Raspberry Pi OS Python 3.13. In addition,
`capture_cmd` caught `CaptureError` but not its sibling
`BackendNotAvailableError`, allowing a traceback to escape.

### Validation

- Picamera2 enumerated one OV5647 camera.
- Camera compile, Ruff lint, Ruff format, and all 24 tests passed.
- `pi5camera doctor` passed with camera and recognition readiness.
- `pi5camera capture` saved a valid RGB 1280×720 JPEG with camera metadata; the
  temporary image was deleted afterward.
- Bootstrap shell syntax passed; ShellCheck is not installed.

### Raspberry Pi status

Camera capture is now a hardware PASS. Face enrollment was intentionally
skipped, as requested.

### Follow-up

Proceed to the USB microphone, PortAudio, and local whisper.cpp phase.

## 2026-07-25 — pi5disp runtime configuration repair

### Summary

- Moved the default writable configuration from the package directory to
  `~/.config/pi5disp/display.json`.
- Added `XDG_CONFIG_HOME` support, a `PI5DISP_CONFIG` override, automatic parent
  directory creation, and regression tests.
- Migrated the known-good rotation-0 configuration into the user runtime path
  without changing the tracked `pi5disp/display.json`.

### Root cause

`ConfigManager` calculated its default by walking four directories upward from
`config_manager.py`. In this source layout that path was the package root, so
`init`, `brightness`, and config writes modified source-controlled
`display.json`.

### Validation

- Package compile, Ruff lint, and Ruff format passed.
- All 65 tests passed, including two new path-selection regressions.
- Clear, 25% brightness, static text, scrolling text, image, and two-second
  animation commands completed on the ST7789V.
- The tracked display config retained SHA-256
  `374f1619c9ccb1c7a8d8aff8b6ded447a250893b9a099b8af6e33cf7639f1b16`.

### Raspberry Pi status

The display was cleared and its backlight set to 0% after validation. Command
execution passed; an operator still needs to confirm orientation, color, text,
and animation visually.

### Follow-up

Proceed to the Picamera2 environment and camera error-handling repair.

## 2026-07-25 — pi5servo DFR0566 GPIO/PWM correction

### Summary

- Confirmed the two test servos use the DFR0566 digital GPIO12/GPIO13
  breakouts, which route to native Raspberry Pi PWM channels 0 and 1.
- Verified the separate DFR0566 I2C controller identity at `0x10`, but did not
  treat that as validation of the digital servo signal path.
- Added the persistent `pwm-2chan` overlay and disabled conflicting analog PWM
  audio in `/boot/firmware/config.txt`; saved a dated backup beside it.
- Corrected the servo and root setup documentation.

### Root cause

The Pi exposed a PWM controller, but GPIO12 and GPIO13 were not muxed to PWM
because the required boot overlay was missing. Earlier status checks therefore
proved only that a PWM controller existed. A temporary runtime overlay changed
both pins to `PWM0_CHAN0`/`PWM0_CHAN1`, and a claim-only probe exported both
channels with `enable=0`, `duty_cycle=0`, and no pulse.

The backend intentionally leaves healthy sysfs PWM channels exported for reuse;
its tests cover that behavior. Attempting to hot-remove the temporary overlay
after export was not a supported validation path and left `dtoverlay -r`
waiting in the kernel. A reboot is required to clear that process and apply the
persistent configuration cleanly.

### Validation

- All 132 package tests passed.
- Package compile, Ruff lint, and Ruff format passed.
- DFR0566 identity registers returned PID `0xDF` and VID `0x10`.
- Native GPIO12/GPIO13 claim-only checks remained disabled at zero duty.
- Driver provenance passed with the documented README repair.

### Raspberry Pi status

No servo pulse, angle, movement, or calibration command was issued. Final
post-reboot pin-mux and claim-only validation remains pending. Actuator movement
continues to be blocked by the missing emergency disconnect.

### Rollback

Restore `/boot/firmware/config.txt.ninjarobotpi5-20260725.bak` over
`/boot/firmware/config.txt` and reboot.

### Follow-up

Continue with `pi5disp`; perform the servo post-reboot check before any future
movement test.

## 2026-07-25 — pi5buzzer reproducible validation repair

### Summary

- Pinned Ruff 0.15.5 and declared the package lint rules explicitly.
- Added a package lockfile and corrected one import-order violation exposed by
  the explicit rule set.
- Updated the package and root developer documentation.

### Root cause

`pi5buzzer` declared an unbounded Ruff development dependency and had no
lockfile. A fresh package-local sync selected Ruff 0.16.0 with a materially
different effective rule set, producing 23 errors even though the validated
Ruff 0.15.5 workflow passed. The runtime driver itself had no reproduced
functional failure.

### Validation

- Fresh frozen environment resolved Ruff 0.15.5.
- Compile, Ruff lint, and Ruff format passed.
- All 65 package tests passed.
- Driver provenance passed with four authorized `pi5buzzer` files.

### Raspberry Pi status

GPIO17 initialization and health checks passed. A 440 Hz tone and all 14
predefined emotion commands completed without exceptions, and GPIO17 returned
to input mode. Audible confirmation remains an operator observation.

### Follow-up

Proceed to `pi5servo` using DFR0566 digital GPIO12/GPIO13 and native hardware
PWM, without issuing an actuator-moving pulse.

## 2026-07-25 — Managed-driver repair authorization

### Summary

- Confirmed the attached expansion HAT is DFR0566.
- Confirmed that the temporary servos remain on DFR0566 digital GPIO12/GPIO13
  breakouts. They use native Raspberry Pi hardware PWM, not the HAT's dedicated
  I2C PWM0/PWM1 sockets.
- Replaced the copied-driver immutability rule with an audited managed-driver
  repair workflow while preserving the historical import hashes.
- Added a separate authorized-change manifest and provenance validation.

### Rationale

The project owner explicitly authorized fixing each standalone Pi5 library
after README review, Serena audit, failure reproduction, linting, tests, and
hardware validation. Keeping original and repaired hashes in separate manifests
preserves historical provenance without blocking validated repairs.

### Validation

The original 221-file import manifest matched with zero authorized repairs.
Compilation, Ruff lint, Ruff format, `git diff --check`, and all six root
governance tests passed.

### Raspberry Pi status

No actuator-moving command is authorized because the continuous-rotation
servos have no accessible emergency disconnect. DFR0566 communication and
non-moving checks may proceed.

### Follow-up

Repair and validate the six libraries one at a time, beginning with
`pi5buzzer`.

## 2026-07-25 — Phase 0 repository foundation

### Summary

- Confirmed the V4 architecture and phase ordering.
- Confirmed `/home/rogerchang/NinjaRobotPi5` as the new repository root.
- Classified nested `NinjaClawBot/` as an ignored, read-only code reference.
- Exported the six tracked Pi5 library trees without changing their contents.
- Added root project governance, documentation, validation, hardware, and ADR
  scaffolding.

### Rationale

The clean root prevents the OpenClaw runtime from becoming an accidental V4
dependency. Immutable driver copies preserve the already-tested hardware
contracts while all integration and containment work moves into V4-owned
middleware.

### Validation

The root gate passed with three governance tests. All six copied-driver suites
passed with 435 tests, and their native Ruff lint and format checks passed.
The 221-file immutable manifest matched before and after validation. Ruff is
pinned to 0.15.5 because 0.16 changes inherited package-configuration behavior;
upgrading it requires a separate review and must not trigger driver rewrites.
Full command output and the one inherited `audioop` deprecation warning are
summarized in `docs/validation/phase-0-baseline.md`.

### Raspberry Pi status

No physical hardware was accessed. Powered servo validation remains blocked
until the supply, current, protection, grounding, and emergency-disconnect
record is complete.

### Follow-up

After Phase 0 review, Phase 1 will add strict shared contracts and the initial
`ninjarobot_pi5_ide` and `ninjarobot_pi5_agent` package skeletons.

## 2026-07-25 — Pre-Phase-1 Raspberry Pi hardware validation

### Summary

- Exercised public standalone hardware paths for all six copied Pi5 libraries.
- Excluded OpenClaw integrations and face enrollment as requested.
- Used temporary configurations and deleted captured camera/audio media.
- Kept servo testing non-moving because no emergency disconnect is available.

### Results

- Buzzer GPIO health, tones, and all 14 predefined sounds completed.
- Display clear, brightness, text, image, and animation commands completed;
  visual confirmation remains pending.
- Direct GPIO and DFR0566 servo backend probes completed without movement.
- Native OV5647 capture passed, but `pi5camera capture` failed because
  Picamera2 is unavailable to its Python environment.
- Native USB microphone capture passed at 44.1 kHz, but `pi5mic` recording
  failed because PortAudio is missing; local Whisper is also unconfigured.
- VL53L0X identity reads passed, but driver initialization timed out during
  reference calibration.
- `pi5disp init --defaults` and brightness commands attempted to rewrite the
  immutable driver config. The manifest caught the changes and the original
  file was restored after the hardware backlight was turned off.

### Safety and rollback

No servo pulse or movement command was issued. The display was cleared with its
backlight set to 0%, relevant GPIO returned to safe states, the Pi remained
unthrottled, all temporary media was deleted, and all 221 immutable files
matched the Phase 0 baseline.

### Follow-up

Resolve the camera Python dependency, microphone runtime/STT setup, and VL53L0X
initialization failure. Add an accessible servo emergency disconnect before
movement validation. Full evidence is recorded in
`docs/validation/raspberry-pi-hardware-validation-2026-07-25.md`.

## 2026-07-25 — pi5vl53l0x timing and validation repair

### Summary

- Replaced incomplete measurement-timing calculations with the Pololu/ST
  sequence-step algorithm.
- Decoded VCSEL period registers before macro-period conversion.
- Added deterministic calibration cleanup and one bounded recovery attempt.
- Prevented CLI commands from reporting success for invalid range samples.
- Prevented calibration from saving an offset derived from sentinel data.

### Root cause

The driver passed raw VCSEL register encodings directly into macro-period
calculations, omitted TCC and DSS/MSRC timing stages, and used incorrect fixed
overheads. A timed-out calibration also left ranging state uncleared. After
those fixes, the live revision-`0x10` sensor consistently required one bounded
retry of phase calibration. The retry succeeds, but the connected module still
returns the `8191 mm` out-of-range sentinel at the reported 100 mm target.

### Validation

- Package compilation, Ruff lint, and Ruff format passed.
- All 71 package tests passed, including timing, VCSEL decoding, timeout
  cleanup/retry, invalid CLI status, and calibration rejection tests.
- I2C address `0x29` and identity `0xEE/0xAA/0x10` passed.
- Live initialization and health checks passed after bounded recovery.
- Live status, quick test, and repeated-read commands correctly returned
  non-zero status for invalid `8191 mm` samples.
- Six repaired files were recorded in the authorized-driver manifest.

### Raspberry Pi status

This phase is a software pass and a partial hardware pass. No actuator was
involved. Valid 100 mm distance measurement remains blocked on a physical
optical/alignment, wiring, power, or sensor-module issue. Calibration remains
intentionally blocked until valid samples are observed.

### Follow-up

With Pi power disconnected, inspect the sensor window for film or obstruction,
verify target alignment and the `3.3V/GND/SDA/SCL` path through DFR0566, then
cold-power-cycle and rerun `pi5vl53l0x status` and `pi5vl53l0x test`.
