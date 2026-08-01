# Agent startup readiness Raspberry Pi validation

## 1. Scope of validation

This checklist validates that the agent distinguishes a running process from a
robot that is ready, reports persistent safety latches after a reinstall,
waits for Greeting/Idle startup, logs the technical failure, and only recovers
through explicit health checks. It does not change any managed driver.

Use one checkout only during the test. The examples use the user's test path:

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
```

## 2. Safety notes

- Stop standalone `pi5disp`, `pi5servo`, `pi5buzzer`, camera, microphone, and
  IDE test programs before starting the integrated agent.
- Do not delete `~/.local/state/ninjarobot_pi5/safety.json`.
- `hardware status --real` initializes device communication but does not
  intentionally move servos, play sound, take a photo, or record audio.
- `service start --real` may illuminate the display and play the Greeting
  melody. The built-in Greeting contains no wheel movement.
- Run servo tests only with the robot raised so its wheels cannot drive off the
  bench. Keep hands, cables, and loose objects away from the wheels.
- Do not run power-risk tests from an undersized supply. Use the approved
  Raspberry Pi 5 supply and inspect for undervoltage before movement.

## 3. Safe smoke tests

These tests do not intentionally operate physical hardware:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
python -m compileall -q ninjarobot_pi5_agent/src ninjarobot_pi5_ide/src
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy .
uv run --frozen pytest -q
```

Expected result: every command passes and immutable verification reports 222
tracked driver files plus 25 authorized repairs.

Check that no integrated or standalone owner is still running:

```bash
pgrep -af 'ninjarobot|pi5disp|pi5servo|pi5buzzer|pi5camera|pi5mic' || true
```

Expected result: no old agent/IDE/standalone hardware process is listed. The
`pgrep` command itself may appear briefly and can be ignored.

## 4. Communication/interface tests

With the agent service stopped, perform the non-moving real probe:

```bash
env -u VIRTUAL_ENV uv run --frozen --extra hardware \
  ninjarobot-ide-tool \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  hardware status --real
```

Expected result: configured display, buzzer, servo, distance, camera, and
microphone boundaries report ready. No servo moves and no media is retained.

Start the single-owner service:

```bash
env -u VIRTUAL_ENV uv run --frozen --extra hardware \
  ninjarobot-agent \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  service start --real
```

Expected result when no Level 2 latch exists:

- the command waits for Greeting to finish;
- top-level `started` and `ready` are both `true`;
- `status.operational_state` is `ready`;
- `status.startup.complete` is `true` and liveliness is `ready`;
- `status.robot.safety.system_latched` is `false`;
- the display returns to looping silent Idle.

Expected result when a Level 2 latch already exists:

- the process remains available but top-level `ready` is `false`;
- `status.operational_state` is `recovery_required`;
- `status.startup.liveliness` is `failed`;
- `status.robot.safety` shows the persisted reason and fault detail;
- `status.recovery.required` is `true` and explains `/resume`;
- no behavior runs until explicit recovery succeeds.

Inspect the same fields again:

```bash
uv run --frozen ninjarobot-agent service status
tail -n 80 "$HOME/.local/state/ninjarobot_pi5/agent-service.log"
```

Expected result: status never equates provider/MCP readiness with robot
readiness. A failed Greeting has a timestamped exception and traceback in the
log.

If recovery is required, start terminal chat and enter `/resume`:

```bash
uv run --frozen ninjarobot-agent chat
```

Type `/resume`, then type `RESUME` only after reviewing the prompt. This path
health-checks every configured module and does not intentionally move servos or
capture media. Expected result: the latch clears only when all probes pass,
Idle returns, status becomes `ready`, startup liveliness becomes `recovered`,
and AI motion remains disarmed.

## 5. Actuator-moving tests

The startup Greeting energizes the display backlight and buzzer but contains
no wheel operation. After the communication checks pass, stop and restart the
service once:

```bash
uv run --frozen ninjarobot-agent service stop
env -u VIRTUAL_ENV uv run --frozen --extra hardware \
  ninjarobot-agent \
  --config "$HOME/.config/ninjarobot_pi5/config.toml" \
  service start --real
```

Expected result: Greeting face and melody run once, followed by silent Idle.

Optional wheel test—this may move the servos. Raise and secure the robot first.
In terminal chat, enter `/arm`, type `ARM`, request one short low-speed movement,
then enter `/disarm`. Expected result: only the requested bounded movement runs,
and disarm stops and revokes further AI movement.

## 6. Power-risk tests

Do not deliberately create undervoltage. Before any wheel test, run:

```bash
vcgencmd get_throttled
```

Expected result: `throttled=0x0`. Any nonzero current-undervoltage indication is
a fail; stop the service and correct the power supply before continuing.

## 7. Pass/fail checklist

- [ ] Immutable drivers pass with 222 tracked files and 25 authorized repairs.
- [ ] Full compile, Ruff, mypy, and pytest gates pass.
- [ ] Only one integrated hardware owner is running.
- [ ] Safe real hardware status reports all configured boundaries ready.
- [ ] Service start waits for Greeting/Idle completion.
- [ ] Healthy startup reports `started: true` and `ready: true`.
- [ ] A persisted latch reports `recovery_required`, reason, and fault detail.
- [ ] Startup failure traceback appears in the agent service log.
- [ ] Confirmed `/resume` runs health checks, restores Idle, and leaves motion
  disarmed.
- [ ] Greeting runs once and returns to silent Idle.
- [ ] Optional raised-wheel movement is bounded and disarm prevents repetition.
- [ ] No unexpected media was captured or retained.
- [ ] Power status is safe before movement.

## 8. Rollback steps

1. Disarm motion and stop the service:

   ```bash
   uv run --frozen ninjarobot-agent service stop
   ```

2. Deploy the previous known-good repository revision or package build. Do not
   copy files from a second checkout into the active tree.
3. Keep the private configuration and safety state. Do not delete a latch to
   make rollback appear successful.
4. Run the non-moving real `hardware status --real` probe again.
5. If the previous revision is healthy but a Level 2 latch remains, use its
   documented explicit system-resume command and repeat the safe checks before
   Greeting or movement.
