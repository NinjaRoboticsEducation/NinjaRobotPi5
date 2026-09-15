# Servo and distance recovery: walkthrough and manual tests

For the subsequent live web and repeated-game repairs, use the
[latest walkthrough](web_game_followup_walkthrough_260915.md). The record below
describes the earlier repair and its validation at that time.

The approved follow-up repair is implemented. This guide explains what changed,
what was tested in software, and how to check the real robot. Physical acceptance
is still pending; passing simulated tests does not certify wiring or motor power.

## What changed

An intentional servo interruption could previously be relabeled as a driver
failure, creating a latch (a saved stop requiring recovery). Normal stop commands
now notify the motion controller, and an expected driver interruption preserves
the original stop cause. This includes stops during servo preparation.

Obstacle checks run before a ramp and throughout movement. Three consecutive
fresh samples at or below the configured threshold, normally 50 mm, prevent or
stop movement. This applies to backward movement and direct servo commands too.
The robot shows a confusing face and supplies a message asking you to clear the
obstacle. After clearance, a new command works without Resume. The old movement
never restarts itself. Once an obstacle has been detected, a missing or stale
reading does not count as clearance. The front sensor cannot see rear or side
hazards. Existing configurations with a more conservative threshold retain it.

A cancelled distance read could previously leave healthy hardware unavailable.
The IDE now waits for its owned background work to finish, within a two-second
bound, and checks sensor health before reuse. It never starts overlapping reads
or treats an old result as a fresh sample. Game startup uses that recovery path;
failed recovery reports the affected device. No manual game enablement is needed.

The existing long-chat repair remains unchanged. A new regression test confirms
that a short turn can recover after an oversized turn without deleting stored
history or repeating a tool action. Character limits remain in force; they are
not exact token limits for every model.

Explicit operator Emergency Stop and genuine equipment faults still stop unsafe
work. A system hardware fault displays **Protective Stop**, rather than calling
it an operator Emergency Stop. Undervoltage, watchdog failures (missed timely
control updates), and unexplained driver interruptions still require recovery.
No managed driver, calibration, private configuration, or saved safety file was
changed. No service was restarted and no live motor command was run by this work.

## Software validation

| Check | Result |
| --- | --- |
| Immutable driver verification | Pass: 222 tracked files, existing 56 authorized repairs |
| Workspace driver-source verification | Pass: all six drivers load from this checkout |
| Python compilation | Pass |
| Ruff lint and formatting | Pass |
| mypy type checking | Pass: 112 source files |
| Root pytest suite | 906 passed, one pre-existing failure; 39.40 seconds |
| Separate managed-driver tests | 457 passed: servo 134, distance 71, display 65, buzzer 68, microphone 92, camera 27 |
| Documentation links | 185 local file links resolve across eight documents |
| `git diff --check` | Pass |
| Real motor, sensor, display, and web acceptance | Pending operator testing |

The remaining root failure is
`test_real_public_checkpoint_and_missing_checkout` in
`ninjarobot_pi5_agent/tests/test_phase4_help_skills.py`. Runtime project help pins
an older public wiki checkpoint; modified wiki pages fail its hash validation
and return no Bluetooth search result. This failure predates this repair and
also appears in the [earlier validation record](servo_chat_game_fixes_260915.md).
Its manifest was not refreshed to hide the failure. Correcting that published
knowledge checkpoint is separate work; wiki ingestion and review are deferred.
The complete root gate is therefore **not entirely green**.

Existing test warnings concern Starlette's HTTPX integration and the standalone
microphone suite's deprecated `audioop` module. No dependency change was made.

## 1. Preparation and safe smoke checks

Run commands from your existing checkout on Raspberry Pi OS Lite. Replace the
path if your checkout lives elsewhere:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen --no-sync ninjarobot-agent service status
uv run --frozen --no-sync ninjarobot-ide-tool hardware status
```

Expected: service ownership is clear and configuration loads. `hardware status`
without `--real` reads configuration rather than probing devices. These commands
do not request movement. Do not print or share private configuration or tokens.

An already running Agent must reload the changed code before testing. Use the
same service manager that started it. For a manually started Agent, stop it with:

```bash
uv run --frozen --no-sync ninjarobot-agent service stop
```

Expected: it exits normally. If systemd manages your Agent, stop/restart that
existing service through the installation guide instead; do not start a second
owner. A systemd service may restart automatically after an IPC stop request.

For a hardware-free movement preview, run:

```bash
uv run --frozen --no-sync ninjarobot-ide-tool behavior simulate move_forward --duration 1
```

Expected: simulated output, no physical movement, and no persistent stop.

## 2. Device communication and game checks

Risk: starting the real Agent initializes configured hardware; the game uses the
sensor, display, and buzzer. The game does not command wheels, capture a camera,
record a microphone, or require a Bluetooth speaker. Raise the wheels for initial
acceptance and keep the robot away from desk edges.

For a manual service owner only, start the real Agent once:

```bash
uv run --frozen --no-sync ninjarobot-agent service start --real
uv run --frozen --no-sync ninjarobot-agent game status
uv run --frozen --no-sync ninjarobot-agent game start --seconds 5
```

Expected: status reports `enabled: true`. During the game, move a flat hand or
target between 5 and 60 cm in front of the sensor. Distance bands appear and
nearer positions produce higher short tones. Invalid/out-of-range samples are
silent; sustained invalid readings can end the game. That is different from an
unavailable device.

Stop and restart the game using new commands:

```bash
uv run --frozen --no-sync ninjarobot-agent game stop
uv run --frozen --no-sync ninjarobot-agent game start --seconds 5
uv run --frozen --no-sync ninjarobot-agent game status
```

Expected: another game works without `/resume` or an enablement setting. Repeat
this after the movement tests below, where stopping can cancel a sensor read.
If recovery fails, record `reason`, `device_errors`, and any user message. Do not
open the standalone sensor tool while the Agent owns the hardware.

## 3. Web movement and obstacle tests

Risk: these tests move wheel servos. Secure the robot with both wheels raised.
Keep hands away from turning parts and an operator ready to remove power.
Use the existing paired web controller; do not expose another network port.

1. Enable the normal movement controls through the existing arming process.
   Arming is still required; the repair does not remove initial motion consent.
2. With the front area clear, press and release a direction briefly. Repeat for
   forward, backward, left, and right. Expected: ordinary release/direction
   changes stop the previous action without Emergency Stop or Resume.
3. While moving briefly, place a flat target within 50 mm of the front sensor.
   Expected: wheel output stops, the confusing face appears, and the controller
   receives a message asking you to clear the obstacle.
4. Keep the target there and try another direction. Expected: the pre-movement
   check prevents another ramp once the nearby obstacle is confirmed.
5. Remove the target to a clearly measurable distance beyond the threshold.
   Expected: the old movement stays stopped. Send a new direction command;
   it should work without Resume or additional obstacle confirmation.
6. Start another five-second game. Expected: no lingering unavailable-sensor
   state from the interrupted movement.
7. Press the explicit **Emergency Stop** button during a controlled movement.
   Expected: the operator stop remains in effect. Clearing the obstacle alone
   must not clear it. Use **Resume Robot Movement** or `/resume`, follow any
   reported health-check guidance, and re-arm where required by the controller.

Fail the test if motors continue through a confirmed obstacle, restart without
a new command, or an ordinary stop creates a persistent driver-failure latch.
Stop testing and record the cause if a genuine protective fault is reported.

## 4. IDE-tool movement checks

Risk: the interactive tool's normal hardware selections can move the robot.
Stop the Agent through its existing owner/manager first; confirm it remains
stopped. Do not run two independent hardware owners.

```bash
uv run --frozen --no-sync ninjarobot-ide-tool
```

1. Open **Hardware Configurations** and check the expected profile.
2. Open the movement menu and confirm one short, supervised movement with raised
   wheels. Repeat the obstacle/clearance sequence from section 3.
3. Expected: the confusing face and returned result explain the temporary stop.
   Clear the obstacle and issue a new movement; no Resume should be necessary.
4. Use the tool's explicit Emergency Stop function once and then its Resume
   function. Expected: this deliberate stop retains its separate recovery flow.
5. Exit the tool before starting the Agent again through its existing manager.

Direct endpoint actions through `servo.move` use the same guard and return
`stop_reason`, `latched`, and obstacle guidance. Their software integration test
also verifies that the servo driver is not called while the obstacle blocks it.

## 5. Chat regression check

With the Agent running, open your normal chat and continue an existing long
conversation with a short question. Expected: a reply using recent context,
without deleting older visible conversation or repeating past tool actions.

If an unusually large new message receives a budget error, send a short message
next. Expected: the next turn can recover when required context fits. Do not
raise the configured budget just to mask the error. Model calls use your normal
provider settings and may have the usual provider costs.

## Acceptance checklist and rollback

- [ ] Configuration and simulation checks pass without movement.
- [ ] Game starts, stops, and restarts without manual enablement or Resume.
- [ ] Normal movement/release/direction changes do not trigger a persistent stop.
- [ ] An obstacle stops movement with the confusing face and useful guidance.
- [ ] A new command works after clearance; no old command restarts itself.
- [ ] Game works after a stopped movement.
- [ ] Explicit Emergency Stop still requires deliberate recovery.
- [ ] Long chat and a short turn after a budget rejection work as described.

Power-risk tests are **not required** for this acceptance: do not deliberately
undervolt the Pi, stall its live control loop, or force shutdown. Those paths were
tested with substitutes, and protection remains enabled.

If a check fails, stop movement and stop the application through its normal
manager. Record the test step, stop reason, and sanitized error. Preserve
`safety.json`, calibration, private configuration, and user data. Restore only
the repair's tracked code files from your known prior revision after preserving
later edits, then restart through the same manager. Do not erase a safety latch
or rewrite managed-driver baselines to make a check pass.

The full successor manuals and development log are under the wiki's
`raw/.../2026-09-15-02/` folders and linked from both READMEs. No wiki ingestion,
semantic review, or publication was performed in this repair.
