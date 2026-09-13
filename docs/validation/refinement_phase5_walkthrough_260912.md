# Phase 5 walkthrough and manual tests

Updated 13 September 2026.

Phase 5 adds an optional hand-distance game and subtle, silent conversational
face variations. It also evaluates four future hardware options without installing
them. Phase 4 has not been implemented. Use a terminal on Raspberry Pi OS Lite;
no desktop is required. Automated results are in the
[handoff](refinement_phase5_handoff_260913.md).

## What the game does

Move a hand 5–60 cm in front of the distance sensor. Nearer gives a higher short
buzzer tone. The display shows NEAR, MIDDLE or FAR. The default session is
30 seconds; allowed sessions are 5–60 whole seconds. It never commands wheels,
camera, microphone or system power. It uses the passive buzzer, not a Bluetooth
speaker. Outside the game area it becomes silent; roughly two seconds without
usable readings ends the session. It never restarts automatically.

Start, stop and status all go through the running Agent's existing IDE (the layer
that coordinates devices). Do not launch a second hardware-owning IDE process.
Stop Game works from another terminal or the web controller while the start
command or chat is waiting.

## 1. Safe software checks — no devices

Run these from the project folder. They use simulated devices and temporary test
state; they do not contact your running robot or model provider:

```bash
cd ~/NinjaRobotPi5
uv run --frozen --no-sync pytest -q ninjarobot_pi5_ide/tests/test_phase5_foundations.py ninjarobot_pi5_ide/tests/test_distance_game.py ninjarobot_pi5_agent/tests/test_game_controls.py
uv run --frozen --no-sync ninjarobot-agent game --help
uv run --frozen --no-sync ninjarobot-agent skill validate ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/distance-game
```

Expected: all selected tests pass, help lists start/stop/status, and the skill is
valid. Tests cover bad/stale readings, cancellation ownership, output limits and
independent controls. A simulated test cannot prove a real speaker is audible or
a sensor meets the timing limit.

## 2. Enable the optional settings

First record which method manages your Agent. These commands only inspect it:

```bash
systemctl show ninjarobot-agent.service -p LoadState -p ActiveState -p User
uv run --frozen --no-sync ninjarobot-agent service status
```

If your existing installation uses another configuration path, use that same path
in every step below. Do not create a second configuration by accident.

Stop the existing service before editing configuration. These operations can stop
hardware already in use. Keep the robot stationary with wheels raised and an
operator ready to disconnect power. Use **one** matching method:

- For the installed system service: `sudo systemctl stop ninjarobot-agent.service`
- For a service started by the Agent CLI: `uv run --frozen --no-sync ninjarobot-agent service stop`

Back up the private file without printing its contents, then open it:

```bash
cp -n ~/.config/ninjarobot_pi5/config.toml ~/.config/ninjarobot_pi5/config.toml.before-phase5
nano ~/.config/ninjarobot_pi5/config.toml
```

Add the following sections only if absent. If present, edit their existing values;
TOML (the configuration file format) does not allow duplicate sections:

```toml
[interaction_variations]
enabled = true

[distance_game]
enabled = true
volume = 16
```

Either feature can be left `false`. Game volume must be an integer from 1 to 32;
16 is the proposed modest starting level, not a measured sound-pressure guarantee.
No existing tone's default volume changes. These settings alone produce no output.

Validate the file without touching hardware or printing provider settings:

```bash
uv run --frozen --no-sync python - <<'PY'
from pathlib import Path
from ninjarobot_pi5_ide import load_robot_config
config = load_robot_config(Path('~/.config/ninjarobot_pi5/config.toml').expanduser())
print('Configuration valid')
print('Game:', config.distance_game.model_dump())
print('Variations:', config.interaction_variations.enabled)
PY
```

Expected: configuration valid and the intended optional values. Fix errors before
starting. Restore individual settings from the backup if needed; preserve unrelated
provider, user, speaker and hardware configuration.

Start the existing service through **the same method**, with wheels raised:

- Installed system service: `sudo systemctl start ninjarobot-agent.service`
- Agent CLI: `uv run --frozen --no-sync ninjarobot-agent service start --real`

A non-default CLI configuration is supplied before `service`, for example
`ninjarobot-agent --config /path/to/your/config.toml service start --real`.
Existing startup behavior still applies. This guide does not install a boot service.
If startup fails, do not start another process; inspect the reported error first.

## 3. Inspect availability before output

```bash
uv run --frozen --no-sync ninjarobot-agent status
uv run --frozen --no-sync ninjarobot-agent game status
```

Expected: the service is running, required display/buzzer/distance capabilities
are ready, and game status says `enabled: true` and `state: idle`. Game status is
read-only and does not sample the sensor. A general service status can perform
existing health checks. Correct unavailable hardware before starting; do not
bypass its safety checks. `enabled: false` means the running configuration still
has the feature disabled, or the service has not loaded your edit.

## 4. First physical game — sensor, display and buzzer only

This step produces visible and audible output and reads the distance sensor.
Use a stable floor/work area, raise the wheels, keep away from desk edges and
leave the normal Emergency Stop available. No camera or microphone consent is
needed for the game itself. Do not enable voice input for this test.

In terminal A:

```bash
uv run --frozen --no-sync ninjarobot-agent game start --seconds 5
```

Immediately hold a hand about 10 cm in front of the sensor. Expected: NEAR and
short high tones. The command waits for the game to finish. It should finish
without wheel movement or a second game starting. The result includes an action
ID and, when local tasks are configured, a task ID.

The outer `status` reports whether the tool call completed. Inspect `data.state`
and `data.reason` for the game outcome: `finished`, `cancelled`, `unavailable` or
`faulted`. Do not interpret a completed call as proof you heard every tone.

## 5. Distance bands, silence and finite duration

Start a longer test:

```bash
uv run --frozen --no-sync ninjarobot-agent game start --seconds 30
```

1. Hold your hand near 10 cm: expect NEAR / 880 Hz (tone frequency).
2. Move to about 22 cm: expect MIDDLE / 660 Hz.
3. Move to about 45 cm: expect FAR / 440 Hz.
4. Hold near a boundary: feedback should not rapidly flicker between bands.
5. Move outside 5–60 cm: expect silence. After roughly two seconds of unusable
   readings the result should explain `readings_unavailable`.
6. Request another run explicitly and keep a usable target present until it ends.
   Confirm it ends at the selected duration, with no replay or lingering tone.

The filter uses a short median (middle value of recent readings) and a 2 cm
boundary margin to reduce jitter. Reads taking over 250 ms are rejected. The
current sensor timestamp describes driver completion, not independently measured
capture time. Measure actual latency and stop time on your Pi; the software
bounds are not a physical timing certification.

## 6. Independent stop and status

While a game is running in terminal A, use terminal B:

```bash
cd ~/NinjaRobotPi5
uv run --frozen --no-sync ninjarobot-agent game status
uv run --frozen --no-sync ninjarobot-agent game stop
uv run --frozen --no-sync ninjarobot-agent game stop
```

Expected: status returns during the run; stop ends only the game and its output;
repeated stop is harmless. Terminal A reports cancellation. Record how quickly
sound ends. No delayed game face or tone should return. A second `game start`
while one is active should be rejected, not queued.

Try an invalid request:

```bash
uv run --frozen --no-sync ninjarobot-agent game start --seconds 4
```

Expected: validation error and no game starts. Do not test failures by unplugging
live I2C wiring (the shared sensor bus).

## 7. Chat and natural-language skill

Open chat through the same service:

```bash
uv run --frozen --no-sync ninjarobot-agent chat
```

Enter these one at a time:

```text
/help game
/game status
/game start 5
/game stop
```

The slash commands do not need a model call. The start command waits, so use the
second terminal or web Stop Game button during a run. For natural conversation,
try “Play the distance game for 10 seconds.” The optional `distance-game` skill
explains the interaction and uses only game tools. A vague “let's play” may need
clarification. The selected model must be available for natural-language requests.

An explicit skill request is also available:

```bash
uv run --frozen --no-sync ninjarobot-agent chat --skill distance-game 'Play the distance game for 5 seconds.'
```

If local tasks are enabled, inspect `/tasks` in the same user/session. A run
should have an outcome and tool evidence. Cancellation or unavailable readings
must not be described as successful physical delivery. Stop/status queries do
not create repeated task records.

## 8. Web controls and busy chat

Open the already-paired web controller and refresh it to load the new assets.
Use Play game (30s), Stop Game and Game status. Start a run, then use Stop Game
before its response arrives. Repeat while a normal chat request is busy.
Expected: Stop Game is still available; no layout jump while typing or receiving
a long reply. The current browser lease (its control permission) remains required.
Try your usual phone size and landscape/portrait layouts.

Close the controlling browser during a run. Existing disconnect/lease cleanup
must end it; there must be no automatic replay on reconnect. Closing a terminal
connection for a direct game request also cancels its request. This does not
introduce microphone listening as a stop mechanism.

## 9. Speech, reminders and expression variations

Only test real Bluetooth speech after your existing Phase 3 output setup has
passed. Start a spoken reply through your usual chat, then request a short game
from another terminal. Expected: output coordination stops/drains speech first;
no queued speech resumes over the game. Speech controls and text remain usable.

Separately create a short, explicitly reviewed display/buzzer reminder through
the existing `/remind-json` workflow in the [Phase 2 walkthrough](refinement_phase2_walkthrough_260909.md).
Confirm its exact task ID, then start a game before it is due. Expected: the game
ends and the approved reminder retains its usual notification behavior. Do not
change an unrelated personal reminder to perform this test.

For variations, ask for several cheerful or excited responses during ordinary
chat. Happy, laughing, excited and shy conversational faces may use a slightly
dimmer reviewed palette. Their meaning and shape stay the same; no new sound or
movement is added. Selection is stable within a presentation request. Named
behaviors, custom definitions, idle, startup, warnings and privacy cues remain
unchanged. The model may choose a different emotion; automated palette tests
verify the deterministic selection independently of model behavior.

## 10. Emergency, actuator and power checks

During a short game, use the existing web Emergency Stop. Expected: game output
ends and the safety indication remains authoritative. Game status/stop remain
available, but new output is blocked. Only after correcting the issue, use the
normal Resume control or `/resume`. It runs health checks and does not restart
the game or re-arm motion. If cleanup cannot be confirmed, stop testing and follow
existing safety guidance; disconnect power if an actual hazard demands it.

No wheel movement is required for Phase 5 acceptance. Automated tests use fake
movement/output arbitration. A real movement regression is optional and requires
separate operator consent, raised wheels and a clear area: one existing bounded,
armed movement should cancel the game first and preserve existing interlocks.
Do not use a tabletop edge as a test site.

Camera/microphone capture, live shutdown, boot edits, UPS testing, new wiring and
hardware prototypes are not required. Those tests need separate consent and a
specific procedure. The [hardware evaluation](../../DevelopmentPlanDoc/hardware/HardwareOptions_260912.md)
is documentation only.

## Results checklist and rollback

Record PASS, FAIL or NOT RUN for each category. Do not mark skipped hardware
steps as passed:

- [ ] Safe software tests and configuration validation pass.
- [ ] Display, buzzer and distance communication are ready.
- [ ] Near/middle/far, invalid-reading silence and finite duration work.
- [ ] Independent status/stop work; measured stop latency: ______.
- [ ] No wheel movement, capture, replay or stale game output occurs.
- [ ] Emergency stop and explicit recovery work.
- [ ] Speech/reminder interaction passes, or is recorded as NOT RUN.
- [ ] Web controls remain usable during chat and after reconnect.
- [ ] Optional visual variations are acceptable.
- [ ] Actuator-moving test: NOT RUN unless separately authorized.
- [ ] Power-risk/capture/prototype tests: NOT RUN.

Rollback: stop the game, stop the existing Agent, set both optional `enabled`
values to `false` and restart using the same service method. Keep unrelated
configuration and user data. The distance ownership repair remains useful with
the game disabled; do not revert to overlapping reads to hide a sensor problem.
A sensor worker that never returns cannot safely be killed by Python. If explicit
resume reports unresolved work, keep movement stopped and seek service recovery.
Do not start a second hardware owner or repeatedly retry the sensor.
