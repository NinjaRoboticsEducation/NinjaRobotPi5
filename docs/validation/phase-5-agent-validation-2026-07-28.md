# Phase 5 NinjaRobotAgent Raspberry Pi Validation

Date prepared: 2026-07-28  
Software status: implemented; local software gate passed  
Raspberry Pi status: operator validation required  
Target: Raspberry Pi 5 with 8 GB RAM and active cooling

This guide checks the Phase 5 agent one layer at a time. Follow it in order.
Do not begin camera, microphone, or wheel tests until the earlier safe section
passes.

Important terms:

- LLM means large language model, the local text model served by Ollama.
- MCP means Model Context Protocol, the connection used for separately
  installed tools such as Tavily web search.
- HTTPS means encrypted browser traffic.
- WebSocket means the persistent browser connection carrying control messages
  and heartbeats.
- Controller lease means the temporary exclusive right held by one browser.
- Heartbeat means the small repeated message proving that browser is still
  connected.
- IDE means the NinjaRobotPi5 hardware-control boundary. The agent reaches
  hardware only through the IDE.

## Safety and privacy preparation

Before running commands:

1. Put the robot on a stable work surface.
2. Keep both wheels raised for every movement test.
3. Keep hair, cables, fingers, and loose objects away from the wheels.
4. Tell everyone nearby before using the camera or either microphone.
5. Keep one browser open on the Emergency Stop button during real movement.
6. Open a second SSH terminal and prepare this model-independent shutdown
   command, but do not press Enter:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen ninjarobot-agent service stop
```

7. Remember that this robot has no independent physical servo cutoff. If
   software cannot stop unsafe motion, remove robot power only if you can do so
   without reaching into moving parts.
8. Do not expose TCP port 8443 to the internet and do not configure router
   port forwarding.

Stop immediately if you see smoke, smell hot insulation, hear a stalled motor,
see repeated undervoltage, or cannot keep the wheels safely clear.

## Record sheet

Fill this in while testing:

| Item | Result |
|---|---|
| Git commit | |
| Raspberry Pi OS version | |
| Ollama version | |
| Qwen model tag | |
| whisper.cpp model | |
| Software gate | Pass / Fail |
| Qwen benchmark | Pass / Fail |
| Simulation service and CLI | Pass / Fail |
| HTTPS browser and exclusive lease | Pass / Fail |
| Tavily search | Pass / Fail / Not configured |
| Temporary camera preview | Pass / Fail |
| USB microphone transcription | Pass / Fail |
| English browser speech | Pass / Fail / Browser unsupported |
| Japanese browser speech | Pass / Fail / Browser unsupported |
| Raised-wheel direct controls | Pass / Fail |
| Emergency Stop and Resume | Pass / Fail |
| Heartbeat-loss stop | Pass / Fail |
| Natural-language motion | Pass / Fail |
| Highest temperature | |
| Final `vcgencmd get_throttled` | |

## A. Safe software and simulation tests

These checks do not intentionally access physical robot hardware.

### A1. Install the locked environment

```bash
cd "$HOME/NinjaRobotPi5"
git status --short
uv sync --frozen --extra hardware
```

Expected result: dependency installation completes. Do not discard local files
if `git status` shows work that you want to keep.

### A2. Run the complete software gate

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python -m compileall .
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy .
uv run --frozen pytest -q
node --check \
  ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js
git diff --check
```

Expected result:

- immutable-driver verification passes
- compilation, Ruff, strict mypy, and JavaScript syntax pass
- all tests pass
- `git diff --check` prints no whitespace errors

The implementation workstation result was 259 passing tests and strict typing
across 55 V4 source files. Your count may be higher after later additions, but
it must not be lower because of skipped or failed tests.

If this section fails, stop. Do not work around a failed gate with real
hardware.

### A3. Confirm Ollama and whisper.cpp

```bash
ollama --version
ollama list

test -x "$HOME/whisper.cpp/build/bin/whisper-cli"
test -f "$HOME/whisper.cpp/models/ggml-base.bin"
```

Expected result: `qwen3:4b` appears in the Ollama list, and both `test`
commands finish silently with exit status zero.

### A4. Run the Qwen3:4B acceptance benchmark

In terminal A:

```bash
cd "$HOME/NinjaRobotPi5"

uv run --frozen ninjarobot-agent benchmark ollama \
  --model qwen3:4b \
  --output "$HOME/.local/share/ninjarobot_pi5/benchmarks/qwen3-4b-latest.json"
```

In terminal B, monitor the Pi:

```bash
watch -n 2 'vcgencmd measure_temp; vcgencmd get_throttled; free -h'
```

Press `Ctrl+C` in terminal B after the benchmark finishes.

Acceptance requires all of these:

- first token in 15 seconds or less
- complete response in 30 seconds or less
- correct tool selection and arguments in at least 90% of benchmark cases
- peak total memory below 7 GB
- temperature below 80°C
- no undervoltage or thermal throttling
- no unsafe loop, repeated physical action, or malformed execution

Expected result: the report contains `"accepted": true`.

If it reports false, save the report and keep Qwen3:4B marked as a candidate.
Do not hide, round away, or manually change a failed metric. The agent
architecture can still be tested in simulation with a fake or slower model,
but Phase 5 model acceptance has not passed.

### A5. Start the simulated owner service

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start

uv run --frozen ninjarobot-agent status
```

Expected result:

- `"started": true`
- Ollama reports ready
- the IDE provider reports ready
- tools include `robot.camera.preview` and
  `robot.microphone.transcribe`

Run the same `service start` command again.

Expected result: it reports that the service is already running. It must not
create a second owner.

### A6. Test CLI reconnection, chat, and transcripts

```bash
uv run --frozen ninjarobot-agent chat \
  "Reply with one short friendly greeting and do not use a tool."

uv run --frozen ninjarobot-agent session list
uv run --frozen ninjarobot-agent session history local-cli
```

Expected result: text streams to the terminal and the user/assistant messages
appear in the history.

Open the interactive tool:

```bash
uv run --frozen ninjarobot-agent
```

Choose **Agent Status**, then **Quit CLI**.

Expected result: Quit disconnects that terminal, but this still succeeds:

```bash
uv run --frozen ninjarobot-agent status
```

### A7. Test built-in skills without executing tools

```bash
uv run --frozen ninjarobot-agent skill list
uv run --frozen ninjarobot-agent skill inspect offline-robot-check
uv run --frozen ninjarobot-agent \
  skill simulate offline-robot-check --input '{}'
uv run --frozen ninjarobot-agent skill inspect current-web-answer
uv run --frozen ninjarobot-agent \
  skill simulate current-web-answer \
  --input '{"query":"Raspberry Pi official news"}'
```

Expected result: both skills are bundled and read-only. Both simulations say
that no robot hardware or external MCP tool was executed.

### A8. Start and inspect the simulated HTTPS web interface

```bash
uv run --frozen ninjarobot-agent web start
uv run --frozen ninjarobot-agent web status
```

Open the printed URL from a desktop or mobile browser on the same LAN. If the
bare hostname does not resolve, try:

```text
https://ninjarobotpi5.local:8443/
```

Expected result:

- the browser shows a self-signed-certificate warning
- after you confirm it is your Pi, the controller loads
- status changes to **Controller active**
- chat, controls, and live activity are visible in mobile landscape and on a
  desktop browser

The certificate and key should exist with a private key mode of `600`:

```bash
stat -c '%a %n' \
  "$HOME/.config/ninjarobot_pi5/tls/agent-cert.pem" \
  "$HOME/.config/ninjarobot_pi5/tls/agent-key.pem"
```

### A9. Test the exclusive controller lease

Keep browser A connected. Open the same address in browser B on another
device.

Expected result: browser B is rejected. Its WebSocket network request has HTTP
status `423 Locked`; some browsers show only a generic connection failure.
Browser A continues controlling the simulation.

Refresh browser A once.

Expected result: it reclaims its lease using the short-lived reconnect token.
It must not create a second lease.

### A10. Test every web control in simulation

From browser A:

1. Press and release each D-pad direction.
2. Press A for Greeting.
3. Press B for Celebrate.
4. Press X for Emergency Stop.
5. Press Y, cancel the confirmation once, then press Y and approve it.
6. Press Camera and close the temporary preview.
7. Press USB Microphone, let the five-second simulated cycle finish, and
   confirm its text enters chat.
8. Select English and use Web Microphone.
9. Select Japanese and use Web Microphone.
10. Confirm chat responses and tool events appear in their separate panels.

Expected result: every robot action reports simulation. Y does nothing when
the dialog is cancelled. Web Microphone may report browser unsupported; this
is a browser limitation rather than a robot failure, but test a current
Chrome, Edge, or Safari version before recording that exception.

### A11. Test heartbeat loss without hardware

While a simulated forward movement is active, turn off Wi-Fi on browser A or
close it without pressing a stop button. Wait 20 seconds. Connect browser B.

Expected result:

- the old lease expires
- simulated motion stops without asking Ollama
- browser B can acquire a new lease

Reconnect browser A afterward. It must now be rejected while browser B owns
the lease.

### A12. Stop the web interface and service separately

```bash
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent status
```

Expected result: web status is stopped, while the agent status still works.

Then:

```bash
uv run --frozen ninjarobot-agent service stop
test ! -S "$HOME/.local/state/ninjarobot_pi5/agent.sock"
```

Expected result: the service stops and the socket is removed.

## B. Device communication and privacy tests

These checks open real camera, microphone, I2C, SPI, and GPIO resources.
They do not intentionally move the wheels until Section C.

### B1. Recheck Phase 4 hardware health

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status --real
```

Expected result: configured devices report ready and both wheel calibration
records exist. If any device is unavailable, repair it with its standalone
`pi5*` tool before starting the agent.

### B2. Start the real owner service

Make sure no `ninjarobot-ide-tool` or standalone hardware tool is still open.
Then run:

```bash
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start --real

uv run --frozen ninjarobot-agent status
uv run --frozen ninjarobot-agent web start
```

Expected result: one service owns the IDE and the web URL opens.

### B3. Test temporary real camera preview

Tell everyone nearby. Before pressing Camera:

```bash
find "$HOME/.local/share/ninjarobot_pi5/camera" \
  -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort
```

Keep that output. Press Camera once in the browser.

Expected result: a correctly oriented temporary image appears and clears from
the browser after about 15 seconds or when closed.

Run the same `find` command again.

Pass condition: no new retained JPEG remains. A new file means the privacy
cleanup failed; stop the service and preserve the filename for investigation.

### B4. Test real USB microphone transcription

Tell everyone nearby. Before pressing USB Microphone:

```bash
find "$HOME/.local/share/ninjarobot_pi5/microphone" \
  -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort
```

Select English, press USB Microphone, and say a short English sentence. Repeat
with Japanese.

Expected result:

- recording stops automatically after five seconds or immediately when the
  button is pressed again
- local whisper.cpp returns text
- the text is submitted to the local agent
- no temporary WAV remains after either run

Repeat the `find` command. A new `transcribe-*.wav` file is a failure.
Recognized text is an ordinary chat message and remains in the seven-day local
conversation history unless that session is cleared.

### B5. Test browser microphone languages

This uses the microphone of the phone or desktop, not the robot's USB
microphone.

1. Select English, approve the browser microphone permission, and speak.
2. Confirm recognized English text enters chat.
3. Select Japanese and repeat.

Expected result: the browser sends recognized text, not an audio file. Browser
speech services may use the browser vendor's network service; this is separate
from the local USB-microphone workflow.

### B6. Configure and test Tavily web search

If you want real-time search, stop the current service, then:

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen ninjarobot-agent secret set TAVILY_API_KEY
uv run --frozen ninjarobot-agent \
  mcp add --preset tavily --id tavily
uv run --frozen ninjarobot-agent mcp health tavily
uv run --frozen ninjarobot-agent mcp tools tavily
uv run --frozen ninjarobot-agent \
  mcp test tavily --tool tavily-search \
  --arguments '{"query":"Raspberry Pi official news","max_results":3}'
```

Expected result: only `tavily-search` is allowlisted, the key is never printed,
and the harmless test returns source URLs.

Restart the real service so it owns the configured MCP connection:

```bash
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start --real
uv run --frozen ninjarobot-agent web start
```

Ask:

```text
Search the web for the latest official Raspberry Pi news and include direct
source links.
```

Pass condition: the answer uses the search tool and includes sources. If the
model does not select the correct tool, record a model tool-calling failure;
do not manually rewrite the result as a pass.

For an optional network-loss test, temporarily block only internet access at
the router while keeping the LAN and SSH connection active. Repeat the search.
The agent must report that current information could not be verified, must not
loop retries, and must not move the robot. Restore internet afterward.

## C. Actuator-moving tests

These tests move the MG90D continuous-rotation wheel servos.

### C1. Prepare raised wheels and shutdown fallback

Confirm:

- both wheels are raised
- the front sensor faces open space
- browser X is visible
- the second SSH terminal still has `ninjarobot-agent service stop` ready
- power is stable:

```bash
vcgencmd get_throttled
```

Expected result before movement: `throttled=0x0`.

### C2. Test each direct D-pad control

Press and hold each direction for about one second, then release:

1. Forward
2. Backward
3. Turn Left
4. Turn Right

Expected result:

- movement begins without a confirmation dialog
- release requests stop
- the face and related behavior run
- forward movement still uses the three-clear-reading startup guard
- three consecutive readings at or below 100 mm cause a Level 1 motion stop

If a wheel direction is wrong, stop. Correct the logical motor mapping or
calibration; do not reverse live wiring.

### C3. Test Level 2 Emergency Stop and Resume

Start one D-pad movement and press X.

Expected result:

- both motors stop
- sensors and active behavior work stop
- the buzzer becomes silent
- the display shows the Emergency Stop sign
- the action does not wait for an Ollama response

Press a D-pad button again before resuming.

Expected result: motion remains blocked.

Press Y, cancel its dialog, and try again.

Expected result: nothing resumes.

Press Y and confirm.

Expected result: modules are reconstructed and health-checked, the prior
movement does not restart, and new direct movement becomes available.

### C4. Test Greeting and Celebrate

Press A.

Expected result: Greeting runs without wheel movement.

Press B with wheels raised.

Expected result: Celebrate runs its short wheel dance without another
confirmation dialog. X must interrupt it immediately.

### C5. Test natural-language session arming

Press **Arm AI motion** and cancel once.

Expected result: chat motion remains disarmed.

Press it again, read the warning, and confirm. Ask:

```text
Move forward now.
```

Expected result: the model selects the validated movement tool only once. Press
X after about one second. The movement and chat tool call must terminate
without a duplicate action.

If the model calls the wrong tool, repeats motion, or cannot produce a bounded
tool call, fail the Qwen tool-reliability check even if direct controls work.

### C6. Test real heartbeat-loss stop

This intentionally allows raised wheels to turn for up to about 15 seconds.
Do not perform it with wheels touching the floor.

Start Forward, then turn off Wi-Fi on the controlling browser device.

Expected result: the server misses heartbeats, revokes the controller lease,
and stops both motors without waiting for Ollama. Record the observed stop
time. Restore Wi-Fi, connect again, and verify a new lease can be acquired.

## D. Power-risk and sustained-load checks

The local model and servos can stress power and cooling together.

With wheels raised, monitor in terminal B:

```bash
watch -n 2 'vcgencmd measure_temp; vcgencmd get_throttled; free -h'
```

In the browser, run several text-only questions, one Greeting, and one short
direct movement.

Pass conditions:

- temperature remains below 80°C
- `vcgencmd get_throttled` remains `0x0`
- the service stays responsive
- no out-of-memory termination occurs
- undervoltage stops servo movement as designed

If undervoltage appears, stop movement, stop the service, inspect the official
power supply, X1208, connectors, and servo load, and do not continue until the
power fault is corrected.

## Rollback and recovery

For an ordinary problem:

```bash
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent service stop
```

To return to hardware-free operation:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  service start
```

If a Level 1 obstacle stop remains latched, stop the agent service first, then
use the IDE recovery command:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" motion resume --confirm
```

If a driver-failure Level 2 state remains latched:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" system resume --confirm
```

Never run this recovery tool while the real agent service still owns hardware.

## Final pass criteria

Phase 5 can be marked operator-validated only when:

- the full software gate passes
- the saved model benchmark is accepted
- CLI reconnect, history, and separate shutdown semantics pass
- one HTTPS browser owns control and a second receives `423 Locked`
- refresh recovery and heartbeat-loss motion stop pass
- camera preview and USB transcription leave no media behind
- English and Japanese browser speech are tested or a specific unsupported
  browser is recorded
- Tavily health and one sourced search pass when web search is enabled
- direct controls, Emergency Stop, Resume, Greeting, and Celebrate pass with
  raised wheels
- one armed natural-language motion uses exactly one correct tool call
- temperature, memory, and power stay within the approved thresholds
- all failures and untested items are recorded honestly

Until then, Phase 5 is software-complete but not Raspberry Pi
operator-validated.
