# NinjaRobotPi5 guided setup, installation, and chat implementation plan

Status: proposed for owner review; implementation is not authorized yet.
Prepared 22 September 2026 from local wiki evidence, Serena code inspection,
and upstream documentation. This document describes future work, not completed features.

## Agreed outcome

Add a beginner-friendly `ninjarobot onboard` command, a curl-based installation
entry point, and editable multiline terminal chat. Preserve existing manual
commands, configuration, services, safety policy, and managed drivers.

Owner clarifications incorporated:

- Enter sends a chat prompt; Shift+Enter inserts a newline; arrows edit the
  current prompt. Offer Alt+Enter as a compatibility fallback where the terminal
  cannot distinguish Shift+Enter from Enter.
- Skipping ngrok selects the existing authenticated HTTPS interface accessible
  from the same Wi-Fi. Start it with the final Agent launch, not merely because
  the user skipped ngrok. Exit leaves newly started setup resources stopped.
- Tavily, Google Calendar, and Notion must all use external MCP servers.
  Do not substitute the existing native Calendar connection.

The supported physical target remains Raspberry Pi 5 with Raspberry Pi OS Lite
64-bit. Development and automated simulation must not operate physical devices.
Hardware setup is mandatory for a completed physical setup. A missing mandatory
device permits saving progress and simulation, but never a falsely completed
hardware checklist or real-mode launch through this wizard.

## Research findings and evidence limits

The Git working tree was clean before research. No runtime files were changed.

The document map identifies the current full manuals under
`ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-18/`, and the development
log under the matching `raw/notes/` directory. The four registered manual hashes
and all mapped implementation hashes match their files. Relevant curated pages
remain `draft` with recorded passing AI semantic reviews from 18 September;
those records are not human or physical acceptance.

Read evidence included the wiki README, overview, workflow guide, architecture,
installation, and features pages; their source catalog records; installation
sections 3–9; development architecture/provider/MCP sections; and the external
Calendar MCP tutorial. The wiki README's introductory date still describes a
17 September checkpoint while its links and map point to 18 September. Correct
that description during documentation work.

`python scripts/wiki.py search`, `source status`, `lint`, and `check` all report
that the separate wiki environment is missing. Direct local reading and hash
comparison were used instead. No dependencies were installed. Full wiki lint and
semantic-review validity are therefore not certified by this inspection.

`python scripts/verify_immutable_drivers.py` passed: 222 tracked files across six
drivers match the baseline plus 56 authorized repairs. Running the workspace
source verifier with the available Python failed because all six driver packages
are uninstalled in that interpreter. This is an environment limitation observed
before implementation. The prescribed frozen-environment gate has not been run.

### Existing code to reuse

Paths in this table are relative to the repository. Agent module names refer to
`ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/`; IDE module names refer to
`ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/`.

| Area | Inspected implementation | Consequence for the plan |
| --- | --- | --- |
| Installer | `install.sh`, `scripts/install-rpi.sh`, `scripts/install-versions.env` | Root script only executes the adjacent installer; the latter needs the version manifest and `uv.lock`. Downloading the root script alone is insufficient. |
| Installer safety | `--dry-run`, `--check`, `--yes`, profile selection; pinned uv/Ollama/whisper inputs; boot backup | Preserve these paths and their existing defaults. The hardware installer already installs whisper.cpp and enables Ollama, but does not select an Ollama model or start the Agent. |
| Agent CLI | `agent_cli.build_parser`, `_run`, `_chat_repl`, `_spawn_service` | Extend the existing argparse CLI and share dispatch. `ninjarobot-agent` remains available; `ninjarobot` is an additional entry point. |
| Terminal chat | `_chat_repl` calls `asyncio.to_thread(input, "You> ")`; both direct chat and the interactive menu call it | Replace only prompt acquisition, preserving slash commands, sessions, streaming, and authorization. Plain input has no guaranteed multiline editing. |
| IDE CLI | `cli.py`, `interactive_tool.py` | Reuse hardware/config/behavior/stop commands. Do not put driver orchestration in the Agent. |
| Driver setup | `pi5buzzer ... buzzer-tool`, `pi5disp ... display-tool`, `pi5vl53l0x ... sensor-tool`, `pi5servo ... servo-tool`, camera and mic `setup_cmd`/tools | Keep these managed setup implementations. Add an IDE-owned guided adapter and command allowlist around them. |
| Config import | `discover_pi5_configs`, `import_pi5_configs`, `save_robot_config`, `load_effective_config` | Import existing private calibration/configuration. Distance calibration stays driver-owned; servo import records its file path. |
| Ownership | IDE `HardwareOwnership.acquire/release` | Hold the existing ownership lock while any wizard-controlled driver process is alive. Detect a running Agent before setup. |
| Bluetooth | IDE `bluetooth_setup.connect_wizard`, `save_selection`, `install_service` | Reuse pairing and output selection; reconnect service remains separately opt-in. Lite audio prerequisites may still require guided repair. |
| Voice | IDE `voice_input.py`, `microphone.py`, bundled ONNX assets; installer whisper setup | Reuse packaged `hey_Ninja.onnx`, existing model checks and transcription path. Do not copy or download a replacement wake model. |
| Providers | `ConfiguredProviderRegistry`, `ModelManager`, `persist_model_selection`, provider CLI commands | All four providers already exist. Add orchestration, not new adapters. Preserve Ollama benchmark acceptance. |
| Secrets | `SecretStore` | Owner-only directory/file, atomic writes, environment precedence, and redaction already exist. Reuse them. |
| MCP | `MCPServerConfig`, `tavily_server_config`, `MCPToolProvider`, `SDKMCPConnection` | Tavily preset exists; stdio and HTTPS bearer transports exist. Interactive OAuth and a Notion preset are missing. |
| External Calendar | Full MCP manual's `google-calendar-readonly` example | It is documentation code, not an installed turnkey server. Package a tested external stdio adapter using existing Calendar HTTP/OAuth primitives. |
| Native Calendar | `calendar_oauth.authorize`, `GoogleCalendarBackend`, `calendar-connect` | Reuse underlying OAuth/HTTP code, but leave the native CLI and database connection untouched. Native `calendar-connect` needs a running service and must not be used for this external MCP flow. |
| Remote access | `RemoteAccessService`, `install_ngrok_binary`, `_run_remote_command`, `WebServerManager` | Reuse token setup, tunnel lifecycle, health, pairing, and local fallback. |
| Existing onboarding | `onboarding.OnboardingCoordinator`, `OnboardingConfig` | These mean startup QR/pairing/greeting, not installation. Put the new wizard in `setup_wizard/` and preserve the existing meanings. |
| Runtime | `service_main.run_service`, IPC service commands, deployment module, simulation builder | Reuse the single service owner. Real startup can run Greeting/Idle and start configured voice input; disclose those effects before launch. |

The user's sample `https://github.com/NinjaRoboticsEducation/NinjaRobotPi5/install.sh`
is not a raw-file download URL, and plain `curl` downloads rather than executes.
Use a reviewed Git revision at `raw.githubusercontent.com` plus an explicit
execution step. No public endpoint for the future implementation is claimed to
exist yet.

## Architecture and shared contracts

```text
ninjarobot / ninjarobot-agent
  -> existing argparse dispatch
  -> setup_wizard (presentation, sequence, progress)
       -> existing Agent configuration/provider/MCP/service operations
       -> IDE setup API
            -> ownership lock + approved standalone driver setup process
            -> existing IDE validation and configuration import
                 -> managed pi5 driver -> device
```

The wizard is deterministic and never asks a model to authorize setup. It must
not import managed drivers, access devices, or run arbitrary shell commands.
External MCP servers never receive hardware authority.

Add small shared application operations only where current CLI handlers mix
printing, argument parsing, and useful behavior. Both manual CLI and wizard call
those operations. Avoid a second service launcher, model catalog, secret store,
ngrok supervisor, or calibration implementation.

Proposed modules:

- Agent `terminal_input.py`: editable prompt abstraction and terminal fallback.
- Agent `setup_wizard/{models,state,ui,runner,steps}.py`: typed state, private
  progress, presentation, orchestration, and step definitions.
- Agent `setup_operations.py`: small reusable adapters around existing provider,
  config, service, and remote operations where extraction is needed.
- IDE `hardware_setup.py`: allowlisted setup runners and component checks.
- Agent `mcp_oauth.py`: SDK OAuth integration and private token storage adapter.
- Agent `mcp_presets.py`: preset factories shared by CLI and wizard; move the
  existing Tavily factory only with a compatibility import if useful.
- Agent `external_mcp/google_calendar.py`: independently launched stdio server,
  using existing Calendar transport/OAuth support; no hardware imports.

Names are proposed; keep modules together if implementation would otherwise
produce trivial one-function wrappers.

### CLI and progress

Provide these additive commands:

```text
ninjarobot onboard
ninjarobot onboard --resume
ninjarobot onboard --status
ninjarobot onboard --dry-run
ninjarobot onboard --step microphone
ninjarobot onboard --simulation
ninjarobot-agent onboard [same options]
```

`--status` and `--dry-run` are read-only, make no network calls, and require no
terminal. Other paths require an interactive terminal for consent and secrets.
`--step` checks prerequisites and cannot bypass mandatory readiness or ownership.
`--simulation` rehearses the flow with simulated adapters, no downloads, accounts,
device operations, or changes to real configuration. It uses separate scratch
state and never records hardware success. Normal onboarding may finish by
launching the existing simulation service with a real selected provider; that
is distinct from an offline wizard rehearsal.

Use stable step IDs and statuses: pending, running, complete, skipped, failed,
needs_attention. Record verification level separately: configured,
software_verified, operator_verified, simulated. Persist progress at
`~/.local/state/ninjarobot_pi5/setup-progress.json` using versioned schema, atomic
replacement, owner-only permissions, symlink refusal, and a single-wizard lock.
Honor existing path conventions rather than changing all defaults to XDG paths.

State contains selections, timestamps, configuration fingerprints, safe error
codes, and the next step. It never contains keys, tokens, calendar contents,
recordings, or camera images. It is a progress record, not a second runtime
configuration. Existing TOML, driver files, secret store, and MCP config remain
authoritative. On resume, recheck readiness; interrupted work becomes pending
review. Do not reuse prior motion/capture consent. Refuse unknown future schemas
without overwriting them.

Preview each configuration change, preserve unrelated settings, detect concurrent
edits before saving, and keep a private recovery copy. Failed verification must
not overwrite a working provider or MCP configuration. Stage new credentials
until validation or explain a separate "saved, not verified" result. Reuse the
existing atomic save functions, extending them only if their concurrency guard
is insufficient. Skipping an already configured optional component means leave
it unchanged; disabling it is a separate explicit choice.

### UX contract

Use one short screen per step, usable over SSH at 80 columns:

```text
Step 4 of 10 — Wheel motors                         Required
What is this? Two motors turn the robot's wheels.
Why? Each motor needs its own exact stop setting.
Before continuing: raise both wheels and keep power removal within reach.

[1] Open calibration    [2] Check saved settings    [B] Back    [Q] Save and exit
```

Show actual progress, not a fabricated percentage during builds or downloads.
Always provide text statuses as well as color, plain-output support, concise
troubleshooting, retry, back, and save/exit. Optional steps also offer skip.
Mandatory steps allow defer with an incomplete result, not a success label.
Explain when control temporarily passes to a familiar standalone tool.

## Phase 1 — Editable terminal chat

**Objective and scope:** fix arrow navigation and multiline editing for both
terminal chat entry points. Hardware risk: none.

**Files:** Agent `terminal_input.py` (new), `agent_cli.py`, `command_help.py`,
Agent `pyproject.toml`, `uv.lock`, `THIRD_PARTY_NOTICES.md`; new terminal-input
tests and existing `test_agent_cli.py`.

**Implementation:**

1. Add a reviewed, locked `prompt-toolkit` 3.x dependency. Use `PromptSession`
   with asynchronous input and custom key bindings; it supports multiline
   buffers and asynchronous prompting according to its
   [official documentation](https://python-prompt-toolkit.readthedocs.io/en/master/pages/asking_for_input.html).
2. Enter submits once. Shift+Enter inserts a newline when the terminal exposes a
   distinct sequence. Alt+Enter always provides the documented newline fallback.
   Prototype decoding against the selected dependency before promising specific
   SSH terminal support. Do not map ordinary Enter to an indistinguishable key.
3. Left/right move by character; up/down move within the multiline/wrapped
   prompt and do not unexpectedly recall history. Preserve Home/End, deletion,
   Unicode, resizing, and bracketed paste. Pasted newlines never submit the prompt.
4. Ctrl+C cancels the unsent draft; Ctrl+D on an empty buffer exits. Restore the
   terminal on exceptions. Preserve one-shot `chat "prompt"` and pipe/non-TTY
   behavior using a plain input adapter. No persistent prompt-history file.
5. Inject the input adapter into `_chat_repl`; leave its dispatch and motion,
   camera, voice, and confirmation semantics unchanged.

**Testing:** byte/input-stream tests for all arrows, multiline edits, submit-once,
paste, Unicode, EOF, cancellation, and slash-command dispatch; a PTY integration
test proves no literal arrow escape strings reach the submitted prompt. Test the
menu and direct chat paths. Manual SSH tests cover distinguishable Shift+Enter
and the fallback terminal case.

**Gate and outcome:** run the common Python gate below and dependency/license
review. Existing chat contracts pass; a multiline draft can be edited before
sending. Draft README/manual keyboard help for Phase 8.

## Phase 2 — Safe curl bootstrap and command availability

**Objective and scope:** install from outside a checkout while preserving the
existing in-checkout installer. Risk: downloads, package installation, services,
and boot configuration; no device tests during installation.

**Files:** `install.sh`, `scripts/install-rpi.sh`, version manifest if needed,
Agent `pyproject.toml`, `tests/test_rpi_installer.py`, new bootstrap tests,
README and new installation-manual source draft.

**Implementation:**

1. Keep the current adjacent-repository dispatch when its expected files exist.
   In standalone/bootstrap mode, accept `--ref <full-reviewed-commit>` and
   `--install-dir`; forward legacy installer flags unchanged.
2. Document a single shell command that completely downloads the script to a
   temporary file, checks curl success, then executes it. Prefer this to streaming
   partially downloaded code into a running shell. Use HTTPS-only redirects,
   failure status checks, bounded download time, and cleanup traps.
3. Use the same reviewed commit in the raw script URL and checkout argument.
   Materialize that commit in public instructions only after the implementation
   exists in the public repository. Until then, documentation is a proposed
   command template. Do not invent a release, publish, or use unpinned `main` as
   the tested installation contract.
4. Default destination is `~/NinjaRobotPi5`. Preflight OS, architecture, curl,
   Git, free disk space, destination safety, terminal availability, and privilege
   needs. Installing missing Git requires an explicit displayed package action.
   Do not run the entire installer as root or put configuration under root's home.
5. Fetch the exact revision into staging, verify the checked-out commit and
   required manifest/files, then make the destination available. Never reset,
   clean, or overwrite an existing checkout. Offer reuse only when compatible;
   otherwise explain how to choose another destination.
6. `--dry-run` and `--check` must not clone, install, create launchers, or edit
   system files. A standalone `--check` without an installation reports absence.
   Prompt through the controlling terminal, supporting downloaded scripts and
   deliberate `bash -s --` usage; no-TTY fails unless existing `--yes` applies.
7. Delegate all actual Pi installation to `scripts/install-rpi.sh`; preserve
   pins, camera bridge, boot backups, profiles, whisper defaults, and no automatic
   Ollama model download. Handle interrupted bootstrap and reruns explicitly.
8. Add `ninjarobot = "ninjarobot_pi5_agent.agent_cli:main"` as an entry point.
   After successful installation, create an owner-local launcher in
   `~/.local/bin` pointing to the installed environment, with collision checks.
   It must work outside the checkout and must not install dependencies on launch.
   Explain PATH setup if needed; preserve activation/manual commands.

Illustrative future command shape, with placeholders intentionally non-runnable:

```text
download raw.githubusercontent.com/NinjaRoboticsEducation/NinjaRobotPi5/<COMMIT>/install.sh
  to a private temporary file, then:
bash <temporary-file> --ref <SAME_COMMIT>
```

**Testing:** fake curl/Git/apt/sudo/systemctl runners, truncated download, failure
status, missing manifest, revision mismatch, spaces in paths, existing/dirty
destination, Ctrl+C, no terminal, dry-run, check, profiles, and repeated install.
Assert installer never launches onboarding, Agent, captures, or motors. Add
clean Debian ARM64/real Pi installation acceptance outside automated hardware tests.

**Gate and outcome:** common applicable gate, `bash -n` and ShellCheck for changed
shell scripts, installer regression suite, launcher tests from another directory.
The same underlying installation can be reached manually or through curl.

## Phase 3 — Wizard framework and configuration transactions

**Objective and scope:** add navigation, resumability, typed results, and existing
operation adapters before physical setup. Risk: private configuration only.

**Files:** new `setup_wizard/` modules, `setup_operations.py`, `agent_cli.py`,
IDE `config_import.py` only if shared transaction support is necessary; new
wizard state/CLI/transaction tests.

**Implementation:** implement the CLI/state/UX contracts above. Use an injected
console, clock, operation adapters, and fake component checks for testing.
Preflight current service mode, ownership, installed prerequisites, reboot needs,
and configuration before offering changes. Request stopping an existing Agent
before driver setup; detect systemd restart supervision and use existing
deployment controls rather than repeatedly killing a supervised process.

```python
for step in selected_steps:
    assessment = await step.inspect(context)
    choice = await ui.explain_and_choose(step, assessment)
    if choice.is_exit:
        return save_and_exit()
    if choice.is_skip:
        record_skip_without_changing_existing_configuration(step)
        continue
    result = await step.run_with_current_consent(context)
    verification = await step.verify(context, result)
    progress.record(step.id, verification)
    progress.save_atomically()
```

This is pseudocode, not an API commitment. Cancellation must reach adapter
cleanup before the wizard reports completion. Keep public state free of secrets.

**Testing:** help/aliases, no-TTY policy, navigation, retry, selected-step
dependencies, optional skip, mandatory defer, resume after interrupted writes,
concurrent wizard/config edits, malformed/future state, symlink rejection, and
full offline simulation rehearsal. Spy on shared operations to prove reuse.

**Gate and outcome:** common gate. A fake end-to-end wizard completes without
hardware or network and never marks simulated checks as physical success.
Draft developer documentation for state, API ownership, and recovery.

## Phase 4 — Required hardware setup and integrated import

**Objective and scope:** guide the five required devices in the requested order.
Risk: GPIO/SPI/I2C, audible output, display changes, servo movement, and camera
privacy. Managed driver edits are not planned.

**Files:** IDE `hardware_setup.py`, IDE public API/CLI exports as needed,
wizard hardware steps, configuration import tests, ownership/cleanup tests.

**Implementation:** the Agent calls a typed IDE setup request. IDE resolves a
fixed executable/argument list from the current installation, acquires
`HardwareOwnership`, and launches the existing standalone tool with the terminal
attached. Do not automate menus by feeding guessed answers. Use existing direct
setup commands where available, with the tool menu as the interactive handoff.
Explain exactly which menu items to choose. Reject arbitrary commands/paths.

| Required step | What and why | Reused action | Verification |
| --- | --- | --- | --- |
| Buzzer | Sound output; correct GPIO and silence after use | `pi5buzzer buzzer-tool`, Init, short tone | Saved GPIO config and IDE health; operator confirms audible tone and silence. |
| Display | Robot screen; wiring, geometry, rotation, brightness | `pi5disp display-tool`, Init/Text/Clear | Imported profile and display health; operator confirms orientation and readable test text. |
| Distance | Measures objects ahead; verify readings before calibration | `pi5vl53l0x sensor-tool` | Bounded valid reads against a known target; calibration remains driver-owned. `8191` is no target, not successful accuracy calibration; null/timeouts are faults. |
| Servo | Two wheel motors; individual neutral/stop values | `pi5servo servo-tool`, calibrate gpio12/gpio13 | Both saved records parsed; explicit raised-wheel confirmation for any movement; operator verifies stop and bounded low-speed test. File existence alone cannot pass calibration. |
| Camera | CSI camera; select supported capture settings | `pi5camera` setup/tool, doctor/status | Profile and device readiness; a temporary capture is offered only after consent, with cleanup. Distinguish no-capture readiness from image-quality verification. |

Hardware adapters must not instantiate the full integrated robot simply to check
one component: that could initialize unrelated devices. Use isolated existing
driver/IDE checks. Confirm which doctor/status commands actually open a device
and classify them accordingly. Automated tests replace all hardware boundaries.

Hold ownership until the tool and its descendants exit. On cancellation, request
normal interruption, allow bounded cleanup, reap the process, and run applicable
IDE stop/close handling. Escalating to kill is not proof of physical safety:
record unverified cleanup and instruct the operator to remove power if necessary.
Never release the lock while a surviving child can still touch hardware.

After the device sequence, call `discover_pi5_configs` and `import_pi5_configs`
against the existing effective configuration. Show imported fields and save with
`save_robot_config` only after confirmation. Preserve providers, optional
services, calibration source files, and unknown user edits by refusing conflicts.

**Testing:** exact command routing, no Agent driver imports, existing owner
conflict, failed child/cleanup, invalid calibration, missing config, mixed device
success, import preservation/idempotence, no motion from read-only checks, and
mandatory-gate behavior. Run each managed driver's suite independently.

**Gate and outcome:** common gate plus separate driver suites; immutable verifier
before and after the phase. Required setup has honest machine/operator evidence.
Document physical steps and troubleshooting in the new installation source.

## Phase 5 — Optional audio and AI provider setup

**Objective and scope:** add optional Bluetooth/mic paths and all four existing
model providers. Risk: audio services, recording, model downloads, and external
API data/costs.

**Files:** wizard audio/provider steps, shared setup operations, existing
Bluetooth/config/provider modules only for necessary extraction; provider-menu,
voice, and configuration tests; notices for any new dependencies.

**Audio implementation:**

- Bluetooth: explain speaker pairing, call `connect_wizard`, select the output,
  offer a low-volume sound check. Guide missing Lite audio prerequisites through
  existing documented steps. Preview opt-in reconnect service using
  `install_service(apply=False)` before applying it. Do not silently change
  lingering, WirePlumber policy, or system services.
- Microphone: offer skip before scanning/capturing. Reuse `pi5mic` standalone
  setup with the local `standalone` profile and `whisper_cpp`, avoiding its
  unrelated OpenClaw integration. Verify executable/model paths and supported
  capture format, then the installed ONNX wake model and supporting assets.
- The hardware installer already installs whisper.cpp/base. When missing,
  explain the existing installer repair/preview path instead of maintaining a
  second build script. Preserve the current manual install behavior.
- Import the supported mic/wake settings through existing config import. Ask
  separately before enabling ongoing wake listening. For a consented sample,
  reuse existing bounded capture/STT/wake routines and delete temporary media.
  Report configured, recorded, transcribed, and wake-detected separately.

**Provider implementation:**

| UI choice | Existing kind / secret | Guided sequence |
| --- | --- | --- |
| Ollama | `ollama`; local endpoint | Inspect daemon; list installed models; explicit user-selected pull if needed; explain size/storage; run existing benchmark; select accepted model. |
| Google | `gemini` / `GEMINI_API_KEY` | Link Google AI Studio setup, hidden key input, existing catalog, model selection, health, consented minimal generation test. |
| OpenAI | `openai` / `OPENAI_API_KEY` | Link API account/key setup, hidden key input, catalog/model selection, health, consented minimal generation test. |
| Anthropic | `anthropic` / `ANTHROPIC_API_KEY` | Link Claude API account/key setup, hidden key input, catalog/model selection, health, consented minimal generation test. |

Use `SecretStore`, `ConfiguredProviderRegistry`, `ModelManager`, and existing
selection persistence. Never ask users to type credentials in a shell command.
Explain inherited environment overrides without displaying their values. Keep
model lists dynamic; existing default names are not a promise of current account
availability. A saved key is not successful authentication, and model discovery
is not proof that generation works. Generation tests send only a fixed benign
prompt with no hardware tools, personal context, or retained conversation.

Official setup references: [Ollama CLI](https://docs.ollama.com/cli),
[Gemini keys](https://ai.google.dev/gemini-api/docs/api-key),
[OpenAI API quickstart](https://developers.openai.com/api/docs/quickstart), and
[Claude API overview](https://platform.claude.com/docs/en/api/overview).

**Testing:** mocked provider catalogs/health/generation, bad credentials,
429/timeouts, unavailable model, failed benchmark, interrupted pull, environment
precedence, no secret output, and fallback to the prior working selection.
Bluetooth and recording tests use fake runners/devices. Live API/audio checks
are explicit manual acceptance, never default pytest.

**Gate and outcome:** common gate and relevant voice/provider regressions.
Users can configure text-only operation, or opt into speaker/mic/voice features.
Update setup instructions and provider troubleshooting drafts.

## Phase 6 — External MCP tools

**Objective and scope:** multi-select Tavily, Google Calendar, and Notion, then
configure them sequentially. Risk: account permissions, private data, network,
and subprocess lifecycle. Initial presets expose reviewed read-only tools.

**Files:** `mcp_config.py`, `mcp_client.py`, `mcp_presets.py`, `mcp_oauth.py`,
external Calendar server, `agent_cli.py`, wizard MCP steps; corresponding
transport/OAuth/preset/Calendar tests and notices/manual updates.

**Shared implementation:** preserve existing MCP schemas/commands. Add preset
selection and additive `mcp login/logout/status` behavior where necessary so the
same setup is available manually. Keep credentials separate from `mcp.toml`.
Merge servers by ID; preserve custom servers and ask before replacing an
existing conflicting ID. Stage configuration, initialize the connection,
discover tools, compare them with the locally reviewed allowlist, perform a
consented bounded read, then enable. Failed optional tools can retry or be skipped.
An empty calendar/search result is a valid successful response.

External descriptions and returned content remain untrusted; discovery cannot
declare new tools safe. Do not enable write tools merely because OAuth grants
broader permissions. Preserve per-server time/result limits and failure isolation.

**Tavily:** reuse `tavily_server_config`, HTTPS endpoint and bearer-header key
handling. Explain account/key setup, store `TAVILY_API_KEY` privately, validate
`tavily_search`, and show status without result bodies or credentials in logs.
Tavily documents header authentication in its
[MCP guide](https://docs.tavily.com/documentation/mcp); never put the key in a URL.

**Google Calendar:** package the existing tutorial's external read-only stdio
pattern as a supported subprocess. It is external to the Agent runtime through
the MCP transport, even though this project supplies its adapter. Launch with
the absolute installed Python path and `-m ...external_mcp.google_calendar`;
no shell, copied scripts, or unpinned third-party executable.

Reuse `calendar_oauth.authorize(write=False, ...)` for browser consent and
`GoogleCalendarBackend` for bounded HTTP and refresh, storing a distinct MCP
credential reference. Configure the API, consent screen, test users where needed,
and Desktop OAuth client using the existing headless SSH loopback workflow.
Support the documented `list_today_events(time_zone, max_results)` contract,
with valid IANA timezone and limit 1–20. Return bounded summaries/start/end,
omitting attendees, descriptions, conference links, and unnecessary identifiers.
The subprocess gets access only to its Calendar credential store, not all Agent
secrets. Never register it as a native Calendar connection or reuse another
user's native credential implicitly.

Google now documents a hosted Calendar MCP server, but it requires Developer
Preview enrollment. Do not make that a prerequisite for ordinary onboarding;
the existing external stdio design remains the proposed baseline. This choice
avoids duplicating Calendar HTTP/OAuth logic while satisfying external MCP use.
Sources: [Google Calendar setup](https://developers.google.com/workspace/calendar/api/quickstart/python)
and [hosted MCP prerequisites](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server).

**Notion:** use maintained `https://mcp.notion.com/mcp` with OAuth. Its old
self-hosted token server is no longer actively maintained, and a Notion
integration token is not a substitute for hosted MCP OAuth, per the
[Notion connection guide](https://developers.notion.com/guides/mcp/get-started-with-mcp).

Add an OAuth authentication option compatible with existing bearer/stdio config.
Use the already locked MCP SDK 1.28.1 `OAuthClientProvider` and `TokenStorage`
interfaces, rather than implementing OAuth cryptography or upgrading to SDK v2.
Implement private atomic storage, expiry/refresh, PKCE/state validation, a
bounded loopback callback, SSH instructions, and explicit reauthorization.
Restrict metadata/authorization/token endpoints to reviewed HTTPS origins and
validate issuer/resource association; reject redirects or metadata that would
send credentials to arbitrary/private hosts. Bind tokens to the server and
connection, and serialize refreshes. Service startup may refresh a credential
but must never initiate browser login automatically. Follow
[Notion's client requirements](https://developers.notion.com/guides/mcp/build-mcp-client)
and the [locked SDK OAuth implementation](https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/v1.28.1/src/mcp/client/auth/oauth2.py).

Start with reviewed Notion search/fetch tools only. Verify exact names and schemas
against current official tool documentation before freezing the preset; tool
drift must fail closed with a helpful message, not widen the allowlist. Explain
workspace access, then validate a user-approved small read without logging page
contents. Account consent may be broader than local tool access; state that clearly.

**Testing:** fake stdio MCP server and mock HTTPS/OAuth endpoints; successful
handshake, discovery, allowed read, denied write, unknown tool, OAuth denial,
state mismatch, expired/refreshed token, revoked scope, callback timeout, metadata
redirection/SSRF attempts, credential separation, redaction, oversized results,
child cleanup, restart, and per-server degradation. Calendar contract tests must
prove existing transport reuse and no native connection/database registration.
Preserve regression tests for native Calendar CONFIRM and manual MCP commands.

**Gate and outcome:** common gate, isolated MCP protocol integration tests, and
manual account tests explicitly marked pending until performed. All three
selections appear as external MCP providers, individually ready/skipped/failed.
Update the full MCP manual as well as installation/developer source drafts.

## Phase 7 — ngrok, local HTTPS, services, and final launch

**Objective and scope:** configure optional remote access and deliver the two
completion options. Risk: authenticated LAN/public access, service lifecycle,
and real-startup motion/voice effects.

**Files:** wizard remote/launch steps, shared setup operations, `agent_cli.py`,
`remote_access.py`, `service_main.py`, `web_app.py`, existing `onboarding.py`
only for necessary reuse or explicit startup options; deployment/remote tests.

**Remote flow:** explain ngrok as an outbound tunnel, link
[ngrok account/setup](https://ngrok.com/docs/start), prompt privately for the
authtoken twice, and reuse existing binary installation, private token/config,
pairing secrets, activation, and health checks. Display account/connection errors
without raw upstream bodies. Do not bypass pairing or open router ports.

Distinguish `configured` from `verified public endpoint`. Before final launch,
offer a consented temporary connection test through the existing remote manager
with a loopback HTTPS test target that exposes no robot actions. Close tunnel
and target deterministically afterward. The final running service must verify
its own endpoint again. If the temporary test is declined, show validation pending.
No test Agent or hardware startup is needed just to validate a token.

When ngrok is skipped, configure authenticated same-Wi-Fi HTTPS at launch using
existing local pairing/session machinery. The current web app's local pairing
requirement is conditional: do not assume binding port 8443 alone is sufficient.
Enable the existing startup-pairing path for newly onboarded configurations,
without redefining `OnboardingConfig` or changing existing manual defaults.
Preserve the current healthy-ngrok/local-fallback exclusivity and degrade safely
to authenticated local access on tunnel failure. Check HTTPS/authentication,
not merely a listening port.

**Services:** explain "start now" versus "start automatically on boot". Preview
existing deployment output, and apply/enable boot startup only after a separate
explicit selection. Default remains manual startup. Show reboot requirements
from installation and offer save/exit rather than initiating reboot or power-off.

**Completion:** show required readiness, provider/model, optional selections,
skips, failed/pending checks, and any services configured to persist. Offer:

1. Start NinjaRobot Agent: choose simulation (default) or real hardware. Recheck
   current service mode/configuration and reuse a matching instance; never treat
   `_spawn_service` returning "already running" as proof it has the requested
   mode. A mismatch needs an explicit stop/restart. Real mode requires mandatory
   readiness, fresh raised-wheel/operator confirmation, and disclosure of existing
   Greeting and enabled microphone behavior. Do not automatically grant session
   motion arms or camera consent. Start through the shared service operation,
   wait for genuine readiness, start/verify web access, then enter `_chat_repl`.
2. Exit Onboarding: save progress, close wizard-owned temporary resources, print
   exact commands for later use, and leave the Agent stopped if the wizard had
   stopped it for setup. Do not disable unrelated pre-existing services.

Explain that leaving chat does not stop the independently running Agent, matching
the current CLI contract, and show the existing service-stop command.

**Testing:** skip-ngrok LAN startup, authenticated requests/denied anonymous
requests, successful/failed tunnel, token configured but not verified, temporary
test cleanup, no router changes, wrong-mode running service, startup not-ready,
timeout cleanup, repeated launch, simulation isolation, and exit-without-launch.
No test executes systemd/sudo/boot edits on the host. Live public endpoint and
phone-on-Wi-Fi acceptance require explicit operator testing.

**Gate and outcome:** common gate plus remote/deployment/service tests. The
completion screen reports actual readiness and enters existing chat only after
successful launch. Draft beginner launch, pairing, fallback, and rollback docs.

## Phase 8 — Documentation, regression, and acceptance

**Objective and scope:** make both installation/setup paths supportable and
publish an honest validation handoff. Risk: documentation accuracy; physical
acceptance remains explicit.

**Files:** root and wiki READMEs; NEW versions of `InstallationGuide.md`,
`DevelopmentGuide.md`, `NinjaRobot_MCP_Skill.md`, and `DevelopmentLog.md`; affected
wiki concepts/reference pages and `project-knowledge.json`; project-help source
mapping/manifests if public manual retrieval requires it; notices; validation
evidence under `docs/validation/`.

**Documentation:** show curl installation first and retain clone/manual steps.
Explain preview/check, revision pins, reboot/reconnect, command PATH, onboarding
resume, each device, credential setup, external MCP choices, Shift+Enter fallback,
LAN versus remote access, service persistence, simulation limitations, privacy,
and recovery. Retain existing command anchors and native Calendar instructions.
Do not put full manuals back at the checkout root.

Create successor raw sources; never edit registered originals. Review source and
implementation diffs and classify new files before updating fingerprints.
Prepare and display the exact semantic wiki plan with `plan validate` and
`plan diff`. Obtain approval for that specific diff before `plan apply --approve`;
approval of this implementation plan alone does not approve a future unseen wiki
diff. Record actual AI review results without claiming human verification.
Run wiki check/lint/link/index validation once its explicitly set-up environment
is available. Report unresolved warnings.

**Common implementation gate:** after every phase, run applicable checks in the
project's frozen environment, with immutable verification before and after
implementation. Repair in-scope failures before continuing and identify baseline
failures accurately.

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

Run managed-driver pytest suites in separate processes. Add shell syntax/static
checks, package build/entry-point checks, clean-install tests, documentation-link
checks, and architecture tests where relevant. No live API, hardware, or service
mutation in default tests. Use mocked subprocesses and disposable configuration
homes. Do not regenerate the immutable baseline; any unavoidable driver edit
requires separate owner authorization, independent tests, and the authorized
change record before proceeding.

Regression coverage must include existing install profiles/options, driver
manual setup, IDE config import, model/provider menus, chat slash commands,
service start/status/stop, native Calendar confirmations, existing MCP servers,
remote pairing/local fallback, deployment previews, and simulation.

### Manual acceptance checklists

| Checklist | Procedure and expected outcome | Rollback/recovery |
| --- | --- | --- |
| Safe smoke | Fresh install preview, help/status, offline rehearsal, chat cursor/paste tests, resume/exit; no device action or unexpected service | Exit; remove only test scratch files; preserve private configuration. |
| Device communication | On Pi, complete one component at a time; valid status/readings and correct screen/sound; consented temporary camera/mic samples | Stop the component/Agent; restore the reviewed prior config; delete wizard-owned sample media. |
| Actuator-moving | Raise wheels, keep operator at power, calibrate both neutrals, bounded low-speed test, explicit stop, cancel/retry, real startup Greeting | Stop/disarm via existing controls; remove power if physical state is uncertain; restore calibration only after inspection. |
| Power-risk | Preview boot/service changes and backups; operator-controlled reboot only after review; no power-off test required for this feature | Restore the installer boot backup through the documented manual procedure; disable only the newly enabled service. |
| Accounts/network | Consented provider test, three external MCP reads, Notion refresh, ngrok endpoint, phone on same Wi-Fi, unauthenticated rejection | Disconnect/disable only the selected connection; close tunnel; retain local authenticated access; revoke credentials through the provider when requested. |

Record tested OS, terminal/SSH client, Python/dependency versions, mode, expected
and actual outcome, and pass/fail/not-run without recording credentials or private
content. Clean installation acceptance must cover a fresh Raspberry Pi OS Lite
image, rerun, interrupted download, reboot and readiness check. Container tests
cannot certify PWM overlays, camera bridge operation, or actual device safety.

**Completion criteria:** all approved features and manual paths work through the
same underlying operations; automated gates pass; documentation accurately
reflects implementation; mandatory/optional status is truthful; and outstanding
physical/account acceptance is explicitly listed. No push, release, PR, or public
installation URL publication is authorized by this plan.

## Approval requested

Approve Phases 1–8 as the implementation scope, including the small external
Calendar MCP subprocess and SDK-based Notion OAuth extension. Approval starts
repository implementation only. Runtime hardware/account confirmations remain
part of the user-facing wizard, and the eventual exact semantic wiki diff has
its separate review gate.
