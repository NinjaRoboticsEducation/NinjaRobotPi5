# Phase 3 follow-up: investigation and implementation plan

This plan addresses the owner's Phase 3 acceptance findings: simpler Bluetooth
setup, complete spoken replies, natural-language command help, stable web controls,
bounded task retrieval and consistent documentation. It preserves the current
Agent -> IDE -> managed driver -> device architecture. Phase 4 and Phase 5
implementation remain outside this work.

**Status: investigation completed to the extent possible without new physical
tests; implementation approval pending.** Prepared 10 September 2026 against
checkout `7badd66`. The working tree was clean at the start. No runtime file,
driver, live configuration, service or wiki publication was changed during this
investigation. This document is a proposal, not an implementation completion report.

The owner has clarified that **automatic speaker reconnection must work both
while the Agent runs and while it is stopped**. The design therefore includes an
independent, optional user service. It must never start the Agent or robot hardware.

## Contents

- [Evidence and remaining questions](#evidence-and-remaining-questions)
- [Delivery sequence](#delivery-sequence)
- [Bluetooth connection and independent reconnection](#bluetooth-connection-and-independent-reconnection)
- [Complete speech from the first word](#complete-speech-from-the-first-word)
- [Natural-language command help and Guided Checks](#natural-language-command-help-and-guided-checks)
- [Stable web layout and Speech ON/OFF buttons](#stable-web-layout-and-speech-onoff-buttons)
- [Bounded scheduled-task retrieval](#bounded-scheduled-task-retrieval)
- [Documentation reconciliation](#documentation-reconciliation)
- [Validation and acceptance](#validation-and-acceptance)
- [Approval boundary](#approval-boundary)

## Evidence and remaining questions

Serena symbol tools and direct source inspection were used to trace the relevant
paths. The knowledge skill, documentation skill, Pi validation skill, current
manuals and upstream references inform this proposal. The earlier Phase 3
[handoff](../docs/validation/refinement_phase3_handoff_260909.md) and
[walkthrough](../docs/validation/refinement_phase3_walkthrough_260909.md) remain
the baseline, qualified by the owner's newer acceptance observations.

| Issue | Evidence from the current implementation | Confidence and implication |
| --- | --- | --- |
| Bluetooth setup | `interactive_tool.py` offers hardware/behavior menus but no speaker wizard. The manual requires separate BlueZ, user audio-service, headless-policy and configuration steps. In the previous live support session, pairing/trust already existed; stopped audio services prevented a useful connection. | Confirmed usability and readiness gap. Pairing alone is not proof that an audio output exists. |
| Automatic reconnection | No project-owned independent reconnect service exists. Saved BlueZ trust and a speaker's own last-device behavior do not guarantee reconnection after every power order. | Confirmed capability gap for the clarified requirement. An Agent-only retry loop would be insufficient. |
| Missing opening words | `LocalSynthesizer.synthesize` writes all supplied text into a completed WAV audio file. `AudioOutput._play_stream` opens a fresh `pw-play` process for each utterance and sends the file immediately. Text sanitization limits the end, not the beginning. | Playback/transport startup is a plausible cause, not yet proven. Compare generated audio, stream startup and audible output before selecting a repair. |
| Natural-language help | Commands live in CLI/controller handlers and help text. Runtime skills are loaded when `skill_id` is explicitly supplied. A new skill file alone would not make ordinary conversation reliably select it. | Confirmed discoverability and activation gap. Add a command catalog, read-only lookup and real natural-language routing. |
| Web geometry | `.controls-panel` declares four explicit grid rows but now contains five sections. The extra speech dropdown also puts unrestricted diagnostic text inside a height-constrained panel. `visualViewport` resize events resize the entire shell while body/panels hide overflow. | Structural mismatch confirmed. Keyboard, focus zoom, orientation and result-size effects still need browser reproduction to identify the exact device-specific sequence. |
| Guided Checks | `onboarding.py` provides five useful read-only onboarding/troubleshooting steps. It does not create reminders or perform its suggested actions. It occupies a full hamburger-menu section. | Preserve its useful service and move access into chat help. Removing its backend would discard valid diagnostics unnecessarily. |
| Task-list exception | `TaskService.list` loads up to 100 full records of mixed kinds/statuses. `TaskControls.list` exports every field. `AgentLoop` serializes the complete result into a `ModelMessage` capped at 20,000 characters. | Reproduced with synthetic data: 100 simple reminders produced 50,065 characters and `string_too_long`. `/tasks` has a separate 15,000-character display guard, explaining the different behavior. |
| Documentation | Seven current entry documents have zero local-link errors. README links to prepared Phase 3 Lite manuals, while `project-knowledge.json` and curated pages still describe the registered Phase 2 checkpoint. | Confirmed freshness/publication mismatch. The filename `InstallationGuide.md` is valid; current targets, status and claims need reconciliation. |

Pending user details are the affected device/browser/orientation and whether speech
loses words on every reply or only after silence/reconnection. Until supplied,
cover desktop Chrome, Android Chrome and iPhone Safari, and both cold and immediate
repeat playback. These assumptions guide reproduction; they do not establish a
physical cause or a browser test pass.

## Delivery sequence

Each increment has its own focused tests, full project gate, documentation notes
and reviewable diff. Stop to repair failures before proceeding. Full manual and
wiki changes are consolidated at the end, respecting the owner's previous request
to avoid repeated ingestion/review during implementation.

| Increment | Objective and likely files | Compatibility, validation and documentation | Risk |
| --- | --- | --- | --- |
| R0 | Preserve baseline; reproduce task overflow, browser behavior and speech startup. Existing tests plus temporary synthetic fixtures. | Record confirmed versus suspected causes. Do not use private conversation data or live devices in automated tests. | Read-only/simulation |
| R1 | Compact paginated task queries and a central model-result size boundary. Agent `task_service.py`, `task_tools.py`, `task_controls.py`, `agent_loop.py`, persistence/prompt integration as needed. | Keep the 20,000-character limit and existing task storage/approval semantics. Test large histories, ownership and incomplete tool turns. Document paging. | Private-data handling |
| R2 | Shared command help, runtime help skill, natural-language routing and chat access to Guided Checks. Agent command catalog/provider, `skills.py` integration, bundled package, runtime, CLI/IPC/web dispatch. | Help is read-only and cannot grant permissions or operate devices. Existing commands continue to work. Test actual ordinary-chat activation. | Low, no hardware effects |
| R3 | Repair web geometry; replace A/B with Speech ON/OFF; remove the speech dropdown and Guided Checks panel. `web_static/`, `web_control.py`, shared speech state/events. | Preserve independent OFF/stop handling, lease checks, emergency controls and existing behavior tools. Browser layout and interaction tests, all UI languages. | Controller reliability |
| R4 | Bluetooth wizard and independent reconnect helper. IDE CLI/menu, new Bluetooth adapter/service module, configuration serialization, optional dependency and user-service template. | No robot startup or driver changes; save selected-device identity only after verified setup. Fake BlueZ, config, lifecycle and packaging tests. Lite setup/rollback docs. | OS Bluetooth, user services and private configuration |
| R5 | Repair the proven speech-start fault within the existing synthesis/IDE playback path. `speech.py`, `audio_output.py`, `audio_process.py`, config if justified. | Preserve all words, output selection, duration/size budgets, mic ownership, cancellation and text fallback. Cold/warm and failure tests. | Audible output during consented acceptance |
| R6 | Consolidated regression, current manuals, README, walkthrough, handoff and reviewable wiki proposal. | Record software/physical/browser results separately; publish only the approved semantic diff. Pause before new refinement phases. | Documentation; publication approval |

R4 readiness and R5 stream-start handling are coordinated but solve different
problems. Reconnection must not replay interrupted speech. Do not make the UI or
task fixes depend on the purchase of another speaker or an architecture replacement.

## Bluetooth connection and independent reconnection

### Proposed user experience

Add **Bluetooth Speaker Connection** to `ninjarobot-ide-tool`, retaining existing
menu identifiers where practical. Opening it must not construct `RobotAssembly`
or initialize motors, display, camera or microphone.

1. Inspect Bluetooth, same-user PipeWire/WirePlumber, the installed Bluetooth audio
   plugin and the headless configuration. PipeWire is the OS audio service;
   WirePlumber manages its devices and routing.
2. Explain any missing prerequisite in one actionable message. Start already
   installed user audio services when permitted, and wait for the audio profiles
   to register. Do not call connection success before those services are ready.
3. Start a bounded discovery session automatically, then show a stable numbered
   snapshot: friendly name, short identifying address and paired/connected status.
   Offer Rescan and Cancel. Sanitize names against terminal escape sequences.
4. Map the chosen number to a captured device identity, not a changing row index.
   Pair only if necessary, trust that selected device, connect and verify the
   Bluetooth audio output. Do not remove existing bonds merely to retry.
5. Save the verified output node, Bluetooth address, adapter identity and automatic
   reconnect preference. Display **Connected and saved** only after persistence
   succeeds. Partial success must say what worked and what remains unsaved.
6. Offer an optional short audible test with a stated volume. Selection/setup is
   not consent to microphone capture or robot startup. Leave speech enablement,
   voice input, existing voice models and unrelated settings unchanged.

If pairing requires a PIN or numeric confirmation, show the request for the
selected device rather than approving all incoming pairing requests. Keep unrelated
devices untouched. A missing audio profile, missing user bus, blocked radio,
unavailable speaker, other connected host, pairing rejection and timeout each
need a distinct recovery instruction.

### Implementation design

Use an IDE-owned Bluetooth backend with injected fake implementations. Prefer
BlueZ's structured D-Bus interface, the OS service communication interface, over
parsing human-readable terminal output for every state transition. Introduce a
small optional maintained Python D-Bus client only after pinning its compatible
version, provenance and license. No new agent framework is needed.

Follow the primary [BlueZ device interface](https://bluez.readthedocs.io/en/latest/device-api/),
[discovery interface](https://bluez.readthedocs.io/en/latest/adapter-api/) and
[pairing-agent interface](https://bluez.readthedocs.io/en/latest/agent-api/).
Hold a pairing agent only for this workflow; stop the discovery session and
unregister callbacks in bounded cleanup. `Connected` is an intermediate state:
the selected PipeWire sink, meaning a playback output, must also be verified.

Use a single new optional configuration section for the selected Bluetooth device
and reconnect preference. Keep `speech_output.output_node` compatible. The wizard
must receive the actual `--config` path; it must not write a different default file.
Extend `RobotConfig` and `robot_config_to_toml` together and reuse the existing
private atomic save procedure. Reload/check the latest configuration before save,
preserve unrelated values and detect concurrent edits. Back up before an update.

Do not start or stop an active robot implicitly to repair audio services. Detect
conflicting active playback/ownership and guide the operator to an idle maintenance
state. The wizard's common already-installed path should require only selection;
missing packages or privileged setup can require a clearly explained extra step.
Preview and obtain OS permission for package or service installation, rather than
silently running broad `sudo` commands or rewriting global Bluetooth policy.

### Independent reconnect service — owner-confirmed requirement

Provide an optional **user-level systemd service**, a background process owned by
the normal robot account, with these contracts:

- Run independently of the Agent and read only the selected-device configuration.
  No `RobotAssembly`, model, camera, microphone, servo or display startup.
- Reuse the same Bluetooth backend as the wizard. Avoid separate competing retry
  loops in the Agent and helper. Serialize wizard/reconnect work for the selected
  device and suspend retries while maintenance changes that selection.
- Connect only the saved paired/trusted device. Never discover broadly, pair new
  devices, increase volume, clear bonds or enable speech in the background.
- React to device/service state changes and retry with increasing delays, capped
  at a modest interval. Bound every attempt. A powered-off speaker is an ordinary
  unavailable state, not a tight log loop or a reason to restart Bluetooth globally.
- Continue attempts after a long speaker-off interval, so reconnection is not
  limited to the first minute after a lost link. Handle Pi-first, speaker-first,
  SSH logout and ordinary supervised boot sequences.
- Re-resolve only the selected speaker's output identity after reconnect; never
  fall back to another audio device. Coordinate node-name changes with the existing
  IDE audio selection rather than rewriting private config on every poll.
- Provide status, pause/disable, retry-now and explicit disconnect behavior. A
  deliberate disconnect must pause reconnection until the user resumes it;
  otherwise the helper would immediately undo the user's action.
- Cancel pending work and release the OS service connection on shutdown. Never
  replay a previously interrupted utterance or automatically speak a greeting.

The wizard prepares the exact user unit, executable/config paths and necessary
headless audio settings. Installation is idempotent, meaning rerunning it preserves
an already correct setup. It previews changes and preserves existing settings.
User lingering, which keeps user services available without an SSH login, is
needed for logout/boot availability and must be explained with its rollback.
Do not change the existing Agent boot template or enable the Agent as a side effect.

The installed WirePlumber version determines its configuration format; see the
[upstream headless Bluetooth guidance](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html).
Tests must cover supported 0.4/0.5 formats without writing live user or system files.

## Complete speech from the first word

Do not label a startup delay as the root cause until the following comparison
separates text generation, synthesis and physical playback:

1. Use a fixed harmless phrase beginning with distinct words, such as “One, two,
   three. This is the beginning of the robot reply.” Capture the sanitized text
   and generated WAV only in an explicitly temporary diagnostic location.
2. Verify the text retains its prefix, the WAV header/frame count is valid, and
   the synthesis call finishes successfully. Compare the original waveform with
   the exact bytes handed to playback. A waveform check alone cannot identify
   spoken words; the operator must listen to the diagnostic comparison.
3. Compare first playback after connection, first playback after idle, and an
   immediate second playback of the same generated file. Record first-word
   audibility separately from process exit status. A wired output comparison is
   optional only if already available; do not require buying hardware.
4. Observe stream/transport activation and sink state without recording the room.
   Check whether early frames precede the usable audio route, and whether a
   supposedly connected sink is still suspended or starting.
5. Fix the stage demonstrated to lose content, then repeat the same comparison.
   If the WAV itself lacks the words, address text/synthesis first. If it is
   complete and only cold playback loses them, address output startup.

For a confirmed output-start fault, prefer a bounded pre-roll in the **same owned
playback stream**, with readiness checks and a configurable measured lead-in, over
sleeping before opening the stream or inserting repeated spoken words. Pre-roll
means sending initial audio frames before speech to allow the route to settle.
Do not assume digital silence wakes every speaker; validate it on this Bose and
revise the strategy if it does not. Any necessary audible cue needs explicit
product approval rather than being hidden inside a repair.

Preserve original speech samples and valid PCM framing, the audio format already
validated by the IDE. Include any lead-in in byte, duration and timeout budgets.
The same cancellation, foreground, microphone pause and generation checks must
cover preparation, lead-in, speech and cleanup. No perpetual keepalive playback,
second player, duplicated words, default-device fallback or automatic replay.

Keep Piper 1.8 and English as the baseline unless the diagnosis demonstrates an
engine issue. The [Piper CLI documentation](https://github.com/OHF-Voice/piper1-gpl/blob/v1.8.0/docs/CLI.md)
and [PipeWire playback interface](https://docs.pipewire.org/page_man_pw-cat_1.html)
explain their separate roles. A new persistent TTS server is not the default fix.
Physical first-word acceptance remains required even when all fake tests pass.

## Natural-language command help and Guided Checks

Create a reviewed **command catalog** with feature name, natural-language aliases,
exact command, short explanation, requirements, effect/permission category and
safe examples. Use it for `/help`, topic help and the new bundled runtime Agent
Skill. This is a runtime skill under `bundled_skills/`, not a developer `.agents`
skill or the full deferred Phase 4 wiki-query provider.

Add a bounded read-only lookup tool and integrate natural-language activation in
normal chat. Current explicit `--skill` selection must continue to work. A package
that is never selected by ordinary chat does not meet the requirement. The catalog
should be registered with the running tool/command availability and covered by
tests against handlers so new commands cannot silently miss help coverage.

For “Can you turn on the audio and voice out your answer?”, give the actual
`/speech on` instructions or identify missing setup. Explain the difference
between spoken output and voice input. Under this requested help scope, do not
silently enable microphones, modify configuration or claim speech was enabled
merely because the model described the command. Do not bypass the trusted controls.

Provide concise English-first explanations for speech, voice input, tasks, memory,
identity, skills, safe behavior use and diagnostics, expanding from the actual
command inventory. Bound lookup query, result count and returned text. Do not load
the entire command/manual collection into every model message.

Move Guided Checks to proposed `/guide` and `/guide 1` through `/guide 5` commands,
available in both terminal and web chat. Preserve its backend and existing
interactive-menu access. General help describes its purpose; detailed diagnostics
are returned only on request, bounded and stripped of secrets. Remove its main
web-menu section and unused listeners without disturbing local task controls.

Test natural paraphrases, unrelated task queries, negation, unavailable features,
explicit skill selection, normal chat activation and zero side effects from help.
Keep actual scheduled-task retrieval routed to task data, not a generic how-to
answer. Existing permission-sensitive commands retain their current authorization.

## Stable web layout and Speech ON/OFF buttons

Use a fake controller transport for browser reproduction; it must not connect to
the real robot. Test typing, multiline input, keyboard open/close, panel toggles,
long/unbroken content, reply streaming, orientation and reconnect.

1. Replace the speech dropdown and A/B behavior bindings with **A. Speech ON** and
   **B. Speech OFF**, calling the existing speech-control service. OFF must stop
   active/queued speech and suppress later replies. Preserve `/speech stop`, status,
   outputs and language commands through help; remove only their dropdown UI.
2. Preserve Greeting and Celebrate as existing robot behaviors/tools. Removing
   their two shortcuts must not delete the underlying functions or startup greeting.
3. Correct the control grid to match its actual children. Give messages and details
   their own bounded scrolling, and stop content size from expanding the shell.
   Essential controls must stay reachable on short screens instead of being clipped.
4. Treat keyboard appearance, browser toolbar changes and physical orientation
   separately. Review the current small input font and focus behavior on Safari.
   Use viewport dimensions deliberately rather than resizing every panel blindly.
   Preserve user zoom and accessibility; do not disable zoom as a layout fix.
5. Preserve the existing physical-orientation/movement safety behavior. A virtual
   keyboard must not be mistaken for device rotation or cause unexpected motion.
   Do not silently remove the portrait safety rule without reviewing its purpose.
6. Keep scrolling inside the conversation. Follow streamed text when already near
   the bottom; preserve the reader's position when reviewing an older message.
   Modal focus and restoring focus must not scroll the entire app unexpectedly.
7. Display concise acknowledged speech state, including pending/error states, with
   proper labels in all four current UI languages. Reconcile state on connection
   and changes made through another chat. ON/OFF must not show success before the
   service accepts the request. Remove null references to deleted DOM elements.
8. Keep speech controls on the existing independent dispatch path: OFF cannot
   wait for a busy conversation lock. Preserve emergency stop, pairing, leases,
   movement release, microphone consent and power confirmation behavior.

Use real browser automation such as Playwright in an isolated development/test
environment if compatible binaries are available; no browser dependency belongs
in the deployed robot runtime. The existing web tests largely check protocol and
static assets, so they cannot establish rendered layout correctness. Add measured
layout assertions and keep real iPhone/Android keyboard acceptance separate from
desktop emulation. [Visual viewport behavior](https://developer.mozilla.org/en-US/docs/Web/API/VisualViewport)
provides the browser-level distinction used by this investigation.

## Bounded scheduled-task retrieval

Keep the existing `ModelMessage` 20,000-character bound. Fix both the task data
shape and the generic point at which tool data becomes a model message.

1. Add an owned paginated task query in `TaskService`. Apply owner, kind and status
   filters in the database before limiting. Use stable ordering and a validated
   continuation token; never let a cursor select another user's records.
2. Preserve `tasks.list` and empty-argument calls. Add optional bounded filters and
   paging fields. For a scheduled-reminder question, request reminders awaiting
   delivery rather than dumping completed requests, approvals and internal evidence.
   Drafts are not scheduled; completed/missed/cancelled history remains explicitly
   accessible. Preserve existing direct/web listing contracts or extend them
   additively rather than replacing full records everywhere.
3. The model-facing page includes complete task ID, content/title, state, exact
   due time and time zone, repeat and delivery mode. Exclude internal scope/session
   IDs, every step's evidence, duplicate timestamps and large historical results
   from ordinary listings. Provide an owned detail lookup when requested.
4. Start with roughly ten entries and a conservative serialized page budget, such
   as 12,000 characters including metadata. Measure the actual JSON string, which
   can expand during escaping. Return count, `has_more` and a continuation token.
   Do not silently hide the fact that more tasks exist or cut a task ID in half.
5. Ask the model for a concise list containing each returned task's ID and content,
   plus due time when relevant. For many tasks, say how many are shown and offer
   the next page. Do not automatically fetch all pages into one prompt.
6. Add a central model-safe tool-result formatter before `ModelMessage`
   construction, covering ordinary and special tool routes. Preserve call identity,
   actual status, error/retry evidence and explicit omissions. An oversized result
   from another provider must produce a valid bounded summary, not crash or
   reclassify an already-executed effect as never executed.
7. Keep detailed results in their existing authorized private receipt/history path
   where appropriate; the model sees only the bounded projection. Do not spill
   private results into public logs or temporary repository files.
8. Test a second chat turn after an oversized result. Inspect history produced by
   the old failure, which may contain an assistant tool call without its reply.
   Recover conservatively using stored evidence; do not delete user history or
   replay an uncertain action simply to repair a message sequence.

Test zero, one, 100 and larger synthetic task collections; long titles/results,
escaped/Unicode text, page boundaries, deleted/changed records, ownership switches,
invalid cursors, mixed history and model output limits. Verify exact IDs/content
and complete paging, not just the absence of an exception. Do not expose a model
confirmation endpoint or change reminder delivery semantics.

## Documentation reconciliation

Inventory tracked project documentation and distinguish current instructions from
dated evidence, registered originals, external references and generated content.
Historical records must remain honest; making all old documents claim current
behavior would destroy the development history.

Update README and the wiki README, current full Installation/Development/MCP and
Skills Guides, a new Development Log version, Phase 3 walkthrough/handoff, progress
and relevant architecture/setup references. Use new raw source versions under
`ninjarobot_pi5_wiki/raw/`; do not overwrite registered originals. Preserve useful
Lite corrections already prepared in `2026-09-09-03`.

Review actual link targets and heading anchors, command names, optional package
installation, new wizard and independent service, output settings, spoken-reply
controls, help, task paging and current limitations. Distinguish browser speech
recognition from local spoken output. Keep English support, optional Mandarin,
unsupported Japanese speech and the separate monetary-cap gap accurate.

The owner's current report establishes that Phase 3 functions were tested with
remaining defects. The earlier support session established Bose audibility at
75%, not complete first-word delivery or boot reconnection. Date these observations
and remove misleading current “not tested at all” wording without rewriting old
test evidence into new passes.

At the consolidated checkpoint, prepare the exact wiki semantic diff (the proposed
changes to documented meaning), review records and manual-pointer updates. Show
them for approval before applying. Reconcile published Phase 2 pointers with the
actual current sources, review affected implementation fingerprints and run the
knowledge checks. Do not blindly refresh hashes or claim human review for AI work.
While approval is pending, clearly identify prepared manuals versus published pages.

## Validation and acceptance

### Investigation evidence

- Managed-driver verifier: pass, 222 files across six drivers plus 56 previously
  authorized repairs. No new managed-file authorization or change.
- Workspace driver sources: pass, all six resolve directly to this checkout.
- Seven current entry documents: zero local-link errors.
- Task overflow: reproduced through the actual task provider and `ModelMessage`
  using 100 synthetic reminders; 50,065 serialized characters; `string_too_long`.
- No private task database, recording, robot action or new audible test was used.
- Focused baseline suite: 26 tests passed in 1.39 seconds outside the sandbox
  with a 90-second outer limit. The initial sandbox run stalled without output
  and was stopped; it is not counted as a pass. The passing suites cover task
  tools, speech, audio output and Guided Checks.

### Software gate after every implementation increment

From the repository root in the reviewed development environment:

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

`--no-sync` preserves the working hardware environment. New optional dependencies
must first be pinned and tested in an explicitly prepared isolated environment;
this flag must not conceal missing dependencies. Run separate managed-driver suites
if needed; preserve the immutable baseline and authorization ledger. Add packaging,
config round-trip, service dry-run, browser and documentation checks as applicable.

### Manual acceptance and rollback

| Category | Acceptance | Rollback |
| --- | --- | --- |
| Safe smoke | Fake Bluetooth discovery/pairing errors, duplicate names, cancellation, saved-config failures; large owned task pages; help with no device calls; browser fake transport. | Disable optional feature in test configuration; remove only test state. |
| OS/device communication | Selected real speaker pairs/connects; verified output saved; reconnect after speaker power cycling with Agent running and stopped; survives SSH logout and a separately supervised boot. | Pause/disable only the new reconnect unit and restore its reviewed configuration backup. Preserve existing bonds and other user services. |
| Audible output | Operator hears the first word on cold, warm, idle and reconnected playback; OFF/stop cancels preparation and sound; no fallback/replay on another speaker. | Speech off; disable the new lead-in setting if present; preserve voice files. Report unresolved silence honestly. |
| Optional microphone | Existing listener pause, manual disable and recording priority remain correct. Consent required; no retained media. | Voice input off and speech off. |
| Browser interaction | Typed/streamed content and keyboard/panels stay usable on the reported browser and test matrix; ON/OFF works while chat is busy; essential stops remain reachable. | Existing terminal stop/speech controls; revert only the reviewed UI increment if necessary. |
| Actuator-moving | Not needed for core repair. Any requested regression uses raised wheels and an operator ready to remove power. | Existing movement stop, disarm and safety recovery. |
| Power risk | No live shutdown or unattended reboot in automated tests. User-service installation is previewed and tested with fake filesystem/commands. | Disable only the newly installed helper; restore original user-service settings when explicitly appropriate. |

Deliver an updated step-by-step Lite walkthrough and a pass/fail handoff with exact
software results, user-observed physical results, unresolved issues and rollback.
Do not describe the work as complete until the implementation gates pass and any
remaining physical or publication acceptance is clearly identified.

## Approval boundary

Approve R0–R6 as a Phase 3 follow-up before implementation. This includes the
owner-confirmed independent reconnect service, read-only natural-language help,
moving Guided Checks into chat help, and the requested A/B speech controls.
No managed driver change, Phase 4/5 implementation, account action, push or release
is included. The exact later wiki publication diff requires its normal approval.

The required approval comes from [AGENTS.md](../AGENTS.md#3-propose-a-phased-plan):
“Obtain explicit approval before implementation.” Browser/device details and the
first-word failure pattern remain useful for reproduction; no unproven speech
cause is presented as established by this plan.
