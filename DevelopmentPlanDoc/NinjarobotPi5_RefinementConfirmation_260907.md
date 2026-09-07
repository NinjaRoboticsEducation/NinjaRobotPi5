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