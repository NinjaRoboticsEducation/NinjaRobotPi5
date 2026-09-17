# NinjaRobotPi5 interface refinement implementation plan

Date: 18 September 2026. Status: proposed implementation, awaiting owner review.
This document is a plan, not a claim that the new interfaces are implemented.

## 1. Outcome and scope

Make the two terminal tools easier to navigate and divide the web controller into
a manual **Game Pad** view and a conversation-focused **Agent Interface**.
Keep the existing robot, Agent, device, and safety functions working as they do
now. UI means user interface; UX means the experience of using that interface.

The approved direction is an interface change. It does not authorize motor tests,
recording, power-off, service deployment, or changes to driver behavior. Development
should use simulated devices and mocked browser connections first.

The owner confirmed these design decisions during planning:

| Decision | Confirmed result |
| --- | --- |
| Languages | English, Japanese, Traditional Chinese, and Simplified Chinese on the web only. Both terminal tools stay English. |
| Clear Message | Clear visible conversation messages only; preserve saved history and memory. |
| Audio controls | Present existing Web Mic, Voice Input, and Spoken Replies functions as stateful controls. |
| Initial web view | Agent Interface on first use; remember the last selected interface in that browser. |
| Record Once and distance-game buttons | Remove these buttons. Retain access through existing commands or Agent requests. No replacement More tools panel. |
| Removed menu cards | Remove Connection and Local tasks cards, while retaining their underlying functions. |

The request refers once to “2 Run Robot Behaviors,” but the supplied new complete
menu places it at **3**. Use the new complete numbering. Emergency Stop is **4
inside Run Robot Behaviors**. The button-removal instruction applies to the IDE
terminal menus; both web views keep Emergency Stop and Resume as the mockups show.

## 2. Evidence and current implementation

The worktree was clean when this review started. Serena symbol inspection and
targeted source reads were used for Python; HTML, CSS, and JavaScript were inspected
directly because the active Serena language server covers Python.

### Design references

- [Hamburger menu](webinterface/HamburgMenu.jpg): dark rounded sheet, language
  selection, two large interface buttons, and orange power-off button.
- [Game Pad](webinterface/GamePadInterface.jpg): large direction cross; A Greetings,
  B Take Photo, X Emergency Stop, Y Resume Movement; saved-behavior selector and Play.
- [Agent Interface](webinterface/AgentInterface.jpg): tall conversation area,
  Clear Message, composer, three audio controls, and A/B/X/Y authorization/safety row.
- [System activity](webinterface/SystemLog.jpg): supplemental reference found in
  the same folder. Preserve the existing activity drawer and align its appearance;
  do not introduce a new logging feature.

These images are 720-pixel-wide design references, not fixed browser dimensions.
Preserve their hierarchy and proportions while adapting to actual screen sizes.

### Verified implementation findings

| Area | Existing implementation | Consequence for this plan |
| --- | --- | --- |
| IDE menus | `interactive_tool.py` adds E Emergency Stop by default and separately accepts `e` in many submenu handlers. | Remove both the displayed option and its input branches; changing labels alone is insufficient. |
| Hardware configuration | `_hardware_menu` first asks for Show Current Configuration, then prints settings. | Print that existing configuration payload immediately and return after Enter. Do not construct hardware. |
| Behavior creator | `_create_menu` contains an introductory Start Guided Creator screen before its actual prompts. | Enter the creator directly from the new grouped menu, without another redundant Start screen. |
| Agent terminal | `agent_cli._interactive` prints and dispatches option 15 Guided checks. | Remove that option and branch; preserve `/guide` and service support. |
| Web shell | One HTML document, one `app.js`, one stylesheet, one WebSocket connection. A WebSocket is the live browser-to-Agent message connection. | Use two views in that same application, not two independent controllers. |
| Saved web behavior execution | `WebRobotController.run_behavior` accepts only `greeting` and `celebrate`. | A selector cannot work through HTML alone; add a narrow presentation adapter to existing catalog/run functions. |
| Catalog | IDE `_BehaviorListAdapter` returns full definitions for built-in and user behaviors. `BehaviorAssetRepository.list_user()` already exists. | Provide an explicit user-only list rather than guessing ownership from names. |
| Clear view | The button already removes visible message elements only. | Preserve the existing meaning; adjust label and test streaming behavior. |
| Audio | Web Mic fills the composer; Voice Input controls the Pi wake-word listener; Speech ON/OFF controls reply playback. | Keep these three meanings distinct. Do not silently make Web Mic submit messages. |
| Translation | Four dictionaries and browser locale persistence already exist. Some newer labels, dynamic statuses, and error text are not fully localized. | Extend the existing translation system rather than add another framework. |
| Layout | A combined dashboard and several fixed/minimum size rules serve both controls and chat. | Introduce view-specific layout rules; avoid merely hiding half of the old grid. |
| Existing tests | `test_web.py` checks control safety, pairing, permissions, and static assets; some assertions encode old markup/CSS. | Preserve behavioral tests and replace obsolete layout assertions with tests of the new behavior. |

Primary source files:

- [IDE interactive tool](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/interactive_tool.py)
- [Agent terminal tool](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_cli.py)
- [Web HTML](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/index.html),
  [JavaScript](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js), and
  [CSS](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/styles.css)
- [Web controller](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_control.py)
  and [request dispatcher](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_app.py)
- [IDE catalog adapter](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/integrated.py)
  and [behavior repository](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/behavior_assets.py)

### Wiki evidence and limitations

The [document map](../ninjarobot_pi5_wiki/project-knowledge.json) now points to
the registered `2026-09-17-03` manuals. The
[development guide](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-17-03/DevelopmentGuide.md)
documents the shared web controller, four language dictionaries, permissions,
and browser session identity. Its current UI descriptions describe the existing
combined page, not this proposed design.

The [feature page](../ninjarobot_pi5_wiki/wiki/concepts/features-and-tools.md) and
[architecture page](../ninjarobot_pi5_wiki/wiki/concepts/architecture.md) have
17 September AI semantic-review records, but their publication status remains
`draft`; search labels also include `unverified`. These labels do not establish
physical validation. No ingestion or semantic review was run for this planning
task. Exact command names and interfaces are checked against code. For example,
the feature page names Calendar preview aliases differently from the implemented
`calendar.propose_change`; this plan does not rely on those aliases or change Calendar.

## 3. Compatibility rules

1. Preserve the existing user/model → Agent → IDE → pi5 driver → device path.
2. Do not change managed drivers, servo values, obstacle thresholds, behavior
   definitions, safety latches, cleanup, health checks, or hardware ownership.
3. Preserve scriptable terminal commands. Only interactive menu numbers change.
4. Preserve pairing, transport security, controller exclusivity, heartbeats,
   camera consent, motion authorization, and the existing power-off confirmation.
   A controller lease is the existing temporary permission for one browser to control the robot.
5. Switching views changes presentation only. It does not start another Agent,
   acquire a second lease, grant AI permissions, change user, or erase conversation.
6. Emergency Stop remains a direct action, and Resume retains its existing checks.
   Routine button release and view changes use ordinary movement stop, not Emergency Stop.
7. Preserve Calendar preview → CONFIRM, task confirmations, and all other chat
   workflows. Interface selection must not send a chat message or reset their session.
8. Display preferences may be remembered. Microphone listening, camera consent,
   motion authorization, and live device state must never be restored from browser
   preference storage as if they were permissions.

## 4. Terminal tool design

### IDE main menu and exact destinations

```text
1. Hardware Configurations
2. Simulation
3. Run Robot Behaviors
   1. Face Expressions
   2. Robot Movements
   3. Special Behaviors
      1. Greetings
      2. Celebrating
      3. Error Warning
      B. Back
   4. EMERGENCY STOP
   5. Resume Hardware Movement
   B. Back
4. User-created Behaviors
   1. Start Behaviors Creator
   2. Run User-Created Behaviors
   3. Delete User-Created Behaviors
   B. Back
5. Bluetooth Speaker Connection
Q. Quit
```

Implementation instructions:

- Make `InteractiveConsole.menu` stop injecting an emergency entry. The built-in
  behavior menu supplies its explicit numeric option instead. Remove `e` from
  every affected choice list and dispatch branch; reject old `e` input normally.
- `_hardware_menu` displays the existing configuration fields once, then uses
  the existing Enter pause and returns directly. No Show, Back, or emergency menu.
- Extract the existing creator prompt sequence into a helper if needed. The new
  user-behavior menu calls it directly and returns to the grouped menu after save
  or cancellation. Preserve validation, simulation, private save, and overwrite rules.
- Reuse `_user_run_menu` and `_user_delete_menu`. Retain motion confirmation,
  private-only deletion confirmation, empty-catalog messages, and Back cleanup.
- Move the existing resume confirmation and `session.resume()` call into option 5
  of Run Robot Behaviors. Rename visible recovery guidance consistently.
- Keep face, movement, simulation, and Bluetooth workflows unchanged except for
  the requested emergency-entry removal and main-menu destinations.
- Keep the current Ctrl+C, quit, exception, and hardware-release cleanup paths.
  Removing menu entries does not remove interruption cleanup or the emergency API.
- Audit Back and Quit transitions with an active behavior. Preserve existing
  stopping behavior so regrouping menus does not orphan an active movement.

### Agent terminal

Remove “15. Guided checks,” its interactive dispatch branch, and update invalid
input guidance to 1–14. Keep option 14 Exit and every other menu number unchanged.
Keep `/guide`, `/help`, and the guided-check service implementation available.

## 5. Web page design guide

### Shared shell and switching

Keep one header, connection badge, hamburger menu, camera-preview dialog,
power-confirmation dialog, activity drawer, and error-notification area.
Render two mutually exclusive main views in the same document. Hide inactive
controls from both visual display and keyboard navigation. Use unique HTML IDs.

Use `state.interfaceMode` with the values `agent` and `gamepad`. Store only that
preference under a separate key such as `ninjarobotInterface`. Read/write failures
in browser storage must not prevent startup. Missing/invalid values choose `agent`.

On a switch:

1. End any held direction with the existing ordinary stop path and invalidate
   pending movement-start callbacks. Check this when opening the menu as well.
2. Preserve the socket, lease, heartbeat, browser chat ID, conversation draft,
   streamed reply, and backend state. Do not issue artificial chat requests.
3. Update the visible view and selected menu button, persist the preference,
   close the menu, and move keyboard focus to the destination heading.
4. Keep incoming chat messages in the shared conversation state while hidden.
   A small localized unread indicator may mark Agent Interface, without making
   the view switch automatically.

A view switch does not authorize cancellation of unrelated Agent tasks or
autonomous behaviors. Safety cancellation remains available in both views.

### Hamburger menu

Order the cards exactly as in the reference: Language, Control Interface, System
Power. Remove the Connection and Local tasks cards and their automatic task
refresh/render bindings. Keep the header connection badge and localized connection
errors, the existing startup/reconnect workflow, and task commands such as `/tasks`.
Connection recovery remains the existing connection workflow; do not invent a
connection-recovery chat command.

The selected interface button is cyan-filled; the other is outlined. Add text
and an accessible selected state, so color is not the only indication. Explain
that Game Pad sends manual controls without asking the conversation model;
the existing Agent service still hosts it.

Preserve modal focus containment, Escape/backdrop closing, scrollable content,
and focus restoration. Power off still uses its existing second confirmation,
availability checks, and one-use server authorization.

### Game Pad view

Place the large direction cross above the A/B/X/Y row and saved-behavior selector.

| Control | Existing action to reuse | Presentation |
| --- | --- | --- |
| Four directions | `move_start`, ordinary `move_stop` on release | Large touch targets; same hold-to-move behavior |
| Center dot | Existing decorative center | Keep non-interactive; do not invent a new stop action |
| A Greetings | `behavior` with `name: greeting` | Green circle |
| B Take Photo | Existing `camera` preview request | Blue circle; temporary preview and existing auto-clear |
| X Emergency Stop | `emergency_stop` | Red circle; visible text and direct action |
| Y Resume Movement | `resume` with existing confirmation | Amber circle |
| User-created Behaviors | New narrow list adapter to existing catalog | Native dropdown plus explicit Play button |

No chat panel or Agent audio controls appear in this view. Selecting a behavior
does not run it. Empty catalog: “No user-created behaviors yet,” disabled Play,
and a short pointer to the IDE creator. Loading/error state must differ from empty.
Preserve the user's selection on refresh if it still exists. Show a localized
motion warning when appropriate and retain required execution confirmation.

### Agent Interface

Give the conversation the flexible majority of available height. Keep the
composer attached to the conversation panel, with messages scrolling inside it.
Remove the direction controller and the manual behavior selector from this view.

Place the three audio controls below conversation, followed by A/B/X/Y:

| Control | Meaning |
| --- | --- |
| Web Mic | Start/stop browser speech recognition; recognized text fills the composer for review. |
| Voice Input | Enable/disable the existing Pi wake-word listener. |
| Spoken Replies | Toggle existing speech on/off; reflect actual returned status. |
| A Arm AI Motion | Existing arm/disarm control and consent prompt. |
| B AI Camera | Existing one-shot AI camera permission; not the manual Take Photo button. |
| X Emergency Stop | Same direct stop action as Game Pad. |
| Y Resume Movement | Same recovery action and confirmation as Game Pad. |

Use clear actual states such as Listening, Off, On, Starting, Unavailable, and
Permission denied. “Enabled” must not suggest the browser is listening when it is
only capable of listening. Speech OFF remains usable while a chat reply or
speech-start request is pending. Preserve current unsupported-browser guidance.
Do not switch a server-controlled state optimistically and leave it wrong after failure.

Use one shared implementation per action. If X/Y buttons are rendered in both
views, use distinct IDs and common `data-action` handlers rather than duplicate IDs.
Update both rendered copies from shared state. Any selectors referring to removed
buttons/cards must be removed or rewritten; optional chaining alone is not a
substitute for deliberately updating their lifecycle.

Clear Message removes visible messages only and must not call `/clear`, delete
history, change browser identity, or reset the runtime. Define a display generation
for active streams so a cleared, detached message node cannot reappear accidentally.
Subsequent new messages must still render normally. Do not discard a Calendar
confirmation merely because a display-only action or view switch happened.

### Removed controls and retained access

- Remove Record Once and distance-game buttons and their button-only handlers.
  Retain the underlying web protocol operations for compatibility.
- Keep `/game start 10`, `/game stop`, and `/game status` in Agent chat.
- A one-shot microphone request can use the existing `robot.microphone.transcribe`
  capability through the Agent, with existing consent and policy. The current
  shared help does **not** define `/record`; do not document a nonexistent command.
  Validate a request such as “Record five seconds using the robot microphone and
  transcribe what I say.” If current model tooling cannot complete that path,
  report the gap before closing the feature; any added command is a separate,
  explicit interface adapter, not permission to change capture behavior.
- Preserve `/tasks`, reminder preview/confirmation, and `/guide` access.
- Correct affected help text that still says the distance game always requires
  manual enablement, after checking the existing configuration-aware behavior.

### Visual system and responsive layout

Use the existing HTML, CSS, and JavaScript; no React, UI component framework,
external font service, or new frontend build pipeline is needed.

Proposed design tokens, based on the mockups rather than claimed exact color sampling:

| Element | Proposed guide |
| --- | --- |
| Background / panels | Near-black `#03080c`, dark panel `#06131b` |
| Accent / outline | Bright cyan-blue `#00a3ff`; thin 1-pixel outlines |
| Primary / secondary text | Near-white `#f2f6fa`; muted `#bdc4ca` |
| Action colors | Green `#16b67e`, blue `#00a3ff`, red `#e53940`, amber `#ffc64b` |
| Power action | Orange `#ff8a00`; retain confirmation |
| Spacing | 8-pixel base rhythm; generally 12–20 pixels between groups |
| Corners | 18–24 pixels for panels; full circles for A/B/X/Y where space permits |
| Text | Body about 16–18 pixels; section titles about 20–24; legible 14-pixel minimum for supporting controls |
| Touch targets | At least 44×44 CSS pixels as the project design target; larger direction and action buttons |

Retain the existing sans-serif stack, adding local Japanese/Chinese fallbacks if
needed. Inter is only a preferred font name today; the page does not guarantee
it is installed. Do not claim an exact mockup font match or download fonts silently.
Test Japanese/Chinese glyphs on the browsing device; Pi OS Lite need not render
the browser itself. Use black text on bright action circles when needed to meet
contrast; the mockup's white-on-cyan labels are not a reason to sacrifice legibility.

Use flexible Grid/Flex layouts with `min-width: 0` and `min-height: 0` in shrinking
containers. Preserve the existing visual-viewport handling for mobile keyboards
and use dynamic viewport height where available. Avoid a large fixed minimum
dashboard height that pushes controls beneath the keyboard.

Illustrative layout, to be tuned in browser tests:

```css
.agent-view {
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 12px;
}
.conversation-panel {
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
}
.chat-messages { min-height: 0; overflow-y: auto; overflow-wrap: anywhere; }
.dpad { width: min(100%, 25rem); aspect-ratio: 1; }
[hidden] { display: none !important; }
```

On narrow/short screens, allow deliberate scrolling or a two-by-two action-button
layout instead of clipping long translated labels. Keep the composer and safety
controls reachable, including when the activity drawer is open. Do not reproduce
a full-height activity overlay that makes the safety controls inaccessible.
Retain the existing mobile landscape safety behavior; changing it is outside this
refinement. Desktop layout can use a centered wider panel without showing both views.

Use visible keyboard focus, real buttons, accessible names for icon buttons, and
`aria-pressed` for toggles (a state read by assistive software). Respect reduced
motion preferences and browser zoom. The design target is readable text contrast
and clear controls in every state, not color-only status information.

Guidance references:
[W3C target sizes](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
defines a 24-pixel minimum with exceptions; this project deliberately targets
larger 44-pixel controls.
[W3C modal dialogs](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
explains keyboard focus containment and return.
[MDN viewport units](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/length)
explains dynamic viewport dimensions. These guide the implementation; they do not
establish accessibility compliance without testing.

## 6. Four-language implementation

Extend `web_static/i18n/en.json`, `ja.json`, `zh-TW.json`, and `zh-CN.json` together.
Keep the existing browser-locale detection, explicit preference, and English fallback.

Cover headings, buttons, toggle states, placeholders, empty/loading states,
validation, consent dialogs, notifications, activity summaries, status badges,
and accessible names. Render known backend states from stable codes rather than
translating by matching English sentences. Keep original diagnostic details
available in activity output where necessary; label them as technical details.

Suggested key families: `interface.*`, `behavior.user.*`, `audio.*`, `chat.clear`,
and shared `common.*`. Prefer existing keys when their meaning remains correct.

| English label | Japanese draft | Traditional Chinese draft | Simplified Chinese draft |
| --- | --- | --- | --- |
| Game Pad | ゲームパッド | 遊戲手把 | 游戏手柄 |
| Agent Interface | エージェント画面 | 智慧助理介面 | 智能助理界面 |
| User-created Behaviors | ユーザー作成動作 | 使用者自訂動作 | 用户自定义动作 |
| Take Photo | 写真を撮る | 拍照 | 拍照 |
| Emergency Stop | 緊急停止 | 緊急停止 | 紧急停止 |
| Resume Movement | 動作を再開 | 恢復動作 | 恢复动作 |
| Clear Message | 表示をクリア | 清除畫面訊息 | 清除界面消息 |

These are translation drafts to validate in context, not a substitute for a full
dictionary review. Preserve user-written behavior names, conversation content,
tool names, command syntax, event IDs, and the literal Calendar word `CONFIRM`.
The interface language continues to select browser speech-recognition language;
it must not silently download voices or promise speech engines support every UI
language. Existing model reply-language behavior remains unchanged.

## 7. Saved-behavior dropdown adapter

This is the one small backend presentation addition needed by the requested UI.
The current web behavior allowlist cannot run arbitrary saved user behavior names.

Recommended design:

1. Add an optional `source: all|user` filter to IDE `behavior.list`, default `all`.
   For `user`, call the existing `assets.list_user(category)`. Keep the old default
   output unchanged so existing model tools and clients remain compatible.
2. Add explicit web request types such as `user_behaviors_list` and
   `user_behavior_run`. Retain existing `behavior` handling for Greeting/Celebrate.
3. Validate the active controller lease using the existing request boundary.
   List through Agent tool execution → IDE catalog. Return only bounded display
   metadata: name, description, and whether it contains motion. Do not expose
   raw paths or arbitrary JSON execution to the browser.
4. Recheck that the selected name is currently a user-created behavior before
   execution. Reject unknown/deleted/built-in names in this path. Never accept a
   filesystem path or raw behavior definition from the browser.
5. Reuse `robot.behavior.run`, current controller attribution, ordinary stop,
   cancellation, policy, and IDE execution. Preserve confirmation requirements;
   a model cannot imitate a direct button action or obtain new permissions.
6. Handle catalog changes between listing and Play. Refresh and require a new
   review when displayed motion/details changed. Do not claim an atomic version
   lock unless the existing execution contract actually supports one. If an atomic
   guarantee needs runtime changes, surface that as a separate scope decision.
7. Keep Emergency Stop responsive during a long behavior; it must not queue
   behind that behavior's request. Disable duplicate Play while the request is
   pending, surface failures, and never automatically replay on reconnect.

This is an additive catalog/presentation adapter, not a new behavior engine.
Do not import a pi5 driver, open hardware in the Agent, or remove the existing
web allowlist indiscriminately. Pagination/bounds must be explicit for large
catalogs, without silently omitting entries. Approval of this plan includes this
small adapter; larger execution or permission changes need a separately reviewed plan.

## 8. Implementation phases and gates

| Phase | Work and likely files | Compatibility contract | Validation gate / risk |
| --- | --- | --- | --- |
| 1. Terminal navigation | IDE `interactive_tool.py`; Agent `agent_cli.py`; corresponding CLI tests | Same existing operations and cleanup; new IDE menu numbers; Agent 1–14 retained | Simulated input transcripts, hardware page without initialization, back/quit/cancel tests. Hardware-facing UI risk; no live actions. |
| 2. Shared web views | `index.html`, `app.js`, `styles.css` | One socket, lease, session, and shared actions; preserve media and power consent | View switching, mobile keyboard, streaming, focus, pointer release, reconnect tests. Hardware-facing UI risk. |
| 3. Saved-behavior adapter | `web_app.py`, `web_control.py`, IDE `_BehaviorListAdapter`, relevant tests | Additive list filter and web routes; existing run contract and driver code unchanged | User-only listing, validation, permission, duplicate Play, cancellation, long-run stop tests using fake devices. Motion dispatch risk only during opt-in real acceptance. |
| 4. Localization and polish | Four dictionaries, dynamic state rendering, CSS, affected help | UI translations only; no command/ID translation or model/policy changes | Dictionary parity, missing-key audit, all four locales, readable layout and known errors. Low software risk. |
| 5. Documentation and handoff | README; new full-manual/log versions; validation walkthrough and evidence | Preserve registered originals; documentation reflects verified final implementation | Full gate, file-link checks, public-help source checks, manual acceptance checklist. No wiki ingestion/review. |

Each phase records its affected documentation for the final update; do not keep
creating partial manual versions during implementation. After each meaningful
code phase, run relevant tests and the required repository gates:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python scripts/verify_workspace_driver_sources.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
git diff --check
```

Python linting does not validate browser layout. Add browser-executed checks
against a fake server, using an available browser harness. If introducing a
browser automation dependency such as Playwright, keep it development-only, pin
it, and document its setup; do not add it to Pi runtime installation or download
browsers silently. Manual cross-browser checks remain necessary.

## 9. Acceptance tests

### Automated software checks

- Exact terminal menu paths, old `e` rejection, only one IDE emergency menu entry,
  numeric option 4 dispatch, resume confirmation, unchanged creator validation,
  user-only deletion, Back, Quit, and Ctrl+C cleanup.
- No hardware initialization when viewing configuration or navigating empty menus.
- First-use Agent view, remembered mode, invalid/blocked storage fallback, selected
  menu styling, no duplicate HTML IDs, and no focusable hidden controls.
- Switch while a direction is held and while movement start is pending: ordinary
  stop reaches the server, no stale restart, no Emergency Stop or Resume requirement.
- Switch during chat streaming: same browser session and one continuous reply.
  Clear Message during streaming: no history deletion and no broken next message.
- Existing Calendar CONFIRM still works after a view switch; no accidental write.
  Use fake Calendar responses, never a real account in automated tests.
- Speech OFF while chat/speech startup is busy; accurate failure states; mic
  unsupported/denied conditions; permission not restored from local preferences.
- User behavior empty/large catalog, unsafe name, stale selection, missing entry,
  duplicate click, execution failure, and controller disconnect. Emergency stop
  bypass remains tested independently of queued ordinary operations.
- Removed cards/buttons leave no null-element exceptions, stale polling, or extra
  requests. Existing request routes remain compatible.
- All translation dictionaries have identical keys and placeholders. Test long
  labels, screen-reader names, known errors, locale switching mid-connection,
  Traditional/Simplified Chinese differences, and no accidental English fallback
  for supported fixed labels. Preserve original user/model text.

### Browser and visual checks

Test at least 320×568, 390×844, 430×932, 768×1024, and 1280×800 browser sizes.
Include Android Chrome and iPhone Safari, portrait keyboard open/closed, the
existing mobile landscape blocker, desktop keyboard navigation, and 200% zoom.
Record screenshots for both views and the menu in all four languages. Check the
activity drawer and power/camera dialogs independently. Fake all device actions.
Pass means no clipped labels, horizontal overflow, inaccessible controls, lost
composer, hidden faults, or unexpected whole-page jumps while typing/streaming.

### Step-by-step manual walkthrough to deliver after implementation

Create `docs/validation/ui_refinement_walkthrough_260918.md` with actual commands,
results, and screenshots after code validation. Its procedure should be:

1. Finish ongoing activity and use the installation's existing service restart
   procedure once to load the new code. Do not start a second hardware owner.
2. Start the IDE tool with the Agent stopped where exclusive hardware ownership
   requires it. Verify the exact new menus, configuration display → Enter, empty
   user catalog, simulation, creator cancellation, and Q exit.
3. Check Agent terminal options 1–14 and confirm `/guide` remains available in chat.
4. Open the web interface. First use shows Agent Interface. Switch views, refresh,
   and verify the selection is remembered without changing chat identity.
5. Check Language → each of the four languages in both views, dialogs, status,
   errors, and activity output. Confirm terminal tools remain English.
6. Send a long chat message, receive a long reply, open the keyboard/menu/drawer,
   switch views during a reply, and use Clear Message. Confirm saved history and
   memory remain accessible and the next reply still displays.
7. Test `/tasks`, `/guide`, distance-game commands, and a one-shot recording request
   with explicit recording consent. Confirm no removed buttons are needed.
8. With camera/microphone consent, compare Take Photo with AI Camera permission;
   test Web Mic text entry, Pi Voice Input, and Spoken Replies on/off separately.
9. Only with wheels raised and an operator ready to remove power, test brief
   direction presses/releases, menu/view switching, and existing obstacle recovery.
   Expect ordinary stops without Resume; then explicitly test X Emergency Stop and
   Y Resume. No interrupted movement should restart automatically.
10. Play Greeting and a known harmless saved behavior. With separate movement
    consent, test a known bounded moving user behavior; verify stop and error paths.
11. Inspect the power confirmation and cancel it. Actual shutdown is a separate
    opt-in power-risk test, not required for this UI refinement.

Separate evidence into safe navigation, device communication/media consent,
actuator movement, and optional power-risk checks. For a failure, stop physical
testing, keep the robot stopped, capture the visible error, and restore the prior
matched UI/server version. Restoring UI code does not undo external task actions.

## 10. Documentation and completion criteria

After all code phases pass, update documentation once:

- README: the two web views, terminal menu paths, four web languages, and retained
  command access for removed buttons.
- New full InstallationGuide source: actual terminal steps, web switching,
  remembered preferences, permissions, and mobile-browser use.
- New full DevelopmentGuide source: view state, shared controller/session,
  translation workflow, additive behavior adapter, and browser test setup.
- New DevelopmentLog source: reasons, changed files, exact validation results,
  screenshots, and manual checks still pending.
- Review NinjaRobot_MCP_Skill and command-help guidance; update a successor only
  where UI instructions or available command guidance changed.
- Update README links and the runtime public-source manifest deliberately for
  new sources, with their correct hashes. Keep registered originals untouched.
- Review THIRD_PARTY_NOTICES only if a development dependency is added; no new
  production dependency is proposed.

Wiki impact: affected topics include features/tools, installation, development
workflow/history, and the web/IDE portions of architecture guidance. Record these
for the owner's later ingestion. Do not ingest, apply semantic diffs, record wiki
reviews, or refresh registered fingerprints during implementation. The owner will
ingest and review after manual validation, as instructed.

Completion requires passing software gates, a checked walkthrough, a truthful
record of any unavailable browser/hardware tests, and no unrelated runtime or
driver changes. The present planning task changes only this document; implementation
starts after the owner approves the plan.
