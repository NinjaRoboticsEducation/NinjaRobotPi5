---
name: pi-validation
description: Use after hardware-facing or deployment-relevant changes to generate Raspberry Pi validation steps, expected outcomes, safety notes, and a concise pass/fail report.
---

# Pi Validation Report

Use this skill after code changes that may affect Raspberry Pi behavior, hardware drivers, GPIO, I2C, SPI, serial, PWM, sensors, motors, camera, or deployment setup.

## Output format
Produce a validation plan with these sections:

1. Scope of validation
2. Safety notes
3. Safe smoke tests
4. Communication/interface tests
5. Actuator-moving tests
6. Expected outcomes
7. Pass/fail checklist
8. Rollback steps

## Rules
- Separate non-moving tests from actuator-moving tests.
- Call out any command that may energize hardware.
- Prefer short, copy-paste-ready commands.
- State what success looks like for each test.
- If the implementation changed deployment assumptions, include environment/setup checks.