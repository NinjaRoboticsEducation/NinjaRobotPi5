# AGENTS.md

## Project identity
This repository is for NinjaRobot: Python-based robot software and hardware drivers developed and validated primarily on raspberry pi 5, synchronized through GitHub.

## Non-negotiable workflow
Follow this sequence for all substantial implementation tasks unless the user explicitly asks to skip a step:

1. Understand the user's request fully.
   - If there is any ambiguity or questions about user's query and instructions, ask for comfirmation before any planning and executions.
   - Extract goals, constraints, hardware assumptions, safety concerns, target files, and expected outputs.
   - If anything in the prompt implies OpenAI APIs, Codex behavior, or model/tool usage, use the OpenAI developer documentation MCP server first.
   - If anything depends on third-party libraries, frameworks, device SDKs, setup instructions, or current package behavior, use Context7 first.
   - If the task requires understanding the repository, architecture, symbol relationships, or code correctness, use Serena first.
   - If the task requires repository, branch, issue, PR, or workflow context, use the GitHub MCP server first.

2. Research and code review before planning.
   - For repository/code review, activate Serena and use:
     - `activate_project`
     - `check_onboarding_performed`
     - `initial_instructions`
   - Prefer Serena's `list_dir`, `find_file`, `get_symbols_overview`, `find_symbol`, and `search_for_pattern` before using `read_file`.
   - Use `read_file` for line-by-line review only when targeted symbolic review is insufficient or when reviewing non-code documents/config files.

3. Produce a phased implementation plan.
   - Break work into explicit phases.
   - For each phase, define:
     - objective
     - files/modules likely to change
     - lint/test/validation checks
     - hardware risk level
     - documentation updates required
   - Present the phased plan to the user for review and approval before coding.

4. Implement only after the user approves the plan.
   - Work phase by phase.
   - Keep diffs small and reviewable.
   - Prefer modifying existing code over adding disconnected new files.
   - For hardware-facing changes, clearly identify impacts to GPIO, I2C, SPI, serial, PWM, motors, sensors, camera, or power behavior.

5. Mandatory linting and validation gate after every implementation phase.
   - Do not proceed to the next phase until the current phase passes linting/validation.
   - Prefer existing project commands if defined in the repo.
   - If no project-standard commands exist, use this default Python gate:
     - `python -m compileall .`
     - `ruff check .`
     - `ruff format --check .`
     - `pytest -q`
   - If typing is already part of the project, also run `mypy .`.
   - If linting or tests fail, stop, fix the problems, and rerun the checks before continuing.

6. Mandatory Raspberry Pi validation planning for hardware-relevant work.
   - After hardware-facing changes, produce a Pi validation checklist.
   - Separate:
     - safe smoke tests
     - device communication tests
     - actuator-moving tests
     - power-risk tests
   - Explicitly note expected outcomes and rollback steps.

7. Mandatory documentation pass before closing the task.
   - Review and update:
     - `README.md` for a complete project introduction, features, drivers, setup, and examples
     - `DevelopmentGuide.md` as the developer wiki/reference manual
     - `DevelopmentLog.md` as the chronological archive of changes, rationale, validation, and progress
   - If behavior changed but docs were not updated, the task is not complete.

8. Final handoff format
   - Summarize:
     - walkthrough of what changed, what passed linting/tests, what still needs Raspberry Pi validation and what docs were updated
     - Clear step-by-step instructions for user to test new development manually
     - recommended next step

## NinjaRobotPi5V4 managed-driver policy

The following root directories began as exact copies of the historical
hardware dependencies:

- `pi5buzzer/`
- `pi5camera/`
- `pi5disp/`
- `pi5mic/`
- `pi5servo/`
- `pi5vl53l0x/`

The project owner authorized robust, independently validated repairs to these
copies on 2026-07-25. Preserve the original import hashes in
`docs/validation/immutable_driver_baseline.json`. Every repaired file must also
be recorded in `docs/validation/authorized_driver_changes.json` with its
original hash, approved hash, date, authorizer, and reason. Keep driver changes
small and do not add agent or middleware responsibilities to a hardware
library. All cross-device integration belongs in `ninjarobot_pi5_ide`. The
agent must access robot capabilities only through the IDE.

Run `uv run python scripts/verify_immutable_drivers.py` before and after every
implementation phase. If verification fails, stop and either revert the
unintended difference or record an explicitly authorized, tested repair.

The nested `NinjaClawBot/` repository remains immutable and ignored. V4 must
not edit it, import it, package it, or copy its OpenClaw runtime.
