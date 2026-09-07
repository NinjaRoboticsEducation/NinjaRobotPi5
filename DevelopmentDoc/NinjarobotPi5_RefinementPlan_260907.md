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

**Status:** proposed development reference, prepared from source inspection on
7 September 2026. Implementation phases require the project owner's approval.
This document is the main planning reference for the next stage. Current behavior
remains documented in the [local knowledge base][N-wiki] and verified against code.

## Contents

- [1. Goals and the experience we want](#1-goals-and-the-experience-we-want)
- [2. Evidence and current project status](#2-evidence-and-current-project-status)
- [3. What to learn from the references](#3-what-to-learn-from-the-references)
- [4. Keep the existing framework](#4-keep-the-existing-framework)
- [5. Refinement checklist](#5-refinement-checklist)
- [6. How the important features should work](#6-how-the-important-features-should-work)
- [7. Development phases and acceptance gates](#7-development-phases-and-acceptance-gates)
- [8. Validation and measures of success](#8-validation-and-measures-of-success)
- [9. Documentation and future decisions](#9-documentation-and-future-decisions)
- [Appendix A. Complete Microduck audit](#appendix-a-complete-microduck-audit)
- [Appendix B. Complete Reachy Mini audit](#appendix-b-complete-reachy-mini-audit)
- [Appendix C. Feature comparison matrix](#appendix-c-feature-comparison-matrix)
- [Appendix D. Evidence directory and audit limitations](#appendix-d-evidence-directory-and-audit-limitations)

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
   interaction requires an output device, playback ownership, and interruption handling.
4. Stored preferences and history need to become transparent, correctable help,
   without turning guesses into permanent facts about the user.
5. Installation and health reporting should distinguish a missing software
   package from an unavailable device, a disabled feature, and a safety stop.
6. Expressions, reminders, tools, and recovery need to tell one consistent story
   across chat, the display, and the web controller.

### 1.2 What success should feel like

These are future acceptance examples, not claims about today's robot:

| Everyday situation | Desired experience |
| --- | --- |
| “Remind me to stretch in 25 minutes.” | The robot displays the exact due time, saves the reminder, and delivers it once while the service is running. A restart preserves it; downtime is explained. |
| “Help me plan tomorrow morning.” | The robot asks only for missing essentials, uses an authorized calendar connection if present, proposes a realistic schedule, and distinguishes a suggestion from a saved calendar event. |
| “Find three useful articles and save the important points.” | It searches through an approved tool, shows sources and dates, saves a private note, and explains any incomplete part. |
| “Please be quieter while I work.” | It proposes or applies the permitted preference change, explains its scope, and offers an easy way to reverse it. |
| The internet disconnects during a task. | It explains what has already happened, keeps local functions usable where safe, and does not repeat an uncertain external action. |
| The user interrupts a long answer. | Speech stops promptly. The screen shows that the robot is listening. Stopping an answer and cancelling a task remain understandable, separate choices. |
| A hardware package is missing. | A health screen names the package and the active Python environment, gives the correct repair instructions, and keeps movement stopped. |

### 1.3 Design principles

- **Useful before impressive.** Reliable timers, notes, and schedule assistance
  matter more than a large number of gestures.
- **Make state visible.** Listening, thinking, waiting for permission, acting,
  completing, and failing should look and read differently.
- **Keep the user in control.** Quiet hours, memory inspection, cancellation,
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
| A11: installer inputs are not fully reproducible | Retain as an installation review item; examine each remaining downloaded input before pinning it. | F05, X02 |
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

This is an extension of the current architecture, not a replacement. A new audio
device adapter is an additive hardware integration requiring approval. A new
deployment layout or any managed-driver repair is also separately reviewable.
Neither is a reason to introduce another robot runtime.

### 4.3 Define a desktop operating profile

Propose an opt-in **desktop assistant profile** that keeps wheel movement disabled
while allowing permitted conversation, display, buzzer, notes, and reminders.
Preserve the existing operating profile for users who intentionally drive the robot.

The forward distance sensor does not establish that the edge of a desk is safe.
NinjaRobotPi5's continuous-rotation servos also do not provide the physical feedback
needed to copy Reachy's pushable antennas or hand-guided head. Express attention
with animated eyes first. Any future physical head, touch input, speaker, wheel
feedback, or desk-edge sensor is a separately approved hardware project.

## 5. Refinement checklist

Each row is independently reviewable. All boxes begin unchecked. Dependencies and
acceptance gates follow in sections 6–8.

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
| [ ] F01 | Enforce safety state, bounded movement, cancellation, and output cleanup at every IDE movement entry point. | A guarded behavior is insufficient if another public command bypasses it; A01 remains relevant. | Stop means stop regardless of how movement was requested. | High | P0 |
| [ ] F02 | Give emergency stop an interrupt path that cannot wait behind ordinary queued work. | A full or blocked queue must not delay the command intended to stop it; A02. | Predictable stopping during slow tools or long behaviors. | High | P0 |
| [ ] F03 | Apply one hardware-ownership contract to the service, interactive tools, and retained real-device commands. | Two clients must not compete for the same device; A03. | Clear “robot already in use” feedback instead of conflicting actions. | Medium | P0 |
| [ ] F04 | Validate all enabled device pins and consistently enforce disabled-device settings. | A04/A05 can make configuration misleading or electrically conflicting. | A disabled feature stays disabled; wiring errors are explained before startup. | Medium | P0 |
| [ ] F05 | Add an environment-aware setup doctor (a diagnostic tool) and consistent hardware/development installation profiles; repair Pi boot-text validation. | Missing optional packages can resemble failed hardware; A09/A11 and the recent installation incident. | One diagnosis identifies the active environment, missing dependencies, and the appropriate repair. | Medium | P0 |
| [ ] F06 | Make backup complete, database-consistent, and restore fully validated before replacement, with recovery from partial failure. | A06 becomes more serious when schedules and personal notes are important. | An upgrade or recovery preserves the user's information. | High | P0 |
| [ ] F07 | Correct MCP failure status, reviewed effect/retry declarations, minimal subprocess environment, bounded discovery, and schema refresh (keeping expected tool arguments current). | A07/A08 can create false success and expose unrelated credentials. | Honest tool results and clearer limits on external access. | High | P0 |
| [ ] F08 | Add missing lifecycle/failure tests and enforce explicit opt-in hardware tests; close the audited face-backend cleanup gap. | Existing passing tests do not cover all ownership or failure cases. | Repeated use and updates are less likely to leave devices stuck. | High | P1 |
| [ ] F09 | Report capability-level health with reason, freshness, dependency, and recovery steps. | A single ready/not-ready answer conceals what is still usable. | Users can continue safe text tasks while understanding why a device is unavailable. | Medium | P1 |

### 5.2 Human-robot interaction and conversation

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] H01 | Extend current presentation into consistent listening, thinking, approval, acting, done, interrupted, and error states across display and web. | Expressions currently cover only part of the task lifecycle. | Users understand what the robot is doing without reading logs. | Medium | P1 |
| [ ] H02 | Add optional TTS — text-to-speech, turning an answer into spoken audio — through an approved IDE audio output. | Voice input alone does not provide two-way speech. | Users hear concise replies and reminders, with text as a fallback. | High | P1 |
| [ ] H03 | Add spoken interruption handling, microphone/playback coordination, and echo control after H02. | The robot must not transcribe its own answer or keep speaking over the user. | More natural turn-taking and immediate control of long answers. | Very High | P1 |
| [ ] H04 | Make clarification brief and specific; confirm exact consequential actions and explain what remains uncertain. | Fluent guesses about time, identity, or external actions damage trust. | Fewer wrong reminders and clearer permission requests. | Medium | P1 |
| [ ] H05 | Add a desktop profile, quiet hours, adjustable expression intensity, speech rate, and a visible microphone state. | A robot that is entertaining briefly may become distracting during work. | The assistant fits the user's environment and attention needs. | Medium | P1 |
| [ ] H06 | Verify multilingual display assets, readable text, captions, keyboard control, and non-color-only status cues. | Browser translations alone do not ensure usable robot display text; A15. | More people can understand and control the robot comfortably. | Medium | P1 |
| [ ] H07 | Add a short guided onboarding experience with capability checks and optional practice interactions. | Users should not have to discover missing hardware through a failed conversation. | Faster setup and a realistic understanding of available functions. | Medium | P2 |

### 5.3 Agentic tasks and everyday usefulness

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] T01 | Add a durable task record with plan, current step, owner, approvals, result evidence, and recovery state. | A bounded chat loop is not a restart-safe task manager. | Users can ask “What happened to my request?” and get a dependable answer. | High | P1 |
| [ ] T02 | Add local timers and reminders with exact due times, repeat rules, snooze, cancellation, and restart recovery. | This is a high-value everyday feature missing from the core task model. | Useful reminders continue without a cloud model once saved. | High | P1 |
| [ ] T03 | Add task progress, cancellation, outcome summaries, and checks that distinguish queued, completed, failed, and uncertain actions. | Tool acceptance is not proof that the user's goal was met. | Less waiting without explanation and fewer misleading “done” messages. | High | P1 |
| [ ] T04 | Add schedule planning using authorized calendar reads; introduce calendar writes later with explicit account, scope, preview, and outcome verification. | Calendar examples exist, but reliable writes need a stronger contract. | Users can plan their day and intentionally save approved changes. | High | P1 |
| [ ] T05 | Make web research a complete workflow: approved search, dated citations, comparison, private note saving, and partial-result reporting. | A search result alone is not a finished information-management task. | Users receive useful, traceable answers they can find again. | Medium | P1 |
| [ ] T06 | Add simple notes, checklists, and a daily briefing assembled from permitted local tasks and connected sources. | Common assistant tasks should not need a new integration each time. | One place to review priorities and remembered information. | Medium | P2 |
| [ ] T07 | Add bounded replanning and recovery policies with time, tool-call, and spending limits. | Retrying everything can duplicate actions or loop indefinitely. | The robot can recover from ordinary failures and knows when to ask for help. | High | P1 |
| [ ] T08 | Add opt-in proactive suggestions with quiet hours, frequency limits, relevance checks, and easy dismissal. | Proactivity is useful only when it respects attention and consent. | Helpful prompts that do not become persistent interruptions. | Medium | P2 |

### 5.4 Memory, personalization, and improvement

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] M01 | Extend memory management to show why an item was saved, its source, confidence, last confirmation, and edit/delete controls. | Existing memory needs understandable provenance — where a claim came from. | Users can correct the assistant instead of repeatedly fighting a wrong assumption. | Medium | P1 |
| [ ] M02 | Distinguish confirmed preferences, temporary context, task outcomes, and unconfirmed suggestions; handle contradictory preferences explicitly. | Different kinds of information should not all become lasting facts. | More accurate personalization and fewer surprising assumptions. | Medium | P1 |
| [ ] M03 | Improve retrieval within the current store before considering semantic search — search by meaning rather than exact words. | Relevant context helps; sending all history wastes resources and exposes excess information. | Better continuity across conversations with controlled data use. | Medium | P2 |
| [ ] M04 | Turn repeated successful workflows into reviewable task recipes, with user feedback, version history, and rollback (restoring a previous version). | “Learning” should improve practical behavior while staying inspectable. | The assistant learns preferred ways to help without rewriting its safety rules. | High | P2 |
| [ ] M05 | Strengthen active-user selection, guest behavior, export, retention, and deletion verification for new task data. | Face similarity is not authentication, and shared rooms contain multiple people. | Private information is less likely to be shown or attributed to the wrong user. | High | P1 |

### 5.5 Expressions and sensing

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] B01 | Coordinate face, buzzer, and future speech on one IDE-owned timeline with interruption and priority rules. | Separate reactions can conflict or appear late. | A coherent robot response that matches the answer or task. | High | P1 |
| [ ] B02 | Add small bounded variations to existing safe expressions and sound cues, with stable personality settings. | Repetition feels mechanical, while uncontrolled randomness feels unreliable. | A recognizable character that remains calm and predictable. | Medium | P2 |
| [ ] B03 | Introduce an opt-in attention experience using camera observations and animated eyes, with freshness limits and consent. | Reacting to the person can make interaction easier, but stale detections can mislead. | The robot visibly attends to the interaction without moving its wheels. | High | P2 |
| [ ] B04 | Offer a distance-controlled sound/display game as an explicit mode, using the existing single-range sensor. | Microduck shows the educational value of a simple sensor-to-feedback loop. | A tangible, beginner-friendly robotics activity. | Low | P3 |
| [ ] B05 | Treat future speakers, touch controls, movable heads, and desk-edge sensors as separate evaluated hardware options. | Competitor interactions depend on hardware NinjaRobotPi5 does not currently have. | Hardware additions solve a clear need and do not destabilize existing drivers. | Very High | P3 |

H02 can select a modest approved speaker before the broader optional hardware work
in B05. B05 does not delay the initial software-only assistant or require a new head.

### 5.6 Extensibility and development quality

| Done / ID | Refinement | Why it is needed | Expected user benefit | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [ ] X01 | Extend existing Agent skill packages with clear capability, permission, version, and test requirements; add focused application templates. | New functions should reuse the registry and policy rather than invent another execution route. | Consistent add-ons that are easier to install, understand, and disable. | Medium | P2 |
| [ ] X02 | Improve release identity, installation checks, staged updates, and rollback evidence before considering automatic updates. | Microduck shows the value of diagnosing installed versus actually running software. | Users can recover from an upgrade without guessing which version is active. | High | P2 |
| [ ] X03 | Keep this plan, feature specifications, manuals, wiki pages, and validation evidence synchronized during every approved phase. | A knowledge base helps only when it describes the current implementation honestly. | All coding tools work from the same accurate context. | Low | P1 |
| [ ] X04 | Build repeatable simulated user journeys, fault scenarios, and consent-aware Pi validation records. | Module tests alone do not establish a good assistant experience. | Improvements are measured against real user tasks before release. | Medium | P1 |
| [ ] X05 | Add an optional runtime project-help tool over selected public wiki content, through the existing read-only tool boundary. | Developer wiki access is not automatically available to the running robot. | Users can ask the robot about supported functions and setup, with cited evidence. | Medium | P2 |

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

### 6.3 Speech with understandable interruption

First establish an approved output device and its health checks. The buzzer can
signal an event but cannot provide normal spoken answers. Keep speech optional;
text, existing buzzer functions, and current voice input remain supported.

Start with a simple listen-then-speak flow. Use short spoken answers, synchronized
captions, volume limits, and a visible mute control. Audio synthesis can run in a
bounded worker or provider, but playback ownership belongs to the IDE.

Then add full-duplex interaction — listening and speaking at the same time — only
after measuring AEC, acoustic echo cancellation, which reduces the robot hearing
its own speaker. VAD, voice activity detection, estimates when someone is speaking.
Both need testing with the actual microphone, speaker placement, and room noise.
If these checks fail, retain the simpler turn-taking mode.

Use separate, clear controls for “stop speaking,” “cancel this task,” and
“emergency stop.” The last must not depend on speech recognition or model inference.
Cancel queued speech as well as the currently playing sound, and invalidate stale
expression callbacks so an interrupted answer cannot later resume its animation.

Evaluate local versus cloud speech using latency (response delay), supported languages, privacy,
installation size, processor load, and cost. This plan deliberately does not select
a model or service from a competitor's old example.

### 6.4 Expressions should communicate real state

Extend the existing presentation controller rather than build another personality
engine. A small vocabulary is enough: ready, listening, thinking, waiting for the
user, acting, successful, interrupted, and unavailable.

The IDE should resolve conflicts in an explicit order: safety and required privacy
indicators first, then the active user interaction or approved notification, then
optional ambient expression. Foreground behavior ownership and quiet hours must
also be respected. An idle animation must never overwrite a stop indication.

Use a shared playback clock for future speech and face animation, borrowing
Reachy's timing idea. Use a monotonic clock — a clock that does not jump when the
wall clock is corrected — for animation duration and timeouts. Use calendar time
for reminder dates. These are different jobs.

Borrow Microduck's stable variation: a small set of timing or sound choices
selected within known limits. Let the user select calmer behavior. Do not let a
fictional mood increase tool authority, movement speed, spending, or data retention.

### 6.5 Memory that improves through interaction

Build on the existing memory store. Record the source of a preference and whether
the user confirmed it. “I am tired today” should ordinarily stay temporary;
“Please use shorter answers from now on” can become a lasting preference.

Allow the user to ask “What do you remember about me?”, correct an item, remove
it, or reset a category. Define deletion across search indexes, task summaries,
exports, and retained backups; do not imply that deleting a live row erases every
older backup automatically.

Track useful feedback such as accepted schedules, corrected names, or repeated
task recipes. Suggest a recipe after repeated success; show what it will do and
obtain the relevant approval before making it a reusable automation. Keep version
history so a bad adaptation can be reversed.

Do not train models online, automatically install tools, change permissions,
rewrite source code, or store speculative psychological profiles. These are not
required to make the assistant noticeably more helpful.

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

## 7. Development phases and acceptance gates

Each phase should become a smaller implementation proposal with exact changes,
tests, and documentation impact. Approval of this planning document does not
approve all hardware, dependency, or account changes listed here.

In this table, Agent filenames are under `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/`;
IDE filenames are under `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/`. New filenames
are suggestions to keep responsibilities focused, not existing modules.

| Phase | Objective and likely files | Compatibility contract | Validation gate | Documentation and risk |
| --- | --- | --- | --- | --- |
| 0 — Establish the release baseline | F01–F08: IDE `engine.py`, `scheduler.py`, `integrated.py`, `robot.py`, `servo.py`, `config.py`, identity ownership; Agent `cli.py`, `mcp_client.py`, `mcp_config.py`, `deployment.py`; setup scripts and tests. Split into small repair patches. | Keep public names and data; repair unsafe or misleading execution. Any managed-driver edit receives separate authorization. | Reproduce relevant audit failures with fakes, repair them, run the required root gate and relevant independent driver suites. | Update current manuals and audit disposition. High movement/data/boot relevance; automated work remains hardware-free. |
| 1 — Make the existing robot understandable | F09, H01, H04–H06, X04: Agent `presentation.py`, `events.py`, `web_app.py`, `web_static/`, onboarding; IDE health and display paths. | Preserve current operation; desktop profile is opt-in; fallback states do not bypass stop conditions. | Simulated missing dependencies, disabled devices, mixed health, crowded queues, and interrupted interactions show accurate status. | Update feature and operating guidance; document font approval if needed. Low for interface work, higher for approved device repairs. |
| 2 — Deliver the first useful assistant | T01–T03, initial T05, T07, M01/M02/M05: Agent proposed `task_service.py`, `reminders.py`, `task_models.py`, existing migrations/store/runtime/tools; web task view. | Additive database migration; existing conversations and skills still work. Initial reminders use available permitted outputs. | Synthetic-clock reminder tests, restart/duplicate-delivery cases, task cancellation, truthful outcomes, user isolation and backup restore. | Add task/reminder specification, missed-delivery rules, retention and recovery instructions. Personal-data relevance; no unapproved media or motion. |
| 3 — Add spoken interaction | H02/H03 and B01: Agent voice/presentation/provider interfaces; proposed IDE audio adapter and current behavior coordination. | Speech optional; existing input and text remain usable. New audio hardware/dependencies explicitly selected and approved. | Fake audio first; then consented microphone/speaker tests, self-echo, interruption, playback failure, and processor-load checks. | Document hardware, privacy, language/cost choices and fallback. Audio/media risk. |
| 4 — Complete connected assistance | T04–T08, M03/M04, X01/X05: reviewed Agent tool providers, skill manifests, task evidence, memory retrieval and project-help adapter. | Existing read-only MCP contract remains intact; writes use separately reviewed permissions. | Fake accounts and failure injection; read-after-write checks; source injection tests; permission expiry; recipe rollback. | Update MCP tutorial, memory guidance, wiki feature pages and service notices. Account/network/privacy risk. |
| 5 — Polish and expand selectively | B02–B05, H07, X02: bounded expression assets, optional perception, installation/release tooling, education examples. | No unsolicited wheel motion or replacement architecture. Hardware additions separately scoped. | Usability sessions, idle-load/thermal checks, compatibility tests, staged-update recovery using temporary releases. | Document supported hardware and measured limits. Risk depends on the approved option; motion/power work remains manual. |

The smallest useful milestone is **phases 0–2**: a healthy installation, understandable
interaction, and dependable local reminders/tasks. It can deliver value before
voice streaming, camera attention, or new physical hardware.

Dependencies: T01 precedes durable T02/T03; F06 precedes reliance on expanded stored
data; F07 precedes T04 writes and wider external tools; H02 precedes H03; F01–F04
precede expanded physical autonomy. Quiet interaction and interface design can be
developed with simulated devices while foundation repairs are reviewed.

## 8. Validation and measures of success

### 8.1 Checks performed for this planning document

This task used read-only inspection and documentation editing. The following
checks passed during the audit:

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

### 8.3 Proposed product acceptance measures

These are initial targets for owner review, not measurements of current performance.
Record the Pi model, installed components, software commit, provider, room conditions,
and test procedure with every result.

| Measure | Proposed acceptance target or required observation |
| --- | --- |
| Visible acknowledgement | Local display/web acknowledgement within 250 milliseconds for at least 95% of accepted inputs under the documented normal load. |
| Stop priority | Demonstrate that emergency-stop dispatch never waits for an ordinary action slot. Set and validate a physical stopping deadline before approving live movement; software timing alone is insufficient. |
| Reminder reliability | All deterministic restart, clock-change, recurrence, cancellation, and duplicate-claim tests pass; online delivery target within two seconds under documented load. Downtime/uncertain-delivery cases are explicitly reported. |
| Task honesty | No test reports completion without a successful terminal result and the required outcome evidence. |
| Speech interruption | Initial playback-stop target below 300 milliseconds for 95% of trials after local interruption detection; measure detection delay separately. |
| Privacy | All denied media/account actions remain unexecuted; zero cross-user retrieval in the controlled test set. |
| Recovery | Missing optional provider/device tests leave unrelated permitted capabilities usable, with accurate reasons; safety-critical dependency failures still block affected actions. |
| Personalization | Corrections take effect on the next applicable interaction; deleted live memories disappear from retrieval, with backup limitations clearly stated. |
| Everyday task success | At least 90% completion on an agreed set of 20 representative bounded tasks before expanding the early user group; report failures by cause, not only a total score. |
| Resource use | Compare idle and active processor, memory, temperature and response time with the baseline. Set budgets from Pi measurements; avoid unmeasured “always-on vision” promises. |
| User experience | Observe beginners creating, inspecting, changing and cancelling reminders without coaching; record confusion and unwanted interruptions. |

Cloud reply speed should be reported separately from local acknowledgement. A fast
animation must not hide a stalled task. Likewise, a command delivered to a wheel
driver does not prove a specific distance travelled without suitable feedback.

### 8.4 Separate manual validation lists

These are future validation steps. They were not performed for this document.

| Level | Operator checklist | Expected result | Stop or rollback |
| --- | --- | --- | --- |
| Safe smoke — no hardware | Run the software doctor, simulated chat/task journeys, fake reminders, and wiki checks. | Accurate capabilities, persistence and errors without opening devices. | Stop the simulated service and preserve diagnostic evidence; revert only the reviewed change. |
| Device communication | On the approved Pi setup, inspect device readiness and test display/buzzer deliberately; obtain consent before microphone or camera capture. | Configured devices are recognized and owned once; capture state is visible; temporary media is removed. | Stop the session, release devices, restore the previous approved configuration/environment. |
| Actuator movement | Only after safety gates pass, raise wheels, clear the area, and keep an operator ready to remove power. Exercise each approved movement route and stop/recovery case. | Bounded movement, prompt stop, no automatic replay after resume, no movement in desktop mode. | Remove actuator power if necessary, stop the service, preserve the fault latch and investigate before resuming. |
| Power and deployment | Separately approve any reboot, boot-file, service, update rollback, or shutdown test; first validate command construction with fakes and verify backups. | Approved service recovery and preservation of configuration/data; no unexpected boot motion. | Use the documented manual recovery route and last known-good release/backup. Never test destructive power paths automatically. |

## 9. Documentation and future decisions

### 9.1 Keep plans, facts, and private memory separate

This document belongs in the requested `DevelopmentDoc/` path as an active proposal.
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

| Decision | Recommended starting assumption | When an explicit decision is needed |
| --- | --- | --- |
| Desk operation | Offer an opt-in stationary assistant profile. | Before changing any current default or enabling new autonomous movement. |
| Audio output | Choose a modest supported speaker/backend after checking the user's actual hardware. | Before dependencies, wiring, or sound-output implementation. |
| Speech processing | Compare local and cloud options with the target languages and Pi load. | Before selecting a service, model download, spending policy, or data flow. |
| Calendar access | Read-only planning first; writes separately approved. | Before storing account credentials or granting write scopes. |
| Memory and household users | Preserve existing ownership and retention; add explicit guest rules. | Before changing stored personal data, identity selection, or automatic capture. |
| Reminder downtime | Report missed delivery; do not imply operation while powered off. | Before choosing catch-up, repeat, escalation, or phone-notification behavior. |
| Update mechanism | Improve existing manual preview/health/rollback first. | Before automatic downloads, service replacement, or a new deployment layout. |

The recommended first implementation proposal is a small foundation repair batch
covering stop coverage, interrupt priority, ownership, and installation diagnosis.
Prepare the local task/reminder specification alongside it using simulated devices.

## Appendix A. Complete Microduck audit

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
limits, with quiet hours and intensity settings. Its buzzer cannot reproduce
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

**Adaptation:** F05/F06/X02 should improve Ninja's current installation and backup
path first: clear version identity, correct environment, staged validation,
complete recovery inventory, and simulated failure tests. Automatic updates can
wait until manual rollback is demonstrated.

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

**Adaptation:** start with consented, low-rate attention cues on Ninja's display,
with stale-observation expiry. Do not turn the whole wheeled robot to imitate a
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
design strengths and tradeoffs, not a measured product ranking.

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
