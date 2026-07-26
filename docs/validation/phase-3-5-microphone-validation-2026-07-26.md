# Phase 3.5 microphone validation report

Date: 2026-07-26

Hardware accessed during implementation: USB/PortAudio enumeration only

Physical Raspberry Pi result: **PASS — OPERATOR CONFIRMED ALL TESTS**

## 1. Scope of validation

This report covers `microphone.status`, privacy-classified
`microphone.capture`, USB input discovery, supported sample-rate fallback,
exclusive microphone ownership, bounded WAV recording, default deletion,
explicit private retention, path confinement, no overwrite, timeout,
cancellation, cleanup, and durable action replay.

WAV is an uncompressed audio-file format. PortAudio is the native audio library
used by Python to open the USB microphone.

Phase 3.5 does not implement transcription, wake-word detection, always-on
listening, Gemini, OpenClaw, or agent-controlled voice input. Those features
remain deferred to Phase 8.

Automated result: **PASS**

- Root/V4 tests: 109 passed.
- Focused microphone, configuration, and CLI tests: 36 passed.
- Managed-library tests: 449 passed, with one inherited `audioop` deprecation
  warning from `pi5mic`.
- Strict mypy type checking passed for 23 V4 source files.
- Root and all six managed libraries passed Ruff lint and format checks.
- Driver provenance remained at 222 tracked files and 23 authorized repairs.
- No managed `pi5*` file changed.
- Safe real health and status passed without recording audio.

## 2. Safety notes

A microphone can capture conversations, names, addresses, passwords, or other
private information. Tell everyone nearby and obtain their consent before
running a real capture.

Real recording requires both:

```text
--real --confirm-microphone
```

Audio is deleted after capture by default. Saving a WAV requires the separate
`--retain` option. Retained audio is restricted to:

```text
~/.local/share/ninjarobot_pi5/microphone
```

Retained files use permission `600`, meaning only the owner can read or change
them. Do not publish or upload the test file. This phase makes no cloud request
and performs no transcription.

The microphone is not an actuator and cannot move the robot. No buzzer,
display, servo, camera, or distance-sensor operation belongs in this checklist.

## 3. Safe smoke tests

These commands generate synthetic silence. They do not import `pi5mic`, open
PortAudio, or access the physical microphone:

```bash
cd /home/rogerchang/NinjaRobotPi5
uv sync --frozen

PHASE35_SIM_LEDGER="$(mktemp /tmp/ninjarobot-phase35-sim-XXXXXX.sqlite3)"

uv run --frozen ninjarobot_pi5_cli capabilities

uv run --frozen ninjarobot_pi5_cli microphone health \
  --ledger "$PHASE35_SIM_LEDGER"

uv run --frozen ninjarobot_pi5_cli microphone status \
  --ledger "$PHASE35_SIM_LEDGER"

uv run --frozen ninjarobot_pi5_cli microphone capture \
  --ledger "$PHASE35_SIM_LEDGER" \
  --duration 0.25 \
  --action-id phase35-sim-transient-1 \
  --idempotency-key phase35-sim-transient-key-1
```

Expected:

- capabilities include `microphone.status` with risk `read_only`
- capabilities include `microphone.capture` with risk `privacy`
- capture requires confirmation and owns the `microphone` resource
- health reports `ready`
- status says `"simulated": true` and retention is false
- capture succeeds with WAV metadata, `"retained": false`, and `"path": null`
- no WAV remains under `data/simulated-microphone`

Test explicit simulated retention:

```bash
uv run --frozen ninjarobot_pi5_cli microphone capture \
  --ledger "$PHASE35_SIM_LEDGER" \
  --duration 0.25 \
  --retain \
  --filename phase35-simulated.wav

SIM_WAV="data/simulated-microphone/phase35-simulated.wav"
file "$SIM_WAV"
stat -c '%a %s %n' "$SIM_WAV"
uv run --frozen python -c \
  "import wave; w=wave.open('$SIM_WAV'); print(w.getnchannels(), w.getframerate(), w.getnframes()); w.close()"
```

Expected: `file` identifies WAV audio, permission is `600`, the channel count
is `1`, and frame count is greater than zero. Then delete only this synthetic
file:

```bash
rm -- "$SIM_WAV"
```

That deletion is permanent unless the file was backed up.

## 4. Communication/interface tests

Install the operating-system and locked project dependencies:

```bash
cd /home/rogerchang/NinjaRobotPi5
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev
uv sync --frozen --extra hardware
```

List the ALSA device. ALSA is Linux's audio device layer:

```bash
arecord -l
```

Expected current hardware:

```text
card 0: Device [USB PnP Sound Device], device 0: USB Audio
```

Create a fresh ledger:

```bash
unset PHASE35_LEDGER
PHASE35_LEDGER="$(mktemp /tmp/ninjarobot-phase35-real-XXXXXX.sqlite3)"
```

Check V4 without recording:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli microphone health \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE35_LEDGER"

uv run --frozen --extra hardware ninjarobot_pi5_cli microphone status \
  --real \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE35_LEDGER"
```

Expected:

- health is `ready`
- status reports `driver_available: true`
- selected device contains `USB PnP Sound Device`
- requested rate is `16000`
- actual rate is `44100`
- the warning clearly explains the supported-rate fallback
- channels are `1`
- retention is false
- `"simulated": false`

The 44.1 kHz result is expected for this USB device and is not a failure.

Verify the consent gate before any recording:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli microphone capture \
  --real \
  --duration 1 \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE35_LEDGER"
```

Expected: the CLI requires `--confirm-microphone`. No recording occurs.

Tell everyone nearby and obtain consent. Then take one three-second transient
recording:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli microphone capture \
  --real \
  --confirm-microphone \
  --duration 3 \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE35_LEDGER" \
  --action-id phase35-real-transient-1 \
  --idempotency-key phase35-real-transient-key-1
```

Expected: success, 44.1 kHz mono WAV metadata, positive frames and bytes, a
64-character SHA-256 fingerprint, `"retained": false`, and `"path": null`.
SHA-256 is a file fingerprint.

Repeat that exact command once. Expected: V4 returns the same stored result and
timestamps without recording again.

Take one explicitly retained recording:

```bash
uv run --frozen --extra hardware ninjarobot_pi5_cli microphone capture \
  --real \
  --confirm-microphone \
  --duration 3 \
  --retain \
  --filename phase35-physical.wav \
  --config config/ninjarobot_pi5.toml.example \
  --ledger "$PHASE35_LEDGER" \
  --action-id phase35-real-retained-1 \
  --idempotency-key phase35-real-retained-key-1

MIC_WAV="$HOME/.local/share/ninjarobot_pi5/microphone/phase35-physical.wav"
file "$MIC_WAV"
stat -c '%a %s %n' "$MIC_WAV"
uv run --frozen python -c \
  "import wave; w=wave.open('$MIC_WAV'); print(w.getnchannels(), w.getframerate(), w.getnframes()); w.close()"
```

Expected: permission `600`, one channel, 44.1 kHz, 132,300 frames for three
seconds, and a positive file size.

Repeat the retained command with a new action ID and idempotency key but the
same filename. Expected: `MICROPHONE_OUTPUT_EXISTS`; the original file remains
unchanged.

After inspection, permanently delete the physical test audio:

```bash
rm -- "$MIC_WAV"
```

Confirm that no temporary directory remains:

```bash
find "$HOME/.local/share/ninjarobot_pi5/microphone" \
  -maxdepth 1 -type d -name '.capture-*' -print
```

Expected: no output.

## 5. Actuator-moving tests

Not applicable. A microphone is an input device and this phase does not move
or energize any robot actuator.

No power-risk test is required. Do not modify unrelated servo, I2C, SPI, camera,
or buzzer wiring during this checklist.

## 6. Expected outcomes

- Simulation never opens the microphone.
- Health and status never record audio.
- Real capture is blocked without explicit consent confirmation.
- Recording duration is bounded by configuration.
- The selected USB device is reported by stable name.
- Unsupported 16 kHz input falls back transparently to 44.1 kHz.
- Default capture leaves no audio behind.
- Retention occurs only with `--retain`.
- Retained names cannot leave the configured directory.
- Existing retained files are never overwritten.
- Retained files use permission `600`.
- Temporary audio is removed after success, failure, timeout, or cancellation.
- Two recordings cannot own the microphone simultaneously.
- Replaying a completed action returns the ledger result without recording.
- No OpenClaw, Gemini, transcription, wake-word, or transport module is loaded.
- No other robot device is accessed.

## 7. Pass/fail checklist

The operator reported that every Phase 3.5 test passed:

- [x] Safe simulated health, status, and transient capture pass.
- [x] Simulated retained WAV is valid, permission `600`, and then deleted.
- [x] PortAudio packages are installed.
- [x] `arecord -l` identifies USB PnP Sound Device at card 0/device 0.
- [x] Real microphone health is ready without recording.
- [x] Real status selects USB PnP Sound Device.
- [x] Status reports requested 16 kHz and actual 44.1 kHz.
- [x] Missing `--confirm-microphone` blocks real capture.
- [x] Everyone nearby consents before real recording.
- [x] Non-retained real capture succeeds and leaves no WAV.
- [x] Replaying the transient action returns the stored result without recording.
- [x] Retained real WAV is valid 44.1 kHz mono audio.
- [x] Retained file permission is `600`.
- [x] Reusing the retained filename is rejected without changing the file.
- [x] Retained physical test audio is deleted after inspection.
- [x] No `.capture-*` directory remains.
- [x] No servo, buzzer, display, distance, or camera action occurs.

## 8. Rollback steps

1. Stop issuing microphone commands. A running bounded capture can be
   interrupted with `Ctrl+C`; V4 waits for stream cleanup.
2. Delete only the explicitly retained test audio if it remains:

   ```bash
   rm -- "$HOME/.local/share/ninjarobot_pi5/microphone/phase35-physical.wav"
   ```

   This deletion is permanent unless the audio was backed up.
3. To disable V4 microphone access without uninstalling dependencies, set:

   ```toml
   [hardware.microphone]
   enabled = false
   ```

4. Do not delete the managed `pi5mic` library or edit its source as rollback.
5. Recheck provenance:

   ```bash
   uv run --frozen python scripts/verify_immutable_drivers.py
   ```

Phase 3 is complete. Phase 4 may begin under the approved implementation plan.
