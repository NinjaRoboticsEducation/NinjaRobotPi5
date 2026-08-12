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
- 405 tests pass (or a documented later count with no regression)
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

   Expected: each switch is explicit; history shown after switching contains
   only the active user's messages. Switching revokes motion/camera grants.

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

7. Say “Please rename yourself to Ninja,” then ask its name again.

   Expected: a visible memory-saved notice appears and the answer uses Ninja,
   even if an older transcript message used another assistant name.

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

4. Run `/identify` with one registered face, no face, one unknown face, and two
   faces in view.

   Expected: only the unique known-face case switches. Every other case reports
   no switch and preserves the previous active user.

5. Temporarily disconnect/disable the camera and register a profile.

   Expected: profile creation succeeds with pending face status; chat, display,
   buzzer, and other hardware remain usable. Reconnect before continuing.

## Behavior capture tests

1. With motion disarmed, request a face + tone dynamic expression.

   Expected: technical success is returned, followed by “Do you want to record
   this new behavior?” Reply No; no successful behavior memory appears.

2. Repeat with a different expression and reply Yes.

   Expected: visible `Memory saved` notice and one `successful_behavior` entry
   containing the normalized request/result reference.

3. Induce a safe technical failure without moving hardware, for example by
   disabling the buzzer in a test configuration and requesting a tone.

   Expected: authoritative tool failure remains unchanged and one
   `failed_behavior` entry is created automatically. A policy denial alone must
   not be classified as technical hardware failure.

4. Say “I prefer blue face animations.”

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
- [ ] face full frames are absent after success, failure, and cancellation
- [ ] unknown/multiple faces never switch users
- [ ] profile deletion rejects active users and owners before transfer
- [ ] confirmed deletion removes messages, structured memory, face index/photo
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
