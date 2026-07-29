# Phase 5 Agent and Mobile Web Refinement Validation

Date prepared: 2026-07-29  
Software status: implemented; local software validation required below  
Raspberry Pi status: operator validation required  
Target: Raspberry Pi 5 with 8 GB RAM and active cooling

This checklist validates the refined agent timeout handling, startup Greeting
and Idle behavior, 50 mm obstacle policy, locally trusted HTTPS certificate,
and portrait controller on mobile Chrome and Safari.

Useful terms:

- HTTPS means the encrypted connection between the browser and robot.
- CA means certificate authority. The robot creates its own private local CA
  and exports only its public certificate for the phone to trust.
- LLM means large language model, such as Qwen3:4B.
- Inactivity timeout means the limit used only when the model sends no
  progress at all.
- Controller lease means the temporary exclusive control held by one browser.
- Level 1 stop means servo movement stops and stays locked until Motion Resume.
- Level 2 stop means all movement and active sensor work stop, the buzzer is
  silenced, and the Emergency Stop screen remains visible.

## 1. Scope of validation

This checklist covers:

- the complete software quality gate
- agent responses that need more thinking time
- one startup Greeting followed by a looping silent Idle face
- immediate movement startup without three clear-distance readings
- Level 1 obstacle protection at 50 mm for Forward, Turn Left, and Turn Right
- backward movement with a coverage warning
- the `.local` web address and local CA trust setup
- portrait mobile Chrome and Safari layouts
- D-pad touch handling without text selection
- the hidden Live Activity drawer
- browser speech recognition that fills the input without sending it
- exclusive browser control, refresh recovery, and heartbeat stop

## 2. Safety notes

Complete the non-moving tests before the actuator-moving tests.

1. Raise both wheels clear of the table before starting real movement.
2. Keep fingers, hair, cables, and loose clothing away from both wheels.
3. Keep a second terminal open with this command ready:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen ninjarobot-agent service stop
```

4. Keep the web Emergency Stop button visible during movement tests.
5. Tell everyone nearby before testing the camera or either microphone.
6. Do not expose port 8443 to the internet or configure router port
   forwarding.
7. Stop if the Pi reports undervoltage, a motor stalls, wiring becomes warm,
   or software no longer responds.

The robot does not have an independent physical motor cutoff. If software
cannot stop unsafe movement, disconnect robot power only when you can do so
without reaching into moving parts.

## 3. Safe smoke tests

### 3.1 Update and install the locked environment

```bash
cd "$HOME/NinjaRobotPi5"
git status --short
uv sync --frozen --extra hardware
```

Expected result: installation completes without an error. Do not delete or
overwrite local configuration files shown by `git status`.

### 3.2 Run the complete software gate

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python -m compileall .
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy .
uv run --frozen pytest -q
node --check \
  ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js
python -m json.tool \
  ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/manifest.webmanifest \
  >/dev/null
git diff --check
```

Expected result: every command passes. Immutable-driver verification must
report that all six managed `pi5*` libraries match their recorded baseline and
authorized repairs.

Do not continue to real hardware if this gate fails.

### 3.3 Start the simulated service

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start

uv run --frozen ninjarobot-agent status
```

Expected result: one owner service starts and its status is ready. Starting it
a second time reports that it is already running; it must not create a second
hardware owner.

### 3.4 Check the refined model timeouts

```bash
uv run --frozen ninjarobot-agent chat \
  "Think carefully, then explain in five short steps how to test a Raspberry Pi LED safely."
```

Expected result:

- model activity continues without exposing private reasoning text
- ordinary slow thinking does not trigger the old 90-second timeout
- the complete request may run for up to 600 seconds
- the request fails only if the model sends no activity for 120 seconds or the
  complete 600-second limit is reached

If Ollama itself is unavailable, fix Ollama before treating this as an agent
timeout failure.

### 3.5 Stop the simulated service

```bash
uv run --frozen ninjarobot-agent service stop
```

Expected result: the owner service exits cleanly.

## 4. Communication and interface tests

### 4.1 Check hardware without moving the wheels

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status --real
```

Expected result: the configured display, buzzer, distance sensor, and both
servo calibration records are available. This command must not intentionally
move a wheel.

### 4.2 Start the real service and check robot liveliness

```bash
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start --real

uv run --frozen ninjarobot-agent status
```

Expected result:

1. Greeting runs once.
2. The display shows the Greeting animation and “Nice to meet you”.
3. The configured Greeting melody plays.
4. Greeting completes and changes to the silent looping Idle face.
5. Idle continues until another behavior starts.

Run one non-moving behavior, such as Greeting, from the IDE tool or web
controller. Expected result: it temporarily replaces Idle and Idle returns
after normal completion.

### 4.3 Generate and export the public browser-trust certificate

```bash
uv run --frozen ninjarobot-agent web certificate-status

uv run --frozen ninjarobot-agent web export-ca \
  --output "$HOME/ninjarobotpi5-local-ca.pem"

stat -c '%a %n' \
  "$HOME/.config/ninjarobot_pi5/tls/local-ca-key.pem" \
  "$HOME/.config/ninjarobot_pi5/tls/agent-key.pem"
```

Expected result:

- the certificate covers `ninjarobotpi5.local`
- both private key files have permission `600`
- `ninjarobotpi5-local-ca.pem` is a public certificate and contains no private
  key

Copy `ninjarobotpi5-local-ca.pem` to each controlling phone using a trusted
local method.

### 4.4 Trust the CA on iPhone or iPad for Safari and Chrome

Both Safari and Chrome on iPhone or iPad use the iOS certificate trust store.

1. Open the copied `ninjarobotpi5-local-ca.pem` file on the device.
2. Allow iOS to download the configuration profile.
3. Open **Settings → General → VPN & Device Management**.
4. Install **NinjaRobotPi5 Local CA**.
5. Open **Settings → General → About → Certificate Trust Settings**.
6. Enable full trust for **NinjaRobotPi5 Local CA**.
7. Close and reopen Safari and Chrome.

Only install the public CA certificate. Never copy
`local-ca-key.pem` or `agent-key.pem` off the Raspberry Pi.

### 4.5 Trust the CA on Android Chrome

The exact menu name varies by Android manufacturer. It is normally under:

**Settings → Security → Encryption & credentials → Install a certificate → CA
certificate**

Choose `ninjarobotpi5-local-ca.pem`, approve the warning, and restart Chrome.
If a managed phone forbids user-installed CA certificates, use a personal
unmanaged test device or an administrator-provided certificate.

### 4.6 Start the web interface

```bash
uv run --frozen ninjarobot-agent web start
uv run --frozen ninjarobot-agent web status
```

Expected result: the printed address is:

```text
https://ninjarobotpi5.local:8443/
```

The phone and Pi must be on the same local network. Do not use an internet
address.

### 4.7 Validate mobile Safari in portrait

Open the address in current mobile Safari.

Check each item:

1. No certificate warning appears after the CA is fully trusted.
2. The page fits the visible portrait screen without document scrolling.
3. The D-pad, camera/audio controls, action buttons, and conversation area are
   usable.
4. Live Activity is hidden at the bottom except for its tab.
5. Tapping or sliding the tab opens the activity drawer.
6. Tapping the tab again or sliding it down closes the drawer.
7. Rotating to landscape shows a rotate-back message and hides live controls.
8. Returning to portrait restores the controller.
9. Pressing and holding a D-pad button does not select text or open a touch
   callout.
10. Releasing the D-pad button sends Stop.

Safari pass condition: all ten checks pass.

### 4.8 Validate mobile Chrome in portrait

Disconnect Safari so it releases the exclusive controller lease. Open the same
address in current mobile Chrome and repeat all ten checks from Step 4.7.

Chrome pass condition: all ten checks pass. If Chrome says the controller is
locked, close Safari and wait for the old heartbeat lease to expire before
trying again.

### 4.9 Check browser speech without automatic sending

Test this once in Safari and once in Chrome when the browser provides speech
recognition:

1. Select English.
2. Press Web Microphone and say a short sentence.
3. Confirm the recognized sentence appears in the chat input.
4. Wait five seconds.
5. Confirm no message was sent automatically.
6. Edit the text, then press Send.
7. Repeat with Japanese.

Expected result: speech fills the input and places focus there. Only pressing
Send transmits the prompt. A browser that does not implement the Web Speech
API must show a clear unsupported message and leave all other controls usable.

### 4.10 Check the exclusive controller lease

Keep one phone connected and open the controller from another browser or
device.

Expected result: the second connection is rejected with `423 Locked` or a
browser-friendly locked message. The first browser remains in control.

Refresh the active browser once. Expected result: it reclaims its lease with
the short-lived reconnect token.

### 4.11 Check temporary camera and USB microphone use

Tell everyone nearby before this test.

1. Press Camera.
2. Confirm a temporary preview appears and closes automatically or when
   dismissed.
3. Confirm no new retained JPEG remains in:
   `~/.local/share/ninjarobot_pi5/camera/`.
4. Press USB Microphone, speak, and stop recording.
5. Confirm local transcription is submitted to chat.
6. Confirm no new temporary WAV remains in:
   `~/.local/share/ninjarobot_pi5/microphone/`.

The USB microphone workflow intentionally submits completed transcription.
The Web Microphone workflow in Step 4.9 intentionally does not.

## 5. Actuator-moving tests

Every command in this section can energize both continuous-rotation servos.
Keep both wheels raised.

### 5.1 Confirm movement starts without a clear-reading preflight

Aim the front VL53L0X sensor into open space. Open space may report the exact
raw value `8191`, which means out of range and is treated as clear.

Press and hold Forward for about one second, then release.

Expected result: movement starts immediately after normal driver and safety
checks. It must not wait for three clear readings.

### 5.2 Check all direct directions

Press and release each direction for about one second:

1. Forward
2. Backward
3. Turn Left
4. Turn Right

Expected result:

- Forward, Turn Left, and Turn Right use obstacle monitoring.
- Backward runs with a visible forward-sensor coverage warning.
- Turning does not show the old directional coverage warning.
- Releasing the D-pad requests Stop.

If wheel direction is wrong, stop and correct calibration or logical role
mapping. Do not reverse live wiring.

### 5.3 Check the 50 mm Level 1 obstacle stop

Start Forward with the wheels raised. Move a flat target toward the front
sensor until it is 50 mm or closer.

Expected result: three consecutive valid readings at or below 50 mm stop and
latch servo movement. One or two low readings must not stop movement.

Try Forward again. Expected result: movement stays locked.

Resume it:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" motion resume --confirm
```

Expected result: the Level 1 latch clears and the silent Idle face returns.

Repeat the obstacle test for Turn Left and Turn Right. Do not repeat it for
Backward because the forward-facing sensor does not protect rear travel.

### 5.4 Check invalid and out-of-range readings safely

With the wheels raised and sensor aimed into open space, confirm that raw
`8191` does not stop Forward or turning. A null, invalid, missing, or stale
reading also must not trigger an obstacle stop; it is still recorded as a
sensor warning or communication condition.

Do not unplug I2C wiring while the robot is powered merely to force a null
reading. The automated tests cover that case.

### 5.5 Check Level 2 Emergency Stop and Resume

Start movement and press X.

Expected result:

- both servos stop
- active sensor work stops
- the buzzer is silent
- the display shows the Emergency Stop sign
- Idle does not overwrite the stop sign

Press Y, cancel once, then press Y and confirm.

Expected result: cancelling changes nothing. Confirming reconstructs and
health-checks modules, does not restart the old movement, and returns to the
silent Idle face.

### 5.6 Check heartbeat-loss stop

With wheels raised, start a direction and disable Wi-Fi on the controlling
phone.

Expected result: missed heartbeats revoke the controller lease and stop servo
movement without waiting for the LLM. Restore Wi-Fi and verify that a new
controller can connect.

## 6. Expected outcomes

The refinement passes only when:

- all automated checks pass
- no private model reasoning appears in chat or logs
- slow model activity is not interrupted by the old timeout
- real startup runs Greeting once and then loops silent Idle
- safety displays are not overwritten by Idle
- movement starts without a clear-distance preflight
- three consecutive valid readings at or below 50 mm stop guarded movement
- locally trusted HTTPS opens without warnings in mobile Safari and Chrome
- the portrait layout has no document scroll and landscape blocks controls
- D-pad presses do not select text
- browser speech waits for Send
- only one browser controls the robot
- camera and microphone temporary files are cleaned up
- heartbeat loss stops movement

## 7. Pass/fail checklist

| Check | Result |
|---|---|
| Immutable drivers | Pass / Fail |
| Compile, Ruff, format, mypy, pytest | Pass / Fail |
| JavaScript and manifest syntax | Pass / Fail |
| Slow agent response | Pass / Fail |
| Startup Greeting once | Pass / Fail |
| Silent Idle loop and restoration | Pass / Fail |
| No clear-reading startup gate | Pass / Fail |
| Forward obstacle stop at 50 mm | Pass / Fail |
| Left-turn obstacle stop at 50 mm | Pass / Fail |
| Right-turn obstacle stop at 50 mm | Pass / Fail |
| Backward coverage warning | Pass / Fail |
| Level 2 stop and Resume | Pass / Fail |
| Public CA exported; private keys protected | Pass / Fail |
| Mobile Safari portrait controller | Pass / Fail |
| Mobile Chrome portrait controller | Pass / Fail |
| Landscape safety overlay | Pass / Fail |
| D-pad touch behavior | Pass / Fail |
| Live Activity drawer | Pass / Fail |
| English browser speech review | Pass / Fail / Unsupported |
| Japanese browser speech review | Pass / Fail / Unsupported |
| Exclusive lease and refresh recovery | Pass / Fail |
| Heartbeat-loss movement stop | Pass / Fail |
| Camera temporary preview cleanup | Pass / Fail |
| USB microphone temporary-file cleanup | Pass / Fail |

## 8. Rollback steps

First stop the web interface and owner service:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent service stop
```

If movement remains latched after a safe restart:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" motion resume --confirm
```

If the browser certificate must be replaced, stop the web interface first.
Preserve the current files for investigation instead of deleting them. The TLS
directory is:

```text
~/.config/ninjarobot_pi5/tls/
```

Remove **NinjaRobotPi5 Local CA** from a phone's trusted certificates if that
phone will no longer control this robot.

For a software rollback, check out the last known-good Git commit, run
`uv sync --frozen --extra hardware`, rerun the complete software gate, and
repeat the safe smoke tests before enabling real hardware.
