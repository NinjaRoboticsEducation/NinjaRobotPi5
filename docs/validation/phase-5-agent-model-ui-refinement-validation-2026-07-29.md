# Phase 5 Agent Model and Controller Refinement Validation

Date prepared: 2026-07-29  
Software status: implemented; automated gate passed before this checklist  
Raspberry Pi status: operator validation required  
Target: Raspberry Pi 5 with 8 GB RAM, active cooling, and the configured robot
hardware

This checklist validates local model selection, expressive face transitions,
the corrected Tavily connection, browser microphone behavior, and the refined
portrait controller.

Useful terms:

- LLM means large language model, the local Ollama model that answers prompts.
- MCP means Model Context Protocol, the connection used for external tools
  such as Tavily web search.
- Hot switch means changing the model without stopping an idle agent service.
- CA means certificate authority, the local certificate that the phone trusts
  for HTTPS.
- PWA means Progressive Web App, the Home Screen version of the controller
  without normal browser controls.
- Controller lease means the one temporary browser permission to control the
  robot.

## 1. Scope

This checklist covers:

- the complete software quality gate
- installed Ollama model discovery and persistent selection
- refusal to switch models while the agent is busy
- benchmark reporting and confirmed natural-language motion arming
- Idle, Thinking, Speaking or emotion, tool action, and return-to-Idle faces
- current raw Tavily tool name `tavily_search` and stable public name
  `mcp.tavily.tavily-search`
- English and Japanese browser speech filling, but not sending, the input
- portrait sizing, fullscreen entry, Safari Home Screen fallback, D-pad touch,
  and Live Activity clearance
- one-browser lease, refresh recovery, and second-browser refusal

It does not accept a model benchmark on the operator's behalf and does not
prove that every mobile browser version implements speech recognition.

## 2. Safety notes

1. Complete Sections 3 and 4 before starting real hardware.
2. Keep both wheels raised for every D-pad or natural-language movement test.
3. Keep fingers, hair, loose clothing, and cables away from the wheels.
4. Keep a second terminal ready with:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen ninjarobot-agent service stop
```

5. Tell people nearby before testing either microphone or the camera.
6. Do not expose port 8443 through router forwarding or to the internet.
7. Stop if the Pi reports undervoltage, overheating, throttling, a stalled
   motor, or an unresponsive control path.

## 3. Safe smoke tests

### 3.1 Install the locked environment

```bash
cd "$HOME/NinjaRobotPi5"
git status --short
uv sync --frozen --extra hardware
```

Expected result: synchronization succeeds. Review any files printed by
`git status`; do not discard owner configuration or unrelated work.

### 3.2 Run the software gate

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_agent/src ninjarobot_pi5_ide/src
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

Expected result: every command passes. The immutable-driver check reports 222
tracked files and 25 authorized repairs.

### 3.3 List and select a local model with the service stopped

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"

ollama list
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model list
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model select qwen3:4b
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model current
```

Replace `qwen3:4b` with an exact name printed by `model list` when necessary.

Expected result:

- the agent catalog matches Ollama's installed models
- metadata includes size, parameter size, and quantization when Ollama
  provides them
- `model current` reports the selected provider, model, benchmark acceptance,
  and `"service_running": false`
- the selection remains after opening the command again

Selecting does not download a missing model. Use `ollama pull MODEL_NAME`
before this test if needed.

### 3.4 Test the interactive model menu

```bash
uv run --frozen ninjarobot-agent
```

Choose **Change Agent Model**, confirm that installed models are numbered, and
choose `0` to go Back without changing anything. Reopen it, select the intended
model number, and confirm that the tool reports the new provider/model.

Choose **Quit CLI**. Expected result: only the terminal tool exits.

### 3.5 Test a hot switch and busy refusal

Start the simulated service:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" service start
```

If at least two small local models are installed, select the second model while
the service is idle:

```bash
uv run --frozen ninjarobot-agent model list
uv run --frozen ninjarobot-agent model select SECOND_MODEL_NAME
uv run --frozen ninjarobot-agent model current
```

Expected result: the service stays running, health-checks the candidate,
switches it, closes the old provider, saves the choice, and reports
`"service_running": true`.

For the busy check, start a long chat in Terminal A:

```bash
uv run --frozen ninjarobot-agent chat \
  "Think carefully and give me a detailed ten-step Raspberry Pi safety checklist."
```

While text is still being generated, run `model select` in Terminal B.

Expected result: Terminal B says the agent is busy and does not switch. Retry
after Terminal A completes; the idle switch should then succeed.

Restore the intended model before continuing.

### 3.6 Verify benchmark reporting and motion arming

```bash
uv run --frozen ninjarobot-agent model current
uv run --frozen ninjarobot-agent motion arm \
  --session model-gate-test --confirm
```

Expected result:

- any installed selected model that passes provider health arms the named
  session after `--confirm`
- `model current` still reports the exact model's benchmark status for
  performance and quality review
- benchmark acceptance does not grant or remove motion permission
- omitting explicit confirmation must still refuse motion arming

Disarm afterward:

```bash
uv run --frozen ninjarobot-agent motion disarm --session model-gate-test
```

## 4. Communication and interface tests

### 4.1 Verify Tavily compatibility

If Tavily has already been configured:

```bash
uv run --frozen ninjarobot-agent mcp health tavily
uv run --frozen ninjarobot-agent mcp tools tavily
uv run --frozen ninjarobot-agent mcp inspect tavily
```

Expected result:

- health is ready
- exactly the approved search tool is available
- the public tool name is `mcp.tavily.tavily-search`
- inspection shows raw allowed name `tavily_search`
- the API key is never printed

An older local file containing `tavily-search` should also pass because it is
migrated safely in memory. New saved presets use `tavily_search`.

Run one harmless search:

```bash
uv run --frozen ninjarobot-agent \
  mcp test tavily --tool tavily-search \
  --arguments '{"query":"Raspberry Pi official news","max_results":3}'
```

Expected result: recent external results and source URLs are returned without
an IDE action or robot movement.

### 4.2 Validate real face lifecycle without movement

Stop simulation and start the real service:

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" service start --real
```

Expected startup result:

1. Greeting face, melody, and “Nice to meet you” run once.
2. The display changes to a silent looping Idle face.

Send a text-only prompt:

```bash
uv run --frozen ninjarobot-agent chat \
  "Answer happily in two short sentences without using a tool."
```

Expected result:

1. Idle changes to looping Thinking while the model reasons.
2. Visible response streaming changes to Speaking or an approved matching
   emotion.
3. No text such as `[[face:happy]]` appears in the terminal response.
4. The display returns to looping Idle after completion.

Ask for one read-only distance measurement. Expected result: the foreground
tool action has priority, the agent returns to Thinking before its final
answer, and then returns to Idle. A presentation failure may be logged, but it
must not crash chat or bypass safety.

### 4.3 Start the HTTPS web controller

```bash
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent web start
grep -c 'BEGIN CERTIFICATE' \
  "$HOME/.config/ninjarobot_pi5/tls/agent-cert.pem"
uv run --frozen ninjarobot-agent web certificate-status
uv run --frozen ninjarobot-agent web export-ca \
  --output "$HOME/ninjarobotpi5-local-ca.pem"
```

Expected result: the generated certificate count is `2`. This proves the
server file contains its leaf certificate and local CA chain. Never copy
either private key from `~/.config/ninjarobot_pi5/tls/`.

Open:

```text
https://ninjarobotpi5.local:8443/
```

Chrome path without CA installation:

1. If Chrome offers **Advanced → Proceed**, accept the warning.
2. Reload the controller.
3. Confirm the connection becomes active and Live Activity does not report an
   HTTPS WebSocket failure.

This warning bypass is optional and browser-dependent. If Chrome offers no
bypass or the WebSocket remains disconnected, install and trust only the
exported public CA as described in `InstallationGuide.md`.

Safari path: install and fully trust the exported CA before testing. Expected
result: no certificate warning appears after trust is configured. The trusted
path is also the recommended browser-microphone setup.

### 4.4 Validate Android Chrome

In portrait Chrome:

1. Tap **Tap to Start Controller**.
2. Confirm fullscreen opens when the device supports it.
3. Confirm the page fits without document scrolling or pinch zoom.
4. Confirm the connection badge and Arm AI motion button share the top control
   row.
5. Confirm no Agent Controller, AI motion badge, or DIRECT CONTROL label is
   present.
6. Confirm the chat input remains above the collapsed Live Activity tab.
7. Open and close Live Activity by tapping and sliding its tab.
8. Hold each D-pad direction briefly with wheels raised; no text selection,
   callout, or stuck pressed state should occur.
9. Leave Chrome outside fullscreen or show its browser controls. Confirm the
   D-pad remains above the camera and USB microphone buttons with no overlap.
10. Rotate to landscape; the rotate-back screen should hide live controls.

### 4.5 Validate iPhone or iPad Safari

Repeat the portrait checks in Safari. Page fullscreen may be unavailable on
this browser; that is not a controller failure.

For the best standalone test:

1. Choose **Share → Add to Home Screen**.
2. Close Safari.
3. Launch the NinjaRobot icon.
4. Confirm it opens in portrait standalone mode without showing the start
   overlay again.
5. Confirm all controls and Live Activity remain usable.

### 4.6 Validate browser speech in English and Japanese

On each supported test browser:

1. Select **English**.
2. Tap **Web Microphone** and allow microphone access.
3. Speak one short sentence.
4. Confirm recognized text fills the message box.
5. Confirm no user chat bubble appears until **Send** is tapped.
6. Edit the text, tap **Send**, and confirm the edited version is transmitted.
7. Repeat with **日本語** selected and one short Japanese sentence.
8. Tap Web Microphone while listening and confirm it stops cleanly.

If the button says speech recognition is unsupported, record the browser and
operating-system versions as an unsupported result rather than an agent
failure. A certificate warning, denied permission, or disabled platform speech
service must be corrected before retesting.

### 4.7 Validate the exclusive browser lease

Keep the first controller open and try the same URL from a second device.

Expected result: the second controller is refused with `423 Locked` or the
browser's equivalent connection error. It must not send controls.

Refresh the first device. Expected result: its short-lived reconnect token
reclaims the same lease and normal controls return. Close it, wait for lease
cleanup, then confirm the second device can connect.

## 5. Actuator-moving tests

These tests move the wheels. Raise both wheels and keep Emergency Stop ready.

### 5.1 Direct D-pad controls

Press and hold Forward, Backward, Left, and Right one at a time, then release.

Expected result: movement begins while held and stops on release. The model's
benchmark state does not block these explicit operator controls.

### 5.2 Network-loss stop

Start a brief raised-wheel D-pad movement, then disable Wi-Fi on the controlling
phone.

Expected result: the missed heartbeat revokes the lease and requests a servo
stop without waiting for the model. Re-enable Wi-Fi and reconnect before any
further test.

### 5.3 Natural-language motion

Arm AI motion for the active chat session, request one brief movement, and keep
Emergency Stop ready. Expected result: any installed healthy selected model
can request motion after the explicit arm. The request still passes through
the existing IDE motion and obstacle guards. Repeat once with a model whose
benchmark reports `"accepted": false` or has no report; benchmark state must
not block the confirmed session.

## 6. Expected outcomes

- Model selection and chat work independently of benchmark acceptance.
- Explicit confirmation is still required before natural-language motion.
- The generated HTTPS server file contains a two-certificate chain.
- Chrome can control the robot after either its supported warning-bypass flow
  or CA trust; Safari works after local CA trust.
- The controller receives one exclusive lease, and lost heartbeats stop
  movement.
- D-pad controls remain visible and separated from media controls in
  fullscreen and short non-fullscreen portrait layouts.
- All physical actions continue through the IDE safety boundary.

### 6.1 Optional power-risk model benchmark

This test can heat the Pi and consume substantial memory. Use active cooling,
stable power, and no simultaneous wheel test.

```bash
uv run --frozen ninjarobot-agent benchmark ollama \
  --model qwen3:4b \
  --output "$HOME/.local/share/ninjarobot_pi5/benchmarks/qwen3-4b-latest.json"
```

Expected result: a complete JSON report records latency, correctness, memory,
temperature, throttling, and final acceptance. Stop immediately for
undervoltage, thermal throttling, or unsafe temperature. The report is
decision evidence and does not change motion permission.

## 7. Pass/fail report

Record one row for every test:

| Check | Pass/Fail/Skipped | Actual result and evidence |
|---|---|---|
| Software gate |  |  |
| Model list/current/offline selection |  |  |
| Idle hot switch and busy refusal |  |  |
| Benchmark reporting and confirmed motion arm |  |  |
| Tavily health, tools, and search |  |  |
| Startup Greeting and Idle |  |  |
| Thinking, response/emotion, action, Idle |  |  |
| Android Chrome portrait/fullscreen |  |  |
| iOS Safari portrait/Home Screen |  |  |
| English browser microphone |  |  |
| Japanese browser microphone |  |  |
| Exclusive lease and refresh |  |  |
| Raised-wheel D-pad and network-loss stop |  |  |
| Any installed-model natural-language motion |  |  |
| Thermal benchmark |  |  |

Overall result is **Pass** only when every applicable safety and functional
check passes. A Skipped browser-speech check must name the unsupported browser
and version; it does not validate that platform.

## 8. Cleanup and rollback

Stop resources in this order:

```bash
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent service stop
```

To roll back only a model choice, select the previous installed model:

```bash
uv run --frozen ninjarobot-agent model select PREVIOUS_MODEL_NAME
```

If the web layout is unusable, stop the web interface and continue with the
local CLI; do not keep testing movement through a partially visible page. If
Tavily is unavailable, disable it without affecting IDE tools:

```bash
uv run --frozen ninjarobot-agent mcp disable tavily
```

If Chrome cannot bypass the warning, install the exported CA instead of
disabling HTTPS. To recover from an unsuccessful software update, stop the
service, restore the previous Git commit, run the following command, and start
the service again:

```bash
uv sync --frozen --extra hardware
```

Do not delete the TLS directory unless you intentionally want every
controlling device to trust a newly generated local CA.
