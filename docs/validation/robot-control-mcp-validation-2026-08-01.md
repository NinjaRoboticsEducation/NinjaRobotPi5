# Robot-Control MCP and API-Key Authentication Validation — 2026-08-01

Software status: implemented; automated validation passed  
Raspberry Pi status: operator acceptance required  
Target: Raspberry Pi 5 with the configured display, GPIO27 buzzer, forward
VL53L0X sensor, and GPIO12/GPIO13 wheel servos

## 1. Scope and safety

This checklist validates API-key-only cloud authentication and the trusted
built-in robot-control MCP path from model tool proposal through policy and the
NinjaRobot IDE. It does not authorize external MCP clients or direct hardware
access.

Before any real test:

1. Complete Sections 2 and 3 in simulation.
2. Raise both wheels before Section 5 and keep the chassis supported.
3. Keep hands, hair, clothing, and cables away from the wheels.
4. Keep the browser Emergency Stop and a second terminal ready.
5. Do not change GPIO, I2C, SPI, PWM, servo, sensor, or power wiring while powered.
6. Stop for unexpected direction, continuous motion, heat, noise, undervoltage,
   delayed cancellation, or a failed emergency stop.

Emergency terminal command:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen ninjarobot-agent service stop
```

Expected result: the service closes the agent and IDE; servos stop and the
safety cleanup path runs. Disconnect actuator power if motion continues.

## 2. Safe smoke tests — no hardware access

```bash
cd "$HOME/NinjaRobotPi5"
uv sync --frozen --extra hardware --group dev
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen ruff format --check ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
```

Expected result: driver verification reports 222 tracked files and 25
authorized repairs; compilation, Ruff, and mypy pass; pytest reports 363
passing tests with no failure. The known Starlette test-client deprecation
warning may appear.

Confirm retired web login cannot execute:

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider login gemini
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider login anthropic
```

Expected result: each command exits with an actionable message directing the
operator to `provider set-api-key`. No browser opens, no Google client file is
requested, and no `ant` command runs.

## 3. Simulation and MCP contract tests — no hardware access

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen ninjarobot-agent service start
uv run --frozen ninjarobot-agent status
```

Expected result: status reports simulation mode and both `ide` and
`robot-control-mcp` tool providers ready. External configured MCP failures may
be degraded but must not stop these trusted providers.

Run an unarmed expression:

```bash
uv run --frozen ninjarobot-agent chat --session robot-mcp-sim \
  "Preview and execute a two-stage expression: first show happy with a short 660 Hz tone, then show Hello Ninja with the happy melody."
```

Expected result: preview returns a canonical expression with
`contains_motion: false`; expression execution succeeds in simulation and no
servo capability is invoked.

Verify unarmed movement refusal:

```bash
uv run --frozen ninjarobot-agent chat --session robot-mcp-sim \
  "Preview and execute a short exciting forward movement with a tone."
```

Expected result: preview may succeed and report `contains_motion: true`, but
execution is denied because this session is not armed. No IDE movement action
runs.

Arm only the simulation session and retry:

```bash
uv run --frozen ninjarobot-agent motion arm \
  --session robot-mcp-sim --confirm
uv run --frozen ninjarobot-agent chat --session robot-mcp-sim \
  "Execute that short exciting forward movement now, then stop."
```

Expected result: `robot.behavior.execute_movement` returns a successful
simulated IDE action. The public execution name remains compatible with older
prompts and Skills.

## 4. Device communication tests — real hardware, no drive movement

Stop simulation, confirm the robot is stable, then start the real service:

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" service start --real
uv run --frozen ninjarobot-agent status
```

Expected result: the service owns hardware once; IDE and robot-control MCP
health are ready. A second real IDE process must be refused by the ownership
lock.

Execute a finite expression only:

```bash
uv run --frozen ninjarobot-agent chat --session robot-mcp-real \
  "Preview and execute a happy face with a quiet 660 Hz tone for half a second. Do not move."
```

Expected result: the display and buzzer operate once, the IDE result succeeds,
and neither servo moves. Confirm the robot returns to Idle and the buzzer is
silent.

Read the distance sensor:

```bash
uv run --frozen ninjarobot-agent chat --session robot-mcp-real \
  --skill offline-robot-check "Read the front distance once."
```

Expected result: one valid reading or a clearly classified sensor error; no
motion and no automatic action retry.

## 5. Actuator-moving tests — wheels raised

Hardware risk: high. Raise and secure both wheels. Test one short movement,
then stop and inspect the robot before continuing.

```bash
uv run --frozen ninjarobot-agent motion arm \
  --session robot-mcp-real --confirm
uv run --frozen ninjarobot-agent chat --session robot-mcp-real \
  "Preview and execute one half-second forward movement with the exciting face and one short tone, then stop."
```

Expected result:

- preview reports motion and canonical logical roles, never raw GPIO numbers
- movement starts only for the armed `robot-mcp-real` session
- face, tone, and configured movement combine in one bounded behavior
- calibrated wheels run in the expected direction and stop at the deadline
- the IDE action result returns to the agent and the presentation returns to Idle

While a second short movement is active, issue Emergency Stop from the browser.

Expected result: the Level 2 stop interrupts the MCP/IDE action, both servos
stop, the result is cancelled or failed with conservative retry evidence, and
the robot remains latched until confirmed healthy resume. Do not automatically
repeat the movement after an uncertain result.

## 6. Power-risk tests — wheels raised

Before and immediately after one short movement, run:

```bash
vcgencmd get_throttled
vcgencmd measure_temp
```

Expected result: no new undervoltage or throttling bit and temperature remains
within the operator's accepted limit. If an undervoltage or watchdog condition
is detected during movement, both servos must stop and the safety state must
latch. Do not test by intentionally shorting, disconnecting, or overloading the
power system.

The current design has no independent physical actuator power cutoff. Treat a
software stop as necessary but not equivalent to removing servo power.

## 7. API-key communication tests

Run only for accounts whose cost and data policy the owner accepts:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider set-api-key gemini
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider health gemini

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider set-api-key anthropic
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider health anthropic
```

Expected result: hidden double-entry prompts store owner-private keys, health
reports ready for valid accounts, and no command prints a key. Repeat the
Section 3 expression test with each selected cloud model before any real
movement. Provider failure must not replay a completed robot action.

## 8. Pass/fail record

| Area | Pass criterion | Result | Evidence / notes |
|---|---|---|---|
| Safe software gate | All checks pass; driver hashes unchanged | Pending | |
| Web-login removal | Migration message only; no browser/CLI auth | Pending | |
| MCP discovery | Five fixed trusted behavior tools; no collision | Pending | |
| Preview | Canonical expression/movement; no execution | Pending | |
| Unarmed policy | Movement denied; expression allowed | Pending | |
| Display and buzzer | Finite expression succeeds; no servo motion | Pending | |
| Raised-wheel motion | Armed finite movement and automatic stop | Pending | |
| Cancellation / E-stop | IDE action stops; no automatic retry | Pending | |
| Sensor and obstacle boundary | Valid reading and guarded front motion | Pending | |
| Power | No unexpected throttle; faults latch and stop | Pending | |
| Gemini API key | Ready without key disclosure | Optional | |
| Anthropic API key | Ready without key disclosure | Optional | |

Overall result: **PENDING OPERATOR VALIDATION**.

## 9. Rollback

Immediate safe rollback:

1. Run `ninjarobot-agent service stop`.
2. Disconnect actuator power if any servo remains energized.
3. Leave a Level 1 or Level 2 latch in place until the cause is understood.
4. Do not delete the action ledger; preserve it as evidence.

Software rollback without overwriting the current worktree:

```bash
cd "$HOME/NinjaRobotPi5"
git log --oneline -5
git worktree add "$HOME/NinjaRobotPi5-rollback" PREVIOUS_COMMIT
cd "$HOME/NinjaRobotPi5-rollback"
uv sync --frozen --extra hardware
uv run --frozen python scripts/verify_immutable_drivers.py
```

Replace `PREVIOUS_COMMIT` with the reviewed pre-refinement commit. Stop every
service before starting one from the rollback worktree because both use the
same hardware-owner lock and user configuration. Legacy OAuth selection is not
required for rollback; configure an API key or select Ollama. To remove a newly
stored cloud key, run `provider logout PROVIDER_ID` from the current release.
