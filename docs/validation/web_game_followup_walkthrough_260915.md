# Web movement and repeated-game repair: walkthrough

The follow-up repairs are implemented. The owner retested web movements and
obstacle recovery without needing Resume. Three real distance games completed
successfully, with a Stop command between runs; the owner confirmed sound and
display output on all three. No memory or private configuration was cleared.

## What caused the remaining failures

### Web movement was rejected before sensor recovery

The live action ledger (the record of requested robot actions) showed a cancelled
movement followed by repeated `ACTION_ADMISSION_FAILED` results with the message
`distance recovery required before movement`. The running robot reported no
motion or system safety latch (a saved stop requiring recovery), and Idle was
running. This reproduction was therefore not an Emergency Stop.

A game-related admission check inspected the distance adapter's temporary
recovery flag and rejected movement before `MotionController` could recover it.
The standalone IDE route did not have that admission check, explaining why the
owner's IDE tests passed while web movements became blocked.

The redundant check is removed. The controller still waits for owned sensor work
to finish and checks health under its movement lock. Unfinished work is not
reused concurrently, and genuine faults remain protected. The web controller now
publishes failed background movement results; the browser displays a notification
and an activity message instead of silently discarding the failure.

### Normal game cleanup released the buzzer

The managed buzzer's `off()` method stops sound, releases resources, and sets
`is_initialized` to false. Game cleanup calls that method. The next game checked
health before initializing the buzzer again, so it reported `buzzer: degraded`.

Each game now calls the existing silent initialization before its health checks.
This follows the same lifecycle as an ordinary tone request. A failed hardware
initialization still reports unavailability; health checks are not bypassed.
The game tool description and bundled skill explain that a new explicit request
uses fresh device checks. An earlier failure in chat is not a permanent refusal.
Automatic retries of the same failed request remain forbidden.

### Slow cleanup could also cause a false watchdog stop

An additional software reproduction found that an ordinary stop ended the
watchdog heartbeat before device cleanup finished. A responsive cleanup lasting
longer than the watchdog timeout was then mistaken for a stalled control loop.

The heartbeat now continues until its owning context closes the watchdog and
cancels the heartbeat task. Tests confirm that slow responsive cleanup creates
no latch, while an actually blocked simulated event loop still triggers the
watchdog. This was a separately reproduced defect, not the cause recorded for
the owner's live web admission rejection.

## Validation evidence

| Check | Result |
| --- | --- |
| Root pytest suite | 914 passed; one pre-existing wiki-checkpoint failure; 41.86 seconds |
| Ruff lint and formatting | Pass; 447 files formatted correctly |
| mypy | Pass; 112 source files |
| Python compilation | Pass |
| Web JavaScript syntax | `node --check` passed |
| Immutable-driver verifier | Pass; 222 managed files, existing 56 authorized repairs |
| Workspace-source verifier | Pass; all six managed libraries load from this checkout |
| Relevant standalone driver suites | 273 passed in separate processes: buzzer 68, servo 134, distance 71 |
| Skill and game checks after guidance updates | Pass: eight skill/game tests and 43 game/control tests |
| Documentation links and whitespace | 187 local links resolve across eight documents; `git diff --check` passed |
| Focused regressions | Buzzer restart/failure, movement admission after cancelled sensor work, visible background failures, responsive cleanup, and real simulated-loop stalls pass |
| Live web tests | Owner confirmed all requested movements and obstacle-clearance tests passed without Resume |
| Live distance games | Three five-second runs finished; valid sample counts 19, 22, 22; no unavailable-device errors |
| Audible/visible game output | Owner confirmed tones and display on every run |

Each live game was followed by `game stop`. Game durations reported 5.085, 5.086,
and 5.086 seconds including cleanup. Small numbers of rejected samples were
handled normally. Tone request totals were 0.60, 0.66, and 0.66 seconds. The owner
confirmed hearing them; successful tool status alone was not treated as proof
of audible output.

The root failure remains
`test_real_public_checkpoint_and_missing_checkout`. The runtime project-help
manifest pins older wiki hashes that no longer match local pages. This predates
the repair. Its manifest was not changed to conceal the failure; the complete
root gate is not entirely green. Wiki ingestion and review remain deferred.

No managed driver, dependency, system-service definition, hardware interface,
stored conversation, or private configuration was changed. The existing real
Agent was restarted to load the fixes. Hardware tests were performed with the
owner supervising and the wheels raised. No deliberate power fault, camera
capture, microphone recording, memory reset, or shutdown test was performed.

## Step 1: Non-moving checks

On Raspberry Pi OS Lite, open a terminal in your checkout:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen --no-sync ninjarobot-agent service status
uv run --frozen --no-sync ninjarobot-agent game status
```

Expected: the existing Agent is running and game status is readable. Status is
a record of the last game, not a new hardware test. An old `unavailable` result
does not by itself mean another explicitly requested game cannot work.

After updating code, restart through the same manager that owns your Agent.
For a manually started service, with movement stopped:

```bash
uv run --frozen --no-sync ninjarobot-agent service stop
uv run --frozen --no-sync ninjarobot-agent service start --real
```

Starting in real mode initializes configured hardware. If systemd manages the
Agent, use that existing service's restart procedure instead. Never start a
second hardware owner. Refresh/reconnect the web controller after restarting.

## Step 2: Web movement and obstacle checks

These steps move servos. Secure the robot with both wheels raised and keep an
operator ready to remove power. The front distance sensor cannot protect the
rear, sides, or table edges.

1. Connect your normal web controller and enable its usual movement controls.
2. Briefly press and release forward, backward, left, and right. Repeat several
   times. Expected: each release stops the old movement; subsequent movement
   commands work without Resume.
3. During a brief movement, place a flat target within the configured threshold,
   normally 50 mm, in front of the sensor. Expected: movement stops and a
   confusing face and obstacle message appear.
4. Keep the target nearby and try a new command. Expected: the obstacle check
   prevents another ramp after confirming the nearby target.
5. Clear the target to a measurable distance beyond the threshold. Issue a new
   command. Expected: movement works without Resume; the old command never
   restarts by itself.
6. If any movement is rejected, read the visible notification/activity message.
   Do not assume every rejected action is an Emergency Stop. Record its wording.

Explicit Emergency Stop still requires deliberate recovery. Genuine driver,
undervoltage, and control-loop failures still retain protective stopping.
Initial arming and privacy consent remain unchanged.

## Step 3: Repeated distance games

Stop movement testing first. These commands sample distance and use the display
and buzzer; the game never commands wheels or needs a Bluetooth speaker.
Hold a flat hand or target 5–60 cm from the sensor.

Run this sequence three times:

```bash
uv run --frozen --no-sync ninjarobot-agent game start --seconds 5
uv run --frozen --no-sync ninjarobot-agent game stop
uv run --frozen --no-sync ninjarobot-agent game status
```

Expected: every game finishes with changing distance bands and short tones.
Neither the second nor third run requires Resume, a feature flag, or a service
restart. The next game initializes a normally released buzzer automatically.
Invalid samples are silent; sustained invalid samples may end the game. Check
target position before treating that as a device failure.

Also stop a game before its five seconds expire, then explicitly start a new
one. Expected: the previous game stays stopped and the new request works.

## Step 4: Chat check without deleting memory

In your existing chat, make a new explicit request such as “Let's play the
distance game for five seconds.” Expect a fresh game attempt through its tool,
not an automatic replay of the previous request. The current tool result is the
evidence for availability. No memory reset is needed.

For a deterministic check that does not depend on language-model interpretation,
use `/game start 5`, then `/game stop`, then `/game start 5` in chat. A genuine
current hardware refusal must still be reported honestly; do not tell the Agent
to ignore it or repeatedly retry automatically.

## Acceptance and rollback

- [ ] Repeated web press/release and direction changes work without Resume.
- [ ] Obstacle stop and a new command after clearance work without Resume.
- [ ] Three games, with Stop between them, all produce sound and display output.
- [ ] A new game works after a cancelled game or stopped movement.
- [ ] Current movement errors are visible rather than silently discarded.
- [ ] Explicit Emergency Stop and genuine-fault recovery remain effective.

The first three items were confirmed by the owner during this repair. The last
items have software coverage and can be included in ongoing physical acceptance.
Do not deliberately undervolt the Pi or stall its live control loop. Power-risk
paths are tested with substitutes only.

If a problem returns, stop movement, record the exact failure text and test step,
and stop the application through its existing manager. Preserve safety state,
calibration, configuration, and memory. To roll back, restore only this repair's
tracked code changes from your known prior revision after preserving later
edits, then restart normally. Do not delete safety files or rewrite driver
baselines to suppress a failure.

Both READMEs link to full successor manuals under `raw/.../2026-09-15-03/`.
The registered wiki map and published pages remain unchanged. This documentation
pass does not claim wiki ingestion, semantic review, or publication.
