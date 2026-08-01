# Agent long-run hardware stability Raspberry Pi validation

## 1. Scope

This checklist validates the permanent repair for display and buzzer loss in
both terminal and web chat. It covers lightweight startup readiness, one
Greeting followed by supervised Idle, cancellation-safe face transitions,
visible diagnostics, explicit Level 2 recovery, and a long-running soak. The
automated suite validates forced display/buzzer reconstruction with fakes; do
not unplug a powered SPI, GPIO, I2C, camera, or USB device merely to create a
physical fault.

Use the checkout that contains the changes. If testing a separate clone, first
pull or copy the reviewed patch into that clone; private state under
`~/.config/ninjarobot_pi5` and `~/.local/state/ninjarobot_pi5` is shared across
clones.

## 2. Safety and prerequisites

- Stop every standalone `pi5*` process and any other integrated agent/IDE
  process. Only one process may own the hardware.
- Do not delete `safety.json` or the hardware ownership lock.
- The safe smoke tests below do not access hardware.
- The real status probe initializes communication but does not intentionally
  move a servo, play a tone, photograph, or record.
- Real service startup illuminates the display and plays the bounded Greeting
  melody. Greeting contains no wheel movement.
- Keep AI motion disarmed for the stability soak. Raise and secure the robot
  before any optional servo test.
- Stop immediately for unusual heat, repeated electrical noise, uncontrolled
  motion, undervoltage, or a burning smell.

## 3. Safe smoke tests

From the active checkout:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen ruff format --check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
git diff --check
```

Expected: all commands pass; immutable verification reports 222 tracked files
and 25 authorized repairs. No managed driver hash changes.

Confirm that no previous owner remains:

```bash
uv run --frozen ninjarobot-agent service stop || true
pgrep -af 'ninjarobot|pi5disp|pi5servo|pi5buzzer|pi5camera|pi5mic' || true
```

Expected: no old agent, IDE, or standalone driver process remains. Ignore the
short-lived `pgrep` command itself.

## 4. Device communication tests

Run the non-moving integrated probe:

```bash
env -u VIRTUAL_ENV uv run --frozen --extra hardware \
  ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  hardware status --real
```

Expected: configured display, buzzer, servo, distance, camera, and microphone
boundaries report ready. Stop here and correct ownership, wiring, permissions,
or configuration if any boundary is unavailable.

Start the real agent once:

```bash
env -u VIRTUAL_ENV uv run --frozen --extra hardware \
  ninjarobot-agent \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  service start --real
```

Expected:

- Greeting runs once and returns to looping silent Idle.
- Top-level `started` and `ready` are `true` when no latch exists.
- `status.operational_state` is `ready`.
- `status.robot.liveliness.state` is `running`, with
  `idle_task_running: true` and `idle_error: null`.
- Startup does not flood the service log with repeated model-list or IDE-health
  probes.

Check status and the log without running a hardware action:

```bash
uv run --frozen ninjarobot-agent service status
tail -n 120 "$HOME/.local/state/ninjarobot_pi5/agent-service.log"
```

Expected: status remains ready and the log contains no `DISPLAY_*`, `BUZZER_*`,
`Idle face supervisor stopped unexpectedly`, or repeated startup polling
errors.

## 5. Non-moving web and terminal transition soak

Keep `/arm` unused. In terminal chat, send 25 short text-only questions. Mix
fast consecutive questions with pauses. Expected for every turn: Idle changes
to Thinking and Speaking or an allowlisted emotion, then returns to Idle.

Start the web controller and repeat 25 text-only chat turns:

```bash
uv run --frozen ninjarobot-agent web start
```

Use direct Greeting and Celebrate controls five times each, but do not touch
the D-pad. Every foreground behavior must finish and return to Idle. Then leave
the service running for at least 30 minutes, sending one terminal or web
text-only turn every two minutes.

Every five minutes run:

```bash
uv run --frozen ninjarobot-agent service status
```

Expected throughout:

- `ready: true` and `operational_state: ready`;
- `robot.liveliness.state` returns to `running` between interactions;
- no blank/frozen display, overlapping/corrupt frames, lost buzzer, or repeated
  Greeting;
- no Level 2 latch, Idle error, traceback, or continuously repeated provider
  health request in the service log.

If a real driver fault occurs naturally, do not restart or delete state. Save
status and logs first, then enter `/resume` and confirm. For a `DISPLAY_*`
fault, the screen may briefly clear black while the fresh backend write is
validated. Expected: recovery clears the latch only if every module and the
display write probe pass; Idle returns; AI motion remains disarmed. A failed
probe must leave `recovery_required` and the original fault detail intact.

## 6. Actuator-moving tests

The stability repair does not require servo motion. Mark this section not run
unless motion validation is independently required.

For an optional check, raise and secure the wheels, verify an accessible
software Emergency Stop, enter `/arm`, confirm with `ARM`, request one short
low-speed movement, and enter `/disarm` immediately afterward.

Expected: only the bounded requested movement runs; display/buzzer presentation
returns to Idle; disarm prevents repetition. Any unexpected movement is a
failure requiring immediate Emergency Stop and service shutdown.

## 7. Power-risk tests

Do not induce undervoltage. Before Greeting soak and before optional movement:

```bash
vcgencmd get_throttled
```

Expected: `throttled=0x0`. A nonzero current-undervoltage condition fails the
test; stop the service and correct the approved power chain before continuing.

## 8. Pass/fail record

| Check | Result | Notes |
|---|---|---|
| Immutable drivers and full software gate | Pass / Fail | |
| Single hardware owner | Pass / Fail | |
| Non-moving device communication | Pass / Fail | |
| Greeting once, then supervised Idle | Pass / Fail | |
| Terminal 25-turn transition soak | Pass / Fail | |
| Web 25-turn transition soak | Pass / Fail | |
| 30-minute mixed-interface soak | Pass / Fail | |
| Status remains ready between turns | Pass / Fail | |
| No display overlap, freeze, or blank loss | Pass / Fail | |
| Buzzer remains available | Pass / Fail | |
| Natural-fault confirmed recovery, if observed | Pass / Fail / N/A | |
| Optional raised-wheel movement | Pass / Fail / N/A | |
| Power status safe | Pass / Fail | |

Record operator, date/time, Pi model, OS/kernel, repository commit, wiring
revision, configuration path, power supply, actual status excerpts, and log
path with this table.

## 9. Rollback

1. Disarm motion, press Emergency Stop if needed, and stop the service:

   ```bash
   uv run --frozen ninjarobot-agent service stop
   ```

2. Preserve `agent-service.log`, service status, and `safety.json` for diagnosis.
3. Deploy the previous reviewed repository revision. Do not mix files from two
   clones and do not modify managed drivers.
4. Run the non-moving real hardware-status probe again.
5. If a Level 2 latch remains, use the reviewed revision's explicit confirmed
   Resume only after all health problems are corrected. Never delete the latch
   to make rollback appear successful.
