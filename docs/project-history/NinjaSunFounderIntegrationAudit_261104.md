# NinjaRobotPi5 SunFounder Fusion HAT+ post-integration system audit and implementation plan

This document records the comprehensive system audit conducted on 4 November 2026
following the integration of the SunFounder Fusion HAT+ kernel driver
(`1.1.0-ninja1`), ALSA sound card (`sndrpigooglevoi`), and staged onboarding
workflow documented in
[NinjaSunFounderRegressionInvestigation_261103.md](NinjaSunFounderRegressionInvestigation_261103.md)
and
[fusion_implementation_261103.md](../validation/fusion_implementation_261103.md).

Although the servos, embedded microphone, and embedded speaker pass standalone
hardware verification during `ninjarobot onboard`, four runtime issues persist
when operating the integrated NinjaRobot Agent service (`ninjarobot-agent`):

1. **Servo control:** Requesting `hat_pwm0` rotation to 90 degrees (with AI
   motion armed) fails with an undervoltage safety refusal.
2. **Embedded speaker:** Requesting spoken output (with `/speech on` active)
   causes the agent to claim it only has a buzzer and cannot use an embedded
   speaker for speech or audio playback, followed by a synthesis failure notice.
3. **Power control:** The **Power off NinjaRobot** button in the web controller
   menu remains permanently disabled.
4. **Voice input:** Web-based voice input (both the browser **WEB MICROPHONE**
   button and the robot **VOICE INPUT** wake-word toggle) is unstable and
   intermittently fails to record or recognize user speech.

## Contents

1. [Executive summary and runtime baseline](#executive-summary-and-runtime-baseline)
2. [Issue 1 root cause analysis: servo control blocked by undervoltage](#issue-1-root-cause-analysis-servo-control-blocked-by-undervoltage)
3. [Issue 2 root cause analysis: embedded speaker refusal and TTS failure](#issue-2-root-cause-analysis-embedded-speaker-refusal-and-tts-failure)
4. [Issue 3 root cause analysis: web power-off button disabled](#issue-3-root-cause-analysis-web-power-off-button-disabled)
5. [Issue 4 root cause analysis: web-based voice input instability](#issue-4-root-cause-analysis-web-based-voice-input-instability)
6. [Potential vulnerabilities and architectural risks](#potential-vulnerabilities-and-architectural-risks)
7. [Phased implementation plan](#phased-implementation-plan)
8. [Wiki and documentation impact decision](#wiki-and-documentation-impact-decision)
9. [Validation gates and Raspberry Pi test checklists](#validation-gates-and-raspberry-pi-test-checklists)

## Executive summary and runtime baseline

Read-only inspection of the Raspberry Pi 5 host, kernel interfaces, private
configuration (`~/.config/ninjarobot_pi5/config.toml`), managed-driver configs
(`~/.config/pi5*/`), persistent state (`~/.local/state/ninjarobot_pi5/`), and
SQLite ledgers (`agent-actions.sqlite3` and `conversations.sqlite3`) established
that **the Fusion HAT+ hardware and kernel driver are healthy**:

- `uv run --frozen python scripts/fusion_hat_setup.py check` reports
  `"ready": true`, `installed_version: "1.1.0-ninja1"`,
  `pwm_channels_present: 12`, `sound_card_ready: true`, and
  `battery_readable: true`.
- `vcgencmd get_throttled` returns `throttled=0x0` (no current or historical
  boot-cycle Raspberry Pi 5 PMIC undervoltage).
- `/sys/class/power_supply/fusion-hat/voltage_now` reads `8022000` microvolts
  (`8.022 V`, status `Charging`), well above the configured `6.9 V` cutoff.
- `/proc/asound/cards` reports card `0` as `sndrpigooglevoi`
  (`snd_rpi_googlevoicehat_soundcard`).
- `~/.config/pi5servo/servo.json` contains valid calibrations for `hat_pwm0` and
  `hat_pwm1` with backend `"fusion_hat"`, imported into `config.toml` with
  `motion_enabled = true` and `group_motion_enabled = true`.

All four reported issues stem from **software state, configuration-import gaps,
prompt/tool-contract omissions, and audio/speech lifecycle defects** between
`ninjarobot_pi5_agent` and `ninjarobot_pi5_ide`.

| Issue | Confirmed primary root cause | Confirmed compounding causes |
| --- | --- | --- |
| **1. Servo blocked by undervoltage** | A persistent Level 1 motion latch (`"motion_latched": true, "reason": "undervoltage"`) recorded on `2026-11-02T03:09:04Z` in `~/.local/state/ninjarobot_pi5/safety.json` remains active across service restarts and re-onboarding. | 1) User's `/resume` attempt (`action_ledger` row 11) failed because `/resume` calls `system.resume` (requiring all 6 devices, including an unconfigured microphone on Nov 2) instead of `motion.resume`.<br>2) `MotionController._check_stop_state()` reports a historical latch in the present tense without checking current power telemetry or showing `updated_at`.<br>3) `servo.status` and LLM `runtime_state` omit `motion_latched`.<br>4) `config_import.py` sets `behaviors.servo_roles = {}` for Fusion HAT+, breaking `behavior.execute_movement` and Gamepad D-pad moves. |
| **2. Embedded speaker refusal & TTS failure** | **Two independent faults:**<br>**2A (LLM refusal):** `IDENTITY_PROMPT` and `runtime_state` never inform the LLM that text replies are automatically spoken via the post-reply `SpeechService` pipeline, while exposed tools only list `buzzer` (`tone`/`melody`).<br>**2B (Silent TTS failure):** `configure_sunfounder_i2s_speaker()` enables `speech_output.enabled = true` in `config.toml` after playing a synthetic sine chime, but Piper TTS (`~/.local/share/ninjarobot_pi5/speech/bin/python`) and voice models (`english_model = ""`, `chinese_model = ""`) were never installed or configured. | 1) `SpeechService.speak()` catches `ValueError("speech_model_not_configured")` and collapses it into a generic `"Spoken output unavailable or stopped; the text reply is retained."` notice.<br>2) `AgentRuntime._append_memory_notice()` both streams that notice into the assistant reply text (without a separator space) and appends a duplicate assistant row in `conversations.sqlite3`, poisoning subsequent LLM turns into repeating that speech hardware does not exist. |
| **3. Web Power Off button disabled** | `app-shared.js` disables `#powerOffButton` unless four gates pass (`poweroffEnabled && poweroffReady && poweroffAuthorized && leaseId`). Currently `deployment.web_poweroff_enabled = false` in `config.toml` and `/usr/libexec/ninjarobot-poweroff` + `/etc/sudoers.d/ninjarobot-agent-poweroff` are not installed. | 1) `ninjarobot onboard` (`setup_wizard.py`) has no step to install the privileged poweroff helper or enable web power-off.<br>2) `DeploymentManager.enable()` couples `web_poweroff_enabled = true` to `systemd enable ninjarobot-agent.service` (`auto_start_enabled = true`), preventing interactive users from enabling web power-off without boot auto-start. |
| **4. Web-based voice input unstable** | **Both web voice paths have confirmed defects:**<br>**4A (`#webMicButton` Browser Speech API):** `onresult` loops from `event.resultIndex` instead of `0` and overwrites `chatInput.value`, discarding earlier segments; `state.speechListening` races between `click`, `onstart`, and `onend`; browser cloud STT fails on Chromium/LAN self-signed TLS.<br>**4B (`#usbMicButton` Robot Voice Input):** `VoiceInputController` aborts on any single PortAudio `overflowed` flag (`VoiceInputError("audio_overflow")`) or empty Whisper result (`VoiceInputError("transcription_failed")`) and permanently enters `FAILED` after `retry_limit = 2` (3 occurrences). | 1) `import_pi5_configs()` ignores `mic.json` `voiceinput` settings (`enabled = true`, `silence_rms_threshold = 500`, `silence_timeout_seconds = 3.0`).<br>2) `_pcm_rms()` does not remove DC offset on the I2S MEMS mic (`sndrpigooglevoi`), causing VAD to either hang until `max_command_seconds` (`6.0s`) or never detect speech start.<br>3) `_PCMFrameAssembler.feed()` resamples 48 kHz -> 16 kHz sample-by-sample in pure Python on the asyncio event loop thread.<br>4) PulseAudio (`PID 875`) wakes on default ALSA queries and holds `hw:0,0` for 5s, causing `PaErrorCode -9985 (Device unavailable)`. |

## Issue 1 root cause analysis: servo control blocked by undervoltage

### 1.1 Confirmed evidence from runtime state and SQLite ledgers

1. **Persistent safety state file (`~/.local/state/ninjarobot_pi5/safety.json`):**
   Inspection of `safety.json` (last modified `2026-11-02 12:09:04 +0900`) shows:

   ```json
   {
     "fault_detail": null,
     "motion_latched": true,
     "reason": "undervoltage",
     "system_latched": false,
     "updated_at": "2026-11-02T03:09:04.813631Z"
   }
   ```

2. **Origin of the latch (`action_ledger` row 3 & `agent-service.log` line 47):**
   On 2 November 2026 at `03:09:04Z` (before the Fusion HAT+ integration on
   3 November), the agent executed `servo.move` on `hat_pwm10` (`target_angle: 45`).
   During that move, `raspberry_pi_undervoltage_active()` observed a transient
   undervoltage flag from `vcgencmd get_throttled`, aborting the servo move and
   writing `motion_latched = true, reason = "undervoltage"` to `safety.json`:

   ```text
   2026-11-02 12:09:04,816 ERROR ninjarobot_pi5_ide.safety: Persistent motion stop activated: reason=undervoltage cause=The Raspberry Pi reported undervoltage while the robot was moving.
   ```

3. **Why the user's `/resume` command failed to clear the latch (`action_ledger` row 11):**
   Later on 2 November at `14:50:33Z`, the operator ran `/resume` in `local-cli`.
   `action_ledger` row 11 records:

   ```json
   {
     "action_id": "agent-control-cc34caa125fc4d3caf28d3989485fc54",
     "capability": "system.resume",
     "requested_by": "ipc-resume",
     "status": "failed",
     "error": {
       "code": "ADAPTER_EXECUTION_FAILED",
       "message": "The capability adapter reported an unexpected failure.",
       "technical_detail": "RuntimeError: system resume refused because these health checks failed: microphone (reported unavailable)"
     }
   }
   ```

4. **Subsequent servo move refusals on 3–4 November (`action_ledger` rows 18–19, 28, 32–37, 39–40, 60–61):**
   After the operator completed the Fusion HAT+ onboarding on 3 November and
   calibrated `hat_pwm0` and `hat_pwm1`, every `servo.move` tool call failed
   within 5 milliseconds at the pre-execution stop-state check (`definitely_not_executed: true`)
   with `code: "MOTION_STOPPED"` because `safety.json` still held the 2 November
   latch. Meanwhile, live hardware checks confirm `vcgencmd get_throttled` is
   `0x0` and `/sys/class/power_supply/fusion-hat/voltage_now` is `8.022 V`.

### 1.2 Code trace across layers

1. **Pre-move latch gate (`ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/safety.py:372-386`):**
   Before touching hardware or checking live voltage, `MotionController.move_endpoint()`
   calls `self._check_stop_state("servo.move")`:

   ```python
   snapshot = self._state.read()
   if snapshot.motion_latched:
       guidance = stop_guidance(
           snapshot.reason or "operator_stop",
           fault_detail=snapshot.fault_detail,
       )
       raise IDEError(
           ErrorDetails(
               code="MOTION_STOPPED",
               message=f"{guidance.cause} Recovery: {guidance.recovery_instruction}",
               ...
           )
       )
   ```

   Because `stop_guidance("undervoltage")` (`safety.py:80-95`) returns the static
   string `"The Raspberry Pi reported undervoltage while the robot was moving."`
   without including `snapshot.updated_at` (`2026-11-02T03:09:04Z`) or checking
   whether undervoltage is *currently* active (`await self._undervoltage_detected()`),
   both the LLM and the operator are told that an electrical fault is happening
   right now.

2. **Resume level mismatch (`runtime.py:1934-1959`, `web_control.py:394-403`, `robot.py:621-655`):**
   - `ninjarobot_pi5_ide` defines two distinct recovery capabilities in
     `integrated.py:450-498`:
     - `motion.resume` (`RobotAssembly.resume_motion`, `robot.py:621-628`):
       verifies live power readiness (`ensure_power_ready()`) and clears a
       **Level 1 (`motion_latched`)** stop.
     - `system.resume` (`RobotAssembly.resume_system`, `robot.py:630-655`):
       verifies live power readiness AND runs health probes across all enabled
       devices (`display`, `buzzer`, `servo`, `distance`, `camera`, `microphone`)
       to clear a **Level 2 (`system_latched`)** stop.
   - However, `AgentRuntime.resume_system()` (`runtime.py:1934-1959`), CLI `/resume`
     (`agent_cli.py:1189-1218`), and Web UI `Resume` (`web_control.py:394-403`)
     **always invoke `robot.system.resume`**, never `robot.motion.resume`!
   - When only `motion_latched` is `True` (`system_latched` is `False`), forcing
     `system.resume` causes unrelated optional sensors (such as an unconfigured
     microphone) to block motion recovery.

3. **Hidden latch state in `servo.status`, `startup_status`, and LLM `runtime_state`:**
   - `ServoDevice.status()` (`servo.py:240-252`) returns `endpoints`, `calibrated`,
     `motion_enabled`, `group_motion_enabled`, `driver_available`, and `simulated`,
     but **omits `motion_latched` and `stop_reason`**. In `conversations.sqlite3`
     (row 58, `2026-11-03 14:11:17Z`), the LLM called `robot.servo.status`, saw
     `motion_enabled: true` and `calibrated: true`, and had no idea motion was
     latched until `robot.servo.move` failed.
   - `AgentRuntime._recovery_status()` (`runtime.py:881-897`) sets
     `"required": system_latched`, ignoring `motion_latched`.
   - `service_main.py:216-247` (`runtime_state`) omits `safety` (`motion_latched`,
     `system_latched`, `reason`, `updated_at`).
   - `ninjarobot onboard` (`setup_wizard.py`) never inspects `safety.json` during
     hardware reconfiguration or offers to clear a stale latch after verifying
     healthy power.

4. **Compounding defect: empty `behaviors.servo_roles` on Fusion HAT+ (`config_import.py:194-205`):**
   - In `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config_import.py:204`:

     ```python
     elif is_fusion:
         roles = {}
     ```

   - When migrating to `fusion_hat_plus` from default legacy roles (`gpio12`/`gpio13`),
     `import_pi5_configs()` wipes `behaviors.servo_roles` to `{}` instead of
     mapping calibrated endpoints or prompting the user.
   - Consequently:
     - Pressing D-pad buttons in the Web Gamepad UI (`action_ledger` rows 22, 25,
       43, 46, 49, 52) fails with
       `MOTION_STOPPED: movement contains unmapped servo roles: left_motor, right_motor`.
     - Meanwhile, `IDENTITY_PROMPT` (`prompts.py:88-89`) instructs the LLM:
       `"Any request containing servo or physical movement must use robot.behavior.execute_movement, never robot.behavior.execute_expression."`
       When the LLM obeys this prompt (`action_ledger` rows 2 and 27),
       `behavior.execute_movement` fails with
       `BEHAVIOR_DRAFT_INVALID: movement preset references unconfigured logical roles: left_motor, right_motor`!
       For single-endpoint angle commands (such as `"rotate PWM0 servo to 90 degrees"`),
       the prompt should direct the LLM to `robot.servo.move` when a specific
       endpoint and angle are requested, or `servo_roles` must be populated.

## Issue 2 root cause analysis: embedded speaker refusal and TTS failure

### 2.1 Confirmed evidence from `config.toml` and `conversations.sqlite3`

1. **Configuration state (`~/.config/ninjarobot_pi5/config.toml`):**

   ```toml
   [speech_output]
   enabled = true
   piper_python = "~/.local/share/ninjarobot_pi5/speech/bin/python"
   english_model = ""
   chinese_model = ""
   output_node = "alsa:sndrpigooglevoi"
   ```

2. **Filesystem verification:**
   - `~/.local/share/ninjarobot_pi5/speech/` **does not exist**.
   - `~/.local/share/ninjarobot_pi5/voices/` **does not exist**.
   - Neither `english_model` nor `chinese_model` is configured.

3. **Conversation transcript evidence (`~/.local/share/ninjarobot_pi5/conversations.sqlite3`):**
   Across every turn in `conversations.sqlite3` (rows 4–9, 17–22, 27–32, 34–41,
   43–45, 51–53, 55, 62, 65), two symptoms appear simultaneously:
   - When asked `"can you speak now"` (row 33), `"now try to speak out loud"`
     (row 36), or `"Can you speak out lout with embeded speaker?"` (row 50), the
     LLM replies:

     > `"I truly wish I could, Master, but I do not have an embedded speaker capable of speech or playing audio files. My only way to make sound is through a small buzzer, which can only play simple tones and melodies."`

   - Immediately after the LLM generates its text reply, `AgentRuntime.chat()`
     attempts automatic TTS synthesis, fails, concatenates
     `Spoken output unavailable or stopped; the text reply is retained.` onto the
     streamed message without a leading space, **and** inserts a duplicate
     `assistant` message row containing
     `Spoken output unavailable or stopped; the text reply is retained.` into
     `conversations.sqlite3`.

### 2.2 Code trace across layers

1. **Root Cause 2A — Why the LLM claims it only has a buzzer (`prompts.py:32-118`, `service_main.py:216-247`):**
   - Spoken reply synthesis in NinjaRobot is a **post-reply runtime pipeline hook**
     in `AgentRuntime.chat()` (`runtime.py:540-553`): after the LLM finishes its
     turn (`reply = await self._chat_with_task(...)`), `AgentRuntime` calls
     `await self.speech.speak(reply.spoken_summary or reply.text)`.
   - There is **no `robot.speaker.*` or `robot.speech.*` tool** in the LLM tool
     registry; the only sound-producing tools exposed to the model are
     `robot.buzzer.play_tone` and `robot.behavior.execute_expression` (which
     supports `tone` and `melody` on the buzzer).
   - Neither `IDENTITY_PROMPT` (`prompts.py:32-118`) nor `runtime_state`
     (`service_main.py:216-247`) informs the LLM that:
     1. The robot has an audio output pipeline (`speech_output`) that
        automatically speaks the assistant's text replies through the configured
        speaker (`alsa:sndrpigooglevoi` on Fusion HAT+ or Bluetooth speaker)
        whenever `/speech on` (`speech_output.enabled = true`) is active; and
     2. To speak out loud through the embedded speaker, the assistant simply
        writes the desired spoken words in its normal text reply (and `spoken_summary`)
        rather than searching for a speaker tool.
   - Compounding this, once earlier turns recorded assistant messages claiming
     `"I do not have a speaker"` and `"Spoken output unavailable or stopped"` in
     `conversations.sqlite3`, those messages remained in the 24-message rolling
     context window (`context.py`), conditioning the LLM to repeat the refusal.

2. **Root Cause 2B — Why onboarding speaker setup succeeded while runtime TTS failed (`setup_wizard.py:604-631`, `bluetooth_setup.py:238-315`, `speech.py:36-74`):**
   - During `ninjarobot onboard`, the Fusion HAT+ **"Embedded Speaker Initialization"**
     step (`setup_wizard.py:604-631`) calls:
     1. `configure_sunfounder_i2s_speaker(config_path)` (`bluetooth_setup.py:238-259`),
        which sets `speech_output.enabled = True` and
        `speech_output.output_node = "alsa:sndrpigooglevoi"`.
     2. `play_sunfounder_speaker_test_tone(node)` (`bluetooth_setup.py:262-315`),
        which generates a pure 440/660 Hz sine-wave WAV in Python
        (`synthesize_test_chime_wav`) and plays it via `aplay -q -D plughw:sndrpigooglevoi`.
   - Because `play_sunfounder_speaker_test_tone()` does **not** use Piper TTS, the
     test tone plays through the Fusion HAT+ speaker even when Piper TTS and voice
     models are completely absent!
   - Onboarding never checks `speech_health()`, never runs
     `scripts/prepare_speech_voice.py`, and never configures `piper_python`,
     `english_model`, or `chinese_model` in `config.toml`.
   - At runtime, `LocalSynthesizer._paths()` (`speech.py:36-45`) checks:

     ```python
     model = self.config.english_model if language == "en" else self.config.chinese_model
     if not model:
         raise ValueError("speech_model_not_configured")
     ```

   - `SpeechService.speak()` (`speech.py:216-222`) catches `Exception` and hides
     the specific `speech_model_not_configured` / `piper_python_missing` reason
     behind `"speech_unavailable_or_interrupted; text retained"`.

3. **Root Cause 2C — Duplicate and unspaced notice corruption in `AgentRuntime._append_memory_notice` (`runtime.py:546-553, 711-728`):**
   - In `AgentRuntime.chat()` (`runtime.py:546-553`):

     ```python
     spoken = await self.speech.speak(reply.spoken_summary or reply.text)
     if spoken.get("status") == "failed":
         notice = "Spoken output unavailable or stopped; the text reply is retained."
         reply = await self._append_memory_notice(
             session_id, reply, notice, on_text_delta=on_text_delta
         )
     ```

   - And in `_append_memory_notice()` (`runtime.py:711-728`):

     ```python
     if on_text_delta is not None:
         res = on_text_delta(notice)
         if inspect.isawaitable(res):
             await res
     await self.store.append_message(
         session_id,
         MessageRole.ASSISTANT,
         notice,
         user_id=user_id,
     )
     return reply.model_copy(update={"text": f"{reply.text}\n\n{notice}"})
     ```

   - This has two bugs:
     1. `on_text_delta(notice)` streams `notice` without a leading `\n\n`, so UI
        clients concatenate `...today?Spoken output unavailable...`.
     2. `self.store.append_message(session_id, MessageRole.ASSISTANT, notice)`
        persists a separate assistant turn in `conversations.sqlite3` for every
        failed TTS attempt, polluting the conversation history and wasting half
        of the 24-message LLM context window on error notices.

## Issue 3 root cause analysis: web power-off button disabled

### 3.1 Confirmed four-gate mechanism

In `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-shared.js:427-435`,
`updatePowerOffState()` controls `#powerOffButton`:

```javascript
export function updatePowerOffState() {
  if (!elements.powerOff) return;
  elements.powerOff.disabled =
    !state.poweroffEnabled ||
    !state.poweroffReady ||
    !state.poweroffAuthorized ||
    !state.leaseId;
  ...
}
```

The four gates are populated by `/api/status` (`web_app.py:446-475`) and WebSocket
`status` frames (`web_app.py:854-882`):

| Gate in `app-shared.js` | Backend source (`web_app.py` / `shutdown.py`) | Current value on host | Why |
| --- | --- | --- | --- |
| `state.poweroffEnabled` | `config.deployment.web_poweroff_enabled` (`shutdown.py:118`) | `false` | `~/.config/ninjarobot_pi5/config.toml` has `[deployment] web_poweroff_enabled = false`. |
| `state.poweroffReady` | `PoweroffCoordinator._probe_poweroff_helper()` (`shutdown.py:201-235`) | `false` | `/usr/libexec/ninjarobot-poweroff` and `/etc/sudoers.d/ninjarobot-agent-poweroff` do not exist on this Raspberry Pi. |
| `state.poweroffAuthorized` | `paired_connection` (`web_app.py:458, 868`) | `true` only after `/pair` | Requires an active paired browser session cookie (`ninjarobot_web_session`). |
| `state.leaseId` | Active WebSocket controller lease | `true` when connected | Assigned on WebSocket controller connection. |

### 3.2 Why deployment artifacts and `web_poweroff_enabled` were never configured

1. **Onboarding (`setup_wizard.py`) completely omits deployment / power-off setup:**
   `run_setup_wizard()` (`setup_wizard.py:215-392`) walks the user through:
   - Hardware profile selection (`fusion_hat_plus` vs `legacy_pi5`)
   - Mandatory hardware (`buzzer`, `display`, `distance`, `servo`, `camera`)
   - Optional hardware (`bluetooth`/embedded speaker, `microphone`)
   - Config import (`_import_hardware_configuration`)
   - AI model provider (`_provider_setup`)
   - MCP servers (`_mcp_setup`)
   - Remote access (`_remote_setup`)
   - Service start (`ninjarobot-agent service start --real`)
   It **never** offers to install `/usr/libexec/ninjarobot-poweroff` +
   `/etc/sudoers.d/ninjarobot-agent-poweroff` or enable `web_poweroff_enabled`.

2. **`DeploymentManager` (`deployment.py:322-372`) couples `web_poweroff_enabled` to systemd boot auto-start:**
   - Currently, the only way to install `/usr/libexec/ninjarobot-poweroff` and set
     `web_poweroff_enabled = true` is by running `ninjarobot-agent deployment setup --confirm`
     (or `deployment install --confirm` followed by `deployment enable --confirm`).
   - However, `DeploymentManager.enable()` (`deployment.py:322-347`) unconditionally
     runs `sudo systemctl enable ninjarobot-agent.service` and sets
     `auto_start_enabled = True` alongside `web_poweroff_enabled = True`.
   - Operators who start the agent via `ninjarobot onboard` or
     `ninjarobot-agent service start --real` (without wanting boot-time systemd
     auto-start) have no supported path to install just the root-owned poweroff
     helper + narrow sudoers rule and enable `web_poweroff_enabled`.

3. **Local LAN un-paired connection authorization edge case (`service_main.py:199-203`, `web_app.py:456-462`):**
   - In `web_app.py:456-462`, `poweroff_authorized` is set to
     `bool(poweroff.get("enabled") and poweroff.get("ready") and paired_connection)`.
   - When `remote_access.enabled = false` and `deployment.auto_start_enabled = false`,
     `_effective_onboarding_enabled()` (`service_main.py:43-50`) returns `False`,
     which sets `require_local_pairing = False` (`service_main.py:202`).
   - When `require_local_pairing` is `False`, a local LAN browser can open
     `https://<pi-ip>:8443/` and acquire a WebSocket controller lease **without**
     visiting `/pair` first, meaning `paired_connection` is `False` (no session
     cookie) even though the user holds the active local controller lease! In that
     mode, `poweroff_authorized` remains `False` despite the UI message saying
     `"Connect as the active controller to use power-off."` (`app-shared.js:445`).

## Issue 4 root cause analysis: web-based voice input instability

The web interface (`ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/agent.html:45-55`)
exposes two voice input controls in `.audio-controls`:

1. **`#webMicButton` ("WEB MICROPHONE / Fill the message box")** — browser-side
   speech recognition (`window.SpeechRecognition || window.webkitSpeechRecognition`).
2. **`#usbMicButton` ("VOICE INPUT / Always-on Ninja: Off")** — robot-side
   always-on wake-word + command capture (`voice_enable` / `voice_disable` ->
   `VoiceInputService` -> `VoiceInputController` -> `ManagedVoiceAudioSource` +
   `WhisperCppTranscriber`).
3. Additionally, `web_app.py:701` (`usb_microphone`) implements a robot-side
   push-to-talk transcription endpoint (`WebRobotController.transcribe()` ->
   `robot.microphone.transcribe`), which is **not wired to any button** in
   `agent.html` or `app-agent.js`.

Both active paths (`#webMicButton` and `#usbMicButton`) contain confirmed bugs
that cause intermittent recording and recognition failures.

### 4.1 Path A: Browser `#webMicButton` (`app-agent.js:240-309`)

1. **`event.resultIndex` transcript truncation bug (`app-agent.js:262-269`):**

   ```javascript
   recognition.onresult = (event) => {
     let transcript = "";
     for (let index = event.resultIndex; index < event.results.length; index += 1) {
       transcript += event.results[index][0].transcript;
     }
     if (elements.chatInput) elements.chatInput.value = transcript.trim();
     setSpeechStatus(transcript.trim() ? `${t("browserMic.heard")}: ${transcript.trim()}` : "");
   };
   ```

   Because `recognition.interimResults = true`, the browser emits multiple
   `onresult` callbacks. Whenever an initial phrase is finalized
   (`event.results[0].isFinal === true`) and a second segment begins
   (`event.results[1]`), the browser advances `event.resultIndex` to `1`. Starting
   the loop at `event.resultIndex` instead of `0` while assigning
   `elements.chatInput.value = transcript.trim()` **overwrites and discards all
   earlier finalized segments (`event.results[0 .. resultIndex - 1]`)**.

2. **Lifecycle race between `click`, `onstart`, `onerror`, and `onend` (`app-agent.js:252-308`):**
   - `state.speechListening` is only set to `true` inside `recognition.onstart`
     (after asynchronous microphone permission and cloud STT startup). Clicking
     `#webMicButton` twice during startup calls `recognition.start()` twice and
     throws `InvalidStateError`.
   - Clicking `#webMicButton` to stop calls `recognition.stop()` and immediately
     sets `setSpeechStatus(t("browserMic.stopped"))`, which gets overwritten by
     any trailing `onresult` or `onerror` event, or leaves `state.speechListening`
     stuck if the browser session hangs before `onend`.

3. **Browser cloud STT unreliability vs robot-side Whisper STT:**
   - `window.SpeechRecognition` / `webkitSpeechRecognition` depends on browser
     vendor cloud services (unavailable on Raspberry Pi Chromium, blocked or
     flaky on mobile browsers over self-signed LAN HTTPS, and immediately aborted
     with `no-speech` on a 1-second pause when `continuous = false`).
   - Meanwhile, the robot already has a working local `whisper.cpp` installation
     (`~/whisper.cpp/build/bin/whisper-cli` + `ggml-base.bin`) and an already-built
     push-to-talk backend handler (`usb_microphone` / `usb_microphone_stop` in
     `web_app.py:701-730` and `web_control.py:415-472`), which `#webMicButton`
     never uses as a fallback or primary push-to-talk capture mechanism!

### 4.2 Path B: Robot `#usbMicButton` ("VOICE INPUT") and Fusion HAT+ microphone pipeline

Comparing `pi5mic/src/pi5mic/core/voiceinput.py` (which works reliably in the
onboard tool) against `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/voice_input.py`,
`microphone.py`, and `config_import.py` reveals five confirmed defects in the
integrated agent voice pipeline:

1. **`import_pi5_configs()` drops `voiceinput` settings from `mic.json` (`config_import.py:216-256`):**
   - The user's `~/.config/pi5mic/mic.json` contains:
     - `"voiceinput": {"enabled": true, "silence_rms_threshold": 500, "silence_timeout_seconds": 3.0, "max_capture_seconds": 10.0}`
   - `import_pi5_configs()` only imports `audio.input_device`, `audio.sample_rate`,
     `audio.channels`, and `audio.duration_seconds`. It leaves `config.toml` at:
     - `voice_input.enabled = false`
     - `voice_input.silence_rms_threshold = 200`
     - `voice_input.silence_stop_seconds = 1.25`
     - `voice_input.max_command_seconds = 6.0`
   - Additionally, `configure_fusion_microphone()` (`fusion.py:111-120`) loads
     `mic.json` (or `{}` if missing) and writes only `audio.input_device` before
     `mic-tool` runs.

2. **Zero-tolerance `audio_overflow` handling kills the listener (`voice_input.py:362-375, 445-446`):**
   - In `pi5mic` (`pi5mic/src/pi5mic/core/voiceinput.py:644-676`), a PortAudio
     `overflowed` flag on `stream.read()` is logged, clears the frame buffer, and
     continues reading; only 3 consecutive overflows trigger stream recreation,
     and the loop never terminates.
   - In `VoiceInputController._listen_once()` (`voice_input.py:445-446`):

     ```python
     pcm, overflowed = await source.read()
     if overflowed:
         raise VoiceInputError("audio_overflow")
     ```

   - And in `ManagedVoiceAudioSource` (`microphone.py:505`), `block_frames` is
     hardcoded to `1280` samples. At the Fusion HAT+ I2S microphone's native
     `48000 Hz` sample rate, `1280` samples is only **26.67 ms** per read while
     `openWakeWord` inference (`detector.process`) runs on every 80 ms frame.
   - Any transient CPU spike (such as LLM HTTP streaming, display SPI rendering,
     or ONNX wake-word inference) that delays a 26.67 ms read causes PortAudio to
     set `overflowed = True`. `VoiceInputController` immediately closes the audio
     stream, enters `DEGRADED` for `2**failures` seconds (2s, then 4s), and after
     `retry_limit = 2` (3 occurrences), permanently transitions to `FAILED` and
     stops listening!

3. **Empty Whisper transcripts are treated as fatal `transcription_failed` errors (`microphone.py:200-201`, `voice_input.py:362-375, 505-517`):**
   - In `pi5mic` (`pi5mic/src/pi5mic/core/voiceinput.py:509-518`), when no speech
     is detected after the wake word, `NoSpeechDetectedError` is caught, `failures`
     is not incremented, and the listener immediately re-arms.
   - In `WhisperCppTranscriber.transcribe()` (`microphone.py:200-201`), an empty
     transcript (or Whisper noise tokens like `[BLANK_AUDIO]`) raises
     `RuntimeError("whisper.cpp returned an empty transcript")`, which
     `VoiceInputController._transcribe()` (`voice_input.py:516-517`) wraps into
     `VoiceInputError("transcription_failed")`.
   - In `VoiceInputController._run()` (`voice_input.py:362-375`), both
     `no_speech_detected` and `transcription_failed` increment `failures += 1`,
     put the listener into `DEGRADED` backoff, and after 3 occurrences **permanently
     shut down Always-On Voice Input (`VoiceInputState.FAILED`)**!

4. **VAD RMS calculation lacks DC-offset removal and mishandles post-wake silence (`voice_input.py:448-462, 590-594`):**
   - `_pcm_rms(frame)` (`voice_input.py:590-594`) computes raw RMS around `0`
     (`sqrt(mean(x^2))`) without subtracting the frame's DC mean. I2S MEMS
     microphones (`snd_rpi_googlevoicehat_soundcar`) commonly exhibit a small DC
     bias whose raw RMS exceeds the default `silence_rms_threshold = 200` (which
     is why `mic.json` was tuned to `500`).
   - Furthermore, in `voice_input.py:450-460`:

     ```python
     if self._vad_enabled:
         silent = _pcm_rms(frame) < self._silence_rms_threshold
         if silent:
             if speech_started:
                 silent_frames += 1
         else:
             speech_started = True
             silent_frames = 0
     ```

     - If DC offset + ambient noise keeps `_pcm_rms(frame) >= 200`, `speech_started`
       is set to `True` immediately on frame 1 and `silent_frames` stays `0`
       forever, forcing every command to record for the full `max_command_seconds`
       (`6.0s`) before Whisper even starts!
     - Conversely, if the user's voice is quieter than the threshold or if wake
       word false-triggers, `speech_started` remains `False` and `silent_frames`
       never increments, again hanging for the full `6.0s`.

5. **Event-loop blocking in `_PCMFrameAssembler.feed()` and PulseAudio `hw:0,0` contention (`voice_input.py:447, 554-577`):**
   - `_PCMFrameAssembler.feed(pcm)` converts 48,000 Hz samples to 16,000 Hz using
     a pure-Python `while` loop (`int(value).to_bytes(2, "little", signed=True)`)
     synchronously on the main `asyncio` event loop thread (`voice_input.py:447`),
     creating ~64,000 Python objects per second of audio and starving both WebSocket
     responsiveness and `source.read()`. (By contrast, `pi5mic` uses C-level
     `audioop.ratecv` in a dedicated thread.)
   - Finally, `/usr/bin/pulseaudio` (`PID 875`) is running on the host. Live
     testing confirmed that whenever any process queries ALSA `default` (`pcm.hat`),
     PulseAudio opens `/dev/snd/pcmC0D0c` (`hw:0,0` capture) and holds it for 5
     seconds (`module-suspend-on-idle`). While PulseAudio holds `hw:0,0`,
     PortAudio `resolve_supported_input_settings()` / `RawInputStream` on
     `snd_rpi_googlevoicehat_soundcar ... (hw:0,0)` fails with
     `Device unavailable [PaErrorCode -9985]`.

## Potential vulnerabilities and architectural risks

During the line-by-line audit across `ninjarobot_pi5_agent` and
`ninjarobot_pi5_ide`, five additional reliability and architectural risks were
identified:

1. **Repeated `pyngrok` paid traffic-policy warning on every service startup (`agent-service.log` lines 15, 74, 99, ..., 692):**
   - Every time `ninjarobot-agent` starts with `remote_access.enabled = true`,
     `pyngrok` logs:
     `failed to start tunnel: This policy includes paid traffic policy features that are not allowed on your current plan. ... ERR_NGROK_2263`
     before falling back to a basic tunnel. This adds 1–2 seconds of startup latency
     and clutters `agent-service.log` with false-positive error warnings.
2. **Continuous HTTP 405 reconnect loop from remote Tavily MCP (`agent-service.log` lines 10–11, 69–70, ..., 687–688):**
   - `mcp.client.streamable_http` attempts a `GET https://mcp.tavily.com/mcp` SSE
     stream which returns `HTTP/1.1 405 Method Not Allowed`, logging a reconnect
     message during every startup and tool session.
3. **Web Controller Resume disarms AI chat motion without clear UI feedback (`web_control.py:394-403`):**
   - When the user clicks **Resume** (`#resumeMovementButton`) in the Agent Web UI,
     `WebRobotController.resume()` calls `self._runtime.disarm_motion(self.chat_session(lease_id))`
     and then `self.activate(lease_id)` (which only arms `control_session(lease_id)`,
     not `chat_session(lease_id)`). If the user had armed **Arm AI motion** (`A`),
     clicking **Resume** (`Y`) silently disarms AI chat motion while leaving the user
     wondering why their next chat motion prompt asks to arm motion again.
4. **Conversation database bloat and prompt poisoning from persisted runtime notices (`runtime.py:711-728`):**
   - `_append_memory_notice()` writes transient runtime failure notices (such as
     `"Spoken output unavailable or stopped; the text reply is retained."`) as
     permanent `ASSISTANT` rows in `conversations.sqlite3`. Over time, these rows
     dominate the 24-message rolling window and degrade LLM tool-calling accuracy.
5. **Dual checkout paths in historical service logs (`agent-service.log` lines 86, 115):**
   - On 2 November (`14:31Z` and `14:33Z`), the service was started from a second
     checkout `/home/rogerchang/Ninja/NinjaRobotPi5` while sharing the same
     `~/.config/ninjarobot_pi5/` and `~/.local/state/ninjarobot_pi5/` directories.
     Although later runs used `/home/rogerchang/NinjaRobotPi5`, `service status`
     and `agent-service.log` should surface a clear warning if the active checkout
     differs from the configured or deployed workspace path.

## Phased implementation plan

> [!IMPORTANT]
> No runtime code or private configuration has been modified during this audit.
> Implementation must proceed only after explicit project-owner approval of this
> phased plan. Managed `pi5*` libraries (`pi5servo`, `pi5mic`, `pi5buzzer`,
> `pi5disp`, `pi5camera`, `pi5vl53l0x`) do **not** require modification for these
> fixes, preserving `docs/validation/immutable_driver_baseline.json`.

### Phase 1: Servo safety latch recovery, status visibility, and Fusion role mapping (Issue 1)

- **Objective:** Ensure Level 1 (`motion_latched`) stops can be cleanly diagnosed
  and resumed without being blocked by unrelated Level 2 device probes, distinguish
  historical latches from active electrical faults, surface latch status in
  `servo.status` and LLM `runtime_state`, and support Fusion HAT+ servo movement
  in both single-servo and behavior/gamepad paths.
- **Target files:**
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/safety.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/robot.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/servo.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config_import.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/runtime.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service_main.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/prompts.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/setup_wizard.py`
- **Implementation steps:**
  1. **Smart Level 1 vs Level 2 resume (`robot.py`, `runtime.py`):** In
     `RobotAssembly.resume_system()` (or `AgentRuntime.resume_system()`), check
     `safety_state.read()`. When `system_latched` is `False` and `motion_latched`
     is `True`, execute `resume_motion(confirmed=True)` (which checks live power
     via `ensure_power_ready()` and clears the motion latch) instead of failing on
     unrelated sensor health checks; when `system_latched` is `True`, continue
     requiring all enabled device health probes.
  2. **Historical vs active fault messaging (`safety.py`):** In
     `MotionController._check_stop_state()`, include `snapshot.updated_at` in the
     `MOTION_STOPPED` message and state clearly that motion is blocked by a
     **latched safety stop recorded at `<updated_at>`** that requires `/resume`
     (or clicking **Resume** in the web controller), rather than implying an
     undervoltage fault just occurred during the blocked call.
  3. **Expose safety latch in `servo.status` and `runtime_state` (`servo.py`, `robot.py`, `service_main.py`):**
     Include `motion_latched` and `stop_reason` in `servo.status` and include the
     non-sensitive `safety` snapshot (`motion_latched`, `system_latched`, `reason`,
     `updated_at`) in `runtime_state` (`service_main.py:216-247`) and
     `AgentRuntime._recovery_status()`.
  4. **Onboarding safety latch check (`setup_wizard.py`):** During `ninjarobot onboard`
     (before starting the agent service), check if `safety.json` has a stale
     `motion_latched` or `system_latched` state; if current power is healthy,
     prompt the operator to confirm clearing the historical latch.
  5. **Single-servo vs movement-behavior prompt & Fusion servo roles (`prompts.py`, `config_import.py`):**
     - Update `IDENTITY_PROMPT` (`prompts.py:88-89`) so that explicit single-servo
       angle requests (e.g., `"rotate PWM0 to 90 degrees"`) use `robot.servo.move`,
       while multi-stage expressions with movement or directional locomotion use
       `robot.behavior.execute_movement` (only when `servo_roles` are configured).
     - In `config_import.py:194-205`, when `is_fusion` is true and at least two
       `hat_pwm*` endpoints are calibrated (`hat_pwm0`, `hat_pwm1`) while no custom
       roles are set, map `left_motor = endpoints[0]` and `right_motor = endpoints[1]`
       (or allow optional role mapping in onboarding) so Gamepad D-pad and
       `move_forward` / `move_backward` presets work out of the box on 2-servo
       Fusion HAT+ builds.
- **Hardware risk level:** Medium (actuator policy and safety latch recovery; no
  automatic motion is triggered by clearing a latch).

### Phase 2: Embedded speaker LLM awareness, Piper TTS onboarding, and notice fix (Issue 2)

- **Objective:** Make the LLM aware of the automatic spoken-output pipeline,
  ensure Piper TTS and voice models are installed/configured when enabling speech
  output during onboarding, surface actionable TTS diagnostics, and fix the
  duplicate/unspaced failure notice in `AgentRuntime`.
- **Target files:**
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/prompts.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service_main.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/speech.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/runtime.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/setup_wizard.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bluetooth_setup.py`
  - `scripts/prepare_speech_voice.py`
- **Implementation steps:**
  1. **Add `speech_output` state to `runtime_state` and `IDENTITY_PROMPT` (`service_main.py`, `prompts.py`):**
     - Include `"speech_output": {"enabled": runtime.speech.enabled, "output_node": config.speech_output.output_node}`
       in `runtime_state` (`service_main.py:216-247`).
     - Add an explicit rule in `IDENTITY_PROMPT` (`prompts.py`):
       `"When runtime_state.speech_output.enabled is true, the runtime automatically synthesizes and speaks your text reply (or spoken_summary) through the configured speaker (such as the Fusion HAT+ embedded speaker or Bluetooth speaker) after you reply. Do not claim that you only have a buzzer when asked to speak out loud; simply write the spoken response in your reply."`
  2. **Integrate Piper TTS & voice model setup/check into speaker onboarding (`setup_wizard.py`, `bluetooth_setup.py`, `scripts/prepare_speech_voice.py`):**
     - During `_bluetooth_setup()` in `setup_wizard.py` (both for Fusion HAT+
       Embedded Speaker and Bluetooth Speaker), check whether `piper_python` and
       at least one voice model (`english_model` / `chinese_model`) exist on disk.
     - If missing, offer to run the pinned voice preparation helper
       (`scripts/prepare_speech_voice.py`) and automatically populate
       `speech_output.piper_python`, `speech_output.english_model`, and
       `speech_output.chinese_model` in `config.toml` when models are present in
       `~/.local/share/ninjarobot_pi5/voices/`.
     - If Piper or voice models are still not installed after onboarding, keep
       `speech_output.output_node = "alsa:sndrpigooglevoi"` saved, set
       `speech_output.enabled = false`, and print the exact command to install
       the voice model so the agent does not fail TTS on every single chat turn.
  3. **Actionable synthesis failure reason & fix duplicate notice (`speech.py`, `runtime.py`):**
     - In `SpeechService.speak()` (`speech.py:216-222`), preserve safe diagnostic
       codes (`speech_model_not_configured`, `piper_python_missing`) in the
       returned `reason` field.
     - In `AgentRuntime._append_memory_notice()` (`runtime.py:711-728`), stream
       `f"\n\n{notice}"` to `on_text_delta` (with proper spacing) and **do not**
       append a separate `MessageRole.ASSISTANT` row to `self.store` for transient
       speech-output notices (preventing conversation database duplication and
       LLM context poisoning).
- **Hardware risk level:** Low (audio output configuration and prompt/runtime
  state).

### Phase 3: Web power-off helper installation and authorization decoupling (Issue 3)

- **Objective:** Allow operators to install the privileged poweroff helper and
  enable the Web UI **Power off NinjaRobot** button during onboarding (or via CLI)
  without forcing systemd boot auto-start, and ensure active local controllers are
  properly authorized.
- **Target files:**
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/setup_wizard.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_cli.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_app.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-shared.js`
- **Implementation steps:**
  1. **Decouple web power-off helper installation from systemd boot auto-start (`deployment.py`, `agent_cli.py`):**
     - Add `DeploymentManager.install_poweroff(confirmed: bool)` (or allow
       `deployment enable --web-poweroff-only --confirm`) that installs only
       `/usr/libexec/ninjarobot-poweroff` (`0755 root:root`) and
       `/etc/sudoers.d/ninjarobot-agent-poweroff` (`0440 root:root`, validated via
       `visudo -cf`), and sets `deployment.web_poweroff_enabled = true` in
       `config.toml` without enabling `ninjarobot-agent.service` at boot.
  2. **Add optional Web Power-Off setup step to `ninjarobot onboard` (`setup_wizard.py`):**
     - After `_remote_setup()` in `setup_wizard.py`, add an explicit, previewable
       step asking whether the operator wants to enable the Web UI **Power off
       NinjaRobot** button (explaining that it installs `/usr/libexec/ninjarobot-poweroff`
       and `/etc/sudoers.d/ninjarobot-agent-poweroff` via `sudo`).
  3. **Align local controller pairing/authorization with `require_local_pairing` (`web_app.py`, `app-shared.js`):**
     - In `web_app.py:456-462, 866-872`, when `require_local_pairing` is `False`
       and the request is from a direct local client (not remote proxy), allow an
       authenticated active local lease holder to satisfy `poweroff_authorized`,
       or surface a clear `"Pair this browser via /pair to authorize power-off"`
       status string in `app-shared.js:436-447`.
- **Hardware risk level:** High / Power-risk (touches `/usr/libexec/ninjarobot-poweroff`
  and `/etc/sudoers.d/ninjarobot-agent-poweroff`; automated tests must stop at
  command construction, sudoers validation, and dry-run checks).

### Phase 4: Web microphone and robot Always-On Voice Input stabilization (Issue 4)

- **Objective:** Fix browser `#webMicButton` transcript truncation and state
  races, provide robot-side push-to-talk fallback when browser `SpeechRecognition`
  is unavailable, and make robot-side Always-On Voice Input (`#usbMicButton` /
  `VoiceInputController`) as resilient on the Fusion HAT+ I2S microphone as
  standalone `pi5mic`.
- **Target files:**
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-agent.js`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config_import.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/fusion.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/microphone.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/voice_input.py`
- **Implementation steps:**
  1. **Fix `#webMicButton` transcript accumulation, state machine, and robot push-to-talk fallback (`app-agent.js`):**
     - In `recognition.onresult` (`app-agent.js:262-269`), iterate from
       `let index = 0` to `event.results.length` so finalized segments are
       preserved across multi-phrase utterances.
     - Guard `recognition.start()` with a `starting` flag cleared on `onstart` /
       `onerror` / `onend` to prevent `InvalidStateError` on rapid taps.
     - When browser `SpeechRecognition` is unavailable (or fails with `network` /
       `not-allowed` / `service-not-allowed`), automatically fall back to the
       existing robot-side push-to-talk WebSocket command (`send("usb_microphone", { duration_seconds: 4, language: state.language })` / `send("usb_microphone_stop")`)
       so `#webMicButton` always works via the robot's microphone and local
       `whisper.cpp`!
  2. **Import `voiceinput` settings from `mic.json` and preserve existing keys in `configure_fusion_microphone` (`config_import.py`, `fusion.py`):**
     - Update `import_pi5_configs()` (`config_import.py:216-256`) to import
       `voiceinput.enabled`, `voiceinput.vad_rms_threshold` /
       `silence_rms_threshold`, `voiceinput.silence_timeout_seconds`,
       `voiceinput.max_capture_seconds`, `voiceinput.cooldown_seconds`, and
       `wakeword.threshold` / `vad_threshold` from `~/.config/pi5mic/mic.json` into
       `payload["voice_input"]`.
     - Ensure `configure_fusion_microphone()` (`fusion.py:82-125`) preserves all
       existing sections in `mic.json`.
  3. **Make `VoiceInputController` resilient to single overflows and empty transcripts (`voice_input.py`, `microphone.py`):**
     - Match `pi5mic`'s overflow resilience: in `VoiceInputController._listen_once()`,
       do not raise `VoiceInputError("audio_overflow")` on a single `overflowed`
       flag; tolerate transient overflows (`overflow_streak < 3`) by resetting the
       assembler when not capturing, or continuing capture without tearing down
       the PortAudio stream.
     - Scale `ManagedVoiceAudioSource` `block_frames` proportionally to sample rate
       (e.g., `max(1280, int(actual_rate * 0.08))` = `3840` frames at `48000 Hz`,
       or `80 ms` per read) to eliminate 26.67 ms read starvation.
     - In `WhisperCppTranscriber.transcribe()` and `VoiceInputController._transcribe()`,
       classify empty transcripts and Whisper non-speech markers (`[BLANK_AUDIO]`,
       `(blank audio)`) as `VoiceInputError("no_speech_detected")`, and in
       `VoiceInputController._run()`, re-arm immediately on `no_speech_detected`
       without incrementing fatal `failures` or entering `DEGRADED`/`FAILED`.
  4. **Remove DC offset in `_pcm_rms()`, add post-wake initial-speech timeout, and optimize resampling (`voice_input.py`):**
     - Update `_pcm_rms(pcm)` (`voice_input.py:590-594`) to subtract the frame's
       mean sample value (`mean = sum(samples) / len(samples)`) before computing
       RMS, eliminating I2S MEMS DC bias from triggering false speech detection.
     - If `speech_started` remains `False` for `silence_frames` after wake-word
       detection, stop capture early and re-arm instead of waiting the full
       `max_command_seconds`.
     - Offload `_PCMFrameAssembler.feed(pcm)` (or use `array("h")` / C-level buffer
       operations) so 48 kHz -> 16 kHz resampling does not block the `asyncio`
       event loop.
     - In `ManagedVoiceAudioSource.start()`, retry `RawInputStream` open briefly
       (e.g., up to 3 attempts over 1.5s) if PortAudio reports transient
       `Device unavailable [PaErrorCode -9985]` due to PulseAudio idle-suspend
       handoff, or prefer the shared ALSA capture PCM (`mic` / `hat`) when `hw:0,0`
       is busy.
- **Hardware risk level:** Low (microphone capture remains opt-in and bounded;
  no audio is retained on disk).

## Wiki and documentation impact decision

Per `AGENTS.md` and `.agents/skills/ninjarobot-knowledge/SKILL.md`:

- **Wiki environment note:** Running `python scripts/wiki.py search` during this
  audit returned `Wiki: Wiki environment missing. Run: python scripts/wiki.py setup`.
  In accordance with `AGENTS.md` ("Queries do not install dependencies or modify
  knowledge. If setup is missing, read local files and explain the limitation"),
  all wiki pages and raw sources were inspected directly from
  `ninjarobot_pi5_wiki/project-knowledge.json`, `ninjarobot_pi5_wiki/wiki/`, and
  `ninjarobot_pi5_wiki/raw/`.
- **Documentation updates required when implementing Phases 1–4:**
  1. `README.md` — document the Web Power-Off onboarding option, Piper TTS voice
     preparation during speaker onboarding, and Fusion HAT+ servo role defaults.
  2. New version of `InstallationGuide` in `ninjarobot_pi5_wiki/raw/` (superseding
     `InstallationGuide_261103.md`) — document Piper TTS setup during Fusion HAT+
     speaker onboarding, Web Power-Off helper installation, and clearing historical
     safety latches with `/resume`.
  3. New version of `DevelopmentGuide` in `ninjarobot_pi5_wiki/raw/` (superseding
     `DevelopmentGuide_261103.md`) — document the Level 1 (`motion.resume`) vs
     Level 2 (`system.resume`) recovery routing, `runtime_state.speech_output` and
     `runtime_state.safety` contracts, and Fusion HAT+ 48 kHz voice input buffering
     and DC-offset-free VAD.
  4. New version of `DevelopmentLog` in `ninjarobot_pi5_wiki/raw/` (superseding
     `DevelopmentLog_261103.md`) — record the 4 November 2026 post-integration
     audit and phase validation results.

## Validation gates and Raspberry Pi test checklists

After each implementation phase, the following automated gates must pass before
proceeding:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python scripts/verify_workspace_driver_sources.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
git diff --check
```

### Manual Raspberry Pi validation checklists (post-implementation)

1. **Safe smoke and latch recovery check (no actuator motion):**
   - Inspect `~/.local/state/ninjarobot_pi5/safety.json` and run `/resume` in
     `ninjarobot-agent chat` (or click **Resume** in the Web UI).
   - **Expected result:** `motion_latched` transitions to `false` without being
     blocked by unrelated sensors; `servo.status` reports `motion_latched: false`.
2. **Device communication check (embedded speaker & voice input, consent required):**
   - Run `uv run --frozen python scripts/prepare_speech_voice.py` (or the
     onboarding speaker step) to configure Piper TTS and a voice model.
   - Start the agent, enable `/speech on`, and ask: `"Please introduce yourself out loud."`
   - **Expected result:** The agent replies normally without claiming it only has
     a buzzer, and the reply is spoken clearly through the Fusion HAT+ embedded
     speaker.
   - Enable **VOICE INPUT** (`#usbMicButton`) in the Web UI, say `"Hey Ninja, what time is it?"`,
     and also test **WEB MICROPHONE** (`#webMicButton`).
   - **Expected result:** Wake word triggers `recording` -> `transcribing` ->
     `dispatching` without `audio_overflow` or premature `FAILED` state;
     multi-phrase browser speech is retained in `#chatInput`.
3. **Actuator-moving check (opt-in; raise wheels and keep power switch accessible):**
   - Arm AI motion (`A` / `/arm`), then ask: `"Rotate hat_pwm0 servo to 90 degrees."`
   - Test Gamepad D-pad forward/backward buttons.
   - **Expected result:** `hat_pwm0` rotates smoothly to 90 degrees and de-energizes
     cleanly; Gamepad D-pad moves `left_motor` (`hat_pwm0`) and `right_motor`
     (`hat_pwm1`) without unmapped-role errors.
4. **Power-risk check (manual operator test only):**
   - After installing the poweroff helper (`ninjarobot-agent deployment install-poweroff --confirm`
     or via onboarding), open the Web UI Robot Menu.
   - **Expected result:** **Power off NinjaRobot** (`#powerOffButton`) is enabled
     for the active paired controller and displays `"Power-off is ready for the active controller."`
