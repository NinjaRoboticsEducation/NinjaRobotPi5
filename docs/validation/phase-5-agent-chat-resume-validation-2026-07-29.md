# Phase 5 Agent Chat `/resume` Validation

Date prepared: 2026-07-29  
Software status: implemented; automated validation passed  
Raspberry Pi status: operator validation required  
Target: Raspberry Pi 5 running the single-owner NinjaRobotAgent service

Useful terms:

- Level 2 means the full Emergency Stop state. It stops servo movement and
  sensors, silences the buzzer, and keeps the Emergency Stop sign visible.
- A health check is a safe readiness probe. It does not intentionally take a
  photograph, record audio, or move a servo.
- A safety latch is saved stop state that prevents normal operation until
  confirmed recovery succeeds.
- Idle is the robot's normal looping face between interactions.

## 1. Scope of validation

This checklist verifies:

- terminal-chat `/resume`
- web-chat `/resume`
- the existing web Y Resume button
- explicit recovery confirmation
- all-module health checks before clearing Level 2
- clear failure reporting
- Idle restoration after success
- AI motion remaining disarmed after recovery
- recovery without restarting NinjaRobotAgent

No `pi5*` driver changed. The resume command continues to use the existing IDE
safety controller.

## 2. Safety notes

1. Complete the simulation tests before starting the real hardware service.
2. Resume itself should not move a servo, but keep the robot clear in case
   other work was already active.
3. Do not disconnect GPIO, PWM, I2C, SPI, camera, microphone, or servo wiring
   while the Raspberry Pi is powered.
4. A failed health check must leave the robot stopped. Correct the reported
   problem before trying again.
5. Do not use `/arm` until `/resume` succeeds and Idle returns.
6. Raise both wheels before the separate movement test in Section 5.
7. Keep the web X Emergency Stop or this command immediately available:

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
uv run --frozen ninjarobot-agent service stop
```

## 3. Safe smoke tests

### 3.1 Update and install

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
git pull
uv sync --frozen --extra hardware
```

Expected result: both commands complete without dependency or lock-file
errors.

### 3.2 Run the software gate

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy ninjarobot_pi5_agent/src ninjarobot_pi5_ide/src
node --check ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js
uv run --frozen pytest -q
```

Expected result: the immutable check reports 222 tracked files and 25
authorized repairs. Ruff, MyPy, JavaScript syntax, and all 306 tests pass. The
known Starlette test-client deprecation warning is acceptable.

### 3.3 Start simulation and the web interface

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen ninjarobot-agent service start
uv run --frozen ninjarobot-agent web start
uv run --frozen ninjarobot-agent status
```

If the first command says the service is not running, continue. Expected
result: the service reports simulation mode and remains running throughout all
resume tests.

## 4. Communication and interface tests

### 4.1 Test web-chat `/resume`

1. Open `https://ninjarobotpi5.local:8443/`.
2. Press X to trigger simulated Emergency Stop.
3. Enter `/resume` in the web chat box.
4. Cancel the first confirmation dialog.
5. Confirm that chat says the resume was cancelled.
6. Enter `/resume` again and approve the dialog.

Expected result: the web chat reports that modules resumed, Idle was restored,
and AI motion remains disarmed. The **Arm AI Motion** button must show its
disarmed state. Live Activity should show `robot.system.resume`; it should not
show an Ollama model turn for `/resume`.

### 4.2 Test the Y Resume button

Press X again, then press Y and approve its confirmation dialog.

Expected result: Y uses the same health-checked recovery, reports success, and
restores direct controls only after success. AI chat remains disarmed.

### 4.3 Test terminal-chat `/resume`

Press X again. From SSH or a local terminal:

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
uv run --frozen ninjarobot-agent
```

At `You>`, enter:

```text
/help
/resume
```

Confirm `/help` lists `/resume`. Type something other than `RESUME` at the
first prompt. Expected result: the command says recovery was cancelled and the
service remains available.

Enter `/resume` again, then type:

```text
RESUME
```

Expected result: the terminal prints the successful tool result followed by:

```text
Robot modules resumed and Idle restored. AI motion remains disarmed; use /arm before requesting servo movement.
```

Enter `/exit`. This closes only the terminal interface; the agent and web
service continue running.

### 4.4 Confirm the command bypasses the model

```bash
uv run --frozen ninjarobot-agent session history local-cli
```

Expected result: `/resume` is not stored as a user prompt and there is no AI
answer inventing a recovery. It was processed as a local safety command.

## 5. Actuator-moving tests

These tests use real hardware. Raise both wheels before continuing.

### 5.1 Restart once in real mode

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent service stop
uv run --frozen --extra hardware ninjarobot-agent service start --real
uv run --frozen ninjarobot-agent web start
```

Expected result: startup Greeting completes and the physical Idle face loops.

### 5.2 Perform a real Level 2 stop and health-only resume

1. Open the web controller.
2. Press X.
3. Confirm servo motion and sensors stop, the buzzer is silent, and the red
   Emergency Stop sign remains visible.
4. Enter `/resume` in web chat and approve the dialog.

Expected result: the display, servo service, distance sensor, camera, and
microphone readiness probes pass; no servo intentionally moves; the red sign
clears; and Idle returns. If a probe fails, the sign and latch remain. Correct
that specific problem before retrying.

### 5.3 Confirm AI movement is still disarmed

Without pressing **Arm AI Motion**, ask:

```text
Move forward for one second, then stop.
```

Expected result: the movement tool is denied because the web chat session is
not armed. Neither wheel moves.

### 5.4 Separately arm and verify recovered movement

Keep both wheels raised. Press **Arm AI Motion**, approve its confirmation,
then ask:

```text
With the wheels raised, move forward for exactly one second, then stop.
```

Expected result: the configured wheels turn in their forward directions for
about one second, stop at neutral, and Idle returns.

Immediately disarm AI motion when finished. If movement does not stop, press X
or run `ninjarobot-agent service stop` from the prepared terminal.

## 6. Expected outcomes

The implementation passes when:

- `/resume` is listed in terminal `/help`
- terminal and web chat both require confirmation
- cancellation sends no recovery request
- `/resume` is never sent to Ollama
- every configured module is healthy before Level 2 clears
- failed recovery leaves the Emergency Stop state active
- successful recovery restores Idle without restarting the service
- web direct control returns only after success
- AI chat remains disarmed until a separate `/arm`
- a separately armed, raised-wheel one-second movement works and stops

## 7. Pass/fail checklist

| Check | Pass or fail | Notes |
|---|---|---|
| Immutable drivers and 306 automated tests |  |  |
| Web `/resume` cancellation |  |  |
| Web `/resume` successful recovery |  |  |
| Y Resume successful recovery |  |  |
| Terminal `/help` lists `/resume` |  |  |
| Terminal `/resume` cancellation |  |  |
| Terminal `/resume` successful recovery |  |  |
| No Ollama turn or transcript entry |  |  |
| Real Level 2 sign remains until healthy resume |  |  |
| Idle returns after success |  |  |
| AI movement remains disarmed |  |  |
| Separate raised-wheel `/arm` movement |  |  |

## 8. Rollback steps

First stop the single owner so hardware resources are released:

```bash
cd "$HOME/NinjaRobotPi5_test/NinjaRobotPi5"
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent service stop
```

Then switch to the previous known-good branch or commit:

```bash
git switch YOUR_PREVIOUS_BRANCH
# or:
git checkout YOUR_PREVIOUS_COMMIT
uv sync --frozen --extra hardware
```

Do not delete servo calibration, robot configuration, TLS certificates, or
other module settings during rollback. If the system is still latched after
returning to the previous version, use that version's documented
`ninjarobot-ide-tool system resume --confirm` only after stopping the agent
service and correcting the original emergency condition.
