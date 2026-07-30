# Hardware Recovery Repair Validation — 2026-07-30

## 1. Scope of validation

This checklist verifies that:

- rejected or invalid robot behaviors no longer stop every hardware module
- genuine hardware-driver failures still create a Level 2 safety stop
- recovery names the component that is not ready
- the agent and direct IDE cannot own the integrated hardware simultaneously
- a healthy Level 2 recovery returns the robot to normal operation

## 2. Safety notes

- Keep the robot wheels raised so they cannot drive off the table.
- Keep hands, cables, and loose objects away from both servos.
- Know how to disconnect robot power before starting an actuator-moving test.
- The safe smoke and interface tests below do not intentionally move a servo,
  record audio, or take a photograph.
- Stop the agent before running a real standalone `pi5*` hardware tool.

Set the shared configuration path once:

```bash
cd "$HOME/NinjaRobotPi5"
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
```

## 3. Safe smoke tests

Install the updated locked environment:

```bash
uv sync --frozen --extra hardware
uv run python scripts/verify_immutable_drivers.py
```

Expected result: immutable-driver verification prints `PASS`.

Inspect configuration and safety state without opening hardware:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status
```

Expected result: the command displays the calibration path, servo roles,
motion settings, and safety state. If `system_latched` is `true`, review
`reason` and `fault_detail`.

Probe configured interfaces without movement or recording:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status --real
```

Expected result: configured components report `ready`. This probe may
initialize buses briefly but does not command servo movement.

## 4. Communication and interface tests

If the safety state is Level 2 latched and the safe probe reports every
component ready, recover it:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" system resume --confirm
```

Expected result: both `system_latched` and `motion_latched` become `false`.
If a component is unhealthy, the command names it and leaves both latches
unchanged.

Start the real agent service:

```bash
uv run --frozen ninjarobot-agent service start --real
uv run --frozen ninjarobot-agent service status
```

While it remains running, try a second direct real probe:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status --real
```

Expected result: the second process exits with “hardware is already owned” and
explains how to use or stop the agent. It must not create a new Level 2 latch.

Stop the service and repeat the probe:

```bash
uv run --frozen ninjarobot-agent service stop

uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" hardware status --real
```

Expected result: the IDE now acquires ownership and completes the safe probe.

## 5. Actuator-moving tests

This section can move both continuous-rotation servos.

Confirm the wheels are raised, then run a short movement behavior through the
interactive tool:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG"
```

Choose **Run Robot Behaviors**, **Robot Movements**, then one movement. Use
Emergency Stop immediately if direction, speed, sound, display, or sensor
behavior is unexpected.

Expected result: the selected movement runs, and a valid obstacle condition
still produces its configured Level 1 motion stop. A normal completed behavior
does not create a Level 2 latch.

## 6. Expected outcomes

- Invalid behavior data returns an ordinary error without stopping unrelated
  modules.
- A real device communication/output failure still stops and latches the
  complete system.
- `fault_detail` identifies the original genuine device failure.
- Failed recovery names every unhealthy component.
- Only one real integrated process owns the hardware.
- Closing or stopping that process releases ownership for the next process.

## 7. Pass/fail checklist

- [ ] Immutable-driver verification passed.
- [ ] Configuration-only status completed.
- [ ] Safe real hardware status reported expected components.
- [ ] Healthy Level 2 recovery cleared both latches.
- [ ] Failed recovery, if exercised, named the unhealthy component.
- [ ] Second-process ownership was rejected without changing safety state.
- [ ] Ownership was released after stopping the first process.
- [ ] Optional raised-wheel movement behaved normally.
- [ ] Emergency Stop remained available during physical movement.

## 8. Rollback steps

Stop active processes:

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen --extra hardware ninjarobot-ide-tool behavior stop
```

Return to the known-good Git commit or branch selected before this repair:

```bash
git status
git log --oneline --decorate -10
git switch <KNOWN_GOOD_BRANCH>
uv sync --frozen --extra hardware
```

Do not delete `~/.local/state/ninjarobot_pi5/safety.json`. After correcting
the fault, clear it through the checked recovery command:

```bash
uv run --frozen --extra hardware ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" system resume --confirm
```
