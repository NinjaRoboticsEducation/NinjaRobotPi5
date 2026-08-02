# NinjaRobotPi5

<div align="center">

**An AI-Powered Raspberry Pi 5 Robot — Talk to It, Control It, Teach It**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Raspberry Pi 5](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/)
[![AI: Local + Cloud](https://img.shields.io/badge/AI-Ollama%20%7C%20OpenAI%20%7C%20Gemini%20%7C%20Anthropic-4285F4.svg)](https://ollama.com/)
[![Release: Alpha](https://img.shields.io/badge/release-alpha-orange.svg)](InstallationGuide.md)

</div>

---

> [!WARNING]
> **Alpha release.** Core features are stable and fully tested in simulation. Physical-device acceptance on the target Raspberry Pi must be completed before normal floor operation. See the [Installation Guide](InstallationGuide.md) before powering the robot.

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
| **Package Manager** | `uv` (manages Python 3.11 and all dependencies) |

---

## ✨ Key Features

### 🧠 Local AI Agent
- **Talk to your robot** — use natural language in English or Japanese
- **Fully local** — the AI model runs on the Pi; no cloud account required for basic use
- **Cloud optional** — connect OpenAI, Gemini, or Anthropic with an API key for more powerful models
- **Session-safe motion** — you explicitly arm and disarm AI control over physical movement
- **Behavior generation** — ask the AI to compose custom face + sound + movement combinations

### 📱 HTTPS Web Controller
- **Phone-friendly** — full D-pad, AI chat, and live camera from any browser on your local network
- **Exclusive controller lease** — only one browser controls the robot at a time
- **Live events panel** — see service and tool activity in real time
- **Browser speech** — speak commands directly (English and Japanese) on supported browsers
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
git clone --branch alpha01 --single-branch \
  https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git
cd NinjaRobotPi5

# 2. Install dependencies
uv sync --frozen

# 3. Verify the environment
uv run --frozen ninjarobot_pi5_cli --version
uv run --frozen ninjarobot_pi5_cli capabilities

# 4. Start the agent in simulation (no hardware opened)
uv run --frozen ninjarobot-agent service start
uv run --frozen ninjarobot-agent chat "Hello! What can you do?"

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
│  AI chat, web controller, provider adapters, MCP, skills   │
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

---

## 📊 Current Status

**Version:** Alpha (Phase 6 complete)  
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
| 🔲 Full Raspberry Pi acceptance (benchmark, live hardware) | Pending operator validation |

---

## 🛡️ Safety Notes

- **Never expose port 8443 to the internet** or configure router port forwarding. The HTTPS controller is for your local network only.
- **Raise the wheels** before any software movement test.
- **Never change wiring while the robot is powered.**
- The current robot has no accessible physical servo cutoff. Software stop and the watchdog reduce risk but cannot replace a physical power disconnect.
- Camera and microphone operations require explicit consent from everyone nearby before you add `--real --confirm-camera` or `--real --confirm-microphone`.

---

<div align="center">

Made with ❤️ for AI Robotics Education and Research

</div>
