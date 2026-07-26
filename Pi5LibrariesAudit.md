# Pi 5 Libraries Audit and Manual Test Guide

## What this report covers

This report records the current condition of the six standalone Raspberry Pi 5
hardware libraries in this repository:

- `pi5buzzer` for the passive buzzer.
- `pi5servo` for servo control.
- `pi5disp` for the ST7789V display.
- `pi5camera` for the Raspberry Pi camera.
- `pi5mic` for the USB microphone and local speech-to-text.
- `pi5vl53l0x` for the VL53L0X distance sensor.

It combines the recorded Raspberry Pi test session with a fresh audit on
2026-07-25. The full previous hardware record is in
[`docs/validation/raspberry-pi-hardware-validation-2026-07-25.md`](docs/validation/raspberry-pi-hardware-validation-2026-07-25.md).

## Short answer

All six libraries pass their automated software tests and their code-quality
checks. The managed-driver checksum check also passes: 222 driver files match
the original import baseline and the 20 approved repairs.

This does **not** mean every physical device is fully certified yet. The
remaining physical work is:

- Confirm by ear that the buzzer sounds are audible.
- Confirm by eye that the display image, text, and orientation are correct.
- Test real servo movement only after an emergency power disconnect is
  available.
- Repair or replace the VL53L0X sensor path because it still reports an invalid
  `8191 mm` distance.
- Repair the `pi5servo` lockfile mismatch before using ordinary `uv run`
  commands without `--frozen`.

## Plain-English terms used in this guide

- **CLI** means command-line interface: a command you type into a terminal.
- **GPIO** means general-purpose input/output: the numbered electrical pins on
  the Raspberry Pi header.
- **I2C** means a two-wire device bus used by small sensors and controller
  boards.
- **SPI** means a fast serial bus commonly used by displays.
- **PWM** means pulse-width modulation: precisely timed electrical pulses used
  to control a servo or a buzzer.
- **DFR0566** is the DFRobot expansion board connected to this Raspberry Pi.
- **OV5647** is the detected Raspberry Pi camera module.
- **VL53L0X** is a laser time-of-flight distance sensor.
- **Provenance** means proof that a managed driver file still matches its
  approved version.
- **Frozen mode** means `uv` must use the existing dependency lockfile instead
  of silently rewriting it.
- **uv** is the Python tool used here to create an environment, install packages,
  and run the project commands.
- **Lockfile** means the saved, exact list of package versions that were tested.
- **0x10**, **0x29**, and **0x36** are hexadecimal (base-16) device addresses.
- **mm** means millimetres, a unit of distance.
- **JPEG** is a common compressed photo-file format. **RGB** means red, green,
  and blue, the three colour channels in a digital image.
- **Whisper** is the local program that turns recorded speech into text.
- **Current-limited** means the servo power supply is set to stop delivering
  unsafe levels of electrical current.

## Evidence collected during this audit

### Software checks

All package checks passed:

| Library | Tests passed | Compile, lint, and formatting |
| --- | ---: | --- |
| `pi5buzzer` | 65 | Passed |
| `pi5camera` | 24 | Passed |
| `pi5disp` | 65 | Passed |
| `pi5mic` | 90 | Passed |
| `pi5servo` | 132 | Passed |
| `pi5vl53l0x` | 71 | Passed |

That is **447 passing library tests**. The root repository governance suite
(the tests that check repository rules) also passed: **6 tests**.

The following command passed before this report was created:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv run --frozen python scripts/verify_immutable_drivers.py
```

Expected result:

```text
PASS: 222 tracked files across 6 drivers match the import baseline plus 20 authorized repairs.
```

### Current Raspberry Pi findings

- The computer is a Raspberry Pi 5 Model B Rev 1.1.
- The Pi has no current power-throttling warning (`throttled=0x0`).
- I2C bus 1 sees the DFR0566 at `0x10`, the VL53L0X at `0x29`, and the camera
  at `0x36`.
- SPI display devices `/dev/spidev0.0` and `/dev/spidev0.1` exist.
- The OV5647 camera is detected.
- A USB PnP Sound Device microphone is detected.
- GPIO12 and GPIO13 now show the required PWM functions
  `PWM0_CHAN0` and `PWM0_CHAN1` after reboot.
- A non-moving `pi5servo` hardware-PWM probe passed. It claims and releases the
  channels but does not send a servo movement command.
- `pi5camera doctor` currently passes.
- `pi5mic doctor` passes when given the validated user configuration file.
- `pi5vl53l0x status` currently initializes the sensor but reports
  `INVALID 8191 mm`. This is a failure, not a usable measurement.

## Important safety rules

1. Turn Raspberry Pi power off before changing any wiring.
2. Never power several servos from the Raspberry Pi header. Use an external
   5 V supply and connect its ground to Raspberry Pi ground.
3. Do not run a servo movement or calibration command until you have an
   immediate way to disconnect servo power.
4. Do not hot-plug the display or distance sensor while a test command is
   running.
5. Keep temporary camera photos and microphone recordings under `/tmp` and
   delete them after testing.
6. Use `--frozen` in the commands below. It prevents a dependency lockfile from
   being silently changed during testing.

## Common pre-test checks

Run these once before testing individual libraries:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv run --frozen python scripts/verify_immutable_drivers.py
vcgencmd get_throttled
vcgencmd measure_temp
i2cdetect -y 1
```

Pass if:

- The provenance command prints `PASS`.
- `get_throttled` prints `throttled=0x0`.
- The I2C scan includes `10`, `29`, and `36`.
- The temperature is reasonable for the room and cooling setup.

If the Pi reports throttling, stop hardware testing and check its power supply
and cooling first.

## 1. `pi5buzzer` manual test

This library controls a passive buzzer on GPIO17. The sound commands below
energize the buzzer.

### Step 1: Check the saved settings

```bash
cd /home/rogerchang/NinjaRobotPi5/pi5buzzer
uv run --frozen pi5buzzer info
```

Expected result: the report shows GPIO17 and the configured volume.

### Step 2: Play short sounds

```bash
uv run --frozen pi5buzzer beep 440 0.3
uv run --frozen pi5buzzer play happy
uv run --frozen pi5buzzer info --health-check
```

Expected result: you hear a short 440 Hz tone, then the happy pattern, and
then the health-check tone. Each command should exit normally and the buzzer
must become silent afterward.

### Step 3: Confirm cleanup

```bash
pinctrl get 17
```

Pass if GPIO17 is not left as an actively driven output after the command.
If a sound does not stop, press `Ctrl+C`; then power off the Pi before checking
the buzzer wiring.

Current status: **provisional pass**. Commands have completed successfully,
but an operator still needs to confirm that the sound was actually audible.

## 2. `pi5servo` manual test

The temporary servos are connected through the DFR0566 digital GPIO12/GPIO13
breakouts. These are Raspberry Pi header GPIO paths; they are **not** the
DFR0566 board's dedicated PWM0/PWM1 connectors.

### Step 1: Run safe, non-moving checks

```bash
cd /home/rogerchang/NinjaRobotPi5/pi5servo
pinctrl get 12
pinctrl get 13

uv run --frozen pi5servo status \
  --backend hardware_pwm \
  --pins 12,13 \
  --pin-channel-map 12:0,13:1 \
  --no-probe

uv run --frozen pi5servo status \
  --backend hardware_pwm \
  --pins 12,13 \
  --pin-channel-map 12:0,13:1 \
  --probe
```

Expected result:

- GPIO12 shows `PWM0_CHAN0`.
- GPIO13 shows `PWM0_CHAN1`.
- The probe reports `Ready (hardware_pwm)`.
- No servo moves during this step.

These checks passed during the audit.

### Step 2: Prepare before any movement

Do not proceed unless all of the following are true:

- The servo has a separate, current-limited 5 V power supply.
- The external power ground and Raspberry Pi ground are connected together.
- The robot is lifted so wheels, horns, and arms cannot strike anything.
- You can immediately unplug or switch off the external servo power.

### Step 3: Calibrate and test one servo only

The following commands can move a servo. Start with one endpoint and stop
immediately if movement is unexpected:

```bash
uv run --frozen pi5servo calib 12 \
  --backend hardware_pwm \
  --pin-channel-map 12:0,13:1

uv run --frozen pi5servo move 12 center \
  --sleep 1 \
  --backend hardware_pwm \
  --pin-channel-map 12:0,13:1
```

Pass if calibration completes, the servo responds only as expected, and the
center command stops it safely. Press `Ctrl+C` and cut servo power if needed.

Current status: **partial pass**. The safe electrical path is verified, but
real movement and abort testing are intentionally blocked until an emergency
disconnect is installed.

## 3. `pi5disp` manual test

This library controls the ST7789V display through SPI. SPI is the fast display
connection; GPIO14, GPIO15, and GPIO16 are used for display control and the
backlight.

### Step 1: Check the connection

```bash
cd /home/rogerchang/NinjaRobotPi5/pi5disp
ls -l /dev/spidev0.0
uv run --frozen pi5disp info
```

Expected result: the SPI device exists and `info` reports that the display is
connected.

### Step 2: Test visible output

These commands turn on the display and backlight:

```bash
uv run --frozen pi5disp brightness 50
uv run --frozen pi5disp clear
uv run --frozen pi5disp text "NinjaRobot Pi5"
uv run --frozen pi5disp text "Scrolling test" --scroll --duration 5
uv run --frozen pi5disp demo --num-balls 3 --fps 10 --duration 5
```

Pass if:

- Text is readable and correctly oriented.
- The scrolling text moves smoothly.
- The animation has no corrupted areas or long flickers.
- Brightness visibly changes.

### Step 3: Safe rollback

Always finish the display test with:

```bash
uv run --frozen pi5disp clear
uv run --frozen pi5disp brightness 0
```

Current status: **partial pass**. The command paths passed, but an operator
must still confirm that the physical screen looks correct.

## 4. `pi5camera` manual test

### Step 1: Confirm that the camera is visible

```bash
cd /home/rogerchang/NinjaRobotPi5/pi5camera
rpicam-hello --list-cameras
uv run --frozen pi5camera doctor
uv run --frozen pi5camera status
```

Expected result: an OV5647 camera appears, and doctor reports that the camera
and local face-recognition support are ready.

### Step 2: Take one photo

```bash
uv run --frozen pi5camera capture --output /tmp/pi5camera-test.jpg
file /tmp/pi5camera-test.jpg
```

Pass if capture exits without a traceback and the file command identifies a
valid JPEG photo. Open the image and confirm it has the expected orientation.

### Step 3: Remove the test photo

```bash
rm -f /tmp/pi5camera-test.jpg
```

Current status: **pass**. Camera doctor passed during this audit and previous
testing produced a verified 1280 by 720 RGB JPEG. Face enrollment was not
tested because it was intentionally excluded.

## 5. `pi5mic` manual test

The microphone library needs the validated user configuration file. Without
the `-C` option below, the tool uses an empty local configuration and may say
that `whisper-cli` is missing even though it is installed.

### Step 1: Check the microphone and local speech-to-text setup

```bash
cd /home/rogerchang/NinjaRobotPi5/pi5mic

uv run --frozen pi5mic \
  -C /home/rogerchang/.config/pi5mic/mic.json \
  devices

uv run --frozen pi5mic \
  -C /home/rogerchang/.config/pi5mic/mic.json \
  doctor
```

Expected result: the USB PnP Sound Device is listed. Doctor should pass; its
warning about automatically using two Whisper threads is acceptable.

### Step 2: Record, listen, and transcribe

Speak a short sentence such as “NinjaRobot microphone test” while recording:

```bash
uv run --frozen pi5mic \
  -C /home/rogerchang/.config/pi5mic/mic.json \
  record --duration 5 --output /tmp/pi5mic-test.wav

aplay /tmp/pi5mic-test.wav

uv run --frozen pi5mic \
  -C /home/rogerchang/.config/pi5mic/mic.json \
  transcribe --backend whisper_cpp /tmp/pi5mic-test.wav
```

Pass if the recording is non-silent, playback is understandable, and the
local Whisper speech-to-text program prints a recognizable version of your
sentence.

### Step 3: Remove the recording

```bash
rm -f /tmp/pi5mic-test.wav
```

Current status: **pass for standalone use**. OpenClaw integration was not
tested and is outside this audit.

## 6. `pi5vl53l0x` manual test

Before testing, power off the Pi, remove any protective film from the sensor,
clean its optical window, and place a flat matte target about 100 to 200 mm
away. The sensor uses 3.3 V logic. Do not use 5 V on its signal pins.

### Step 1: Confirm I2C communication

```bash
cd /home/rogerchang/NinjaRobotPi5/pi5vl53l0x
i2cdetect -y 1
```

Expected result: `29` appears in the scan. This proves that the Pi can talk to
the sensor, but it does not prove that distance measurements are valid.

### Step 2: Take readings

```bash
uv run --frozen pi5vl53l0x status
uv run --frozen pi5vl53l0x test
uv run --frozen pi5vl53l0x get --count 5 --interval 0.5
```

Pass only if all readings are valid and reasonably close to the real target
distance. `8191 mm` is the sensor's out-of-range error value. It is a failure,
not a real distance.

### Step 3: Calibrate only after valid readings

Do **not** run calibration while any reading is invalid. When every test
reading is valid, place a target at a measured 200 mm and run:

```bash
uv run --frozen pi5vl53l0x calibrate --distance 200 --count 10
```

Current status: **failed live-ranging test**. The current device identifies
correctly and initializes, but it still returns `8191 mm`. Cold-power-cycle
the sensor, recheck wiring and target alignment, and test a replacement sensor
module before changing more software.

## Known software follow-up: `pi5servo` lockfile

`pi5servo/pyproject.toml` allows Python 3.11 through 3.13, while its `uv.lock`
file is limited to Python 3.11 through 3.12. Therefore this command currently
fails:

```bash
cd /home/rogerchang/NinjaRobotPi5/pi5servo
uv lock --check
```

Ordinary `uv run` may update `uv.lock`, which violates the managed-driver
provenance rule. Use `uv run --frozen` until a separately approved repair
updates the lockfile and its authorization record.

## Final pass/fail checklist

- [x] All six library test suites pass.
- [x] All six library compile, lint, and formatting checks pass.
- [x] Managed-driver provenance passes.
- [x] I2C, SPI, camera, USB microphone, and non-moving servo interfaces are
  detected.
- [x] Camera capture and standalone microphone workflow have passed.
- [ ] A person confirms the buzzer is audible.
- [ ] A person confirms the display looks correct.
- [ ] Servo movement is tested with a safe emergency power disconnect.
- [ ] The VL53L0X returns valid distances instead of `8191 mm`.
- [ ] The `pi5servo` lockfile mismatch is repaired and authorized.

## Recommended next steps

1. Install or make accessible a servo-power emergency disconnect, then perform
   the one-servo calibration test.
2. Diagnose the VL53L0X optical path or replace the sensor module.
3. Record the buzzer and display operator confirmations.
4. Create an approved managed-driver repair for the `pi5servo` lockfile
   mismatch.
5. Rerun the provenance command after every future driver change.

