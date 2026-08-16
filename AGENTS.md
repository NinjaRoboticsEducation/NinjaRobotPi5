# AGENTS.md

## Purpose

This file defines the required workflow and safety boundaries for AI-assisted
development of NinjaRobotPi5. The repository targets Raspberry Pi 5 and
contains code that can move motors, capture personal data, expose a network
service, modify boot configuration, and power off the computer. Treat those
effects as real even when development occurs on another platform.

## Architecture boundaries

NinjaRobotPi5 has one permitted hardware path:

```text
user/model -> ninjarobot_pi5_agent -> ninjarobot_pi5_ide -> pi5* driver -> device
```

- `ninjarobot_pi5_agent` may not import a `pi5*` library or access GPIO, I2C,
  SPI, PWM, camera, microphone, serial, or system power directly.
- Cross-device coordination, locks, safety state, behavior execution, and
  hardware ownership belong in `ninjarobot_pi5_ide`.
- A managed `pi5*` library owns only its device and standalone setup/test UI.
  Do not add agent, memory, MCP, web, or multi-device responsibilities there.
- Models and external MCP servers propose typed actions. Only deterministic
  Agent policy and IDE contracts may authorize and execute them.
- The ignored `NinjaClawBot/` history is immutable. Never edit, import, package,
  or copy its runtime into this project.

## Required workflow

Follow this sequence for every substantial task unless the project owner
explicitly approves a different sequence.

### 1. Establish scope

- Restate the outcome, target files, compatibility expectations, hardware
  assumptions, privacy/security impact, and required documentation.
- Inspect `git status --short` and preserve all unrelated user changes.
- Ask for clarification before planning when different reasonable answers would
  materially change behavior, safety, stored data, public APIs, dependencies,
  deployment, or hardware operation.
- Do not infer approval to push, publish, merge, tag, open a pull request, alter
  an external account, run a live power command, or delete user data.

### 2. Research and inspect before planning

- Use repository-aware symbol tools first for architecture, references, and
  code review when available. Use targeted `rg`, symbol inspection, and file
  reads when they are unavailable; state the fallback rather than blocking.
- Use the official OpenAI developer documentation for OpenAI products.
- Use official or primary upstream documentation for current third-party APIs,
  device SDKs, systemd, Raspberry Pi, ngrok, and installation behavior.
- Use GitHub repository tools for branch, issue, pull-request, or workflow state
  when available. Read-only local Git is the fallback for checkout state.
- Never paste secrets, credentials, captured media, conversation databases, or
  private configuration into prompts, logs, fixtures, or commits.

### 3. Propose a phased plan

For each phase, name the objective, likely files, compatibility contract,
validation gate, documentation work, and hardware risk level. Obtain explicit
approval before implementation.

### 4. Implement in reviewable phases

- Prefer small changes to existing components over parallel mechanisms.
- Preserve public CLI, configuration, database, IPC, behavior, and tool
  contracts unless the approved plan explicitly changes them.
- Make migrations backward-compatible and idempotent. Existing private
  configuration and user data take precedence over new defaults.
- Use timeouts and deterministic cleanup for hardware, subprocess, socket,
  network, and service lifecycles. Cancellation must leave actuators and shared
  devices safe.
- Do not perform live hardware actions as part of an automated test.
- Pin new installer inputs and document provenance and licenses. Installers must
  be rerunnable, previewable, explicit about privilege, and must not silently
  start the Agent, move hardware, capture media, deploy boot startup, or choose
  a large model.

### 5. Pass the gate after every phase

Run the project commands applicable to the change and stop to repair failures:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python scripts/verify_workspace_driver_sources.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
git diff --check
```

Run each managed driver's tests in a separate pytest process because standalone
suites intentionally reuse test module names. Run relevant packaging,
installer dry-run, documentation-link, service, or security tests when those
areas change. Never describe a baseline failure as introduced by the current
change, but do not ignore it: reproduce, explain, and repair it when in scope.

## Managed-driver policy

These directories are managed copies of independently tested historical
drivers:

- `pi5buzzer/`
- `pi5camera/`
- `pi5disp/`
- `pi5mic/`
- `pi5servo/`
- `pi5vl53l0x/`

Preserve `docs/validation/immutable_driver_baseline.json`; never regenerate it
to make a change pass. Run the verifier before and after every implementation
phase. Every approved managed-file change must be independently tested and
recorded in `docs/validation/authorized_driver_changes.json` with its original
hash, approved hash, authorization date, authorizer, and precise reason:

```bash
uv run python scripts/verify_immutable_drivers.py \
  --record-authorized path/to/changed-file \
  --reason "approved reason" \
  --authorized-by "Project owner" \
  --authorized-on YYYY-MM-DD
```

If verification fails, stop. Revert an unintended change or obtain explicit
authorization and validate the repair before recording it.

## Hardware and deployment safety

Classify and communicate changes affecting GPIO, I2C, SPI, PWM, motors,
sensors, camera, microphone, network exposure, systemd, sudoers, boot files,
UPS behavior, or shutdown.

- Keep actuator tests opt-in; require raised wheels and an operator ready to
  remove power.
- Require consent before camera or microphone capture and avoid retaining test
  media.
- Never expose the local web port through router forwarding. Remote access must
  use the approved pairing and tunnel boundary.
- Do not write `/boot`, `/etc/systemd`, `/etc/sudoers.d`, or live user
  configuration during repository tests.
- Power-off tests are manual power-risk tests. Automated coverage must stop at
  command construction, authorization, and helper validation.
- End hardware-relevant work with separate safe smoke, device communication,
  actuator-moving, and power-risk checklists, each with expected result and
  rollback.

## Documentation and release hygiene

Before closing behavior, setup, dependency, architecture, or workflow changes:

- update `README.md` for public behavior and supported features;
- update `InstallationGuide.md` for beginner setup or operations;
- update `DevelopmentGuide.md` for architecture and developer workflow;
- append the rationale and validation to `DevelopmentLog.md`;
- update `THIRD_PARTY_NOTICES.md` for dependency or service changes; and
- follow `docs/markdown-style-guide.md`.

Historical plans and audits live in `docs/project-history/`. Validation evidence
belongs in `docs/validation/`. Never commit checkout-root runtime JSON, `.env`
files, API keys, tokens, TLS private keys, databases, media, or logs.

## Final handoff

Lead with the outcome. Summarize changed behavior and files, compatibility and
safety decisions, exact gates and results, documentation updates, remaining
Raspberry Pi validation, and beginner-friendly manual test steps. Recommend the
next safe action. Do not claim hardware validation that was not actually run.
