# Phase 8 Final Interactive Raspberry Pi Validation

Date prepared: 2026-08-14  
Target: Raspberry Pi 5, branch `public_v01`, release candidate `v1.0.0`  
Method: normal-user workflows through `ninjarobot-ide-tool`,
`ninjarobot-agent`, and the web controller

This is the consolidated acceptance sequence for both the existing checkout
and a clean clone. Command-line operations below are limited to installation,
launching the interactive tools, and collecting final evidence. Feature tests
use the same menus, chat commands, buttons, and browser workflows available to
an ordinary user.

## 1. Safety and evidence preparation

- Raise both wheels so the robot cannot leave the work surface.
- Clear hands, hair, cables, and loose objects from the movement envelope.
- Use a stable Raspberry Pi 5 supply and keep an accessible power disconnect.
- Obtain consent before camera or microphone tests.
- Keep AI motion disarmed until an actuator step explicitly says to arm it.
- Perform the web power-off test last because it shuts down the Pi.
- Do not paste an ngrok authtoken, pairing fragment, cookie, or private key into
  this report.

Record:

| Item | Value |
|---|---|
| Pi model / RAM | |
| Raspberry Pi OS version | |
| Git commit | |
| Test checkout path | |
| Browser/device versions | |
| USB microphone | |
| ngrok agent version | |
| Start time / end time | |

## 2. Existing-checkout acceptance

### 2.1 Preserve local work and update dependencies

From the existing checkout:

```bash
cd "$HOME/NinjaRobotPi5"
git status --short
uv sync --frozen --extra hardware
./scripts/bootstrap-rpi-camera-workspace.sh --skip-apt
source .venv/bin/activate
```

Expected: dependency synchronization completes, and any pre-existing local
file such as `mic.json` remains visible in `git status`. Do not discard local
changes merely to run validation.

### 2.2 Validate integrated hardware through the IDE Interactive Tool

Ensure the agent service is stopped, then launch:

```bash
ninjarobot-ide-tool
```

Use these menu workflows:

1. **Hardware Configurations → Show Current Configuration**. Confirm display,
   buzzer, I2C, camera, microphone, servo endpoints, servo roles, calibration,
   and safety paths point to the intended user configuration.
2. Optionally use **Simulation** for one hardware-free preview.
3. Use **Run Robot Behaviors** directly on real hardware.
   Run Greeting first. Expected: face/display and buzzer operate and Idle
   returns.
4. Run **Emergency Stop**. Expected: active sound/motion/presentation stops and
   the display holds the red emergency icon. Wait 15 seconds; the face must not
   overwrite it.
5. Select **Resume Robot Movement** and confirm. Expected: health checks pass,
   Idle returns, and AI motion remains disarmed.
6. With wheels raised, run one short movement behavior and then Emergency Stop.
   Expected: movement stops promptly and the same persistent icon wins the
   display.
7. Quit the tool normally. Expected: hardware ownership is released.

Fail immediately if the display freezes on the previous face, the stop frame
is overwritten, hardware remains active, or Resume bypasses a failed health
check.

### 2.3 Start the real Agent through the Agent Interactive Tool

Launch:

```bash
ninjarobot-agent
```

1. Select **2. Start Agent Service**.
2. Select **2. real hardware**.
3. Select **3. Agent Service Status**.
4. Select **9. MCP Tools (Built-in and External)**. Expected: IDE,
   robot-control, and memory providers/tools are listed even when the external
   server list is empty.

Expected: one real-hardware service is running, the IDE and trusted tool
providers are ready, and the status names the expected model/configuration.
The service log begins with a marker containing this checkout path,
`mode=real`, timestamp, and Python interpreter.

### 2.4 Voice readiness, wake word, recording, and recovery

In the Agent Interactive Tool select **1. Chat with NinjaRobot**.

1. Enter `/voice input status`. Note the initial state.
2. Enter `/voice input on`.
3. Expected: the operation returns only after `state: listening`, with
   `model_loaded: true` and `listening_indicator: true`. A successful response
   must never remain `starting`.
4. Say “Hey Ninja”, then ask a harmless question. Stop speaking before 15
   seconds. Expected: recording ends after silence, exactly one transcript is
   dispatched, one reply appears, and the listener returns to `listening`.
5. Repeat once in English, Japanese, Traditional Chinese, and Simplified
   Chinese after selecting/configuring the applicable recognition locale.
6. Leave motion disarmed and request movement by voice. Expected: no movement.
7. Enter `/arm`, type `ARM`, and issue one one-second voice movement with the
   wheels raised. Expected: exactly one bounded action.
8. Enter `/voice input off`. Expected: voice becomes disabled and the voice
   motion grant is cleared.
9. Re-enable voice without `/arm` and repeat the movement request. Expected:
   it is denied.

Recovery trial: temporarily occupy or disconnect the USB microphone, then
enable voice. Expected: within the configured startup bound the operation
reports a stable microphone/startup error, leaves `enabled: false`, and releases
the partial stream. Correct the device and enable again; it must reach
`listening` without restarting the entire Pi.

### 2.5 Web interface, i18n, media controls, and stop display

Return from chat, then use **5. Local Web Interface** and **6. Local Web
Interface Status**. Open the reported HTTPS URL using a paired browser.

1. Confirm the main surface contains Camera, Web Microphone, Voice Input, and
   Record Once. Voice Input and Record Once must be directly below the first
   two media controls and absent from the hamburger.
2. While the connection badge is active, switch successively to English,
   Japanese, Traditional Chinese, and Simplified Chinese.
3. Expected: every label changes language while the badge continues to mean
   connected. It must not change to `Not connected`, `未接続`, `尚未連線`, or
   `尚未连接` unless the WebSocket truly disconnects.
4. Reload. Expected: the chosen language persists in that browser.
5. Test Camera with consent. Expected: countdown, temporary preview, cleanup,
   and return to Idle.
6. Test Web Microphone. Expected: browser speech fills the message box but does
   not submit unexpectedly.
7. Turn Voice Input on from the main button. Expected: it reports listening and
   the terminal status agrees.
8. Select Record Once. Expected: always-on listening pauses, one bounded local
   recording/transcription completes, and listening resumes without a device
   busy error.
9. Open the hamburger. Expected: only language, connection information, and
   power controls are present; focus/close/Escape behavior works.
10. Trigger Emergency Stop from the main controller. Expected: the display
    immediately shows and retains the red emergency icon. Select Resume and
    confirm; expected: Idle returns and AI motion is disarmed.
11. Open a second browser. Expected: it cannot silently take the exclusive
    controller lease from the first browser.

### 2.6 Shared memory and model-switch regression

Use terminal chat to state an explicit preferred name and robot name, then ask
the agent to recall them. Open the web interface as the same user and confirm
the same profile preferences are recalled. Use **3. Change Agent Model**, select
another configured model, and confirm the preferences and a saved behavior are
still available. Expected: terminal/web transcripts remain interface-specific,
but user profile and long-term memory remain shared and model-independent.

### 2.7 ngrok remote access and pairing

In the Agent Interactive Tool choose **8. Ngrok Remote Access**.

1. Select **1. Set ngrok token**. Enter the authtoken twice at the hidden
   prompts.
2. Expected: a valid existing ngrok v3 binary is reused, or a replacement is
   installed without `Text file busy`.
3. Select **2. Activate ngrok remote access service**, then return to the main
   menu and start the Agent if it is not already running.
4. Select **3. Ngrok service status**. Expected: `waiting_for_connection` (or connected), a
   public HTTPS URL, and pairing available. `configuration_invalid` is a fail.
5. Select **4. Show existing pairing URL**. Expected: a URL with a short-lived
   `#pair=` fragment. There is no separate numeric pairing code and no browser
   username/password prompt.
6. Open it from a device outside the LAN. Complete any ngrok interstitial.
   Expected: one exchange removes the fragment and creates the normal dashboard.
7. Reuse the consumed URL in another private browser. Expected: it cannot gain
   control.
8. While the tunnel is healthy, select **5. Local Web Interface** from the main
   menu. Expected: `ready: false`, `running: false`, `url: null`, with the ngrok
   instruction.
9. Disconnect networking briefly. Expected: Local Web fallback and a local QR
   appear. Restore it and confirm recovery returns to remote-only mode using one
   endpoint/process.
10. Select **5. Stop ngrok remote access service**. Expected: public URL clears and remote sessions are
   revoked while local service/memory/hardware remain available.
11. Confirm Local Web does not start silently; start it explicitly and verify
    the local URL works. Activate remote access again before boot validation.

If Status reports a permanent authentication/account/configuration error,
correct it and explicitly activate again. The supervisor should not continuously
restart a permanently invalid endpoint. If pairing URL reports
`tunnel_not_ready`, Status must explain the upstream failure without an argparse
usage traceback.

### 2.8 Auto-start, QR onboarding, and Greeting

In the Agent Interactive Tool select **12. Startup Agent Deployment**.

1. Select **3. Show startup Agent status** and record the result. An older
   failed installation may correctly show `enabled: true`, `running: false`,
   `ready: false`, plus its systemd result and restart count.
2. Select **1. Install and deploy automatic startup Agent** and type `ENABLE`.
   Expected: `systemd_unit`, `poweroff_helper`, and `sudoers_rule` are all true;
   `running_now` and `ready` are true. Setup must clear an old start-limit and
   must not report success merely because the unit is enabled.
3. Select **3. Show startup Agent status** again. Expected: installed, enabled,
   running, and ready are true and every artifact remains present.
4. Reboot the Pi normally.
5. Expected after boot: QR onboarding appears without Greeting or motion. If a
   configured ngrok endpoint is healthy, its remote QR remains while waiting.
   Local mDNS is used only after an explicit remote failure or when remote
   access is disabled.
6. Pair and connect a browser. Expected: QR clears, Greeting runs exactly
    once, and Idle follows. Reload/reconnect must not replay Greeting.
7. Reboot once with the microphone disconnected and once with networking
    unavailable. Expected: safe error/degraded reporting, no unbounded startup,
    local recovery where applicable, and no unexpected movement.

### 2.9 Power-off test — perform last

From the paired active browser, open the hamburger and choose Power Off.

1. Choose Cancel. Expected: nothing shuts down.
2. Reopen it, choose Power Off, and confirm in the second popup.
3. Expected order: hardware safe stop, voice/tunnel/web closure, durable-store
   and IDE cleanup, then Raspberry Pi power-off.
4. After power is fully off, inspect the filesystem/log/database on the next
   boot. Expected: no corruption and no restart loop.

This is a power-risk test. If deployment is incomplete, the browser must reject
the request before the Agent or hardware is stopped and direct the operator to
repair deployment. A rare helper failure after confirmed cleanup leaves the
robot stopped; use the documented local orderly shutdown. Use the physical
disconnect immediately if any actuator remains unsafe.

## 3. Clean-clone acceptance

Use a new empty directory; do not delete or overwrite the existing checkout.

```bash
mkdir -p "$HOME/NinjaRobotPi5_test"
cd "$HOME/NinjaRobotPi5_test"
git clone --branch public_v01 --single-branch \
  https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git \
  NinjaRobotPi5
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
uv sync --frozen --extra hardware
./scripts/bootstrap-rpi-camera-workspace.sh
source .venv/bin/activate
```

Follow Installation Guide Steps 4 and 5 to create the six standalone hardware
profiles, calibrate both wheel servos with wheels raised, and import them into
`~/.config/ninjarobot_pi5/config.toml`. Hardware calibration is user data and
is intentionally shared outside either Git checkout; review every imported
path before applying it.

Then repeat Sections 2.2 through 2.9 from inside `NinjaRobotPi5_test`. The
service-start marker and deployment logs must show the test checkout—not the
old checkout. Pay particular attention to these clean-install conditions:

- `pi5camera camera-tool` captures through the apt-managed system-Python bridge
  without adding system site packages to `.venv`;
- all six standalone tools use `~/.config/pi5*/` without explicit path flags;
- the bundled `hey_Ninja.onnx` package resource and openWakeWord assets load offline;
- the integrated agent reads `~/.config/ninjarobot_pi5/config.toml`, not a
  checkout-root `mic.json`;
- ngrok reuses or atomically replaces its owner-private installed binary;
- profiles, memory, faces, saved behaviors, and calibration remain available
  after model changes and interface changes;
- exactly one process owns display, buzzer, servo, camera, distance sensor, and
  microphone resources;
- auto-start points to the clean clone only after the explicit transactional
  setup confirmation.

If the clean clone fails while the existing checkout passes, stop the service
through the Interactive Tool, compare the startup source marker and private
configuration paths, and rerun dependency/camera setup. Do not copy `.venv`,
edit managed `pi5*` sources, delete the safety state, or start a second service
as a workaround.

## 4. Two-hour stability soak

With wheels raised and motion disarmed unless actively testing:

1. Leave voice, web, and ngrok enabled for at least two hours.
2. Every 15 minutes use **Agent Status**, **Web Interface Status**, and **Remote
   Access → Status**.
3. Perform at least eight valid wake cycles, four Record Once cycles, four
   camera previews, four language switches, and two remote reconnects.
4. Trigger and resume one Emergency Stop near the beginning and one near the
   end.

Expected: one agent/ngrok/audio owner, bounded memory/log growth, no temporary
WAV buildup, no duplicate command dispatch, no frozen display, no lost
hardware ownership, and successful recovery after each stop/reconnect.

## 5. Pass/fail record

| Area | Pass/Fail | Evidence / notes |
|---|---|---|
| IDE simulation and hardware configuration | | |
| Greeting, Idle, display, buzzer, camera, sensors | | |
| Emergency icon persistence and Resume | | |
| Voice readiness and wake/silence cycle | | |
| Voice failure cleanup and re-enable | | |
| Four-language web state and layout | | |
| Camera/Web Mic/Voice/Record Once serialization | | |
| Shared memory and model switching | | |
| ngrok install/Traffic Policy/tunnel | | |
| Pairing, replay rejection, rotation | | |
| Auto-start and QR/Greeting | | |
| Confirmed web power-off | | |
| Clean-clone repeat | | |
| Two-hour stability soak | | |

Any unexpected movement, anonymous remote control, secret leakage, duplicate
hardware owner, indefinite voice `starting`, repeating permanent ngrok failure,
frozen emergency display, or corrupted persistent data is a release blocker.

## 6. Rollback

Use the Agent Interactive Tool in this order:

1. Chat: `/voice input off`, then `/disarm`.
2. Remote Access: **Deactivate**.
3. Auto-Start & Deployment: **Disable and stop automatic startup**.
4. **Stop Agent Service**.

If the Interactive Tool cannot communicate, use the installed service manager
or physical power disconnect according to the failure severity. Restore the
deployment backup through **Auto-Start & Deployment → Roll back from a backup**.
Rollback must preserve profiles, memory, face data, saved behaviors,
calibration, and secrets unless the operator explicitly chooses the separate
credential/memory deletion workflows.
