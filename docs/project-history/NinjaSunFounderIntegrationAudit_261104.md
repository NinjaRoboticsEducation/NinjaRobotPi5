# NinjaRobotPi5 SunFounder Fusion HAT+ post-integration system audit and implementation plan

This document records the comprehensive system audit and refined implementation
plan conducted on 4 November 2026 following the integration of the SunFounder
Fusion HAT+ kernel driver (`1.1.0-ninja1`), ALSA sound card (`sndrpigooglevoi`),
and staged onboarding workflow documented in
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
  `hat_pwm1` with backend `"fusion_hat_plus"`, imported into `config.toml` with
  `motion_enabled = true` and `group_motion_enabled = true`.

All four reported issues stem from **software state, configuration-import gaps,
prompt/tool-contract omissions, and audio/speech lifecycle defects** between
`ninjarobot_pi5_agent` and `ninjarobot_pi5_ide`.

| Issue | Confirmed primary root cause | Confirmed compounding causes |
| --- | --- | --- |
| **1. Servo blocked by undervoltage** | A persistent Level 1 motion latch (`"motion_latched": true, "reason": "undervoltage"`) recorded on `2026-11-02T03:09:04Z` in `~/.local/state/ninjarobot_pi5/safety.json` remains active across service restarts and re-onboarding. | 1) User's `/resume` attempt (`action_ledger` row 11) failed because `AgentRuntime.resume_system()` always invokes `robot.system.resume` (Level 2 recovery requiring all 6 devices, which failed on `microphone (reported unavailable)`) instead of `robot.motion.resume`.<br>2) `MicrophoneDevice.start()` latches `_start_attempted = True` on first failure and never re-probes during `_microphone_health()` unless `suspend()` is called first, nor does it acquire `manual_access()` to pause `VoiceInputController`.<br>3) `MotionController._check_stop_state()` reports a historical latch in the present tense without `snapshot.updated_at`.<br>4) `ServoDevice.status()`, `AgentRuntime._recovery_status()`, and LLM `runtime_state` omit `motion_latched`.<br>5) `IDENTITY_PROMPT` forces all movement requests onto `robot.behavior.execute_movement` (requiring `behaviors.servo_roles`), which is `{}` on Fusion HAT+ because positional servos must not silently become wheels (`config_import.py:222`). |
| **2. Embedded speaker refusal & TTS failure** | **Two independent faults:**<br>**2A (LLM refusal):** `IDENTITY_PROMPT` and `runtime_state` never inform the LLM that text replies are automatically spoken via the post-reply `SpeechService` pipeline, while exposed tools only list `buzzer` (`tone`/`melody`).<br>**2B (Silent TTS failure):** `configure_sunfounder_i2s_speaker()` (`hardware_setup.py:436-463`) sets `speech_output.enabled = true` in `config.toml` after playing a synthetic sine chime (`play_sunfounder_speaker_test_tone`), even though the isolated Piper environment (`~/.local/share/ninjarobot_pi5/speech/bin/python`, `requirements/local-speech.txt`) and voice model (`english_model = ""`) were never installed or configured. | 1) `SpeechService.speak()` (`speech.py:223-229`) catches `ValueError("speech_model_not_configured")` and collapses it into a generic `"speech_unavailable_or_interrupted; text retained"` reason.<br>2) `AgentRuntime._append_memory_notice()` (`runtime.py:1485-1501`) persists a standalone `MessageRole.ASSISTANT` row (`metadata={"workflow": "memory-notice"}`) into `conversations.sqlite3` on every failed TTS turn, and `AgentLoop` (`agent_loop.py:299-305`) loads those rows unfiltered into the LLM prompt context, conditioning the model to repeat that speech output is unavailable. |
| **3. Web Power Off button disabled** | `app-shared.js:427-435` disables `#powerOffButton` unless four gates pass (`poweroffEnabled && poweroffReady && poweroffAuthorized && leaseId`). Currently `deployment.web_poweroff_enabled = false` in `config.toml` and `/usr/libexec/ninjarobot-poweroff` + `/etc/sudoers.d/ninjarobot-agent-poweroff` are not installed (`poweroffReady = false`). | 1) `ninjarobot onboard` (`setup_wizard.py`) has no step to install the privileged poweroff helper or enable web power-off.<br>2) `DeploymentManager.enable()` (`deployment.py:314-342`) couples `web_poweroff_enabled = true` to `sudo systemctl enable ninjarobot-agent.service` (`auto_start_enabled = true`), preventing interactive users from enabling web power-off without boot auto-start.<br>3) When `require_local_pairing` is `False`, local LAN controllers can acquire a lease without `/pair`, leaving `paired_connection` (`poweroff_authorized`) `False`. |
| **4. Web-based voice input unstable** | **Both web voice paths have confirmed defects:**<br>**4A (`#webMicButton` Browser Speech API in `app-agent.js:240-309`):** `recognition.continuous = false` stops on the first pause, and a subsequent utterance overwrites `elements.chatInput.value = transcript.trim()`, erasing earlier text; `state.recognitionActive` is set only in `onstart` (race on rapid clicks); browser cloud STT is unsupported/blocked on Chromium and self-signed LAN HTTPS and never falls back to the existing `usb_microphone` robot Whisper endpoint.<br>**4B (`#usbMicButton` Robot Voice Input in `voice_input.py` & `microphone.py`):** `VoiceInputController` aborts on any single PortAudio `overflowed` flag (`VoiceInputError("audio_overflow")`) or empty Whisper transcript (`VoiceInputError("transcription_failed")`) and permanently enters `FAILED` after `retry_limit = 2` (3 occurrences). | 1) `import_pi5_configs()` (`config_import.py:283-297`) omits `voiceinput.enabled` (`true` in `mic.json`) and `stt.whisper_cpp` paths/threads.<br>2) `#usbMicButton` click handler (`app-agent.js:230-235`) has `.catch(() => {})`, silently swallowing startup failures.<br>3) `_pcm_rms()` (`voice_input.py:589-593`) does not remove DC offset on the I2S MEMS mic (`sndrpigooglevoi`), and post-wake silence when `speech_started` stays `False` hangs for the full `max_command_seconds` (`15.0s`).<br>4) `_PCMFrameAssembler.feed()` (`voice_input.py:553-576`) resamples 48 kHz -> 16 kHz sample-by-sample in pure Python on the asyncio event loop thread.<br>5) PulseAudio (`PID 875`) wakes on default ALSA queries and holds `hw:0,0` for 5s, causing `PaErrorCode -9985 (Device unavailable)`. |

## Issue 1 root cause analysis: servo control blocked by undervoltage

### 1.1 Confirmed evidence from runtime state and SQLite ledgers

1. **Persistent safety state file (`~/.local/state/ninjarobot_pi5/safety.json`):**
   Inspection of `safety.json` (last modified `2026-11-02 12:09:04 +0900`) shows:

   ```json
   {
     "fault_detail": null,
     "motion_latched": true,
     "reason": "undervoltage",
     "schema_version": 1,
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

1. **Pre-move latch gate (`ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/safety.py:404-419`):**
   Before touching hardware or checking live voltage, `MotionController.move_endpoint()`
   enters `_guarded_motion()` (`safety.py:441-448`), which calls `self._check_stop_state()`:

   ```python
   snapshot = self._state.read()
   system_stopped = snapshot.system_latched or self._system_stopped()
   if system_stopped or snapshot.motion_latched:
       guidance = stop_guidance(
           snapshot.reason or "operator_stop", fault_detail=snapshot.fault_detail
       )
       raise IDEError(
           ErrorDetails(
               code="SYSTEM_STOPPED" if system_stopped else "MOTION_STOPPED",
               message=f"{guidance.cause} Recovery: {guidance.recovery_instruction}",
               ...
           )
       )
   ```

   Because `stop_guidance("undervoltage")` (`safety.py:66-92`) returns the static
   string `"The Raspberry Pi reported undervoltage while the robot was moving."`
   without including `snapshot.updated_at` (`2026-11-02T03:09:04.813631Z`),
   both the LLM and the operator are told that an electrical fault is occurring
   right now rather than that a persistent safety latch from `2026-11-02` is
   waiting for `/resume`.

2. **Resume level mismatch (`runtime.py:1935-1960`, `web_control.py:416-426`, `robot.py:621-655`):**
   - `ninjarobot_pi5_ide` defines two distinct recovery capabilities in
     `integrated.py:450-498` (documented in
     `ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-03-04/DevelopmentGuide.md:1410-1425`):
     - `motion.resume` (`RobotAssembly.resume_motion`, `robot.py:621-628`):
       verifies live power readiness (`ensure_power_ready()`) and clears a
       **Level 1 (`motion_latched`)** stop.
     - `system.resume` (`RobotAssembly.resume_system`, `robot.py:630-655`):
       verifies live power readiness AND runs health probes across all enabled
       devices (`display`, `buzzer`, `servo`, `distance`, `camera`, `microphone`)
       to clear a **Level 2 (`system_latched`)** stop.
   - However, `AgentRuntime.resume_system()` (`runtime.py:1935-1960`), CLI `/resume`
     (`agent_cli.py:1189-1218`), and Web UI `Resume` (`web_control.py:416-426`)
     **always invoke `robot.system.resume`**, never `robot.motion.resume`.
   - When only `motion_latched` is `True` (`system_latched` is `False`), forcing
     `system.resume` causes unrelated non-motion peripherals (such as an
     unconfigured or busy microphone) to block motion recovery.

3. **Sticky `_start_attempted` in `MicrophoneDevice.start()` and missing `manual_access()` in `_microphone_health()` (`microphone.py:704-740`, `robot.py:929-931`):**
   - Even when a genuine Level 2 `system.resume` runs, `RobotAssembly._microphone_health()`
     (`robot.py:929-931`) simply calls `await self.microphone.start()` followed
     by `await self.microphone.health() is ResourceHealth.READY`.
   - In `MicrophoneDevice.start()` (`microphone.py:708-709`), `self._start_attempted`
     is set to `True` before `_inspect_backend()` runs and is **never reset on
     exception** (`microphone.py:734-740`). If `MicrophoneDevice.start()` fails
     once at service boot (for example, because PulseAudio or `VoiceInputController`
     briefly held `hw:0,0`), every subsequent `await self.microphone.start()` is
     a no-op and `health()` permanently returns `ResourceHealth.UNAVAILABLE`
     unless `await self.microphone.suspend()` is called first.
   - Furthermore, `_microphone_health()` does not acquire
     `async with self.microphone.manual_access():`, so if Always-On Voice Input
     is active when `system.resume` runs, `_inspect_backend()` collides with
     `ManagedVoiceAudioSource` on `hw:0,0`.

4. **Hidden latch state in `servo.status`, `startup_status`, and LLM `runtime_state`:**
   - `ServoDevice.status()` (`servo.py:240-252`) returns `endpoints`, `calibrated`,
     `motion_enabled`, `group_motion_enabled`, `driver_available`, and `simulated`,
     but **omits `motion_latched` and `stop_reason`**. In `conversations.sqlite3`
     (row 58, `2026-11-03 14:11:17Z`), the LLM called `robot.servo.status`, saw
     `motion_enabled: true` and `calibrated: true`, and had no idea motion was
     latched until `robot.servo.move` failed.
   - `AgentRuntime._recovery_status()` (`runtime.py:881-897`) sets
     `"required": system_latched`, ignoring `motion_latched` even though
     `startup_status()` (`runtime.py:857-858`) sets
     `operational_state = "motion_latched"`.
   - `service_main.py:250-281` (`runtime_state`) omits `safety` (`motion_latched`,
     `system_latched`, `reason`, `updated_at`) and configured `servo_roles` /
     `servo_endpoints`.

5. **Compounding defect: `IDENTITY_PROMPT` forces `robot.behavior.execute_movement` while `behaviors.servo_roles` is `{}` on Fusion HAT+ (`prompts.py:88-96`, `config_import.py:219-228`):**
   - Per `InstallationGuide.md:190-191` ("One calibrated Fusion servo is
     sufficient. Assign wheel roles only to actual wheel servos; positional
     servos must not silently become wheels"), `config_import.py:222`
     intentionally includes `not is_fusion` so calibrated `hat_pwm*` ports are
     not silently assigned to `left_motor` and `right_motor`. As a result,
     `config.toml` has `[behaviors.servo_roles]` empty (`{}`).
   - However, `IDENTITY_PROMPT` (`prompts.py:88-89`) instructs the LLM:
     `"Any request containing servo or physical movement must use robot.behavior.execute_movement, never robot.behavior.execute_expression."`
   - When the LLM obeys this rule (`action_ledger` rows 2 and 27),
     `robot.behavior.execute_movement` fails with
     `BEHAVIOR_DRAFT_INVALID: movement preset references unconfigured logical roles: left_motor, right_motor`.
   - Meanwhile, the operator has no onboarding prompt in `setup_wizard.py` to
     explicitly assign `left_motor` and `right_motor` when `hat_pwm0` and
     `hat_pwm1` *are* used as wheels, causing Web Gamepad D-pad commands
     (`action_ledger` rows 22, 25, 43, 46, 49, 52) to fail with
     `MOTION_STOPPED: movement contains unmapped servo roles: left_motor, right_motor`.

## Issue 2 root cause analysis: embedded speaker refusal and TTS failure

### 2.1 Confirmed evidence from `config.toml` and `conversations.sqlite3`

1. **Configuration state (`~/.config/ninjarobot_pi5/config.toml`):**

   ```toml
   [speech_output]
   enabled = true
   language = "en"
   piper_python = "~/.local/share/ninjarobot_pi5/speech/bin/python"
   english_model = ""
   chinese_model = ""
   output_node = "alsa:sndrpigooglevoi"
   volume = 0.35
   max_characters = 500
   synthesis_timeout_seconds = 30.0
   playback_timeout_seconds = 60.0
   bluetooth_lead_in_seconds = 0.5
   fusion_speaker = true
   ```

2. **Filesystem verification:**
   - `~/.local/share/ninjarobot_pi5/speech/` **does not exist**.
   - `~/.local/share/ninjarobot_pi5/voices/` **does not exist**.
   - Neither `english_model` nor `chinese_model` is configured in `config.toml`.

3. **Conversation transcript evidence (`~/.local/share/ninjarobot_pi5/conversations.sqlite3`):**
   Across turns in `conversations.sqlite3` (rows 4–9, 17–22, 27–32, 34–41,
   43–45, 51–53, 55, 62, 65), two symptoms appear simultaneously:
   - When asked `"can you speak now"` (row 33), `"now try to speak out loud"`
     (row 36), or `"Can you speak out lout with embeded speaker?"` (row 50), the
     LLM replies:

     > `"I truly wish I could, Master, but I do not have an embedded speaker capable of speech or playing audio files. My only way to make sound is through a small buzzer, which can only play simple tones and melodies."`

   - Immediately after the LLM generates its text reply, `AgentRuntime.chat()`
     attempts automatic TTS synthesis, fails, streams
     `\n\nSpoken output unavailable or stopped; the text reply is retained.` onto
     the reply, **and** inserts a separate `assistant` message row containing
     `Spoken output unavailable or stopped; the text reply is retained.` into
     `conversations.sqlite3`.

### 2.2 Code trace across layers

1. **Root Cause 2A — Why the LLM claims it only has a buzzer (`prompts.py:32-118`, `service_main.py:250-281`):**
   - Spoken reply synthesis in NinjaRobot is a **post-reply runtime pipeline hook**
     in `AgentRuntime.chat()` (`runtime.py:547-555`): after the LLM finishes its
     turn (`reply = await self._chat_with_task(...)`), `AgentRuntime` calls
     `await self.speech.speak(reply.spoken_summary or reply.text)`.
   - There is **no `robot.speaker.*` or `robot.speech.*` tool** in the LLM tool
     registry; the only sound-producing tools exposed to the model are
     `robot.buzzer.play_tone` and `robot.behavior.execute_expression` (which
     supports `tone` and `melody` on the buzzer).
   - Neither `IDENTITY_PROMPT` (`prompts.py:32-118`) nor `runtime_state`
     (`service_main.py:250-281`) informs the LLM that:
     1. The robot has an audio output pipeline (`speech_output`) that
        automatically synthesizes and speaks the assistant's text replies through
        the configured speaker (`alsa:sndrpigooglevoi` on Fusion HAT+ or
        Bluetooth speaker) whenever `/speech on` (`speech_output.enabled = true`)
        is active; and
     2. To speak out loud through the embedded speaker, the assistant simply
        writes the desired spoken words in its normal text reply (and optional
        `spoken_summary`) rather than looking for a speaker tool.

2. **Root Cause 2B — Why onboarding speaker setup succeeded while runtime TTS failed (`setup_wizard.py:594-639`, `hardware_setup.py:412-462`, `speech.py:29-70`):**
   - During `ninjarobot onboard`, the Fusion HAT+ **"Embedded Speaker Initialization"**
     step (`setup_wizard.py:594-639`) calls:
     1. `configure_sunfounder_i2s_speaker(config_path)`
        (`ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/hardware_setup.py:435-462`),
        which unconditionally sets `payload["speech_output"]["enabled"] = True`,
        `payload["speech_output"]["output_node"] = node` (`"alsa:sndrpigooglevoi"`),
        and `payload["speech_output"]["fusion_speaker"] = True`.
     2. `play_sunfounder_speaker_test_tone(node)`
        (`ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/hardware_setup.py:412-432`),
        which generates a pure 440/660 Hz sine-wave WAV in Python
        (`synthesize_test_chime_wav()`) and plays it via
        `aplay -q -D plughw:CARD=sndrpigooglevoi,DEV=0 -`.
   - As noted in `InstallationGuide.md:214-215`, a successful onboarding tone
     verifies ALSA playback only, not Piper TTS engine or voice model availability.
     Installing Piper TTS requires creating the isolated Python 3.11 venv at
     `~/.local/share/ninjarobot_pi5/speech` (`requirements/local-speech.txt`),
     downloading the 114 MB English voice via `scripts/prepare_speech_voice.py --apply`,
     and setting `english_model = "~/.local/share/ninjarobot_pi5/voices/en/en_US-ljspeech-high.onnx"`
     (`InstallationGuide.md:830-850, 1154-1160`).
   - Because `configure_sunfounder_i2s_speaker()` sets `speech_output.enabled = True`
     even when `english_model` is `""` and `~/.local/share/ninjarobot_pi5/speech/bin/python`
     is absent, every subsequent chat reply invokes `LocalSynthesizer._paths()`
     (`speech.py:33-52`):

     ```python
     model = self.config.english_model if language == "en" else self.config.chinese_model
     if not model:
         raise ValueError("speech_model_not_configured")
     ```

   - `SpeechService.speak()` (`speech.py:223-229`) catches `Exception` and hides
     the specific `ValueError` code (`speech_model_not_configured`,
     `piper_not_installed`, `speech_model_missing`) behind the generic string
     `"speech_unavailable_or_interrupted; text retained"`.

3. **Root Cause 2C — Conversation history pollution from persisted `memory-notice` rows (`runtime.py:547-555, 1485-1501`, `agent_loop.py:299-305`):**
   - In `AgentRuntime.chat()` (`runtime.py:547-555`):

     ```python
     if self.speech is not None and self.speech.enabled:
         spoken = await self.speech.speak(reply.spoken_summary or reply.text)
         if spoken.get("status") not in {"played", "simulated", "disabled"}:
             notice = "Spoken output unavailable or stopped; the text reply is retained."
             await self._append_memory_notice(
                 session_id, notice, on_text_delta=on_text_delta
             )
             reply = reply.model_copy(update={"text": reply.text + "\n\n" + notice})
     ```

   - And in `_append_memory_notice()` (`runtime.py:1485-1501`):

     ```python
     await self.store.append_message(
         session_id,
         ModelMessage(role=MessageRole.ASSISTANT, content=notice),
         message_id=f"message-{uuid.uuid4().hex}",
         user_id=self._active_users.get(session_id),
         metadata={"workflow": "memory-notice"},
     )
     if on_text_delta is not None:
         await on_text_delta("\n\n" + notice)
     ```

   - When `AgentLoop.chat()` (`agent_loop.py:299-305`) loads conversation history
     on the next turn:

     ```python
     history = tuple(
         stored.message
         for stored in await self._store.messages(
             session_id,
             user_id=self._active_user(session_id),
         )
     )
     ```

     it includes every `metadata={"workflow": "memory-notice"}` row as a standalone
     `MessageRole.ASSISTANT` turn in the LLM prompt context! Over repeated turns,
     the LLM sees its own history filled with assistant messages saying
     `"Spoken output unavailable or stopped; the text reply is retained."`,
     reinforcing its refusal to speak.

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
  if (elements.powerAvailability) {
    elements.powerAvailability.textContent =
      !state.poweroffEnabled ? t("power.disabled") :
      !state.poweroffReady ? t("power.helperUnavailable") :
      (!state.poweroffAuthorized || !state.leaseId) ? t("power.pairingRequired") : t("power.enabled");
  }
}
```

The four gates are populated by `/api/status` (`web_app.py:424-441`) and WebSocket
`lease` / `status` frames (`web_app.py:554-580`):

| Gate in `app-shared.js` | Backend source (`web_app.py` / `shutdown.py`) | Current value on host | Why |
| --- | --- | --- | --- |
| `state.poweroffEnabled` | `config.deployment.web_poweroff_enabled` (`service_main.py:246, 401`) | `false` | `~/.config/ninjarobot_pi5/config.toml` has `[deployment] web_poweroff_enabled = false`. |
| `state.poweroffReady` | `PoweroffCoordinator._probe_poweroff_helper()` (`shutdown.py:64-76, 202-260`) | `false` | `/usr/libexec/ninjarobot-poweroff` and `/etc/sudoers.d/ninjarobot-agent-poweroff` are not installed on this Raspberry Pi. |
| `state.poweroffAuthorized` | `paired_connection` (`web_app.py:446, 465, 577`) | `true` only after `/pair` | Requires a paired browser session cookie (`ninjarobot_web_session`). |
| `state.leaseId` | Active WebSocket controller lease | `true` when connected | Assigned on WebSocket controller connection. |

### 3.2 Why deployment artifacts and `web_poweroff_enabled` were never configured

1. **Onboarding (`setup_wizard.py`) omits power-off / deployment helper setup:**
   `run_setup_wizard()` (`setup_wizard.py:215-392`) walks the user through
   hardware profile selection, mandatory hardware, optional speaker/microphone,
   config import, AI model provider, MCP servers, and remote access
   (`_remote_setup`), then offers to start `ninjarobot-agent service start --real`.
   It never offers to install `/usr/libexec/ninjarobot-poweroff` +
   `/etc/sudoers.d/ninjarobot-agent-poweroff` or enable `web_poweroff_enabled`.

2. **`DeploymentManager` (`deployment.py:314-342, 554-561`) couples `web_poweroff_enabled` to systemd boot auto-start:**
   - Currently, the only CLI path that installs `/usr/libexec/ninjarobot-poweroff`
     and sets `web_poweroff_enabled = true` is `ninjarobot-agent deployment setup --confirm`
     (or `deployment install --confirm` followed by `deployment enable --confirm`).
   - Note that on `fusion_hat_plus`, `DeploymentManager._requires_full_poweroff()`
     (`deployment.py:495-499`) and `PoweroffCoordinator` (`service_main.py:408`)
     already set `require_full_poweroff = False` (orderly OS shutdown without
     requiring Raspberry Pi EEPROM `POWER_OFF_ON_HALT=1` changes).
   - However, `DeploymentManager.enable()` (`deployment.py:314-342`) unconditionally
     runs `sudo systemctl enable ninjarobot-agent.service` and sets
     `auto_start_enabled = True` alongside `web_poweroff_enabled = True`.
   - Operators who launch the agent manually (`ninjarobot-agent service start --real`)
     without wanting boot-time systemd auto-start have no supported command to
     install only the root-owned poweroff helper + narrow sudoers rule and set
     `web_poweroff_enabled = True`.

3. **Local LAN un-paired connection authorization edge case (`service_main.py:239-243, 421`, `web_app.py:354, 465-475, 577`):**
   - In `web_app.py:577`, `poweroff_authorized` is set to `paired_connection`.
   - When `onboarding.enabled = false`, `remote_access.enabled = false`, and
     `deployment.auto_start_enabled = false`, `_effective_onboarding_enabled()`
     (`service_main.py:66-73`) returns `False`, which sets
     `require_local_pairing = False` (`service_main.py:421`).
   - When `require_local_pairing` is `False`, a local LAN browser can open
     `https://<pi-ip>:8443/` and acquire the active WebSocket controller lease
     without visiting `/pair` first (`web_app.py:354, 474`), leaving
     `paired_connection = False` (`poweroff_authorized = False`).

## Issue 4 root cause analysis: web-based voice input instability

The web interface (`ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/agent.html:45-55`)
exposes two voice input controls in `.audio-controls`:

1. **`#webMicButton` ("WEB MICROPHONE / Fill the message box")** — browser-side
   speech recognition (`window.SpeechRecognition || window.webkitSpeechRecognition`)
   configured in `app-agent.js:240-309`.
2. **`#usbMicButton` ("VOICE INPUT / Always-on Ninja: Off")** — robot-side
   always-on wake-word + command capture (`voice_enable` / `voice_disable` ->
   `VoiceInputService` -> `VoiceInputController` -> `ManagedVoiceAudioSource` +
   `WhisperCppTranscriber`).
3. Additionally, `web_app.py:705-718` (`usb_microphone` / `usb_microphone_stop`)
   and `WebRobotController.transcribe()` (`web_control.py:441-486`) implement a
   robot-side push-to-talk transcription endpoint (`robot.microphone.transcribe`),
   which is currently **unused by `agent.html` and `app-agent.js`**.

Both active paths (`#webMicButton` and `#usbMicButton`) contain confirmed defects
that cause intermittent recording and recognition failures.

### 4.1 Path A: Browser `#webMicButton` (`app-agent.js:240-309`)

Inspection of `configureSpeechRecognition()` in
`ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-agent.js:240-309`
shows:

```javascript
export function configureSpeechRecognition() {
  if (!elements.webMic) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    elements.webMic.disabled = true;
    const small = elements.webMic.querySelector("small");
    if (small) small.textContent = t("speech.notSupported");
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.onstart = () => {
    state.recognitionActive = true;
    ...
  };
  recognition.onresult = (event) => {
    let transcript = "";
    for (let index = 0; index < event.results.length; index += 1) {
      transcript += event.results[index][0].transcript;
    }
    elements.chatInput.value = transcript.trim();
    if (event.results[event.results.length - 1].isFinal && transcript.trim()) {
      elements.chatInput.focus();
      toast(t("speech.added"));
    }
  };
```

This implementation has three confirmed issues:

1. **Browser `SpeechRecognition` unreliability and lack of robot-microphone push-to-talk fallback (`app-agent.js:242-248, 272-284`):**
   - `window.SpeechRecognition` / `webkitSpeechRecognition` relies on browser
     vendor cloud speech services. On Raspberry Pi Chromium ( lacks Google API
     keys), Firefox, or mobile browsers connected over LAN to a self-signed TLS
     certificate (`https://<pi-ip>:8443`), `SpeechRecognition` is either
     undefined (disabling `#webMicButton` completely at line 244) or fails
     intermittently with `network`, `service-not-allowed`, `not-allowed`, or
     `no-speech`.
   - Meanwhile, the backend already provides a complete, privacy-gated
     push-to-talk handler (`usb_microphone` and `usb_microphone_stop` in
     `web_app.py:705-718` -> `WebRobotController.transcribe()` in
     `web_control.py:441-486` -> `MicrophoneTranscribeAdapter` in
     `microphone.py:1159-1292`) that records from the robot's microphone and
     transcribes locally with `whisper.cpp`, but `app-agent.js` never falls back
     to it!
2. **Single-utterance cutoff (`continuous = false`) and input overwrite (`app-agent.js:251, 266`):**
   - Because `recognition.continuous = false`, any brief pause ends the browser
     recognition session. If the user clicks `#webMicButton` again to dictate a
     second sentence (or had already typed text in `#chatInput`),
     `elements.chatInput.value = transcript.trim()` overwrites the entire input
     box instead of appending to the existing prefix saved when recording started.
3. **Startup race on rapid clicks (`app-agent.js:253, 295-308`):**
   - `state.recognitionActive` is only set to `true` inside `recognition.onstart`
     (after asynchronous mic permission and cloud handshake). Clicking
     `#webMicButton` twice before `onstart` fires calls `recognition.start()`
     twice and throws `InvalidStateError`.

### 4.2 Path B: Robot `#usbMicButton` ("VOICE INPUT") and Fusion HAT+ microphone pipeline

Comparing `pi5mic/src/pi5mic/core/voiceinput.py` (which works reliably in the
onboard tool) against `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/voice_input.py`,
`microphone.py`, `config_import.py`, and `app-agent.js` reveals six confirmed
defects in the integrated agent voice pipeline:

1. **`import_pi5_configs()` omits `voiceinput.enabled` and `stt.whisper_cpp` from `mic.json` (`config_import.py:255-297`, `integrated.py:795-797`):**
   - Inspection of `~/.config/pi5mic/mic.json` shows:
     - `"audio": {"input_device": "snd_rpi_googlevoicehat_soundcar: ...", "sample_rate": 48000, "channels": 1}`
     - `"wakeword": {"enabled": true, "threshold": 0.5, "vad_threshold": 0.3}`
     - `"voiceinput": {"enabled": true, "silence_timeout_seconds": 1.25, "max_capture_seconds": 15.0, "cooldown_seconds": 1.0, "vad_rms_threshold": 200.0}`
     - `"stt": {"selected": "whisper_cpp", "whisper_cpp": {"command": "/home/rogerchang/whisper.cpp/build/bin/whisper-cli", "model_path": "/home/rogerchang/whisper.cpp/models/ggml-base.bin", "language": "auto", "threads": 2, "timeout_seconds": 120}}`
   - While `import_pi5_configs()` (`config_import.py:283-297`) imports
     `max_capture_seconds`, `silence_timeout_seconds`, `cooldown_seconds`, and
     `vad_rms_threshold`, it **does not import `voiceinput.enabled`** (leaving
     `voice_input.enabled = false` in `config.toml` after onboarding) and **does
     not import `stt.whisper_cpp`** (`command`, `model_path`, `threads`,
     `timeout_seconds`).

2. **Silent error swallowing on `#usbMicButton` in `app-agent.js:229-236`:**
   - In `app-agent.js:230-235`:

     ```javascript
     elements.voiceInput.addEventListener("click", () => {
       const request = state.voiceEnabled ? "voice_disable" : "voice_enable";
       send(request)
         .then((data) => updateVoiceInput(data))
         .catch(() => {});
     });
     ```

   - And in `app-agent.js:211`, `const enabled = status.enabled === true && status.state !== "disabled";`
     treats `status.state === "failed"` (when `status.enabled` is still `true` in
     `VoiceInputController._run()`, `voice_input.py:345-391`) as `enabled = true`!
     When `VoiceInputController` transitions to `FAILED`, the button stays
     highlighted as `VOICE INPUT ON` (`Always-on Ninja: failed`), and clicking it
     sends `voice_disable` instead of `voice_enable`, confusing the user.

3. **Zero-tolerance `audio_overflow` handling kills the listener (`voice_input.py:345-378, 444-447`, `microphone.py:503`):**
   - In `pi5mic` (`pi5mic/src/pi5mic/core/voiceinput.py:644-676`), a PortAudio
     `overflowed` flag on `stream.read()` is logged, clears the frame buffer, and
     continues reading; only 3 consecutive overflows trigger stream recreation,
     and the loop never terminates.
   - In `VoiceInputController._listen_once()` (`voice_input.py:444-447`):

     ```python
     pcm, overflowed = await source.read()
     if not self._resume_event.is_set() or self._stop_event.is_set():
         break
     if overflowed:
         raise VoiceInputError("audio_overflow")
     ```

   - And in `ManagedVoiceAudioSource.__init__()` (`microphone.py:503`),
     `block_frames` is hardcoded to `1280` samples. At the Fusion HAT+ I2S
     microphone's `48000 Hz` sample rate, `1280` samples is only **26.67 ms** per
     read while `openWakeWord` inference (`detector.process`) runs on every 80 ms
     frame.
   - Any transient CPU spike (such as LLM HTTP streaming, display SPI rendering,
     or ONNX wake-word inference) that delays a 26.67 ms read causes PortAudio to
     set `overflowed = True`. `VoiceInputController` immediately closes the audio
     stream, enters `DEGRADED` for `2**failures` seconds (2s, then 4s), and after
     `retry_limit = 2` (3 occurrences), permanently transitions to `FAILED` and
     stops listening!

4. **Empty Whisper transcripts are treated as fatal `transcription_failed` errors (`microphone.py:200-202`, `voice_input.py:345-378, 505-517`):**
   - In `pi5mic` (`pi5mic/src/pi5mic/core/voiceinput.py:509-518`), when no speech
     is detected after the wake word, `NoSpeechDetectedError` is caught, `failures`
     is not incremented, and the listener immediately re-arms.
   - In `WhisperCppTranscriber.transcribe()` (`microphone.py:200-202`), an empty
     transcript raises `RuntimeError("whisper.cpp returned an empty transcript")`,
     which `VoiceInputController._transcribe()` (`voice_input.py:516-517`) wraps
     into `VoiceInputError("transcription_failed")` (and even if `no_speech_detected`
     were raised, `VoiceInputController._run()` at `voice_input.py:345-360` treats
     *all* `VoiceInputError` codes as fatal strikes!).
   - Consequently, 3 empty/blank-audio captures after wake-word triggers
     permanently shut down Always-On Voice Input (`VoiceInputState.FAILED`).

5. **VAD RMS calculation lacks DC-offset removal and hangs for `max_command_seconds` (`15.0s`) on post-wake silence (`voice_input.py:451-463, 589-593`):**
   - `_pcm_rms(pcm)` (`voice_input.py:589-593`) computes raw RMS around `0`
     (`sqrt(mean(x^2))`) without subtracting the frame's DC mean. I2S MEMS
     microphones (`snd_rpi_googlevoicehat_soundcar`) commonly exhibit a DC bias
     whose raw RMS exceeds `silence_rms_threshold = 200`.
   - Furthermore, in `voice_input.py:451-463`:

     ```python
     if self._vad_enabled:
         silent = _pcm_rms(frame) < self._silence_rms_threshold
         if silent:
             if speech_started:
                 silent_frames += 1
         else:
             speech_started = True
             silent_frames = 0
     if len(capture) >= max_capture_bytes or (
         self._vad_enabled and speech_started and silent_frames >= silence_frames
     ):
         return await self._transcribe(bytes(capture), detector.sample_rate)
     ```

     - If DC offset + ambient noise keeps `_pcm_rms(frame) >= 200`, `speech_started`
       is set to `True` immediately on frame 1 and `silent_frames` stays `0`
       forever, forcing every command to record for the full `max_command_seconds`
       (`15.0s` in `config.toml`) before Whisper even starts!
     - Conversely, if wake word triggers and the user does not speak (or speaks
       below threshold), `speech_started` remains `False` and `silent_frames`
       never increments, again hanging for the full `15.0s`.

6. **Event-loop blocking in `_PCMFrameAssembler.feed()` and PulseAudio `hw:0,0` contention (`voice_input.py:448, 553-576`, `microphone.py:514-547`):**
   - `_PCMFrameAssembler.feed(pcm)` (`voice_input.py:553-576`) converts 48,000 Hz
     samples to 16,000 Hz using a pure-Python `while` loop
     (`int(value).to_bytes(2, "little", signed=True)`) synchronously on the main
     `asyncio` event loop thread, creating ~64,000 Python objects per second of
     audio and starving both WebSocket responsiveness and `source.read()`.
   - Finally, `/usr/bin/pulseaudio` (`PID 875`) is running on the host. Live
     testing confirmed that whenever any process queries ALSA `default` (`pcm.hat`),
     PulseAudio opens `/dev/snd/pcmC0D0c` (`hw:0,0` capture) and holds it for 5
     seconds (`module-suspend-on-idle`). While PulseAudio holds `hw:0,0`,
     PortAudio `resolve_supported_input_settings()` / `RawInputStream` on
     `snd_rpi_googlevoicehat_soundcar ... (hw:0,0)` fails with
     `Device unavailable [PaErrorCode -9985]`.

## Potential vulnerabilities and architectural risks

During the line-by-line audit across `ninjarobot_pi5_agent` and
`ninjarobot_pi5_ide`, six additional reliability and architectural risks were
identified:

1. **Sticky `_start_attempted` in `MicrophoneDevice.start()` blocks Level 2 recovery (`microphone.py:704-740`, `robot.py:929-931`):**
   - If `MicrophoneDevice.start()` fails once at startup (e.g., due to PulseAudio
     holding `hw:0,0`), `_start_attempted` stays `True` and `_backend` stays
     `None` for the lifetime of the service process, causing every subsequent
     `system.resume` health check (`_microphone_health()`) to fail without
     re-probing hardware.
2. **Repeated `pyngrok` paid traffic-policy warning on every service startup (`agent-service.log` lines 15, 74, 99, ..., 692):**
   - Every time `ninjarobot-agent` starts with `remote_access.enabled = true`,
     `pyngrok` logs:
     `failed to start tunnel: This policy includes paid traffic policy features that are not allowed on your current plan. ... ERR_NGROK_2263`
     before falling back to a basic tunnel. This adds 1–2 seconds of startup latency
     and clutters `agent-service.log` with false-positive error warnings.
3. **Continuous HTTP 405 reconnect loop from remote Tavily MCP (`agent-service.log` lines 10–11, 69–70, ..., 687–688):**
   - `mcp.client.streamable_http` attempts a `GET https://mcp.tavily.com/mcp` SSE
     stream which returns `HTTP/1.1 405 Method Not Allowed`, logging a reconnect
     message during every startup and tool session.
4. **Web Controller Resume disarms AI chat motion without updating the UI button (`web_control.py:416-426`, `app-agent.js:187-205`):**
   - When the user clicks **Resume** (`#resumeMovementButton`, `Y`) in the Agent
     Web UI, `WebRobotController.resume()` calls
     `self._runtime.disarm_motion(self.chat_session(lease_id))` on the backend,
     but `app-agent.js:195-200` does **not** call `updateAiMotion(false)`. Thus
     the **Arm AI motion** (`A`) button in the web UI remains visually highlighted
     as armed (`aria-pressed="true"`) even though the backend just disarmed AI
     chat motion!
5. **Conversation database bloat and prompt poisoning from persisted runtime notices (`runtime.py:1485-1501`, `agent_loop.py:299-305`):**
   - `_append_memory_notice()` writes runtime notices (`metadata={"workflow": "memory-notice"}`)
     as permanent `ASSISTANT` rows in `conversations.sqlite3`, and `AgentLoop`
     includes them in `history` on every subsequent model turn.
6. **Dual checkout paths in historical service logs (`agent-service.log` lines 86, 115):**
   - On 2 November (`14:31Z` and `14:33Z`), the service was started from a second
     checkout `/home/rogerchang/Ninja/NinjaRobotPi5` while sharing the same
     `~/.config/ninjarobot_pi5/` and `~/.local/state/ninjarobot_pi5/` directories.

## Phased implementation plan

> [!IMPORTANT]
> No runtime code or private configuration has been modified during this audit.
> Implementation must proceed only after explicit project-owner approval of this
> phased plan. Managed `pi5*` libraries (`pi5servo`, `pi5mic`, `pi5buzzer`,
> `pi5disp`, `pi5camera`, `pi5vl53l0x`) do **not** require modification for these
> fixes, preserving `docs/validation/immutable_driver_baseline.json`.

### Phase 1: Servo safety latch recovery, status visibility, and prompt/role alignment (Issue 1)

- **Objective:** Ensure Level 1 (`motion_latched`) stops can be cleanly diagnosed
  and resumed via `/resume` and Web UI **Resume** without being blocked by
  unrelated Level 2 device probes; fix sticky microphone health probes during
  Level 2 `system.resume`; distinguish historical latches from active electrical
  faults; surface latch status in `servo.status`, `runtime_state`, and UI; and
  align `IDENTITY_PROMPT` and optional wheel role setup with Fusion HAT+ servo
  rules.
- **Target files:**
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/safety.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/robot.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/servo.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/microphone.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/runtime.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service_main.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/prompts.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/setup_wizard.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-agent.js`
- **Compatibility contract:**
  - Preserve `RobotAssembly.resume_system()` and `RobotAssembly.resume_motion()`
    signatures and existing unit test contracts (`test_ipc.py`,
    `test_distance_game.py`, `test_disabled_devices.py`).
  - Preserve `config_import.py`'s safety rule (`InstallationGuide.md:190-191`)
    that positional servos on `fusion_hat_plus` are never *silently* mapped to
    `left_motor` / `right_motor`.
- **Implementation steps:**
  1. **Smart Level 1 vs Level 2 routing in `AgentRuntime.resume_system()` (`runtime.py:1935-1960`):**
     - Inspect `self._read_robot_status()` before dispatching the resume tool.
     - When `safety.get("motion_latched") is True` and
       `safety.get("system_latched") is False`, dispatch
       `tool_name="robot.motion.resume"` (which verifies live power via
       `ensure_power_ready()` and clears the Level 1 motion latch).
     - When `system_latched` is `True` (or when `_robot_status` is `None` /
       unlatched, preserving `test_ipc.py:443-466`), dispatch
       `tool_name="robot.system.resume"`.
  2. **Resilient `_microphone_health()` and `_camera_health()` during Level 2 `system.resume` (`robot.py:925-931`, `microphone.py:704-740`):**
     - In `RobotAssembly._microphone_health()`, if
       `await self.microphone.health() is not ResourceHealth.READY`, acquire
       `async with self.microphone.manual_access():` (pausing `VoiceInputController`
       if open) and call `await self.microphone.suspend()` before
       `await self.microphone.start()`. Do the same `suspend()` + `start()`
       retry in `_camera_health()` when not `READY`.
  3. **Historical vs active fault messaging (`safety.py:66-92, 404-419`):**
     - Pass `updated_at=snapshot.updated_at` into `stop_guidance()` (or format it
       in `_check_stop_state()`) so a persisted latch clearly states:
       `"Motion is blocked by a persistent safety stop recorded at <updated_at>: <cause>"`
       and instructs the operator to run `/resume` or click **Resume Robot
       Movement**.
  4. **Expose safety latch in `servo.status`, `_recovery_status`, `runtime_state`, and Web UI (`servo.py:240-252`, `runtime.py:881-897`, `service_main.py:250-281`, `app-agent.js:187-205`):**
     - Include `motion_latched` and `stop_reason` in `ServoDevice.status()` (via
       an optional `safety_reader` callback passed from `RobotAssembly`) and
       include `safety` (`motion_latched`, `system_latched`, `reason`,
       `updated_at`), `servo_endpoints`, and `servo_roles` in `runtime_state`
       (`service_main.py:250-281`).
     - Update `AgentRuntime._recovery_status()` (`runtime.py:881-897`) so
       `motion_latched` also populates `reason`, `detail`, and `instructions`.
     - In `app-agent.js:165, 198`, call `updateAiMotion(false)` when `resumeRobot`
       completes so the **Arm AI motion** button accurately reflects that
       `/resume` disarmed AI motion.
  5. **Single-servo vs locomotion prompt & opt-in wheel role mapping (`prompts.py:88-96`, `setup_wizard.py:562-583`):**
     - Update `IDENTITY_PROMPT` (`prompts.py:88-96`) to distinguish:
       - Direct single-servo angle requests (e.g., `"rotate PWM0 / hat_pwm0 to 90 degrees"`):
         call `robot.servo.move` with the requested `endpoint` and `target_angle`.
       - Multi-stage expressive movements or directional wheel locomotion (when
         `runtime_state.servo_roles` has `left_motor` and `right_motor`
         configured): call `robot.behavior.execute_movement`.
     - In `_import_hardware_configuration()` (`setup_wizard.py:562-583`), when
       the profile is `fusion_hat_plus`, `len(updated.hardware.servos.endpoints) >= 2`,
       and `not updated.behaviors.servo_roles` (only during interactive
       tty/real hardware import when `servo.json` is present), offer an explicit
       opt-in choice to map `left_motor` and `right_motor` to the first two
       calibrated `hat_pwm*` endpoints if they are wheel servos (defaulting to
       keeping positional servos unmapped).
- **Validation gate:** Unit tests in `ninjarobot_pi5_ide/tests/test_safety.py`,
  `test_behavior_runtime.py`, `test_ipc.py`, and full gate suite.
- **Hardware risk level:** Medium (actuator policy and safety latch recovery; no
  automatic motion is triggered by clearing a latch).

### Phase 2: Embedded speaker LLM awareness, Piper TTS provisioning, and memory hygiene (Issue 2)

- **Objective:** Make the LLM aware of the automatic spoken-output pipeline,
  prevent onboarding from enabling `speech_output.enabled = true` when Piper TTS
  or voice models are missing, provide a streamlined Piper TTS + English voice
  provisioning workflow, surface exact TTS diagnostic codes, and stop polluting
  LLM conversation context with `memory-notice` rows.
- **Target files:**
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/prompts.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service_main.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/speech.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/runtime.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/setup_wizard.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/hardware_setup.py`
  - `scripts/prepare_speech_voice.py`
- **Compatibility contract:**
  - Preserve `_optional_hardware()` prompt sequence in `setup_wizard.py` so
    existing `test_setup_wizard.py` console tests pass unchanged.
  - Keep Piper in its isolated `~/.local/share/ninjarobot_pi5/speech` virtual
    environment (`requirements/local-speech.txt`), never installing Piper into
    the root robot environment (`InstallationGuide.md:830-843`).
- **Implementation steps:**
  1. **Add `speech_output` state to `runtime_state` and `IDENTITY_PROMPT` (`service_main.py:250-281`, `prompts.py:32-118`):**
     - Include `"speech_output": {"enabled": bool(runtime.speech and runtime.speech.enabled), "output_node": config.speech_output.output_node, "fusion_speaker": config.speech_output.fusion_speaker}`
       in `runtime_state` (`service_main.py:250-281`).
     - Add an explicit instruction in `IDENTITY_PROMPT` (`prompts.py`):
       `"When runtime_state.speech_output.enabled is true, the runtime automatically synthesizes and speaks your text reply (or spoken_summary) through the configured speaker (such as the Fusion HAT+ embedded speaker or Bluetooth speaker) after you reply. Do not claim that you only have a buzzer when asked to speak out loud; write the spoken response normally in your reply."`
  2. **Auto-bind existing English voice model and guard `speech_output.enabled` in `configure_sunfounder_i2s_speaker()` (`hardware_setup.py:435-462`, `scripts/prepare_speech_voice.py`):**
     - In `configure_sunfounder_i2s_speaker(config_path)`
       (`ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/hardware_setup.py:435-462`),
       check if the default English voice model
       (`~/.local/share/ninjarobot_pi5/voices/en/en_US-ljspeech-high.onnx`)
       exists on disk when `payload["speech_output"]["english_model"]` is empty;
       if so, set `payload["speech_output"]["english_model"] = "~/.local/share/ninjarobot_pi5/voices/en/en_US-ljspeech-high.onnx"`.
     - Check whether `piper_python` (`~/.local/share/ninjarobot_pi5/speech/bin/python`)
       and the configured language model exist on disk: set
       `payload["speech_output"]["enabled"] = True` when ready, or `False` when
       Piper/voice files are not yet installed (while still saving
       `output_node = node` and `fusion_speaker = True`), and report the exact
       setup command in `setup_wizard.py` without adding an extra blocking
       `ui.ask()` call inside `_optional_hardware()`.
     - Enhance `scripts/prepare_speech_voice.py` with optional `--install-piper`
       and `--configure-config` flags (or provide a single documented command)
       that creates `~/.local/share/ninjarobot_pi5/speech`, installs
       `requirements/local-speech.txt`, downloads and verifies
       `en_US-ljspeech-high.onnx`, and updates `speech_output.english_model` and
       `speech_output.enabled = true` in `~/.config/ninjarobot_pi5/config.toml`.
  3. **Surface specific synthesis failure reasons (`speech.py:54-70, 223-229`):**
     - In `LocalSynthesizer.status()` (`speech.py:54-70`) and
       `SpeechService.speak()` (`speech.py:223-229`), preserve known safe
       `ValueError` diagnostic codes (`speech_model_not_configured`,
       `piper_not_installed`, `speech_model_missing`,
       `speech_model_language_mismatch`, `speech_language_unavailable`) in the
       returned `detail` / `reason` field so `/speech status` and logs identify
       the exact missing prerequisite.
  4. **Filter `memory-notice` rows out of LLM prompt history and avoid persisting transient TTS errors (`agent_loop.py:299-305`, `runtime.py:547-555`):**
     - In `AgentRuntime.chat()` (`runtime.py:547-555`), when `spoken` fails,
       stream `\n\n` + notice to `on_text_delta` and append it to the returned
       `reply.text`, but **do not** persist transient TTS failure notices as
       `MessageRole.ASSISTANT` messages in `conversations.sqlite3`.
     - In `AgentLoop.chat()` (`agent_loop.py:299-305`), exclude stored messages
       with `stored.metadata.get("workflow") == "memory-notice"` when building
       `history` for the model turn so historical notices in
       `conversations.sqlite3` no longer poison the LLM context.
- **Validation gate:** Unit tests in `ninjarobot_pi5_agent/tests/test_speech.py`,
  `test_setup_wizard.py`, `test_fusion_setup.py`, and full gate suite.
- **Hardware risk level:** Low (audio output configuration, prompt/runtime state,
  and conversation context filtering).

### Phase 3: Web power-off helper installation and authorization decoupling (Issue 3)

- **Objective:** Allow operators to install the privileged poweroff helper and
  enable the Web UI **Power off NinjaRobot** button via CLI or onboarding without
  forcing systemd boot auto-start, and ensure local controllers are properly
  authorized or guided to pair.
- **Target files:**
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/deployment.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_cli.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/setup_wizard.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_app.py`
- **Compatibility contract:**
  - Keep `/usr/libexec/ninjarobot-poweroff` and
    `/etc/sudoers.d/ninjarobot-agent-poweroff` byte-identical to the audited
    deployment assets and validated via `visudo -cf` and
    `validate_poweroff_helper()`.
  - Never run a live power-off command in automated tests.
- **Implementation steps:**
  1. **Add standalone `install-poweroff` / `enable_poweroff` to `DeploymentManager` (`deployment.py`, `agent_cli.py`):**
     - Add `DeploymentManager.install_poweroff(*, confirmed: bool) -> dict[str, Any]`
       that stages and installs `/usr/libexec/ninjarobot-poweroff` (`0755 root:root`)
       and `/etc/sudoers.d/ninjarobot-agent-poweroff` (`0440 root:root`, checked
       with `visudo -cf`), verifies `self._poweroff_authorized()`, runs
       `_ensure_full_poweroff_configuration()` (which is a safe no-op on
       `fusion_hat_plus`), and persists `deployment.web_poweroff_enabled = True`
       in `config.toml` **without** enabling `ninjarobot-agent.service` at boot
       (`auto_start_enabled` remains unchanged).
     - Expose this in `ninjarobot-agent deployment install-poweroff --confirm`
       and in the interactive `ninjarobot-agent deployment` menu (`agent_cli.py`).
  2. **Offer optional Web Power-Off setup during onboarding (`setup_wizard.py`):**
     - Support `ninjarobot onboard --step poweroff` (and offer opt-in helper
       installation inside `_remote_setup()` when running interactively) so
       operators can enable the Web Power-Off button during onboarding while
       preserving existing `_Console` test fixtures.
  3. **Authorize active local controller when `require_local_pairing` is `False` (`web_app.py:446-475`):**
     - In `websocket_controller()` (`web_app.py:446-475`), when
       `scope == "local"` (direct LAN connection, not `remote_connection`) and
       `not require_local_pairing`, treat the authenticated local controller as
       `paired_connection = True` (or require local pairing whenever
       `web_poweroff_enabled` is `True` by including `config.deployment.web_poweroff_enabled`
       in `_effective_onboarding_enabled()` in `service_main.py:66-73` so local
       browsers always pair via `/pair` and receive the session cookie). Including
       `web_poweroff_enabled` in `_effective_onboarding_enabled()` is even safer
       because it preserves the strict `/pair` session-cookie requirement for
       power-off!
- **Validation gate:** Unit tests in `ninjarobot_pi5_agent/tests/test_deployment.py`
  and `test_web.py`.
- **Hardware risk level:** High / Power-risk (touches `/usr/libexec/ninjarobot-poweroff`
  and `/etc/sudoers.d/ninjarobot-agent-poweroff`; automated tests must stop at
  command construction, sudoers validation, and dry-run checks).

### Phase 4: Web microphone and robot Always-On Voice Input stabilization (Issue 4)

- **Objective:** Make `#webMicButton` work reliably across all browsers (with
  automatic fallback to the robot's local `whisper.cpp` push-to-talk endpoint
  when browser `SpeechRecognition` is unavailable or fails), and make robot-side
  Always-On Voice Input (`#usbMicButton` / `VoiceInputController`) as resilient
  on the Fusion HAT+ 48 kHz I2S microphone as standalone `pi5mic`.
- **Target files:**
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-agent.js`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config_import.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/microphone.py`
  - `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/voice_input.py`
- **Compatibility contract:**
  - Preserve `VoiceInputController` state machine (`DISABLED`, `STARTING`,
    `LISTENING`, `DETECTED`, `RECORDING`, `TRANSCRIBING`, `DISPATCHING`,
    `COOLDOWN`, `PAUSED`, `DEGRADED`, `FAILED`) and existing unit tests in
    `ninjarobot_pi5_ide/tests/test_voice_input.py`.
- **Implementation steps:**
  1. **Upgrade `#webMicButton` with robot push-to-talk fallback and fix `#usbMicButton` error/failed-state handling (`app-agent.js:209-309`):**
     - In `configureSpeechRecognition()` (`app-agent.js:240-309`), do **not**
       disable `#webMicButton` when `window.SpeechRecognition || window.webkitSpeechRecognition`
       is missing, and if browser `SpeechRecognition` fails with `network`,
       `service-not-allowed`, `not-allowed`, or `audio-capture`, automatically
       fall back to robot-side push-to-talk (`send("usb_microphone", { duration_seconds: 5, language: state.locale || "auto" })` /
       `send("usb_microphone_stop")`) and place the returned `data.transcript`
       into `elements.chatInput.value`.
     - Preserve any existing text in `elements.chatInput.value` when starting a
       new dictation segment (`prefix + " " + transcript.trim()`), and guard
       `recognition.start()` with a synchronous ` recognitionStarting` flag to
       prevent `InvalidStateError` on rapid clicks.
     - In `updateVoiceInput()` (`app-agent.js:209-227`), treat
       `status.state === "failed"` or `"stopped"` as `enabled = false` so the
       user can click `#usbMicButton` to re-enable voice input after a failure,
       and replace `.catch(() => {})` (`line 234`) with error toast/log feedback.
  2. **Import `voiceinput.enabled` from `mic.json` (`config_import.py:283-297`):**
     - In `import_pi5_configs()` (`config_import.py:283-297`), include
       `"enabled": "enabled"` in `voice_mapping` when `isinstance(voiceinput.get("enabled"), bool)`
       so enabling Always-On Voice Input in `mic-tool` persists into
       `config.toml` during onboarding config import.
  3. **Tolerate transient PortAudio overflows and scale 48 kHz read block size (`voice_input.py:444-447`, `microphone.py:497-550`):**
     - In `ManagedVoiceAudioSource.start()` (`microphone.py:514-547`), scale the
       effective read block size for high sample rates when `self._block_frames == 1280`
       (e.g., `max(self._block_frames, int(actual_rate * 0.08))` = `3840` frames
       at `48000 Hz`, matching the 80 ms `openWakeWord` frame period) and retry
       `RawInputStream` open up to 3 times with a `0.4s` backoff if PortAudio
       reports transient `Device unavailable [PaErrorCode -9985]` from
       PulseAudio idle-suspend handoff.
     - In `VoiceInputController._listen_once()` (`voice_input.py:444-447`), track
       consecutive overflows (`overflow_streak`): only raise
       `VoiceInputError("audio_overflow")` if **3 consecutive reads** overflow
       (matching `pi5mic/src/pi5mic/core/voiceinput.py:644-676`), resetting
       `overflow_streak = 0` on normal reads.
  4. **Treat `no_speech_detected` and empty/blank Whisper transcripts as non-fatal re-arm events (`microphone.py:200-202`, `voice_input.py:345-360, 505-517`):**
     - In `VoiceInputController._transcribe()` (`voice_input.py:505-517`),
       classify empty transcripts, `RuntimeError("whisper.cpp returned an empty transcript")`,
       and Whisper blank-audio tokens (`[BLANK_AUDIO]`, `(blank audio)`) as
       `VoiceInputError("no_speech_detected")`.
     - In `VoiceInputController._run()` (`voice_input.py:345-360`), when
       `exc.code == "no_speech_detected"`, reset to `LISTENING` and `continue`
       immediately **without** incrementing `failures` or entering
       `DEGRADED` / `FAILED` (matching `pi5mic`).
  5. **Remove DC offset in `_pcm_rms()`, bound post-wake initial silence, and optimize `_PCMFrameAssembler.feed()` (`voice_input.py:450-465, 553-593`):**
     - In `_pcm_rms(pcm)` (`voice_input.py:589-593`), subtract the frame's mean
       sample value (`mean = sum(samples) / len(samples)`) before computing RMS
       so I2S MEMS DC bias cannot masquerade as continuous speech.
     - In `_listen_once()` (`voice_input.py:450-465`), also count initial
       post-wake silent frames (`initial_silent_frames`): if `not speech_started`
       after `max(silence_frames * 2, 25)` frames (~2.0s–2.5s of silence after
       wake word), abort capture with `no_speech_detected` instead of recording
       dead air for `max_command_seconds` (`15.0s`).
     - In `_PCMFrameAssembler.feed(pcm)` (`voice_input.py:553-576`), replace the
       per-sample `int(value).to_bytes(2, "little", signed=True)` loop with
       `array("h")` bulk packing (or integer decimation when `source_rate == 48000`
       and `target_rate == 16000`, which is an exact 3:1 ratio!) to eliminate
       64,000 object allocations/sec on the `asyncio` event loop.
- **Validation gate:** Unit tests in `ninjarobot_pi5_ide/tests/test_voice_input.py`,
  `test_microphone.py`, `test_config_import.py`, and full gate suite.
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
- **Current registered wiki sources in `ninjarobot_pi5_wiki/project-knowledge.json`:**
  - `raw/articles/ninjarobotpi5/2026-11-03-04/InstallationGuide.md`
  - `raw/articles/ninjarobotpi5/2026-11-03-04/DevelopmentGuide.md`
  - `raw/notes/ninjarobotpi5/2026-11-03-04/DevelopmentLog.md`
- **Documentation updates required when implementing Phases 1–4:**
  1. `README.md` — document the standalone Web Power-Off helper installation
     command (`ninjarobot-agent deployment install-poweroff --confirm`), Piper
     TTS voice preparation (`scripts/prepare_speech_voice.py`), and Fusion HAT+
     servo role behavior.
  2. New version of `InstallationGuide.md` under
     `ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-04/InstallationGuide.md`
     (never editing the registered `2026-11-03-04` original) — document Piper TTS
     provisioning for the Fusion HAT+ embedded speaker, standalone Web Power-Off
     helper installation, and Level 1 vs Level 2 `/resume` behavior.
  3. New version of `DevelopmentGuide.md` under
     `ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-04/DevelopmentGuide.md` —
     document automatic `motion.resume` vs `system.resume` routing in
     `AgentRuntime.resume_system()`, `runtime_state.speech_output` and
     `runtime_state.safety` contracts, `memory-notice` history filtering, and
     48 kHz Fusion HAT+ voice-input buffering and DC-offset-free VAD.
  4. New version of `DevelopmentLog.md` under
     `ninjarobot_pi5_wiki/raw/notes/ninjarobotpi5/2026-11-04/DevelopmentLog.md` —
     record the 4 November 2026 post-integration audit rationale and validation
     results.

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
   - **Expected result:** `AgentRuntime.resume_system()` dispatches
     `robot.motion.resume`, `motion_latched` transitions to `false`, and
     `servo.status` reports `motion_latched: false`.
   - **Rollback:** Run `ninjarobot-agent service stop` or trigger Emergency Stop (`X`).
2. **Device communication check (embedded speaker & voice input, consent required):**
   - Provision the isolated Piper environment and English voice model using
     `scripts/prepare_speech_voice.py`, then start the agent, enable `/speech on`,
     and ask: `"Please introduce yourself out loud."`
   - **Expected result:** The agent replies normally without claiming it only has
     a buzzer, and the reply is spoken clearly through the Fusion HAT+ embedded
     speaker (`alsa:sndrpigooglevoi`).
   - Enable **VOICE INPUT** (`#usbMicButton`) in the Web UI, say
     `"Hey Ninja, what time is it?"`, and test **WEB MICROPHONE** (`#webMicButton`).
   - **Expected result:** Wake word triggers `recording` -> `transcribing` ->
     `dispatching` without `audio_overflow` or premature `FAILED` state;
     `#webMicButton` captures speech via browser STT or robot push-to-talk
     fallback.
   - **Rollback:** Toggle `/speech off` and click **VOICE INPUT** to disable
     listening.
3. **Actuator-moving check (opt-in; raise wheels and keep power switch accessible):**
   - Arm AI motion (`A` / `/arm`), then ask: `"Rotate hat_pwm0 servo to 90 degrees."`
   - **Expected result:** The LLM calls `robot.servo.move(endpoint="hat_pwm0", target_angle=90)`,
     and `hat_pwm0` rotates smoothly to 90 degrees and de-energizes cleanly.
   - **Rollback:** Click **Emergency Stop** (`X`) or remove servo power.
4. **Power-risk check (manual operator test only):**
   - Run `uv run --frozen ninjarobot-agent deployment install-poweroff --confirm`,
     restart the service, pair the browser via `/pair`, and open the Web UI
     Robot Menu.
   - **Expected result:** **Power off NinjaRobot** (`#powerOffButton`) is enabled
     for the active paired controller and displays `"Available to this active controller."`
   - **Rollback:** Cancel the confirmation dialog, or set
     `web_poweroff_enabled = false` in `~/.config/ninjarobot_pi5/config.toml`.

## Post-testing follow-up fixes (4 November 2026)

Following repeated live testing on the Raspberry Pi 5 + SunFounder Fusion HAT+, three additional issues were traced in `~/.local/state/ninjarobot_pi5/agent-service.log`, `agent-actions.sqlite3`, and `conversations.sqlite3` and resolved:

1. **Chat motion arming command (`/arm`):**
   - **Root cause:** `IMMUTABLE_SAFETY_PROMPT` did not name `/arm`, leading the LLM and user to try `/motion` / `/motion on` in chat (`2026-11-04T01:50:34Z`), and Web UI `submitChat()` (`app-agent.js`) only intercepted `/resume` and `/camera`.
   - **Fix:** Updated `IMMUTABLE_SAFETY_PROMPT` (`prompts.py`) to specify `/arm` and `/disarm`, added deterministic `/motion` guidance in `AgentRuntime.chat()` (`runtime.py`), and added `/arm` and `/disarm` interception in `submitChat()` (`app-agent.js`).
2. **Servo `-90`~`0`~`90` degree range and `0` degree center interpolation:**
   - **Root cause A (LLM convention):** Neither `ServoMoveAdapter.descriptor` nor `IDENTITY_PROMPT` specified that `target_angle` uses `-90` to `90` degrees with `0` as center, so the LLM assumed `0..180` hobby servo convention (`center = 90`) when asked to rotate to center (`2026-11-04T01:56:15Z`).
   - **Root cause B (`ServoDevice.move()` interpolation bug):** When `target_angle=0` was called (`01:58:05Z`, `01:59:55Z`, `02:33:25Z`), `ServoDevice.move()` unconditionally called `servo.move_to_center()` *before* `runtime.group.move_all_async()`. `move_to_center()` overwrote `servo._last_angle = 0.0`, causing `move_all_async([0.0])` to see `distance = abs(0.0 - 0.0) < 0.1` and return immediately in `1ms`, where `finally: runtime.group.off()` cut PWM before the physical servo could move back from `-90°`/`90°` to `0°`.
   - **Fix:** Updated `ServoMoveAdapter.descriptor` (`servo.py`), `IDENTITY_PROMPT` (`prompts.py`), and `runtime_state.calibrated_servo_endpoints` (`service_main.py`) to explicitly define `-90` (min), `0` (center), and `90` (max). Updated `ServoDevice.move()` (`servo.py`) to call `servo.move_to_center()` only when `previous_angle is None`, preserving `last_angle` for smooth interpolation back to `0°`.
3. **Web Mic continuous back-to-back voice input failure:**
   - **Root cause:** In `app-agent.js`, neither `recognition.onresult` (on `isFinal`) nor `submitChat()` stopped the active `SpeechRecognition` session. When the user submitted the first voice prompt and clicked `#webMicButton` a second time (`02:31:05Z`), `state.recognitionActive` was still `true`, so clicking `#webMicButton` merely stopped the lingering session instead of starting a new one. Reusing a single `SpeechRecognition` instance across turns also left stale browser state.
   - **Fix & Further Investigation:** Refactored `configureSpeechRecognition()` (`app-agent.js`) to instantiate a fresh session per click. When immediate re-arming instability persisted due to asynchronous browser engine teardown and handler stripping, a comprehensive root cause investigation and lifecycle state machine proposal was produced in `docs/project-history/NinjaWebMicContinuousInvestigation_261104.md`.
