# Phase 7 persistent memory and identity validation

Date: 2026-08-12  
Branch: `alpha02`  
Hardware target: Raspberry Pi 5 / NinjaRobotPi5  
Implementation status: software gate passed; physical validation pending

## Scope

Validate Phase 7 without weakening existing hardware ownership, motion consent,
camera privacy, Greeting/Idle presentation, or provider behavior. The scope is:

- migration of an existing conversation database
- first owner and additional user registration
- IDE-owned face enrollment and explicit recognition
- strict active-user transcript/memory isolation
- successful and failed behavior capture
- bounded automatic and MCP retrieval
- deterministic profile/memory deletion and retention
- deterministic inactive-profile face recovery and full-memory reset
- exact face verification before terminal/web user switching
- restart, long-run responsiveness, database size, and permissions

No managed `pi5*` driver changed. The agent must continue to reach the camera
only through `ninjarobot_pi5_ide`.

## Safety prerequisites

- Keep the robot stationary; memory and face tests do not require servo motion.
- If any actuator test is attempted later, raise the wheels and keep the power
  disconnect within reach.
- Do not expose HTTPS port 8443 outside the trusted local network.
- Tell participants that profile enrollment stores a cropped face image and
  recognition data readable by the Raspberry Pi administrator.
- Back up the owner-only agent database before testing migration:

```bash
systemctl --user stop ninjarobot-agent.service 2>/dev/null || true
cp -a "$HOME/.local/share/ninjarobot_pi5/conversations.sqlite3" \
  "$HOME/.local/share/ninjarobot_pi5/conversations.sqlite3.phase7-backup"
```

If the source database does not exist, skip the backup command.

## Software gate (no hardware)

```bash
cd "$HOME/NinjaRobotPi5"
git branch --show-current
uv sync --frozen --extra hardware
uv run python scripts/verify_immutable_drivers.py
uv run python scripts/validate_face_recognition_backend.py
uv run python -m compileall -q .
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest -q
uv run python scripts/benchmark_agent_memory.py --entries 1000 --queries 50
```

Expected:

- branch is `alpha02`
- immutable check reports 222 tracked files and 26 authorized repairs
- face backend check reports OpenCV 4.x and a loadable Haar cascade
- compilation, Ruff, and mypy succeed
- 415 tests pass (or a documented later count with no regression)
- benchmark reports `passed: true`, p95 at or below 100 ms, and database size
  at or below 16 MiB

## Safe smoke tests

These tests do not move actuators.

1. Start in simulation and inspect memory tools:

   ```bash
   uv run ninjarobot-agent service start
   uv run ninjarobot-agent status
   uv run ninjarobot-agent memory settings
   uv run ninjarobot-agent skill inspect memory-retrieval
   ```

   Expected: status contains `memory.enabled: true`; `memory-mcp` is ready with
   four read-only tools; defaults are 7/180/1000 unless previously changed.

2. Open `uv run ninjarobot-agent chat` in a new database.

   Expected: first message asks for a name. Entering a name creates owner
   `local-user`. In simulation a face may remain pending, but chat continues.

3. Run `/new user`, enter a second name, then `/switch user` twice.

   Expected in simulation: a profile without an enrolled face cannot switch;
   the original user remains active and the response directs the operator to
   deterministic face recovery. History remains user-isolated.

4. Restart the service and open a new chat session.

   Expected: the current owner is selected by default, even if another user was
   active before shutdown.

5. Use the interactive **Manage Memory** menu to list profiles/settings.

   Expected: no secrets, face encoding, or other user's raw content is printed
   by the profile list.

6. Run `/update profile`.

   Expected: the current user name and registered/unregistered face state are
   shown. `name=<new name>` changes the user name. `robot_name=...` is rejected
   with guidance to rename NinjaAgent through ordinary chat.

7. Say “I want to call you Pocky, and please call me Master,” then ask its name.

   Expected: visible notices confirm both saved fields, the answer uses Pocky
   and naturally addresses the active user as Master, even if older transcript
   messages contain other names. Restart chat and repeat the questions; both
   values remain.

8. From **Manage Memory**, choose **Clean All Robot Memory**, but enter an
   incorrect confirmation phrase.

   Expected: the operation is cancelled and all profiles remain.

## Device communication tests (camera/display, no actuator motion)

1. Start real hardware:

   ```bash
   uv run --extra hardware ninjarobot-agent service start --real
   uv run ninjarobot-agent chat
   ```

2. Register a new user. Watch the display.

   Expected: the existing `3 → 2 → 1` countdown is visible; one camera capture
   occurs; exactly one face enrolls; the result returns to silent Idle.

   If enrollment fails, run `/update profile`, confirm the displayed face state,
   then enter `register user face`. Expected: another visible countdown starts;
   success enrolls/refreshes the face, while failure reports the cause and next
   step and still returns the display to silent Idle.

3. Verify data permissions and raw-frame cleanup:

   ```bash
   find "$HOME/.local/share/ninjarobot_pi5/faces" -type d -printf '%m %p\n'
   find "$HOME/.local/share/ninjarobot_pi5/faces" -type f -printf '%m %p\n'
   find "$HOME/.local/share/ninjarobot_pi5/camera" \
     -maxdepth 1 -name 'identity-*.jpg' -print
   ```

   Expected: directories are `700`, files are `600`, one cropped known-face
   photo/index exists, and no `identity-*.jpg` full frame remains.

4. Run `/switch user`, select another enrolled profile, and present that exact
   user's face.

   Expected: the countdown runs, Idle is restored, and the switch succeeds only
   for the exact selected profile. Repeat while showing a different registered
   face: the response reports a mismatch without naming that person, the
   original user remains active, and motion/camera grants are revoked. Repeat
   from both terminal chat and web chat.

5. Run `/identify` with one registered face, no face, one unknown face, and two
   faces in view.

   Expected: only the unique known-face case switches. Every other case reports
   no switch and preserves the previous active user.

6. Temporarily disconnect/disable the camera and register or switch a profile.

   Expected: profile creation succeeds with pending face status; chat, display,
   buzzer, and other hardware remain usable. Reconnect before continuing.

7. Select **Manage Memory → Register or Replace User Face** for an existing
   inactive profile.

   Expected: the countdown runs without switching the active chat user; success
   makes the profile eligible for verified switching and returns to Idle.

8. Back up the database and face directory, then select **Clean All Robot
   Memory** and type the exact confirmation phrase.

   Expected: all profiles and face files disappear, memory settings return to
   configured defaults, motion/camera grants are revoked, and the next chat asks
   for the new owner's name. Provider/model settings, saved IDE behaviors,
   calibration, and logs remain. Repeat with an induced database failure only
   in a disposable test environment; quarantined face data must be restored.

## Behavior capture tests

1. With motion disarmed, request a face + tone dynamic expression.

   Expected: technical success is returned, followed by “Do you want to record
   this new behavior?” Reply No; no successful behavior memory appears.

2. Repeat with a different expression and reply
   `Yes, name it "Pi validation smile"`.

   Expected: the reply reports both destinations, one `successful_behavior`
   entry contains the normalized request/result plus display/catalog names, and
   the private IDE catalog contains runnable `pi_validation_smile`. No model
   turn, `/confirm`, or nonexistent confirmation button is involved. Running
   the catalog entry later remains subject to normal motion/safety policy.

   Repeat once with `Yes and name this behavor "Pi typo smile"`. Expected: the
   exact quoted display label is retained and the catalog entry is
   `pi_typo_smile`; the typo does not discard the requested name.

3. Repeat a new successful expression, give it the same name, then retry with
   a unique quoted name.

   Expected: the existing catalog asset is not overwritten; the failed
   dual-save does not leave a successful memory and remains retryable. The
   unique-name retry saves both destinations.

4. Induce a safe technical failure without moving hardware, for example by
   disabling the buzzer in a test configuration and requesting a tone.

   Expected: authoritative tool failure remains unchanged and one
   `failed_behavior` entry is created automatically. A policy denial alone must
   not be classified as technical hardware failure.

5. Say “I prefer blue face animations.”

   Expected: chat continues and displays `Memory saved: preference.` Repeating
   the exact sentence does not create a duplicate.

## Read-only retrieval tests

```bash
uv run ninjarobot-agent skill simulate memory-retrieval \
  --input '{"query":"birthday behavior"}'
```

Expected: simulation lists only `memory.*` reads and no hardware/mutation tool.
Ask the agent about a saved behavior after switching between two users.
Expected: each user sees only their own profile and memories. Retrieved content
must never arm motion, authorize a camera, or override safety instructions.

Open terminal chat and web chat. Independently switch both to the same enrolled
user, save a behavior in one interface, and ask a generic “What do you remember
about my behaviors?” in the other. Then change the configured AI model and ask
again in the original session.

In the terminal, also say “I want to call you Pocky, and please call me Master.”
Ask “What is your name, and what should you call me?” in terminal, in the web
session after it independently selects the same user, and again after changing
the model/provider.

Expected: transcripts and active-user switching stay independent, while the
same user's profile and long-term memories are visible from both interfaces.
The model switch preserves the transcript and memory but revokes motion
authorization. Every interface/model answer uses Pocky and Master from
structured memory, not from the terminal transcript. Renew or reconnect the
same browser controller lease and verify that its transcript remains; a
different browser gets a different chat session.

## Actuator-moving tests (optional, separate authorization)

Phase 7 does not require motion. If validating a remembered movement:

1. Raise the wheels and confirm power/emergency-disconnect readiness.
2. Arm only the current chat session.
3. Execute one short bounded movement and save it after technical success.
4. Disarm, switch users, and verify the arm was revoked.

Expected: remembered parameters may guide planning, but the normal policy and
IDE safety checks still authorize and execute every movement. Memory never
executes an actuator directly.

## Power-risk tests

No new power-risk test is required. Face recognition adds CPU/camera load only.
During a 30-minute chat/identify/retrieval loop, monitor:

```bash
watch -n 5 'vcgencmd measure_temp; vcgencmd get_throttled'
```

Expected: temperature remains below the approved limit and `get_throttled`
does not gain new undervoltage/throttling flags. Stop if thermal or power faults
appear.

## Long-run pass/fail checklist

- [ ] 50 service restarts/migrations complete without database corruption
- [ ] 100 user switches show no cross-user transcript or memory
- [ ] 100 bounded retrievals remain responsive and within 4,000 characters
- [ ] same-user memory is consistent across terminal, web, and model changes
- [ ] robot name and form of address survive terminal/web/model changes
- [ ] terminal/browser transcripts and user switching remain independent
- [ ] browser lease reconnect preserves only that browser's stable chat session
- [ ] named confirmations save both memory and a runnable IDE catalog entry
- [ ] catalog collision preserves the original asset and remains retryable
- [ ] face full frames are absent after success, failure, and cancellation
- [ ] unknown/multiple faces never switch users
- [ ] selected-user switches require an exact face match in terminal and web
- [ ] mismatches retain the original user and reveal no other profile name
- [ ] inactive-profile face recovery never switches the active chat user
- [ ] profile deletion rejects active users and owners before transfer
- [ ] confirmed deletion removes messages, structured memory, face index/photo
- [ ] cancelled reset preserves all data; confirmed reset leaves no owner/data
- [ ] first chat after reset starts owner registration with default retention
- [ ] failed-behavior pruning enforces days and cap per user
- [ ] display/buzzer/servo behavior remains stable for the full run
- [ ] immutable-driver verification still passes

Pass only if every applicable item succeeds. Record measured p95 latency,
database size, temperature, and any recognition false-positive/negative count.

## Rollback

1. Stop the agent and web service.
2. Preserve the failed database and service log for analysis.
3. Restore the pre-Phase-7 database backup only while the service is stopped:

   ```bash
   mv "$HOME/.local/share/ninjarobot_pi5/conversations.sqlite3" \
     "$HOME/.local/share/ninjarobot_pi5/conversations.sqlite3.failed"
   cp -a "$HOME/.local/share/ninjarobot_pi5/conversations.sqlite3.phase7-backup" \
     "$HOME/.local/share/ninjarobot_pi5/conversations.sqlite3"
   ```

4. Check out the last known-good commit/branch; do not modify managed drivers.
5. Run immutable verification and simulation tests before restarting real mode.

Profile photos created after the backup are not restored by the database copy.
If rollback requires removing them, identify the exact user directory first and
move it to an owner-only quarantine directory rather than deleting broadly.
