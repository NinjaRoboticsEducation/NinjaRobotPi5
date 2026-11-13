# Gemini tool-calling resilience validation

14 November 2026. Software implementation and automated validation are complete.
Live Gemini generation and Raspberry Pi hardware acceptance remain pending.

## Scope and safety

The approved proposal is
[GeminiToolCallingRefinement_261114.md](../../DevelopmentPlanDoc/GeminiToolCallingRefinement_261114.md).
Changes are confined to Agent HTTP handling, Gemini generation, prompt guidance,
post-tool reply recovery, tests, and documentation. The IDE and all six managed
drivers are unchanged. CLI, private configuration, IPC/tool schemas, confirmation,
arming, camera consent, and safety latches retain their existing contracts.

Cloud requests can contain conversation and tool context under existing provider
settings. No live provider requests, media capture, hardware actions, account
changes, private configuration changes, deployment, or power commands were run.
The software tests use fake providers/devices and mocked HTTP transports.

## Implemented behavior

- Gemini retries HTTP 429/502/503/504 up to three times after the first attempt,
  only before receiving text or tool calls. Delay is bounded numeric
  `Retry-After`, or exponential 1/2/4 seconds with jitter up to 0.1/0.2/0.25
  seconds, capped at ten seconds. Pacing may add a wait after a shorter backoff.
- A per-provider lock serializes generation requests and enforces a 0.35-second
  gap from completion to the next request. It is not a global account quota
  limiter. All waits remain subject to cancellation and existing Agent timeouts.
- HTTP 402 is not retried; safe Gemini diagnostics direct operators to AI Studio
  billing/Prepay or an eligible unbilled Free Tier project. Shared HTTP errors
  retain provider-neutral billing hints for other adapters.
- Prompt guidance uses the injected host time for ordinary date/time questions.
  This is guidance, not a deterministic ban on `system.time.get`.
- After tools return results, provider failures during a follow-up produce a
  persisted, streamed, bounded summary of recorded outcomes. It reports denied
  and uncertain outcomes honestly and does not repeat tools. Arbitrary tool data
  and raw errors are omitted to avoid exposing secrets or personal data; detailed
  results remain in tool history. This deliberately tightens the proposal's JSON
  excerpt example. Existing spoken briefing summaries and reply counters survive.
- Partial streamed text is separated from direct outcomes. Provider streams are
  explicitly closed on consumer exit so HTTP resources and the pacing lock are
  released. Cancellation, programming errors, timeouts, and failures before tools
  retain their existing behavior.

Retries mitigate transient errors; they cannot guarantee availability. A model
catalog/health request does not prove that generation billing or quota is ready.
The implementation uses existing dependencies and services; third-party notices
were reviewed and need no new entry.

## Automated validation

Run from the repository root:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python scripts/verify_workspace_driver_sources.py
uv run --frozen python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
git diff --check
```

Phase 1 passed all gates with 1,172 tests. Phase 2 passed all gates with 1,197
tests and one existing Starlette/httpx deprecation warning. Ruff checked 480
Python files; mypy passed for 122 source files. The targeted final recovery,
prompt, and Gemini tests passed all 86 tests. Initial new-test/lint mistakes
were corrected before the passing gates.

Coverage includes every selected transient status in both generation modes,
bounded exhaustion, 402 without retries or raw-body disclosure, concurrent
pacing from completion, bounded jitter/Retry-After, and refusal to retry after
text or tool-call content. Agent tests cover streamed/non-streamed cloud,
Ollama, and model-selection failures after success or denial; persisted replies,
accurate counts, single execution, bounded summaries, uncertain execution,
first-turn failures, cancellation, programming errors, and stream cleanup.

Each driver suite must run in its own pytest process because their standalone
module names overlap. Driver-suite and final documentation results are recorded
in the final validation section below.

## Documentation and knowledge status

New full successors are under
`ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-14/` for InstallationGuide
and DevelopmentGuide, and `raw/notes/ninjarobotpi5/2026-11-14/` for DevelopmentLog.
Both READMEs link to them and label registration/review pending. Registered
originals, the knowledge map, catalog, generated pages, and review records are
preserved. No ingestion, normalization, semantic-plan application, or review
workflow ran, as requested by the owner.

`python3 scripts/wiki.py check` and `python3 scripts/wiki.py lint` could not run:
the separate wiki environment is missing. No setup or dependency installation
was performed. Direct `python3 scripts/verify_project_knowledge.py` reports
expected review drift for `agent_loop.py`, `cloud_common.py`,
`gemini_provider.py`, and `prompts.py`. Seven other reported files already drift
at `HEAD`: `web_static/agent.html`, `app-agent.js`, `styles.css`, and the four
`i18n/{en,ja,zh-CN,zh-TW}.json` files. These are pre-existing documentation
fingerprint mismatches, not changes introduced here. Hashes were not refreshed.
There are no new implementation files to map. The affected map entries already
associate these modules with architecture/features guidance. The owner should
reconcile these claims and update mappings during the deferred wiki workflow.

## Safe smoke tests

These instructions are for the owner on the Pi; they were not executed here.
Use a maintenance window: the first commands stop an existing service and its
active work. Start a fresh simulation service without `--real`; chat attaches
to whichever service is running and does not independently select simulation.

```bash
cd "$HOME/NinjaRobotPi5"
source .venv/bin/activate
ninjarobot-agent service stop
ninjarobot-agent service start
ninjarobot-agent status
ninjarobot-agent provider health gemini
ninjarobot-agent model list --provider gemini
```

Expected: simulation mode is reported. If mode is real or unclear, stop before
chat. Model health/listing indicates visibility only. Select a model already
available to your project and verify its Free Tier/billing eligibility in AI
Studio. Do not copy an assumed current model name from the historical proposal.
Then run `ninjarobot-agent chat` and enter:

1. `/disarm`
2. `What time is it right now?`
3. `Check the robot status using robot.status.`

Expected: time agrees with the Pi's clock/timezone; ordinary time questions can
use the prompt snapshot. Status runs at most once for its proposed tool call,
with a model summary or direct recorded outcome if follow-up generation fails.
Do not deliberately induce quota exhaustion or spend credits to force an error;
502/503/504 and post-tool failure injection are covered by the mocked tests.

Rollback: stop simulation if needed and select an already installed local model:

```bash
ninjarobot-agent model select qwen3:4b --provider ollama --route local
```

Use your actual installed model if different. This changes provider selection;
it does not clear latches or grant hardware authority.

## Device communication tests

Optional, using the owner's existing real-hardware setup and consent. Confirm
AI motion is disarmed. Request a known display-only expression once. Expect one
local expression result and an honest completion summary; no movement or capture.
If communication fails, stop the behavior with `/stop` or the existing emergency
stop, retain the failure status, and return to simulation. Provider switching is
not a substitute for checking a device or safety latch.

## Actuator-moving tests

Optional and separate from smoke tests. Raise wheels clear of the surface on a
stable stand, check calibrated safe motion limits, and keep an operator ready to
remove power. Only after those checks, use `/arm`, request one short known-safe
movement, and then `/disarm`. Expected: the movement executes once; a failed
model follow-up reports the recorded outcome without repeating motion. If the
outcome is uncertain, stop and inspect the device rather than resending it.
Rollback: use `/stop` or Emergency Stop, disarm, and return to simulation.
These are physical actions; they are not part of automated validation.

## Power-risk tests

No boot, systemd, sudoers, UPS, shutdown, or power helper changed. No live power
command is required or authorized by this validation. Rollback needs no power
configuration changes.

## Acceptance checklist and rollback

- [x] Required phase-one and phase-two software gates pass.
- [x] No managed-driver or IDE implementation changes.
- [x] Recorded outcome summaries omit arbitrary tool data and raw errors.
- [ ] Owner confirms live Gemini billing/model eligibility and simulation chat.
- [ ] Optional real device communication acceptance.
- [ ] Optional raised-wheel actuator acceptance.
- [ ] Owner registers, ingests, and reviews the new raw sources after testing.

To undo this patch, restore the four Agent runtime modules and their three test
files together from the prior reviewed revision, preserving unrelated work.
Restore README links consistently if withdrawing the new raw manuals. Do not
regenerate immutable-driver baselines or delete historical registered sources.

## Final validation results

The final documentation-phase gate passed: immutable-driver verification (226
tracked files plus the existing 67 authorized repairs), workspace driver source
verification (six libraries), compilation, Ruff lint, Ruff formatting (480 files),
mypy (122 modules), `pytest -q` (1,197 passed), and `git diff --check`.
The main suite retained one existing Starlette/httpx deprecation warning.

Standalone suites ran as separate `uv run --frozen pytest -q DRIVER/tests`
processes and passed:

| Driver | Passed |
| --- | ---: |
| `pi5buzzer` | 68 |
| `pi5camera` | 27 |
| `pi5disp` | 65 |
| `pi5mic` | 92 |
| `pi5servo` | 159 |
| `pi5vl53l0x` | 71 |

Total standalone driver cases: 482. The microphone suite retained the existing
Python `audioop` deprecation warning. No driver source or authorization manifest
was modified. Registered predecessor manual bytes were compared against `HEAD`
and remain unchanged. Local links and anchors passed in all six changed/new
Markdown documents. The installation guide's TOML example validates with the
existing `RobotConfig` schema in the frozen project environment.

Wiki check/lint remain unavailable for the missing-environment reason above.
The standalone knowledge verifier still reports exactly the four changed
implementation mappings and seven pre-existing web-asset fingerprint mismatches;
no new mapping, manual, or link failures were introduced. No fingerprints were
refreshed to hide this pending review.

For setup and troubleshooting, use the
[new installation manual](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-14/InstallationGuide.md)
and [development manual](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-14/DevelopmentGuide.md).
