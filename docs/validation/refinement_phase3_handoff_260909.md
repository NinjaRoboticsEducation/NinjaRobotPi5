# Phase 3 implementation handoff — 9 September 2026

Phase 3 H02/B01 software is implemented. **Pause before Phase 4 until the owner
confirms acceptance.** Start with the
[step-by-step setup and manual tests](refinement_phase3_walkthrough_260909.md).
Physical acceptance is pending; no automated result below proves audibility.

## Scope and decisions

The owner approved Phase 3 and requested English first, optional Japanese/Chinese,
a free local speech engine, and an unpaired Bluetooth speaker. Piper 1.8.0 is the
selected optional local engine. English has a pinned explicit voice download;
Mandarin accepts a suitable operator-supplied model. Japanese speech is deferred.
There is no cloud speech provider or speech API charge. The selected conversation
model's existing privacy and charges remain unchanged.

The latest instruction skips wiki ingestion and review workflows. Consolidated
manual revisions are prepared below; registered sources, searchable pages,
review records and the knowledge map remain unchanged. The reference to a Phase 2
documentation checkpoint was interpreted in context as the requested Phase 3
handoff. The owner reports Phase 2 manual tests and wiki maintenance completed;
the coding agent has not independently repeated those physical tests.

## Changed implementation

| Area | Files and behavior |
| --- | --- |
| Agent speech | `speech.py`, `service_main.py`, `runtime.py`: bounded local synthesis, optional reply output, service-session controls, four-job limit, cancellation and text fallback. Simulation does not load Piper. |
| IDE audio | `audio_output.py`, `audio_process.py`, `integrated.py`, `config.py`: explicit PipeWire output, validated PCM WAV, bounded child processes, no default-device substitution, stale-output rejection. |
| Coordination | `voice_input.py`, `microphone.py`, `robot.py`: balanced pause reservations, active-capture priority, manual/output exclusion, existing speaking face, foreground and safety preemption. |
| Reminders | Agent task models/service/controls/tools: reviewed `speech` notification and saved `en`/`zh` language, honest delivery evidence, reviewed display/buzzer fallback, no fallback after explicit speech cancellation. |
| Controls | CLI help, IPC dispatch, web controller/dispatch and static UI: `/speech` and dedicated buttons; controller speech controls bypass an ongoing chat's operation lock. |
| Setup | `requirements/local-speech.in`, `requirements/local-speech.txt`, `scripts/prepare_speech_voice.py`: isolated pinned packages and preview-first hash-verified English download. No install/start/pair/play side effect without operator commands. |

No managed Pi5 driver, hardware interface, wheel behavior, power path, root Python
dependency lock, live private configuration or database was changed. Existing
configuration gets disabled speech defaults. New fields are additive; old reminder
records default to English. Downgrading to older code requires removing its unknown
speech configuration and addressing new speech reminder records; see rollback.
No calendar-write, briefing, personality-profile or Phase 4 functionality was added.

## Validation evidence

Commands ran from the repository root with `--no-sync` to preserve the existing
working hardware environment:

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

| Gate | Result |
| --- | --- |
| Immutable drivers | Pass: 222 tracked files, six drivers, 56 existing authorized repairs. No new driver repair. |
| Workspace driver sources | Pass: all six execute from this checkout. |
| Compilation, Ruff lint/format, JavaScript syntax, diff whitespace | Pass. |
| Mypy (static type checking) | Pass: 91 source files. |
| Root tests | Pass: 772 tests, one existing Starlette TestClient deprecation warning. |
| Added/changed documentation local links | Pass: ten changed/new documents checked with the repository local-link validator, zero errors. |
| Wiki ingestion, semantic review and publication | Skipped under the latest owner instruction; no claim of current Phase 3 search coverage. |
| Physical playback, Bluetooth pairing, real capture, actuators, boot-service access | Not run; manual acceptance required. |

New regression coverage includes no-shell subprocess execution, bounded output and
timeouts, temporary-file cleanup, output disconnect/cancel handling, playback
cleanup before microphone release, stale generation rejection, listener recording
priority, reservation rollback, explicit microphone disable, cancelled queues,
unchanged text replies, reminder approval/language persistence, independent Stop
Speech on a busy web connection, and offline/idempotent voice-download preparation.
No live speaker, microphone, motors or power commands are part of these tests.

The optional requirements were resolved and hashed, not installed. No actual Piper
model inference or speaker output was benchmarked. Pi latency, device buffering,
OS compatibility and boot-session access remain explicit acceptance items.

## Consolidated documentation and deferred wiki work

The original registered manuals are preserved byte-for-byte. These complete new
source versions contain Phase 3 additions and updated checkpoint wording:

- [Installation Guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-09-02/InstallationGuide.md)
- [Development Guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-09-02/DevelopmentGuide.md)
- [MCP and Skills Guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-09-02/NinjaRobot_MCP_Skill.md)
- [Development Log](../../ninjarobot_pi5_wiki/raw/notes/ninjarobotpi5/2026-09-09-02/DevelopmentLog.md)

README, refinement plan/progress, third-party notices and the walkthrough are also
updated. The README explains that existing wiki/manual pointers remain at the
published earlier checkpoint. The new raw sources above have **not been ingested**.

When the owner resumes wiki maintenance, register these versions, update affected
installation/architecture/features/history/reference pages from the actual code,
classify the new speech/setup/test files in the knowledge map, review changed
fingerprints, and prepare the normal semantic diff and pointer changes. Do not
mark old page reviews as reviews of Phase 3. Run the knowledge/wiki gates after
publication. No stale fingerprint was rewritten merely to make a gate green.

## Remaining acceptance and next action

Follow the walkthrough's separate safe smoke, device communication, consented
microphone, optional actuator and power-risk sections. No live shutdown test is
required. Check English first, same-browser Stop, disconnect/reconnect, microphone
state preservation and spoken-reminder fallback before enabling persistent speech.
Test the actual boot-service account separately if using boot startup.

Use `/speech off` for immediate rollback; preserve the installed voice and private
data. Leave Phase 4 untouched until the owner confirms. The unrelated Traditional
Chinese display-font proposal and strict monetary spending cap remain pending.
