# NinjaRobotPi5

<div align="center">

**An AI-Powered Raspberry Pi 5 Robot — Talk to It, Control It, Teach It**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Raspberry Pi 5](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/)
[![AI: Local + Cloud](https://img.shields.io/badge/AI-Ollama%20%7C%20OpenAI%20%7C%20Gemini%20%7C%20Anthropic-4285F4.svg)](https://ollama.com/)
[![Release: v1.0.0 RC](https://img.shields.io/badge/release-v1.0.0%20RC-orange.svg)](docs/architecture/v1.0.0-support-matrix.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

> [!WARNING]
> **v1.0.0 release candidate.** The complete software gate passes, but the Phase 8 display, microphone, ngrok, boot, actuator, and power checklists still require operator acceptance on the target Raspberry Pi before public tagging or normal floor operation. See the [support matrix](docs/architecture/v1.0.0-support-matrix.md) and [Installation Guide](InstallationGuide.md).

---

## 🎯 What Is NinjaRobotPi5?

**NinjaRobotPi5** is an AI-powered robot platform built on the Raspberry Pi 5. It brings a robot's display, buzzer, wheel servos, distance sensor, camera, and microphone together behind one clean software interface — and then adds a fully local AI agent that you can talk to, type to, or control from your phone.

Unlike traditional robot platforms, NinjaRobotPi5 is designed with a **hard safety boundary** between AI and hardware. The AI model can propose actions, but it can never reach a motor, camera, or sensor directly. Every physical action passes through a deterministic safety layer, so you stay in control at all times.

---

## 🤔 What Problem Does It Solve?

Building an AI robot usually means either:
- Writing low-level hardware code and forgetting about AI, or
- Using a cloud AI service that controls nothing, or
- Duct-taping an AI chatbot onto robot code with no safety model

NinjaRobotPi5 solves all three problems. It gives you a **safe, tested AI robot** where:
- The AI runs **locally on the Pi** — no cloud required for basic operation
- The hardware is guarded by a dedicated safety layer the AI cannot bypass
- A phone-friendly browser lets you drive or chat without any extra app
- Local, user-separated memory lets the robot remember preferences and confirmed behaviors
- The whole system can be extended with MCP web tools and reusable AI skills

---

## 🤖 Hardware Profile

| Component | Specification |
|---|---|
| **Computer** | Raspberry Pi 5 (8 GB RAM recommended) |
| **Operating System** | Raspberry Pi OS Lite 64-bit |
| **Storage** | microSD or NVMe SSD; several GB needed for local AI models |
| **Cooling** | Active cooler required for sustained AI inference |
| **Expansion Board** | DFRobot DFR0566 |
| **Left Wheel** | MG90D 360° continuous-rotation servo on GPIO12 |
| **Right Wheel** | MG90D 360° continuous-rotation servo on GPIO13 |
| **Buzzer** | Passive buzzer on GPIO27 |
| **Distance Sensor** | VL53L0X Time-of-Flight, I2C bus 1, address 0x29 |
| **Display** | ST7789V 240×320 IPS, SPI0, DC GPIO4, RST GPIO5, BL GPIO6 |
| **Camera** | Raspberry Pi CSI camera (OV5647) at 1280×720 |
| **Microphone** | USB audio input device |
| **Power** | Official 27 W supply through the Geekworm X1208 |

## 🧩 Software Stack

| Layer | Technology |
|---|---|
| **Hardware Drivers** | Six managed `pi5*` libraries (`pi5servo`, `pi5disp`, `pi5buzzer`, `pi5vl53l0x`, `pi5camera`, `pi5mic`) |
| **Robot Middleware** | `ninjarobot_pi5_ide` — deterministic hardware coordinator and safety layer |
| **AI Agent** | `ninjarobot_pi5_agent` — Ollama, OpenAI, Gemini, Anthropic, HTTPS web interface |
| **Local AI Model** | Ollama + Qwen3:4B (local, no internet required) |
| **Web Interface** | FastAPI + HTTPS, browser-based D-pad and AI chat |
| **Speech** | `whisper.cpp` for local USB microphone transcription |
| **Persistent Memory** | Owner-only SQLite + FTS5, local multi-user profiles, bounded retrieval |
| **Package Manager** | `uv` (manages Python 3.11 and all dependencies) |

---

## ✨ Key Features

### 🧠 Local AI Agent
- **Talk to your robot** — use natural language in English or Japanese
- **Fully local** — the AI model runs on the Pi; no cloud account required for basic use
- **Cloud optional** — connect OpenAI, Gemini, or Anthropic with an API key for more powerful models
- **Gemini 3 tool continuity** — Gemini 3.5/3.6 function-call IDs and opaque reasoning state are retained only for the matching Gemini continuation; older or other-provider tool traces remain safe reference context after a model switch
- **Session-safe motion** — you explicitly arm and disarm AI control over physical movement
- **Behavior generation** — ask the AI to compose custom face + sound + movement combinations
- **Personalization** — separate local profiles, preferences, and memories for each user
- **Behavior learning** — confirm successful new behaviors into both searchable memory and the private IDE behavior catalog; technical failures remain available for analysis

### 🧠 Persistent Multi-User Memory
- **First-user owner setup** — the first chat asks for a name and creates the default owner profile
- **Face identity through the IDE** — enrollment and explicit `/identify` use the existing `pi5camera` API; identity is not authentication
- **Recoverable profile enrollment** — `/update profile` shows the current name/face state and `register user face` retries or refreshes enrollment
- **Per-user conversational identity** — the default is `NinjaAgent`; explicit ordinary-chat requests such as “I want to call you Pocky, and please call me Master” atomically store both the robot name and form of address for that user, overriding older transcript claims
- **Face-verified switching** — `/switch user` changes the active profile only after the camera matches the selected user's registered face; every failure keeps the original user
- **Bounded retrieval** — profile/preferences plus recent successful behaviors and task recipes are always available within a strict cap; query matches add only relevant success/failure context
- **Provider continuity** — changing the AI provider/model does not replace the active user's profile, long-term memory, or current transcript
- **Interface isolation with shared memory** — terminal and browser transcripts and selected-user state stay independent; after each interface selects the same user, both read that user's same long-term memory
- **Read-only model access** — four `memory.*` MCP tools can read only the active user's data; models have no memory mutation tool
- **Deterministic management** — the interactive **Manage Memory** menu and `ninjarobot-agent memory` CLI perform confirmed deletes, face recovery, retention changes, and a separately confirmed full reset
- **Clean initial-state reset** — “Clean All Robot Memory” removes every user (including the owner), transcript, learned behavior, preference, retrieval index, and face record; the next chat starts owner registration again
- **Default retention** — raw conversations 7 days, failed behaviors 180 days, profiles and confirmed successes until manual deletion

### 📱 HTTPS Web Controller
- **Phone-friendly** — full D-pad, AI chat, and live camera from any browser on your local network
- **Exclusive controller lease** — only one browser controls the robot at a time
- **Stable browser chat identity** — controller lease renewal or reconnect keeps that browser's chat session without switching terminal sessions or other browsers
- **Live events panel** — see service and tool activity in real time
- **Four-language browser speech** — English, Japanese, Traditional Chinese, and Simplified Chinese on supported browsers
- **Fullscreen on mobile** — add the controller to your iPhone Home Screen for a standalone app view

### 🔊 Expression & Sound
- **20 animated face expressions** — idle, happy, laughing, sad, angry, surprising, sleepy, speaking, shy, scary, exciting, confusing, greeting, listening, thinking, curious, success, warning, error, and cry
- **Named melodies and tones** — play sounds as part of any behavior
- **Synchronized stages** — face, sound, and movement can start together in one behavior

### 🦺 Safety By Design
- **Simulation by default** — all commands simulate unless you explicitly add `--real`
- **Motion arming** — wheel movement requires your explicit per-session confirmation
- **Privacy confirmation** — camera and microphone require separate consent
- **Hardware lock** — only one process can own the robot at a time (OS file lock)
- **Two-level stop** — Level 1 halts motors only; Level 2 (Emergency Stop) closes all devices
- **Obstacle detection** — three consecutive forward readings below 50 mm automatically stop forward movement
- **Watchdog** — a background thread stops the motors if the main loop freezes
- **AI is sandboxed** — the AI model proposes actions; the IDE safety layer executes or refuses them

### 🔌 Flexible Connectivity
- **Local Wi-Fi** — HTTPS controller at `https://ninjarobotpi5.local:8443/`
- **USB microphone transcription** — offline speech-to-text using `whisper.cpp`
- **Tavily web search** — let the AI search the internet for current information (optional)
- **MCP protocol** — extend the agent with local or hosted tool servers
- **Agent Skills** — reusable validated workflows combining instructions with allowed tools

---

## 🚀 Quick Start (Software Only — No Hardware Required)

```bash
# 1. Clone the repository
git clone --branch public_v01 --single-branch \
  https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git
cd NinjaRobotPi5

# 2. Install dependencies
uv sync --frozen

# 3. Verify the environment
uv run --frozen ninjarobot_pi5_cli --version
uv run --frozen ninjarobot_pi5_cli capabilities

# 4. Start the agent in simulation (no hardware opened)
uv run --frozen ninjarobot-agent service start
uv run --frozen ninjarobot-agent chat
# The first chat asks for your name and creates the owner profile.

# 5. Open the web controller (simulation, no hardware)
uv run --frozen ninjarobot-agent web start
# Open the printed URL in your browser

# 6. Stop everything when done
uv run --frozen ninjarobot-agent web stop
uv run --frozen ninjarobot-agent service stop
```

For full Raspberry Pi hardware setup, follow the [Installation Guide](InstallationGuide.md).

---

## 🏗️ Architecture Overview

NinjaRobotPi5 uses a strict **three-layer boundary**:

```
┌────────────────────────────────────────────────────────────┐
│  Layer 3 — NinjaRobotAgent                                 │
│  AI chat, web controller, memory, provider adapters, MCP   │
│  ↓  (calls only through IDE contracts — never imports pi5*)│
├────────────────────────────────────────────────────────────┤
│  Layer 2 — NinjaRobotPi5 IDE                               │
│  Capability registry, scheduler, safety engine, behaviors  │
│  ↓  (one lazy import per adapter — no direct GPIO from IDE)│
├────────────────────────────────────────────────────────────┤
│  Layer 1 — Managed pi5* Driver Libraries                   │
│  pi5servo · pi5disp · pi5buzzer · pi5vl53l0x               │
│  pi5camera · pi5mic                                        │
└────────────────────────────────────────────────────────────┘
```

- **The AI model can never bypass the IDE safety layer.**
- **Each driver library is independently testable** and has its own lockfile and test suite.
- **Cloud providers** translate model traffic only — they never execute a tool or access the Pi directly.

---

## 📚 Documentation

| Document | Purpose |
|---|---|
| [Installation Guide](InstallationGuide.md) | Step-by-step: from blank Pi to a calibrated, running robot |
| [Development Guide](DevelopmentGuide.md) | Architecture, API reference, driver policy, and contributor workflow |
| [Audit Report](AuditReport_260731.md) | Security, reliability, and documentation audit findings |
| [Implementation Plan](NinjaRobotPi5V4_ImplementationPlan.md) | Authoritative design and phase decisions |
| [Hardware Profile](docs/hardware/hardware-profile.md) | Confirmed wiring and electrical records |
| [Phase 7 Pi Validation](docs/validation/phase-7-persistent-memory-validation-2026-08-12.md) | Memory, identity, retention, and hardware checklist |
| [Phase 8.2 Voice Validation](docs/validation/phase-8-2-voice-input-pi-checklist.md) | Wake word, microphone ownership, privacy, soak, and armed-motion checklist |
| [Phase 8.3 Remote Validation](docs/validation/phase-8-3-remote-access-pi-checklist.md) | ngrok setup, pairing/replay rejection, recovery, and removal checklist |
| [Phase 8.4 Web/Power Validation](docs/validation/phase-8-4-web-poweroff-pi-checklist.md) | Four-locale dashboard, accessible menu, preserved controls, shutdown nonce, and power-risk checklist |
| [Phase 8.5 Onboarding Validation](docs/validation/phase-8-5-onboarding-pi-checklist.md) | QR decoding, remote/local fallback, pairing gate, exactly-once Greeting, and error recovery |
| [Phase 8.6 systemd Validation](docs/validation/phase-8-6-systemd-pi-checklist.md) | Disabled-by-default install, boot/restart, hardware groups, power-off privilege, upgrade/rollback, and uninstall |
| [v1.0.0 Release-Candidate Report](docs/validation/v1.0.0-release-candidate-report.md) | Final software, packaging, architecture, privacy/security, residual-risk, and publication status |
| [Phase 8 Final Interactive Validation](docs/validation/phase-8-final-interactive-pi-validation-2026-08-14.md) | Existing checkout, clean clone, normal-user tools, hardware, remote, boot, power, and soak acceptance |
| [v1.0.0 Support Matrix](docs/architecture/v1.0.0-support-matrix.md) | Supported platforms/features, compatibility guarantees, known limitations, and open Pi acceptance |

---

## 📄 License and Release Assets

NinjaRobotPi5 source code is licensed under the [MIT License](LICENSE).
Third-party dependencies, the optional ngrok service, and model/runtime assets
retain the terms recorded in [Third-Party Notices](THIRD_PARTY_NOTICES.md).

The approved custom **Hey Ninja** ONNX wake model and its pinned openWakeWord
feature/VAD assets are packaged with the IDE and protected by recorded SHA-256
checksums. Always-on voice is opt-in and runs locally: say **Hey Ninja**, speak
for up to 15 seconds, and the command ends early after silence. No continuous
audio or command WAV is retained, and v1.0.0 is input-only—replies remain on
the display/web interface and use existing robot behaviors rather than TTS.

---

## 📊 Current Status

**Version:** Alpha (Phase 7 implemented)
**Status:** All software gates pass ✅ | Raspberry Pi acceptance pending 🔲

| Feature Area | Status |
|---|---|
| ✅ Six managed hardware driver libraries | Complete |
| ✅ IDE capability registry, scheduler, safety engine | Complete |
| ✅ 20 animated face expressions | Complete |
| ✅ Integrated behaviors (faces + sounds + movement) | Complete |
| ✅ NinjaRobotAgent — Ollama local AI | Complete |
| ✅ NinjaRobotAgent — OpenAI, Gemini, Anthropic cloud adapters | Complete |
| ✅ HTTPS web controller (D-pad, chat, camera, microphone) | Complete |
| ✅ MCP tool protocol — Tavily web search preset | Complete |
| ✅ Agent Skills system | Complete |
| ✅ Session-lived motion arming | Complete |
| ✅ Level 1 / Level 2 stop and resume | Complete |
| ✅ USB microphone + local whisper.cpp transcription | Complete |
| ✅ Behavior draft compiler (AI → IDE behavior format) | Complete |
| ✅ Persistent multi-user memory, face identity, bounded retrieval | Software complete |
| ✅ Read-only memory MCP + bundled retrieval skill | Complete |
| ✅ Interactive/scriptable memory management | Complete |
| ✅ Phase 8 release configuration, dependency, secret, and status foundations | Complete |
| ✅ IDE-owned Hey Ninja voice input, four transcription locales, shared safety path | Software complete |
| ✅ Optional ngrok lifecycle and passwordless, short-lived remote pairing | Software complete; live account validation pending |
| ✅ Four-locale responsive web menu and safe power-off boundary | Software complete; Pi power-risk validation waits for Phase 8.6 helper installation |
| ✅ QR onboarding and connection-triggered Greeting | Software complete; Pi display/Greeting validation pending |
| ✅ Opt-in boot service and narrow power-off deployment | Software complete; Pi boot/power acceptance pending |
| ✅ v1.0.0 software/package release candidate | Complete; public tag waits for signed Pi acceptance and owner approval |
| 🔲 Full Raspberry Pi acceptance (benchmark, live hardware) | Pending operator validation |

---

## 🛡️ Safety Notes

- **Never expose port 8443 to the internet** or configure router port forwarding. The HTTPS controller is for your local network only.
- **Raise the wheels** before any software movement test.
- **Never change wiring while the robot is powered.**
- The current robot has no accessible physical servo cutoff. Software stop and the watchdog reduce risk but cannot replace a physical power disconnect.
- Camera and microphone operations require explicit consent from everyone nearby before you add `--real --confirm-camera` or `--real --confirm-microphone`.
- Profile enrollment intentionally captures a photo after the visible countdown. Cropped profile photos and face data remain readable by the Raspberry Pi administrator and must be treated as personal data.
- Always-on voice continuously processes short PCM frames locally while it is enabled, but retains no background audio. Use `/voice input off` or the web **VOICE INPUT** control whenever people nearby have not consented.
- Never share a remote pairing URL or screenshot its fragment. Anyone who possesses a current physical QR/pairing link can claim a browser session until it expires or is rotated.

### Always-on voice commands

Install the hardware/release dependencies and make sure local `whisper.cpp`
transcription is configured, then start the real service. In terminal chat:

```text
/voice input on
/voice input status
/voice input off
```

The web **VOICE INPUT** button controls the same global listener. **RECORD
ONCE** remains available as an independent manual capture; the IDE pauses and
restores the listener around it. English, Japanese, Traditional Chinese, and
Simplified Chinese are supported transcription selections. `/arm` or **Arm AI
motion** also authorizes the independent voice session; voice disablement,
model replacement, emergency stop, disconnect of the granting browser, and
service restart revoke that voice motion grant.

Enablement succeeds only after the USB stream reaches `listening`. A busy,
missing, unsupported, permission-denied, or stalled microphone returns a
bounded error and leaves voice disabled instead of remaining indefinitely in
`starting`.

### Optional remote access

Remote access is disabled by default. Start the agent service, then use the
Interactive Tool's **Remote Access** menu, or the scriptable commands:

```bash
uv run --frozen --extra hardware ninjarobot-agent remote configure
uv run --frozen --extra hardware ninjarobot-agent remote activate
uv run --frozen ninjarobot-agent remote pairing-url
```

`remote configure` is the only operation allowed to download/install the ngrok
agent. It reuses a valid ngrok v3 binary and installs replacements atomically,
so a running binary is never overwritten in place. It uses hidden double-entry
for the authtoken and stores credentials in the owner-only secret store.
Service boot never downloads or updates ngrok.
Open the returned pairing URL on the controlling browser. The URL fragment is
exchanged once for a Secure/HttpOnly cookie, so there is no second username or
password prompt. Use `remote rotate-pairing` to revoke browsers and issue a new
link, or `remote deactivate` to stop the exact tunnel and revoke all sessions.

An ngrok authtoken identifies the Pi agent; it does not authenticate a browser.
The project therefore enforces its own short-lived pairing, exact Origin/Host
checks, and an ngrok-injected transport marker before exposing assets or the
WebSocket controller. ngrok accounts, free-plan interstitials/limits, and
possible charges remain governed by [ngrok's current limits](https://ngrok.com/docs/pricing-limits/free-plan-limits).

The complete normal-user Raspberry Pi acceptance workflow is in the
[Phase 8 interactive validation guide](docs/validation/phase-8-final-interactive-pi-validation-2026-08-14.md).

---

<div align="center">

Made with ❤️ for AI Robotics Education and Research

</div>
