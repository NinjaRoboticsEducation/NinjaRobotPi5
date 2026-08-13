# Phase 8.2 Raspberry Pi Voice-Input Validation

Status: software and offline ONNX model-load pass; live microphone and physical
acceptance pending operator execution.

## 1. Scope of validation

Validate packaged offline wake assets, one-owner USB microphone behavior,
“Hey Ninja” detection, four transcription locales, text/web fallback, motion
authorization, cleanup, and long-running resource stability on Raspberry Pi 5.

## 2. Safety notes

- Tell everyone nearby before enabling the always-on microphone.
- Do not use private speech in the test area; transcripts follow the configured
  seven-day conversation retention policy.
- Keep AI motion disarmed for all smoke and microphone tests.
- For the actuator test, raise the wheels, clear the robot's full movement
  envelope, use stable power, and keep an accessible power cutoff.
- Stop standalone `pi5mic`, ALSA, browser capture, or recording programs before
  starting the agent so there is one microphone owner.

## 3. Safe smoke tests

From the repository root:

```bash
uv sync --frozen --extra hardware
uv run python scripts/verify_immutable_drivers.py
uv run --frozen pytest -q \
  ninjarobot_pi5_ide/tests/test_voice_input.py \
  ninjarobot_pi5_ide/tests/test_microphone.py \
  ninjarobot_pi5_agent/tests/test_voice_service.py
uv run --frozen --extra hardware python - <<'PY'
from pathlib import Path
from ninjarobot_pi5_ide.microphone import build_managed_wake_detector

assets = Path("ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/assets").resolve()
detector = build_managed_wake_detector(
    model_path=assets / "hey_Ninja.onnx",
    threshold=0.5,
    vad_threshold=0.3,
    enable_noise_suppression=False,
    inference_framework="onnx",
    runtime_asset_directory=assets / "openwakeword",
)
print(detector.sample_rate, detector.frame_length)
detector.close()
PY
```

Expected: tests pass; driver verification passes; the last command prints
`16000 1280` and performs no network download or microphone access.

## 4. Communication/interface tests

Start the real service using the normal configured command, then open terminal
chat and run:

```text
/voice input status
/voice input on
/voice input status
```

Expected: state progresses to `listening`; the web **VOICE INPUT** status agrees.
The enable operation itself must not return a successful `starting` state. If
the stream cannot become ready within 10 seconds, expected behavior is a
bounded failure, a closed partial stream, and `enabled: false` rather than a
stuck background task.
Say “Hey Ninja”, then a harmless question. Expected: one transcript and one
reply appear on the web interface, the reply is presented normally, and the
listener returns to `listening` after cooldown.

Repeat with `language` set in the private configuration to `en`, `ja`, `zh-TW`,
and `zh-CN`, restarting the service after each config change. Confirm early
completion after speech followed by silence. Run **RECORD ONCE** while listening;
expected: the listener reports paused, the manual transcript completes, and
listening resumes without PortAudio “device busy” errors.

Run `/voice input off`. Expected: the stream closes, voice motion is revoked,
and ordinary terminal/web chat and manual recording remain available.

For a soak test, leave voice enabled for at least two hours with ordinary room
noise and record CPU, RSS, wake-hit count, and any false triggers every 15
minutes. Expected: one listener task/stream, bounded memory, no accumulating
temporary WAV files, no repeated unsolicited dispatch, and no loss of other
hardware ownership.

## 5. Actuator-moving tests

This section can energize servos. Raise the wheels first.

1. Enable voice, leave AI motion disarmed, and request a one-second movement.
   Expected: policy denial and no movement.
2. Type `/arm`, confirm `ARM`, then issue the same request after “Hey Ninja”.
   Expected: one bounded movement through the existing IDE path, followed by
   Idle; it must not execute twice.
3. Disable voice, re-enable it, and repeat without arming. Expected: movement is
   denied because voice disablement cleared authorization.
4. Arm from the web, disconnect that controlling browser, then issue a voice
   movement request. Expected: the lease-scoped voice grant is revoked and the
   robot does not move.

## 6. Expected outcomes

- Wake/model processing is fully local and starts without downloading assets.
- Exactly one microphone stream exists; manual operations pause and restore it.
- No background audio or temporary command WAV remains on disk.
- Each wake cycle dispatches no more than one transcript.
- Text chat stays usable after any detector, microphone, or transcription error.
- Motion occurs only with the existing explicit arm and stops/revokes through
  all existing safety paths.

## 7. Pass/fail checklist

- [ ] Immutable-driver and focused software checks pass.
- [ ] Offline ONNX model load prints `16000 1280`.
- [ ] Voice reaches `listening` without a network download.
- [ ] Busy/missing/stalled microphone fails within the startup bound and can be re-enabled after correction.
- [ ] Positive wake, negative speech, silence, and noise trials are recorded.
- [ ] All four transcription locales produce acceptable text.
- [ ] Manual recording never competes with the listener.
- [ ] Temporary command clips are deleted.
- [ ] Two-hour soak has stable resource use and acceptable false triggers.
- [ ] Disarmed voice movement is denied.
- [ ] Armed voice movement executes exactly once with wheels raised.
- [ ] Disable, disconnect, model switch, stop, and restart revoke voice motion.

Any failure in microphone ownership, duplicate dispatch, safety revocation, or
unexpected actuator movement is a Phase 8 release blocker.

## 8. Rollback steps

```text
/voice input off
/disarm
```

Then stop the agent service through the existing Interactive Tool. Keep the
private config and logs for diagnosis. If the new listener prevents startup,
set `[voice_input].enabled = false`, validate the configuration, and restart;
terminal and web text chat should operate without voice input. Do not delete
the safety-state file or modify managed-driver hashes as a workaround.
