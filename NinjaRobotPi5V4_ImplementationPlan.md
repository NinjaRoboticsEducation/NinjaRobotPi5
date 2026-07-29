# NinjaRobotPi5V4 Implementation Plan

Status: Approved architecture and active delivery record
Last updated: 2026-07-30 (Phase 5 recovery, Idle, and one-shot camera refinement)
Primary development computer: Raspberry Pi 5, 8 GB RAM
Target computer: Raspberry Pi 5, 8 GB RAM
Implementation status: Phases 0–4 implemented and operator-validated; Phase
5.0–5.7 implemented with the local software gate passing and Raspberry Pi
operator acceptance pending

## 1. Purpose of this document

This is the single source of truth for building `NinjaRobotPi5V4`, formerly
planned under the name NinjaClawBot V4.
It explains what will be built, why the design is structured this way, how the
parts communicate, and how each phase will be validated.

The redesign has three main goals:

1. Replace the OpenClaw-based AI integration with a project-owned agent package
   named `ninjarobot_pi5_agent`.
2. Introduce a clean robot middleware package named `ninjarobot_pi5_ide`, so the AI
   agent never imports or controls a hardware driver directly.
3. Treat the copied `pi5*` drivers as immutable, independently usable Raspberry
   Pi 5 libraries. V4 integrates them through adapters without editing their
   source, tests, package metadata, or documentation.

This plan deliberately separates design from implementation. No V4 production
code should be written until this plan is approved. After approval, each phase
should be implemented and reviewed separately.

## 2. Plain-English glossary

The terms below are used throughout this plan.

- **Agent**: Software that receives a user request, decides what should happen,
  asks an AI model for help when useful, invokes approved tools, observes the
  result, and replies to the user.
- **AI model or LLM**: A large language model such as a local Ollama model or a
  cloud model from OpenAI, Google, or Anthropic.
- **Provider adapter**: A small translation layer that makes one AI provider
  conform to NinjaRobotPi5V4's common model interface.
- **Tool**: A typed operation that the model may request, such as reading the
  distance sensor or moving a servo. A tool request is only a proposal until
  deterministic application code validates and executes it.
- **Tool provider**: An adapter that supplies tools to the unified tool
  registry. The IDE and each connected MCP server are separate tool providers.
- **Capability**: An operation offered by `ninjarobot_pi5_ide`. Tools are the
  agent-facing view of capabilities.
- **MCP**: Model Context Protocol, an open client-server protocol that lets an
  agent discover and call tools supplied by separate local or remote programs.
- **MCP host**: NinjaRobotAgent's component that owns MCP connections and
  decides which discovered tools may be shown to the model.
- **MCP server**: A separate program or hosted service that exposes tools,
  resources, or prompt templates through MCP.
- **Agent skill**: A validated, reusable task workflow that combines
  instructions with a strict allowlist of existing tools. A skill cannot grant
  itself new permissions.
- **Controller lease**: A short-lived exclusive permission held by one browser
  connection. It prevents two browser devices from controlling the robot at the
  same time.
- **Middleware**: Software between the agent and device drivers. It gives the
  agent one consistent interface even though each device has a different
  low-level API.
- **Driver**: A `pi5*` library that talks to one kind of hardware.
- **Backend**: A replaceable implementation of an interface. V4 will use real
  hardware backends on the Pi and fake or simulated backends on macOS.
- **Schema**: A machine-readable description of valid inputs or outputs.
- **Idempotency key**: A unique identifier that prevents one requested action
  from being executed twice by accident.
- **Short-term memory**: Context used during the current conversation.
- **Long-term memory**: Project-owned, persistent data such as user preferences,
  task recipes, and summaries from earlier sessions.
- **ADR**: An Architecture Decision Record: a short document explaining a
  significant technical decision and its trade-offs.
- **Quality gate**: A required check, such as tests or linting, that must pass
  before a phase is accepted.

## 3. Sources reviewed

This plan is based on a full review of the current NinjaClawBot documentation,
source code, tests, all six `pi5*` libraries, the OpenClaw integration, and the
local `reachy_mini-main` reference project.

The NinjaClawBot review included:

- `README.md`
- `DevelopmentGuide.md`
- `InstallationGuide.md`
- `AGENTS.md`
- the workspace configuration and scripts
- `ninjaclawbot`
- `pi5buzzer`
- `pi5servo`
- `pi5disp`
- `pi5camera`
- `pi5mic`
- `pi5vl53l0x`
- `integrations/openclaw`

These are historical audit sources. NinjaRobotPi5V4 is a clean build and does
not include the old `ninjaclawbot` runtime or OpenClaw plugin.

The Reachy Mini review included its repository instructions, SDK documentation,
client façade, daemon, real/simulation/mock backends, command protocol,
application manager, application lock, JSON-RPC implementation, movement
handling, tests, and conversation-application templates.

The Reachy Mini repository itself is not a complete AI-agent or long-term-memory
implementation. Its conversation agent lives in a separate application. The
useful local lessons are its robot-control boundaries and application lifecycle,
not a memory system to copy.

For the OpenAI adapter, implementation should follow the current official
[Responses API](https://platform.openai.com/docs/api-reference/responses) and
[function calling guide](https://platform.openai.com/docs/guides/function-calling).
OpenAI-managed conversation state may be used inside that adapter, but it must
not replace V4's provider-neutral short-term or long-term memory.

### 3.1 Confirmed project decisions

The following decisions were confirmed on 2026-07-23 and are requirements, not
open design options:

- Product and repository name: `NinjaRobotPi5V4`
- Middleware import package: `ninjarobot_pi5_ide`
- Agent import package: `ninjarobot_pi5_agent`
- Unified command-line entry point: `ninjarobot_pi5_cli`
- Phase 5 agent command-line entry point: `ninjarobot-agent`. It provides
  conversational, interactive, service, MCP, and skill commands without
  replacing the existing unified IDE-oriented CLI.
- Python baseline: Python 3.11
- Runtime topology: one single-owner service process owns the agent, IDE,
  hardware resources, MCP connections, session state, and optional web server
- User interfaces: a conversational CLI, an interactive CLI menu, and an HTTPS
  FastAPI web interface for the local network
- Web control: one exclusive browser controller lease; a second device is
  refused until the first lease is released or expires
- LAN security: HTTPS only, no public-internet exposure or router port
  forwarding, and no pairing authentication in Phase 5. The owner accepts the
  residual risk that another device on the same LAN could connect first.
- Interaction order: text CLI and web text chat in Phase 5; spoken robot
  responses remain deferred
- Default model service: Ollama running directly on the Raspberry Pi 5
- Initial model candidate: Qwen3:4B in a Pi-suitable quantization, accepted as
  the default only after the Phase 5 benchmark meets the recorded latency,
  memory, temperature, and tool-call thresholds
- Default target: Raspberry Pi 5 with 8 GB RAM, 256 GB NVMe, active cooling,
  Raspberry Pi OS Lite 64-bit, headless operation, and normal internet access
- Persistent memory: single local user, SQLite on the Pi, seven-day
  conversation transcript retention, no raw microphone retention, and no
  camera-media retention unless explicitly requested
- Default current-information tool: the official hosted Tavily MCP server,
  using the robot owner's free Tavily API key and a search-only allowlist
- Startup: manual by default; optional managed auto-start may be enabled later
- Hardware expansion board: DFRobot DFR0566 is mandatory
- Existing `pi5*` directories: independently usable hardware libraries.
  The project owner's 2026-07-25 authorization permits narrowly scoped,
  audited repairs after README review, failure reproduction, package-level
  linting/tests, and Raspberry Pi validation. Original import hashes remain
  permanent provenance, and repaired hashes must be recorded separately.
- Repository checkout path: `/home/rogerchang/NinjaRobotPi5` is the new V4
  root even though the product and repository name remain `NinjaRobotPi5V4`
- Historical reference: nested `NinjaClawBot/` is read-only, excluded from V4
  Git, and used only to inspect or export approved driver code
- Temporary MG90D continuous-rotation servos do not change the confirmed
  six-endpoint production topology; current test wiring uses DFR0566 digital
  GPIO12/GPIO13 breakouts and therefore native Raspberry Pi hardware PWM, not
  the HAT's dedicated I2C PWM0/PWM1 sockets

## 4. Current project: what exists today

At Phase 0 entry, the new `NinjaRobotPi5V4` root contained the implementation
plan and a nested historical `NinjaClawBot/` checkout. Phase 0 exports only the
six tracked `pi5*` library trees into the root, excludes the historical checkout
from V4 Git, and creates the clean workspace and root documentation. It does
not copy generated caches, the OpenClaw integration, or the old runtime.

The historical NinjaClawBot system used this flow:

```mermaid
flowchart LR
    U["User"] --> O["OpenClaw agent and model"]
    O --> P["OpenClaw NinjaClawBot plugin"]
    P --> N["ninjaclawbot integrated runtime"]
    N --> D["Independent pi5* libraries"]
    D --> H["Raspberry Pi 5 hardware"]
```

The copied immutable libraries are the V4 hardware foundation:

| Library | Responsibility |
| --- | --- |
| `pi5buzzer` | Buzzer output and melodies |
| `pi5servo` | Servo control, groups, movement, and calibration |
| `pi5disp` | ST7789V display access |
| `pi5camera` | Camera capture and recognition-related operations |
| `pi5mic` | Microphone input and optional voice-input functions |
| `pi5vl53l0x` | VL53L0X distance measurement |

The historical `ninjaclawbot` package initializes the robot, loads movements and
expressions, coordinates multiple devices, and exposes action-oriented methods.
The OpenClaw plugin translates model tool calls into those actions.

In the historical design, OpenClaw owns model choice, tool-call orchestration,
and conversation behavior. This prevents the robot project from owning its complete
agent workflow and makes persistent, provider-neutral memory difficult.

## 5. Audit findings that V4 must address

The earlier audit found a healthy test baseline, but it also identified issues
that must be resolved before V4 relies on the affected paths.

### 5.1 Safety and correctness findings

1. A persistent OpenClaw tool timeout can retry a one-shot request. A hardware
   action may therefore happen twice even though the user requested it once.
   V4 must use action IDs and must never automatically retry a non-idempotent
   hardware operation when its outcome is uncertain.
2. A pending camera recognition identifier is used as a path component without
   sufficient validation. V4 must constrain identifiers and keep all generated
   paths inside an approved data directory.
3. The buzzer's worker and `off()` path can race. Shutdown and output ownership
   must be serialized.
4. VL53L0X calibration can fail without restoring the previous measurement
   offset. Calibration must use guaranteed cleanup.
5. A recognition backend is not consistently closed. Every device and backend
   must have an explicit lifecycle and safe teardown.
6. `pi5servo` contains version metadata that is not consistent across project
   surfaces. Package and runtime versions must have one source of truth.

### 5.2 Process and documentation findings

1. Some development instructions and actual commands have drifted apart.
2. Hardware and non-hardware validation are not consistently distinguished.
3. The OpenClaw TypeScript test path is less self-contained than the Python
   workspace.
4. Driver responsibilities are generally good, but integrated behavior and
   agent responsibilities are mixed in `ninjaclawbot`.

The copied drivers remain independent hardware libraries. V4 addresses
integration concerns at the adapter boundary: it validates camera identifiers,
serializes buzzer ownership, snapshots and restores sensor configuration around
calibration, owns backend teardown, records observed versions, and prevents
duplicate actions. Hardware-library defects may be repaired only under the
managed-driver workflow: review the library README, audit with Serena,
reproduce the root cause, make a focused fix, pass package lint/tests, validate
on the Pi, and record the changed hashes without replacing the import baseline.

### 5.3 Verified baseline

At the time of the audit:

- Python compilation passed.
- Ruff linting passed.
- 513 Python tests passed.
- OpenClaw TypeScript tests were not executed because their external
  dependencies were not installed in the audited environment.

This baseline should be recorded again at the start of Phase 0 so later changes
can be compared fairly.

## 6. Lessons adopted from Reachy Mini

Reachy Mini uses a client/server robot architecture with a stable SDK façade,
typed commands, replaceable real and simulation backends, explicit application
ownership, managed subprocess lifecycles, cancellation, and structured errors.

V4 should adopt these patterns:

- A stable façade hides low-level device differences.
- Real, fake, and future simulated backends implement the same contracts.
- The AI loop is outside the real-time device-control loop.
- Model-requested movements are queued and executed by deterministic code.
- Resource ownership prevents two operations from controlling one device at
  the same time.
- Long-running operations have IDs, progress, cancellation, and deadlines.
- Applications and devices have explicit start, health, stop, and close
  lifecycles.
- Protocol objects are typed and validated at the boundary.
- macOS development uses fakes; hardware-specific tests are marked and deferred
  to the Pi.
- Graceful shutdown is attempted first, followed by a bounded fallback.
- Tool descriptions are declarative and can be enabled by profile.

V4 should not copy these Reachy-specific elements:

- Reachy's kinematics, head pose, antenna, WebRTC, or app marketplace design.
- Its process and network complexity before NinjaRobotPi5V4 needs remote control.
- Provider-specific conversation behavior.
- Any assumption that Reachy's SDK supplies persistent memory; it does not.

## 7. V4 architectural principles

The following rules are mandatory.

1. The copied `pi5*` packages are immutable external boundaries inside this
   repository. V4 code and documentation must not modify them.
2. The agent never imports a `pi5*` package.
3. All robot operations go through `ninjarobot_pi5_ide`.
4. An AI model may select or propose a tool, but deterministic code validates
   policy, arguments, availability, ownership, timeout, and result.
5. A model provider is replaceable through an adapter.
6. Project-owned memory is provider-neutral and remains usable when the active
   model changes.
7. Robot configuration is authoritative configuration, not learned memory.
8. Non-idempotent hardware actions are not blindly retried.
9. All resources have explicit ownership and cleanup.
10. Every new hardware type is developed as an independent library outside the
    immutable copied drivers, then integrated through an IDE adapter. Agent
    tools are generated from registered capabilities.
11. V4 starts with one understandable agent loop. Multi-agent orchestration is
    out of scope until a proven use case justifies it.
12. macOS checks must never pretend to validate physical Raspberry Pi hardware.
13. Production servo pulses must be hardware-backed. GPIO12 and GPIO13 use the
    Pi 5 RP1 hardware-PWM path, never Python-timed or software PWM.
14. The DFR0566 and VL53L0X share I2C bus 1 at different addresses (`0x10` and
    `0x29` respectively).

## 8. Target architecture

```mermaid
flowchart TB
    U["Local user"]
    CLI["Conversational and interactive CLI"]
    WEB["FastAPI HTTPS web UI"]
    LEASE["Exclusive browser controller lease"]

    subgraph A["ninjarobot_pi5_agent"]
        SV["Single-owner agent service"]
        S["Session manager"]
        C["Context builder"]
        L["Bounded agent loop"]
        PR["Provider registry"]
        TR["Tool registry"]
        MP["MCP client manager"]
        SK["Skill registry"]
        PC["System-prompt composer"]
        SG["Policy and safety gate"]
        M["Memory service"]
    end

    subgraph I["ninjarobot_pi5_ide"]
        IC["IDE client contract"]
        CR["Capability registry"]
        EX["Execution engine and scheduler"]
        RL["Resource locks"]
        EV["Events, state, and health"]
        AD["Device adapters"]
    end

    subgraph P["Immutable copied pi5* drivers"]
        B["pi5buzzer"]
        SV["pi5servo"]
        DP["pi5disp"]
        CA["pi5camera"]
        MI["pi5mic"]
        DS["pi5vl53l0x"]
    end

    subgraph Models["Model providers"]
        OL["Ollama"]
        OA["OpenAI"]
        GE["Google Gemini"]
        AN["Anthropic Claude"]
    end

    subgraph External["External MCP servers"]
        TV["Tavily web search"]
        XM["Future approved MCP servers"]
    end

    U --> CLI --> SV
    U --> WEB --> LEASE --> SV
    SV --> S --> C --> L
    C <--> M
    C <--> PC
    PC <--> SK
    L <--> PR
    PR <--> OL
    PR <--> OA
    PR <--> GE
    PR <--> AN
    L <--> TR
    MP --> TR
    MP <--> TV
    MP <--> XM
    TR --> SG --> IC
    IC --> CR --> EX
    EX --> RL
    EX --> AD
    EX --> EV
    AD --> B
    AD --> SV
    AD --> DP
    AD --> CA
    AD --> MI
    AD --> DS
    EV --> IC --> TR --> L
    L --> S --> SV
    SV --> CLI --> U
    SV --> WEB --> U
```

There are two important planes:

- The **model plane** is probabilistic. It interprets language and proposes a
  plan or tool call.
- The **control plane** is deterministic. It enforces rules and operates the
  robot.

The control plane always has final authority.

## 9. Proposed repository layout

The product name is `NinjaRobotPi5V4`. Python import packages and the unified
CLI use the exact confirmed underscore names below.

```text
NinjaRobotPi5V4/
├── pyproject.toml
├── uv.lock
├── README.md
├── AGENTS.md
├── DevelopmentGuide.md
├── DevelopmentLog.md
├── InstallationGuide.md
├── tests/
├── ninjarobot_pi5_ide/
│   ├── pyproject.toml
│   ├── src/ninjarobot_pi5_ide/
│   │   ├── api/
│   │   ├── capabilities/
│   │   ├── adapters/
│   │   ├── execution/
│   │   ├── lifecycle/
│   │   ├── errors.py
│   │   ├── models.py
│   │   └── cli.py
│   └── tests/
├── ninjarobot_pi5_agent/
│   ├── pyproject.toml
│   ├── src/ninjarobot_pi5_agent/
│   │   ├── agent/
│   │   ├── providers/
│   │   ├── tools/
│   │   ├── memory/
│   │   ├── policy/
│   │   ├── sessions/
│   │   ├── config/
│   │   └── cli.py
│   └── tests/
├── pi5buzzer/
├── pi5servo/
├── pi5disp/
├── pi5camera/
├── pi5mic/
├── pi5vl53l0x/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── validation/
│   └── hardware/
└── NinjaRobotPi5V4_ImplementationPlan.md
```

The new root does not copy `ninjaclawbot` or `integrations/openclaw`. Historical
behavior may be studied as a reference, but V4 does not provide a legacy
runtime-compatibility layer.

## 10. Layer 1: immutable `pi5*` libraries

### 10.1 Responsibility

Each copied driver is treated as an already delivered standalone dependency.
Its existing public surface may be used, but the V4 project does not change it.
Conceptually, each driver owns:

- device-specific configuration
- hardware communication
- validation of physical input ranges
- device lifecycle
- device-specific errors
- a fake backend suitable for non-hardware tests where practical
- a CLI or script for focused manual device tests

Some copied packages contain historical integration features. In particular,
`pi5mic` contains OpenClaw transport/session code and model-based transcription.
Because the package is immutable, those modules remain on disk, but
NinjaRobotPi5V4 must not import, configure, invoke, or document them as V4
features. The IDE adapter uses only the approved device-facing portions.

### 10.2 Compatibility rule

Existing public imports, methods, tests, READMEs, package metadata, and lockfiles
are preserved byte-for-byte. If V4 needs a different behavior, it implements a
wrapper, policy, validator, or compatibility object in `ninjarobot_pi5_ide`.
If containment is unsafe or impossible, the capability remains disabled.

### 10.3 Driver lifecycle

The IDE adapts each driver's existing methods into this common conceptual
lifecycle without changing the driver:

```text
create -> open/initialize -> ready -> operate -> stop -> close
```

The adapter makes repeated close requests safe, uses context managers where the
existing driver supports them, and owns cleanup after partial initialization.

### 10.4 Hardware and fake backends

Fakes belong to the new IDE test package, not inside the immutable drivers. A
fake must be deterministic, record commands for assertions, and clearly label
results as simulated. Production servo control remains hardware-backed.

## 11. Layer 2: `ninjarobot_pi5_ide`

### 11.1 Purpose

`ninjarobot_pi5_ide` is the only robot-control surface available to the agent.
It is a clean implementation; it does not depend on the historical
`ninjaclawbot` runtime.

The IDE remains an in-process Python API plus its own CLI; it is not a separate
network service. During Phase 5, the single-owner agent service may expose the
approved FastAPI HTTPS interface and call the IDE in-process. Web clients never
receive a direct IDE or driver endpoint.

### 11.2 Core components

#### Capability registry

Stores the operations currently available, their schemas, risk, device
requirements, and runtime health.

#### Device adapters

Translate common capability requests into one driver's API. An adapter imports
one or more `pi5*` libraries; the agent does not.

#### Execution engine

Validates a request, acquires resources, invokes the adapter, records progress,
normalizes the result, and releases resources.

#### Action scheduler

Queues actions that cannot safely overlap. It supports deadlines, cancellation,
and explicit concurrency only when resource sets do not conflict.

#### Resource locks

Provide exclusive ownership for resources such as:

- `servo_bus`
- `camera`
- `display`
- `microphone`
- `buzzer`
- `distance_sensor`

Cross-device behaviors acquire all required resources in a deterministic order
to avoid deadlocks.

#### Lifecycle manager

Initializes configured devices, reports unavailable optional devices, shuts
down safely, and makes partial startup failures visible.

#### State and event service

Provides current availability, action progress, cancellation, health, and
recent structured events.

### 11.3 Main contracts

The exact Python syntax will be finalized in Phase 1, but the conceptual
contracts are:

```python
class CapabilityAdapter(Protocol):
    def descriptors(self) -> list[CapabilityDescriptor]: ...
    async def execute(
        self,
        request: ActionRequest,
        context: ExecutionContext,
    ) -> ActionResult: ...
    async def close(self) -> None: ...
```

```python
@dataclass(frozen=True)
class CapabilityDescriptor:
    name: str
    version: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    risk: RiskLevel
    resources: tuple[str, ...]
    default_timeout_seconds: float
    idempotent: bool
    cancellable: bool
    confirmation_required: bool
```

```python
@dataclass(frozen=True)
class ActionRequest:
    action_id: str
    capability: str
    arguments: dict[str, object]
    requested_by: str
    session_id: str
    deadline: datetime | None
    idempotency_key: str
```

```python
@dataclass(frozen=True)
class ActionResult:
    action_id: str
    status: ActionStatus
    data: dict[str, object] | None
    error: IDEError | None
    started_at: datetime
    finished_at: datetime
    retry_safety: RetrySafety
```

### 11.4 Standard error model

Every error should contain:

- a stable code
- a beginner-readable message
- an optional technical detail for logs
- whether the request was definitely not executed
- whether retry is safe
- the affected capability and action ID

Initial error categories:

| Code family | Meaning | Normal response |
| --- | --- | --- |
| `INVALID_*` | Input failed schema or range checks | Correct input; do not execute |
| `UNAVAILABLE_*` | Device or capability is unavailable | Offer an alternative |
| `BUSY_*` | Resource is owned by another action | Wait or cancel explicitly |
| `TIMEOUT_BEFORE_START` | Action never started | Retry may be safe |
| `OUTCOME_UNKNOWN` | Timeout/disconnect after action began | Do not auto-retry |
| `DEVICE_*` | Driver reported a device failure | Stop affected workflow |
| `CANCELLED` | User or policy cancelled the action | Return current safe state |
| `POLICY_DENIED` | Safety policy rejected it | Explain the rule |
| `INTERNAL_*` | Unexpected IDE failure | Log correlation ID; fail closed |

### 11.5 IDE CLI

The CLI exists for developers and manual testing, independent of the AI agent.
The root workspace registers the exact console-script name
`ninjarobot_pi5_cli`, pointing to the agent CLI. IDE-only subcommands delegate
through the in-process IDE API. Proposed commands:

```text
ninjarobot_pi5_cli capabilities list
ninjarobot_pi5_cli health
ninjarobot_pi5_cli action run <capability> --json '<arguments>'
ninjarobot_pi5_cli action status <action-id>
ninjarobot_pi5_cli action cancel <action-id>
ninjarobot_pi5_cli device list
ninjarobot_pi5_cli config validate
ninjarobot_pi5_cli --dry-run ...
```

`--dry-run` uses fake adapters and clearly labels every result as simulated.

### 11.6 Adding new hardware

The supported workflow will be:

```mermaid
flowchart LR
    D["Develop a separate standalone device library"]
    T["Validate and version that library independently"]
    A["Create IDE adapter"]
    R["Register capability descriptors"]
    C["IDE CLI discovers capability"]
    G["Agent tool registry discovers capability"]

    D --> T --> A --> R --> C --> G
```

The copied six `pi5*` directories remain untouched. A future driver is added as
a separate, approved dependency and then registered through a new IDE adapter.
No provider-specific prompt or agent source file should need editing when a
properly described capability is added. Profiles and policy may still choose
whether the new capability is enabled.

## 12. Layer 3: `ninjarobot_pi5_agent`

### 12.1 Purpose

The agent owns interaction, model selection, context, planning, tool-call
coordination, recovery, memory, and the final reply. It does not own hardware.

### 12.2 Bounded agent workflow

V4 should use an explicit state machine instead of an unbounded autonomous loop.

```mermaid
stateDiagram-v2
    [*] --> Receive
    Receive --> BuildContext
    BuildContext --> Decide
    Decide --> Respond: no tool needed
    Decide --> ValidatePlan: tool proposed
    ValidatePlan --> AskConfirmation: policy requires consent
    AskConfirmation --> ValidatePlan: approved
    AskConfirmation --> Respond: rejected
    ValidatePlan --> Execute: valid and authorized
    ValidatePlan --> Recover: invalid or unavailable
    Execute --> Observe
    Observe --> Decide: more bounded work needed
    Observe --> Reflect: task complete or failed
    Recover --> Decide: safe alternative exists
    Recover --> Reflect: no safe alternative
    Reflect --> MemoryCandidates
    MemoryCandidates --> Respond
    Respond --> [*]
```

Each turn has:

- a maximum number of model calls
- a maximum number of tool calls
- a wall-clock deadline
- a cancellation token
- a budget for context and output
- a trace/correlation ID

The initial default should favor short plans and one action at a time. Complex
parallel robot actions are allowed only when the IDE explicitly declares that
their resources do not conflict.

### 12.3 Planning and reasoning

The agent should request a concise, structured execution plan, not expose hidden
model reasoning. A plan contains:

- the understood goal
- assumptions visible to the user when important
- ordered steps
- proposed tools and arguments
- required confirmations
- completion criteria

The application validates the structured plan. Free-form model text never
becomes a hardware command.

### 12.4 Unified tool registry

The tool registry accepts tools from multiple `ToolProvider` implementations.
The IDE provider converts enabled IDE capability descriptors into robot tool
definitions. Each MCP provider converts the tools discovered from one approved
MCP server into the same provider-neutral definition. Model-provider-specific
tool-call formats are normalized back into the same `ToolCall` object.

A tool definition contains:

- stable name and version
- plain-language description
- JSON input schema
- expected output schema
- risk and confirmation requirements
- availability
- timeout
- idempotency and cancellation information
- source provider and trust level
- tool namespace and collision-safe external name

Profiles can enable a safe subset, for example:

```text
default: distance, display, simple motion, buzzer
observer: read-only camera and sensors
maintenance: calibration and diagnostics with confirmation
voice: microphone plus default capabilities
```

Robot tools use the `robot.*` namespace. MCP tools use
`mcp.<configured-server-id>.*`. Server IDs, rather than self-reported MCP server
names, provide collision-resistant namespaces. Duplicate names are rejected.
The registry never gives an MCP server direct access to an IDE client or a
hardware driver.

### 12.4.1 MCP client manager

NinjaRobotAgent is the MCP host. It owns one client session per configured
server and supports:

- local `stdio` transport, meaning messages exchanged with a child process
  through standard input and output
- remote Streamable HTTP transport over HTTPS
- connection initialization and capability negotiation
- dynamic tool discovery and explicit refresh
- independent health, timeout, cancellation, and shutdown handling per server
- per-server tool allowlists, result-size limits, and risk-policy overlays
- secrets resolved from environment variables rather than URLs or checked-in
  configuration

MCP tool descriptions, annotations, prompt templates, resources, and returned
web content are untrusted input unless a project-owned policy says otherwise.
They cannot change risk levels, session arming, confirmations, emergency-stop
behavior, or the IDE boundary. External content is clearly separated from
system instructions before it is sent to a model.

The default Phase 5 server is the official hosted Tavily MCP server:

```toml
[[servers]]
id = "tavily"
enabled = true
transport = "streamable_http"
url = "https://mcp.tavily.com/mcp"
authentication = "bearer_environment"
token_environment = "TAVILY_API_KEY"
allowed_tools = ["tavily_search"]
timeout_seconds = 20.0
max_result_bytes = 131072
preset = "tavily"

[servers.default_parameters]
search_depth = "basic"
max_results = 5
include_images = false
include_raw_content = false
```

The project does not bundle or share an API key. During installation, each
owner creates a Tavily account and supplies `TAVILY_API_KEY`. Tavily currently
documents 1,000 free API credits per month with no credit card required; this
external price and quota are not guaranteed by NinjaRobotPi5. The key is sent
in an `Authorization: Bearer` header and is never placed in the server URL,
logs, prompts, transcripts, or configuration inspection output.

Only raw server tool `tavily_search` is enabled by default. It is normalized to
stable agent-facing name `mcp.tavily.tavily-search`. Extract, map, and crawl
tools require an explicit allowlist change. The agent searches when the answer
depends on current information or the user requests a search, not for every
conversation. Search-based answers include source links. Quota exhaustion,
authentication failure, or network loss produces a clear unavailability
result; the agent must not present an unverified current claim as verified.

### 12.4.2 Agent skills and system prompts

System prompts and skills have different responsibilities:

- The immutable safety prompt states non-overridable robot rules.
- The identity prompt defines NinjaRobot's voice and normal interaction style.
- Runtime context states current health, configuration, controller lease, and
  motion-arming state.
- A selected skill supplies task-specific workflow instructions.
- Conversation context contains the current user interaction.

The prompt composer always uses that order. A skill cannot replace or precede
the safety prompt.

Each skill is a confined directory containing:

```text
skill-id/
├── skill.json
├── instructions.md
└── examples.json        # optional
```

`skill.json` is a strict, versioned manifest containing identity, activation
examples, JSON input schema, allowed tool names, turn/tool/time limits, and
safety metadata. `instructions.md` contains the plain-language workflow.
`examples.json` may contain simulation-only examples. Skills cannot contain
executable Python or shell code, symlinks, absolute paths, or parent-directory
traversal. File sizes and directory depth are bounded.

Bundled skills are read-only package assets. User skills live in
`~/.config/ninjarobot_pi5/skills/`. Installation validates the complete
directory before an atomic, non-overwriting copy. AI-proposed skills require a
simulation preview and explicit user approval before saving or execution.

A fixed display, buzzer, and servo choreography remains an IDE behavior. An
agent skill is used when a task needs reasoning, conditions, external tools, or
several existing behaviors. All robot steps still call IDE tools through the
normal registry and safety policy.

### 12.5 Safety policy

Initial risk levels:

| Level | Examples | Default behavior |
| --- | --- | --- |
| `READ_ONLY` | Read distance, health, or state | Execute if available |
| `LOW` | Display text, short quiet beep | Execute within limits |
| `MOTION` | Move a servo or run an expression | Check limits and workspace |
| `PRIVACY` | Capture image or audio | Require visible policy/consent |
| `MAINTENANCE` | Calibration or raw diagnostics | Require explicit confirmation |
| `EMERGENCY` | Stop, release, safe shutdown | Always locally available |

The policy engine must be ordinary deterministic Python, covered by table-driven
tests. The model cannot lower a risk level or bypass confirmation.

### 12.6 Error and recovery behavior

Recovery must depend on what is known:

| Situation | Agent behavior |
| --- | --- |
| Invalid arguments | Correct once from schema feedback |
| Capability unavailable | Explain and offer an available alternative |
| Resource busy | Wait only within the turn deadline or ask the user |
| Timeout before action started | One bounded retry may be allowed |
| Outcome unknown after action started | Observe state; never repeat blindly |
| Device failure | Stop related steps and move to a safe state if possible |
| Provider timeout | Retry provider request within policy or use configured fallback |
| Provider tool format invalid | Reject it and request corrected structured output once |
| User cancellation | Propagate cancellation to IDE and report final known state |
| Memory write failure | Complete the user task; report/log memory degradation |

Provider fallback must not repeat already-started robot actions. The durable
action ledger is consulted before continuing a turn with another model.

## 13. Model provider architecture

### 13.1 Provider-neutral interface

```python
class LLMProvider(Protocol):
    @property
    def capabilities(self) -> ProviderCapabilities: ...

    async def generate(self, request: ModelRequest) -> ModelTurn: ...

    async def stream(
        self,
        request: ModelRequest,
    ) -> AsyncIterator[ModelEvent]: ...

    async def health(self) -> ProviderHealth: ...

    async def close(self) -> None: ...
```

`ModelRequest` contains provider-neutral messages, tool schemas, model settings,
and correlation metadata. `ModelTurn` contains normalized text, tool calls,
usage, finish reason, and provider diagnostics.

### 13.2 Planned adapters

| Adapter | Role |
| --- | --- |
| Ollama | Default local provider running on the Raspberry Pi 5 |
| OpenAI | Cloud models through the current Responses API |
| Google Gemini | Cloud Gemini models |
| Anthropic | Cloud Claude models |
| Fake provider | Deterministic tests with scripted responses |

No model identifier is hard-coded into the core. Configuration selects provider
and model. Each adapter declares whether it supports native tool calling,
streaming, images, audio, structured output, usage reporting, and provider-side
conversation state.

The first Ollama profile must be benchmarked and tuned for the confirmed 8 GB
Pi. Initial defaults should favor a small quantized model, bounded context,
bounded output, and one model request at a time. The exact model and
quantization are selected from measured Pi results rather than assumed in this
plan. Larger models may be selectable but are not part of the minimum hardware
acceptance target.

### 13.3 Configuration

A non-secret TOML configuration is recommended:

```toml
[agent]
default_provider = "ollama"
fallback_providers = []
max_model_turns = 6
max_tool_calls = 8
request_timeout_seconds = 600
model_inactivity_timeout_seconds = 120

[providers.ollama]
model = "configured-by-user"
base_url = "http://127.0.0.1:11434"
max_loaded_models = 1

[providers.openai]
model = "configured-by-user"
api_key_env = "OPENAI_API_KEY"

[mcp]
user_server_directory = "~/.config/ninjarobot_pi5/mcp"

[skills]
user_directory = "~/.config/ninjarobot_pi5/skills"

[memory]
database_path = "~/.local/share/ninjarobot_pi5/agent.sqlite3"
transcript_retention_days = 7

[profile]
name = "default"
```

API keys must come from environment variables, an operating-system key store,
or a separate secret manager. They must not be committed to TOML, SQLite,
logs, prompts, or action events.

### 13.4 Provider selection and fallback

Provider selection is explicit. Ollama on `127.0.0.1` is the default and must
work on the 8 GB Pi without a cloud credential. A setup command should show
available adapters, check health, and save the user's choice. LAN-hosted Ollama
is not required for the first release, although the configurable base URL keeps
that future option inexpensive.

Fallback is allowed for language generation when configured, but only at a
safe boundary. Before a fallback model continues a tool-using turn, it receives
the action ledger and observed results so it cannot assume an action failed and
repeat it.

### 13.5 Adding a provider

A new provider requires:

1. one adapter implementing `LLMProvider`
2. capability metadata
3. configuration validation
4. contract tests using recorded or fake provider responses
5. optional live tests excluded from the default suite
6. documentation

It must not require changes to memory storage, IDE adapters, or core tool
execution.

## 14. Persistent memory design

### 14.1 What belongs in memory

V4 needs several distinct stores:

| Store | Lifetime | Examples |
| --- | --- | --- |
| Current turn | One request | Parsed intent and pending tool result |
| Session context | One conversation | Recent messages and active plan |
| User profile | Long term | Name, preferred language, response style |
| Preferences | Long term | Quiet buzzer, preferred local model |
| Task recipes | Long term | A user-approved sequence used frequently |
| Episodic summaries | Long term | Concise summaries of useful past sessions |
| Action ledger | Durable audit | Requested, started, finished, cancelled actions |
| Robot configuration | Authoritative config | Pins, limits, enabled devices |

Robot configuration is not learned memory. The model may propose a configuration
change, but an approved configuration service performs and records it.

### 14.2 Storage choice

SQLite is the recommended first persistent store because it is local,
transactional, available on macOS and Raspberry Pi, easy to back up, and does
not require a server.

The first retrieval system should use structured queries plus SQLite FTS5 text
search. Semantic vector retrieval can be added behind a `MemoryIndex` interface
later. V4 does not need a vector database to ship its first reliable version.

Recommended tables:

```text
schema_migrations
users
preferences
sessions
messages
memory_items
task_recipes
action_events
memory_audit_events
```

Every memory item includes owner/scope, kind, content, source, confidence,
creation time, update time, optional expiry, and sensitivity.

### 14.3 Memory write workflow

```mermaid
flowchart LR
    E["Turn events"]
    X["Extract candidate"]
    V["Validate and classify"]
    D["Deduplicate"]
    P["Privacy and consent policy"]
    W["Transactional write"]
    A["Audit event"]

    E --> X --> V --> D --> P
    P -->|approved| W --> A
    P -->|not approved| A
```

The model may suggest a memory candidate, but it never writes directly to the
database. Deterministic code checks type, size, scope, consent, duplicates, and
sensitive data.

### 14.4 Memory retrieval

The context builder retrieves only a small, relevant set:

1. authoritative robot state/configuration
2. current session messages or summary
3. explicit user preferences
4. relevant task recipes
5. a bounded number of episodic memories

Retrieved items retain provenance so the agent can distinguish a user-stated
preference from a low-confidence inferred behavior.

### 14.5 User control and privacy

The CLI must support:

```text
ninjarobot_pi5_cli memory list
ninjarobot_pi5_cli memory show <id>
ninjarobot_pi5_cli memory forget <id>
ninjarobot_pi5_cli memory export
ninjarobot_pi5_cli memory clear-session <id>
```

Deletion is an application operation with an audit event. Secrets, raw
credentials, and raw microphone audio are not stored as ordinary memory.
Camera media is not retained unless the user explicitly requests it. Any media
retention needs a separate opt-in policy.

### 14.6 Provider state is not long-term memory

Some cloud APIs can maintain conversation objects between responses. That can
reduce adapter work for a live session, but:

- it is provider-specific
- retention and privacy rules differ
- it may not be available offline
- it does not contain IDE action truth
- switching providers would lose it

Therefore, V4's own session store and action ledger remain authoritative.

## 15. End-to-end data flow

Example: “Look left, and if something is closer than 20 cm, warn me.”

```mermaid
sequenceDiagram
    participant U as User
    participant A as ninjarobot_pi5_agent
    participant M as Model adapter
    participant P as Policy
    participant I as ninjarobot_pi5_ide
    participant S as pi5servo
    participant D as pi5vl53l0x

    U->>A: Natural-language request
    A->>A: Load session, preferences, and robot state
    A->>M: Messages plus enabled tool schemas
    M-->>A: Proposed ordered tool calls
    A->>P: Validate plan and risk
    P-->>A: Approved within configured limits
    A->>I: Move request with action and idempotency IDs
    I->>I: Validate and lock servo resource
    I->>S: Execute movement
    S-->>I: Device result
    I-->>A: Normalized successful result
    A->>I: Distance-read request
    I->>D: Read sensor
    D-->>I: Measurement
    I-->>A: Normalized distance
    A->>A: Evaluate deterministic threshold
    A-->>U: Result and warning if required
    A->>A: Append action events and approved memory candidates
```

The distance comparison should be deterministic application logic, not a second
model guess.

## 16. Observability and operations

Use structured logs with:

- timestamp
- severity
- component
- session ID
- turn ID
- action ID
- capability
- provider
- stable error code

Prompts and model output may contain private data, so full prompt logging is off
by default. Development logs should use redaction.

Useful local metrics:

- provider latency and failures
- tool-call validation failures
- action queue time and duration
- device health changes
- cancellations
- unknown-outcome events
- memory retrieval and write failures

A single `health` command should summarize agent, provider, IDE, drivers,
database, and optional devices without invoking dangerous hardware behavior.

## 17. Configuration and deployment

Configuration precedence should be:

```text
safe built-in defaults
  < project/system configuration
  < user configuration
  < explicit CLI argument
```

Secret values are resolved separately and never printed by configuration
inspection.

The deployment baseline is:

- Raspberry Pi 5 with 8 GB RAM
- 256 GB NVMe storage
- active cooling
- Raspberry Pi OS Lite 64-bit
- Python 3.11
- headless operation
- normal internet access
- Ollama running locally on the Pi
- one single-owner service process for agent, IDE, hardware, MCP sessions, and
  the optional FastAPI web server
- locally generated or administrator-supplied HTTPS certificate for LAN access
- exclusive browser controller lease with heartbeat and reconnect-token expiry
- no router port forwarding or public-internet exposure
- writable application data on the NVMe drive
- explicit device permissions
- shutdown hooks that cancel work and close adapters

The application starts manually by default. An optional systemd service may be
provided and enabled manually, but installation must not silently enable
auto-start. The CLI can reconnect to an already-running service, stop only the
web interface, or request an orderly stop of the complete agent service. Quitting
one CLI client does not stop the service.

## 18. Clean-build and reference strategy

NinjaRobotPi5V4 is not an in-place migration of the old runtime:

1. Record the copied driver baseline without changing it.
2. Remove only generated cache artifacts copied into the new root.
3. Create new root workspace files and the two new V4 packages.
4. Build IDE adapters around the existing public driver contracts.
5. Reimplement only the integrated robot behaviors V4 actually needs.
6. Build and validate `ninjarobot_pi5_agent`.
7. Compare useful historical behavior through tests and documentation, without
   importing or shipping the old runtime.

The old NinjaClawBot repository remains an external historical reference and
rollback source. OpenClaw modules that happen to remain inside immutable
`pi5mic` are never used by V4.

## 19. Testing strategy

### 19.1 Test layers

| Test type | Runs on macOS | Runs on Pi | Purpose |
| --- | --- | --- | --- |
| Unit tests with fakes | Yes | Yes | Pure behavior and error paths |
| Contract tests | Yes | Yes | Every adapter obeys the common interface |
| Agent scenario tests | Yes | Yes | Scripted model/tool conversations |
| IDE dry-run integration | Yes | Yes | Multi-component flow without hardware |
| Provider live tests | Optional | Optional | Verify external API compatibility |
| Driver hardware tests | No | Yes | Verify real devices |
| Full robot acceptance | No | Yes | Validate safety and end-to-end behavior |

Hardware tests must have explicit pytest markers and must not run in the default
macOS suite.

### 19.2 Deterministic agent scenarios

The fake model provider should script:

- direct answer with no tool
- one successful tool
- multi-step tool sequence
- invalid tool arguments
- unavailable capability
- confirmation required
- user cancellation
- provider timeout before any action
- provider failure after an action succeeds
- IDE timeout with unknown outcome
- repeated tool call with the same idempotency key
- memory write rejected by privacy policy

### 19.3 Quality gates

The normal workspace gate after relevant code changes is:

```bash
uv run --extra dev python -m compileall \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src

uv run --extra dev ruff check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent tests
uv run --extra dev ruff format --check \
  ninjarobot_pi5_ide ninjarobot_pi5_agent tests
uv run --extra dev pytest tests ninjarobot_pi5_ide/tests ninjarobot_pi5_agent/tests
```

If static typing is adopted in Phase 1, its command becomes a required gate for
new V4 packages. The immutable `pi5*` packages retain their own package-local
commands. Phase 0 records those baseline results; later V4 gates do not format,
rewrite, or silently update the copied packages.

Every phase also requires:

- focused tests for changed modules
- `git diff --check`
- documentation review
- no unexplained decrease in the baseline test count
- a recorded result for each required gate

## 20. Confirmed hardware profile

### 20.1 Bus and pin allocation

| Function | Confirmed connection | V4 rule |
| --- | --- | --- |
| Passive buzzer | BCM GPIO27 | Use the existing `pi5buzzer` API |
| Direct servo 1 | BCM GPIO12 | RP1 hardware PWM; endpoint `gpio12` |
| Direct servo 2 | BCM GPIO13 | RP1 hardware PWM; endpoint `gpio13` |
| HAT servo 1 | DFR0566 physical PWM0 | Endpoint `hat_pwm1` |
| HAT servo 2 | DFR0566 physical PWM1 | Endpoint `hat_pwm2` |
| HAT servo 3 | DFR0566 physical PWM2 | Endpoint `hat_pwm3` |
| HAT servo 4 | DFR0566 physical PWM3 | Endpoint `hat_pwm4` |
| DFR0566 control | I2C bus 1, address `0x10` | Mandatory expansion board |
| VL53L0X | I2C bus 1, address `0x29` | One sensor; shared bus |
| Display data | SPI0, CE0, MOSI GPIO10, SCLK GPIO11, CE0 GPIO8 | 32 MHz initial setting |
| Display control | DC GPIO4, RST GPIO5, BL GPIO6 | Rotation 90°, brightness 75% |
| Camera | Raspberry Pi CSI camera through Picamera2 | 1280×720 initial capture |
| Microphone | Default USB audio input | 16 kHz, mono |

No other UART, I2S, SPI, or HAT interface is currently in scope.

The user's phrase “software PWM pin 12 and 13” is normalized here to **RP1
hardware PWM on GPIO12 and GPIO13**. Python-timed/software PWM is prohibited for
production servo control. The Pi firmware must enable the matching two-channel
PWM overlay, and signal accuracy is verified on the Pi with a logic analyzer or
oscilloscope before a servo is attached.

Planned Raspberry Pi firmware setting:

```ini
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

This setting is applied only during the later Pi setup phase, never on the
macOS development computer.

### 20.2 DFR0566 servo topology

DFRobot's official DFR0566 documentation states that:

- the board provides four PWM ports, PWM0 through PWM3
- its on-board STM32 generates those PWM signals
- the Raspberry Pi controls them over I2C
- the board exposes Raspberry Pi I2C, SPI, UART, I2S, and BCM-numbered digital
  connections
- its external PWM-power input is specified as 6–12 V

References:

- [DFR0566 official getting-started guide](https://wiki.dfrobot.com/dfr0566/docs/22892)
- [DFR0566 official product page](https://www.dfrobot.com/product-1930.html)

The four HAT servos therefore use the DFR0566's MCU-managed PWM ports, while
the two GPIO12/GPIO13 servos use the Pi's independent RP1 hardware PWM.

Phase 4 defaults to two TowerPro MG90D 360-degree continuous-rotation motors on
the digital D12/D13 connections, using native GPIO12/GPIO13 hardware PWM. The
owner reports red wires on D12/D13 `+`, a measured voltage within the MG90D
4.8–6.6 V range, and this power chain: official Raspberry Pi 27 W supply to
Geekworm X1208, then Raspberry Pi/DFR0566, then both motors.

There is no accessible physical emergency power disconnect. The owner
explicitly approved Phase 4 real-motion support with that residual risk.
Software stop, obstacle monitoring, undervoltage stop, and watchdog controls
do not replace a physical cutoff. The four dedicated HAT PWM endpoints remain
optional future expansion. Every added servo requires a new voltage, current,
protection, grounding, and disconnect review.

### 20.3 Display orientation

The required display orientation is 90° horizontal with brightness set to 75%.
The copied driver source defaults to 90°, while its copied `display.json`
contains 0°. Because `pi5disp` is immutable, V4 does not edit that file. The
IDE's V4-owned robot configuration explicitly requests DC GPIO4, reset GPIO5,
backlight GPIO6, rotation 90°, and brightness 75% when constructing or invoking
the display.

### 20.4 Hardware-owned V4 configuration

The V4 root keeps its own authoritative robot configuration. It records the
confirmed mapping above and passes values to driver constructors or adapter
calls. It does not rewrite configuration files inside the copied libraries.

### 20.5 Remaining hardware-record items

The logical topology is confirmed, but these electrical or product identifiers
must be recorded before the corresponding powered Pi checklist:

- passive-buzzer module voltage/current and whether a transistor driver is used
- exact ST7789V board revision, supply voltage, and backlight polarity
- exact Raspberry Pi camera module and CSI connector, including confirmation
  that continuous autofocus is supported
- exact USB microphone model and ALSA device identity
- whether speaker/audio output is required in a later phase
- any future servo beyond the two default MG90D motors and its supply design

These items do not block root scaffolding, contracts, fakes, or macOS adapter
development. They do block production hardware certification for the affected
capability.

### 20.6 Live Pi observations recorded on 2026-07-25

The pre-Phase-1 hardware run recorded:

- Raspberry Pi 5 Model B Rev 1.1, Debian 13, kernel 6.18.34
- DFR0566 detected at I2C `0x10`
- VL53L0X detected at `0x29` with correct identification registers, but the
  immutable driver times out during reference calibration
- OV5647 camera detected at `0x36`; native capture works, but Picamera2 is not
  available to the Python environment used by `pi5camera`
- USB PnP Sound Device detected; native mono capture works at 44.1 kHz, while
  `pi5mic` is blocked by missing PortAudio and local Whisper assets
- MG90D servos are connected to GPIO12/GPIO13 through the HAT digital
  connectors and were not moved during this historical audit because no
  accessible emergency disconnect existed; the later Phase 4 decision
  explicitly accepts that residual risk for ordered operator testing
- buzzer command paths and both servo backend probes completed
- display command paths completed; visual sign-off is still required

The complete evidence and rollback record is
`docs/validation/raspberry-pi-hardware-validation-2026-07-25.md`.

## 21. Raspberry Pi 5 validation policy

No hardware validation will be run during macOS development. A phase that
changes hardware-facing behavior produces a Pi checklist, expected results,
safety notes, and a pass/fail report template.

The checklist is executed later on a Raspberry Pi 5 by an authorized operator.
Implementation can proceed on macOS through fake and contract tests, but a
hardware-facing phase is not production-certified until its Pi checklist
passes.

General Pi safety:

- verify wiring and voltage before powering devices
- begin servo tests with conservative angles and no mechanical load
- keep an accessible power cutoff
- use short buzzer output at low duty where supported
- avoid storing unintended camera or microphone media
- verify sensor cleanup after failures and cancellation
- test one device before cross-device behaviors

## 22. Phased implementation plan

Each phase requires approval before coding begins. A phase is complete only
when its deliverables, macOS gates, documentation, and any required deferred Pi
checklist are present.

### Phase 0: Clean root, immutable baseline, and project governance

**Objective**

Create a clean, reproducible NinjaRobotPi5V4 workspace without modifying any
copied driver.

**Deliverables**

- Remove copied `__pycache__`, `.pytest_cache`, and `.ruff_cache` artifacts.
- Add root `README.md`, `AGENTS.md`, `.gitignore`, `pyproject.toml`, and
  workspace `uv.lock`.
- Add `DevelopmentGuide.md` and `DevelopmentLog.md`.
- Record checksums or Git tree state for every immutable `pi5*` directory.
- Record current package versions, exports, tests, CLI behavior, and assets.
- Add an architecture-decision directory and ADR template.
- Add root-owned hardware markers and baseline scripts without editing
  driver-local tests.
- Add an immutable-driver policy to `AGENTS.md`.
- Add an adapter containment matrix for every known audit finding.
- Add the confirmed hardware mapping and unresolved servo-power record.
- Record historical behavior used for comparison without copying the old
  OpenClaw or `ninjaclawbot` runtimes.

**Pi validation**

- Run and record each copied package's existing test and lint commands without
  changing failures or formatting its files.
- Validate the root workspace and documentation.
- Verify copied driver checksums are unchanged after all Phase 0 commands.
- No physical-device test.

**Exit criteria**

- Baseline report is committed.
- Every copied driver is demonstrably unchanged.
- Known driver risks have a wrapper containment rule or a disabled-capability
  decision.
- Root governance and naming use `NinjaRobotPi5V4` consistently.
- Servo hardware power remains explicitly blocked until its electrical record
  is complete.

### Phase 1: V4 contracts and package skeletons

**Status: Complete (2026-07-26)**

**Objective**

Define stable boundaries before migrating behavior.

**Deliverables**

- Add `ninjarobot_pi5_ide` and `ninjarobot_pi5_agent` packages.
- Add unified `ninjarobot_pi5_cli` entry point.
- Define capability, action, result, error, provider, tool, session, and memory
  contracts.
- Add fake IDE, fake provider, fake clock, and deterministic ID helpers.
- Choose validation library and static typing policy through ADRs.
- Add root workspace sources, test paths, and commands.
- Add configuration schema with secret references.

**Pi validation**

- Contract unit tests.
- Serialization round-trip tests.
- Configuration validation tests.
- Compile, Ruff, formatting, pytest, and selected type checking.

**Exit criteria**

- No agent package imports a driver.
- Contract documentation includes examples and error semantics.
- Copied driver checksums remain unchanged.

### Phase 2: IDE core and one reference adapter

**Status: Complete (2026-07-26)**

**Objective**

Build the capability registry, lifecycle, scheduler, resource locks, action
ledger, dry-run CLI, and one simple adapter end to end.

The recommended first adapter is `pi5vl53l0x` because a read-only sensor
capability is easier to validate safely than motion.

**Deliverables**

- IDE registry and adapter discovery.
- Execution engine and durable action records.
- Resource ownership and bounded queue.
- Standard errors and health.
- CLI commands and fake backend.
- Distance sensor adapter.

**Pi validation**

- Race, cancellation, timeout, idempotency, and lifecycle tests with fakes.
- CLI tests.
- Unknown-outcome behavior tests.
- Full workspace gates.
- Initialize, read, timeout, close, restart, and repeated-read checks for
  VL53L0X.

**Exit criteria**

- A dry-run action and a real-adapter contract share identical result shapes.
- Repeating an action ID cannot duplicate execution.

### Phase 3: Integrate all immutable device libraries through IDE adapters

**Status: Complete; all Phase 3.1–3.5 physical validation passed operator
review (2026-07-26)**

**Objective**

Add adapters incrementally without changing the copied standalone libraries.

**Order**

1. `pi5buzzer`
2. `pi5disp`
3. `pi5servo`
4. `pi5camera`
5. `pi5mic`

Each device is its own subphase and review.

The Phase 3.3 servo adapter was validated with a six-endpoint-capable topology:

- `gpio12` and `gpio13` use the Pi 5 RP1 hardware-PWM backend
- `hat_pwm1` through `hat_pwm4` map to DFR0566 physical PWM0 through PWM3
- the DFR0566 uses I2C bus 1 at address `0x10`
- the adapter must create or select the copied library's supported mixed
  hardware backend without changing `pi5servo`
- every servo begins at its safe calibrated center and is validated one at a
  time before group motion
- group motion remained disabled during Phase 3.3. Phase 4 changes the default
  active topology to calibrated GPIO12/GPIO13 and adds its own guarded
  two-motor group boundary.

**Deliverables per device**

- Capability descriptors.
- Adapter and fake.
- CLI manual-test command.
- Resource and risk classification.
- Lifecycle, cancellation, and error tests.
- Documentation and deferred Pi checklist.

**Pi validation**

- Existing driver tests run as immutable baselines; all new tests live in V4
  root or IDE test directories.
- Adapter contract tests.
- Cross-device lock-order tests as resource combinations grow.
- Full workspace gates after every subphase.
- One device-specific checklist after every subphase.
- No full-robot behavior until individual device checks pass.

**Exit criteria**

- Every current device is available through the IDE.
- The agent-facing layer has no direct driver import.
- Checksums prove that all six copied driver directories remain unchanged.

### Phase 4: Integrated V4 robot behaviors

**Objective**

Implement validated cross-device expressions, continuous wheel movements,
private action creation, two-level stopping, and a user-facing IDE tool. No
historical runtime or OpenClaw code is imported.

**Deliverables**

- Strict behavior, stage, display, melody, wait, and logical-drive schemas.
- Read-only bundled assets plus owner-private confined user assets.
- Sequential stages with concurrent operations inside each stage.
- Twenty independently implemented, scalable, animated Pillow faces:
  `idle`, `happy`, `laughing`, `sad`, `cry`, `angry`, `surprising`, `sleepy`,
  `speaking`, `shy`, `scary`, `exciting`, `confusing`, `greeting`,
  `listening`, `thinking`, `curious`, `success`, `warning`, and `error`.
- Matching existing `pi5buzzer` emotion melodies. Normal movement behaviors
  deliberately omit buzzer output.
- Default movement commands: `move_forward`, `move_backward`, `turn_right`,
  and `turn_left`. `stop` remains a safety command rather than an asset.
- Special combinations: bounded `greeting`, guarded `celebrate`, and
  non-moving `error_warning`. Emergency Stop and Resume remain direct safety
  operations rather than assets.
- Default logical roles: GPIO12 left MG90D wheel motor and GPIO13 right MG90D
  wheel motor.
- Exact motor targets: forward `+45/-45`, backward `-30/+30`, right
  `+45/+45`, and left `-45/-45`.
- Motion starts without a distance-clear preflight. The exact VL53L0X `8191`
  clear-space/out-of-range sentinel is clear. Null, invalid, missing, and stale
  readings do not stop motion. Three consecutive valid readings at or below
  50 mm cause a Level 1 stop for forward and turning movement. Backward
  movement is warning-only.
- Level 1 stops for obstacle, current undervoltage, and watchdog timeout.
- Level 2 cleanup for Ctrl+C, shutdown, explicit stop, and driver failure.
  Driver failure remains latched until explicit confirmation and healthy
  probes.
- Interactive and scriptable `ninjarobot-ide-tool` with hardware status,
  configuration discovery/import, behavior list/show/health/simulate/run,
  private action creation/validation, stop, and resume commands.
- A Blessed-style interactive menu that directly executes selections, keeps
  face animation alive until it is changed or stopped, provides Back from
  every submenu, exposes a global Emergency Stop shortcut, reconstructs and
  health-checks modules on Resume, and keeps advanced scriptable commands.
- A persistent red Emergency Stop sign on the display until Resume or Quit.
- Simulation preview and user confirmation before saving new actions. Future
  AI-proposed actions use the same approval boundary.

**Pi validation**

- Safe configuration and simulation tests before any real hardware.
- Real health probes that move no motors and record no media.
- Real greeting and expression checks before actuator use.
- Raised-wheel movement checks with a second terminal prepared to stop.
- Front-obstacle debounce and Level 1 resume check.
- Ctrl+C/cross-process stop and full cleanup check.
- Power-risk and watchdog triggers are not intentionally induced on hardware.
- Immutable driver verification before and after the phase.

**Exit criteria**

- All approved V4 behaviors work through IDE-owned APIs and the IDE tool.
- Private actions are validated, previewed, confined, and confirmation-gated.
- Level 1 and Level 2 stop behavior passes deterministic tests.
- No V4 package imports `ninjaclawbot` or OpenClaw.

**Implementation result**

The original Phase 4 physical checklist and the 2026-07-27 refinement checklist
were reported passed by the operator. The refinement completed the 20-face
catalog, direct interactive menu, distance sentinel handling, persistent
emergency sign, resume path, and configuration workflow. Its recorded software
gate passed 213 tests, strict mypy, Ruff lint and formatting, and unchanged
managed-driver provenance. The operator subsequently reported the complete
installation-guide workflow passed on Raspberry Pi 5.

### Phase 5: Agent core, local interfaces, MCP, and skills

**Implementation record — 2026-07-28**

Phase 5.0 through Phase 5.8 are implemented. The immutable-driver check, Python
compilation, Ruff lint and formatting, strict mypy, 278 automated tests,
JavaScript syntax check, wheel-package asset inspection, and simulated
single-owner service/HTTPS lifecycle smoke test pass. No managed driver changed
during Phase 5. Qwen3:4B remains a candidate until the Raspberry Pi benchmark
passes. Live Tavily, camera, microphone, browser, network-loss, and raised-wheel
motion checks remain operator validation and are not represented as completed.

**Objective**

Implement the bounded agent state machine with Ollama running locally on the
confirmed 8 GB Raspberry Pi 5. Provide conversational CLI and local-network web
interfaces, default real-time Tavily search through MCP, and safe extension
contracts for future MCP servers and agent skills. Language generation remains
local by default, while web search intentionally requires internet access.

#### Phase 5.0 — Close Phase 4 and freeze contracts

**Objective**

- Record the completed Phase 4 operator validation.
- Re-run the full workspace gate and immutable-driver verification.
- Freeze the IDE capability, action-ledger, cancellation, and two-level-stop
  contracts used by the agent.

**Likely files**

- Phase 4 validation records
- `NinjaRobotPi5V4_ImplementationPlan.md`
- `DevelopmentLog.md`

**Validation**

- Immutable-driver verification before and after the phase.
- Ruff lint and format checks, strict mypy, and the full pytest suite.

**Hardware risk**

None. This is evidence and contract work.

**Documentation**

Close the Phase 4 validation status before agent implementation begins.

#### Phase 5.1 — Agent contracts, service ownership, and persistence

**Objective**

- Session manager and context builder.
- Plan/tool/result normalized models.
- Bounded state machine with model-turn, tool-call, wall-clock, and context
  limits.
- Single-owner service lifecycle and reconnectable client contract.
- Seven-day conversation transcript retention and deletion.
- Structured event stream for chat, service state, tool execution, warnings,
  recovery, and errors.
- Quit-CLI, stop-web-interface, and stop-agent-service remain distinct actions.

**Likely files**

- `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/`
- agent migrations and tests
- root configuration examples

**Validation**

- Deterministic lifecycle, restart, retention, cancellation, corruption, and
  concurrent-client tests.
- A second service owner must be rejected without touching hardware.
- Standard workspace quality gate and immutable-driver verification.

**Hardware risk**

None. Use fake IDE clients only.

**Documentation**

Document data locations, seven-day retention, service ownership, and shutdown.

#### Phase 5.2 — Unified tool registry and deterministic policy

**Objective**

- Introduce a `ToolProvider` contract.
- Register IDE capabilities through an IDE tool provider.
- Namespace every tool and reject collisions.
- Policy and confirmation engine.
- Recovery matrix implementation.
- Preserve the durable action ledger across model or client failures.
- Implement one-time physical-motion session arming. Direct web D-pad commands,
  the Celebrate button, and natural-language motion can execute without a
  second per-action dialog only while the session is armed and healthy.
- Emergency stop remains independent of model availability.

**Likely files**

- agent tool registry, policy, and recovery modules
- IDE capability-adapter boundary
- policy and scenario tests

**Validation**

- Table and property tests for risk, arming, privacy, cancellation,
  idempotency, unknown outcomes, and emergency stop.
- Prove that no agent or provider module imports a `pi5*` driver.
- Standard workspace quality gate and immutable-driver verification.

**Hardware risk**

None during this subphase; all actions use deterministic fakes.

**Documentation**

Document tool namespaces, profiles, session arming, and recovery rules.

#### Phase 5.3 — MCP host and default Tavily web search

**Objective**

- Implement MCP client sessions over local `stdio` and remote Streamable HTTP.
- Discover and normalize MCP tools through the unified registry.
- Add server configuration, allowlists, health, inspect, test, enable, disable,
  remove, reload, timeout, cancellation, and result-size controls.
- Add environment-based bearer-token resolution with redaction.
- Add `ninjarobot-agent secret set NAME`, using hidden input and an owner-only
  secret file, so keys do not enter shell history or ordinary configuration.
- Ship Tavily as the default configured search provider after
  `TAVILY_API_KEY` setup.
- Enable only raw Tavily tool `tavily_search` by default, publish it as
  `mcp.tavily.tavily-search`, and enforce basic depth, at most five results, no
  images, and no raw page content.
- Require source links in search-grounded answers.
- Treat all MCP metadata and output as external untrusted content.
- Refuse any attempt by MCP content to change safety policy or invoke hardware
  outside an independently validated agent tool call.

**Likely files**

- MCP client manager and transport adapters
- MCP configuration and secret resolver
- fake MCP server and protocol fixtures
- agent CLI MCP-management commands

**Validation**

- Fake-server initialization, discovery, call, list-change, cancellation,
  timeout, malformed result, oversized result, collision, and shutdown tests.
- Prompt-injection and secret-redaction tests.
- Optional live Tavily search test, excluded unless a key is deliberately set.
- Pi network-loss, quota, authentication, and clean-shutdown tests.
- Standard workspace quality gate and immutable-driver verification.

**Hardware risk**

None. MCP servers have no direct IDE or driver reference.

**Documentation**

Update `InstallationGuide.md` with default Tavily setup, health testing, MCP
server installation, configuration formats, security rules, and
troubleshooting. Update `DevelopmentGuide.md` with the `ToolProvider` contract.

#### Phase 5.4 — Agent skills and system-prompt composition

**Objective**

- Implement strict `skill.json`, confined `instructions.md`, and optional
  `examples.json` loading.
- Provide read-only bundled skills and a confined user skill directory.
- Validate tool allowlists, inputs, limits, paths, sizes, and schema versions.
- Compose prompts in immutable-safety, identity, runtime-state, skill, and
  conversation order.
- Add list, inspect, validate, install, simulate, enable/disable, and remove
  commands.
- Require preview and explicit approval before saving an AI-proposed skill.
- Include one offline demonstration skill and one Tavily search skill.

**Likely files**

- skill manifest models, repository, prompt composer, and CLI
- bundled example skill assets
- validation and scenario tests

**Validation**

- Path traversal, symlink, overwrite, oversized asset, unknown schema, forbidden
  tool, prompt-override, atomic install, cancellation, and simulation tests.
- Verify that fixed hardware choreography remains inside IDE behaviors.
- Standard workspace quality gate and immutable-driver verification.

**Hardware risk**

None. New skills validate and simulate before any physical test.

**Documentation**

Document the exact skill directory and file formats, installation workflow,
simulation, approval, troubleshooting, and behavior-versus-skill distinction.

#### Phase 5.5 — Fake provider, Ollama adapter, and model benchmark

**Objective**

- Fake provider and Ollama adapter.
- Provider-neutral streaming and structured tool-call handling.
- Pi-oriented model configuration with bounded context, output, concurrency,
  and memory use.
- Benchmark command that records model load time, first-token latency,
  tool-call correctness, peak memory, temperature, and throttling.
- Benchmark Qwen3:4B in candidate quantizations before choosing the default.
- Reject or replace Qwen3:4B if it does not meet the accepted Pi thresholds;
  model selection must not change agent, tool, MCP, skill, or IDE contracts.

**Likely files**

- provider adapters and provider registry
- benchmark command, reports, and fixtures
- model profile configuration

**Validation**

- Provider contract, malformed output, streaming cancellation, timeout,
  unavailable model, and bounded-loop tests.
- Sustained Pi benchmark under active cooling with no memory exhaustion or
  thermal throttling.
- Standard workspace quality gate and immutable-driver verification.

**Hardware risk**

None to actuators. This phase creates substantial CPU, memory, and thermal load.

**Documentation**

Record tested model tags, quantization, context, latency, memory, temperature,
and acceptance thresholds without claiming unmeasured performance.

#### Phase 5.6 — Conversational and interactive CLI

**Objective**

- Add streaming chat, history, status, execution logs, and clear error reports.
- Support `/help`, `/exit`, `/clear`, and `/status`.
- Provide scriptable service, web, MCP, skill, session, and health commands.
- Add the `ninjarobot-agent` package entry point while preserving
  `ninjarobot_pi5_cli` and `ninjarobot-ide-tool`.
- Provide an interactive menu consistent with `ninjarobot-ide-tool`.
- Allow a new CLI process to reconnect and stop an already-running web
  interface or agent service.

**Likely files**

- agent CLI, service client, interactive UI, and tests

**Validation**

- Scriptable and interactive command parity.
- Reconnect, Ctrl+C, terminal loss, streaming, cancellation, and orderly
  service-stop tests.
- Standard workspace quality gate and immutable-driver verification.

**Hardware risk**

None for simulated acceptance; later physical conversation tests use the
existing IDE safeguards.

**Documentation**

Add complete start, reconnect, chat, stop-web, stop-service, MCP, skill, and
troubleshooting instructions.

#### Phase 5.7 — FastAPI HTTPS web interface

**Objective**

- Serve a portrait-first, no-page-scroll interface for mobile Chrome, mobile
  Safari, and desktop browsers. Landscape shows a rotate-back safety overlay.
- Display AI chat, system status, tool execution logs, robot actions, warnings,
  errors, and recovery events.
- Provide D-pad Move Forward, Move Backward, Turn Left, and Turn Right controls.
- Provide X Emergency Stop, Y Resume with confirmation, A Greeting, and
  B Celebrate controls.
- Capture and temporarily preview a camera image without retaining it by
  default.
- Start/stop USB microphone capture and send completed audio into the approved
  Phase 5 text workflow without adding spoken robot responses.
- Use browser speech recognition for English and Japanese, place recognized
  text in the message input, and require Send before transmission.
- Keep Live Activity in a hidden bottom drawer with tap and slide controls.
- Suppress D-pad text selection and touch callouts with Pointer Events and a
  touch-event fallback.
- Enforce one exclusive browser WebSocket controller lease. A second connection
  receives `423 Locked`.
- Require the active lease identifier on control requests.
- Revoke the lease and stop movement after missed heartbeats.
- Permit short-lived reconnect-token recovery after browser refresh.
- Refuse control endpoints when no active WebSocket lease exists.
- Use a local-CA-signed HTTPS certificate for
  `ninjarobotpi5.local`, provide public-CA export, and document one-time
  Chrome/Safari trust plus the accepted first-device risk.

**Likely files**

- FastAPI application, WebSocket lease manager, HTTPS setup, static web assets,
  event bridge, and tests

**Validation**

- FastAPI contract, WebSocket lease, second-client rejection, heartbeat,
  reconnect, refresh, malformed request, camera lifetime, microphone
  cancellation, language selection, and service-shutdown tests.
- Browser checks in portrait mobile Chrome, portrait mobile Safari, and desktop
  layouts. Landscape must show the rotate-back safety overlay instead of live
  robot controls.
- Network interruption must stop active movement without waiting for a model.
- Standard workspace quality gate and immutable-driver verification.

**Hardware risk**

Camera and microphone privacy risk plus actuator risk during final Pi
acceptance. Start with simulated controls, then camera/microphone, then one
unloaded motion test with the existing stop path available.

**Documentation**

Add HTTPS certificate setup, LAN URL, one-device lease behavior, browser
microphone permissions, English/Japanese selection, privacy, and recovery.

**Pi validation**

- All deterministic agent scenarios.
- Property/table tests for policy.
- Malformed model output and loop-bound tests.
- Provider unavailability and cancellation tests.
- Full workspace gates.
- Text request to safe read-only capability.
- One-time motion-session arming followed by physical motion and stop.
- Model failure before and after a hardware action.
- Emergency stop without model availability.
- Default Tavily health check and one cited current-information search.
- MCP network loss and quota-exhaustion behavior.
- Skill validation, simulation, and one approved bundled skill.
- CLI reconnect and orderly service shutdown.
- HTTPS LAN access, exclusive lease, second-client rejection, heartbeat loss,
  and refresh reconnection.
- Temporary camera preview, USB microphone flow, and browser speech recognition
  in English and Japanese.
- Sustained local Ollama run under active cooling with no thermal throttling or
  memory exhaustion.

**Exit criteria**

- Local Ollama on the 8 GB Pi can complete safe tool tasks within the accepted
  benchmark thresholds recorded during this phase.
- The loop always terminates within configured bounds.
- Current-information requests can use the configured Tavily MCP server and
  present source links, while network or quota failures remain explicit.
- A validated new MCP server and a validated new skill can be installed by
  following `InstallationGuide.md` without changing the agent core.
- CLI and web clients observe the same service, policy, tool registry, action
  ledger, and safety state.
- Only one browser controls the robot, and loss of its lease stops movement.
- No provider code imports a driver.

#### Phase 5.8 — Tested model, presentation, MCP, and controller refinement

**Status**

Implemented on 2026-07-29. The full software gate passes; the dated Raspberry
Pi checklist remains operator work.

**Objective**

- Discover locally installed Ollama models and let the interactive or
  scriptable CLI select one without hard-coding Qwen3:4B.
- Keep model selection provider-neutral so later cloud adapters register
  without rebuilding the agent loop.
- Permit idle-time hot switching and persistent stopped-service selection,
  while blocking switches during responses or robot actions.
- Record exact-model benchmark acceptance as recommended performance and
  quality evidence, without using it as a physical-motion permission gate.
- Continue to require explicit session arming and every existing IDE safety
  check for natural-language physical motion.
- Coordinate silent Idle, Thinking, Speaking, emotion, and action presentation
  only through the IDE-owned robot assembly.
- Keep model-selected emotion display-only, strictly allowlisted, stripped
  from visible and persisted text, and unable to affect safety or permission.
- Update the Tavily preset for current raw server tool name `tavily_search`
  while preserving public `mcp.tavily.tavily-search`.
- Repair browser speech controls and retain review-before-Send behavior.
- Match the approved portrait controller mockup, consolidate AI motion state
  into the Arm button, reserve space above Live Activity, and add a
  user-gesture fullscreen flow with a Safari standalone fallback.

**Validation**

- Ollama `/api/tags` catalog parsing and strict metadata tests.
- Offline persistence, running-service hot switch, busy rejection, previous
  provider cleanup, motion-disarm, informational benchmark, and confirmed-arm
  tests.
- Split-stream presentation directive, invalid face, persisted-text, and IDE
  lifecycle tests.
- Tavily legacy migration, raw/public name mapping, live health, and tool
  discovery checks.
- Browser static contract, WebSocket lease, microphone, touch, fullscreen,
  and packaged-asset tests.
- Full compile, Ruff, formatting, MyPy, pytest, JavaScript syntax,
  immutable-driver, and diff checks after each implementation phase.

**Hardware risk**

Model benchmarking produces CPU, memory, and thermal load. Face validation
uses the display. Final mobile D-pad validation moves raised wheels only.
No managed `pi5*` driver changes are authorized or required.

**Documentation**

Updated `README.md`, `InstallationGuide.md`, `DevelopmentGuide.md`,
`DevelopmentLog.md`, this implementation plan, and the dated Phase 5 model and
controller Raspberry Pi validation checklist.

#### Phase 5.9 — Post-validation motion, HTTPS, and viewport repair

**Status**

Implemented on 2026-07-29. Automated validation passes; Chrome, Safari, and
raised-wheel Raspberry Pi checks remain operator work.

**Objective**

- Let every installed and healthy selected model arm natural-language
  physical motion after the operator's explicit session confirmation.
- Preserve the motion arm, controller lease, policy, IDE motion guards, and
  emergency-stop boundaries independently of benchmark status.
- Serve the generated HTTPS server leaf and local CA as a complete chain.
- Atomically upgrade a valid older generated leaf-only certificate without
  changing its private key.
- Keep CA installation optional where Chrome explicitly permits warning
  bypass, while documenting CA trust as recommended and normally necessary
  for Safari and reliable browser speech.
- Size the D-pad from its allocated grid height so it cannot overlap camera
  and microphone controls in short non-fullscreen mobile viewports.

**Files**

- Agent runtime and interactive model guidance.
- FastAPI certificate generation and migration.
- Browser connection guidance and responsive controller styles.
- Model-selection and web regression tests.
- Project, installation, developer, log, and Raspberry Pi validation
  documentation.

**Validation**

- Unbenchmarked-model confirmed arm and unconfirmed-arm refusal tests.
- Complete-chain creation and leaf-only migration tests that verify private-key
  preservation.
- Static browser contract tests for connection recovery guidance and
  allocation-bounded D-pad sizing.
- Full compile, Ruff, formatting, MyPy, pytest, JavaScript syntax, package
  build, immutable-driver, and diff checks.

**Hardware risk**

Automated validation is simulation-only. Manual natural-language motion and
D-pad checks move actuators and must use raised wheels with Emergency Stop
ready. Certificate and layout checks do not move hardware.

**Documentation**

Update `README.md`, `InstallationGuide.md`, `DevelopmentGuide.md`,
`DevelopmentLog.md`, this plan, and the dated Phase 5 Raspberry Pi validation
checklist.

#### Phase 5.10 — Session-lived authorization and creative behavior composition

**Status**

Implemented on 2026-07-29. Automated validation passes; the dated Raspberry Pi
expression, raised-wheel motion, cancellation, and saving checklist remains
operator work.

**Objective**

- Prevent confirmed motion authorization from expiring while a slow local
  model is still reasoning.
- Make runtime facts unambiguous: `execution_mode = real` means physical
  hardware, and an armed authorization permits trusted motion tools.
- Revoke authorization on Disarm, Emergency Stop, lease loss, model change,
  and service shutdown.
- Cancel active motion work and request a servo stop when a session disarms.
- Let the agent create transient multi-stage behaviors from approved animated
  faces, text, bounded tones, named melodies, and configured logical servo
  roles.
- Keep expression-only and motion-capable tools separate so catalog risk
  remains deterministic.
- Preserve camera and microphone privacy confirmation independently from
  motion arming.
- Require explicit request confirmation before saving an AI-created behavior.

**IDE deliverables**

- `ToneOperation` with the existing buzzer limits: 20–20,000 Hz, 0.05–2
  seconds, and volume 1–128.
- `behavior.execute_expression`, whose published schema excludes drive
  operations.
- `behavior.execute_movement`, whose published schema lists only configured
  logical servo roles and retains all motion guards.
- `behavior.save_user`, classified as maintenance work and backed by the
  confined, atomic, non-overwriting behavior repository.
- Sequential stages, concurrent non-conflicting operations, cancellation,
  shared resources, and return-to-Idle cleanup.

**Agent deliverables**

- Session-lived `MotionArmManager` state.
- Structured real/simulation and motion-authorization runtime facts.
- Model guidance to execute trusted tools rather than incorrectly refusing or
  merely describing an available action.
- Creative composition guidance and exact tool schemas.
- `/confirm <request>` for one explicitly approved interactive request.
- Compatibility fields retained for existing clients.

**Validation**

- Reproduced the physical test timing: a tool call more than five minutes
  after arming remains authorized.
- Unarmed and mismatched-lease motion remains denied.
- Disarm cancels registered motion work and invokes the servo-stop boundary.
- Expression schema omits drive; movement schema rejects unconfigured roles.
- Tone bounds and same-stage buzzer conflicts are rejected.
- Transient expression and movement definitions execute in simulation.
- Model tool-call tests cover armed creative movement.
- Saving is denied without confirmation, succeeds with confirmation, rejects
  duplicates, and remains path-confined.
- Full compile, Ruff, formatting, MyPy, pytest, package-build,
  immutable-driver, JavaScript, manifest, and diff checks.

**Hardware risk**

Automated tests are simulation-only. Physical expression tests energize the
display and buzzer. Dynamic movement tests must start with both wheels raised,
Emergency Stop ready, and short finite drive stages. Floor testing follows
only after cancellation, Disarm, Level 1, and Level 2 checks pass.

**Documentation**

Update `README.md`, `InstallationGuide.md`, `DevelopmentGuide.md`,
`DevelopmentLog.md`, this implementation plan, and
`docs/validation/phase-5-dynamic-behavior-validation-2026-07-29.md`.

#### Phase 5.11 — Generated-behavior compatibility and recovery

**Status**

Implemented on 2026-07-29. The complete local software gate passes; the dated
Raspberry Pi simulation, expression, and raised-wheel movement checklist
remains operator work.

**Objective**

- Reproduce the generic failure from the operator's persisted conversation and
  action history.
- Give small local models a compact behavior-draft format while preserving the
  strict canonical format used for saved behaviors.
- Add a bundled robot-behavior-generation skill with exact expression and
  movement workflows.
- Return correctable validation feedback without implying that hardware may
  have moved when validation failed before execution.
- Recover conservatively from a known movement/expression tool-name routing
  error without weakening motion policy.
- Make pre-output Ollama transport failures and disconnected IPC clients
  recover cleanly.

**IDE deliverables**

- `BehaviorDraftCompiler` for compact and canonical definitions.
- Safe stage-name and finite-duration defaults.
- Named movement resolution through configured logical roles.
- Note-name conversion and documented melody alias normalization.
- Ordered splitting of same-stage display or buzzer conflicts.
- `BEHAVIOR_DRAFT_INVALID`, marked definitely not executed and safe to retry.

**Agent deliverables**

- Bundled `robot-behavior-generation` skill.
- Essential compact-format and expression-versus-movement rules in the base
  prompt for normal CLI and web sessions.
- A 1,024-token output allowance for local models.
- Structured-only correction of explicit motion sent to the expression tool;
  the corrected movement call is evaluated by the normal arm and tool policy.
- One Ollama retry only for connection/read failure before visible output.
- IPC disconnect handling that avoids secondary write failures.

**Validation**

- Nine real failed payloads preserved as non-sensitive regression fixtures.
- Compact and canonical expression/movement compiler tests.
- Invalid-draft pre-execution and safe-retry tests.
- Bundled-skill validation and simulation tests.
- Armed correction reaches the movement capability; unarmed correction is
  denied without an IDE request.
- Pre-output retry, post-output no-retry, and IPC disconnect tests.
- Full compilation, Ruff, formatting, strict MyPy, 299-test pytest, package
  build, wheel-content, immutable-driver, and diff checks.

**Hardware risk**

Automated validation is simulation-only. Physical expression checks energize
the display and buzzer. Physical movement acceptance must use raised wheels,
one-second finite movement, an armed matching session, and an immediately
accessible Emergency Stop. No managed `pi5*` driver changed.

**Documentation**

Update `README.md`, `InstallationGuide.md`, `DevelopmentGuide.md`,
`DevelopmentLog.md`, this plan, and
`docs/validation/phase-5-behavior-generation-repair-validation-2026-07-29.md`.

#### Phase 5.12 — Agent chat system recovery

**Status**

Implemented on 2026-07-29. Automated validation passes; health-check-only and
raised-wheel Raspberry Pi acceptance remain operator work.

**Objective**

- Recover a Level 2 Emergency Stop without restarting the single-owner agent
  service.
- Support `/resume` in both terminal and web chat.
- Reuse the IDE's existing confirmed, all-module health-checked system resume.
- Restore Idle only after successful recovery.
- Keep AI physical-motion authorization separate and disarmed.
- Repair the existing web Y Resume path so it supplies the strict IDE
  confirmation argument and never reports success after a failed probe.

**Deliverables**

- `AgentRuntime.resume_system()` as the shared non-bypassable recovery
  boundary.
- A dedicated owner-only IPC request for terminal chat.
- Terminal `RESUME` confirmation and updated `/help`.
- Web-chat command interception and browser confirmation without an Ollama
  turn.
- Clear success, cancellation, and failed-health-check messages.
- Direct web controls reactivate only after success; AI chat still requires
  `/arm` or **Arm AI Motion**.

**Validation**

- Missing confirmation refuses recovery.
- Runtime submits `{"confirmed": true}` and policy confirmation.
- Successful resume stays AI-disarmed.
- Failed health result raises a clear error and does not reactivate controls.
- IPC routes the exact session to the shared boundary.
- Terminal cancellation sends no service request.
- Terminal and web `/resume` do not become model prompts.
- Web Y Resume shares the corrected path.
- Full compilation, Ruff, formatting, strict MyPy, JavaScript syntax, 306-test
  pytest, package-build, wheel-content, immutable-driver, and diff checks.

**Hardware risk**

Automated tests are simulation-only. A real resume initializes and probes
configured modules but does not intentionally move servos, take a photograph,
or record audio. A separate movement acceptance test must use raised wheels,
explicit `/arm`, a one-second command, and an immediately accessible
Emergency Stop.

**Documentation**

Update `README.md`, `InstallationGuide.md`, `DevelopmentGuide.md`,
`DevelopmentLog.md`, this plan, and
`docs/validation/phase-5-agent-chat-resume-validation-2026-07-29.md`.

#### Phase 5.13 — Restartable recovery, deterministic Idle, and one-shot AI camera

**Status**

Implemented on 2026-07-30. Automated validation passes; physical Raspberry Pi
acceptance remains operator work.

**Objective**

- Repair Level 2 Resume after the distance, camera, and microphone services
  have been stopped.
- Make looping Idle the deterministic post-condition of every normally
  completed foreground behavior.
- Add an explicitly granted, one-shot, temporary AI camera preview.
- Show a visible `3`, `2`, `1` countdown and animated camera icon before and
  during AI capture.

**Deliverables**

- Restartable IDE `suspend()` lifecycle separate from terminal `close()`.
- Health-checked device reinitialization before Resume clears Level 2.
- Canonical Idle restoration for web buttons, agent actions, and generated
  behaviors, with degraded health for an unexpected Idle-task failure.
- Session-and-lease-bound `CameraGrantManager`.
- Terminal and web `/camera`, plus an **AI camera** web button.
- Ephemeral browser preview delivery with JPEG removal from transcripts,
  event history, and model-visible tool results.
- Failed camera attempts keep the grant; a successful delivered preview
  consumes it.

**Validation**

- Immutable drivers unchanged.
- Restart tests cover distance, camera, and microphone suspension.
- Greeting, Celebrate, camera presentation, and foreground behavior tests end
  in Idle.
- Camera policy tests cover confirmation, lease matching, failed-attempt
  release, and successful consumption.
- Agent tests verify that preview bytes are live-only and redacted from
  durable/model context.
- JavaScript syntax, compilation, Ruff, formatting, strict MyPy, and the full
  pytest suite pass.

**Hardware risk**

Resume initializes configured devices but does not intentionally record or
move. AI camera validation takes one temporary photograph. Celebrate may move
the wheel servos, so its physical acceptance requires raised wheels and an
accessible Emergency Stop.

**Documentation**

Update the core project documents and
`docs/validation/phase-5-recovery-idle-camera-validation-2026-07-30.md`.

#### Phase 5.14 — Repeatable one-photo AI camera grants

**Status**

Implemented on 2026-07-30. Automated validation passes; repeatable physical
camera acceptance remains operator work.

**Objective**

Allow the user to issue a new one-photo camera grant after every successful
preview without restarting, clearing, or replacing the active chat session.

**Deliverables**

- Monotonically numbered camera grants per chat session.
- Trusted runtime facts for the current grant, remaining captures, in-flight
  state, and last issued sequence.
- Prompt rules that make a fresh runtime grant override stale assistant text
  about an older consumed grant.
- An explicit requirement to use `robot.camera.preview`, never retained
  `robot.camera.capture`, for this authorization.
- IPC and web responses that report the fresh grant number.
- Same-conversation regression coverage for two independently authorized
  successful previews.

**Validation**

- Immutable managed drivers remain unchanged.
- Compilation, Ruff, formatting, strict MyPy, and the full pytest suite pass.
- Tests cover successful consumption, failure retry, lease binding, sequence
  increments, repeated grants, and JPEG redaction.

**Hardware risk**

Each accepted grant takes one real photograph. It does not move an actuator or
retain a file, but everyone in view must consent before each capture.

**Documentation**

Update the core project documents and the Phase 5 recovery, Idle, and AI camera
validation checklist with a three-grant same-session acceptance test.

#### Phase 5.15 — Deterministic granted camera requests

**Status**

Implemented on 2026-07-30. Automated validation passes; Raspberry Pi camera
acceptance remains operator work.

**Objective**

Prevent any selected language model from verbally refusing a valid one-photo
grant before calling `robot.camera.preview`.

**Deliverables**

- Conservative English and Japanese capture-intent recognition.
- Deterministic no-grant guidance without an LLM turn.
- Direct construction of the fixed temporary-preview tool call when the
  session-and-lease grant is active.
- Existing policy, IDE, countdown, camera animation, cancellation, retry,
  ephemeral delivery, redaction, and Idle behavior remain authoritative.
- Camera questions and negated capture requests continue to normal
  conversation and never trigger the deterministic capture path.
- Accurate `model_turns = 0` reporting for deterministic replies.

**Validation**

- A fake model scripted to refuse is never called during an authorized photo.
- Three successive numbered grants capture three previews in one unchanged
  conversation.
- English, Japanese, negative intent, camera questions, lease mismatch,
  failure retry, live-only JPEG delivery, transcript redaction, and streaming
  response behavior are covered.
- Immutable drivers, compilation, Ruff, formatting, strict MyPy, and full
  pytest pass.

**Hardware risk**

This path captures a real temporary photograph. It does not move servos or
retain the image, but the operator must obtain consent from everyone in view.

**Documentation**

Update the core project documents and the Phase 5 recovery, Idle, and AI camera
validation checklist with explicit model-independence checks.

### Phase 6: Cloud provider adapters

**Implementation status — 2026-07-30**

Implemented in software and ready for opt-in Raspberry Pi/account validation.
The implementation uses one configuration-driven registry for Ollama, OpenAI,
Google Gemini, and Anthropic. All adapters consume the existing
provider-neutral `ModelRequest`, including MCP tools and selected Agent Skill
instructions, and return normalized `ModelTurn` values. No adapter executes a
tool or imports a hardware driver.

Authentication support follows official provider constraints:

- OpenAI API key only; ChatGPT account web login is not exposed as API
  authentication.
- Gemini API key or Google Application Default Credentials created through the
  official `gcloud` browser/no-browser flow.
- Anthropic API key or the official `ant auth login --no-browser` profile.

The provider-first interactive model selector, scriptable provider
authentication/health commands, dynamic model catalogs, safe idle-time
selection, owner-private secrets, provider-safe tool aliases, and optional
pre-tool fallback are implemented. Fallback is disabled by default, never
persists an automatic switch, stops after public output begins, and is not
allowed after a tool has executed in the current request. Recorded/fake
OpenAI, Gemini, and Anthropic responses are part of the default suite. Live
provider tests remain opt-in because they use owner credentials, network
access, and potentially billable API calls.

**Objective**

Add OpenAI, Gemini, and Anthropic without changing the agent or IDE contracts.

**Deliverables**

- OpenAI Responses API adapter.
- Gemini adapter.
- Anthropic adapter.
- Provider capability matrix and setup/health CLI.
- Secret-loading and redaction tests.
- Optional provider fallback at safe boundaries.

**Pi validation**

- Recorded/fake response contract tests by default.
- Opt-in live smoke tests when credentials are intentionally supplied.
- Tool-call normalization parity across providers.
- Fallback tests that prove completed actions are not repeated.
- One read-only and one confirmed action per configured provider.
- Network-loss recovery with final known robot state.

**Exit criteria**

- Changing provider is configuration-only.
- Secrets do not appear in logs, database, or exported memory.

### Phase 7: Persistent memory

**Objective**

Add provider-neutral sessions, profiles, preferences, recipes, summaries, and
the durable action ledger.

**Deliverables**

- SQLite schema and migrations.
- Repositories and transactional service.
- FTS5 retrieval.
- Memory-candidate validation and privacy policy.
- CLI list/show/forget/export operations.
- Backup and restore guide.
- Optional semantic-index interface, with no mandatory vector dependency.

**Pi validation**

- Migration forward/rollback strategy tests.
- Concurrent read/write and interrupted-transaction tests.
- Retrieval relevance fixtures.
- consent, redaction, expiry, export, and deletion tests.
- Provider-switch continuity test.
- Persistence across service and Pi restart.
- Database recovery from a copied backup.
- Storage-pressure behavior.

**Exit criteria**

- Switching model providers retains project-owned memory.
- Users can inspect and delete stored information.

### Phase 8: Voice and multimodal interaction

**Objective**

Add microphone, camera, and optional speech output to the agent without
bypassing the IDE or privacy policy.

**Deliverables**

- Voice session state and cancellation.
- A V4-owned transcription/provider boundary that uses only approved
  device-facing `pi5mic` APIs.
- Explicit camera/audio consent and retention controls.
- Backpressure so media processing cannot starve robot control.
- Text fallback when media services fail.
- Proof that no `pi5mic.integration.openclaw_*`,
  `pi5mic.transport.openclaw_*`, or other OpenClaw path is imported.

**Pi validation**

- Recorded fixtures only.
- Privacy, cancellation, buffering, and fallback tests.
- No implicit local camera or microphone access in the default suite.
- Wake/listen/stop behavior.
- Microphone contention and release.
- Camera access indication and cleanup.
- Text fallback after media failure.

**Exit criteria**

- Voice is an input/output mode, not a second control path.

### Phase 9: Deployment hardening and release

**Objective**

Make NinjaRobotPi5V4 a self-contained supported runtime.

**Deliverables**

- Final parity report.
- Installation and rollback guide.
- Raspberry Pi service files and permissions.
- Startup, restart, update, backup, and recovery documentation.
- Optional systemd unit that is installed disabled and enabled only by an
  explicit operator command.
- Release checklist and versioning policy.

**Pi validation**

- Clean install in a fresh environment.
- Documentation command verification.
- Full quality gates.
- Full installation from documented steps.
- Reboot/startup and safe shutdown.
- Local Ollama and any intentionally configured cloud provider.
- All devices independently, then integrated.
- Cancellation, network loss, provider failure, database restart, and rollback.

**Exit criteria**

- Complete Pi pass/fail report.
- No unresolved safety-critical issue.
- User approves NinjaRobotPi5V4 for release.

## 23. Documentation deliverables

Documentation is part of every phase, not a final cleanup task.

Required living documents:

- V4 architecture overview
- capability and tool authoring guide
- provider adapter guide
- memory and privacy guide
- configuration reference
- developer setup for macOS
- installation and service guide for Raspberry Pi 5
- per-adapter and full-hardware Pi validation checklists
- installation and rollback guide
- ADRs for significant decisions

`README.md`, `DevelopmentGuide.md`, and `InstallationGuide.md` must be updated
when the corresponding behavior actually changes. They should not describe
unimplemented V4 features as already available.

Documentation inside `pi5buzzer`, `pi5servo`, `pi5disp`, `pi5camera`, `pi5mic`,
and `pi5vl53l0x` may be corrected when a validated driver repair changes setup,
behavior, or troubleshooting guidance. Historical NinjaClawBot and OpenClaw
references remain unsupported by V4 and must not be introduced into new runtime
paths.

## 24. Definition of done

NinjaRobotPi5V4 is complete when:

- every copied `pi5*` file either matches its original Phase 0 import hash or
  an explicitly authorized and validated repair hash
- all robot access flows through `ninjarobot_pi5_ide`
- the agent has no direct hardware imports
- Ollama, OpenAI, Gemini, and Anthropic adapters pass the same provider contract
- model/tool loops are bounded and cancellable
- non-idempotent actions cannot be duplicated by automatic retry
- users can inspect, export, and delete persistent memories
- project-owned memory survives a provider change
- the current supported robot behavior has a documented parity result
- macOS quality gates pass
- Raspberry Pi 5 validation passes with a signed-off report
- installation, development, migration, privacy, and recovery documentation is
  accurate
- the default two-servo power path is recorded, with the missing physical
  cutoff documented as an accepted residual risk
- no V4 runtime path imports OpenClaw
- the user approves the release

## 25. Important non-goals for the first V4 release

The first release will not attempt:

- unrestricted autonomous operation
- a multi-agent hierarchy
- a remote public robot-control service
- a third-party app marketplace
- a mandatory vector database
- silent learning from every conversation
- direct model access to hardware drivers
- automatic retries when physical action outcome is uncertain
- full robot simulation before deterministic fakes provide sufficient coverage
- modifying any copied `pi5*` library or its documentation
- a separate IDE process
- a public-internet robot-control service or router port forwarding
- browser pairing authentication in Phase 5
- spoken robot responses in Phase 5
- enabling Tavily extract, crawl, or map tools by default
- executable-code agent skills
- automatic startup immediately after installation
- LAN-hosted Ollama as a first-release requirement

These can be reconsidered through later ADRs after the core system is reliable.

## 26. Approval checkpoints

Approval is requested at these points:

1. Approve this architecture and phase ordering.
2. Approve Phase 0 before any cleanup, root scaffolding, or V4 code change.
3. Review results and approve the next phase after each phase exit report.
4. Approve any proposed copied-driver change separately; the default answer is
   no change.
5. Approve Pi hardware execution when the deferred checklists are ready.
6. Review the Phase 4 servo power record and residual-risk statement before
   powered servo tests.
7. Approve optional systemd auto-start separately after manual startup is
   stable.

Until checkpoint 1 is approved, this plan is the only V4 project change.
