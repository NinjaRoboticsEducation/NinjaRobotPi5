# NinjaRobotPi5 Refinement confirmlist — 7 September 2026

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

| Done / ID | Refinement | Why it is not needed | Questions of the implementation | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| Confirmed F01 | Enforce safety state, bounded movement, cancellation, and output cleanup at every IDE movement entry point. | - | - | High | P0 |
| Confirmed F02 | Give emergency stop an interrupt path that cannot wait behind ordinary queued work. | - | - | High | P0 |
| Confirmed F03 | Apply one hardware-ownership contract to the service, interactive tools, and retained real-device commands. | - | - | Medium | P0 |
| Confirmed F04 | Validate all enabled device pins and consistently enforce disabled-device settings. | - | - | Medium | P0 |
| Confirmed F05 | Add an environment-aware setup doctor (a diagnostic tool) and consistent hardware/development installation profiles; repair Pi boot-text validation. | - | - | Medium | P0 |
| Confirmed F06 | Make backup complete, database-consistent, and restore fully validated before replacement, with recovery from partial failure. | - | - | High | P0 |
| Confirmed F07 | Correct MCP failure status, reviewed effect/retry declarations, minimal subprocess environment, bounded discovery, and schema refresh (keeping expected tool arguments current). | - | - | High | P0 |
| Confirmed F08 | Add missing lifecycle/failure tests and enforce explicit opt-in hardware tests; close the audited face-backend cleanup gap. | - | - | High | P1 |
| Confirmed F09 | Report capability-level health with reason, freshness, dependency, and recovery steps. | - | - | Medium | P1 |

### 5.2 Human-robot interaction and conversation

| Done / ID | Refinement | Why it is not needed | Questions of the implementation | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| [X] H01 | Extend current presentation into consistent listening, thinking, approval, acting, done, interrupted, and error states across display and web. | No need to extend current presntation accross display, only show it in the system log | - | Medium | P1 |
| Confirmed H02 | Add optional TTS — text-to-speech, turning an answer into spoken audio — through an approved IDE audio output. | - | Does this feature work simply by connecting to the speaker via Bluetooth, or does it require an additional speaker driver? | High | P1 |
| [X] H03 | Add spoken interruption handling, microphone/playback coordination, and echo control after H02. | Due to hardware performance limitations, real-time voice input is neither feasible nor practical. | - | Very High | P1 |
| Confirmed H04 | Make clarification brief and specific; confirm exact consequential actions and explain what remains uncertain. | - | - | Medium | P1 |
| [X] H05 | Add a desktop profile, quiet hours, adjustable expression intensity, speech rate, and a visible microphone state. | - | - | Medium | P1 |
| Confirmed H06 | Verify multilingual display assets, readable text, captions, keyboard control, and non-color-only status cues. | - | - | Medium | P1 |
| Confirmed H07 | Add a short guided onboarding experience with capability checks and optional practice interactions. | - | How will this onboarding guide be implemented? Is this a extra onboarding CLI tool? | Medium | P2 |

### 5.3 Agentic tasks and everyday usefulness

| Done / ID | Refinement | Why it is not needed | Questions of the implementation | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| Confirmed T01 | Add a durable task record with plan, current step, owner, approvals, result evidence, and recovery state. | - | - | High | P1 |
| Confirmed T02 | Add local timers and reminders with exact due times, repeat rules, snooze, cancellation, and restart recovery. | - | - | High | P1 |
| Confirmed T03 | Add task progress, cancellation, outcome summaries, and checks that distinguish queued, completed, failed, and uncertain actions. | - | - | High | P1 |
| Confirmed T04 | Add schedule planning using authorized calendar reads; introduce calendar writes later with explicit account, scope, preview, and outcome verification. | - | Can I set alarm by prompting the robot "call me up at 4 pm today" after implementation? | High | P1 |
| Confirmed T05 | Make web research a complete workflow: approved search, dated citations, comparison, private note saving, and partial-result reporting. | - | - | Medium | P1 |
| Confirmed T06 | Add simple notes, checklists, and a daily briefing assembled from permitted local tasks and connected sources. | - | - | Medium | P2 |
| Confirmed T07 | Add bounded replanning and recovery policies with time, tool-call, and spending limits. | - | - | High | P1 |
| [X] T08 | Add opt-in proactive suggestions with quiet hours, frequency limits, relevance checks, and easy dismissal. | Now need for these function for now | - | Medium | P2 |

### 5.4 Memory, personalization, and improvement

| Done / ID | Refinement | Why it is not needed | Questions of the implementation | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| Confirmed M01 | Extend memory management to show why an item was saved, its source, confidence, last confirmation, and edit/delete controls. | - | - | Medium | P1 |
| Confirmed M02 | Distinguish confirmed preferences, temporary context, task outcomes, and unconfirmed suggestions; handle contradictory preferences explicitly. | - | - | Medium | P1 |
| Confirmed  M03 | Improve retrieval within the current store before considering semantic search — search by meaning rather than exact words. | - | - | Medium | P2 |
| Confirmed  M04 | Turn repeated successful workflows into reviewable task recipes, with user feedback, version history, and rollback (restoring a previous version). | - | - | High | P2 |
| [X] M05 | Strengthen active-user selection, guest behavior, export, retention, and deletion verification for new task data. | No need for now | - | High | P1 |

### 5.5 Expressions and sensing

| Done / ID | Refinement | Why it is not needed | Questions of the implementation | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| Confirmed B01 | Coordinate face, buzzer, and future speech on one IDE-owned timeline with interruption and priority rules. | - | - | High | P1 |
| Confirmed B02 | Add small bounded variations to existing safe expressions and sound cues, with stable personality settings. | - | - | Medium | P2 |
| [X] B03 | Introduce an opt-in attention experience using camera observations and animated eyes, with freshness limits and consent. | - | - | High | P2 |
| Confirmed B04 | Offer a distance-controlled sound/display game as an explicit mode, using the existing single-range sensor. | - | How could this sound/display game be actived? Can the user prompt the robot something like "Lets play a game" to activate this distance-controlled game? And how does this game play? Ex: put hand in front of the sensor and robot will do some fun reaction according to the distance.  | Low | P3 |
| Confirmed B05 | Treat future speakers, touch controls, movable heads, and desk-edge sensors as separate evaluated hardware options. | - | - | Very High | P3 |

H02 can select a modest approved speaker before the broader optional hardware work
in B05. B05 does not delay the initial software-only assistant or require a new head.

### 5.6 Extensibility and development quality

| Done / ID | Refinement | Why it is not needed | Questions of the implementation | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| Confirmed X01 | Extend existing Agent skill packages with clear capability, permission, version, and test requirements; add focused application templates. | - | - | Medium | P2 |
| [X] X02 | Improve release identity, installation checks, staged updates, and rollback evidence before considering automatic updates. | - | - | High | P2 |
| Confirmed X03 | Keep this plan, feature specifications, manuals, wiki pages, and validation evidence synchronized during every approved phase. | - | - | Low | P1 |
| [X] X04 | Build repeatable simulated user journeys, fault scenarios, and consent-aware Pi validation records. | - | - | Medium | P1 |
| Confirmed X05 | Add an optional runtime project-help tool over selected public wiki content, through the existing read-only tool boundary. | - | Can users prompt the bot through a conversation and ask questions about the NinjaRobotPi5 project to retrieve relevant information from ninjarobot_pi5_wiki? | Medium | P2 |

---

## Review answers and plan alignment — 7 September 2026

The original decisions and questions above are preserved. This section records the
review; it does not mark any feature as implemented. The updated
[implementation plan](NinjarobotPi5_RefinementPlan_260907.md) is the main development
reference. Its [scope register](NinjarobotPi5_RefinementPlan_260907.md#0-owner-decisions-and-scope)
and [revised phases](NinjarobotPi5_RefinementPlan_260907.md#7-development-phases-and-acceptance-gates)
carry these decisions forward.

### How the decisions were applied

- **31 confirmed items** remain selected for development.
- **H01 is revised to system logs only.** Existing display/web presentation remains;
  no additional lifecycle faces, badges or panels are planned. Explicit task progress
  under T03 and existing-expression coordination under B01 remain selected.
- **Seven items are deferred:** H03, H05, T08, M05, B03, X02 and X04. They are excluded
  from active phases, not marked completed.
- H02 is listen-then-speak output. Existing optional voice input remains; real-time
  interruption and simultaneous speaking/listening are not added.
- Existing permissions, user-data boundaries and required tests remain in force.
  Deferring M05 and X04 does not remove them or create separate replacement projects.
- T06 briefings and M04 recipe reviews are user-requested. No unsolicited T08 prompts
  are added. F05/F06 setup and backup repairs remain; the X02 updater project does not.
- B05 remains hardware evaluation, with actual devices/designs reviewed separately.
- H01's estimate changes from Medium to **Low** for its narrower scope. B04 changes
  from Low to **Medium** because conversation activation, resource ownership,
  cancellation and cleanup are part of a complete game. Priorities are unchanged.

`Confirmed` means scope selected. `[X]` in the original list means deferred/rejected
for this stage, not implementation complete. All selected work remains unimplemented
by this documentation revision.

### Answer 1 — H02: Bluetooth speaker and driver requirements

A compatible Bluetooth speaker can use the operating system's existing audio support;
we normally do not need a custom Pi5 speaker driver. Connecting it is only the output
connection. NinjaRobotPi5 still needs a **text-to-speech generator** (turns text into
audio) and an **IDE playback adapter** (starts, stops and monitors audio output).

The plan checks the actual speaker and OS, and tests output from the deployed Agent
service. Success in a desktop music player does not prove that service audio access
is configured. Missing/disconnected output should preserve the text answer and report
speech unavailable. Listen-then-speak coordination preserves the existing voice-enable
setting. See [the speech design](NinjarobotPi5_RefinementPlan_260907.md#63-sequential-speech-output-including-bluetooth),
including its official audio documentation links.

### Answer 2 — H07: How the onboarding guide is implemented

Extend the **existing Agent interactive menu and web controller**, using F05's shared
diagnostic results. A separate onboarding executable is unnecessary. Preserve the
current pairing/startup coordinator.

The optional guide explains configuration and available features, stop/resume controls,
a sample text question, and a practice reminder. Speaker/media/device tests remain
explicit choices. Users can skip steps and return later without overwriting settings.
The current deployment setup command installs/enables startup, so it must not become
the guide's harmless “start tour” action. See [H07 details](NinjarobotPi5_RefinementPlan_260907.md#h07--will-onboarding-be-a-separate-command-line-tool).

### Answer 3 — T04: “Call me up at 4 pm today”

**Yes, after the local reminder feature is implemented.** This request primarily
uses T02, supported by T01 task storage and H04 clarification. It does not require
a connected calendar. T04 is needed only for an external calendar event.

The robot saves an alarm and confirms its full date, time and local time zone.
If today's 4 pm has already passed, it asks for another time. It explains that the
alarm sounds on this robot; it does not make a telephone call. The existing buzzer
can deliver it, and H02 enables a spoken reminder on the selected speaker.

The Pi must be powered on and the Agent running when delivery is due. Saved alarms
survive a restart, with missed or uncertain deliveries handled explicitly. Snooze,
dismiss and cancellation are part of the task controls. See [alarm details](NinjarobotPi5_RefinementPlan_260907.md#t04--can-i-say-call-me-up-at-4-pm-today).

### Answer 4 — B04: Starting and playing the distance game

**Yes.** “Let's play the distance game” selects it directly. “Let's play a game”
can offer it or ask which game when multiple games are installed.

For a short, explicitly started session, move a hand closer to or farther from the
distance sensor. Nearer can produce a higher buzzer note, farther a lower note,
with an existing face or simple graphic changing alongside it. Optional prompts
can ask the user to find a near/middle/far band. Exact distances and sound limits
must be validated against the hardware.

The game uses no wheel commands or camera capture. Invalid/stale readings silence
its output; session timeout, cancellation and system stop clean up its resources.
Current safety/privacy indications take priority. See [game details](NinjarobotPi5_RefinementPlan_260907.md#b04--can-lets-play-a-game-start-the-distance-game-and-how-is-it-played).

### Answer 5 — X05: Asking project questions in robot conversation

**Yes, after X05 is implemented.** Users can ask about project features, setup,
architecture or documented troubleshooting through typed conversation or the current
optional voice-input route.

The Agent calls a restricted read-only wiki tool and answers from relevant pages
and cited current manuals. It includes source/version information and distinguishes
draft or planned features from implemented behavior. Live hardware status requires
the existing health tool as well; documents alone cannot inspect a device.

The runtime tool exposes only bounded search/read operations, never wiki maintenance,
installation, arbitrary file access or command execution. Missing evidence produces
an honest limitation. The separate wiki environment remains separate from robot
packages. See [runtime project-help details](NinjarobotPi5_RefinementPlan_260907.md#x05--can-i-ask-the-running-robot-questions-about-ninjarobotpi5).

### Result of this review

The plan now records each original decision, answers all five questions, maps the
selected work to phases, and keeps deferred features out of the active acceptance
criteria. The competitor audit remains available as reference evidence. Only
planning documents are changed; no robot code, dependencies, devices, services,
user configuration or wiki source records are modified.
