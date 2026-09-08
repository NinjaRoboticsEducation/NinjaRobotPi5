# NinjaRobotPi5 refinement plan — 7 September 2026

The goal is to turn NinjaRobotPi5 into a dependable desktop assistant: a robot
that listens, explains what it is doing, remembers useful preferences, and
finishes everyday tasks. It should feel approachable while remaining predictable
when a service, connection, or device fails.

AI means artificial intelligence: software that interprets information and proposes
responses or actions. In this project, the Agent handles conversation and tool
decisions; the IDE is the layer that coordinates devices and safe execution.

This plan builds on the existing project. It does not replace the robot's
framework, and it does not authorize implementation, hardware operation, or
deployment. All checklist items below are proposals, not newly available features.

**Status:** revised on 7 September 2026 against the owner's
[refinement confirmation list](NinjarobotPi5_RefinementConfirmation_260907.md).
31 items are confirmed, H01 is narrowed to system logs, and seven items are
deferred. Scope confirmation is recorded; no implementation is marked complete.
This document is the main planning reference for the next stage. Current behavior
remains documented in the [local knowledge base][N-wiki] and verified against code.

**Implementation progress — 9 September 2026:** Phase 2 core code is implemented
and the combined software gate passes 734 tests. Development pauses here for owner
manual testing; phases 3–5 have not started. The managed face cleanup was approved and implemented on 9 September; the font
repair still awaits separate approval. T07 has bounded usage/retries/time, but strict
currency-denominated spending enforcement remains an explicit requirement gap.
Physical validation is outstanding. The latest owner instruction consolidates
manual/wiki updates once at this checkpoint, replacing the earlier all-phases
deferral. See the [progress record](../docs/validation/refinement_progress_260907.md)
and [walkthrough](../docs/validation/refinement_phase2_walkthrough_260909.md).
The original planning checklist and evidence below are retained as historical
scope; they are not a claim that every approved refinement has shipped.

## Contents

- [0. Owner decisions and scope](#0-owner-decisions-and-scope)
- [1. Goals and the experience we want](#1-goals-and-the-experience-we-want)
- [2. Evidence and current project status](#2-evidence-and-current-project-status)
- [3. What to learn from the references](#3-what-to-learn-from-the-references)
- [4. Keep the existing framework](#4-keep-the-existing-framework)
- [5. Refinement checklist](#5-refinement-checklist)
- [6. How the important features should work](#6-how-the-important-features-should-work)
- [Answers to the five confirmation questions](#67-answers-to-the-confirmation-questions)
- [7. Development phases and acceptance gates](#7-development-phases-and-acceptance-gates)
- [8. Validation and measures of success](#8-validation-and-measures-of-success)
- [9. Documentation and future decisions](#9-documentation-and-future-decisions)
- [Appendix A. Complete Microduck audit](#appendix-a-complete-microduck-audit)
- [Appendix B. Complete Reachy Mini audit](#appendix-b-complete-reachy-mini-audit)
- [Appendix C. Feature comparison matrix](#appendix-c-feature-comparison-matrix)
- [Appendix D. Evidence directory and audit limitations](#appendix-d-evidence-directory-and-audit-limitations)

## 0. Owner decisions and scope

The confirmation list is the authority for this revision. Its `Confirmed` labels
mean selected for development, not completed. Its `[X]` labels mean excluded from
this development stage, not checked-off work. H01 has an explicit replacement:
record the additional lifecycle states in system logs only. This revision changes
the plan and records answers; it does not start robot implementation.

| Decision | Items | Meaning for implementation |
| --- | --- | --- |
| Confirmed | F01–F09; H02, H04, H06, H07; T01–T07; M01–M04; B01, B02, B04, B05; X01, X03, X05 | 31 selected refinements, with the concrete boundaries below. |
| Revised | H01 | Additional lifecycle reporting goes to system logs. Preserve current display/web presentation; add no H01 state animations, badges, or panels. |
| Deferred | H03, H05, T08, M05, B03, X02, X04 | No real-time spoken interruption, new desktop/quiet-hour profile, unsolicited suggestions, expanded household/privacy-management feature set, camera attention, release-updater project, or separate experience-benchmark program. |

Important boundaries prevent confirmed features from quietly reintroducing deferred work:

- H02 uses **listen-then-speak** operation. It needs bounded playback and temporary
  microphone coordination, but not H03's simultaneous speaking/listening or echo
  cancellation. Keep existing opt-in voice input and its privacy indicators.
- B01/B02 coordinate existing expressions and small variations; B04 may show
  game-specific reactions. None adds H01's rejected lifecycle presentation.
- T03 still provides requested task progress, cancellation, and results through
  existing conversational/controller routes. Those task records are distinct from
  a new general-purpose lifecycle-status interface.
- Deferring M05 leaves current user ownership, permissions, retention and deletion
  behavior in force. New task records must honor those boundaries; do not add a
  separate guest/profile/export redesign under another item.
- Deferring X04 removes a separate benchmarking initiative, not the required
  tests for confirmed work. F08 and the existing root validation gates remain.
- F05/F06 retain setup diagnosis and backup/restore repair. X02's new staged-update
  and automatic-update work is deferred.
- T02 delivers reminders the user explicitly schedules. T06 briefings and M04
  recipe suggestions are user-requested; no unsolicited T08 prompts are added.
- B05 confirms evaluation of optional hardware, not installation of every listed
  device. H02's speaker selection is the immediate hardware decision.

The appendices retain the competitor evidence. Where an appendix describes a
broader opportunity, this scope table and the updated phase plan determine whether
it is active. A future implementation proposal should carry forward these recorded
decisions and resolve only outstanding design, dependency, or hardware choices.

## 1. Goals and the experience we want

### 1.1 The problem to solve

A robot can have many commands and still be difficult to live with. Users need
to know whether it heard them, whether it understood, whether an action actually
worked, and what to do when it did not. A friendly animation cannot compensate
for a missed reminder or a misleading success message.

NinjaRobotPi5 already has much of the foundation: conversational model support,
controlled tool execution, a web controller, user memory, reusable behaviors,
and a device-coordination layer. The next stage should connect these into
complete experiences rather than add unrelated demonstrations.

The main problems are:

1. Some safety and recovery gaps identified in the previous audit remain in the
   implementation. More autonomy would increase their consequences.
2. Conversation is mainly a bounded request-and-response activity. It needs a
   clearer path to durable tasks that survive a restart or a lost connection.
3. Voice input exists, but a speaking face is not spoken audio. Natural spoken
   replies require an output device and controlled playback. Simultaneous real-time
   voice interaction is outside the selected scope.
4. Stored preferences and history need to become transparent, correctable help,
   without turning guesses into permanent facts about the user.
5. Installation and health reporting should distinguish a missing software
   package from an unavailable device, a disabled feature, and a safety stop.
6. Task results and recovery must remain understandable in conversation, while
   additional internal lifecycle states are recorded in system logs.

### 1.2 What success should feel like

These are future acceptance examples, not claims about today's robot:

| Everyday situation | Desired experience |
| --- | --- |
| “Remind me to stretch in 25 minutes.” | The robot displays the exact due time, saves the reminder, and delivers it once while the service is running. A restart preserves it; downtime is explained. |
| “Help me plan tomorrow morning.” | The robot asks only for missing essentials, uses an authorized calendar connection if present, proposes a realistic schedule, and distinguishes a suggestion from a saved calendar event. |
| “Find three useful articles and save the important points.” | It searches through an approved tool, shows sources and dates, saves a private note, and explains any incomplete part. |
| “Remember that I prefer shorter answers.” | It records the permitted preference, explains its scope, and offers correction. No new quiet-hour profile is introduced. |
| The internet disconnects during a task. | It explains what has already happened, keeps local functions usable where safe, and does not repeat an uncertain external action. |
| The user cancels speech from the controller. | Current and queued playback stop. Cancelling speech is separate from cancelling the task; real-time spoken interruption is deferred. |
| A hardware package is missing. | A health screen names the package and the active Python environment, gives the correct repair instructions, and keeps movement stopped. |

### 1.3 Design principles

- **Useful before impressive.** Reliable timers, notes, and schedule assistance
  matter more than a large number of gestures.
- **Make outcomes clear.** Explain task outcomes through existing user interfaces
  and record additional lifecycle transitions in system logs.
- **Keep the user in control.** Memory inspection, cancellation,
  camera consent, and movement permissions must be easy to find.
- **Verify outcomes.** “Requested,” “accepted,” and “finished” mean different things.
- **Adapt gradually.** Learning should initially mean remembering approved
  preferences and improving reusable task recipes, not changing the robot's own
  code, model weights (the learned numerical settings inside a model), or safety rules.
- **Fit this hardware.** Use the existing display and buzzer for expression.
  Do not assume a movable head, touch-sensitive antennas, a speaker, wheel
  position feedback, or a depth camera is already fitted.

## 2. Evidence and current project status

### 2.1 Which versions were reviewed

The primary evidence is the supplied local checkouts, not an assumption about
the latest public release. A commit is a saved version of a Git repository.

| Project | Reviewed commit | Scope |
| --- | --- | --- |
| NinjaRobotPi5 | `47e7d2e07ad7a7119a6df3117148186ea3e05740` | Current wiki and manuals, prior audit, selected implementation paths and tests, and comparison with the audited source version. |
| Microduck | `bc41fb5c9a9b39894669c1e022e375cf83800382` | Local reference checkout dated 3 September 2026; inventory, architecture, control, interaction, sensing, transport, deployment, and test design. |
| Reachy Mini | `234a978e4426895fc88d864e7f154643aea77f53` | Local reference checkout dated 3 September 2026; Python and browser interfaces, daemon, media, motion, perception, applications, recovery, and test design. |
| Previous NinjaRobotPi5 audit | `3854f807df94d368de8806f148b2b50b679e2749` | [Audit dated 6 September 2026][N-audit]. Its tests and reproductions are historical evidence, not tests rerun for this report. |

All three working trees were clean at the start. The Agent and IDE source trees
have no changes between the previous audit's commit and the current NinjaRobotPi5
commit. Selected important findings were also checked directly in the current code.
This supports carrying those findings forward; it does not establish that every
old documentation or tooling finding remains unchanged.

Serena successfully provided the current Ninja Agent's symbol overview. It could
not extract symbols from the supplied reference paths; its active language server
was Python, which also excludes Microduck's Rust code (Rust is another programming
language). Reference inspection
therefore used file inventories, targeted symbol searches, source reads, package
definitions, and test-source inspection. No reference setup commands were run.

### 2.2 What NinjaRobotPi5 already provides

| Area | Existing foundation | What it does not yet establish |
| --- | --- | --- |
| Conversation | Local Ollama and cloud-provider adapters, streamed text, bounded model/tool turns, cancellation and request deadlines. | A durable, independently scheduled assistant that completes work across service restarts. |
| Agentic work — planning and using tools toward a goal | `AgentLoop`, `ToolRegistry`, policy evaluation, typed requests — requests with a checked structure — tool results, reusable skill instructions. | Reliable reminders, a task inbox, or an end-to-end calendar-writing workflow. |
| Expressions | Thinking/responding/action/idle presentation, approved emotional faces, behavior generation and playback, buzzer sounds. | Spoken replies. The `speaking` face name is a visual state. |
| Voice | Opt-in wake listening and bounded recording/transcription through the IDE. | Continuous two-way spoken conversation, speaker playback, or tested echo handling. |
| Memory | Local SQLite storage — a small database kept on the device — with user profiles, preferences, searchable memories, behavior outcomes, retention controls (how long information is kept), and audit records. | Unrestricted self-learning, reliable recognition of every speaker, or correct inference of every preference. |
| Web and external tools | Web controller, controller leases — temporary permission to control the robot — and allowlisted external MCP tools. MCP means Model Context Protocol, a standard way to discover and call tools. | Guaranteed availability of configured web/calendar services, or permission for arbitrary external writes. |
| Physical behavior | Existing display, buzzer, continuous-rotation wheel servos, distance sensor, camera, microphone, bounded behavior execution and stop/resume mechanisms. | A stationary expressive neck, arm manipulation, reliable distance travelled, or desk-edge protection. |
| Developer knowledge | Versioned full manuals, 11 searchable topic pages, shared coding-tool workflow, source fingerprints and review records. | Runtime access by the robot's conversational Agent. Developer wiki skills and robot Agent skills are different systems. |

Evidence: [Agent loop][N-loop], [tool registry][N-tools], [presentation][N-present],
[memory schema][N-memory], [voice service][N-voice], [IDE assembly][N-integrated],
and the [wiki feature page][N-features]. The MCP tutorial includes read-only web
search and calendar examples; examples do not prove that an account is connected.

### 2.3 Carry forward the previous audit accurately

“Source unchanged” below means that the relevant reviewed code has not received
a repair since the earlier audit. It does not mean a fresh hardware reproduction
was performed. New checklist identifiers appear in section 5.

| Previous finding | Treatment in this plan | Refinement |
| --- | --- | --- |
| A01: some direct servo commands bypass the system-stop path | Current integrated registration and `ServoDevice.move` still show the separate path. Close every entry point before expanding autonomous movement. | F01 |
| A02: emergency stop shares ordinary scheduling | Current execution still calls the resource scheduler. Give stopping an independently tested interrupt path. | F02 |
| A03: older real-device commands can create another owner | Source unchanged. Preserve command names while enforcing shared ownership. | F03 |
| A04: device `enabled` flags are inconsistent | Source unchanged. Define disabled, missing, and temporarily failed states separately. | F04 |
| A05: pin conflicts are incompletely validated | Source unchanged. Validate the entire enabled hardware configuration before opening devices. | F04 |
| A06: backup/restore can omit data or restore partially | Source unchanged. Repair before storing important schedules and expanded personal memory. | F06 |
| A07: external MCP `isError` may be reported as success | Direct source review confirms bounded payloads are still wrapped as success. Repair authoritative result status. | F07 |
| A08: external tool effects and inherited environment are too broadly trusted | Direct review confirms read-only/retry assumptions and environment copying. Do not add calendar writes through this shortcut. | F07, T04 |
| A09: Pi boot configuration conditional sections are mishandled | Boot-renderer source unchanged. Repair using text fixtures before any live boot-file change. | F05 |
| A10: manuals mix historical and current statements | Navigation and wiki organization improved. Review individual behavior claims during each repair; do not call the whole wiki obsolete. | X03 |
| A11: installer inputs are not fully reproducible | Retain as an installation review item; examine each remaining downloaded input before pinning it. The broader updater project is deferred. | F05; X02 deferred |
| A12: quality gate and hardware-test boundaries | The old formatting result is historical. Wiki checks now pass. Reassess the current full gate and explicit hardware-test exclusion during implementation. | F08 |
| A13: face-recognition cleanup is incomplete | Source unchanged. Repair at the narrowest ownership boundary; a managed-driver edit needs separate authorization. | F08 |
| A14: large modules and aging validation evidence | Use focused extraction only when needed for an approved feature. Do not begin with a broad refactor. | X01, X03 |
| A15: invalid bundled Traditional Chinese font | Treat as an unresolved asset issue, not a failure of all Chinese display paths. Replacing the managed asset requires authorization. | H06 |

The recent missing-`pi5disp` incident adds a practical installation requirement.
An earlier isolated environment check in this conversation showed that installing
the hardware extra supplied the six driver packages, while a bare root
`uv sync --frozen` removed optional hardware dependencies. That establishes a
reproducible failure mechanism, not the exact command the user originally ran.
The current read-only workspace-driver check passes for all six packages.
No installation command was rerun for this planning task.

## 3. What to learn from the references

### 3.1 Microduck: coherent reactions and repairability

Microduck demonstrates how small, timely reactions can make a robot seem alive.
A stable synthesized voice, a hand-controlled musical interaction, and coordinated
sound and mouth motion establish a recognizable character without requiring a
language model for every response. Its control loop reads recent intent and sensor
snapshots instead of waiting for a network reply. [Sound personality][M6],
[theremin interaction][M7], [intent storage][M5].

Its strongest reliability lesson is equally practical: diagnostics and recovery
should still work when robot control is broken. Its updater verifies releases
and checks their health after installation; its configuration and update services
are deliberately separated from the control service. [Architecture][M2],
[update engine][M12], [verification][M13].

Adapt the principles through NinjaRobotPi5's existing IDE and service tools.
Do not copy its seven-service deployment, biped motion policies, or assumptions
about what a fallen robot should do. Its richer autonomous personality remains
described as work to port, and its privacy design contains unfinished elements.
The appendix explains these distinctions.

### 3.2 Reachy Mini: expressive timing and accessible applications

Reachy Mini makes movement an understandable interaction language. Smooth
transitions, gaze, recorded expressions, and speech-related movement help users
interpret attention and response. A shared playback timeline avoids sound and
motion drifting apart because separate client messages arrive at different times.
[Playback implementation][R4], [speech movement][R5], [face tracking][R7].

Its application ecosystem also reduces the gap between an interesting idea and
something a user can try. Templates, Python and browser interfaces, visible
connection states, and explicit application teardown reduce repeated setup work.
[Application lifecycle][R10], [manager][R11], [browser host protocol][R14].

NinjaRobotPi5 should adopt the experience: understandable states, bounded reusable
behaviors, clean ownership handoffs, and small discoverable applications. It should
express these through its screen and existing tools. It should not reproduce
Reachy's head mechanics or let a browser bypass Agent policy.

### 3.3 What neither reference solves for us

Neither audited core checkout establishes a complete personal productivity
assistant with durable reminders, verified calendar updates, transparent lifelong
memory, and safe improvement through feedback. Reachy's separate conversation
application extends the ecosystem, but it is not the same repository as the core.
Microduck's learned movement policies are not a general task-planning agent.

The opportunity for NinjaRobotPi5 is therefore broader than feature matching:
combine its existing tool and memory foundation with the references' interaction
and recovery lessons, then measure whether ordinary tasks actually get completed.

## 4. Keep the existing framework

### 4.1 Ownership stays the same

The existing hardware path remains mandatory:

```text
User or model
    -> ninjarobot_pi5_agent: conversation, task planning, permissions, tools
    -> ninjarobot_pi5_ide: coordinated execution, safety, device ownership
    -> managed pi5 driver
    -> device
```

The IDE is this project's device-coordination layer. A driver is the small library
that operates a particular device. An API is the set of calls that components
use to communicate. Existing APIs, command names, configurations, saved behaviors,
and private data should remain compatible unless a separately approved change
explicitly requires otherwise.

External information tools remain on the Agent side. They do not need to pass
through the IDE unless they request a physical robot action. Every such action
must use the existing tool-to-IDE bridge.

### 4.2 Add focused responsibilities inside existing packages

| Responsibility | Existing home and proposed extension | Boundary to preserve |
| --- | --- | --- |
| Durable tasks and reminders | Agent `runtime.py`, `service.py`, `agent_loop.py`, memory/store migration framework; add focused task and reminder modules. | The model proposes a task; deterministic code stores, schedules, authorizes, and verifies it. |
| Conversation and visible progress | Agent `voice_service.py`, `presentation.py`, `events.py`, and web controller. | Display and microphone access still go through the IDE. |
| Sound output | A proposed IDE-owned audio capability, called through Agent tools. | The current buzzer and microphone drivers are not a general speech speaker. Select and approve the output hardware and backend (its controlling software) before adding it. |
| Expression coordination | IDE `behavior_runtime.py`, `behavior_models.py`, `robot.py`, and current display renderer. | One owner resolves competing expressions; safety/privacy indicators take precedence. |
| Personal memory | Agent `memory_store.py`, `memory_services.py`, `memory_models.py`, migrations and existing management UI. | Private user records stay separate from the public developer wiki. |
| External actions | Existing tool registry and reviewed provider adapters, with explicit effect and retry declarations. | Do not relabel arbitrary external writes as read-only MCP tools. |
| Health and recovery | Existing service/readiness/deployment paths, IDE health, and diagnostic scripts. | A software diagnostic must work without initializing motors or capturing media. |
| Developer knowledge | Existing wiki source-version and review workflow. | Planned behavior must remain labelled planned until code and validation support it. |

This is an extension of the current architecture, not a replacement. H02 adds an
IDE audio adapter over an approved operating-system output. It does not require
a new managed Pi5 speaker library by default. The concrete device/dependency/service
choices and any managed-driver repair remain separately reviewable. A new deployment
layout under X02 is deferred. No second robot runtime is planned.

### 4.3 Preserve current operating settings

H05's new desktop profile and quiet-hour controls are deferred. Preserve existing
movement settings and startup behavior. A product described as a desktop assistant
does not thereby become safe to drive near a desk edge: the forward distance
sensor does not establish edge protection.

B04's game commands only the display, buzzer, and distance sensor. It never enables
wheel motion and refuses to start while movement is active. Existing stop, privacy,
and hardware-ownership rules remain in force. New head/touch/edge hardware remains
an evaluation option under B05, requiring a concrete reviewed design before use.

## 5. Refinement checklist

Each row is independently reviewable. An unchecked box means implementation has
not been completed. `Confirmed`, `revised`, and `deferred` describe the owner's
scope decision. Deferred rows retain the original estimate for reference and are
excluded from active phases. Dependencies and acceptance gates follow in sections 6–8.

Effort is relative to this codebase, including tests and documentation:
**Low** means a focused change; **Medium** crosses a few existing components;
**High** adds a substantial feature or recovery contract; **Very High** involves
several subsystems or significant hardware/operational uncertainty. These are not
calendar estimates. Hardware access, model choice, and account setup affect timing.

Priority: **P0 = critical**, **P1 = high**, **P2 = medium**, **P3 = nice to have**.
P0 blocks expanded live autonomy where the corresponding risk applies. Independent
documentation, interface mockups, and tests with simulated devices can proceed.

### 5.1 Foundation and reliability

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] F01 (confirmed) | Enforce safety state, bounded movement, cancellation, and output cleanup at every IDE movement entry point. | A guarded behavior is insufficient if another public command bypasses it; A01 remains relevant. | Stop means stop regardless of how movement was requested. | High | P0 |
| [ ] F02 (confirmed) | Give emergency stop an interrupt path that cannot wait behind ordinary queued work. | A full or blocked queue must not delay the command intended to stop it; A02. | Predictable stopping during slow tools or long behaviors. | High | P0 |
| [ ] F03 (confirmed) | Apply one hardware-ownership contract to the service, interactive tools, and retained real-device commands. | Two clients must not compete for the same device; A03. | Clear “robot already in use” feedback instead of conflicting actions. | Medium | P0 |
| [ ] F04 (confirmed) | Validate all enabled device pins and consistently enforce disabled-device settings. | A04/A05 can make configuration misleading or electrically conflicting. | A disabled feature stays disabled; wiring errors are explained before startup. | Medium | P0 |
| [ ] F05 (confirmed) | Add an environment-aware setup doctor (a diagnostic tool) and consistent hardware/development installation profiles; repair Pi boot-text validation. | Missing optional packages can resemble failed hardware; A09/A11 and the recent installation incident. | One diagnosis identifies the active environment, missing dependencies, and the appropriate repair. | Medium | P0 |
| [ ] F06 (confirmed) | Make backup complete, database-consistent, and restore fully validated before replacement, with recovery from partial failure. | A06 becomes more serious when schedules and personal notes are important. | An upgrade or recovery preserves the user's information. | High | P0 |
| [ ] F07 (confirmed) | Correct MCP failure status, reviewed effect/retry declarations, minimal subprocess environment, bounded discovery, and schema refresh (keeping expected tool arguments current). | A07/A08 can create false success and expose unrelated credentials. | Honest tool results and clearer limits on external access. | High | P0 |
| [ ] F08 (confirmed) | Add missing lifecycle/failure tests and enforce explicit opt-in hardware tests; close the audited face-backend cleanup gap. | Existing passing tests do not cover all ownership or failure cases. | Repeated use and updates are less likely to leave devices stuck. | High | P1 |
| [ ] F09 (confirmed) | Report capability-level health with reason, freshness, dependency, and recovery steps. | A single ready/not-ready answer conceals what is still usable. | Users can continue safe text tasks while understanding why a device is unavailable. | Medium | P1 |

### 5.2 Human-robot interaction and conversation

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] H01 (revised) | Record additional listening/thinking/approval/action/completion/interruption/error transitions in the existing system log. | Troubleshooting needs correlated events; additional display/web lifecycle presentation was declined. | Operators can understand task flow from logs while current presentation stays unchanged. | Low | P1 |
| [ ] H02 (confirmed) | Add optional TTS — text-to-speech, turning an answer into audio — and IDE-owned playback to a configured OS audio output, including Bluetooth when supported. | Connecting a speaker alone does not generate or manage spoken answers. | Listen to spoken replies and reminders using sequential input/output. | High | P1 |
| Deferred H03 (deferred) | Add spoken interruption handling, microphone/playback coordination, and echo control after H02. | The robot must not transcribe its own answer or keep speaking over the user. | More natural turn-taking and immediate control of long answers. | Very High | P1 |
| [ ] H04 (confirmed) | Make clarification brief and specific; confirm exact consequential actions and explain what remains uncertain. | Fluent guesses about time, identity, or external actions damage trust. | Fewer wrong reminders and clearer permission requests. | Medium | P1 |
| Deferred H05 (deferred) | Add a desktop profile, quiet hours, adjustable expression intensity, speech rate, and a visible microphone state. | A robot that is entertaining briefly may become distracting during work. | The assistant fits the user's environment and attention needs. | Medium | P1 |
| [ ] H06 (confirmed) | Verify multilingual display assets, readable text, captions, keyboard control, and non-color-only status cues. | Browser translations alone do not ensure usable robot display text; A15. | More people can understand and control the robot comfortably. | Medium | P1 |
| [ ] H07 (confirmed) | Add optional guided checks and practice to the existing Agent interactive tool and web controller, sharing F05 diagnostics. | Current startup pairing is not a beginner feature tour; a separate standalone tool would duplicate setup. | Follow one resumable guide without automatic movement, capture, or deployment. | Medium | P2 |

### 5.3 Agentic tasks and everyday usefulness

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] T01 (confirmed) | Add a durable task record with plan, current step, owner, approvals, result evidence, and recovery state. | A bounded chat loop is not a restart-safe task manager. | Users can ask “What happened to my request?” and get a dependable answer. | High | P1 |
| [ ] T02 (confirmed) | Add local timers and reminders with exact due times, repeat rules, snooze, cancellation, and restart recovery. | This is a high-value everyday feature missing from the core task model. | Useful reminders continue without a cloud model once saved. | High | P1 |
| [ ] T03 (confirmed) | Add task progress, cancellation, outcome summaries, and checks that distinguish queued, completed, failed, and uncertain actions. | Tool acceptance is not proof that the user's goal was met. | Less waiting without explanation and fewer misleading “done” messages. | High | P1 |
| [ ] T04 (confirmed) | Add schedule planning through authorized calendar reads, then reviewed calendar writes with account/scope preview and verification. | External calendar actions need a stronger contract; ordinary alarms belong to T02. | Plan and save schedules; “wake me at 4 pm” works through local reminders without a calendar account. | High | P1 |
| [ ] T05 (confirmed) | Make web research a complete workflow: approved search, dated citations, comparison, private note saving, and partial-result reporting. | A search result alone is not a finished information-management task. | Users receive useful, traceable answers they can find again. | Medium | P1 |
| [ ] T06 (confirmed) | Add simple notes, checklists, and a daily briefing assembled from permitted local tasks and connected sources. | Common assistant tasks should not need a new integration each time. | One place to review priorities and remembered information. | Medium | P2 |
| [ ] T07 (confirmed) | Add bounded replanning and recovery policies with time, tool-call, and spending limits. | Retrying everything can duplicate actions or loop indefinitely. | The robot can recover from ordinary failures and knows when to ask for help. | High | P1 |
| Deferred T08 (deferred) | Add opt-in proactive suggestions with quiet hours, frequency limits, relevance checks, and easy dismissal. | Proactivity is useful only when it respects attention and consent. | Helpful prompts that do not become persistent interruptions. | Medium | P2 |

### 5.4 Memory, personalization, and improvement

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] M01 (confirmed) | Extend memory management to show why an item was saved, its source, confidence, last confirmation, and edit/delete controls. | Existing memory needs understandable provenance — where a claim came from. | Users can correct the assistant instead of repeatedly fighting a wrong assumption. | Medium | P1 |
| [ ] M02 (confirmed) | Distinguish confirmed preferences, temporary context, task outcomes, and unconfirmed suggestions; handle contradictory preferences explicitly. | Different kinds of information should not all become lasting facts. | More accurate personalization and fewer surprising assumptions. | Medium | P1 |
| [ ] M03 (confirmed) | Improve retrieval within the current store before considering semantic search — search by meaning rather than exact words. | Relevant context helps; sending all history wastes resources and exposes excess information. | Better continuity across conversations with controlled data use. | Medium | P2 |
| [ ] M04 (confirmed) | Turn repeated successful workflows into reviewable task recipes, with user feedback, version history, and rollback (restoring a previous version). | “Learning” should improve practical behavior while staying inspectable. | The assistant learns preferred ways to help without rewriting its safety rules. | High | P2 |
| Deferred M05 (deferred) | Strengthen active-user selection, guest behavior, export, retention, and deletion verification for new task data. | Face similarity is not authentication, and shared rooms contain multiple people. | Private information is less likely to be shown or attributed to the wrong user. | High | P1 |

### 5.5 Expressions and sensing

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] B01 (confirmed) | Coordinate face, buzzer, and future speech on one IDE-owned timeline with interruption and priority rules. | Separate reactions can conflict or appear late. | A coherent robot response that matches the answer or task. | High | P1 |
| [ ] B02 (confirmed) | Add small bounded variations to existing safe expressions and sound cues, with stable personality settings. | Repetition feels mechanical, while uncontrolled randomness feels unreliable. | A recognizable character that remains calm and predictable. | Medium | P2 |
| Deferred B03 (deferred) | Introduce an opt-in attention experience using camera observations and animated eyes, with freshness limits and consent. | Reacting to the person can make interaction easier, but stale detections can mislead. | The robot visibly attends to the interaction without moving its wheels. | High | P2 |
| [ ] B04 (confirmed) | Add an explicit distance-controlled buzzer/display game, selectable through conversation, with bounded duration and stop handling. | A simple sensor-to-feedback loop makes robotics tangible. | Ask “let’s play a game,” then move a hand in front of the sensor to change sound and an existing face or simple graphic. | Medium | P3 |
| [ ] B05 (confirmed) | Treat future speakers, touch controls, movable heads, and desk-edge sensors as separate evaluated hardware options. | Competitor interactions depend on hardware NinjaRobotPi5 does not currently have. | Hardware additions solve a clear need and do not destabilize existing drivers. | Very High | P3 |

H02 can select a modest approved speaker before the broader optional hardware work
in B05. B05 does not delay the initial software-only assistant or require a new head.

### 5.6 Extensibility and development quality

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] X01 (confirmed) | Extend existing Agent skill packages with clear capability, permission, version, and test requirements; add focused application templates. | New functions should reuse the registry and policy rather than invent another execution route. | Consistent add-ons that are easier to install, understand, and disable. | Medium | P2 |
| Deferred X02 (deferred) | Improve release identity, installation checks, staged updates, and rollback evidence before considering automatic updates. | Microduck shows the value of diagnosing installed versus actually running software. | Users can recover from an upgrade without guessing which version is active. | High | P2 |
| [ ] X03 (confirmed) | Keep this plan, feature specifications, manuals, wiki pages, and validation evidence synchronized during every approved phase. | A knowledge base helps only when it describes the current implementation honestly. | All coding tools work from the same accurate context. | Low | P1 |
| Deferred X04 (deferred) | Build repeatable simulated user journeys, fault scenarios, and consent-aware Pi validation records. | Module tests alone do not establish a good assistant experience. | Improvements are measured against real user tasks before release. | Medium | P1 |
| [ ] X05 (confirmed) | Add a bounded read-only project-help tool over selected public wiki pages and cited current manuals, through the Agent registry. | Developer wiki skills are not automatically available to the running Agent. | Ask the robot project questions in conversation and receive cited answers with review/version limits. | Medium | P2 |

## 6. How the important features should work

### 6.1 A durable task without replacing the Agent loop

Keep `AgentLoop` as the bounded reasoning and tool-calling mechanism. Add a task
service around it, owned by the existing Agent runtime. A task should contain:

- A stable task identifier and user identifier.
- The requested outcome, constraints, creation time, and deadline if any.
- A short user-visible plan and current step, not private model reasoning.
- Status: proposed, waiting for approval, ready, running, paused, completed,
  failed, cancelled, or uncertain.
- The exact approved action scope, expiry, and affected account or device.
- Each attempted tool call, its result, and evidence of the resulting state.
- Recovery instructions and whether repeating the action is safe.

Use the existing database migration approach to add tables without replacing
current memory or action-ledger records. A task links to those records rather
than duplicating all their contents. Give durable user tasks a separate retention
policy from short-lived conversation history.

On restart, inspect unfinished tasks. Read-only work may be resumed within its
remaining limits. An uncertain external write must first be reconciled — checked
against the actual external state. Movement must never replay automatically.
Permission granted for yesterday's account or movement session must not silently
authorize a new one.

Example: a calendar service times out after receiving “create event.” The task
becomes uncertain, not simply failed. Check for the event using a stable request
identifier where the provider supports it. If its existence cannot be established,
ask the user before creating another event. An idempotency key is an identifier
that lets a service recognize repeated requests; it helps only if that service
actually honors it.

### 6.2 Reminders that users can trust

The IDE's existing `ResourceScheduler` coordinates competing device actions.
It is not a calendar scheduler. Put reminder scheduling in the Agent task service,
and use the IDE only when delivering a permitted display or sound notification.

Store the user's local time zone, intended local date/time, resolved UTC time
(a shared worldwide time reference), repeat rule, delivery status, and revision.
Ask about ambiguous times such as “at eight” when context is insufficient.
Account for daylight-saving changes, system-clock corrections, and time-zone changes.

Recommended first contract:

1. Confirm the exact due time after saving a reminder successfully.
2. Assign each scheduled occurrence a unique identifier, claim it transactionally
   — as one protected database operation — and prevent concurrent duplicate delivery.
3. If the process crashes between making a sound and recording delivery, label
   the outcome uncertain. Do not promise mathematically exact-once physical sound.
   Reconcile the task record and follow a documented missed-reminder policy.
4. After downtime, show missed reminders and offer dismissal or rescheduling.
   Do not burst-play every overdue sound.
5. Keep reminder delivery independent of a cloud model. A saved reminder needs
   deterministic time handling and a notification, not new reasoning each minute.
6. Offer quiet display/web delivery if permitted sound is unavailable. Preserve
   the safety stop and the current privacy-indicator requirements.

A powered-off Pi cannot ring an alarm. The initial feature must say this plainly.
Phone delivery, battery guarantees, and waking a powered-off device are separate
future integrations, not implicit features of a local reminder.

### 6.3 Sequential speech output, including Bluetooth

H02 is confirmed; H03 is deferred. Keep the existing opt-in wake-word and bounded
recording/transcription path. Add spoken output after a complete request has been
transcribed, or in response to typed conversation. Do not add simultaneous audio
streaming, real-time spoken interruption, or acoustic echo cancellation (filtering
speaker sound out of microphone input). This is a scope choice based on the owner's
performance concerns, not a new claim that every Pi configuration is incapable of it.

The proposed path is:

```text
Agent answer -> bounded text-to-speech generation
             -> IDE-owned playback -> operating-system audio -> selected speaker
```

The operating system handles the speaker connection. A compatible Bluetooth speaker
usually uses the standard Bluetooth/audio support rather than a new custom Pi5
speaker driver. The project still needs text-to-speech generation, an IDE playback
adapter (the component that starts/stops audio), output selection, and health checks.
Pairing alone does not add those application functions. H02 should use the existing
OS audio stack; do not replace it or modify a managed driver merely to play audio.

PipeWire (Linux audio routing software) and WirePlumber (its device/session manager)
provide Bluetooth audio integration. Their documentation also explains that access
can depend on the active login session. Therefore, a desktop playback test alone
cannot establish that the deployed Agent service can use the same speaker.
Validate its actual service user, audio-session access, reconnection after restart,
and speaker disconnection. No system-wide audio policy change is authorized by this
plan. [WirePlumber Bluetooth documentation](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html).

Raspberry Pi documents selecting an audio output device. Confirm the installed OS
and connected outputs before choosing exact configuration steps; none were changed
for this review. [Raspberry Pi audio configuration](https://www.raspberrypi.com/documentation/computers/configuration.html#change-audio-output).

Before speaking, the IDE temporarily pauses microphone intake using the existing
voice-input pause/resume ownership pattern. Do not change the persisted voice-enable
setting, grant voice-motion permission, or restart a listener the user disabled.
Resume only the listener that was enabled before playback and is still permitted.
If the pause cannot be established, keep the text answer and decline playback.
On completion, timeout, cancellation or disconnect, clean up playback and temporary
audio in a guaranteed cleanup path. These are minimal H02 lifecycle requirements,
not the deferred H03 real-time feature. [Existing voice-input ownership][N-voiceinput].

Handle races explicitly: a user disabling voice while speech is active takes
precedence over restoration; nested audio/manual-microphone owners must balance
their pause reservations even after a pause timeout. Test both voice-originated
replies and typed/background reminders. A background alarm must not cut off a
recording already in progress: wait within a bounded policy or deliver a permitted
non-speech notification and record the limitation. The current pause/resume methods
are a starting pattern, not proof that these new playback paths already exist.

A controller/terminal cancellation can stop current and queued audio; spoken
interruption during playback is not promised. Retain text on synthesis/output
failure and use a permitted existing buzzer notification for a scheduled alarm if
speech is unavailable. Never report “played” merely because synthesis succeeded.
Validate device/software readiness separately from an operator hearing the sound.

The speech provider, voice languages, dependency versions, output device and service
configuration remain implementation choices to resolve before H02. A synthesis
component may generate data on the Agent side, but it may not open audio devices;
all playback stays behind the IDE boundary.

### 6.4 System logs and existing expression coordination

H01 is reduced to log reporting. Extend the existing event/log path with a task or
request identifier, timestamp, phase, outcome, and safe reason code. Send these
records to the existing system logger and service journal (the operating system's
log collection). The current in-memory event broker alone is not persistent system
logging. Do not log raw transcripts, prompts, private notes, credentials, or model
reasoning for this new lifecycle stream. Avoid logging every animation frame.
[Existing events][N-events], [service logging configuration][N-serviceunit].

Do not add H01 lifecycle faces, badges, panels, or new web/display states. Keep
current presentation and privacy/safety indications. H06 can repair fonts and
accessibility; T03 can show explicit task progress in existing interfaces; neither
requires a replacement presentation system.

B01 coordinates existing face/buzzer behavior and H02 speech on an IDE-owned timeline.
B02 adds small bounded variations to those existing expressions. B04's explicit
sound/display game is also confirmed. Safety and privacy indicators retain priority
and optional output yields or stops when it cannot own the resource safely.

Use playback time for speech/expression coordination and a monotonic clock (a clock
that does not jump when the calendar clock is corrected) for durations and timeouts.
Do not add H05's quiet-hour/intensity/profile controls, B03's camera attention, or
wheel movements to compensate for limited display expression. Small sound/motion
examples in the competitor appendices do not override these scope decisions.

### 6.5 Memory that improves through interaction

Build on the existing memory store. Record the source of a preference and whether
the user confirmed it. “I am tired today” should ordinarily stay temporary;
“Please use shorter answers from now on” can become a lasting preference.

Allow the user to ask “What do you remember about me?”, correct an item, remove
it, or reset a supported category using existing controls. Preserve existing user
ownership, retention and deletion behavior when adding records. Define how new
memory/search/task references respond to those existing controls; do not imply
that deleting a live row erases older backups. M05's separate guest selection,
export and household-management redesign is deferred.

Track useful feedback such as accepted schedules, corrected names, or repeated
task recipes. When the user asks to review or improve a routine, suggest a recipe
based on recorded outcomes; show what it will do and
obtain the relevant approval before making it a reusable automation. Keep version
history so a bad adaptation can be reversed.

Do not train models online, automatically install tools, change permissions,
rewrite source code, or store speculative psychological profiles. These are not
required to make the assistant noticeably more helpful. T08 proactive suggestions
remain deferred; do not add unsolicited recipe prompts.

### 6.6 External tools and project knowledge

For web research, retain source URLs and retrieval dates, state when information
is stale, and separate quoted content from instructions. A web page or imported
document must not be able to grant permission or request secret disclosure.
This is prompt injection: outside text trying to redirect the assistant's actions.

Start calendar integration with the existing read-only pattern. Calendar writes
need a separately reviewed provider contract covering credentials, allowed calendars,
action preview, confirmation, cancellation, and verification. A permission request
should name the exact event and account. Tool metadata alone is not a security boundary.

For project help, expose only selected public wiki content through a read-only
provider. Return document title, version, review state, and citations. Search must
not execute installation instructions. An unreviewed or planned page must not be
presented as verified operating behavior. Keep personal notes and conversation
databases out of the developer wiki and public repository.

### 6.7 Answers to the confirmation questions

#### H02 — Is connecting a Bluetooth speaker enough?

A compatible, paired speaker can provide the physical output through the OS's
standard Bluetooth/audio support. It normally does not require a custom Pi5 device
driver. However, it does not itself turn Agent text into speech: H02 must add a
text-to-speech generator and a bounded IDE playback adapter. See section 6.3 for
service-user access, output selection, disconnect recovery and microphone coordination.
Actual speaker compatibility and the installed audio stack still need checking.

The implementation should therefore separate three checks: synthesis available,
selected audio output accessible to the Agent service, and sound heard in an
operator-approved playback test. Pairing success is not proof of all three.

#### H07 — Will onboarding be a separate command-line tool?

No separate application or standalone onboarding CLI is planned. Extend the existing
`ninjarobot-agent` interactive menu and web controller with an optional guided-checks
entry, backed by the same F05 diagnostic results. The exact menu label is proposed,
not an existing command. Keep the existing pairing/startup coordinator intact.

The source already has `OnboardingCoordinator` for pairing and startup, plus
Agent deployment menus. The existing `deployment setup` command installs/enables
startup and must not be reused as a harmless tour button. Guided checks must not
start deployment, run the greeting, move wheels, or capture media as an incidental
side effect. [Onboarding coordinator][N-onboard], [existing CLI][N-cli].

Proposed guide:

1. Show the chosen configuration, real/simulated mode, environment and F05 results
   without opening devices unnecessarily. Explain missing/disabled components.
2. Explain the existing stop/resume controls and how to reach current manuals.
3. Offer a text-only sample question or X05 project-help question when available.
4. Explain T02 reminders and optionally let the user create/cancel a short practice
   reminder, making its sound/display effect explicit before scheduling it.
5. If H02 is installed, show the selected output and offer a separately initiated
   speaker test. Camera, microphone, movement and deployment remain explicit choices.
6. Let the user skip optional steps and return later. Reuse validated configuration
   rather than overwrite existing settings or start a second hardware owner.

Existing QR pairing and required indications are preserved. The guide appears in
existing menu/web routes; H01 does not add a new robot-screen onboarding animation.

#### T04 — Can I say “call me up at 4 pm today”?

Yes, the planned conversational experience supports that as a **local alarm** through
T02, with T01 persistence and H04 time clarification. T04 is needed only if the user
also wants a connected calendar event. A local alarm does not require a Google
Calendar account or a new cloud call when it fires.

Accept typed conversation and the existing opt-in wake-word/recorded voice route.
Resolve “today” and “4 pm” using the configured local time zone; if it is missing,
ask. State the full date, time and zone after the record has been saved successfully.
If 4 pm today has passed, ask for another time rather than silently moving it to tomorrow.
Explain “I will sound an alarm here” so the phrase does not imply a telephone call.
If context instead suggests calling a person, clarify rather than initiating one.

Delivery can use an approved existing buzzer sound; H02 additionally enables a
spoken reminder on the selected speaker. Provide stop/dismiss, snooze and cancel
through the task controls. After a restart, recover the saved record and apply the
missed-reminder policy from section 6.2. The Pi must be powered on and the Agent
running to deliver locally; an unavailable speaker must not be reported as audible
success. No real-time spoken interruption is required for this feature.

#### B04 — Can “let’s play a game” start the distance game, and how is it played?

Yes. Add the game to the existing skill/tool selection route. “Let’s play the distance
game” selects it directly; a broad request such as “let’s play a game” can offer it
or ask which game if several exist. Interpret the request through Agent policy and
start the game through one IDE-owned capability. Do not run source code supplied
by the model or give the game direct driver access.

The proposed first experience is a short **distance music game**:

1. Explain that it uses the distance sensor, buzzer and display, and ask the user to
   move a hand in front of the sensor without touching it. Use existing task prompts;
   no camera or microphone capture is needed just to play.
2. During an illustrative 30-second session, map valid distance to a few stable sound
   bands: closer raises pitch, farther lowers it. Show an existing face or simple
   size/color graphic that changes with the same reading. Color is not the only cue.
3. Optional prompts can ask the user to find a near/middle/far band; a short sound
   and existing expression confirm a match. Exact distance thresholds and buzzer
   limits are implementation settings to validate against this sensor and setup,
   not calibrated values promised by this document.
4. Smooth small changes and add hysteresis (different switching thresholds to avoid
   flicker). Invalid, stale or out-of-range readings produce a neutral/silent state,
   not a fabricated hand distance. Bound update rate and duration inside the IDE.
5. Finish when the session times out or the user stops it through existing controls.
   A spoken stop may use existing voice input when enabled, but a controller stop
   always remains available and does not depend on recognition. Cleanup silences
   game sound, releases resources and restores the current permitted presentation.

The game issues no wheel commands and refuses to start during movement or a system
stop. If an authorized movement request arrives during the game, the IDE must end
the game and release its resources before allowing that movement; checking only at
game startup is insufficient. The game also yields/cancels if a safety/privacy
indication or approved higher-priority output needs the shared display/buzzer.
A missing sensor produces a useful refusal.
A missing optional game output may use a clearly announced simpler variant; it must
not pretend the full game is operating. Resource ownership, cancellation and
conversational activation raise the estimate from Low to **Medium**; priority stays P3.

#### X05 — Can I ask the running robot questions about NinjaRobotPi5?

Yes, after X05 is implemented. Examples include “What can NinjaRobotPi5 do?”,
“How do I configure the distance sensor?”, and “Why is movement unavailable?”
For live status, use the existing health tool alongside documentation; the wiki
alone cannot establish the actual device state.

The path is conversation → Agent tool registry → a bounded read-only wiki provider
→ selected topic pages and cited current manuals → an answer with local source links.
A proposed `project.help` name is illustrative; the final public tool name must be
checked for compatibility. The model receives data, not permission to execute manual
commands. The provider is Agent-side because document retrieval operates no device.

Reuse the wiki's existing keyword search in its separate environment through a
fixed argument list, limited output and a shorter task deadline. Do not import its
dependencies into the robot environment or expose the launcher's general setup/apply
commands to the model. The launcher currently supports mutating maintenance actions
and a 600-second subprocess timeout; a runtime provider must deliberately expose
only bounded search/read operations. [Wiki launcher][N-wikilauncher].

Constrain source reads to approved public wiki paths and current registered manuals;
reject traversal and redirected paths, cap linked-page depth/size, and keep private
configuration, logs, media and user memory out. If the wiki environment is absent,
use an allowlisted direct-file fallback or return a clear unavailable result; never
install dependencies during a conversation. A zero-result keyword query can try
related short terms or consult the overview. Do not invent an answer.

Return source title, path, version, review status and any detected freshness concern.
Draft/AI-reviewed information remains labelled as such. Task-time retrieval must not
run global maintenance or rewrite review records. After a source update, invalidate
cached results by reviewed version/hash so new answers use current evidence. Current
installed behavior takes precedence over historical or proposed features.

The developer wiki already supports questions from coding tools, but the running
robot does not gain X05 merely because these files exist. No X05 runtime provider
has been implemented in this document revision.

## 7. Development phases and acceptance gates

The phases below include only the 31 confirmed items and revised H01. Carry forward
the recorded approvals; prepare concrete patches and resolve remaining choices under
the root workflow before implementation. Hardware modifications, managed-driver edits,
account access and live deployment still need their specific reviewed scope.

Agent filenames below are under `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/`;
IDE filenames are under `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/`. New module names
are suggestions, not claims that those modules already exist.

| Phase | Objective and likely files | Compatibility contract | Validation gate | Documentation and risk |
| --- | --- | --- | --- | --- |
| 0A — Stop and ownership | F01–F04: IDE `engine.py`, `scheduler.py`, `integrated.py`, `robot.py`, `servo.py`, `config.py`; Agent legacy `cli.py`; corresponding tests. | Preserve public commands and ordinary behavior; consistently enforce stop, disabled-device settings and ownership. | Fake-device reproductions for every movement entry, blocked/full queues, competing owners and pin collisions; root gates. | Installation/development manuals, safety evidence and log. High movement relevance; no automated live motion. |
| 0B — Installation and persistence | F05/F06: setup/boot-renderer scripts, Agent `deployment.py`, environment verification and backup tests. | Preserve private configuration, all required stored data and existing install entry points. No X02 updater project. | Temporary boot text, isolated dependency-profile checks, consistent database snapshots and interrupted restore tests. | Installation/recovery manuals and log. Boot/deployment/data risk; no live OS writes in tests. |
| 0C — External tools and lifecycle | F07/F08: Agent `mcp_client.py`, `mcp_config.py`; IDE identity/cleanup boundary; test configuration and focused failure tests. | Preserve read-only external-tool boundary; managed-driver repairs separately authorized. | Error/status normalization, environment minimization, discovery limits, cleanup and explicit hardware-test exclusion; relevant driver suite separately. | MCP tutorial, containment guidance, tests and log. Privacy/media relevance. |
| 1 — Diagnosis and guided setup | F09, revised H01, H04/H06/H07: Agent `events.py`, logging/runtime, `onboarding.py`, existing interactive CLI/web routes; IDE health and approved font repair. | New lifecycle states go to logs only. Preserve display/web presentation and startup pairing. Guided checks do not reuse privileged deployment setup. | Fake missing/disabled devices, correlation/redaction checks, actionable errors, skip/re-enter guide, no incidental device actions, required accessibility checks. | Guides and wiki pages for diagnostics/onboarding; log. Mostly software/UI work; any font/driver change follows approval policy. |
| 2 — Local task assistant | T01/T02/T03/T07, M01/M02: proposed Agent `task_service.py`, `task_models.py`, `reminders.py`; existing runtime, tool registry, migrations/store and task management routes. | Additive data changes; preserve existing user isolation/retention. No M05 redesign, quiet-hour profile or unsolicited suggestions. | Fake clocks, persistence/restart, duplicate claims, uncertainty, snooze/cancel, stored scope and result evidence; F06 recovery coverage. | Task/reminder and memory specifications, manuals, wiki and log. Personal-data relevance; notification tests use fakes first. |
| 3 — Spoken replies and coordinated output | H02/B01: Agent response/synthesis interface; proposed IDE audio adapter, voice pause/resume and behavior coordination; minimal approved audio/service configuration. | Optional listen-then-speak; existing voice-enable state and display behavior preserved. No H03 real-time voice or H05 profile. | Fake playback lifecycle plus consented speaker tests under actual service user, Bluetooth loss/reconnect, no unsolicited microphone enabling, cancellation and cleanup. | Audio installation/operation/privacy notes, dependency notices and log. Speaker/media/service risk. |
| 4 — Connected information and reusable help | T04/T05/T06, M03/M04, X01/X05: reviewed Agent providers, task receipts, skills, memory retrieval and a bounded wiki-help adapter. | Read-only calendar first, writes explicitly scoped. Briefings and recipe suggestions user-requested. Wiki tooling stays separate from robot dependencies. | Fake accounts, source citation/version checks, allowlisted read paths, prompt-injection and uncertain-write handling, recipe rollback and existing user-boundary checks. | MCP/tutorial, information/task/memory guidance, runtime wiki-help documentation and log. Network/account/privacy relevance. |
| 5 — Optional interaction and hardware evaluation | B02/B04/B05: existing expression assets; proposed IDE distance-game capability and Agent skill; separate hardware-option specifications. | Bounded variations and explicit game only; no camera-attention feature or new desktop mode. B05 evaluates options before any hardware build. | Fake distance sequences, invalid/stale readings, no servo resources/commands, priority/timeout/stop cleanup; optional consented sensor/game test. | Game guide, capability requirements, hardware evaluation and log. Buzzer/display/sensor relevance; new hardware risk assessed separately. |

X03 applies throughout all phases: update affected manuals, wiki pages and validation
records when implementation changes. It is not an additional background wiki writer.

Dependencies: 0A precedes expanded physical execution; F06 precedes reliance on durable
user task data; F07 precedes wider external tools and calendar writes; T01 precedes
reminder recovery and durable task progress; H02/B01 are developed together for safe
playback ownership. B04 can be implemented after the foundation using the existing
buzzer/display, without H02, Bluetooth or camera attention. X05 requires only reviewed
read-only tooling and the local wiki, not a new robot hardware capability.

The first useful milestone remains phases 0–2: reliable setup, troubleshooting and
local reminders/tasks. Spoken alarms follow in phase 3. The deferred identifiers
H03, H05, T08, M05, B03, X02 and X04 have no active phase allocation.

## 8. Validation and measures of success

### 8.1 Initial audit checks and this revision

The original audit used read-only inspection and documentation editing. The
following results describe that original pass; revision validation is recorded
in section 9.3 rather than reusing the original link counts as current results:

- Wiki search returned relevant architecture, tools, and development pages.
- `python scripts/wiki.py source status` reported seven registered sources as ingested.
- `python scripts/wiki.py check` passed current manuals, implementation mappings,
  adapters, and local links.
- `python scripts/wiki.py lint --strict` reported zero errors, warnings, or suggestions.
- `uv run --frozen --no-sync python scripts/verify_immutable_drivers.py` passed:
  222 tracked files across six drivers matched the baseline plus 55 authorized repairs.
- `uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py`
  passed for all six driver libraries using this checkout.
- Document validation found all 39 checklist items complete in structure, all
  reference labels defined, all 85 local file/section links valid, and no whitespace
  errors. Both reference checkouts remained clean.

`--no-sync` uses the already installed environment without changing dependencies.
These results establish documentation health and source/package integrity, not
device operation. No robot service, competitor application, motor test, microphone
capture, camera capture, account action, or power command was started. Competitor
test suites and the full Ninja runtime suite were not run for a document-only task.

### 8.2 Required gates for future implementation

Use the exact applicable root [AGENTS.md gate][N-policy]: immutable-driver check,
workspace-driver check, compilation, Ruff code checks and formatting, Mypy type
checks, pytest tests, and `git diff --check`. Run each affected managed driver's
suite in its own process. Add packaging, installer-preview, documentation-link,
service and security checks for the areas changed.

Before adding any tests that could touch hardware, enforce their explicit opt-in
boundary. Merely naming a test “hardware” does not guarantee that ordinary test
runs exclude it. No automated test may operate live motors, capture private media,
change boot/service files, or shut down the machine.

Maintain fake devices, fake clocks, fake accounts, and injected failures — deliberately
simulated problems — as the main development gate. Check behavior at the public
entry points, including the web, voice, CLI (command-line interface, the commands
run in a terminal), and MCP routes. A successful unit test (an automated check of
a small component in isolation) does not prove that all routes enforce the same permission.

### 8.3 Acceptance checks for the confirmed scope

These checks belong to the confirmed features and F08. X04's separate broad usability
benchmark program and its previous 20-task/90-percent target are deferred. No new H01
visual-response timing target or H03 spoken-interruption target is an active gate.
Record the software commit and test conditions; distinguish fake results from Pi tests.

| Confirmed behavior | Required observation |
| --- | --- |
| H01 log-only reporting | Correlated transitions appear in the existing system log; no added lifecycle display/web presentation and no raw personal content in new log records. |
| F01–F04 stopping | Every public movement route respects stop/ownership/configuration; stop dispatch cannot wait for an ordinary action slot. Validate physical timing only in a separately approved test. |
| T01–T03 reminders/tasks | Synthetic restart, date/time-zone, recurrence, duplicate-claim, uncertainty, snooze/cancel and overdue tests pass. “Call me up at 4 pm today” saves the intended future local alarm or clarifies a past/ambiguous time. |
| T03/T04/T07 outcomes | Never report completion without the required result evidence; do not duplicate an uncertain external write. Calendar writes require the intended account/action scope. |
| H02 playback | Bounded synthesis and playback, controller cancellation, selected output accessible by the service, safe listener pause/resume, and honest disconnect/failure reporting. No simultaneous listening/speaking required. |
| H07 guided checks | Reuses existing menu/web entry points and F05 diagnostics; skips/re-entry work; no implicit deployment, greeting, movement, capture or configuration overwrite. |
| M01–M04 memory | Correction and retrieval use appropriate source/confidence; new records preserve existing user/retention boundaries. Recipes require user request/review; no M05 product expansion. |
| B01/B02/B04 outputs | Current presentation semantics preserved; bounded variations and game effects yield to safety/privacy; stale sensor data silences the game; no wheel commands and complete cleanup. |
| X05 project help | Known questions return cited current public sources; missing/stale/draft evidence is explicit. Traversal, setup/apply commands and private paths are inaccessible; no query-time installation. |
| F05/F06/X03 integration | Robot environment, user settings and durable data survive relevant changes; documentation reflects actual implemented status and passes wiki checks. |

For new speech processing, measure the actual Pi's processor/memory load as part of
H02 validation before choosing a provider. This focused integration check does not
reintroduce always-on vision, real-time voice or the deferred benchmarking initiative.

### 8.4 Separate manual validation lists

These are future validation steps. They were not performed for this document.

| Level | Operator checklist | Expected result | Stop or rollback |
| --- | --- | --- | --- |
| Safe smoke — no hardware | Run the software doctor, simulated chat/task journeys, fake reminders, and wiki checks. | Accurate capabilities, persistence and errors without opening devices. | Stop the simulated service and preserve diagnostic evidence; revert only the reviewed change. |
| Device communication | On the approved Pi setup, inspect device readiness and test display/buzzer deliberately; obtain consent before microphone or camera capture. | Configured devices are recognized and owned once; capture state is visible; temporary media is removed. | Stop the session, release devices, restore the previous approved configuration/environment. |
| Actuator movement | Only after safety gates pass, raise wheels, clear the area, and keep an operator ready to remove power. Exercise each approved movement route and stop/recovery case. | Bounded movement, prompt stop, no automatic replay after resume, no unintended movement from audio, guided checks or the distance game. | Remove actuator power if necessary, stop the service, preserve the fault latch and investigate before resuming. |
| Power and deployment | Separately approve any reboot, boot-file, service, update rollback, or shutdown test; first validate command construction with fakes and verify backups. | Approved service recovery and preservation of configuration/data; no unexpected boot motion. | Use the documented manual recovery route and last known-good release/backup. Never test destructive power paths automatically. |

## 9. Documentation and future decisions

### 9.1 Keep plans, facts, and private memory separate

This document now lives in `DevelopmentPlanDoc/` beside the owner’s confirmation list.
It does not replace the historical audit or redefine implemented behavior.
On approval of a phase, link its detailed specification and acceptance evidence
from this document. Mark checklist items complete only after implementation,
validation, and documentation are complete. Record the commit and any remaining
manual Pi checks beside the item or in a linked phase record.

For each implemented feature, follow the [existing wiki maintenance procedure][N-workflow]:

1. Identify affected current manuals using `project-knowledge.json`.
2. Create a new dated full source version under `raw/`; preserve registered originals.
3. Register and normalize the source, then prepare the exact proposed searchable
   page changes and review records.
4. Review the displayed changes, apply the approved plan, and record honest evidence.
5. Update the document map and README links, run wiki checks, and append rationale
   and validation to the new development-log version.

Installation changes affect the Installation Guide; architecture/task ownership
affect the Development Guide; external tools affect the MCP tutorial; public
behavior affects the root README. Dependency and service additions also need
third-party notices. Use the current wiki source locations rather than recreating
the removed root manual files.

For this document-only task, implemented behavior and registered manual sources
are unchanged. No curated wiki claims or review records need rewriting. This plan
can later be registered as a **proposal source** using the existing ingest/review
workflow; creating it here does not automatically add it to keyword search.
Coding agents can read it directly from the requested path now.

### 9.2 Decisions to resolve during phase planning

| Decision | Recorded direction | Remaining concrete choice |
| --- | --- | --- |
| Operating settings | H05 deferred; retain current profiles and startup behavior. | No desktop/quiet-hour default change in this stage. |
| Audio output | H02 confirmed; compatible Bluetooth uses standard OS support plus project playback integration. | Actual speaker, installed OS audio stack, service-user access and fallback output. |
| Speech processing | Sequential input/output only; H03 deferred. | Synthesis provider, languages, dependency/download size, cost and approved data flow. |
| Guided setup | H07 confirmed inside existing interactive/web routes; keep startup pairing intact. | Final menu wording and placement, shared diagnostics and optional practice actions. |
| Calendar access | Read-only planning followed by explicitly scoped writes. Local alarms use T02. | Connected account/calendars and exact approval/verification contract. |
| Memory | M01–M04 confirmed; preserve current boundaries and defer M05 expansion. | Additive record fields, existing-control behavior and reviewed recipe presentation. |
| Reminder downtime | Report missed or uncertain delivery and preserve saved records. | Catch-up and snooze details in the T02 specification; no phone call or off-Pi wake promise. |
| Distance game | B04 confirmed as an explicit bounded buzzer/display experience with no wheel commands. | Valid distance bands, session duration, output limits and resource arbitration. |
| Project help | X05 confirmed through read-only runtime tools; no maintenance commands exposed. | Final tool names, allowlisted source set, short query deadline and cache invalidation. |
| Release updates and optional hardware | X02 deferred; B05 evaluation confirmed. | No new updater work. Any hardware option needs a separate concrete design before installation. |

The recommended first implementation batch is phase 0A, with 0B installation diagnosis
and backup repair following closely. Existing scope decisions need not be asked again;
resolve concrete implementation choices where they affect behavior, data or hardware.
This revision itself performs only documentation work.

### 9.3 Confirmation-review record

Reviewed the owner's 39 entries against this plan and selected current code at
`939b821d8d426fd3ecf6d87e87c426d1e47eba91`. Serena inspected the existing onboarding
and voice-service symbols; targeted reads checked voice pause/resume, event logging,
service deployment and the wiki launcher. The search phrase “voice onboarding”
returned no curated match, so the review used “installation,” cited current manuals,
and implementation files. The wiki pages remain AI-reviewed drafts.

Changes in this revision: 31 confirmed items retained, H01 narrowed to logs with
its estimate reduced to Low, seven items deferred, B04 raised from Low to Medium
for complete conversational/lifecycle integration, phases and acceptance checks
aligned, and all five questions answered
in section 6.7. The owner's original confirmation rows remain unchanged; review
answers are appended separately to that document. The owner's file move/rename is
preserved. Current manuals and curated knowledge claims are unaffected because no
runtime feature has been implemented.

Validation for this revision:

- Compared all 39 decisions with the original confirmation: 31 confirmed, H01
  revised, seven deferred. All 32 active items have a phase allocation, including
  X03 throughout the phases; no deferred item is allocated as active work.
- Checked all five answer sections, table structure, reference definitions and
  local file/heading links: 186 link occurrences in this plan and eight in the
  confirmation document passed. External links are not counted as local checks.
- Verified that the original confirmation remains an unchanged byte-for-byte
  prefix; only the separate review section was appended.
- From the repository root, `python scripts/wiki.py check` passed and
  `python scripts/wiki.py lint --strict` reported zero errors, warnings or
  suggestions. No wiki source or review record was changed.
- `uv run --frozen --no-sync python scripts/verify_immutable_drivers.py` passed
  for 222 tracked files across six drivers, including 55 existing authorized
  repairs. `uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py`
  passed for all six libraries. These checks did not install dependencies.
- `git diff --check` passed. A separate whitespace check of the renamed,
  currently untracked plan also reported no whitespace errors.

These are documentation and source-integrity results. The full runtime test suite,
live service, speaker, sensor and movement tests were not run for this planning-only
revision. Their required checks remain in sections 7 and 8 for implementation.

## Appendix A. Complete Microduck audit

The competitor findings below are retained from the original audit. Adoption ideas
are evidence for design decisions, not an additional work queue; section 0 and the
revised checklist determine the currently selected scope.

### A.1 Product character and evidence boundary

Microduck is a small moving character rather than a productivity assistant. Its
README describes a roughly 25 cm, 800 g robot running on a Rockchip RK3566 board,
with fifteen servos and a control loop targeting 50 Hz — fifty updates per second.
Walking, roller movement, sitting, kicking, and ground-pick behaviors are connected
to learned movement policies (models that turn observations into motor commands).
Policy training lives in the separate `microduck_rl`
project; that training repository was not audited here. [README][M1],
[control implementation][M3], [workspace definition][M18].

The local checkout contains 283 files outside `.git`, including 135 Rust files
and 35 Markdown files (plain-text documents with formatting markers). The 19
workspace packages divide responsibilities into
control, perception, transports, configuration, updates, and development tools.
This breadth was inventoried; the analysis below concentrates on executable
paths and documentation relevant to the requested assistant refinement.

The architecture document explicitly labels itself a draft. It describes both
implemented structures and intended guarantees. The roadmap and code sometimes
supersede its wording. The report therefore uses implementation evidence when
documents disagree. No claim here is based on running or physically observing
a Microduck during this audit.

### A.2 Architecture and ownership

The core path is a client sending an intent, `robotd` interpreting it, and the
`duck-control` safety wrapper applying motor targets. An intent is a request such
as velocity, gaze, or a named action, rather than an unrestricted motor write.
The controller calculates targets without holding the hardware write handle.
The safety wrapper owns that handle. [Controller][M3], [safety wrapper][M4].

`robotd`, `configd`, `updaterd`, `btd`, `padd`, `mediad`, and `tofd` communicate
through service-specific channels. A daemon is a program that runs in the
background. Local control uses JSON-RPC — structured request-and-response messages —
over Unix sockets, local communication endpoints on the same computer.

Configuration and recovery are separated so they can remain reachable when
`robotd` fails. `btd` carries selected Bluetooth requests; `padd` converts gamepad
input into intents; `mediad` handles media and remote requests; `tofd` owns the
depth sensor. The shared protocol defines destinations, and each transport has
its own explicit permission selection. [Architecture][M2], [Bluetooth routing][M21].

**Why this is effective:** the control loop does not need to know whether a
request came from a gamepad or a remote application. Recovery does not depend on
the component it is trying to repair. Explicit routing also makes a newly added
command a deliberate transport decision.

**Limit:** many services, operating-system integrations, sockets, and deployment
units increase operational complexity. This separation fits a biped whose control
must stay responsive; it is not evidence that NinjaRobotPi5 needs seven daemons.
Retain the existing IDE owner and improve its diagnostics instead.

### A.3 Timing, intentions, and physical movement

`Intents` uses timestamped latest-value slots for velocity and head targets.
`ArcSwap` is a Rust mechanism for exchanging a shared value without making readers
wait for a writer's lock. One-shot skill requests use pending flags consumed by
the loop, rather than accumulating an unlimited queue. [Intent implementation][M5].

The controller selects among bounded skills and movement modes using a defined
priority. Learned policy output is converted into joint targets, with optional
smoothing. The policy-loading layer checks runtime and model compatibility.
The main loop records achieved timing and missed ticks rather than assuming that
an alive process is necessarily meeting its intended update rate. [Controller][M3],
[main loop][M24], [policy loading][M25].

**Why this works for interaction:** current intent matters more than a backlog of
old joystick positions. A delayed request should not make a robot repeat stale
motion after the user has stopped. Smooth transitions help a physical character
look coordinated while keeping expensive work outside the immediate path.

**Adaptation:** apply timestamps, cancellation, bounded queues, and explicit
precedence inside the Ninja IDE. Keep durable reminders in a separate Agent task
queue: “latest value wins” is appropriate for gaze or velocity, but would lose
important user tasks. Do not port biped policies to continuous-rotation wheel
servos or interpret timing estimates as measured wheel position.

### A.4 Safety and error handling: strengths and limits

The current safety wrapper rejects non-finite targets — invalid numbers such as
infinity — and clamps finite targets to the actuator's travel. Its command deadman,
a timeout that stops stale movement commands, defaults to 500 milliseconds and
zeros velocity while leaving the head target alone. [Safety implementation][M4].

There are important limits:

- The range clamp is the actuator's broad travel range, not complete anatomical
  limits for every joint. The source states this explicitly.
- `fallen` is reported but does not itself prohibit all driving. The main loop
  has a limp-fall sequence — reducing motor stiffness during a detected fall and
  progressing toward a recovery pose — controlled above the wrapper.
- The architecture's broad fall/joint/thermal safety aspirations must not be read
  as proof that every such condition is enforced identically in the checked code.
- Timestamped slots do not, by themselves, prove full arbitration among all remote,
  physical, and autonomous clients. The design still lists authority decisions.
- The robot's safe posture after a lost connection is specific to a balancing
  biped. It should not replace NinjaRobotPi5's existing stop/latch rules.

**Adaptation:** borrow enforceable ownership, non-finite validation, freshness,
and clearly reported reasons. Test Ninja's stop behavior through every public
entry point. Do not copy a fallen-robot recovery sequence or automatically resume
movement because another robot does so. [Main loop and fall tests][M24].

### A.5 Personality and nonverbal interaction

The sound system creates a stable acoustic character from a seed, a repeatable
starting number. Pitch, tone color, variation, and timing are derived from it.
Named cues such as greeting, inquiry, alarm, chirp, and coo give interaction events
a recognizable vocabulary. This is procedural sound generation, not spoken
language understanding or text-to-speech. [Personality implementation][M6],
[sound requests][M5].

**Why it can feel effective:** consistency lets a user recognize the character,
while bounded variation reduces obvious repetition. Local reactions do not need
to wait for a cloud answer. The interpretation that this improves perceived
character is a design inference; this audit did not measure user preference.

**Adaptation:** vary approved Ninja faces, blink timing, and buzzer cues within
limits. New quiet-hour/intensity controls are deferred under H05. Its buzzer cannot reproduce
Microduck's full synthesized voice. Preserve clear error and privacy indications
instead of making every event a playful reaction.

### A.6 The hand-controlled musical interaction

The theremin mode maps hand proximity to coordinated sound and mouth expression.
A theremin is an instrument played by moving a hand without touching it.
The implementation deliberately uses an explicit on/off mode after a more
automatic background-detection approach proved inconsistent in development.
The same proximity value drives the related expressive effects. [Theremin][M7].

Depth arrives asynchronously. A stale frame older than 500 milliseconds fades
the sound toward silence; a background reader retries the sensor connection.
The feature can report that usable frames are absent instead of accepting a
command that silently does nothing.

**Why this works:** the user can directly discover the cause and effect, and
the robot communicates sensor loss rather than freezing a note forever. An
explicit mode is easier to understand than an unreliable automatic guess.

**Adaptation:** B04 can use Ninja's single distance measurement to change a buzzer
pitch or face scale. It cannot copy an 8×8 depth image or reliable hand location
from the VL53L0X's single range. Use a short explicit game mode, validated readings,
and a timeout; keep it independent of wheel movement.

### A.7 Social behavior and the unfinished autonomous brain

The implemented chorale coordinates several ducks singing together. Bluetooth
beacons advertise participation, a deterministic leader assigns parts, and a beat
counter lets participants follow a shared musical position. Peers expire when
their signals become stale; a robot that does not know a piece keeps listening
rather than pretending to perform it. [Chorale implementation][M8].

The autonomy ideas document explicitly says the former runtime's richer brain
has not been ported into the daemon. Its proposed states include wandering,
resting, being petted, novelty-based exploration, and mood/energy-driven choices.
Remembering familiar ducks and spontaneous social singing are also described
as future behavior ideas. They must not be counted as completed persistent
personalization or a current general autonomous assistant. [Autonomy ideas][M15].

Conversely, that ideas file's “duck detector waiting” section is stale relative
to current code: `mediad/src/detect.rs` now contains the detector worker. This
is a useful example of why a design note cannot be the sole feature inventory.

**Adaptation:** apply the shared-state and stale-participant lessons to current
Ninja sessions and expressions. Multi-robot singing is optional entertainment,
not a prerequisite for a desktop assistant. Do not create a mood system that can
override user tasks or safety.

### A.8 Voice, sensing, and perception

Microduck has sound production, microphone-based perception, camera processing,
an IMU — an inertial measurement unit that senses rotation and acceleration —
and an optional time-of-flight depth sensor, which estimates distance from light.
These are useful local interaction inputs, not evidence of a conversational LLM,
a large language model that generates and interprets language.

| Component | Source-confirmed approach | Value and limitation |
| --- | --- | --- |
| Petting detection | Small audio classifier and a worker extracting recent microphone features. | Detects a narrow sensory event; accuracy depends on the robot's acoustic construction. Not a universal touch sensor or speaker identification. |
| Ambient sound | Worker classifies sound events and gates some reactions against self-generated activity. | Useful groundwork for attention; the autonomy document notes inputs waiting for the fuller brain. Not a speech conversation pipeline. |
| Duck detection | Camera worker supports model execution on the CPU (main processor) or Rockchip NPU (specialized neural-processing chip), based on model type. Work is paced and placed on a separate thread — an independently scheduled part of a process. | Concrete perception code exists; comments document heat and throughput tradeoffs. No accuracy/thermal benchmark was reproduced here. |
| Depth | Dedicated service reports starting, available, or unavailable and publishes depth frames. | Clients can explain absence and freshness. Its richer sensor is not interchangeable with Ninja's single-range sensor. |
| Position estimate | Contact-based odometry — estimating movement from the feet and inertial readings — shares the robot's geometry model. | Avoids duplicated geometry, but depends on flat-ground/contact assumptions and includes documented placeholder dimensions. It is not general navigation. |

Evidence: [petting model][M9], [audio worker][M22], [camera detector][M10],
[depth status][M11], [odometry][M17].

**Adaptation:** emit small recent observations through the IDE, with timestamp,
validity, confidence, and clear ownership. Budget camera/audio computation so it
does not disrupt control or conversation. Do not reuse models trained on a
different microphone/robot shape without evaluation and consented data collection.

### A.9 AI, tools, tasks, and memory

The verified learning machinery here is mainly movement-policy inference and
narrow perception. The named skills are robot motions, not Ninja-style reusable
language-agent workflows. The control protocol offers useful typed robot commands,
but the audited core does not establish a general language planning loop,
personal calendar agent, durable reminder service, or user-profile memory store.

Persisted configuration, sound personality, installed policy choices, and update
history should not be confused with memory about a human user. Proposed social
recognition in the ideas document is also distinct from implemented personalization.

**Adaptation:** retain Ninja's existing Agent and memory foundation. Learn from
Microduck how a fast local reaction can accompany a slower task, not how to replace
the language agent with a movement policy.

### A.10 Remote interaction, privacy, and security

`mediad` carries media and routes control messages, reusing shared service contracts.
WebRTC is a technology for real-time browser media and data connections. Its use
can avoid writing a separate robot command interface for each transport.
[Media session][M14].

However, the checked session layer explicitly does not authenticate local peers.
The roadmap still describes unfinished remote bridging, session consent, and
the hardware question of a visible streaming indicator. Account-login machinery
does not establish a completed remote-access experience. Encrypted transport also
does not establish user consent or authorization. [Roadmap][M16].

**Adaptation:** retain Ninja's existing pairing, controller lease, media consent,
and approved tunnel boundary. Borrow transport reuse and clear session state;
do not copy the local-network trust model or expose a new unauthenticated port.

### A.11 Installation, updates, robustness, and testing

The updater verifies signed manifests and artifacts before extraction, stages
release directories, changes the active release, and performs a health gate with
rollback. A signature is a cryptographic check of an artifact's approved origin;
a hash checks that its contents match expected bytes. These are distinct checks.
[Verification][M13], [engine][M12].

The design separates software health from board conditions so an unrelated
hardware problem does not automatically condemn a new release. It preserves
per-board state outside release directories. Diagnostics distinguish installed
software from the version actually running. The workspace records important
runtime/model input versions centrally and tests agreement with standalone setup
scripts. [Architecture][M2], [workspace pins][M18].

Update tests use a real update engine with temporary local artifacts, fake robot
health, and injected failures. Their value is in exercising the recovery mechanism
without provoking a real robot failure. They were inspected, not executed here.
[Update tests][M19].

**Limits:** hooks and service replacement are powerful operations; a signed release
can still contain a software defect. Policy installation follows a different path
from daemon release replacement, so “every update is equally reversible” would
be too broad. Some bundled material also carries test-only comments. Do not copy
assets or deploy its updater as a shortcut.

**Adaptation:** F05/F06 should improve Ninja's current installation and backup
path first: clear version identity, correct environment, staged validation,
complete recovery inventory, and simulated failure tests. Automatic updates can
wait until manual rollback is demonstrated; the broader X02 updater project is deferred.

### A.12 Module coverage and realistic adoption

This inventory covers all workspace packages at responsibility level. A grouped
overview is not a claim that every statement in every file was manually reviewed.

| Packages or files | Responsibility reviewed | Ninja lesson |
| --- | --- | --- |
| `robotd`, `duck-control` | Main loop, policy selection, hardware input/output interface, safety, observations, fall handling. | Enforced ownership and bounded, fresh intent. Physical policy is not portable. |
| `robotd-params`, `duck-ipc-proto` | Shared parameter/protocol definitions and command routing contracts. | Avoid drift between help, validation, adapters, and actual behavior. |
| `sounds` | Seeded character, synthesized cues, streaming voice and shared beat. | Bounded variation and synchronized expression. |
| `pet-detect`, `duck-detect` | Audio and vision perception workers/models. | Small validated observations; account for hardware and training differences. |
| `tof`, `kinematics`, `odometry` | Depth service, spatial geometry, hand tracking, movement estimate. | Freshness and a shared geometry source; no assumption of equivalent Ninja sensors. |
| `btd`, `padd`, `mediad` | Bluetooth, gamepad and media/remote transports. | Reuse typed commands; maintain explicit permissions and ownership. |
| `configd` | Network, identity, pairing and administrative operations, including fake backends. | Diagnostics/configuration should survive a control failure. |
| `updater` | Verification, staging, health, rollback, state, sources and policy handling. | Test recovery with deliberately broken temporary releases. |
| `robotctl`, `duckctl` | On-robot and Bluetooth operator interfaces. | Make troubleshooting accessible without asking users to interpret raw logs. |
| `test-support`, `xtask` | Fixtures, release packaging and validation. | Reuse realistic test mechanisms without touching live services. |
| `docs/`, `deploy/`, `scripts/`, package metadata | Architecture, roadmap, operating guidance and delivery configuration. | Distinguish draft plans, installation behavior, and executable guarantees. |

**Best near-term transfers:** fresh intent, stable small expressions, capability
health, and recovery testing. **Later optional transfer:** a simple sensor game.
**Poor fits:** learned biped locomotion, acoustic petting without retraining,
multi-robot social state, the seven-daemon layout, and unreviewed remote trust.

## Appendix B. Complete Reachy Mini audit

### B.1 Product character and evidence boundary

Reachy Mini is designed around expressive desktop interaction and application
development. Its head has six degrees of freedom — six independent ways to change
position or orientation — plus body rotation and two expressive antennas.
The local documentation distinguishes the Wireless version, with onboard computing
and an IMU, from Lite, which uses a host computer. [README][R1], [agent guide][R2].

The checkout contains 894 files outside `.git`, including 248 Python files,
60 TypeScript files (a form of JavaScript with checked data types), 21 `.tsx`
user-interface component files, and 88 Markdown
files. Many remaining files are physical design models and assets. They were
inventoried, not mechanically validated or visually inspected one by one.

The core repository supplies robot access, media, motion, applications and supporting
tools. Full conversational behavior belongs to a separately distributed conversation
application. This distinction is central to a fair comparison.

### B.2 Architecture and access paths

The Python `ReachyMini` interface communicates with a daemon that owns a backend
for either the real robot or simulation. A backend is an interchangeable
implementation behind a shared interface. The project includes a real hardware
backend, MuJoCo physics simulation, and a lightweight mock simulation.
[Python interface][R3], [daemon][R17], [backend][R4], [mock simulation][R18].

Browser applications use the JavaScript/TypeScript SDK, a software development kit
that packages robot commands and connection handling. Browser media and control
travel through WebRTC. HTTP (ordinary web requests) and WebSocket (a continuing
two-way web connection) routes provide additional access paths.
Structured protocol models and the backend command dispatcher keep much of the
command meaning in one place. [Protocol][R19], [browser SDK][R13].

**Why this works:** application developers can work in familiar languages and
reuse motion/media behavior without rewriting hardware control. Simulation
reduces the cost of trying an interaction before hardware is available.

**Limits:** multiple transports and substantial browser/media machinery create
more lifecycle and version-compatibility work. The backend is large and coordinates
many concerns. This audit does not treat that size as a demonstrated defect, but
it is not a model for putting all new Ninja features in one file.

**Adaptation:** extend Ninja's existing typed tools and simulated IDE. Do not add
a browser-to-driver route or replace Agent policy with direct SDK calls.

### B.3 Human-robot interaction and physical input

The interaction guidance treats the body as both output and input: antenna
displacement can act like a button, and a compliant head can act as a controller
or be guided for recording. Readiness, processing, success and error can be
communicated with a small movement vocabulary. [Interaction patterns][R20].

**Why this can be effective:** a user can discover a tangible cause and effect,
and interaction does not always require a phone or a full conversation. Gaze and
small gestures provide attention cues while an application performs other work.
These are design inferences, not usability results measured during this audit.

**Limits:** touch-like input depends on compliant mechanics and readable joint
positions. It needs tuned thresholds, repeated-input suppression, accessibility
alternatives, and careful torque handling. A tutorial saying an antenna is pushable
does not certify every motor mode or modified robot as safe to handle.

**Adaptation:** use Ninja's existing web buttons, explicit voice commands and screen
cues first. Do not ask users to push the wheel servos or infer touch from commands
that provide no physical feedback. Add a dedicated button or touch sensor only
as a separately scoped hardware change.

### B.4 Motion design and expressive behavior

The project separates smooth `goto_target` movements from repeatedly updated
`set_target` control. Interpolation calculates the intermediate positions between
two poses; provided methods include linear, minimum-jerk, ease-in/out, and cartoon
styles. Minimum-jerk movement reduces abrupt changes in acceleration.
[Motion guidance][R21], [playback implementation][R4].

Recorded moves combine motion and optional sound. Backend playback evaluates
the move against its timeline, supports sound timing adjustment, checks stop or
cancellation signals, and cleans up delayed sound tasks. Direct control is
appropriate for tracking, but applications should combine desired effects before
issuing the final target rather than let several loops fight each other.

The older motion skill says a `goto_target` commits to its motion. Current backend
code is more nuanced: the application call may block its own flow, but the backend
playback loop checks a global stop request and optional cancellation token.
Do not describe all current Reachy moves as uninterruptible based only on the skill.

**Adaptation:** coordinate Ninja face, buzzer, and future speech through its existing
behavior system. Add bounded cancellation and final-state cleanup there. Do not
copy pose coordinates, head mechanics, or movement rates directly into wheel commands.

### B.5 Speech, audio, and conversation

The core contains microphone/speaker media paths, direction-of-arrival support —
estimating where sound came from — audio controls, and a text-to-speech example
that calls an external service. It also includes speech-reactive head movement.
The example is not a built-in always-available local speech engine.
[Media server][R6], [TTS example][R22], [speech movement][R5].

`HeadWobbler` derives small movement offsets from audio and schedules them against
expected playback time. It skips stale work and uses a generation counter to
invalidate callbacks after stop/reset. The audio path contains echo-probe support
and corresponding tests. This is evidence of implementation effort, not proof of
echo-free operation in every room or hardware variant. [Wobbler][R5],
[audio tests][R23].

**Why the approach helps:** a robot moving with the sound being heard feels more
coherent than one reacting to network packet arrival. Cancelling future callbacks
prevents old speech from causing movement after the user interrupts.

**Adaptation:** use playback time to coordinate Ninja's face, not its wheels.
Implement an approved speaker path before promising voice output. Confirm the
actual microphone's capabilities before proposing sound-direction tracking;
the current USB microphone is not established as equivalent to Reachy's audio hardware.

#### Separate conversation application: supplementary evidence

The core includes a tool that clones a separate conversation application;
that implementation is not vendored into the audited core. Its upstream README,
consulted on 7 September 2026, describes real-time voice, vision, queued expressive
motion, personality-aware tools, and optional external MCP tools. It currently
describes a Hugging Face real-time backend, whereas the local core AI skill refers
to an OpenAI-based setup. This is version drift, not evidence that one configuration
works across all versions. The external application was not installed, run, or
given a full source audit. [Fork utility][R24], [local AI skill][R25],
[upstream conversation README](https://github.com/pollen-robotics/reachy_mini_conversation_app).

### B.6 AI, tool use, task completion, and personality

The core AI skill recommends that model tools enqueue expressive actions while
a control loop executes them. It describes personality profiles as instructions
and permitted tools. These are useful application patterns, but the core daemon
does not itself become a general language-agent planner because it accepts commands.
[AI integration skill][R25], [conversation fork utility][R24].

**Why this works:** delayed model reasoning need not disrupt motion timing, and
an application can change conversational style without replacing hardware control.
Queued expression also makes the boundary between a proposal and actual execution
more explicit.

**Limit:** the tutorial's illustrative “queued” response is not proof the action
finished. Profile instructions do not supply deterministic authorization or durable
task recovery. The inspected core does not establish alarms, a personal schedule
manager, or reliable verification of arbitrary external goals.

**Adaptation:** keep Ninja's stronger separation of policy and tools. Add terminal
outcomes and durable task records around it. Personality may influence phrasing
and permitted expression selection, but cannot authorize an action.

### B.7 Memory and user personalization

The core persists useful operational configuration and supports application/profile
customization. Motion recording stores actions for playback. These are not the same
as a consent-aware user memory system that retrieves previous preferences and
task outcomes across conversations.

The audited core and inspected application scaffolding do not establish a
Ninja-style user memory database, correction workflow, or learned personal task
recipes. This is a scoped finding; it does not claim that no external community
application could implement them.

**Adaptation:** keep the existing Ninja memory store and improve its transparency.
Use profile configuration for user-selected style and separate it from inferred
facts. Do not replace structured memory with an ever-growing personality prompt.

### B.8 Perception and attention

The face-tracking implementation runs detection separately and publishes recent
observations. It selects a plausible face, uses association and miss limits to
avoid arbitrary switching, smooths small movements, and converts image positions
into gaze through shared geometry. [Tracking][R7], [look-at geometry][R8].

The hardware backend caches inertial readings with a freshness limit. If the
control loop stops updating, old data is treated as absent rather than current.
This makes state more honest during a fault. [Robot backend][R9].

**Why this helps:** jittery detection otherwise becomes jittery movement, and
switching attention between faces can feel confusing. Sensor freshness matters
because “last known” is not necessarily “true now.”

**Limits:** face tracking is not face identification or permission to disclose
personal data. Gaze accuracy depends on camera geometry and mechanical calibration.
Tracking also adds camera use and processor load. No tracking-accuracy or multi-user
experience benchmark was run here.

**Possible later adaptation (B03 is deferred):** consented, low-rate attention cues on Ninja's display,
with stale-observation expiry. This is not active work in this stage. Do not turn the whole wheeled robot to imitate a
head movement on a desk. Keep identity and authorization separate.

### B.9 Ownership, stopping, and network recovery

`RobotAppLock` coordinates managed local Python apps and centrally connected remote
sessions. A local app can evict a remote session; a remote session is refused while
the local app owns the slot. The source explicitly states this is not a general
hardware lock: direct local REST and LAN/WebSocket access bypass it. REST is an
HTTP-based interface; LAN means local area network. [App lock][R12].

When managed ownership is released, the backend can reset to an idle/sleep state,
with a grace period for handoff and cancellation if a new owner arrives. This is
more robust than trusting every browser tab or application to exit cleanly.
It can also involve physical motion, so the idea is not a drop-in Ninja stop policy.
[Idle reset][R4], [idle-reset tests][R26].

The browser SDK separates session recovery into a supervisor. It handles brief
connection failures, bounded redial attempts, and prolonged data-channel silence.
A separate pending-reply ledger settles outstanding requests when a connection
ends so they do not hang indefinitely. [Session supervisor][R15],
[pending replies][R16].

**Adaptation:** improve Ninja's existing service/lease recovery and pending-request
cleanup. Reconnect the user interface, but do not automatically replay movement
or assume an uncertain external action failed. Enforce the shared owner across
all public routes, including older tools, rather than copying the limited app lock.

### B.10 Hardware safeguards and robustness limits

The real backend owns a periodic motor loop, tracks live state and errors, and
contains retry/error handling. Motion and protocol layers validate requests;
media upload handling bounds input and cleans up stale transfers. Test sources
cover backend readiness, playback cancellation, upload behavior, and recovery.
[Robot backend][R9], [backend][R4], [protocol][R19], [request limits][R27].

However, geometric collision checking is optional and defaults to false in the
inspected real backend constructor. Broad SDK angle guidance, selectable torque
modes, an app lock, and collision-checking support do not collectively establish
a universal emergency-stop or safety guarantee.

The mock simulation applies targets immediately and does not simulate physics.
Its documentation also notes that applications may use the host camera/microphone.
Consequently, “simulation” is not automatically equivalent to “no personal-data
capture.” No simulator was launched for this audit. [Mock backend][R18].

**Adaptation:** use explicit Ninja fake-device tests with no actual media. Measure
physical stopping separately. Keep emergency stop outside slower application
lifecycle machinery and retain the current safe-resume contract.

### B.11 Extensibility, educational applications, and browser experience

`ReachyMiniApp` provides a reusable lifecycle and stop signal; `AppManager` launches
Python apps as processes, monitors their results, and escalates termination after
a timeout. Templates and the application assistant generate a starting structure.
Installed applications can be discovered from community sources.
[Application base][R10], [manager][R11], [application sources][R28].

The browser host provides recognizable connecting, live, leaving and error states.
Its versioned embedded-app message contract validates origins, helping distinguish
expected parent/app communication from unrelated browser messages. These are
concrete improvements to onboarding and failure visibility. [Host protocol][R14].

**Why this works for education:** a learner can start with a bounded interaction
and then add sensing, motion, or AI. Examples isolate concepts such as gaze, sound,
recording and interpolation. A reusable host lets each application focus on what
it teaches rather than repeat connection screens.

**Limits:** installed Python apps are executable software, not a sandboxed data
format. Desktop/wireless modes use a shared application environment separate from
the daemon, so dependency conflicts can still occur among apps. Browser hosting,
account sign-in, network access and library compatibility add operational dependencies.
An app-store listing is not a security review or proof of long-term maintenance.

**Adaptation:** begin with a small reviewed Ninja skill/behavior catalog and templates
that use existing tools. Declare required capabilities and consent before running.
Keep the robot environment distinct from development/wiki tooling and optional app
dependencies. A full public app store is not required for the next milestone.

### B.12 Documentation, tests, and adoption constraints

The checkout includes practical examples, notebooks, AI-agent instructions, focused
skills, Python tests, browser protocol/recovery tests, and fake backend fixtures.
Examples of valuable failure tests include idle-reset races, backend status,
speech callback cancellation, app stop behavior, media uploads, and network redial.
Tests were read as evidence of intended contracts; no passing competitor test
result or coverage percentage is claimed.

The instructions and implementation are not perfectly synchronized. Besides the
voice-provider and movement-cancellation differences noted above, tutorial snippets
and external application paths need checking before reuse. That supports Ninja's
wiki source/review workflow rather than replacing it with copied skills.

The core README declares Apache 2.0 for software and a separate Creative Commons
BY-SA-NC label for hardware design files. Treat these as repository-declared terms;
review exact licenses and attribution obligations before any reuse. This task
copies no implementation or assets. [README/license declaration][R1].

| Area inventoried/reviewed | Main responsibilities | Realistic Ninja transfer |
| --- | --- | --- |
| `reachy_mini.py`, `io/`, `utils/` | Client interface, messages, discovery, geometry helpers and configuration. | Typed boundaries and clear compatibility; no duplicate hardware client. |
| `daemon/`, real/mock/MuJoCo backends | Control, state, lifecycle, routing and simulation. | Hardware ownership, fresh status and realistic fakes. |
| `motion/`, `vision/` | Smooth/recorded motion, speech movement, face detection, tracking and gaze. | Shared expression timeline and consented display attention. |
| `media/` | Camera/audio paths, transport, echo support, device detection and cleanup. | Single media owner, explicit privacy state and resource budgets. |
| `apps/`, source helpers, templates | Discovery, generation, process lifecycle and installation. | Reviewed skills and templates with declared capabilities. |
| `ts/lib/` | Browser commands, sessions, tokens, request completion and recovery. | Reconnect and error presentation through the existing Ninja web boundary. |
| `ts/host/` | User-facing connection/leave flow and embedded-app protocol. | Consistent progress and teardown UX — user experience. |
| `tests/`, browser tests, `examples/` | Contract checks, fakes, failure scenarios and demonstrations. | Repeatable user journeys; isolate hardware/media examples from ordinary tests. |
| `docs/`, `skills/`, agent files | Educational guidance and AI-assisted app-building workflow. | Short evidence-backed development recipes in the existing wiki. |
| `descriptions/`, assets, firmware/tools, package/release files | Physical models, device resources and deployment support. | Inventory and provenance discipline; hardware-specific content is not portable. |

**Best near-term transfers:** interaction states, cancellation-aware expression,
session cleanup, and developer templates. **Later transfers:** audio-driven display
expression and optional perception. **Poor fits:** wheel-based imitation of head
motion, pushable motor input, direct unmediated browser control, or assuming every
community application supplies dependable assistant memory and task completion.

## Appendix C. Feature comparison matrix

“Implemented” means supported by the inspected source, not proven reliable on
physical robots in this audit. “Not established” means not found in the reviewed
core paths; external applications may differ. Qualitative observations explain
design strengths and tradeoffs, not a measured product ranking. Adoption suggestions in this historical comparison are
subject to section 0; deferred items are not implementation commitments.

| Feature or experience | NinjaRobotPi5 baseline | Microduck reference | Reachy Mini reference | Lesson and applicability |
| --- | --- | --- | --- | --- |
| Primary purpose | Conversational controller with tool policy, memory and web access; useful assistant foundation. | Responsive mobile character with learned movement and recovery tooling. | Expressive desktop platform with accessible applications. | Preserve Ninja's assistant foundation; improve embodiment and task reliability. High fit. |
| Hardware ownership | Integrated Agent → IDE → driver path, with audited gaps in direct/legacy paths. | Hardware write handle owned by safety wrapper; transports send intents. | Daemon backend owns normal control; managed app lock excludes some direct routes. | Enforce Ninja's intended boundary across every route; do not weaken it to match a reference. High fit. |
| Immediate feedback | Thinking/responding/idle faces and tool-related expression exist. | Local sound/motion reactions avoid language-model latency. | Gaze, antennas, head motion and visible app states convey engagement. | Extend existing screen states and acknowledgement; no new hardware needed. High fit. |
| Voice input/output | Opt-in wake/record/transcribe; no established spoken output pipeline. | Synthesized nonverbal voice and sound-event detection; no general conversation stack established. | Core media and speech examples; fuller conversation is an external application. | Add optional speaker/TTS, then measure interruption and echo. High value, hardware-dependent. |
| Personality | Approved emotion faces, behaviors and preference foundation. | Stable seeded voice; richer autonomous mood system remains to be ported. | Expressive motion and app-level personality/profile patterns. | Stable style, restrained variation, user control. High fit; mood never grants authority. |
| Goal planning | Bounded Agent reasoning and tool execution already exist. | Learned locomotion and named physical skills; not general goal planning. | Core exposes controls; AI application pattern queues actions. | Durable tasks around existing AgentLoop, not a new intelligence runtime. High fit. |
| Outcome verification | Typed results and ledger, with MCP false-success gap. | Intent acceptance plus state/health; not general task proof. | Playback completion/cancellation and app status; queueing alone is insufficient. | Distinguish accepted, finished and uncertain; verify external effects. High fit. |
| Alarms/reminders | No durable user reminder service established; IDE scheduler is resource coordination. | Alarm sound tag, not a personal alarm-clock service. | Sound/playback primitives, not a core personal reminder service. | Add local durable reminders; avoid confusing a sound cue with scheduling. Highest practical fit. |
| Schedule planning | Read-only calendar tutorial and external tool infrastructure, conditional on setup. | No personal calendar workflow established. | No core calendar workflow established. | Read planning first, verified writes with separate approval later. High fit. |
| Web research | External search skill/tutorial and bounded untrusted results. | Remote robot access is not web research. | App extensibility may supply tools; core is not a research assistant. | Citations, dates, saving and honest partial results complete the user journey. High fit. |
| Persistent user memory | User-scoped profiles/preferences/history and memory search exist. | Operational state, sound identity and proposed social memory are different. | Configuration/profiles/recordings; core human-memory service not established. | Improve current store's provenance, correction and privacy. High fit. |
| Learning from users | Narrow preference capture and behavior outcomes provide groundwork. | Offline-trained movement policies; proposed autonomous habits. | App customization and recorded motion; adaptive personal learning not established in core. | Reviewable recipes and feedback; no autonomous code or safety-rule rewriting. High fit. |
| Expressive coordination | IDE behavior system and presentation already coordinate several outputs. | Shared proximity/beat inputs coordinate sound and physical expression. | Recorded playback and speech offsets share timing and cancellation. | One IDE expression timeline with safety/privacy precedence. High fit. |
| Physical touch input | Not established with current wheel hardware. | Acoustic petting classifier is hardware-specific. | Compliant antennas/head and position feedback enable tangible input. | Dedicated future input hardware only; use web/voice now. Low immediate fit. |
| Face attention | Face identity/camera capabilities; continuous attention behavior not established. | Duck detection and local sensing; not general human gaze tracking. | Smoothed, associated face targets and calibrated look-at geometry. | Opt-in animated-eye attention; never steer wheels as a head substitute. Medium fit. |
| Distance/spatial sensing | Single forward VL53L0X range; no proven desk-edge protection or wheel odometry. | Optional 8×8 depth plus contact/inertial position estimate. | Head geometry, camera and variant-specific inertial/audio information. | Fresh observations and explicit limits transfer; hardware capabilities do not. High principle fit. |
| Movement | Continuous-rotation wheels with calibrated/timed behavior and stop mechanisms. | Fifteen-servo walking/roller/skill policies with smoothing. | Expressive head/body/antenna pose control. | Improve bounded Ninja behavior; neither physical control model is a replacement. Low direct portability. |
| Safety and interruption | Latches, leases and cancellation exist, but A01–A05 need closure. | Deadman and numeric checks; fallen status is not universal inhibition. | Interruptible playback, ownership handoff; optional collision check and partial lock coverage. | Fix baseline first; no competitor is a blanket safety template. Critical. |
| Degraded operation | Optional tools and health exist; missing driver episode exposed diagnostic confusion. | Recovery services survive control failure; sensor states explain absence. | Live backend status, controlled teardown and session recovery. | Capability health plus software-only diagnostics. High fit. |
| Remote control | Existing pairing and approved tunnel/lease boundary. | Local WebRTC and routing; remote/privacy roadmap still has gaps. | Browser sessions and host flow with separate managed ownership. | Reuse current secure boundary; borrow reconnection UX. High fit. |
| Recovery after restart | Existing service/persistence, but complete backup and durable task recovery need work. | Verified staged releases and health rollback; operational state kept separately. | App-stop/idle cleanup and browser retry mechanisms. | Combine data-safe backup with non-replaying task/session recovery. High fit. |
| Education and extensibility | Existing skills, typed tools, behavior definitions and local wiki. | Focused services, operator tools, fakes and design rationale. | Examples, simulation, templates, Python/browser apps and community catalog. | Reviewed small Ninja applications and reproducible examples. High fit. |
| Development knowledge | Versioned source manuals and AI-reviewed draft topic pages across coding tools. | Detailed rationale, but draft/idea documents can lag implementation. | Strong agent instructions/skills, with some version drift. | Keep code comparison and explicit review state; do not import instructions blindly. High fit. |
| Privacy | Existing media consent and local user memory controls; external environment needs tightening. | Session privacy aspirations exceed some current implementations. | Rich media and application access require explicit deployment policy. | Preserve Ninja consent and user isolation; optimize experience without silent capture. Critical. |

## Appendix D. Evidence directory and audit limitations

### D.1 Source navigation

All local links below resolve relative to this document. `DevelopmentReferences/`
contains separate local reference repositories and is not tracked as ordinary
NinjaRobotPi5 source in this checkout. Another developer may need to obtain the
same reference commits before local links are available. The pinned upstream
trees provide alternative navigation:

- [Microduck at the audited commit](https://github.com/pollen-robotics/microduck/tree/bc41fb5c9a9b39894669c1e022e375cf83800382).
- [Reachy Mini at the audited commit](https://github.com/pollen-robotics/reachy_mini/tree/234a978e4426895fc88d864e7f154643aea77f53).

These links identify source versions, not a recommendation to install or execute
their setup scripts. No reference implementation was copied into NinjaRobotPi5.

| Evidence group | Entry points for future developers |
| --- | --- |
| Ninja baseline and policy | [Prior audit][N-audit], [root policy][N-policy], [current wiki][N-wiki], [development guide][N-guide], [installation guide][N-install], [MCP tutorial][N-mcpguide]. |
| Ninja execution and interaction | [AgentLoop][N-loop], [registry][N-tools], [MCP provider][N-mcp], [presentation][N-present], [voice service][N-voice], [integrated IDE][N-integrated], [scheduler][N-scheduler], [servo path][N-servo]. |
| Ninja persistence and maintenance | [Memory schema][N-memory], [memory services][N-memoryservices], [deployment/backup][N-deploy], [knowledge workflow][N-workflow], [source map][N-map]. |
| Microduck architecture/control | [README][M1], [architecture][M2], [controller][M3], [safety][M4], [intents][M5], [main loop][M24], [policy loader][M25]. |
| Microduck interaction/perception | [Sound personality][M6], [theremin][M7], [chorale][M8], [petting][M9], [audio worker][M22], [vision worker][M10], [depth status][M11], [odometry][M17]. |
| Microduck delivery and gaps | [Updater][M12], [verification][M13], [media session][M14], [autonomy ideas][M15], [roadmap][M16], [workspace][M18], [update tests][M19], [parameter registry][M20], [Bluetooth routing][M21]. |
| Reachy platform and motion | [README][R1], [agent guide][R2], [Python interface][R3], [backend][R4], [real backend][R9], [daemon][R17], [mock backend][R18], [protocol][R19], [motion guidance][R21]. |
| Reachy interaction/media | [Speech movement][R5], [media server][R6], [tracking][R7], [gaze geometry][R8], [interaction guidance][R20], [TTS example][R22], [audio tests][R23]. |
| Reachy applications and recovery | [Application base][R10], [manager][R11], [app lock][R12], [browser SDK][R13], [host protocol][R14], [session supervisor][R15], [reply cleanup][R16], [fork utility][R24], [AI skill][R25], [idle-reset tests][R26], [request limits][R27], [application environment][R28]. |

### D.2 What this audit can and cannot conclude

- This is a comprehensive architecture, interaction, capability and adaptation
  audit of the requested reference projects. It is not a line-by-line security
  certification of every dependency, firmware image, model weight, or design asset.
- File inventories establish scope. Code and test-source inspection establish
  implementation patterns. Neither establishes physical performance by itself.
- No comparative latency, speech accuracy, perception accuracy, battery life,
  mechanical safety, or user-satisfaction benchmark was performed. “Effective”
  explains why a pattern is promising, with limitations, rather than claiming a
  measured winner.
- External model services, accounts, media servers, community applications,
  Microduck training, and hardware-manufacturing repositories were not fully
  audited. The separate Reachy conversation README is supplementary, dated evidence.
- The previous Ninja audit's test counts and hardware findings remain attributed
  to that report. This document does not repeat them as fresh validation.
- Passing wiki review means the recorded source claims were checked by an AI
  reviewer. The relevant pages remain drafts; it does not imply human approval
  or hardware certification.
- New features stay proposed until implemented and tested. In particular, this
  plan does not make reminders, spoken replies, calendar writes, or runtime wiki
  retrieval available merely by documenting them.

For implementation, begin with the [root workflow][N-policy], consult the
[current manuals][N-wiki], and attach new validation evidence to the approved phase.

[N-audit]: ../DevelopmentPlanDoc/NinjaRobotPi5_v2_audit_260906.md
[N-policy]: ../AGENTS.md
[N-wiki]: ../ninjarobot_pi5_wiki/README.md
[N-guide]: ../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07/DevelopmentGuide.md
[N-install]: ../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07/InstallationGuide.md
[N-mcpguide]: ../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07/NinjaRobot_MCP_Skill.md
[N-workflow]: ../ninjarobot_pi5_wiki/docs/PROJECT_WORKFLOW.md
[N-map]: ../ninjarobot_pi5_wiki/project-knowledge.json
[N-features]: ../ninjarobot_pi5_wiki/wiki/concepts/features-and-tools.md
[N-loop]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py
[N-tools]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/tools.py
[N-present]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/presentation.py
[N-memory]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_migrations.py
[N-memoryservices]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/memory_services.py
[N-voice]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/voice_service.py
[N-integrated]: ../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/integrated.py
[N-scheduler]: ../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/scheduler.py
[N-servo]: ../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/servo.py
[N-mcp]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/mcp_client.py
[N-deploy]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment.py
[M1]: ../DevelopmentReferences/microduck/README.md
[M2]: ../DevelopmentReferences/microduck/docs/design/architecture.md
[M3]: ../DevelopmentReferences/microduck/robotd/src/control.rs
[M4]: ../DevelopmentReferences/microduck/duck-control/src/safety.rs
[M5]: ../DevelopmentReferences/microduck/robotd/src/intents.rs
[M6]: ../DevelopmentReferences/microduck/sounds/src/personality.rs
[M7]: ../DevelopmentReferences/microduck/robotd/src/theremin.rs
[M8]: ../DevelopmentReferences/microduck/robotd/src/chorale.rs
[M9]: ../DevelopmentReferences/microduck/pet-detect/src/lib.rs
[M10]: ../DevelopmentReferences/microduck/mediad/src/detect.rs
[M11]: ../DevelopmentReferences/microduck/tof/src/status.rs
[M12]: ../DevelopmentReferences/microduck/updater/src/engine.rs
[M13]: ../DevelopmentReferences/microduck/updater/src/verify.rs
[M14]: ../DevelopmentReferences/microduck/mediad/src/session.rs
[M15]: ../DevelopmentReferences/microduck/docs/ideas/autonomous_behavior.md
[M16]: ../DevelopmentReferences/microduck/docs/project/roadmap.md
[M17]: ../DevelopmentReferences/microduck/odometry/src/lib.rs
[M18]: ../DevelopmentReferences/microduck/Cargo.toml
[M19]: ../DevelopmentReferences/microduck/updater/tests/apply.rs
[M20]: ../DevelopmentReferences/microduck/robotd-params/src/registry.rs
[M21]: ../DevelopmentReferences/microduck/btd/src/route.rs
[M22]: ../DevelopmentReferences/microduck/pet-detect/src/worker.rs
[M24]: ../DevelopmentReferences/microduck/robotd/src/main.rs
[M25]: ../DevelopmentReferences/microduck/duck-control/src/policy.rs
[R1]: ../DevelopmentReferences/reachy_mini/README.md
[R2]: ../DevelopmentReferences/reachy_mini/AGENTS.md
[R3]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/reachy_mini.py
[R4]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/daemon/backend/abstract.py
[R5]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/motion/head_wobbler.py
[R6]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/media/media_server.py
[R7]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/vision/face_tracking.py
[R8]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/vision/look_at.py
[R9]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/daemon/backend/robot/backend.py
[R10]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/apps/app.py
[R11]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/apps/manager.py
[R12]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/daemon/robot_app_lock.py
[R13]: ../DevelopmentReferences/reachy_mini/ts/lib/reachy-mini.ts
[R14]: ../DevelopmentReferences/reachy_mini/ts/host/src/lib/protocol.ts
[R15]: ../DevelopmentReferences/reachy_mini/ts/lib/session-supervisor.ts
[R16]: ../DevelopmentReferences/reachy_mini/ts/lib/pending-replies.ts
[R17]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/daemon/daemon.py
[R18]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/daemon/backend/mockup_sim/backend.py
[R19]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/io/protocol.py
[R20]: ../DevelopmentReferences/reachy_mini/skills/interaction-patterns.md
[R21]: ../DevelopmentReferences/reachy_mini/skills/motion-philosophy.md
[R22]: ../DevelopmentReferences/reachy_mini/examples/sound_tts.py
[R23]: ../DevelopmentReferences/reachy_mini/tests/unit_tests/test_media_server_aec.py
[R24]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/apps/fork_conversation.py
[R25]: ../DevelopmentReferences/reachy_mini/skills/ai-integration.md
[R26]: ../DevelopmentReferences/reachy_mini/tests/unit_tests/test_backend_idle_reset.py
[R27]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/daemon/app/middleware.py
[R28]: ../DevelopmentReferences/reachy_mini/src/reachy_mini/apps/sources/local_common_venv.py

[N-voiceinput]: ../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/voice_input.py
[N-events]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/events.py
[N-serviceunit]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment/ninjarobot-agent.service.in
[N-onboard]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/onboarding.py
[N-cli]: ../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_cli.py
[N-wikilauncher]: ../scripts/wiki.py
