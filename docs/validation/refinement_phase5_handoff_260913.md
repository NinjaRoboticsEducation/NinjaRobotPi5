# Phase 5 implementation handoff — 13 September 2026

Phase 5 software is implemented, with both new interactions disabled by default.
The hardware evaluation is complete as a documented recommendation to retain the
existing speaker and defer additional hardware. Physical acceptance has not been
performed. Phase 4 has not started.

Start with the [step-by-step walkthrough](refinement_phase5_walkthrough_260912.md).
It covers Raspberry Pi OS Lite without a desktop and distinguishes safe software
checks from sensor/output, optional actuator and power-risk work.

## Delivered behavior

| Area | Result |
| --- | --- |
| B02 expressions | Optional subtle palette variations on happy, laughing, excited and shy conversational faces. Stable within an expression opportunity. No added sound, motion, assets or changed named behaviors. |
| B04 game | Explicit 5–60 second distance/buzzer/display game; near/middle/far feedback, invalid-reading silence and finite output budgets. No wheel, camera, microphone or power commands. |
| Controls | `ninjarobot-agent game start --seconds 5`, `game stop`, `game status`; equivalent `/game` chat commands and web buttons. Stop/status bypass busy ordinary execution. |
| Agent skill | Bundled version-1 `distance-game`, restricted to the three game tools. No Phase 4 database or schema required. Natural-language interaction uses the selected model; direct commands do not. |
| Outcomes | Existing policy, IDE action ledger and local task records. A finished tool call is distinguished from a cancelled, unavailable or faulted game. |
| B05 evaluation | [Index and four option specifications](../../DevelopmentPlanDoc/hardware/HardwareOptions_260912.md), with current primary references, connection conflicts, unknown costs, proposed tests and explicit deferrals. No prototypes or purchases. |

## Reliability changes and review findings

The original distance adapter awaited a worker thread while holding a caller lock.
Cancelling that caller could release the lock without stopping the underlying
thread. It now retains and observes one owned operation, prevents read/health/
close/reopen overlap and requires explicit recovery after cancelled work.
Unresolved close retains assembly hardware ownership. Python cannot safely kill
an arbitrary blocked bus thread; service/operator recovery can still be required.

The game is admitted before resource locking. Incoming ordinary work cancels it
before waiting for shared devices. The trusted emergency-stop path remains
independent. A game cannot silently queue behind existing work or arm motion.
Read status never samples hardware. Existing system-stop error codes and statuses
were preserved after regression tests caught an initial mapping difference.

A required device being unavailable at startup reports unavailable without
blocking unrelated functions. Failed output cleanup reports a fault and blocks
conflicting work. Motion-only resume cannot clear that fault; full system resume
requires successful health checks. Late/cached/future readings are rejected and
no worker backlog or automatically replayed game is created.

The main changed files are `distance.py`, `distance_game.py`,
`expression_variants.py`, `config.py`, `robot.py`, `engine.py` and `integrated.py`
in the IDE package; and the existing runtime, CLI, IPC, web and help modules in
the Agent package. New tests live in `test_phase5_foundations.py`,
`test_distance_game.py` and `test_game_controls.py`. The existing browser
regression script now checks game controls while a start reply is pending.

## Validation evidence

All automated robot tests used fakes or simulation. No live movement, sensing,
recording, pairing, power command, private configuration or service change was
performed for this implementation.

| Check | Result |
| --- | --- |
| Managed-driver integrity | PASS: 222 tracked files, six drivers, existing 56 authorized repairs; baseline/authorization files unchanged. |
| Workspace driver sources | PASS: all six driver libraries resolve to this checkout. |
| Python compilation | PASS for Agent, IDE, scripts and tests. |
| Ruff lint and format | PASS; 425 Python files checked for formatting. |
| Mypy type checks | PASS; 100 source files. |
| Full main test suite | PASS: 842 tests, one existing deprecation warning; final run after documentation was assembled. |
| Standalone driver tests, separate processes | PASS: buzzer 68, display 65, distance 71, servo 134, camera 27, microphone 92; total 457. |
| JavaScript syntax | PASS with `node --check`. |
| Browser simulation | PASS: 16 combinations, four languages and four viewport sizes; typing, long response, speech controls, pending game start/independent stop/status and keyboard resize. No real phone or robot was contacted. |
| Skill validation and packaging | PASS: version-1 package validation; built Agent wheel includes all three skill files and the new web controls. |
| Documentation links / whitespace | PASS: 177 local file targets, 54 heading anchors and `git diff --check`. |
| Physical tests | NOT RUN. Timing, sound quality, sensor response and operator acceptance remain required. |

The full gate was run after implementation increments. Intermediate main-suite
results were 802, 831 and 838 passes; later robustness tests increased coverage.
The final suite retains the existing Starlette/HTTPX deprecation warning. The
separate microphone suite also reports the existing Python `audioop` deprecation.
Neither is a new driver modification or a reason to claim hardware failure.

Reproduce from the repository root:

```bash
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py
uv run --frozen --no-sync python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen --no-sync pytest -q
node --check ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js
git diff --check
```

The browser script requires its separate test environment with Playwright 1.55.0
and Chromium. The existing isolated environment was used; neither dependency was
added to robot runtime requirements. Run each managed driver's tests in its own
pytest process, as in `uv run --frozen --no-sync pytest -q pi5buzzer/tests`.

## Documentation and wiki impact

Updated the root README, wiki README, master/Phase 5 plan checkpoints, example
configuration, walkthrough and this handoff. New complete Installation Guide,
Development Guide, MCP/Skills Guide and Development Log sources live under
`ninjarobot_pi5_wiki/raw/{articles,notes}/ninjarobotpi5/2026-09-13/`.
Registered originals were preserved. No runtime dependency or external service
was added; `THIRD_PARTY_NOTICES.md` was reviewed and needs no new runtime entry.

Wiki ingestion, semantic review, publication, fingerprint updates, wiki lint and
knowledge-map refresh are deferred by the owner's explicit instruction. Curated
pages and `project-knowledge.json` remain at their existing checkpoint and should
not be treated as documenting the new game. Future publication should include
the new source versions, configuration, game/help tools, sensor lifecycle,
architecture and development history, with the actual semantic diff reviewed
before application. This handoff does not claim that publication has occurred.

## Remaining acceptance and next action

1. Follow safe software checks in the walkthrough.
2. Enable the optional settings while the existing service is stopped.
3. With wheels raised, test the sensor/buzzer/display game, independent stop,
   invalid readings, duration, emergency stop and full recovery.
4. Separately test already-accepted speech and reviewed reminders alongside it.
5. Record physical timing and PASS/FAIL/NOT RUN for every manual category.
6. Decide whether the interactions feel useful. B05 prototypes and Phase 4 remain
   separate future work requiring the owner's next decision.

Rollback is to stop the game, disable the two optional settings and restart the
same service. Preserve private data and the sensor ownership repair. Do not
restore unsafe overlapping reads merely to make a failed device appear ready.
