# Phase 5 Behavior-Generation Repair Validation

Date prepared: 2026-07-29  
Software status: implemented; automated validation passed  
Raspberry Pi status: operator validation required  
Target: Raspberry Pi 5 with the existing NinjaRobotPi5 configuration

Useful terms:

- A behavior draft is the small JSON description produced by the AI model.
- The compiler validates and converts that draft into the IDE's strict robot
  behavior format.
- IDE means the NinjaRobotPi5 integration layer. The agent reaches hardware
  only through this layer.
- Motion arming means the operator has allowed one named chat session to use
  trusted servo tools.
- Raised-wheel means both drive wheels are physically clear of the floor, so
  an unexpected direction cannot move the robot across the room.

## 1. Scope

This checklist verifies the repair for AI-created robot behaviors. It covers:

- installation of the bundled `robot-behavior-generation` skill
- expression and movement draft compilation
- useful correction messages for invalid drafts
- motion-tool routing without bypassing arming
- clean Ollama and local-service connection recovery
- return to Idle after the action
- one short raised-wheel physical movement

It does not change or recalibrate any `pi5*` driver. It does not prove that
every Ollama model has equal reasoning or tool-calling quality.

## 2. Safety

Complete Sections 3 and 4 in simulation before allowing physical movement.
For Section 5:

1. Raise both wheels clear of the floor.
2. Keep hands, hair, clothing, and cables away from the wheels.
3. Keep a second terminal open and ready to run the stop command.
4. Start with a one-second movement.
5. Do not change GPIO, PWM, I2C, servo, or power wiring while powered.
6. Stop for undervoltage, overheating, a stalled servo, an unexpected
   direction, or delayed cleanup.
7. Do not place the robot on the floor until the existing Phase 4 obstacle,
   Disarm, Level 1, and Level 2 checks also pass.

Emergency terminal:

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
uv run --frozen ninjarobot-agent service stop
```

Stopping the service releases agent, IDE, model, sensor, buzzer, display, and
servo resources. The web X button remains the fastest Level 2 Emergency Stop
when an active web controller is already open.

## 3. Safe smoke tests

### 3.1 Update and synchronize

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
git pull
uv sync --frozen --extra hardware
```

Expected result: both commands finish without a dependency or lock-file error.

### 3.2 Run the software checks

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy ninjarobot_pi5_agent/src ninjarobot_pi5_ide/src
uv run --frozen pytest -q
```

Expected result: the immutable-driver check reports 222 tracked files and 25
authorized repairs. Ruff, MyPy, and all 299 tests pass. The known Starlette
test-client deprecation warning is acceptable.

### 3.3 Inspect and simulate the bundled skill

```bash
uv run --frozen ninjarobot-agent skill list
uv run --frozen ninjarobot-agent \
  skill inspect robot-behavior-generation
uv run --frozen ninjarobot-agent \
  skill simulate robot-behavior-generation \
  --input '{"request":"Show a happy face and play a short tone.","save_requested":false}'
```

Expected result: the skill is listed as bundled and enabled. Inspection shows
expression and movement tools, and simulation previews
`robot.behavior.execute_expression` without executing hardware.

### 3.4 Start a clean simulation service

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen ninjarobot-agent service start
uv run --frozen ninjarobot-agent status
uv run --frozen ninjarobot-agent session clear behavior-repair-sim
```

If the first stop says no service is running, continue. Expected result: the
service reports simulation mode and the selected Ollama model is ready.

### 3.5 Execute a generated expression

```bash
uv run --frozen ninjarobot-agent chat \
  --session behavior-repair-sim \
  --skill robot-behavior-generation \
  "Create and execute two stages. First show a happy face with a short 880 Hz tone. Then show Nice to meet you while playing the happy melody."
```

Expected result: the agent calls `robot.behavior.execute_expression`, reports
success, and does not ask for motion arming. Because the service is simulated,
no physical display, buzzer, or servo is operated.

### 3.6 Confirm unarmed movement remains blocked

```bash
uv run --frozen ninjarobot-agent chat \
  --session behavior-repair-sim \
  --skill robot-behavior-generation \
  "Move forward for one second with an exciting face, then stop."
```

Expected result: no movement is executed. The result explains that motion is
not armed for `behavior-repair-sim`. This confirms that compact draft support
does not bypass the safety policy.

## 4. Communication and interface tests

### 4.1 Check conversation history

```bash
uv run --frozen ninjarobot-agent session history behavior-repair-sim
```

Expected result: the stored assistant tool call uses either
`robot.behavior.execute_expression` for the expression or
`robot.behavior.execute_movement` for the movement request. A pre-execution
validation error, if deliberately produced by the selected model, contains
`BEHAVIOR_DRAFT_INVALID` and a useful field correction. It must not say only
“I've encountered an unexpected system failure.”

### 4.2 Check restart recovery

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen ninjarobot-agent service start
uv run --frozen ninjarobot-agent status
```

Expected result: all commands complete cleanly, the Unix socket reconnects,
and status reports the selected provider. A disconnected client must not leave
the service unable to restart.

### 4.3 Understand model-specific results

If a model answers with prose but never calls a tool, change to another
installed model:

```bash
uv run --frozen ninjarobot-agent model list
uv run --frozen ninjarobot-agent model select MODEL_NAME
uv run --frozen ninjarobot-agent session clear behavior-repair-sim
```

Expected result: selection succeeds only for an installed healthy model.
Tool-calling quality and latency can differ substantially by model. A
no-tool-call answer is not evidence that the IDE or servo driver failed.

## 5. Actuator-moving tests

These steps operate real hardware.

### 5.1 Prepare the robot

Raise both wheels, confirm the servo calibration file still exists, and open a
second terminal:

```bash
test -f "$HOME/.config/pi5servo/servo.json" && echo "servo calibration found"
```

Expected result: `servo calibration found`.

In Terminal B, prepare this command but do not run it yet:

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
uv run --frozen ninjarobot-agent service stop
```

### 5.2 Start the real owner service

In Terminal A:

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
uv run --frozen ninjarobot-agent service stop
uv run --frozen --extra hardware ninjarobot-agent service start --real
uv run --frozen ninjarobot-agent status
uv run --frozen ninjarobot-agent session clear behavior-repair-real
```

Expected result: status reports real execution and healthy configured
hardware. Startup Greeting may use the display and buzzer, then Idle loops.

### 5.3 Test a real expression first

```bash
uv run --frozen ninjarobot-agent chat \
  --session behavior-repair-real \
  --skill robot-behavior-generation \
  "Show a happy face and play one short 880 Hz tone."
```

Expected result: the physical display and buzzer respond, no wheel moves, and
the robot returns to looping Idle.

### 5.4 Arm and run one finite movement

```bash
uv run --frozen ninjarobot-agent motion arm \
  --session behavior-repair-real \
  --confirm

uv run --frozen ninjarobot-agent chat \
  --session behavior-repair-real \
  --skill robot-behavior-generation \
  "With the wheels raised, move forward for exactly one second with an exciting face, then stop."
```

Expected result: the model uses the movement capability, both wheels turn in
the configured forward directions for about one second, the stop stage
returns both motors to neutral, and Idle resumes. A model that accidentally
labels explicit movement as an expression is rerouted to the movement
capability before policy evaluation; the already-armed session is still
required.

### 5.5 Verify Disarm

```bash
uv run --frozen ninjarobot-agent motion disarm \
  --session behavior-repair-real

uv run --frozen ninjarobot-agent chat \
  --session behavior-repair-real \
  --skill robot-behavior-generation \
  "Move forward for one second."
```

Expected result: Disarm requests a servo stop and the following movement is
denied. No wheel should turn.

## 6. Expected outcomes

The repair passes when:

- the bundled skill validates and simulates
- a generated expression executes in simulation
- unarmed generated movement is denied before IDE execution
- invalid drafts receive field-specific, safe-to-retry feedback
- the generic unexpected-system-failure response no longer masks a schema
  problem
- service stop/start and client reconnection are clean
- a real expression uses only the display and buzzer
- one armed raised-wheel movement runs briefly and stops
- Disarm blocks the next movement
- the robot returns to Idle after each completed action

Different models may take different amounts of time or may fail to produce a
tool call. Record that as a model compatibility result separately from the
software and hardware result.

## 7. Pass/fail report

Copy this table into your test notes:

| Check | Pass or fail | Notes |
|---|---|---|
| Immutable drivers and 299 automated tests |  |  |
| Bundled skill inspect and simulation |  |  |
| Generated expression in simulation |  |  |
| Unarmed movement refusal |  |  |
| Actionable invalid-draft feedback |  |  |
| Service restart and reconnect |  |  |
| Real display and buzzer expression |  |  |
| Armed one-second raised-wheel movement |  |  |
| Disarm prevents another movement |  |  |
| Return to Idle |  |  |

Also record the exact Ollama model name from:

```bash
uv run --frozen ninjarobot-agent model current
```

## 8. Rollback

First stop the service so every owned resource is released:

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
uv run --frozen ninjarobot-agent service stop
```

Then switch to the previous known-good commit or branch using the exact
identifier you recorded before updating:

```bash
git switch YOUR_PREVIOUS_BRANCH
# or:
git checkout YOUR_PREVIOUS_COMMIT
uv sync --frozen --extra hardware
```

Do not delete `~/.config/pi5servo/servo.json`,
`~/.config/ninjarobot_pi5/config.toml`, or other calibrated module
configuration during rollback. If any wheel does not stop, disconnect robot
power using the safest available physical method before doing further
software work.
