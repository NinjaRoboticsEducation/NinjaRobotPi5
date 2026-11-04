# NinjaRobotPi5 Web Microphone Continuous Recognition Investigation

Implementation follow-up: see [the source fact check and validation](../validation/web_mic_lifecycle_261104.md). Browser teardown timing and the specific logged pipe failure remain hypotheses; the source-level lifecycle defects are confirmed.

This document details the root cause investigation, runtime log evidence, and
architectural recommendations for resolving the continuous usage instability of
the Web Microphone feature (`#webMicButton`) in NinjaRobotPi5.

## Context and reported issue

Following the initial integration audit and follow-up repairs on 4 November 2026,
the user reported the following behavior:

1. **First activation succeeds:** When clicking the **Web Mic** button in the web
   interface, the browser microphone activates normally, records the user's
   voice, and transcribes the speech into the chat input box.
2. **Immediate second activation fails:** When attempting to activate the Web Mic
   again immediately to input a second consecutive voice prompt, the microphone
   does not record or transcribe.
3. **Typing text temporarily restores it:** If the user manually types a text
   prompt and sends it, subsequent activation of the Web Mic works once, but
   fails again if used continuously back-to-back.

## Runtime log and database evidence

An investigation of the running agent environment, database stores, and service
logs was conducted:

### 1. Verification of the active audio recognition path

The system provides two distinct microphone input paths on the web interface:
- **Path A (Browser Web Speech API):** Triggered by `#webMicButton` using
  the browser's native `window.SpeechRecognition` / `window.webkitSpeechRecognition`.
- **Path B (Robot Onboard Push-to-Talk):** Dispatched via WebSocket request
  `usb_microphone`, executing `microphone.transcribe` (`whisper.cpp`) on the Pi.

A query against the persistent action ledger (`agent-actions.sqlite3`) revealed:

```bash
uv run --frozen python -c '
import sqlite3, pathlib
conn = sqlite3.connect(pathlib.Path.home() / ".local/state/ninjarobot_pi5/agent-actions.sqlite3")
rows = conn.cursor().execute("SELECT count(*) FROM action_ledger WHERE request_json LIKE \"%microphone%\" OR request_json LIKE \"%transcribe%\"").fetchone()
print("Microphone actions count:", rows[0])
'
# Output: Microphone actions count: 0
```

**Finding:** Zero server-side `usb_microphone` actions were logged. This confirms
that the user's browser (e.g. Chrome, Edge, or Safari) natively supports the Web
Speech API and is executing recognition entirely client-side. The failure is
therefore rooted in the browser's JavaScript recognition lifecycle rather than
the backend `whisper.cpp` engine.

### 2. Conversation timeline and server-side speech synthesis latency

Inspection of `conversations.sqlite3` during the testing window (around 12:35–12:40
local / 03:35–03:40 UTC) revealed:

- `12:35:40`: User submitted speech transcript:
  `"Ninja how is the weather condition in Yokohama today"`
- `12:35:41`–`12:35:43`: Tool call `mcp.tavily.tavily-search` executed.
- `12:35:45`: Ollama produced the text reply:
  `"In Yokohama today, November 4, 2026, it's currently around 15°C with light rain. It feels a bit cooler, around 11°C, and it's quite cloudy. You might want to bring an umbrella if you're heading out!"`
- `12:35:45`–`12:36:00`: Because `/speech on` was active, `SpeechService.speak()`
  invoked Piper TTS (`en_US-ljspeech-high.onnx`) through the I2S speaker.
- **Benchmark:** Directly profiling Piper synthesis for this 48-word paragraph
  on the Pi 5 took **15.55 seconds**.
- `12:36:00`: The synthesis/playback exceeded the IDE audio deadline, appending
  `"Spoken output unavailable or stopped; the text reply is retained."` to the session.
- `12:36:47`: In `agent-service.log`, an unretrieved `BrokenPipeError` appeared:
  ```text
  2026-11-04 12:36:47,286 ERROR asyncio: Future exception was never retrieved
  future: <Future finished exception=BrokenPipeError()>
  BrokenPipeError
  ```
  This occurred because the child audio process pipe closed when speech timed
  out, while the background stdin drain task in `audio_process.py:exchange()`
  was still pending.

## Root cause analysis

### Root cause 1: Asynchronous browser engine teardown race condition

In `app-agent.js`, the recognition stopping logic was previously implemented as:

```javascript
function stopActiveRecognition({ abort = false } = {}) {
  recognitionStarting = false;
  state.recognitionActive = false;
  resetWebMicButton();
  const active = state.recognition;
  if (!active) return;
  state.recognition = null;
  active.onstart = null;
  active.onresult = null;
  active.onerror = null;
  active.onend = null;
  try {
    if (abort && typeof active.abort === "function") {
      active.abort();
    } else {
      active.stop();
    }
  } catch {}
}
```

When a final transcript is produced (`isFinal == true`) or when the user submits
chat, `stopActiveRecognition()` immediately set `state.recognition = null` and
stripped all event handlers (including `active.onend = null`).

However, inside the Chromium and WebKit rendering engines:
1. Calling `active.stop()` or `active.abort()` initiates an **asynchronous IPC**
   to the browser's audio capture service to release the OS microphone handle and
   disconnect the speech service.
2. This teardown process typically takes between **200 ms and 600 ms**.
3. During this window, the browser considers the speech recognition session to be
   in the `stopping` or `aborting` state.
4. When the user clicks **Web Mic** immediately for a second prompt, `state.recognition`
   is already `null`. The click handler creates a `new SpeechRecognition()` instance
   and immediately calls `.start()`.
5. Chromium rejects starting a new session while a previous session in the same
   origin/tab is still closing. Chromium emits an asynchronous `onerror` event on
   the new instance with:
   ```javascript
   event.error = "aborted" // or "audio-capture" / InvalidStateError
   ```
6. In `app-agent.js`:
   ```javascript
   recognition.onerror = (event) => {
     if (state.recognition !== recognition) return;
     const errorCode = event?.error;
     stopActiveRecognition({ abort: true });
     if (errorCode === "aborted") return; // Silently swallowed!
     ...
   };
   ```
   Because `errorCode === "aborted"` was silently ignored, the button reset to idle
   with no notification and no retry. To the user, clicking the button immediately
   simply did nothing.

### Root cause 2: Event handler stripping breaks browser lifecycle synchronization

By setting `active.onend = null` inside `stopActiveRecognition()`, the client
intentionally detached itself from the only browser event that signals when the
audio hardware has actually been freed. Without waiting for `onend`, the client
state (`state.recognition = null`) and the browser's internal state
(`SpeechRecognitionState::kStopping`) were completely out of sync.

### Root cause 3: Why typing a text prompt "restored" functionality

When consecutive voice input failed, the user manually typed a prompt into the
chat input box. The 5 to 10 seconds spent typing allowed the browser engine
to complete its background teardown and return to the `IDLE` state. As a result,
the subsequent Web Mic click succeeded for one turn, but failed again on the next
immediate turn.

## Proposed architectural recommendations

To provide continuous, robust Web Mic operation across repeated voice prompts,
the following changes are recommended:

### 1. Implement a 4-state client lifecycle machine

Replace the boolean flags (`state.recognitionActive`, `recognitionStarting`) with
an explicit state model:

```text
[IDLE] ──(click)──> [STARTING] ──(onstart)──> [RECORDING]
  ▲                                                │
  │                                           (isFinal / click / submit)
  │                                                ▼
  └──────────(onend)──────────────────────── [STOPPING]
```

- **`IDLE`:** No recognition running or stopping. Clicking starts a new session.
- **`STARTING`:** `recognition.start()` was called, awaiting `onstart`.
- **`RECORDING`:** Active microphone capture in progress.
- **`STOPPING`:** `stop()` or `abort()` was requested, but the browser has not
  yet emitted `onend`.

### 2. Immediate re-arming via `pendingStart` queueing

If the user clicks **Web Mic** while the state is `STOPPING` (e.g. immediately
after submitting a prompt or immediately after a final transcript):
- Do not attempt an immediate `new SpeechRecognition().start()` (which Chromium
  would reject).
- Set `pendingStart = true` and update the button UI to indicate a pending start.
- When the active session's native `onend` event fires, check `pendingStart`.
  If `true`, automatically instantiate and start the new session immediately
  upon clean hardware release.

### 3. Natural utterance finalization for `continuous: false`

With `recognition.continuous = false`, the browser automatically stops listening
and emits `onend` once the user finishes speaking an utterance. The client should:
- Populate `elements.chatInput.value` with the final transcript.
- Let the browser naturally transition to `onend` without calling an abrupt
  synchronous `.stop()` inside the `onresult` callback.
- Call `.abort()` only when the user explicitly cancels or clicks Send (`submitChat`).

### 4. Robust error handling

- Do not silently swallow `error === "aborted"` if the user intended to record.
  If an `aborted` event occurs while `pendingStart` is active, retry after a
  short backoff (e.g. 150 ms).
- Preserve user input prefixes when concatenating successive dictation passes.

### 5. Backend `BrokenPipeError` hardening in `audio_process.py`

In `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/audio_process.py`, wrap the
`exchange()` stdin drain task to catch and suppress `BrokenPipeError` and
`ConnectionResetError` cleanly, ensuring that interrupted or timed-out speech
synthesis does not leave unretrieved `asyncio` task exceptions in
`agent-service.log`.

## Phased implementation plan

### Phase 1: Web speech lifecycle state machine and queueing
- **Target file:** `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-agent.js`
- **Actions:**
  1. Define explicit state tracking (`IDLE`, `STARTING`, `RECORDING`, `STOPPING`).
  2. Implement `pendingStart` queueing in `onend`.
  3. Remove premature `recognition.stop()` from `onresult`.
  4. Ensure `stopWebMicSession({ abort: true })` in `submitChat()` properly
     synchronizes with the `STOPPING` state.
- **Validation:** Frontend integration tests in `test_web.py`.

### Phase 2: Backend audio process pipe exception suppression
- **Target file:** `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/audio_process.py`
- **Actions:**
  1. Ensure `exchange()` catches `BrokenPipeError` during process termination so
     `asyncio` does not log unretrieved task exceptions.
- **Validation:** Unit tests in `test_audio_output.py`.

### Phase 3: Gate verification
- Run immutable driver verifiers, compilation, ruff lint/format, mypy, and
  full pytest suite (`1,139+` tests).

## Manual Raspberry Pi test checklist (post-fix)

1. Open the NinjaRobot web interface in Chrome or Safari.
2. Click **Web Mic**, speak: *"What is the time?"*, and wait for transcription.
3. Click **Send**.
4. **Immediately** (within 1 second) click **Web Mic** again.
   - **Expected result:** The button enters recording state cleanly without
     failing or throwing `"aborted"`.
5. Speak: *"Rotate all servos to center."*
   - **Expected result:** The speech is transcribed into the input box.
6. Repeat consecutively 3–4 times in rapid succession.
   - **Expected result:** All consecutive voice dictations activate and transcribe
     reliably.
