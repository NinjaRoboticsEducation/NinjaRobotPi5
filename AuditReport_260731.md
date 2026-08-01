# NinjaRobotPi5 Alpha Release — Audit Report
**Date:** 2026-07-31  
**Auditor:** Antigravity (Automated Code Audit)  
**Scope:** Full project audit — `NinjaRobotPi5/` root, including `ninjarobot_pi5_agent`, `ninjarobot_pi5_ide`, six `pi5*` driver libraries, documentation, scripts, and tests.  
**Baseline:** V4 implementation as of commit series ending 2026-07-30, Phase 5 (cloud provider) complete.

---

## 1. Executive Summary

NinjaRobotPi5 is a well-engineered, intentionally layered robotics platform. The security posture is **strong by design**: hardware ownership uses OS file locks, physical motion gates are session-scoped and require explicit confirmation, privacy-sensitive operations require separate consent, secrets are stored owner-only at `0600`, and the AI model is architecturally incapable of bypassing any of these controls. The policy engine, PromptComposer, and tool registry are cleanly separated from model output.

That said, the audit identified **one high-risk item** and a set of **medium and low-risk findings** that should be addressed before a broad public release. The high-risk item is a documentation and setup experience issue, not a code defect. Most findings are hardening opportunities rather than functional defects.

---

## 2. Risk Assessment

| ID | Category | Severity | Title |
|---|---|---|---|
| R-01 | Installation UX | **HIGH** | Non-technical users are likely to fail at Step 4 (config sync) without automation |
| R-02 | Security | **MEDIUM** | `secrets.env` parser: values beginning with `=` are silently dropped on re-read |
| R-03 | Security | **MEDIUM** | `example.toml` ships with `enabled = true` for all four cloud providers — credential leakage risk |
| R-04 | Reliability | **MEDIUM** | Watchdog daemon thread may not flush safety state on OS SIGTERM |
| R-05 | Reliability | **MEDIUM** | Camera bridge subprocess timeout (18 s) leaves only 2 s margin vs outer timeout (20 s) |
| R-06 | Security | **LOW** | Skill prompt-injection regex set is English-only; Japanese bypass not detected |
| R-07 | Code Quality | **LOW** | `BehaviorConfig` carries two dead Phase 4 fields with no deprecation warning |
| R-08 | Reliability | **LOW** | `BaseException` catch in `_write` lacks explanatory comment; risk of future misrefactoring |
| R-09 | Documentation | **LOW** | Installation Guide Section 2 mixes non-technical and advanced-developer instructions |
| R-10 | Documentation | **LOW** | No documented rollback path for a failed mid-update scenario |

---

## 3. Detailed Findings

### R-01 · HIGH · Installation: Step 4 Config Sync Is a Non-Technical User Blocker

**Description:**  
The installation process requires users to:
1. Configure six standalone `pi5*` tools in separate wizard sessions,
2. Locate each canonical `~/.config/pi5*/` file manually,
3. Run `config discover`, inspect a diff preview, and run `config import --apply --overwrite` with the exact `$NINJAROBOT_CONFIG` environment variable set,
4. Then validate and restart.

This is a four-command manual configuration-merge workflow with no undo. A mistake (for example, running `import` without `--destination $NINJAROBOT_CONFIG` while the variable is unset) silently uses a different path. No interactive wizard or setup script automates this path.

**Impact:**  
Almost all non-technical users will either fail silently (IDE ignores calibrations) or apply an import into the wrong file.

**Recommendation:**
- Ship a `setup-wizard.sh` or `ninjarobot-ide-tool setup` interactive command that walks the user through all six device config steps in order, then calls `config import --apply --overwrite` automatically.
- Add a pre-flight check in `ninjarobot-ide-tool` that warns on startup if canonical `pi5*` configs have not been imported since last change.
- At minimum, add a bold-bordered callout box in the Installation Guide before Step 4 warning: "If you skip this step, hardware calibration will not be applied."

---

### R-02 · MEDIUM · Security: `SecretStore._read_file` Silently Drops Values Starting With `=`

**Description:**  
`secrets.py` L89–91:

```python
name, separator, value = line.partition("=")
if separator and _NAME_PATTERN.fullmatch(name):
    secrets[name] = value
```

`str.partition` correctly handles values containing `=` (e.g., base64 tokens like `sk-abc123==`). However, `set()` at L27 rejects `\n`, `\r`, `\x00` but **not** values beginning with `=`. A value of `=anything` written to the file would parse `name=""`, fail `_NAME_PATTERN`, and the secret would be silently dropped on re-read.

**Impact:**  
A secret value beginning with `=` is silently lost on re-read, causing `require()` to raise `KeyError` with no clear error message pointing to the format issue.

**Recommendation:**  
Add an explicit guard in `set()`:

```python
if not value or value.startswith("=") or "\n" in value or "\r" in value or "\x00" in value:
    raise ValueError("secret values must be non-empty single-line text and must not begin with '='")
```

---

### R-03 · MEDIUM · Security: Example Config Ships With All Cloud Providers Enabled

**Description:**  
`config/ninjarobot_pi5.toml.example` ships with `openai`, `gemini`, and `anthropic` all set to `enabled = true`. A user who copies this file without reviewing will expose unused API key environment variables to the agent's model-selection and fallback logic — even if those keys are not yet configured.

`ProviderConfig` validates that `api_key_env` is set, but does not check that the named environment variable actually resolves to a value. An enabled-but-keyless cloud provider can be selected at runtime, causing a confusing error.

**Impact:**  
Credential-related errors surface at runtime rather than config-load time. Users may see Anthropic or OpenAI errors when only Ollama is intended.

**Recommendation:**  
Change the example file to ship all cloud providers as `enabled = false`:

```toml
[providers.openai]
enabled = false  # Set to true and add api_key_env only when using OpenAI
```

Also add a startup health check warning when a provider is `enabled = true` but its resolved secret is `None`.

---

### R-04 · MEDIUM · Reliability: Motion Watchdog Thread May Not Flush Safety State on OS Shutdown

**Description:**  
`safety.py` L214: `_WatchdogThread` is started as `daemon=True`. Daemon threads are killed by the Python runtime without running `close()` if the main thread exits due to SIGTERM (e.g., `systemctl stop`).

If SIGTERM arrives slightly before a watchdog timeout fires, the daemon thread is killed with servos still energized and no safety latch written. Even if the latch is written, `SafetyStateStore._write` uses `os.fsync` for durability, but a daemon thread killed mid-write could leave a corrupt state file — which the store correctly treats as a full latch, but `fault_detail` would be empty.

**Impact:**  
Under a rapid OS shutdown during active robot motion, the watchdog cannot guarantee a servo-stop PWM signal is sent.

**Recommendation:**  
Register the robot's stop sequence as an `atexit` handler and route SIGTERM explicitly to the asyncio event loop graceful shutdown sequence before daemon threads are killed. Confirm that the existing `RobotAssembly` close path is invoked on SIGTERM.

---

### R-05 · MEDIUM · Reliability: Camera Bridge Timeout Window Is Too Narrow

**Description:**  
`camera.py`:

```python
CAMERA_CAPTURE_TIMEOUT_SECONDS = 20.0          # outer adapter timeout
SYSTEM_CAMERA_CAPTURE_TIMEOUT_SECONDS = 18.0   # inner subprocess timeout
```

The outer timeout exceeds the inner by only 2 seconds. After the subprocess is killed on the 18-second inner timeout, the adapter must still: kill the child process, drain stdout, unlink the staging file, and raise an exception — all within 2 seconds on a potentially loaded Raspberry Pi 5.

**Impact:**  
Under load, camera capture timeouts can produce a confusing secondary timeout error or leave the staging file temporarily unlinked. The privacy model is correct (the grant remains claimable), but the error report to the agent may be misleading.

**Recommendation:**  
Increase the margin to at least 5 seconds, or derive the outer from the inner:

```python
SYSTEM_CAMERA_CAPTURE_TIMEOUT_SECONDS = 18.0
CAMERA_CAPTURE_TIMEOUT_SECONDS = SYSTEM_CAMERA_CAPTURE_TIMEOUT_SECONDS + 5.0  # = 23.0
```

---

### R-06 · LOW · Security: Skill Prompt Injection Patterns Are English-Only

**Description:**  
`skills.py` L34–39:

```python
_FORBIDDEN_INSTRUCTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|system|safety)\b", re.IGNORECASE),
    re.compile(r"\b(?:bypass|disable|override)\s+(?:the\s+)?safety\b", re.IGNORECASE),
    re.compile(r"\breveal\s+(?:the\s+)?system\s+prompt\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
)
```

The system supports Japanese (camera requests, microphone transcription). A skill `instructions.md` containing Japanese equivalents such as `以前の指示を無視してください` would not be caught.

**Impact:**  
Bounded by the skill-confinement architecture (skills cannot grant new tool permissions, cannot change safety policy, `PromptComposer` explicitly labels skill content as subordinate). Risk is low but non-zero.

**Recommendation:**  
Add representative Japanese patterns, or document that operator review of `instructions.md` is required before installation. For AI-proposed skills, require a human review step before the `--ai-proposed --confirm` flag is used.

---

### R-07 · LOW · Code Quality: Dead Configuration Fields in `BehaviorConfig`

**Description:**  
`config.py` L159–162:

```python
# Accepted only so Phase 4 configuration files continue to load. Movement no
# longer waits for clear readings before energizing the servos.
clear_readings_before_motion: Annotated[int, Field(ge=1, le=10)] = 3
clear_reading_timeout_seconds: Annotated[float, Field(ge=1.0, le=30.0)] = 5.0
```

These fields are silently accepted but have no effect. Users who include them believe they control safety behavior.

**Recommendation:**  
Add a `model_validator` that emits a logged warning when these fields are present with non-default values. Mark them as `# DEPRECATED — has no effect` in `ninjarobot_pi5.toml.example`.

---

### R-08 · LOW · Reliability: `BaseException` Catch Lacks Explanatory Comment

**Description:**  
`safety.py` L176:

```python
except BaseException:
    temporary.unlink(missing_ok=True)
    raise
```

This pattern is correct (`raise` preserves `SystemExit` and `KeyboardInterrupt`), but a future maintainer may incorrectly "fix" it to `except Exception`.

**Recommendation:**  
Add: `# BaseException intentional: ensures temp file cleanup even on KeyboardInterrupt or SystemExit before re-raising.`

---

### R-09 · LOW · Documentation: Installation Guide Mixes Audiences

**Description:**  
Installation Guide Section 2 (NinjaRobotAgent) contains both non-technical user prose ("Tap to Start Controller", "Arm AI Motion button") and advanced developer CLI references (`--session dynamic-test`, `--confirmed`, `--skill robot-behavior-generation`). A non-technical user is likely to copy-paste advanced CLI flags into the wrong context.

**Recommendation:**  
Split Section 2 into:
- **"Quick Start (Standard Users)"** — web interface only
- **"Advanced CLI Usage"** — clearly marked optional, for power users

---

### R-10 · LOW · Documentation: No Rollback Path for Failed Updates

**Description:**  
The update procedure (`InstallationGuide.md` L2386–2398) uses `git pull --ff-only` but gives no guidance for a failed `uv sync` or test failure mid-update, leaving the system in a partially updated state.

**Recommendation:**  
Add a recovery block:

```markdown
If any step after `git pull` fails, restore the previous state:

    git reflog      # identify the previous commit hash
    git checkout <previous-commit>
    uv sync --frozen --extra hardware
```

Or recommend backing up the project directory before running `git pull`.

---

## 4. Positive Findings (Strengths to Preserve)

| Area | Observation |
|---|---|
| **Hardware ownership lock** | OS-level non-blocking file lock prevents concurrent driver access without application coordination |
| **Policy engine separation** | `PolicyEngine.evaluate()` reads only from the trusted `ToolDefinition.risk` catalog — never from model-provided input |
| **Atomic secret writes** | `SecretStore.set()` and `save_google_credentials()` use `tempfile` + atomic rename with `fchmod(0o600)` before rename |
| **Fail-closed safety state** | `SafetyStateStore.read()` returns a fully latched snapshot on any parse error |
| **Skill confinement** | Skills are schema-validated, size-bounded, path-confined, and can only **restrict** — never **expand** — the active tool policy |
| **Camera privacy pipeline** | JPEG never enters the conversation transcript or model context; `retain_media_by_default = false` is hardcoded as `Literal[False]` |
| **MCP server HTTPS-only** | `MCPServerConfig` enforces `url.startswith("https://")` at config-load time |
| **Cloud API host pinning** | Provider validators accept only official API hostnames, blocking credential forwarding attacks |
| **Immutable driver verification** | SHA-256 baseline + authorization manifest + CI-run test creates a tamper-evident supply-chain check for all six hardware drivers |
| **Session-scoped motion arming** | `MotionArmManager` is scoped by `(session_id, lease_id)` — arming the CLI does not arm a browser controller |

---

## 5. Roadmap Recommendations

### Before Public Alpha Release (Required)

| Priority | Action | Addresses |
|---|---|---|
| 1 | Add a `setup-wizard.sh` or guided `ninjarobot-ide-tool setup` command | R-01 |
| 2 | Change `ninjarobot_pi5.toml.example` to ship all cloud providers as `enabled = false` | R-03 |
| 3 | Increase camera bridge timeout margin to 5 s | R-05 |
| 4 | Split Installation Guide Section 2 into Quick Start vs Advanced CLI | R-09 |

### Before Beta / Public Stable Release (Recommended)

| Priority | Action | Addresses |
|---|---|---|
| 5 | Add `secrets.py` guard against values beginning with `=` | R-02 |
| 6 | Register SIGTERM handler in agent service for graceful servo shutdown | R-04 |
| 7 | Deprecate dead `BehaviorConfig` fields with logged warning | R-07 |
| 8 | Add rollback documentation to update procedure | R-10 |
| 9 | Add runtime warning for `enabled = true` provider with unresolved secret | R-03 (extended) |

### Future Hardening (Post-Release Backlog)

| Priority | Action | Addresses |
|---|---|---|
| 10 | Add Japanese prompt injection patterns to skill validator | R-06 |
| 11 | Add `# BaseException intentional` comment to safety state writer | R-08 |

---

## 6. Installation Experience Review

### Current State

The installation guide is comprehensive and technically correct. The phased validation approach (safe-first, non-moving hardware, then actuators with raised wheels) is an excellent non-technical safety pattern. The troubleshooting section covers ~30 distinct failure modes with clear commands.

### Key Gaps for Non-Technical Users

1. **Config sync automation** — see R-01.
2. **whisper.cpp build requirement** — the guide links to `whisper.cpp` documentation without providing build commands. A non-technical user encounters a C++ CMake build with no guidance on dependencies or verification.
3. **TLS certificate trust step** — Safari full-trust toggle is buried in a paragraph; should be a numbered step.
4. **Ollama model download** — `ollama pull qwen3:4b` does not mention the ~2.3 GB download size, expected duration, or the need for active cooling during inference.

### Recommended Additions

```markdown
> [!TIP]
> The `qwen3:4b` model download is approximately 2.3 GB. Ensure the Pi has
> adequate cooling — an official Raspberry Pi Active Cooler is strongly recommended.

> [!IMPORTANT]
> USB microphone transcription requires a compiled `whisper-cli` binary.
> Run the following to build it:
>
>     sudo apt install -y build-essential cmake git
>     git clone https://github.com/ggml-org/whisper.cpp ~/whisper.cpp
>     cmake -B ~/whisper.cpp/build ~/whisper.cpp
>     cmake --build ~/whisper.cpp/build --config Release -j$(nproc)
>     ~/whisper.cpp/build/bin/whisper-cli --download-model base
```

---

## 7. Documentation Review

### README.md

**Verdict: Good baseline, needs alpha-readiness caveats.**

- Phase completion table is accurate.
- CLI quick-start is correct and well-formed.
- **Missing:** A "System Requirements" section (Pi model, OS version, minimum RAM, storage).
- **Missing:** A prominent "Alpha Release" banner at the top.

### InstallationGuide.md

**Verdict: Excellent technical depth; non-technical UX needs improvement (see R-01, R-09).**

- Troubleshooting section is thorough and maps ~30 symptoms to causes.
- Validation order is exemplary.
- MCP and Skill appendix correctly warns about allowlist review.
- **Missing:** whisper.cpp build commands.
- **Missing:** Expected download sizes and timings for Ollama models.

### DevelopmentGuide.md

**Verdict: Comprehensive and well-maintained. Appropriate for developer audience.**

- Driver-containment boundary and import prohibition are clearly stated and tested.
- Quality gate commands are accurate and complete.
- Authentication boundary section is an excellent security reference.
- **Minor:** Should note that Phase 5 is complete and Phase 6 (documentation refactor, public release prep) is the current target.

---

## 8. Audit Methodology

This audit was performed by:

1. **Structural review** — full directory map, package layout, `pyproject.toml` and lockfile structure
2. **Governance review** — `AGENTS.md`, `SKILL.md`, implementation plan constraints
3. **Documentation review** — complete read of `README.md`, `InstallationGuide.md`, `DevelopmentGuide.md`
4. **Source code review** — deep read of all security-sensitive modules: `secrets.py`, `policy.py`, `prompts.py`, `google_oauth.py`, `provider_auth.py`, `mcp_config.py`, `skills.py`, `safety.py`, `config.py`, `camera.py`, `web_app.py`
5. **Test review** — `test_repository_governance.py`, driver verification script
6. **Configuration review** — `ninjarobot_pi5.toml.example`, `.gitignore`
7. **Validation artifact review** — 22-file `docs/validation/` directory listing

No dynamic execution, hardware testing, or fuzzing was performed. This is a static code and documentation audit only.

---

*End of Report — NinjaRobotPi5 AuditReport_260731.md*

---

## 9. Documentation Standards: Recommended Format, Structure, Tone, and Style

This section defines the target standard for each of the three project documents. Each sub-section states the document's purpose, its intended audience, the required content structure, tone and style rules, and a concise worked example that can be used as a starting template.

---

### 9.1 README.md

#### Purpose

The README is the front door of the project. It is the first document every visitor reads, whether they are a curious hobbyist, a potential contributor, or a new maintainer. Its job is to **answer five questions in under two minutes**: What is this? Who is it for? What does it do? Is it safe for me to use? How do I get started?

#### Intended Audience

- Non-technical makers and hobbyists exploring AI robotics
- Developers evaluating the project before cloning
- Contributors scanning the project for the first time

#### Required Content Structure

Use this section order exactly. Each heading maps to one clear question.

```
# NinjaRobotPi5

[One-sentence value statement]
[One-sentence hardware / platform statement]

## What It Does
[3–5 bullet points: user-facing capabilities, not implementation details]

## System Requirements
[Table: Hardware / Software / Version]

## Quick Start
[4–6 numbered steps from zero to a running simulation]

## Key Features
[Grouped bullets: AI, Hardware, Safety, Web Interface]

## Architecture Overview
[One diagram or 3-sentence summary of the 3-layer design]

## Documentation
[Link table to README, InstallationGuide, DevelopmentGuide, validation docs]

## Safety
[2–3 sentences: what safety measures protect the user and hardware]

## License
[License name and link]
```

#### Tone and Style Rules

| Rule | Correct | Incorrect |
|---|---|---|
| Address the reader directly | "You can ask the robot to…" | "The agent provides the capability to…" |
| Plain English first, jargon only with a definition | "SPI (the display's data bus)" | "SPI frequency_hz is 32 MHz" |
| Active voice | "The safety system stops the motors" | "Motors are stopped by the safety system" |
| Present tense for current state | "Phase 5 is complete" | "Phase 5 has been completed" |
| No internal development history in user-facing paragraphs | ✓ Omit "Phase 0 established…" from README body | ✗ Do not list every phase in the README |
| Link, don't embed | "See [InstallationGuide.md](InstallationGuide.md) for full steps" | Copy-pasting installation commands into README |
| Explicit alpha warning at top | `> [!WARNING] Alpha release — expect rough edges` | No warning, or warning buried at bottom |

#### Worked Example (README.md fragment)

```markdown
# NinjaRobotPi5

An AI-powered Raspberry Pi 5 robot that you control by talking — or by tapping
a browser controller from your phone. NinjaRobotPi5 runs a local AI model
entirely on the Pi, so your conversations never leave your home network.

> [!WARNING]
> **Alpha release.** Core features are stable and tested, but some setup steps
> require command-line experience. Read the [Installation Guide](InstallationGuide.md)
> before powering the robot.

## What It Does

- **Talk to your robot** — ask it to move, make sounds, show expressions, or
  take a photo using plain English or Japanese.
- **Control from your phone** — a secure HTTPS web interface gives you a D-pad,
  live camera preview, and AI chat from any browser on your local network.
- **Stays private** — the AI model runs locally on the Pi; no cloud account is
  required for basic use.
- **Safe by design** — the robot stops itself when it detects an obstacle,
  loses its network connection, or if the power supply drops.
- **Expandable** — connect external AI search tools (Tavily) or teach the robot
  new workflows using the validated skill system.

## System Requirements

| Item | Requirement |
|---|---|
| Hardware | Raspberry Pi 5 (4 GB RAM recommended) |
| Operating System | Raspberry Pi OS Bookworm (64-bit) |
| Storage | 16 GB microSD minimum, 32 GB recommended |
| Cooling | Official Raspberry Pi Active Cooler (required for AI inference) |
| Python | 3.11 (managed automatically by `uv`) |

## Quick Start

1. Follow the [Installation Guide](InstallationGuide.md) to wire and configure
   your robot.
2. Clone the repository and install dependencies:
   ```bash
   git clone https://github.com/<owner>/NinjaRobotPi5.git ~/NinjaRobotPi5
   cd ~/NinjaRobotPi5
   uv sync --frozen
   ```
3. Run a software-only simulation (no hardware required):
   ```bash
   uv run --frozen ninjarobot-agent service start
   uv run --frozen ninjarobot-agent chat "Hello, what can you do?"
   ```
4. Open the [full Installation Guide](InstallationGuide.md) to connect and
   calibrate your hardware.

## Documentation

| Document | Purpose |
|---|---|
| [InstallationGuide.md](InstallationGuide.md) | Step-by-step hardware setup and calibration |
| [DevelopmentGuide.md](DevelopmentGuide.md) | Architecture, driver boundaries, and contribution workflow |
| [AuditReport_260731.md](AuditReport_260731.md) | Security and reliability audit findings |
```

---

### 9.2 InstallationGuide.md

#### Purpose

The Installation Guide is the **single authoritative reference** a user follows from an unboxed Raspberry Pi to a fully calibrated, running robot. It must be complete enough that a user never needs to search outside this document for a standard setup task.

#### Intended Audience

**Primary:** Non-technical makers with basic Raspberry Pi experience (can SSH in, can run a command). They may not know Python, Git, or networking.

**Secondary:** Technical users who want the exact command sequence and understand why each step is required.

The document must serve both without alienating either. Use **callout boxes** to mark optional advanced steps.

#### Required Content Structure

```
# NinjaRobotPi5 Installation Guide

## Before You Begin
  ### Hardware You Need [table]
  ### Software You Need [list]
  ### Safety Rules [numbered, before any wiring]

## 1. Prepare the Raspberry Pi
  ### 1.1 Install Raspberry Pi OS
  ### 1.2 Enable Required Interfaces (SPI, I2C, Camera, GPIO)
  ### 1.3 Install System Packages

## 2. Install NinjaRobotPi5
  ### 2.1 Clone the Repository
  ### 2.2 Install Python Dependencies
  ### 2.3 Verify the Software Installation [simulation test]

## 3. Configure Each Hardware Module
  ### 3.1 Buzzer [setup wizard → test command]
  ### 3.2 Display [setup wizard → test command]
  ### 3.3 Distance Sensor [setup wizard → test command]
  ### 3.4 Servos / Wheel Motors [setup wizard → calibration → test command]
  ### 3.5 Camera [bootstrap script → test command]
  ### 3.6 Microphone and Speech [build whisper.cpp → test command]
  ### 3.7 Sync All Settings into the Robot Configuration [config import]

## 4. Run the Robot
  ### 4.1 Start the Agent Service
  ### 4.2 Open the Web Controller
  ### 4.3 Try Your First AI Chat
  ### 4.4 Enable AI Motion (Optional)

## 5. Troubleshooting
  [Symptom → cause → fix format, one subsection per symptom]

## 6. Updating and Uninstalling
  ### Updating [with rollback steps]
  ### Uninstalling

## Appendix: Advanced Configuration
  [MCP, Skills, Cloud Providers — clearly marked as optional]
```

#### Tone and Style Rules

| Rule | Correct | Incorrect |
|---|---|---|
| One task per step | "Run this command. Expected output: …" | Multiple unrelated steps combined |
| State the expected outcome | "Expected result: the display shows 'Hello World'" | No outcome stated; user guesses if it worked |
| Warn before danger, not after | `> [!CAUTION] Raise wheels before this step.` placed above the command | Warning placed below the command that moves the robot |
| Define every abbreviation on first use | "SPI (Serial Peripheral Interface, the display's data bus)" | "SPI frequency_hz" with no explanation |
| Separate safe steps from hardware-energizing steps | Visual section break and a CAUTION box | Mixed sequence of safe and unsafe commands |
| Keep troubleshooting in a dedicated section | Link from the main step: "If this fails, see [Troubleshooting: Display stays blank](#display-stays-blank)" | Troubleshooting embedded mid-step |
| Mark advanced content clearly | `> [!NOTE] Advanced users only.` or a collapsible `<details>` block | Advanced CLI commands inline with beginner steps |
| Include download size and time estimates | "The `qwen3:4b` model is approximately 2.3 GB (~10–20 min on home broadband)" | `ollama pull qwen3:4b` with no context |

#### Worked Example (InstallationGuide.md fragment — Section 3.7)

```markdown
## 3.7 Sync All Settings into the Robot Configuration

After configuring each hardware module, you must merge their settings into the
single NinjaRobotPi5 configuration file that the agent uses. This step is
required once after initial setup and again whenever you change a module's
wiring or recalibrate a servo.

> [!IMPORTANT]
> Complete Sections 3.1–3.6 before this step. If you skip configuration for a
> module you have not yet installed, that is fine — re-run this step after you
> set it up later.

**Step 1 — Set your config path (run this in every new terminal session):**

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
```

**Step 2 — Preview what will change:**

```bash
cd ~/NinjaRobotPi5
uv run --frozen ninjarobot-ide-tool config discover
uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" \
  config import \
  --destination "$NINJAROBOT_CONFIG"
```

Expected result: a preview of changed values is printed. No file is modified yet.

**Step 3 — Review the preview carefully**, then apply it:

```bash
uv run --frozen ninjarobot-ide-tool \
  --config "$NINJAROBOT_CONFIG" \
  config import \
  --destination "$NINJAROBOT_CONFIG" \
  --apply --overwrite

chmod 600 "$NINJAROBOT_CONFIG"
```

Expected result: the command prints `Applied` and exits with code 0.

**Step 4 — Validate the merged configuration:**

```bash
uv run --frozen ninjarobot_pi5_cli config validate \
  --config "$NINJAROBOT_CONFIG"
```

Expected result: `Configuration is valid.`

If validation fails, re-open the standalone tool for the reported module,
correct its settings, save, and repeat from Step 2.

> [!TIP]
> You do not need to repeat Steps 1–4 after calibrating a servo. Servo
> calibration is read directly from `~/.config/pi5servo/servo.json` each time
> the IDE starts.
```

---

### 9.3 DevelopmentGuide.md

#### Purpose

The Development Guide is the **technical reference** for contributors, maintainers, and any agent (human or AI) making changes to the codebase. It establishes the **why** behind architectural decisions, not just the **how**.

#### Intended Audience

- Software developers contributing to NinjaRobotPi5
- AI coding agents operating within the governance rules
- The project maintainer reviewing or approving changes

Non-technical users should not need to read this document. It may assume familiarity with Python, Git, `uv`, and basic software architecture.

#### Required Content Structure

```
# NinjaRobotPi5 Development Guide

## Architecture Overview
  ### Three-Layer Boundary Model [diagram strongly recommended]
  ### Why This Boundary Exists [rationale, not just rules]
  ### What Each Layer Owns and Does Not Own

## Repository Layout
  [Annotated directory tree]

## Development Environment Setup
  ### Prerequisites
  ### First-Time Setup
  ### Running the Test Suite
  ### Quality Gate Commands [exact commands in copy-pasteable blocks]

## Driver Library Policy
  ### What "Managed Driver" Means
  ### Prohibited Operations [explicit list]
  ### How to Propose a Driver Change

## Configuration System
  ### Schema Overview
  ### How Config Flows Between Layers
  ### Adding a New Configuration Field

## Safety and Security Architecture
  ### Hardware Ownership Lock
  ### Policy Engine and Tool Trust
  ### Motion Arming and Session Scope
  ### Secret Storage
  ### Prompt Composition Order

## Agent and IDE Extension Points
  ### Adding a New Capability Adapter
  ### Adding a New MCP Server
  ### Adding a New Agent Skill
  ### Adding a New Cloud Provider Adapter

## Testing and Validation
  ### Test Categories [unit, integration, hardware]
  ### Validation Flow [phases and checklists]
  ### Raspberry Pi Acceptance Criteria

## Troubleshooting for Developers
  [Developer-specific failures: import conflicts, lockfile issues, driver hash mismatches]

## Changelog and Phase Status
  [Current phase, completed phases, next planned phase]
```

#### Tone and Style Rules

| Rule | Correct | Incorrect |
|---|---|---|
| State the reason before the rule | "Because the Pi can only have one hardware owner at a time, the IDE uses an OS file lock. Never bypass this lock." | "Do not bypass the hardware lock." |
| Use tables for rules that have multiple related attributes | Policy matrix table with risk level, confirmation, motion arming | Prose list of policy conditions |
| Separate what IS from what MUST NOT be | "The agent owns: user interaction, planning, session state. It must never: import driver objects, open GPIO, or bypass policy." | Mixing permission and prohibition in a single paragraph |
| Code examples must be copy-pasteable and verified | Show exact `uv run --frozen` commands with expected output | Pseudo-code or approximate commands |
| Cross-reference to authoritative source | "See `policy.py` `PolicyEngine.evaluate()` for the implementation." | "The policy engine handles this." |
| Version stability markers | Note when a feature was added (phase or date) so maintainers can track drift | No version context |
| Avoid embedding validation checklists inline | "See `docs/validation/phase-5-agent-refinement-validation-2026-07-29.md` for the full checklist" | Reproducing checklist content inside the guide |

#### Worked Example (DevelopmentGuide.md fragment — Driver Policy)

```markdown
## Driver Library Policy

### What "Managed Driver" Means

The six `pi5*` directories (`pi5buzzer`, `pi5camera`, `pi5disp`, `pi5mic`,
`pi5servo`, `pi5vl53l0x`) are **managed copies** of historical standalone
libraries. They exist in this repository so that V4 can:

- Lock their exact content with SHA-256 checksums
- Run their own tests in isolation
- Ship them together without requiring an external Git dependency

They are **not** V4 sub-packages. They remain independent projects with their
own `pyproject.toml`, lockfiles, and test suites.

### What You Must Not Do

| Prohibited action | Why |
|---|---|
| `import pi5servo` inside `ninjarobot_pi5_ide` or `ninjarobot_pi5_agent` | Breaks the containment boundary; IDE talks to drivers through adapter contracts only |
| Edit a `pi5*` source file without recording an authorization | The SHA-256 baseline check will fail CI and the governance test suite |
| Add a `pi5*` directory as a `[tool.uv.sources]` workspace member | Drivers are editable path dependencies managed by the root `pyproject.toml`, not workspace members |
| Run `uv sync` inside a `pi5*` folder during normal development | Use the root environment; package-local environments are for standalone driver validation only |

### How to Propose a Driver Change

1. File an issue describing the defect and the proposed fix.
2. Get maintainer approval **before writing code**.
3. Apply the minimal fix inside the affected `pi5*` directory.
4. Run the driver's own isolated test suite:
   ```bash
   (cd pi5servo && uv run --isolated --frozen --extra dev --python 3.11 \
     python -B -m pytest -q -p no:cacheprovider)
   ```
5. Update `docs/validation/authorized_driver_changes.json` with the new hash
   and the approval rationale.
6. Run the governance test to confirm the baseline accepts the change:
   ```bash
   uv run --frozen python scripts/verify_immutable_drivers.py
   uv run --frozen pytest tests/test_repository_governance.py -q
   ```
7. Submit the PR with the driver fix, the updated authorization manifest,
   and the test run output.

> [!CAUTION]
> Never use `--record-authorized` to silence a hash mismatch caused by an
> accidental edit. Only use it after step 6 passes with the intended change.
```

---

### 9.4 Cross-Document Consistency Rules

These rules apply to all three documents and must be enforced uniformly:

| Consistency Rule | Detail |
|---|---|
| **Terminology** | Use exactly: `ninjarobot-agent` (CLI command), `ninjarobot_pi5_agent` (package), `ninjarobot-ide-tool` (IDE CLI), `NinjaRobotPi5` (project name). Do not mix hyphens and underscores in the wrong context. |
| **Command format** | All shell commands use `uv run --frozen` as the prefix. Never show bare `python` calls for installed CLI tools. |
| **File paths** | Use `$HOME/NinjaRobotPi5` for the cloned directory and `~/.config/ninjarobot_pi5/` for user config — never `/home/pi/` (fragile) or `.` without context. |
| **Alert type discipline** | `[!NOTE]` = background info. `[!TIP]` = optimization or shortcut. `[!IMPORTANT]` = required step often missed. `[!WARNING]` = may break something. `[!CAUTION]` = may physically harm hardware or person. Do not use CAUTION for software-only warnings. |
| **Expected result statements** | Every command in a user-facing guide must be followed by an `Expected result:` line that states exactly what success looks like. |
| **Link policy** | README links to InstallationGuide and DevelopmentGuide. InstallationGuide links to DevelopmentGuide for architectural background only. DevelopmentGuide links to validation docs. No circular links. |
| **Alpha/beta status banner** | README must show a `[!WARNING]` alpha banner until the project reaches a stable release. InstallationGuide must echo the same status in its "Before You Begin" section. |
| **Abbreviation discipline** | Define every abbreviation once, at first use in each document. Do not assume the reader of InstallationGuide has read README. |

---

*End of Section 9 — Documentation Standards*

---

## 10. Maintainer Verification Addendum — 2026-08-01

This addendum preserves the original audit as historical evidence while
correcting claims against executable source and dynamic tests. The original
audit was static only; this verification used targeted source review plus the
complete project quality gate. It does not mean every valid recommendation was
implemented by the 2026-08-01 authentication/MCP refinement.

| Finding | Verified assessment | Evidence / disposition |
|---|---|---|
| R-01 | Partially supported UX concern | Config discovery/import is preview-first and documented, and servo calibration is read directly at IDE startup. A unified setup wizard could still improve first-time installation but is separate product work. |
| R-02 | Incorrect | A line is written as `NAME=<value>`. If the value begins with `=`, `partition("=")` returns the valid name and a value beginning with `=`. The audited report incorrectly treated the value as the variable name. Round-trip regression coverage passes. |
| R-03 | Partially correct configuration observation; security impact overstated | The example does enable cloud entries, but API keys are never sent to the model, fallback is empty by default, and a provider secret is resolved only when that provider is created. Missing credentials cause a bounded authentication failure. A disabled-by-default example remains a possible UX hardening task. |
| R-04 | Incorrect | `service_main.run_service` registers both `SIGINT` and `SIGTERM` with the asyncio server stop path, and `finally: await server.close()` closes the runtime and IDE. The daemon-watchdog observation does not establish a missing service shutdown path. Abrupt power loss remains a hardware limitation, not a SIGTERM defect. |
| R-05 | Confirmed hardening opportunity | The 18-second subprocess and 20-second capability timeouts exist. No failure or leaked file was reproduced. Increasing the cleanup margin should be a focused camera change with Pi validation, outside this refinement. |
| R-06 | Confirmed defense-in-depth observation | The regex is advisory content screening, not the authorization boundary. Skills remain schema/path/tool confined and subordinate to immutable policy. Multilingual patterns and human review guidance remain backlog work. |
| R-07 | Confirmed documentation/deprecation concern | The compatibility fields are intentionally accepted and have no effect. A future schema revision should warn before removing them. |
| R-08 | Correct maintainability note | The `BaseException` cleanup/re-raise is correct. An explanatory comment would reduce future refactor risk but does not change runtime behavior. |
| R-09 | Confirmed documentation-structure concern | The guide remains comprehensive but mixes standard and advanced paths in places. The 2026-08-01 pass removes obsolete web-login setup and labels built-in/external MCP boundaries; a full information-architecture rewrite remains separate. |
| R-10 | Confirmed | Uninstall uses a recoverable directory move, but the update section still needs a commit-based rollback procedure. Treat this as release-documentation backlog. |

Two additional installation claims were not correct at audit time:

- `InstallationGuide.md` already contained complete `whisper.cpp` clone,
  CMake build, multilingual model download, executable/file checks, and
  heat-limited `-j2` guidance.
- Provider configuration does not expose environment-secret values to model
  selection. The model receives provider-neutral tool definitions and messages,
  not the secret store.

### 10.1 Refinement completed from this review

- Google Gemini and Anthropic web-login execution was removed. OpenAI, Gemini,
  and Anthropic now use API keys only.
- Legacy OAuth configuration loads in API-key mode and is rewritten without
  the old profile field. `provider login` is explanatory compatibility only.
- A trusted built-in robot-control MCP façade now provides focused catalog,
  preview, expression, movement, and stop tools.
- Behavior preview compiles compact face, buzzer, melody, text, and movement
  combinations to canonical IDE format without starting hardware.
- Behavior execution retains existing public tool names and flows through the
  IDE with the existing action ledger, session arm, policy, obstacle guard,
  cancellation, latch, and emergency stop.

### 10.2 Verification result

The final local gate passed on 2026-08-01: immutable-driver verification (222
tracked files and 25 authorized repairs), Python compilation, Ruff lint and
format, strict mypy across 66 source files, 363 pytest tests, `git diff
--check`, and IDE/agent source and wheel builds. One pre-existing Starlette
test-client deprecation warning remains. Physical hardware was not operated;
the required staged checklist is
`docs/validation/robot-control-mcp-validation-2026-08-01.md`.
