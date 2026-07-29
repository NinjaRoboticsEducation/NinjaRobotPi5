# Phase 5 Recovery, Idle, and AI Camera Raspberry Pi Validation

## 1. Scope of validation

This checklist verifies:

- web X Emergency Stop followed by web Y Resume
- web X Emergency Stop followed by terminal-chat `/resume`
- distance, camera, and microphone restart in the same agent service
- Greeting and Celebrate returning to looping Idle
- one-shot AI camera permission from `/camera` and **AI camera**
- the `3`, `2`, `1` countdown and animated camera icon
- temporary preview cleanup and transcript redaction

MCP (Model Context Protocol) search and Ollama model quality are outside this
checklist.

## 2. Safety notes

- Complete the non-moving checks before testing Celebrate.
- Raise both drive wheels before Celebrate. Celebrate can energize both
  continuous-rotation servos.
- Keep the web X Emergency Stop button visible.
- Keep hands, wires, and clothing away from the raised wheels.
- Do not unplug I2C, SPI, camera, microphone, or servo wiring while power is on.
- AI camera preview takes a real photograph. Point the camera only at a scene
  everyone present has agreed may be photographed.
- `/resume` does not arm AI motion. This is intentional.

## 3. Safe smoke tests

### 3.1 Install the updated source

From the project root:

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
git pull
uv sync --frozen --extra hardware
source .venv/bin/activate
```

Set the configuration path:

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
```

Stop an older service if one is running:

```bash
uv run --frozen ninjarobot-agent service stop
```

If it reports that no service is running, continue.

Start the real service and web interface:

```bash
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start --real

uv run --frozen ninjarobot-agent web start
```

Expected result:

- the service starts without an exception
- startup Greeting completes
- the display changes to looping Idle
- the web command prints `https://ninjarobotpi5.local:8443/`

### 3.2 Check service health

```bash
uv run --frozen ninjarobot-agent service status
```

Expected result: the provider and IDE tool provider are available. Fix any
reported camera, microphone, display, servo, or distance-sensor problem before
testing Resume.

## 4. Communication and interface tests

### 4.1 Test web Emergency Stop and Y Resume

1. Open `https://ninjarobotpi5.local:8443/`.
2. Press X.
3. Confirm that the red Emergency Stop sign remains on the display.
4. Press Y.
5. Approve the browser confirmation.

Expected result:

- X stops servo output, sensors, and the buzzer
- Y does not report `distance adapter is closed`
- Y does not report `The capability adapter reported an unexpected failure`
- distance, camera, and microphone health checks pass
- the display returns to looping Idle
- **Arm AI motion** remains off

If Resume fails, open **Live Activity** and correct the named unhealthy module.
The Emergency Stop state should remain active after a failed health check.

### 4.2 Test terminal `/resume`

Press X again, then open the interactive terminal chat:

```bash
uv run --frozen ninjarobot-agent
```

Enter:

```text
/help
/resume
```

Type `RESUME` when prompted.

Expected result:

- `/help` lists `/resume` and `/camera`
- recovery happens without an Ollama model turn
- Idle returns
- AI motion remains disarmed

Enter `/exit` to leave the terminal without stopping the service.

### 4.3 Test Greeting returning to Idle

1. Press A in the web interface.
2. Watch the complete Greeting face, sound, and text sequence.
3. Wait two seconds after it finishes.

Expected result: the display does not remain on the last Greeting frame. It
starts the looping Idle face.

### 4.4 Test one-shot AI camera

First verify that camera permission is required:

1. Make sure **AI camera** does not say **AI camera ready**.
2. Ask: `Use the robot camera to take one temporary photo now.`

Expected result: the model cannot execute `robot.camera.preview` without the
one-shot grant.

Now grant and use one photo:

1. Press **AI camera**.
2. Approve the confirmation.
3. Confirm the button says **AI camera ready**.
4. Ask: `Use robot.camera.preview now and take one temporary photo.`

Expected result:

- the robot display clearly shows `3`, then `2`, then `1`
- an animated camera icon loops while capture is active
- the photograph appears in the temporary browser preview
- **AI camera ready** turns off after successful preview delivery
- the response completes and the display returns to looping Idle
- the preview closes automatically after about 15 seconds

Ask for another photo without pressing **AI camera** again.

Expected result: the second capture is refused. Pressing **AI camera** grants
exactly one new preview.

You can also grant from terminal chat:

```text
/camera
```

A failed camera attempt keeps the grant ready. A successful preview consumes
it.

### 4.5 Check that preview bytes were not retained

Stop the service so the SQLite (local database) files are fully flushed:

```bash
uv run --frozen ninjarobot-agent service stop
```

Search the normal state and transcript directories:

```bash
uv run python - <<'PY'
from pathlib import Path

roots = (
    Path.home() / ".local/state/ninjarobot_pi5",
    Path.home() / ".local/share/ninjarobot_pi5",
)
matches = []
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if path.is_file() and b"jpeg_base64" in path.read_bytes():
            matches.append(path)
if matches:
    print("FAIL: preview data was found in retained state")
    for path in matches:
        print(path)
else:
    print("PASS: no preview data was found in retained state")
PY
```

Expected result: `PASS`. The camera directory may contain older photographs
that you explicitly retained in earlier tests, but this AI preview must not
create a new retained photograph.

Restart the service before continuing:

```bash
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start --real

uv run --frozen ninjarobot-agent web start
```

## 5. Actuator-moving tests

### 5.1 Test Celebrate returning to Idle

This test moves the servos.

1. Raise both wheels so neither touches the floor.
2. Keep X immediately accessible.
3. Press B.
4. Allow Celebrate to finish normally.
5. Wait two seconds.

Expected result:

- the expected face, melody, and short servo sequence run
- servo output stops at completion
- the display changes from the last Celebrate frame to looping Idle

Press X immediately if motion is unexpected. Then use Y only after checking
the robot and confirming all modules are healthy.

## 6. Expected outcomes

- Level 2 is recoverable without restarting the agent service.
- Terminal `/resume` and web Y use the same health-checked IDE boundary.
- Normal foreground work always returns to Idle.
- Emergency Stop presentation is not replaced by Idle before Resume.
- AI camera access is separate from AI motion permission.
- One successful temporary preview consumes exactly one camera grant.
- A failed preview does not consume the grant.
- Preview JPEG bytes remain live-only and are not stored in transcripts or
  durable events.

## 7. Pass/fail checklist

| Check | Pass/Fail | Notes |
|---|---|---|
| Startup Greeting returns to Idle |  |  |
| Web X then Y resumes all modules |  |  |
| Terminal `/resume` resumes all modules |  |  |
| Resume leaves AI motion disarmed |  |  |
| Web A Greeting returns to Idle |  |  |
| AI camera is refused without a grant |  |  |
| `/camera` is listed and grants one preview |  |  |
| Web AI camera button grants one preview |  |  |
| Display shows `3`, `2`, `1` |  |  |
| Camera icon loops during capture |  |  |
| Successful preview consumes the grant |  |  |
| Second ungranted capture is refused |  |  |
| Preview data is absent from retained state |  |  |
| Raised-wheel Celebrate returns to Idle |  |  |
| Chrome mobile flow passes |  |  |
| Safari mobile flow passes |  |  |

## 8. Rollback steps

1. Press X if any actuator is moving unexpectedly.
2. Stop the service:

   ```bash
   uv run --frozen ninjarobot-agent service stop
   ```

3. Return to the previous known-good Git commit or branch.
4. Reinstall that version:

   ```bash
   uv sync --frozen --extra hardware
   ```

5. Start in simulation first:

   ```bash
   uv run --frozen ninjarobot-agent service start
   uv run --frozen ninjarobot-agent web start
   ```

6. Repeat the non-moving smoke tests before starting the real service.
