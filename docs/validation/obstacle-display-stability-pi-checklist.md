# Obstacle interruption and display stability Raspberry Pi checklist

Use this checklist after pulling the obstacle and display lifecycle refinement
onto the physical NinjaRobotPi5. Automated validation does not move hardware or
prove the condition of the connected display, sensor, power supply, or wiring.

## Scope

- Confirm obstacle detection stops only the current guarded behavior.
- Confirm persistent safety stops explain their cause and recovery step.
- Confirm the ST7789V remains supervised through long animation sequences.
- Confirm the existing manual Emergency Stop and Resume path remains intact.

## Safety preparation

1. Put the robot on a stable stand with both wheels clear of the table.
2. Keep the web Emergency Stop open and keep an operator ready to disconnect
   motor power.
3. Keep hands, wires, and tools away from the raised wheels.
4. Use a large, flat target for the VL53L0X test; do not touch the robot while
   its wheels are moving.
5. Do not rewire SPI, I2C, GPIO, PWM, or power while the Raspberry Pi is on.

## Safe smoke tests

These checks do not intentionally move actuators.

1. Start NinjaRobotAgent and connect through the configured local or ngrok web
   interface.
2. Run Greeting, several face behaviors, display text, and buzzer behaviors.
3. Repeat at least 100 face/Idle transitions over 15 minutes.
4. Review the Agent status and service log.

Expected result: the display remains lit, animations continue, Idle returns
after every finite behavior, and no persistent safety latch appears. A
transient injected or real frame fault may log one reconstruction and one
successful retry; repeated unbounded retries are a failure.

## Display communication and endurance

1. With the Agent stopped, open `ninjarobot-ide-tool` and run several display
   expressions. Exit the tool cleanly.
2. Start the Agent and confirm the QR/Greeting/Idle sequence.
3. From chat, alternate short face, text, and buzzer requests for at least 30
   minutes.
4. Confirm no other `pi5disp`, IDE tool, or Agent process owns SPI concurrently.
5. Review the last 200 deployment log lines.

Expected result: only one runtime owns the hardware, the backlight never turns
off unexpectedly, no task writes after `Closing ST7789V display driver`, and
shutdown contains no pending-task or `DISPLAY_UNAVAILABLE` escalation.

## Actuator-moving obstacle test

This section moves the raised wheels.

1. Arm AI motion through `/arm` or **Arm AI motion**.
2. Request a three-second forward behavior with a face animation.
3. While the raised wheels turn, place the flat target within 50 mm of the
   forward sensor until three valid readings are collected.
4. Confirm both wheels stop immediately and remove the target.
5. Confirm the current face/audio and all later behavior stages stop, a silent
   scary face appears for about two seconds, and Idle returns.
6. Confirm chat says that an obstacle stopped the movement, no Resume is
   required, and a new command must be issued.
7. Without running `/resume`, request a short turn in the opposite direction.

Expected result: the second command reaches the motors. Agent status reports
both `motion_latched=false` and `system_latched=false`; the interrupted forward
behavior never resumes automatically.

## Persistent stop and manual Emergency Stop test

1. Start a short raised-wheel movement and click **Emergency Stop**.
2. Confirm the wheels and buzzer stop and the red Emergency Stop display remains.
3. Confirm the result/log identifies `operator_stop` and instructs the operator
   to remove hazards, click Resume or use `/resume`, and issue a new command.
4. Click Resume, complete the confirmation, and confirm all health checks pass.
5. Confirm Idle returns and AI motion remains disarmed until explicitly armed.

Expected result: manual Emergency Stop still blocks further behavior until the
confirmed Resume workflow succeeds. An unrecoverable driver, undervoltage,
watchdog, or corrupt-state stop must provide the same cause-and-recovery shape.

## Power-risk checks

No shutdown, boot, UPS, or power-off behavior changed in this refinement. Do
not run a power-off test as part of this checklist. Existing validated UPS and
power-off procedures remain authoritative.

## Pass/fail report

Record each section as `PASS`, `FAIL`, or `NOT RUN`, followed by:

- checkout commit;
- Raspberry Pi OS and kernel version;
- Agent execution mode;
- display duration and approximate face-transition count;
- obstacle test result and both latch values;
- relevant bounded log excerpt with secrets removed; and
- any wiring, power, or environmental observation.

Do not report a full hardware pass when the actuator section was not run.

## Rollback

If the display turns off, movement fails to stop, a latch is created by an
obstacle, or any recovery loops repeatedly:

1. Click Emergency Stop or disconnect motor power.
2. Stop the Agent service.
3. Do not delete `safety.json` or user configuration.
4. Save a redacted copy of the relevant service log and Agent status.
5. Return to the previously validated Git commit and synchronize its locked
   environment.
6. Restart only with the wheels raised. If the display remains blank, power off
   and inspect SPI/DC/RST/BL wiring before another attempt.
