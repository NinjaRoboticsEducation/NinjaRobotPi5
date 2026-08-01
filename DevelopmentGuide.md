# NinjaRobotPi5 Development Guide

This guide is the single source of truth for developers, maintainers, and AI coding agents working on NinjaRobotPi5. When this guide conflicts with the implementation plan, [`NinjaRobotPi5V4_ImplementationPlan.md`](NinjaRobotPi5V4_ImplementationPlan.md) takes precedence.

---

## 🏗️ Architecture Overview

### The Three-Layer Boundary Model

NinjaRobotPi5 enforces a strict, one-directional dependency boundary:

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 3 — ninjarobot_pi5_agent                                  │
│                                                                  │
│  • User interaction: conversational CLI, HTTPS web controller    │
│  • AI providers: Ollama, OpenAI, Gemini, Anthropic               │
│  • Extension: MCP tool protocol, Agent Skills                    │
│  • Policy, prompt composition, session and transcript management │
│                                                                  │
│  ✗ Never imports any pi5* package directly                       │
│  ✗ Never opens GPIO, I2C, SPI, camera, or audio                  │
│  ✓ Calls hardware only through IDE capability contracts          │
├──────────────────────────────────────────────────────────────────┤
│  Layer 2 — ninjarobot_pi5_ide                                    │
│                                                                  │
│  • Capability registry, resource scheduler, action ledger        │
│  • Behavior system: face renderer, stages, safety engine         │
│  • Configuration import from standalone pi5* JSON files          │
│  • Hardware ownership lock (OS file lock)                        │
│                                                                  │
│  ✓ One lazy driver import per adapter module                     │
│  ✗ Never exposes raw driver objects outside the IDE              │
├──────────────────────────────────────────────────────────────────┤
│  Layer 1 — Managed pi5* Driver Libraries                         │
│                                                                  │
│  pi5servo  pi5disp  pi5buzzer  pi5vl53l0x  pi5camera  pi5mic    │
│                                                                  │
│  • Each library is an independently testable project             │
│  • Own pyproject.toml, uv.lock, README, and test suite           │
│  • Standalone CLI tools for hardware setup and calibration        │
└──────────────────────────────────────────────────────────────────┘
```

### Why This Boundary Exists

The boundary has three concrete safety consequences:

1. **The AI model cannot reach hardware.** The agent may propose a robot action; the IDE decides whether to execute it. The IDE may refuse based on safety state, calibration, arming, or resource availability — regardless of what the model says.

2. **Hardware has exactly one owner.** An OS file lock (`~/.local/state/ninjarobot_pi5/hardware-owner.lock`) prevents a second agent or IDE process from opening GPIO, I2C, SPI, PWM, camera, or audio while a first process owns them. Driver failure, crash, or process exit releases the lock automatically.

3. **Cloud providers are translation-only.** OpenAI, Gemini, and Anthropic adapters convert the same provider-neutral `ModelRequest` into each provider's API format and return a `ModelTurn`. They never execute a tool, access a driver, or bypass policy.

---

## 📁 Repository Layout

```text
NinjaRobotPi5/
├── ninjarobot_pi5_ide/
│   ├── src/ninjarobot_pi5_ide/
│   │   ├── adapters/           Per-device adapter modules (buzzer, camera, display, …)
│   │   ├── behavior_assets.py  Bundled and private behavior catalog
│   │   ├── behavior_models.py  Strict immutable stage/operation definitions
│   │   ├── behavior_runtime.py Ordered-stage, concurrent-operation executor
│   │   ├── camera.py           Privacy-bounded camera adapter
│   │   ├── cli.py              ninjarobot-ide-tool entry point
│   │   ├── config.py           V4 configuration schema (TOML)
│   │   ├── config_import.py    Preview-first import from standalone pi5* JSON files
│   │   ├── contracts.py        Shared data contracts (capabilities, results, errors)
│   │   ├── face_renderer.py    Procedural Pillow face animations
│   │   ├── interactive_tool.py Blessed-style direct-control menus
│   │   ├── robot.py            Shared RobotAssembly (all devices in one object)
│   │   ├── runtime_control.py  Owner-private active-process registration
│   │   ├── safety.py           Motion guard, watchdog, stop levels, recovery
│   │   └── scheduler.py        ResourceScheduler and ActionLedger
│   └── pyproject.toml
│
├── ninjarobot_pi5_agent/
│   ├── src/ninjarobot_pi5_agent/
│   │   ├── providers/          OllamaProvider, OpenAIProvider, GeminiProvider, AnthropicProvider
│   │   ├── agent_loop.py       Main AI turn loop, tool routing, camera-intent boundary
│   │   ├── benchmark.py        Ollama performance and safety benchmark
│   │   ├── camera_grant.py     Repeatable one-photo AI camera consent manager
│   │   ├── cli.py              ninjarobot-agent entry point
│   │   ├── google_oauth.py     Legacy OAuth migration shim (API-key migration only)
│   │   ├── ipc_server.py       Owner-only Unix-domain socket service
│   │   ├── mcp_config.py       MCP server catalog loader and validator
│   │   ├── model_manager.py    Provider-neutral model selection and hot-switching
│   │   ├── motion_arm.py       Session-lived motion authorization manager
│   │   ├── policy.py           Tool call policy engine
│   │   ├── prompts.py          PromptComposer — ordered system prompt builder
│   │   ├── robot_mcp.py        Trusted in-process robot-control MCP façade
│   │   ├── secrets.py          SecretStore — owner-only, atomic, redacted
│   │   ├── skills.py           Skill validation, confinement, and registry
│   │   └── web_app.py          FastAPI HTTPS controller and WebSocket lease
│   └── pyproject.toml
│
├── pi5buzzer/                  Standalone buzzer library (independent project)
├── pi5camera/                  Standalone camera library (independent project)
├── pi5disp/                    Standalone display library (independent project)
├── pi5mic/                     Standalone microphone library (independent project)
├── pi5servo/                   Standalone servo library (independent project)
├── pi5vl53l0x/                 Standalone distance-sensor library (independent project)
│
├── config/
│   └── ninjarobot_pi5.toml.example   Authoritative V4 configuration example
│
├── docs/
│   ├── architecture/           Architecture and driver-containment records
│   ├── adr/                    Architecture Decision Records
│   ├── hardware/               Hardware mapping, wiring, and electrical records
│   └── validation/             Phase validation checklists and authorized driver changes
│
├── scripts/
│   ├── bootstrap-rpi-camera-workspace.sh   Camera bridge setup
│   ├── verify_immutable_drivers.py         Driver SHA-256 checksum verification
│   └── verify_workspace_driver_sources.py  Editable-source path verification
│
├── tests/                      Root integration and governance tests
├── pyproject.toml              Root project — orchestrates all packages
├── uv.lock                     Locked dependency graph
└── NinjaClawBot/               ← Ignored historical reference; never imported by V4
```

---

## 🔧 Development Environment Setup

### Prerequisites

| Tool | Version | How to install |
|---|---|---|
| Python | 3.11 | `uv python install 3.11` |
| `uv` | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Git | Any recent | `sudo apt install git` |

### First-Time Setup (Simulation — No Hardware)

```bash
git clone --branch NinjaPi5Agent --single-branch \
  https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git
cd NinjaRobotPi5

# Install all Python dependencies (hardware packages excluded)
uv sync --frozen

# Verify the environment
uv run --frozen ninjarobot_pi5_cli --version
uv run --frozen ninjarobot_pi5_cli capabilities
uv run --frozen ninjarobot_pi5_cli dry-run \
  --capability system.echo \
  --json '{"message":"hello"}'
```

`dry-run` never opens GPIO, I2C, SPI, camera, or audio. The result must include `"simulated": true`.

### First-Time Setup (With Hardware — Raspberry Pi Only)

```bash
# Install hardware packages
uv sync --frozen --extra hardware

# Verify all six managed drivers resolve to this checkout
uv run --frozen --extra hardware python \
  scripts/verify_workspace_driver_sources.py

# Verify all driver checksums match approved records
uv run --frozen python scripts/verify_immutable_drivers.py

# Set up the camera bridge (first time only)
./scripts/bootstrap-rpi-camera-workspace.sh
```

### Running the Test Suite

```bash
uv run --frozen pytest -q
```

Hardware tests are excluded from the default run. They are in a `hardware` pytest marker group and require an explicit include flag on the Raspberry Pi.

---

## ✅ Root Quality Gate

Run this full gate before merging any change. Every check must pass.

```bash
# 1. Driver provenance
uv run --frozen python scripts/verify_immutable_drivers.py

# 2. Syntax
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests

# 3. Lint
uv run --frozen ruff check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests

# 4. Format
uv run --frozen ruff format --check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests

# 5. Static type checking
uv run --frozen mypy \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src

# 6. Tests
uv run --frozen pytest -q

# 7. No trailing whitespace or merge conflicts
git diff --check
```

Strict mypy typing is mandatory for `ninjarobot_pi5_ide` and `ninjarobot_pi5_agent`. It does not apply to the independently maintained `pi5*` libraries.

---

## 🚦 Development Workflow

1. **Read** the relevant phase in `NinjaRobotPi5V4_ImplementationPlan.md` and any related Architecture Decision Records (ADRs) in `docs/adr/`.
2. **Review** the affected code using Serena or your preferred editor.
3. **Present** your plan and obtain explicit approval before writing code.
4. **Implement** only the V4-owned files or the approved driver repair.
5. **Run** focused tests, then the complete root quality gate.
6. **Verify** driver provenance and authorized repair hashes.
7. **Update** `README.md`, this guide, and any relevant documentation.
8. **Prepare** a Raspberry Pi checklist for hardware-facing changes.
9. **Stop** for review before starting the next phase.

---

## 🔒 Managed Driver Policy

### What "Managed Driver" Means

The six `pi5*` directories are **managed copies** of historical standalone libraries. They exist in this repository so V4 can:

- Lock their exact source content with SHA-256 checksums
- Run their tests in isolation with their own lockfiles
- Ship them as editable path dependencies — never as copied wheels

They are **not** V4 sub-packages. They remain independent projects with their own `pyproject.toml`, lockfiles, and test suites.

Because the drivers are editable path dependencies, a pulled or locally authorized repair is immediately visible without any stale wheel hiding an old copy.

### Prohibited Operations

| Prohibited action | Why |
|---|---|
| `import pi5servo` (or any `pi5*`) inside `ninjarobot_pi5_ide` or `ninjarobot_pi5_agent` | Breaks the containment boundary; drivers are reached only through IDE adapter contracts |
| Editing a `pi5*` source file without recording an authorization | The SHA-256 baseline check will fail the quality gate |
| Adding a `pi5*` directory as a `[tool.uv.sources]` workspace member | Drivers are editable path dependencies, not workspace members |
| Running `uv sync` inside a `pi5*` folder for normal NinjaRobotPi5 use | Use the root environment; package-local environments are for standalone driver validation only |
| Importing or running `NinjaClawBot/` code | That directory is strictly read-only historical reference |

### How to Propose a Driver Change

1. Reproduce the failure and document the root cause.
2. File an issue describing the defect and proposed fix.
3. Get maintainer approval **before writing code**.
4. Apply the minimal fix inside the affected `pi5*` directory.
5. Run the driver's own isolated test suite (see [Driver Package Validation Commands](#-driver-package-validation-commands)).
6. Record the changed file with the authorized hash tool:

```bash
uv run python scripts/verify_immutable_drivers.py \
  --record-authorized pi5example/path/to/file.py \
  --reason "Concise root cause and validated repair summary"

uv run python scripts/verify_immutable_drivers.py
```

7. Run the root governance test:

```bash
uv run --frozen pytest tests/test_repository_governance.py -q
```

8. Submit the PR with the driver fix, the updated authorization manifest, and the test run output.

> [!CAUTION]
> Never use `--record-authorized` to silence a hash mismatch caused by an accidental edit. The original hashes in `immutable_driver_baseline.json` are permanent and must never be regenerated after repairs. Only `authorized_driver_changes.json` records the approved repaired state.

---

## ⚙️ Configuration System

### Schema Overview

The integrated robot configuration lives in `~/.config/ninjarobot_pi5/config.toml`. The source schema is in `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config.py`.

The example at `config/ninjarobot_pi5.toml.example` is the authoritative reference for the current hardware profile:

- GPIO12/GPIO13 servos (MG90D continuous-rotation, motion disabled by default)
- GPIO27 buzzer
- ST7789V display on DC4/RST5/BL6, rotation 90°, brightness 75%
- Fixed-focus OV5647 camera at 1280×720, retention disabled by default
- USB PnP microphone at 16 kHz (actual rate may fall back to 44.1 kHz)

Validate any configuration file:

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example
```

### How Configuration Flows Between Layers

```
Standalone pi5* JSON files  →  IDE importer (preview-first, read-only)
        ↓                               ↓
~/.config/pi5*/             →  ~/.config/ninjarobot_pi5/config.toml
                                        ↓
                            ninjarobot_pi5_ide reads TOML at startup
                                        ↓
                            IDE adapters use settings to initialize drivers
```

The import is **one-way**. The standalone JSON files never change when you run `config import`. The integrated TOML never changes when you use a standalone tool.

### Canonical Standalone Configuration Paths

| Library | Canonical config file |
|---|---|
| `pi5buzzer` | `~/.config/pi5buzzer/buzzer.json` |
| `pi5camera` | `~/.config/pi5camera/camera.json` |
| `pi5disp` | `~/.config/pi5disp/display.json` |
| `pi5mic` | `~/.config/pi5mic/mic.json` |
| `pi5servo` | `~/.config/pi5servo/servo.json` |
| `pi5vl53l0x` | `~/.config/pi5vl53l0x/vl53l0x.json` |

> [!IMPORTANT]
> Always pass the explicit canonical path when using a library for integrated NinjaRobotPi5. Some tools create their JSON in the current directory if you omit the path. `pi5disp` uses the `PI5DISP_CONFIG` environment variable.

### IDE Configuration Import and Synchronization

First import (new file):

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"

uv run --frozen ninjarobot-ide-tool config discover
uv run --frozen ninjarobot-ide-tool config import \
  --destination "$NINJAROBOT_CONFIG"          # preview — nothing written
uv run --frozen ninjarobot-ide-tool config import \
  --destination "$NINJAROBOT_CONFIG" \
  --apply                                     # write the file
chmod 600 "$NINJAROBOT_CONFIG"
```

After changing a standalone configuration, synchronize with `--overwrite`:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" \
  config import \
  --destination "$NINJAROBOT_CONFIG"            # preview first
uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" \
  config import \
  --destination "$NINJAROBOT_CONFIG" \
  --apply \
  --overwrite                                  # write
uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$NINJAROBOT_CONFIG"
```

The preview returns `"applied": false` by design — it is not a failure.

---

## 🦺 Safety and Security Architecture

### Hardware Ownership Lock

`RobotAssembly` claims `~/.local/state/ninjarobot_pi5/hardware-owner.lock` with a non-blocking OS file lock at startup. A second agent or real IDE process receives a clear ownership error before opening any device. Process exit releases the lock even after a crash. Standalone `pi5*` tools do not use this lock — stop the agent and IDE before running a standalone hardware tool.

### Policy Engine and Tool Trust

Every tool call passes through `PolicyEngine.evaluate()` before reaching the IDE or any external server. The policy engine checks:

- Tool name against the allowlist
- Session arming state (for motion tools)
- Privacy confirmation (for camera and microphone)
- Input against the tool's JSON Schema

The model's output is an **untrusted proposal**. The policy engine makes the final decision. External MCP tool results are also untrusted — they can never elevate permissions or bypass IDE safety.

### Motion Arming and Session Scope

`MotionArmManager` holds session-lived consent rather than a wall-clock timeout. This prevents a valid arm from expiring while a small local model is reasoning.

Motion authorization is revoked by:
- Explicit `/disarm` command
- Emergency Stop
- Controller browser disconnection
- Model replacement
- Service shutdown

Runtime disarm also cancels any in-flight motion tokens and requests `robot.servo.stop` — it does not merely block the next tool call.

### Safety Stop Levels

**Level 1** — stops servo movement only and blocks another movement:

- Triggers: three consecutive front-obstacle readings ≤ 50 mm, Raspberry Pi undervoltage, software watchdog timeout
- Recovery: `ninjarobot-ide-tool motion resume --confirm`

**Level 2 (Emergency Stop)** — stops servos and ranging, closes camera and microphone, silences the buzzer, and displays a red octagonal Emergency Stop sign:

- Triggers: Ctrl+C, explicit behavior stop, shutdown cleanup, hardware driver failure
- Recovery: `ninjarobot-ide-tool system resume --confirm` (or `/resume` in chat)
- Recovery checks every configured module by health probe — refuses to clear the latch if any probe fails

Invalid generated behavior arguments, oversized display text, policy rejections, and configuration mistakes return ordinary action errors and **do not** create a Level 2 latch.

### Secret Storage

`SecretStore` stores API keys and sensitive values in `~/.config/ninjarobot_pi5/secrets.env`:

- Created with mode `0600` (owner-read/write only)
- Written atomically using `tempfile` + `rename`
- Reports presence of a key without revealing its value
- Redacts known secret values from nested error diagnostics
- `provider logout` removes only the selected provider's saved key

The web interface never accepts provider secrets. The terminal uses hidden, double-entry prompts.

### Prompt Composition Order

`PromptComposer` assembles the system prompt in this fixed order:

1. Immutable safety rules
2. Robot identity
3. Current health, controller lease, and arming state
4. Selected Skill instructions (if any)
5. Conversation context

External text, MCP results, and Skill instructions cannot precede or replace the safety rules.

---

## 🤖 IDE — Core Modules and Responsibilities

### CapabilityRegistry

Registers one unique adapter per capability and owns startup, health, and close ordering. Prevents two adapters from registering the same capability name.

### ResourceScheduler

Bounds concurrent and waiting work. Locks shared resources in sorted order to prevent deadlock. Example: the display, SPI0, and GPIO4/GPIO5/GPIO6 are claimed together by every display operation.

### ActionLedger

Stores accepted, running, and completed actions in SQLite. Enforces idempotency: repeating the same action ID and idempotency key returns the stored result without re-executing. An action that was running at restart is recorded as unknown outcome; the caller must decide whether to retry.

### ExecutionEngine

Enforces deadlines, timeouts, cancellation, restart recovery, and normalized error codes. Returns structured failures for timeouts, queue full, cancelled, and unknown outcomes.

### BehaviorRuntime

Executes ordered stages with concurrent operations. A stage may contain one display operation, one buzzer operation (existing melody or one bounded tone), one drive operation, and one wait. Tone frequency is limited to 20–20,000 Hz, duration to 0.05–2 seconds, and volume to 1–128.

### FaceRenderer

Procedural Pillow-based face animations. All 20 expressions are independently implemented. Each renderer scales from the configured display dimensions and uses elapsed time to produce successive frames. A finite expression remains bounded; an interactive face loops until replaced or stopped.

### SafetyStateStore

Persists the safety latch in `~/.local/state/ninjarobot_pi5/safety.json`. Uses `threading.Lock` for atomic state access. Returns a full latch on any parse error — fail-closed.

### WatchdogThread

A daemon thread that calls the servo zero-pulse path directly if the main asyncio event loop stops updating within its timeout. Tested with both a frozen event loop and a legitimately slow servo ramp.

---

## 🧑‍💻 Agent — Framework Design

### AgentIPCServer

Binds an owner-only Unix-domain socket at `~/.local/state/ninjarobot_pi5/agent.sock`. CLI processes connect to the running service; quitting a CLI terminal does not release service resources. The service owns the Ollama connection, the in-process IDE client, the tool registry, MCP sessions, SQLite transcripts, motion arms, and the optional FastAPI web server.

### ToolProvider Protocol

All tool sources — IDE capabilities, the trusted robot-control MCP façade, and external MCP servers — implement the same protocol:

```python
class ToolProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    async def start(self) -> None: ...
    async def list_tools(self) -> tuple[ToolDefinition, ...]: ...
    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult: ...
    async def health(self) -> ProviderHealth: ...
    async def close(self) -> None: ...
```

Required behaviour: deterministic lifecycle, idempotent close, collision-safe names, strict input validation, bounded time and result size, cancellation propagation, declared source and trust level.

### Trusted Robot-Control MCP Façade (`RobotControlMCPProvider`)

A fixed, in-process MCP server owned by the agent service. Unlike external MCP servers, its manifest is project source, its tools are classified from authoritative IDE descriptors, and its trust level is `TRUSTED`.

| Agent tool | IDE capability | Purpose |
|---|---|---|
| `robot.behavior.catalog` | `behavior.list` | List validated behaviors |
| `robot.behavior.preview` | `behavior.preview` | Compile to canonical IDE format without hardware |
| `robot.behavior.execute_expression` | same (no `robot.` prefix) | Run face/text/buzzer stages |
| `robot.behavior.execute_movement` | same (no `robot.` prefix) | Run motion combinations after session arming |
| `robot.behavior.stop` | `behavior.stop` | Request the existing Level 2 stop |

The façade validates each call against the IDE JSON Schema, creates an `ActionRequest`, and returns the IDE's authoritative normalized result. It does not own or close the IDE — the primary IDE provider owns that lifecycle.

### LLMProvider Protocol and Cloud Adapters

All model providers implement the same `LLMProvider` protocol. The common boundary:

```
PromptComposer + selected Skill
      |
ToolRegistry: robot.* + allowlisted mcp.*
      |
  ModelRequest
      |
selected LLMProvider adapter
      |
   ModelTurn
      |
PolicyEngine → ToolRegistry → IDE, robot MCP, or external MCP
```

Cloud adapters use documented HTTPS JSON and Server-Sent Events endpoints:

- **OpenAI**: Responses API with `store=false`, manual function calls, streamed text deltas, `GET /v1/models`
- **Gemini**: `generateContent`/`streamGenerateContent`, function declarations without callable Python functions, filtered model list
- **Anthropic**: Messages API, streamed content blocks and `tool_use` JSON, paginated Models API

Cloud adapters can **propose** tools but cannot **execute** them. The existing policy and registry remain the only execution path.

### MCP Client Configuration

MCP servers are configured in `~/.config/ninjarobot_pi5/mcp.toml`. The format for a remote (Streamable HTTP) server:

```toml
[[servers]]
id = "example"
enabled = false
transport = "streamable_http"
url = "https://mcp.example.com/mcp"
authentication = "bearer_environment"
token_environment = "EXAMPLE_MCP_TOKEN"
allowed_tools = ["search"]
timeout_seconds = 20.0
max_result_bytes = 131072
```

For a local `stdio` server:

```toml
[[servers]]
id = "example-local"
enabled = false
transport = "stdio"
command = "/absolute/path/to/example-mcp-server"
args = []
allowed_tools = ["lookup"]
timeout_seconds = 20.0
max_result_bytes = 131072
```

Rules:
- Remote bearer credentials name an environment secret — never the secret itself
- `stdio` commands use absolute paths; no shell pipelines, redirection, or command substitution
- A failed server degrades only its own tools and never stops the IDE or agent service
- MCP tool descriptions, annotations, resources, prompts, and results are **untrusted**

Restart the agent service after changing the MCP catalog.

### Agent-Skill Package

A skill is a confined directory of data and instructions — not executable code:

```text
skill-id/
├── skill.json          Schema version, ID, version, tools, limits, safety metadata
├── instructions.md     Plain-language task guidance only
└── examples.json       Optional simulation examples
```

The prompt composer inserts selected Skill instructions **after** the immutable safety rules. External text and Skill instructions cannot precede or replace safety rules.

Skill validation rejects: unknown fields, executable code, symlinks, absolute paths, parent traversal (`../`), oversized files, excessive directory depth, unknown tools, and attempts to weaken safety. A skill can only **reduce** the allowlisted tools and execution budget — it cannot add a permission.

Built-in skills are read-only package assets. User skills live under `~/.config/ninjarobot_pi5/skills/`.

### BehaviorDraftCompiler

The single compatibility boundary between variable model output and the strict Phase 4 behavior schema. Accepts both the full canonical saved format and a smaller transient draft:

```json
{
  "name": "exciting_forward",
  "description": "Move briefly while looking excited.",
  "stages": [
    {
      "face": "exciting",
      "melody": "exciting",
      "movement": "move_forward",
      "duration_seconds": 1
    }
  ]
}
```

The compiler:
- Assigns missing stage names
- Resolves named movement assets through configured logical servo roles
- Converts note names (e.g., `C5`) to frequency
- Recognizes documented melody aliases
- Supplies a default one-second duration for transient movements
- Separates display or buzzer conflicts into ordered stages

Invalid model output raises `BEHAVIOR_DRAFT_INVALID` with field-specific correction guidance and `definitely_not_executed: true`. The agent can repair the JSON without guessing whether hardware moved.

### Deterministic Camera-Intent Boundary

`AgentLoop` intercepts explicit English and Japanese capture requests before the first model turn. A recognized request is resolved directly through the trusted `robot.camera.preview` tool — the AI model is not consulted. This prevents model refusals from overriding a valid current camera grant.

The matching is conservative: it recognizes explicit requests to take a photo and rejects camera questions and negated requests. Any new language form needs positive, negative, no-grant, failure, and redaction tests before merging.

### HTTPS Web Controller

- Started and stopped through IPC — cannot create a second IDE or hardware owner
- Generated local CA + `.local` server certificate stored under `~/.config/ninjarobot_pi5/tls/`
- One exclusive WebSocket controller lease — a second browser receives HTTP `423 Locked`
- A missed heartbeat revokes the lease and requests `robot.servo.stop`
- D-pad controls, Emergency Stop, Resume, Greeting, Celebrate, AI camera, USB speech transcription, and browser speech recognition

The D-pad rows use the height allocated by the parent grid, preventing overlap with camera and microphone controls in short non-fullscreen viewports. iPhone/iPad users should use **Add to Home Screen** for the most reliable standalone portrait view.

---

## 📐 Behavior System

### Behavior Format

A behavior contains one or more ordered stages. Operations within a stage begin concurrently. Each stage may contain:

| Field | Limits |
|---|---|
| `face` | One of the 20 embedded animated expressions |
| `text` | Display text (cannot be combined with `face` in the same stage) |
| `melody` | One named Pi5 buzzer melody |
| `tone` | Frequency 20–20,000 Hz, duration 0.05–2 s, volume 1–128 |
| `movement` | Named movement or logical servo targets |
| `duration_seconds` | How long the stage remains active |
| `wait_seconds` | Optional quiet delay after the stage |

### The 20 Animated Faces

`idle`, `happy`, `laughing`, `sad`, `cry`, `angry`, `surprising`, `sleepy`, `speaking`, `shy`, `scary`, `exciting`, `confusing`, `greeting`, `listening`, `thinking`, `curious`, `success`, `warning`, `error`

### Default Motor and Obstacle Policy

Logical roles map to servo endpoints:

```toml
[behaviors.servo_roles]
left_motor = "gpio12"
right_motor = "gpio13"
```

Default movement targets for MG90D continuous-rotation motors:

| Behavior | Left motor | Right motor |
|---|---:|---:|
| `move_forward` | +45 | −45 |
| `move_backward` | −30 | +30 |
| `turn_right` | +45 | +45 |
| `turn_left` | −45 | −45 |

Zero (or the calibrated center) represents neutral for these motors. Emergency Stop uses zero PWM pulse through the driver's `off()` path — not a motion target.

### Obstacle Detection Rules

- Movement starts without waiting for clear-distance readings
- The exact VL53L0X raw sentinel `8191` = clear space (no target in range)
- `null`, invalid, missing, and stale samples do not stop movement
- Three consecutive valid readings ≤ 50 mm → Level 1 stop (forward, turn_left, turn_right only)
- Backward movement: warning only (the sensor faces forward)
- The schema refuses obstacle thresholds below 50 mm

### Private Behaviors

Private behaviors are stored under `~/.config/ninjarobot_pi5/behaviors`. Write rules:

- Names cannot contain a directory path
- Symbolic links are rejected
- Files use mode `0600`
- Writes are atomic
- Existing assets are never overwritten silently

`stop` and `resume` are safety commands, not behavior assets — they cannot be embedded or redefined.

---

## 🔌 Extension Points

### Adding a New Hardware Capability

1. Create a new adapter module inside `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/adapters/`.
2. The adapter must lazily import the relevant `pi5*` library — only when explicit `--real` use is confirmed.
3. Register the capability descriptor in `CapabilityRegistry`.
4. Add the capability to the IDE contracts schema.
5. Add simulation and real-device tests.
6. Add the capability to the Phase validation checklist.

### Adding a New MCP Server

See the [Installation Guide](InstallationGuide.md#-set-up-tavily-web-search-optional) for operator setup. For development:

1. Never pass raw GPIO fields or hardware-library objects through the MCP surface.
2. Sandbox the server — a failed server must degrade only its own tools.
3. Add tests for: prompt injection, malicious schemas, name collisions, oversized content, timeouts, cancellation, secret redaction, authentication failure, and connection loss.

### Adding a New Agent Skill

See the [Installation Guide](InstallationGuide.md) Agent Skills section. For development:

- Do not add SDK calls or provider credentials to a Skill
- Skills are declarative Markdown plus strict JSON metadata
- A skill can only restrict the active tool allowlist — it cannot expand it
- AI-proposed skills require validation, simulation, and explicit approval before saving

### Adding a New Cloud Provider Adapter

1. Implement the `LLMProvider` protocol.
2. Register in `ConfiguredProviderRegistry`.
3. Use `auth_method = "api_key"` only — no OAuth, browser login, or external auth command.
4. The adapter URL must be validated against the official host — reject any configuration that would forward credentials to another server.
5. Add fake-provider and recorded-response contract tests.

---

## 🧪 Testing and Validation

### Test Categories

| Category | Scope | Markers |
|---|---|---|
| Unit | Single module, simulation only | (default) |
| Integration | Multi-module, simulation | (default) |
| Hardware | Real device communication | `@pytest.mark.hardware` |
| Provider (live) | Real cloud API | `@pytest.mark.live_provider` |

### Phase Validation Flow

Each development phase follows this sequence before merging:

1. Safe smoke tests that do not move actuators
2. Device communication tests (GPIO, I2C, SPI, camera, USB audio)
3. Actuator-moving tests with an accessible emergency stop
4. Power-risk tests requiring a completed electrical record

Record: expected outcomes, actual results, rollback steps, operator name, Pi model, OS version, and wiring revision.

### Current Test Suites

- Driver provenance and governance (`test_repository_governance.py`)
- IDE contracts and execution engine
- Fake-device simulation for all hardware adapters
- Behavior model validation and draft compiler
- Fake MCP server contract and transport tests
- Skill confinement and schema tests
- System-prompt ordering and override-resistance tests
- Tool policy and unknown-outcome recovery tests
- FastAPI and exclusive WebSocket lease tests
- Fake-provider and Ollama contract tests
- Model discovery, persistence, hot-switch, informational benchmark, and explicit motion-arm tests
- Presentation-directive filtering and IDE face-lifecycle tests
- Restartable Level 2 device lifecycle and one-shot camera redaction tests
- Cancellation-safe SPI serialization, repeated display/buzzer reconstruction, and rapid Idle-restart stress tests

### Running the Full Gate with JavaScript Check

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen ruff format --check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent scripts tests
uv run --frozen mypy \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
node --check \
  ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js
git diff --check
```

---

## 🛠️ Driver Package Validation Commands

Each `pi5*` package has its own isolated test environment. Run tests using the package-local layout:

```bash
# Each driver in its own directory, frozen and isolated
(cd pi5servo && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5disp && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5vl53l0x && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5camera && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5mic && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)

(cd pi5buzzer && uv run --isolated --frozen --extra dev --python 3.11 \
  python -B -m pytest -q -p no:cacheprovider)
```

Run driver Ruff checks using the root's pinned Ruff version:

```bash
for package in \
  pi5buzzer pi5servo pi5disp pi5vl53l0x pi5camera pi5mic
do
  (cd "$package" && uv run --project .. --isolated --locked --python 3.11 \
    ruff check --no-cache src tests)
  (cd "$package" && uv run --project .. --isolated --locked --python 3.11 \
    ruff format --check src tests)
done
```

### Standalone Driver README Standard

Each `pi5*` README must work for a user who has only that library folder. Requirements:

- Do not require NinjaRobotPi5, NinjaClawBot, or an invented Git URL
- Tell the user to obtain a copied source folder from the project owner
- Use `uv sync --frozen` and the library's own CLI
- Explain every abbreviation and specialist term in plain language
- Clearly separate safe checks from commands that energize hardware or move an actuator

---

## 🔍 Authentication Boundary Reference

All three cloud providers use API-key-only authentication:

| Setting | Behaviour |
|---|---|
| `auth_method = "api_key"` | Resolves `api_key_env` from process environment, then `~/.config/ninjarobot_pi5/secrets.env` |
| Legacy `auth_method = "oauth"` | Loaded as `api_key` and rewritten without `oauth_profile` — no old bearer or refresh credential consumed |
| `provider login` command | Compatibility-only; raises a migration message pointing to `provider set-api-key`; never starts a browser |
| `provider logout PROVIDER_ID` | Removes only that provider's saved API key |

Cloud adapter URL validators accept only HTTPS and the official host for each provider:
- OpenAI: `api.openai.com`
- Gemini: `generativelanguage.googleapis.com`
- Anthropic: `api.anthropic.com`

A configuration change that points to another host is rejected — preventing credential forwarding.

---

## 🐛 Developer Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Root `pytest` imports the wrong driver package | Use the package-local commands shown above; drivers are independent projects |
| `ruff: command not found` | Run through `uv run --frozen ruff ...` |
| Ruff upgrade reports new driver errors | Reproduce the Phase 0 gate with pinned Ruff 0.15.5 before deciding whether it is code or tool-version drift |
| Driver checksum changes unexpectedly | Stop immediately. Revert an unintended change or, for an approved repair, record the new hash with `--record-authorized` |
| A test accesses hardware | Ensure it is explicitly marked `hardware` and excluded from the default gate |
| `distance read` returns 250 mm without opening I2C | Expected simulation result. Add `--real` only on the Pi when you intend to open the sensor |
| Real command reports `DEVICE_OUT_OF_RANGE` and raw `8191` | The middleware is working correctly. In open space, no target is measurable. Integrated movement treats this exact result as clear space |
| Real command reports `DEVICE_UNAVAILABLE` | Install with `uv sync --frozen --extra hardware`, confirm I2C is enabled, and confirm address `0x29` appears on bus 1 |
| A repeated action does not re-read the sensor | Intentional when the same action ID or idempotency key is reused. Generate new IDs for a new physical reading |
| Real servo health is unavailable | Verify the `pwm-2chan` overlay in `/boot/firmware/config.txt`, confirm I2C address `0x10`, install the hardware extra, confirm the user can access `/sys/class/pwm` and `/dev/i2c-1` |
| Real move returns `SERVO_MOTION_DISABLED` | The checked-in configuration intentionally blocks movement. Use a private configuration only after the electrical record is approved |
| Real move returns `SERVO_NOT_CALIBRATED` | Calibrate that endpoint with the standalone `pi5servo` tool. Do not substitute another servo's calibration |
| Display shows `simulated: true` | Safe default. Add `--real` only on a correctly wired Pi |
| Screen goes dark when a command exits | Intentional cleanup. Add `--hold 5` to a real manual test to keep the backlight active for inspection |
| Text is sideways on the display | Authoritative V4 rotation is 90°. Confirm `--config` points to the correct TOML file |
| Hardware already owned by another process | Use the existing agent interface, or run `uv run --frozen ninjarobot-agent service stop`, then retry. Also stop both integrated tools before opening a standalone `pi5*` tool |
| A repaired `pi5*` source file is present but Python runs an older copy | Run `uv sync --frozen --extra hardware`, then `scripts/verify_workspace_driver_sources.py`. Editable dependencies must resolve into this checkout |
| Root camera health reports unavailable while `/usr/bin/python3` imports Picamera2 | Run `./scripts/bootstrap-rpi-camera-workspace.sh` and retry from the project root. Do not recreate `.venv` with `--system-site-packages` |
| `pi5mic` reports PortAudio missing | Install `libportaudio2` and `portaudio19-dev`, then run `pi5mic devices`. Local transcription also requires a built `whisper-cli` and `ggml-base.bin` |
| V4 microphone status reports 44.1 kHz instead of 16 kHz | Expected. The USB device rejected 16 kHz; the managed driver selected its supported native rate. Check both `requested_sample_rate_hz` and `actual_sample_rate_hz` in the status output |
| VL53L0X reference calibration retries once | This is the bounded recovery path on the live revision-`0x10` device. A second timeout is a hard initialization failure — do not bypass calibration |
| Clean checkout reports `recovery_required` | Inspect `robot.safety.reason` and `robot.safety.fault_detail`, close any standalone `pi5*` programs, and use the confirmed recovery path. Never remove `safety.json` as a repair |

---

## 📋 Phase and Feature Status

| Phase | Status | Description |
|---|---|---|
| Phase 0 | ✅ Complete | Project governance, driver hash baseline, quality gate |
| Phase 1 | ✅ Complete | IDE and agent contracts, deterministic fakes, unified CLI |
| Phase 2 | ✅ Complete | IDE capability registry, scheduler, action ledger, distance adapter |
| Phase 3.1 | ✅ Complete | GPIO27 buzzer adapter |
| Phase 3.2 | ✅ Complete | ST7789V display adapter |
| Phase 3.3 | ✅ Complete | Six-servo mixed-backend adapter |
| Phase 3.4 | ✅ Complete | Privacy-bounded camera adapter |
| Phase 3.5 | ✅ Complete | USB microphone adapter |
| Phase 4 | ✅ Complete | Integrated behaviors, 20 faces, IDE tool, safety engine |
| Phase 5 | ✅ Complete | NinjaRobotAgent, Ollama, HTTPS web controller, MCP, Skills |
| Phase 6 | ✅ Complete | OpenAI, Gemini, Anthropic cloud provider adapters |
| Pi Acceptance | 🔲 Pending | Full Raspberry Pi hardware validation by operator |

The implementation plan `NinjaRobotPi5V4_ImplementationPlan.md` remains the authoritative source for all design decisions and phase requirements.
