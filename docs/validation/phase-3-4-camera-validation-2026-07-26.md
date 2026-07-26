# Phase 3.4 camera validation report

Date: 2026-07-26

Hardware accessed during implementation: No

Physical Raspberry Pi result: **PENDING OPERATOR TEST**

## 1. Scope of validation

This report covers the V4 camera environment, the read-only `camera.status`
capability, the privacy-classified `camera.capture` capability, simulation,
explicit real-camera confirmation, private file retention, path confinement,
timeouts, cancellation, cleanup, action-ledger behavior, and restart.

The real path uses the managed `pi5camera` library and Raspberry Pi OS
Picamera2 at 1280×720. Picamera2 is the Raspberry Pi Python camera interface.
The observed OV5647 module is fixed-focus, meaning software cannot change its
focus, so V4 configures `autofocus_mode = "none"`.

Face recognition, face enrollment, video, streaming, and agent-controlled
camera access are not part of Phase 3.4.

Automated result: **PASS**

- Root/V4 tests: 92 passed.
- Focused camera, configuration, and CLI tests: 31 passed.
- Managed-library tests: 449 passed, with one inherited `audioop` deprecation
  warning from `pi5mic`.
- Strict mypy type checking passed for 22 V4 source files.
- Driver provenance remained at 222 tracked files and 23 authorized repairs.
- No managed `pi5*` file changed.

## 2. Safety notes

A camera image can contain faces, documents, screens, addresses, or other
private information. Tell everyone nearby before running a real capture and
capture only with their consent.

Real capture requires both `--real` and `--confirm-camera`. Images are deleted
after capture by default. Saving an image requires the separate `--retain`
option. Retained files are restricted to:

```text
~/.local/share/ninjarobot_pi5/camera
```

V4 rejects filenames containing directory components and never overwrites an
existing retained image. Retained files use owner-only permissions. Owner-only
means the account that created the file can read and write it, while other
ordinary accounts cannot.

Power down the Raspberry Pi before connecting, disconnecting, or reversing the
CSI ribbon cable. CSI is the flat camera connection on the Raspberry Pi. This
phase does not move a servo, sound the buzzer, write the display, read the
distance sensor, or record audio.

## 3. Safe smoke tests

These commands use the synthetic camera and do not open Picamera2 or the
physical camera:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen

PHASE34_LEDGER="$(mktemp /tmp/ninjarobot-phase34-XXXXXX.sqlite3)"
echo "$PHASE34_LEDGER"

uv run --frozen ninjarobot_pi5_cli capabilities
uv run --frozen ninjarobot_pi5_cli camera health \
  --ledger "$PHASE34_LEDGER"
uv run --frozen ninjarobot_pi5_cli camera status \
  --ledger "$PHASE34_LEDGER"
uv run --frozen ninjarobot_pi5_cli camera capture \
  --ledger "$PHASE34_LEDGER" \
  --action-id phase34-sim-capture-1 \
  --idempotency-key phase34-sim-capture-key-1
```

Expected:

- capabilities include `camera.status` with risk `read_only`
- capabilities include `camera.capture` with risk `privacy`
- `camera.capture` requires confirmation and owns the `camera` resource
- health reports `ready`
- status says `"retain_media_by_default": false`
- capture says `"simulated": true`, `"retained": false`, and `"path": null`
- capture reports `retry_safety: unsafe` because taking another photograph
  would repeat a privacy-sensitive action
- no JPEG remains under `data/simulated-camera`

Test explicit simulated retention:

```bash
uv run --frozen ninjarobot_pi5_cli camera capture \
  --ledger "$PHASE34_LEDGER" \
  --retain \
  --filename phase34-simulated.jpg

file data/simulated-camera/phase34-simulated.jpg
stat -c '%a %n' data/simulated-camera/phase34-simulated.jpg
```

Expected: `file` identifies a JPEG and `stat` reports permission `600`.
After inspecting it, delete only this synthetic test file:

```bash
rm -- data/simulated-camera/phase34-simulated.jpg
```

That deletion is permanent unless the file was backed up.

## 4. Communication/interface tests

### Prepare the Picamera2 environment

The ordinary project `.venv` may use a downloaded Python that cannot see the
Raspberry Pi OS camera packages. Run the provided bootstrap:

```bash
cd /home/rogerchang/NinjaRobotPi5
./scripts/bootstrap-rpi-camera-workspace.sh
source .venv/bin/activate
```

If `python3-picamera2` and `python3-libcamera` are already installed:

```bash
./scripts/bootstrap-rpi-camera-workspace.sh --skip-apt
source .venv/bin/activate
```

The script preserves an incompatible old environment beside the project as
`NinjaRobotPi5.venv-before-camera-<timestamp>`. Confirm imports and detection:

```bash
python -c \
  "import libcamera, picamera2; print('Picamera2:', picamera2.__file__)"
rpicam-hello --list-cameras
```

Expected: Picamera2 imports from Raspberry Pi OS and at least one camera is
listed. For the current hardware, the list should identify an OV5647 camera.

### Check V4 without taking a photograph

```bash
PHASE34_LEDGER="${PHASE34_LEDGER:-$(mktemp /tmp/ninjarobot-phase34-XXXXXX.sqlite3)}"

uv run --frozen --extra hardware ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example

uv run --frozen --extra hardware ninjarobot_pi5_cli camera health \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE34_LEDGER"

uv run --frozen --extra hardware ninjarobot_pi5_cli camera status \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE34_LEDGER"
```

Expected: health is `ready`; status says 1280×720, autofocus `none`,
retention false, and `"simulated": false`. These commands import the backend
and check the private directory but do not take a photograph.

### Verify the consent gate

Do not include `--confirm-camera` in this first command:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli camera capture \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE34_LEDGER"
```

Expected: the CLI exits with an error saying `--confirm-camera` is required.
No photograph is taken.

### Take one non-retained photograph

Tell everyone nearby and obtain consent, then run:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli camera capture \
  --real \
  --confirm-camera \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE34_LEDGER" \
  --action-id phase34-real-transient-1 \
  --idempotency-key phase34-real-transient-key-1
```

Expected: the result succeeds with `"simulated": false`,
`"retained": false`, `"path": null`, a positive byte count, and a 64-character
SHA-256 value. SHA-256 is a file fingerprint used to distinguish captured
content. No photograph remains after the action.

### Take and inspect one explicitly retained photograph

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli camera capture \
  --real \
  --confirm-camera \
  --retain \
  --filename phase34-physical.jpg \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE34_LEDGER" \
  --action-id phase34-real-retained-1 \
  --idempotency-key phase34-real-retained-key-1

CAMERA_FILE="$HOME/.local/share/ninjarobot_pi5/camera/phase34-physical.jpg"
file "$CAMERA_FILE"
stat -c '%a %s %n' "$CAMERA_FILE"
python -c \
  "from PIL import Image; im=Image.open('$CAMERA_FILE'); print(im.format, im.size)"
```

Expected: the result path equals `$CAMERA_FILE`, permissions are `600`, file
size is greater than zero, and Pillow reports `JPEG (1280, 720)`. Inspect the
image visually and confirm that it is correctly exposed, oriented, and
focused before checking the item in Section 7.

Test no-overwrite behavior by repeating the command with a new action ID but
the same filename. Expected: `CAMERA_OUTPUT_EXISTS` and the original file is
unchanged.

After inspection, permanently delete the test photograph unless you have an
explicit reason and consent to retain it:

```bash
rm -- "$CAMERA_FILE"
```

## 5. Actuator-moving tests

Not applicable. A camera is not an actuator and this phase does not move any
robot component.

Power-risk testing is limited to the CSI ribbon. Do not alter the ribbon while
the Raspberry Pi is powered. No external power supply, PWM output, motor, or
servo-power rail is used by this phase.

## 6. Expected outcomes

- Simulation never imports Picamera2 or opens the CSI camera.
- Health and status never take a photograph.
- Real capture is rejected without explicit consent confirmation.
- Default capture leaves no image behind.
- Retention occurs only when `--retain` is supplied.
- Retained names cannot escape the configured directory.
- Existing retained files are never overwritten.
- Temporary and partial files are removed after success, failure, timeout, or
  cancellation.
- Captures are serialized; two actions cannot own the camera simultaneously.
- Repeating the same completed action ID returns the stored result without
  taking another photograph.
- The managed camera backend stops and closes after each real capture.
- No other robot device is accessed.

## 7. Pass/fail checklist

- [ ] Safe simulated health, status, and transient capture pass.
- [ ] Simulated retained JPEG is valid, permission `600`, and then deleted.
- [ ] Camera bootstrap completes without deleting the previous `.venv`.
- [ ] Picamera2 and libcamera import inside the root `.venv`.
- [ ] `rpicam-hello --list-cameras` identifies the OV5647.
- [ ] Real camera health passes without taking a photograph.
- [ ] Real status reports 1280×720, autofocus none, and retention false.
- [ ] Missing `--confirm-camera` blocks real capture.
- [ ] Everyone nearby consents before real capture.
- [ ] Non-retained real capture succeeds and leaves no JPEG.
- [ ] Retained real capture is a valid 1280×720 JPEG.
- [ ] Retained file permission is `600`.
- [ ] The retained image looks correctly exposed, oriented, and focused.
- [ ] Reusing the retained filename is rejected without changing the file.
- [ ] The retained physical test image is deleted after inspection.
- [ ] No unexpected camera process or temporary `.capture-*` directory remains.
- [ ] No servo, buzzer, display, distance, or microphone action occurs.

## 8. Rollback steps

1. Stop issuing camera commands. Each one-shot action closes Picamera2 during
   cleanup.
2. Delete only the explicitly retained test image if it still exists:

   ```bash
   rm -- "$HOME/.local/share/ninjarobot_pi5/camera/phase34-physical.jpg"
   ```

   This deletion is permanent unless the photograph was backed up.

3. If the bootstrap replaced an older environment, preserve the new one and
   restore the timestamped backup:

   ```bash
   deactivate 2>/dev/null || true
   mv -- .venv "../NinjaRobotPi5.venv-phase34-rollback"
   mv -- "../NinjaRobotPi5.venv-before-camera-<timestamp>" .venv
   ```

   Replace `<timestamp>` with the exact backup name printed by the bootstrap.

4. Keep `retain_media_by_default = false`. Do not change camera wiring while
   powered.
5. Recheck driver integrity:

   ```bash
   uv run --frozen python scripts/verify_immutable_drivers.py
   ```

Report the command output and the checked Section 7 items before Phase 3.5
microphone integration begins.
