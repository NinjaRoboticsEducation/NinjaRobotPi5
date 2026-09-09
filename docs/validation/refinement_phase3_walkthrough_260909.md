# Phase 3: spoken replies and coordinated output — walkthrough

Phase 3 is implemented and software-tested. **Development pauses before Phase 4.**
These instructions are for your acceptance test (checking the real robot yourself).
The coding agent has not paired your speaker, installed Piper, played audio,
captured media, changed the running service, or tested physical behavior.

## Contents

- [What changed](#what-changed)
- [Prepare safely](#prepare-safely)
- [Install the optional English voice](#install-the-optional-english-voice)
- [Pair and select the Bluetooth speaker](#pair-and-select-the-bluetooth-speaker)
- [Configure spoken output](#configure-spoken-output)
- [Safe smoke tests](#safe-smoke-tests)
- [Speaker and controller tests](#speaker-and-controller-tests)
- [Microphone coordination tests](#microphone-coordination-tests)
- [Spoken reminders](#spoken-reminders)
- [Optional Mandarin and Japanese](#optional-mandarin-and-japanese)
- [Actuator-moving tests](#actuator-moving-tests)
- [Power-risk tests](#power-risk-tests)
- [Troubleshooting and rollback](#troubleshooting-and-rollback)
- [Record your results](#record-your-results)

## What changed

TTS (text-to-speech: converting written words into sound) uses **Piper 1.8.0**
on the Pi. It does not send reply text to a speech provider or charge per utterance.
Your selected conversation model may still use a cloud service and incur its usual
charges. Speech is off by default and needs both a local voice and an explicit
speaker selection. Enabling it is a service-session setting: it applies to normal
model replies across connected chat sessions, including voice-originated replies.
Anyone nearby may hear them. Profile management, direct task commands and other
local control replies remain text-only.

The Agent produces a short audio file; the IDE (the project's device coordination
layer) alone plays it through PipeWire (the operating system's audio service).
The existing speaking face follows playback. Explicit device actions take priority;
the existing buzzer is used for an approved reminder fallback, not doubled over
speech. No wheel animation is added. Text remains available if audio fails.
Temporary generated audio is removed after synthesis, including errors and
cancellation. Spoken text is limited to 500 characters by default; the full written
answer remains available. Code blocks and web addresses are omitted from speech.

This is **listen, then speak**. The robot pauses an idle wake listener before
playback and releases that pause afterwards. It never enables a microphone that
you disabled. A recording already in progress wins: speech fails safely rather
than cutting it short. Simultaneous conversation, interrupting speech by voice,
lip synchronization, and new personality profiles are outside this phase.

A successful playback process is evidence that software finished sending audio,
not proof that the speaker was audible. Your listening test supplies that evidence.

## Prepare safely

1. Work from the project root in a terminal under the same Linux account that runs
   the Agent. Preserve your private configuration/database using your normal backup
   procedure. Do not share those files or put them in Git.
2. Keep the wheels raised and an operator ready to remove power before any real
   Agent startup or behavior test. Existing startup greetings may move hardware.
   Close standalone hardware tools; do not start a second device owner.
3. Start with voice input disabled, no camera access, and a quiet, low-volume speaker.
   Obtain consent from people nearby before the microphone tests.
4. Run the normal environment checks. Do not run a broad package synchronization
   command in the robot environment to install optional speech dependencies.
5. Use harmless test messages. Disable spoken replies when discussing private data.

## Install the optional English voice

This section downloads software and one **114 MB** voice model. It does not pair
a speaker, modify boot services, start the robot or produce sound. You explicitly
choose this download by running the commands. The existing robot environment is
unchanged. Allow additional disk space for Piper and its dependencies.

The pinned requirements target Python 3.11 on 64-bit Linux ARM, the Pi 5 platform.
The selected `en_US-ljspeech-high` voice uses a dataset identified as public domain
by its [upstream model card](https://huggingface.co/rhasspy/piper-voices/blob/1162a9173d0ce503555aed757976b7a9912eae4c/en/en_US/ljspeech/high/MODEL_CARD).
Piper itself has a GPL-3.0-or-later license; retain its notices if redistributing it.
See [third-party notices](../../THIRD_PARTY_NOTICES.md).

Create a separate environment only if its Python executable is absent:

```bash
if [ ! -x "$HOME/.local/share/ninjarobot_pi5/speech/bin/python" ]; then
  uv venv --python 3.11 "$HOME/.local/share/ninjarobot_pi5/speech"
fi
uv pip install --python "$HOME/.local/share/ninjarobot_pi5/speech/bin/python" \
  --require-hashes --only-binary=:all: -r requirements/local-speech.txt
```

Expected: the pinned packages install only into the dedicated speech environment.
No `sudo` is needed. If a compatible binary package is unavailable, stop and report
it; do not build unknown dependencies or install them into the robot environment.
An existing environment may receive the explicitly pinned versions on rerun.

Preview the voice download first, then explicitly apply it:

```bash
uv run --frozen --no-sync python scripts/prepare_speech_voice.py
uv run --frozen --no-sync python scripts/prepare_speech_voice.py --apply
```

Expected: preview writes nothing and uses no network. Apply downloads the exact
registered upstream revision, verifies SHA-256 (a content fingerprint) and retains
its model card. Rerunning verifies existing files. Different existing files are
preserved with an error; an interrupted download can be retried. No voice/model
is automatically downloaded at Agent startup.

Piper loads its model for each utterance, so expect a pause before the first sound.
This makes cancellation and cleanup straightforward but is slower than a persistent
engine. Measure actual latency on your Pi before tuning the defaults. The
[Piper command documentation](https://github.com/OHF-Voice/piper1-gpl/blob/v1.8.0/docs/CLI.md)
explains this startup cost.

## Pair and select the Bluetooth speaker

Pairing changes the operating system's Bluetooth settings. Do this yourself; the
project installer and Agent do not perform pairing or choose an output for you.

1. Log into the Raspberry Pi desktop as the account that will run the Agent.
2. Put your speaker into pairing mode using its own instructions.
3. Open the desktop Bluetooth device menu, add the speaker and complete pairing.
   Menu wording varies by Raspberry Pi OS version. Verify the speaker is connected.
4. In the desktop sound controls, choose its stereo playback profile if available
   and set a low volume. Selecting the desktop default alone is not sufficient:
   NinjaRobotPi5 also requires an explicit device name below.
5. Check the audio tools without playing anything:

   ```bash
   command -v pw-play
   command -v pw-dump
   ```

   Expected: both commands print installed program paths. If either is absent,
   complete your OS audio setup first. Raspberry Pi OS Lite may need separate
   PipeWire/Bluetooth setup; this guide does not silently replace its audio stack.
6. After starting the updated Agent under the safety conditions below, open
   **Spoken replies → List speaker outputs**, or enter `/speech outputs` in chat.
   Copy the speaker's exact `name`, such as `bluez_output.…`, into the configuration.
   This query runs inside the Agent's environment and is stronger evidence than
   seeing the speaker only in a separate desktop terminal.

Bluetooth audio can be restricted to the active logged-in user. Pairing in one
account does not guarantee access from a boot service, SSH session or another
account. First test from the logged-in desktop account. If boot startup is used,
repeat the output/status and listening tests in that deployment. No automatic
logout, lingering, system service or WirePlumber policy changes are included.
See [WirePlumber's Bluetooth session guidance](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html)
and [Raspberry Pi audio guidance](https://www.raspberrypi.com/documentation/computers/getting-started.html).

## Configure spoken output

Edit your existing private `~/.config/ninjarobot_pi5/config.toml` with your editor.
If you use `--config`, edit that selected file instead. Add or update **one**
`[speech_output]` section; do not replace unrelated settings or add duplicate tables.
Replace the example output name with the exact one returned by `/speech outputs`.

```toml
[speech_output]
enabled = false
language = "en"
piper_python = "~/.local/share/ninjarobot_pi5/speech/bin/python"
english_model = "~/.local/share/ninjarobot_pi5/voices/en/en_US-ljspeech-high.onnx"
chinese_model = ""
output_node = "bluez_output.REPLACE_WITH_YOUR_SPEAKER_NAME"
volume = 0.35
max_characters = 500
synthesis_timeout_seconds = 30.0
playback_timeout_seconds = 60.0
```

`output_node` is the stable PipeWire name, not a numeric device ID and not `auto`.
The Agent will not silently switch to HDMI or another speaker after a disconnect.
The selected [PipeWire target](https://docs.pipewire.org/page_man_pw-cat_1.html)
controls routing; the operating system and speaker's own volume also affect loudness.

Under the safety conditions above, restart your existing service to load code and
configuration. For the ordinary manually started Agent, use:

```bash
uv run --frozen --no-sync ninjarobot-agent service stop
uv run --frozen --no-sync ninjarobot-agent service start --real
```

**Startup can move the robot or activate configured microphone input.** If your
Agent is managed by boot startup, use its existing documented restart procedure
instead; do not compete with it by starting another service. Refresh the controller
page to load the new buttons. Keep `enabled = false` for initial testing. You can
later choose `true` for spoken replies at every startup after acceptance.

## Safe smoke tests

These shell checks do not start hardware:

```bash
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py
uv run --frozen --no-sync python scripts/prepare_speech_voice.py
uv run --frozen --no-sync pytest -q ninjarobot_pi5_agent/tests/test_speech.py ninjarobot_pi5_ide/tests/test_audio_output.py
```

Expected: both verifiers and all tests pass; the voice helper prints a preview.
The tests use fake routing and synthetic audio; they do not validate your speaker.

In a chat attached to the updated service, enter:

```text
/speech status
/speech outputs
```

Expected: speech starts disabled; the status separates local model availability
from playback availability. `ready: true` for synthesis checks files, not successful
inference. Missing models or an unpaired speaker must not activate the system's
emergency stop or prevent normal text-only chat.

## Speaker and controller tests

These tests produce sound. Keep voice input disabled initially.

1. Enter `/speech on`, then ask: “Please reply with: Hello, I am NinjaRobot.”
   Expected: written reply appears, then English audio from the selected speaker.
   The current speaking face runs during output and returns to the normal idle face.
   Record delay before sound, intelligibility, volume and whether the full short
   sentence plays. `/speech status` should report `played`, with hearing unverified.
2. Ask for a longer answer. During speech, click **Spoken replies → Stop speech**.
   Expected: sound stops promptly (Bluetooth may briefly drain buffered sound), text
   stays visible, and a later reply can speak again. Test while the same browser's
   chat request is still open. Stop must not wait for that request to finish.
3. Repeat, selecting **Disable spoken replies** instead. Expected: current speech
   stops and later replies remain silent. `/speech on` enables it again.
4. CLI alternative: open a second terminal with
   `uv run --frozen --no-sync ninjarobot-agent chat`, then enter `/speech stop`.
   The first interactive terminal may be busy receiving the reply; a second terminal
   or the controller provides the independent stop control.
5. During a spoken answer, switch the speaker off. Expected: audio fails or stops,
   text remains, no substitute speaker plays it, and the robot reports speech
   unavailable/stopped. It must not repeat the answer automatically on reconnect.
   Turn the speaker on, check `/speech status`, then issue a **new** request.
6. Set `english_model` temporarily to a nonexistent test path, restart safely and
   repeat one request with speech enabled. Expected: text remains and speech reports
   failure. Restore the path and restart. Do not remove your installed model.
7. With the robot stationary, test the existing Emergency Stop during speech.
   Expected: speech stops and the existing safety indication takes priority.
   Speech must not bypass a latched stop. Remove the cause and use the existing
   reviewed Resume operation; the interrupted utterance must not restart.

The automated timeouts cover stalled synthesis and playback. Do not deliberately
hang or kill unrelated OS audio services to reproduce a timeout manually.

## Microphone coordination tests

These steps use the microphone. Obtain consent; do not retain test recordings.
Use the existing separate robot microphone, not the Bluetooth speaker's headset mic.

1. With **Voice Input off**, play a reply. Expected: Voice Input remains off afterwards.
2. Explicitly enable **Voice Input**, say “Ninja” followed by a simple request, then
   stop speaking. Expected: the request is transcribed once, the reply plays after
   recording closes, and the wake listener returns afterwards. The robot must not
   treat its own reply as a second command.
3. While it is speaking, disable **Voice Input**. Expected: playback cleanup does not
   undo your choice; it remains off. Re-enable only when you choose to do so.
4. With consent, start a bounded recording and arrange for a spoken reminder to become
   due during it. Expected: speech does not truncate recording. The reminder may use
   its already reviewed display/buzzer fallback. Inspect the inbox for honest outcome
   evidence; it must not claim spoken delivery when none occurred.
5. During speech, use the explicit **Record Once** control only if you consent to that
   capture. Expected: the foreground request stops speech before recording begins.
   After it completes, ownership is released for the next requested operation.

If self-triggering occurs, stop speech and disable voice input, then report your
speaker distance, volume and timing. Full echo cancellation is not implemented;
Bluetooth buffering must be checked on your actual equipment.

## Spoken reminders

A reminder must be explicitly reviewed and confirmed. Its review includes both
speech and a display/buzzer fallback. The default `/remind 60 Practice` remains a
silent inbox notice. The Pi and Agent must be running at the due time.

1. Pick a time a few minutes in the future. In chat, enter the following after
   replacing the date/time with that future local time. The example uses Japan's
   time zone and is deliberately not a command that schedules immediately:

   ```text
   /remind-json {"title":"Phase three practice","due_at":"2026-09-09T16:00:00+09:00","timezone":"Asia/Tokyo","notification":"speech","notification_language":"en"}
   ```

2. Read the returned message, time, language and fallback. Nothing is scheduled yet.
   Copy its task ID into `/tasks confirm TASK_ID` only if the review is correct.
3. With `/speech on` and the speaker connected, wait for it to become due. Expected:
   one spoken reminder; `/tasks` reports software playback completion and does not
   claim that a person heard it. Refresh the controller task list if needed.
4. Schedule a second harmless reminder. Turn speech off before it becomes due.
   Expected: its explicitly reviewed display/buzzer fallback is used, with matching
   result evidence. There must be no silent switch to an unrelated speaker.
5. During a third spoken reminder, press Stop Speech. Expected: no fallback is played
   after this dismissal, and the record reports an uncertain/cancelled delivery
   rather than claiming success. It must not replay itself. Snooze creates a new
   review that you must confirm.
6. For a restart test, schedule another reminder well into the future and restart
   safely. Expected: its chosen language persists. Existing missed/uncertain recovery
   rules still prevent automatically replaying effects whose outcome is unknown.
7. Cancel only your test reminders with `/tasks cancel TASK_ID`. Do not clear the
   database or remove unrelated tasks to clean up the test.

## Optional Mandarin and Japanese

English is the supported first setup. The implementation also accepts a compatible
Piper Mandarin voice through `chinese_model`, with its matching `.onnx.json` file
and metadata language `zh_CN`. Enter `/speech zh` to select it, and `/speech en` to
return to English. This does not translate an English reply into Chinese: request
Chinese text from the conversation model first. A reminder's saved language takes
precedence over the current reply language.

No Chinese voice is bundled or automatically downloaded. The upstream Huayan model
card lists its dataset license as **Unknown**, so this phase does not describe it
as a cleared free-to-redistribute voice. Supply a model whose terms fit your use,
keep its provenance and license, and test a short Chinese sentence before enabling
it for normal use. Missing or incompatible models retain the written reply.
See the [Huayan model card](https://huggingface.co/rhasspy/piper-voices/blob/1162a9173d0ce503555aed757976b7a9912eae4c/zh/zh_CN/huayan/medium/MODEL_CARD).

Japanese text interaction remains available, but Japanese speech is not implemented.
The selected Piper voice collection does not provide the required Japanese option;
adding another phonemizer/engine needs its own compatibility and license review.
Do not select an English voice and treat its reading of Japanese as supported speech.

## Actuator-moving tests

Phase 3 adds no wheel movement or driver changes. A regression test of existing
behavior is optional and **moves hardware**: raise wheels, clear the area, and keep
an operator ready to remove power. Use a previously accepted short behavior while
speech is active. Expected: the explicit behavior takes priority, speech stops,
and existing movement safety remains effective. A stale synthesized reply must
not start afterwards. Roll back by stopping the behavior and disabling speech.
Do not use an uncalibrated movement for this test.

## Power-risk tests

No shutdown or power-management change was made. **Do not issue a live power-off
command for Phase 3 acceptance.** No destructive power test is required. If another
fault appears, follow the existing safety/recovery procedure; do not erase its latch.

## Troubleshooting and rollback

| Symptom | Meaning and next action |
| --- | --- |
| `check_piper_and_language_model` | Check the dedicated Python path, both model files and matching language. Status alone does not test synthesis. |
| `select_output_node` / `selected_output_unavailable` | Choose the exact current node name, reconnect the speaker and check from the Agent account. |
| `pipewire_tools_missing` | Complete supported OS audio setup; do not substitute a raw hardware path in the Agent. |
| `audio_session_unavailable` | Check the active login/session and service user. Desktop pairing is not proof of boot-service access. |
| Playback completes but nothing is heard | Check speaker volume/mute and actual routing. Software completion is not an audibility guarantee. |
| Text works but speech times out | Try a shorter sentence; check Pi load and model paths. Defaults bound synthesis to 30 seconds and playback to 60 seconds. |
| Speech stops during another operation | Foreground actions, capture, safety, or Stop Speech intentionally take priority. Send a new request if desired. |

For immediate rollback, use `/speech off` and set `enabled = false` in the speech
section for future starts. Restart under the normal safety conditions. This leaves
text chat, reminders, drivers and hardware contracts intact. Preserve your prior
configuration, voice files and private data. If reverting to pre-Phase-3 code,
remove the new `[speech_output]` section from that older code's configuration
(strict configuration rejects unknown fields). Back up the database first: older
software may not understand newly saved `notification = "speech"` reminders.
Cancel or migrate only those reviewed test records; do not erase the database.

## Record your results

| Test | Pass/fail and notes |
| --- | --- |
| English installation and selected speaker visible to Agent | Pending owner test |
| Short English audio, acceptable latency and volume | Pending owner test |
| Controller and second-terminal Stop while chat is busy | Pending owner test |
| Disconnect/reconnect with no fallback speaker or automatic replay | Pending owner test |
| Microphone pause/resume and explicit disable preserved | Pending owner test |
| Foreground priority and emergency-stop behavior | Pending owner test |
| Spoken reminder, reviewed fallback, cancellation and restart | Pending owner test |
| Boot-service access, if that deployment is used | Pending owner test |
| Optional Mandarin with a suitable model | Optional; model not supplied |

Record OS version, service launch method, speaker model and approximate latency.
Report errors without private text, credentials or media. After your confirmation,
Phase 4 can be planned/started under the existing approval workflow.
