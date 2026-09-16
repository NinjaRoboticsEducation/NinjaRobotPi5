# Distance game in web chat: diagnosis and manual tests

The repair separates a missing hand from a failed sensor and shows a starting
instruction in web chat before the game finishes. It preserves the existing
movement repair, Emergency Stop, device ownership, and real fault handling.
No managed drivers, dependencies, private configuration, or memories changed.

## What caused the problem

The owner confirmed they waited for the final chat reply before placing a hand
in front of the sensor. The game tool runs before that final reply. Its old
filter treated measurements outside the 5–60 cm playing area as failed readings,
and its loop stopped after two seconds without an accepted sample. The Agent
then described the outcome as trouble reading the sensor.

The saved action results support this explanation: web games reached execution
and passed device health checks, but ended after about 2.098 seconds with zero
accepted readings and 11 rejected samples. A 30-second terminal game also ended
with the same reason after 15 seconds, despite first accepting 62 samples.
The failure was therefore not exclusive to web connections. Older records did
not retain rejection categories, so the precise cause of every historical
rejected sample cannot be reconstructed.

## What changed

- A fresh measurement outside the playing area, including a healthy clear-space
  response, means silent waiting. A hand can enter later during the same game.
- A game with no hand detected finishes at its requested time and reports
  `no_target_detected`, with hand-placement instructions rather than a sensor
  unavailability claim.
- Real read errors, invalid data, repeated cached readings, and read timeouts
  still stop the game after two seconds without a healthy response. Existing
  freshness and tone limits remain in force.
- Results add `no_target_samples`, `rejection_counts`, and `last_sample_issue`.
  Existing `invalid_samples` still includes every sample rejected for tone
  generation. This counter alone is not evidence of a broken sensor.
- The natural-language Agent publishes a starting instruction before calling the
  game tool. The browser shows it directly in chat, without waiting for the
  final model answer. This notice says “Starting”; device checks can still refuse
  the request and the final result remains authoritative.
- The bundled distance-game skill explains timing and the different outcomes.

The implementation is in `distance_game.py`, `agent_loop.py`, `web_static/app.js`,
and the bundled distance-game instructions. Public contracts are preserved;
additional game-result fields are diagnostic information.

## Other modules and web routing

`WebRobotController.chat` delegates to the same Agent runtime used by other chat
clients. `IDEToolProvider` passes typed requests to the shared IDE (the layer
that owns devices); it does not choose different drivers for web sessions.
Review of recent device action results found successful web camera preview and
microphone transcription, one cancelled microphone operation, and successful
servo Stop requests. An older game rejection was an invalid mode argument,
followed by an accepted game request. These are not evidence of unavailable
hardware. No additional web-only availability gate was found in this path.

This is a code and log review, not physical validation of every module. No
camera/microphone capture or motor movement was initiated during this repair.

## Automated validation

| Check | Result |
| --- | --- |
| Focused game and Agent-loop tests | 86 passed |
| Full root suite | 925 passed; one existing wiki-checkpoint failure; 42.44 seconds |
| Distance-driver standalone tests | 71 passed |
| Ruff lint and formatting | Pass; 447 files |
| mypy type checks | Pass; 112 source files |
| Python compilation and JavaScript syntax | Pass |
| Managed-driver integrity | Pass; 222 files and 56 existing authorized repairs |
| Workspace driver sources | Pass; all six use this checkout |
| Documentation links and whitespace | Local file links checked; `git diff --check` passed |

The existing failure is
`test_phase4_help_skills.py::test_real_public_checkpoint_and_missing_checkout`:
the pinned public project-help checkpoint does not return a matching local page.
It also failed before this repair. Wiki ingestion, review, and fingerprint
refresh remain deferred; this unrelated failure has not been hidden.

Regression tests exercise a late-arriving hand, an absent hand, measurements
closer and farther than the playing area, the driver's no-target error, actual
read failure, stale/cached samples, and notification delivery before tool
execution. Existing stop, cleanup, repeated-buzzer, motion, web, and safety tests
are included in the root suite.

## Step-by-step manual tests

### Safe checks and loading the update

Run commands in the NinjaRobotPi5 checkout. Stop any ongoing user activity first.
For the manually started Agent used during this investigation, load the updated
code with:

```bash
uv run --frozen --no-sync ninjarobot-agent service stop
uv run --frozen --no-sync ninjarobot-agent service start --real
```

These commands stop and start the real hardware service. They do not install a
boot service. Refresh the browser and reconnect your usual controller. If your
installation instead uses a system service, use its documented restart procedure
rather than launching a second hardware owner.

### Device communication and game output

These tests use the distance sensor, display, and buzzer. They should not move
wheels or capture audio/video. Keep the robot stationary and the sensor clear.

1. In web chat, ask: “Play the distance game for 10 seconds.” Keep your hand away.
   Expect a starting instruction before the final answer. The game should stay
   silent for the requested duration. The final answer should explain that no
   hand was detected, not claim the sensor is unavailable.
2. Ask the same question again. When the starting notice appears, wait roughly
   three seconds, then hold your hand 10–30 cm in front of the sensor. Expect
   display feedback and short tones without restarting or using Resume.
3. Move your hand away for more than two seconds, then return it before the timer
   ends. Expect silence while away and tones when it returns.
4. Repeat twice. Expect no `buzzer: degraded` admission failure. Use **Stop Game**
   during one run; sound should stop promptly and a new explicit request should
   work.
5. Compare the command-line route, placing your hand before starting:

   ```bash
   uv run --frozen --no-sync ninjarobot-agent game start --seconds 5
   uv run --frozen --no-sync ninjarobot-agent game status
   uv run --frozen --no-sync ninjarobot-agent game stop
   ```

   Expect `finished`, a positive `valid_samples` count with the hand in range,
   and no device error. Stop after completion may retain the last finished result.
6. If any test fails, record the time, returned `reason`, `last_sample_issue`, and
   `rejection_counts`. Do not diagnose sensor failure from `invalid_samples` alone.
   Do not disconnect a powered sensor to manufacture a fault; automated tests
   already cover failures safely.

### Actuator-moving checks — optional and separate

No new motor behavior needs acceptance for this patch. To repeat the previous
movement regression, raise both wheels and have an operator ready to remove
power. Briefly press/release each direction. Expect normal stops and obstacle
recovery without Resume. Stop testing if behavior differs; preserve the result
and logs. Do not continue moving a robot with an unexplained protective fault.

### Power-risk checks

None required. Do not run shutdown, boot configuration, or power interruption
tests for this change.

## Acceptance and rollback

- [x] Automated no-target, delayed-hand, and failure regressions pass.
- [x] Existing shared runtime and device test coverage checked.
- [ ] Live web starting notice is visible before the final answer.
- [ ] Live absent-hand game finishes without a false sensor failure.
- [ ] Live late-hand and repeated games produce visible/audible feedback.

Live acceptance is pending the owner's test of this updated code. Previous
successful games and movement tests are not claimed as validation of this patch.
If rollback is needed, stop the Agent and restore only this repair's runtime
files from the preceding revision, then restart and refresh the browser. Preserve
private configuration and user data. No database or driver migration is needed.

Full manuals have new, unpublished 16 September successor sources. Both READMEs
link to them. Wiki ingestion and semantic review were deliberately not run.
