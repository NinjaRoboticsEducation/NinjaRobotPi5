# UI Refinement: Walkthrough and Validation

Date: 2026-09-18
Scope: Implementation of the UI refinement specified in `DevelopmentPlanDoc/UI_Refinement_ImplementationPlan_260918.md`.
Safety: No hardware movement, camera capture, or microphone recording occurred during automated testing. Wiki ingestion and semantic review are deferred for owner verification.

---

## Executive Summary

This implementation delivers the user interface refinement for NinjaRobotPi5 across terminal and web surfaces, without altering any underlying robot capabilities, driver code, safety latches, or existing Agent behavior.

### 1. Terminal Navigation (`ninjarobot_pi5_ide` & `ninjarobot_pi5_agent`)

- **Interactive Console Menu Cleanup**: Removed the `emergency` parameter and the `E. EMERGENCY STOP` line injection from `InteractiveConsole.menu()`. Removed `e` choice handling from all submenus.
- **Main Menu Restructuring**:
  1. `Hardware Configurations` — Prints hardware and software configuration JSON immediately and returns after Enter pause. No redundant submenu or initialization.
  2. `Simulation` — Direct access to simulated runs with simulated devices (no physical GPIO, PWM, I2C, SPI access).
  3. `Run Robot Behaviors` — Groups built-in animated faces, movements, and special behaviors. Includes **4. EMERGENCY STOP** and **5. Resume Hardware Movement** (with confirmation) as explicit sub-options.
  4. `User-created Behaviors` — Groups **1. Start Behaviors Creator**, **2. Run User-Created Behaviors**, and **3. Delete User-Created Behaviors**.
  5. `Bluetooth Speaker Connection` — Direct launch of the Bluetooth speaker configuration wizard.
  Q. `Quit` — Stops active work, releases hardware locks, and exits cleanly.
- **Direct Creator Entry**: `Start Behaviors Creator` enters the parameter prompt sequence directly without a redundant introductory confirmation screen.
- **Agent Terminal Menu**: Removed option 15 "Guided checks" from `_interactive()` in `agent_cli.py`. Updated guidance message to "Please choose a number from 1 through 14." The underlying guided-checks service, `/guide 1-5`, and `/help` remain fully functional in chat.

### 2. Shared Web Views (`web_static/`)

- **Two Switchable Main Views**:
  - `#gamepadView`: Dedicated manual control view featuring the large directional cross (D-pad), action pad buttons (A: Greetings, B: AI Camera, X: Emergency Stop, Y: Resume), and the User Created Behaviors dropdown with Play button.
  - `#agentView`: Dedicated AI conversation view featuring the flexible chat message scroll container, message composer with `Clear Message` button, audio controls section (Web Microphone, Voice Input wake-word, and Spoken Replies toggle), and action pad buttons (A: Arm AI Motion, B: AI Camera, X: Emergency Stop, Y: Resume).
- **View Switching & Persistence**:
  - Mode is managed via `state.interfaceMode` (`"gamepad"` or `"agent"`), persisted in `localStorage` under `ninjarobotInterface`.
  - Seamless view switching: any active direction hold is stopped before switching; socket connection, active lease, and conversation state are completely preserved.
  - Focus is moved accessible to the target view heading upon switching.
  - An unread message dot indicator alerts the user when new chat arrives while in Game Pad view.
- **Hamburger Menu Reorganization**:
  - Cards strictly ordered: **Language Selection**, **Control Interface** (Game Pad / Agent Interface buttons with active styling), and **System Power** (guarded two-step power-off).
  - Removed obsolete `Connection` and `Local tasks` cards and their automatic polling overhead.
- **Removed Deprecated Controls**:
  - Removed button-only `Record Once` (`#usbRecordButton`) and distance game buttons from the DOM.
  - Underlying protocols, chat commands (`/game start 10`, `/game stop`, `/game status`), and tasks (`/tasks`) remain fully operational.
- **Clear Message with Generation Tracking**:
  - `Clear Message` empties visible message elements without deleting conversation history or resetting browser chat session ID.
  - `state.displayGeneration` counter prevents active asynchronous streaming chunks from reviving cleared DOM nodes.

### 3. Saved-Behavior Backend Adapter (`integrated.py`, `web_control.py`, `web_app.py`)

- **IDE `behavior.list` Capability**:
  - Added optional `source` argument (`"all"` | `"user"`, defaulting to `"all"`) to `_BehaviorListAdapter` input schema.
  - When `source == "user"`, calls `self._robot.assets.list_user(category)`.
- **Web Controller User Behavior Methods**:
  - `list_user_behaviors(lease_id)`: Fetches private user behaviors and returns bounded metadata (`name`, `description`, `contains_motion`).
  - `run_user_behavior(lease_id, name)`: Validates name against currently available user behaviors (rejecting built-in, deleted, or path traversal strings), stops active motion, and executes `robot.behavior.run`.
- **Websocket Message Dispatch**:
  - Added `user_behaviors_list` and `user_behavior_run` message handlers in `_dispatch_web_message()`.

### 4. Localization Parity (`web_static/i18n/`)

- Added 12 new translation keys across all 4 supported languages (`en.json`, `ja.json`, `zh-TW.json`, `zh-CN.json`):
  - `interface.title`, `interface.gamepad`, `interface.gamepadDetail`, `interface.agent`, `interface.agentDetail`
  - `behavior.user.title`, `behavior.user.detail`, `behavior.user.empty`, `behavior.user.play`, `behavior.user.confirmMotion`, `behavior.user.error`
  - `chat.clearMessage`
- All 4 dictionaries maintain strict key parity (146 keys each) with zero missing or empty strings.

---

## Changed Files

| File | Changes |
|---|---|
| `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/interactive_tool.py` | Restructured main menu (1-5, Q), removed emergency stop injection, simplified hardware config and creator entry |
| `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/integrated.py` | Added `source` filter (`all`/`user`) to `_BehaviorListAdapter` |
| `ninjarobot_pi5_ide/tests/test_ide_cli.py` | Updated interactive menu unit tests for new menu options and navigation paths |
| `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_cli.py` | Removed option 15 "Guided checks" from interactive menu, updated guidance to 1–14 |
| `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_control.py` | Added `list_user_behaviors()` and `run_user_behavior()` with validation |
| `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_app.py` | Added `user_behaviors_list` and `user_behavior_run` websocket dispatch |
| `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/index.html` | Restructured into `#gamepadView` and `#agentView`, reorganized hamburger menu, removed obsolete buttons |
| `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/styles.css` | Implemented design tokens, view-specific layouts, D-pad, and audio controls styling |
| `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js` | Added view switching, display generation tracking, user behavior loading/playing, removed old button handlers |
| `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/i18n/*.json` | Added 12 new keys to `en.json`, `ja.json`, `zh-TW.json`, and `zh-CN.json` (146 keys each) |
| `ninjarobot_pi5_agent/tests/test_web.py` | Added unit tests for user behavior listing/running, updated mobile UI assertions |
| `README.md` | Documented two-view web interface, updated IDE menu numbering (Bluetooth is option 5) |

---

## Verification Results

### Automated Gate Checks

1. **Driver Baseline Verification**:
   ```bash
   uv run --frozen python scripts/verify_immutable_drivers.py
   ```
   *Result*: PASS: 222 tracked files across 6 drivers match the import baseline plus 56 authorized repairs.

2. **Bytecode Compilation**:
   ```bash
   uv run --frozen python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
   ```
   *Result*: PASS: Clean compilation with zero syntax errors.

3. **Code Style & Formatting**:
   ```bash
   uv run --frozen ruff check .
   uv run --frozen ruff format --check .
   ```
   *Result*: All files checked and formatted cleanly.

4. **Type Checking**:
   ```bash
   uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
   ```
   *Result*: Success: no issues found in 71 source files.

5. **Automated Unit Tests**:
   - `test_ide_cli.py`: 14 passed (interactive menu exit, submenu navigation, hardware config page)
   - `test_agent_cli.py`: 21 passed (agent interactive menu 1–14, guided checks retained)
   - `test_web.py`: 23 passed (websocket connection, user behavior list/run, mobile interface assertions)
   - `test_shutdown.py`: 9 passed (full 4-locale i18n key parity and script coverage)

---

## Manual Raspberry Pi Validation Checklist

When deploying to the Raspberry Pi 5 hardware, execute the following safe checks:

### Checklist 1: Terminal Menu Navigation (Safe, Wheels Can Remain Stationary)

1. Run `uv run --frozen --extra hardware ninjarobot-ide-tool interactive`
2. Verify main menu shows options 1 through 5 plus Q:
   - `1. Hardware Configurations` -> Press `1`, verify configuration JSON displays immediately, press Enter to return.
   - `2. Simulation` -> Press `2`, verify simulation submenu opens, press `b` to return.
   - `3. Run Robot Behaviors` -> Press `3`, verify options include `1. Face Expressions`, `2. Movement Behaviors`, `3. Special Behaviors`, `4. EMERGENCY STOP`, and `5. Resume Hardware Movement`.
   - `4. User-created Behaviors` -> Press `4`, verify options include `1. Start Behaviors Creator`, `2. Run User-Created Behaviors`, and `3. Delete User-Created Behaviors`.
   - `5. Bluetooth Speaker Connection` -> Press `5`, verify wizard opens.
   - `Q. Quit` -> Press `q`, verify clean exit and lockfile release.
3. Test old input rejection: enter `e` on any menu and confirm it is rejected as an invalid choice.

### Checklist 2: Web Interface Switching & Game Pad

1. Start the Agent service: `uv run --frozen --extra hardware ninjarobot-agent service start`
2. Navigate to `https://ninjarobotpi5.local:8443/` on mobile or desktop browser.
3. Verify the default view is **Agent Interface** (or previous preference if stored).
4. Open the hamburger menu:
   - Verify card order: Language -> Control Interface -> System Power.
   - Click **Game Pad** in Control Interface.
   - Verify view switches immediately to `#gamepadView` showing D-pad, action buttons (A, B, X, Y), and User Created Behaviors dropdown.
5. In Game Pad view:
   - Tap **A** (Greeting) -> Verify greeting face and chime run.
   - Tap **B** (AI Camera) -> Verify temporary camera preview opens and auto-clears.
   - Select a user behavior from dropdown -> Tap Play button -> Verify confirmation prompt appears if behavior contains motion.
   - Tap **X** (Emergency Stop) -> Verify robot stops immediately.
   - Tap **Y** (Resume) -> Verify confirmation dialog and resume operation.

### Checklist 3: Agent Interface & Audio Controls

1. Switch to **Agent Interface** via hamburger menu.
2. Verify conversation panel occupies primary viewport height.
3. Tap **Clear Message** -> Verify visible messages disappear, chat session ID remains unchanged, and subsequent messages render properly.
4. Test audio controls:
   - **Web Microphone**: Tap once, speak into browser mic -> Recognized text fills composer input box for review.
   - **Voice Input**: Tap to toggle Pi always-on wake word listener.
   - **Speech ON/OFF**: Tap to toggle spoken replies.

### Checklist 4: Multi-Language Parity

1. Open hamburger menu -> Language dropdown.
2. Select each locale in sequence:
   - **日本語**: Verify interface text updates to Japanese (e.g., "ゲームパッド", "エージェント画面", "表示をクリア", "ユーザー作成動作").
   - **繁體中文**: Verify interface text updates to Traditional Chinese (e.g., "遊戲手把", "智慧助理介面", "清除畫面訊息", "使用者自訂動作").
   - **简体中文**: Verify interface text updates to Simplified Chinese (e.g., "游戏手柄", "智能助理界面", "清除界面消息", "用户自定义动作").
   - **English**: Verify return to English.
