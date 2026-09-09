# Phase 3: spoken replies and coordinated output — walkthrough

The baseline is **Raspberry Pi OS Lite (64-bit), with no desktop**. All essential
setup and speech controls below work from a terminal. Phase 3 is implemented and software-tested. **Development pauses before Phase 4.**
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

The default platform is **Raspberry Pi OS Lite, 64-bit, without a desktop**.
Run these steps over SSH (a remote terminal) or a locally connected keyboard.
No desktop menus, browser on the Pi, PulseAudio replacement or graphical login
are needed. The optional phone/computer web controller still works separately.

### 1. Identify the account and stop the existing robot owner

Log in directly as the normal Linux account that runs NinjaRobotPi5, not `root`.
Run these read-only checks from your checkout; adjust the first path if necessary:

```bash
cd "$HOME/NinjaRobotPi5"
id -un
id -u
cat /etc/os-release
uname -m
systemctl show ninjarobot-agent.service -p LoadState -p ActiveState -p User
```

Expected: a non-root account, architecture `aarch64`, and the OS release name.
If a system service is installed, its `User=` must match `id -un`. If it differs,
log in as that account before continuing; do not configure root's audio session.
`LoadState=not-found` means there is no installed system service; this is normal
for a manually launched Agent.

Stop the robot before changing audio services. Choose **one** command according
to the launch method. Stopping ends in-progress operations; do not do it mid-task.

For an installed system service:

```bash
sudo systemctl stop ninjarobot-agent.service
```

For a manually launched Agent:

```bash
uv run --frozen --no-sync ninjarobot-agent service stop
```

Do not use the manual launcher to compete with an installed running service.
Keep this terminal open for the following steps. Starting the Agent later can
move devices or activate configured microphone input, so raise the wheels and
have an operator ready to remove power before that step.

### 2. Install the Lite audio prerequisites

These commands change installed **OS packages** and need `sudo`. They do not
install a desktop or Piper into the robot Python environment. A package install
may start its own audio/Bluetooth service; keep the Agent stopped.

First refresh package metadata, then preview the exact package transaction:

```bash
sudo apt-get update
sudo apt-get --simulate install --no-install-recommends \
  bluez rfkill pipewire pipewire-bin wireplumber libspa-0.2-bluetooth \
  dbus-user-session jq nano
```

Read the preview. If it proposes removing your existing audio stack or unrelated
robot packages, stop and resolve that conflict instead of accepting it. Otherwise:

```bash
sudo apt-get install --no-install-recommends \
  bluez rfkill pipewire pipewire-bin wireplumber libspa-0.2-bluetooth \
  dbus-user-session jq nano
wireplumber --version
pw-play --version
```

Expected: both version commands succeed. `pipewire-bin` supplies `pw-play` and
`pw-dump`; the Bluetooth plugin supplies Bluetooth audio support. `jq` filters
structured output in later commands. This setup uses native PipeWire playback;
`pipewire-pulse` and changing the default ALSA audio route are not required here.
Use the distribution's repositories, not a mixture of Bookworm/Trixie packages.
See the [Debian PipeWire package](https://packages.debian.org/bookworm/pipewire-bin)
and [Bluetooth plugin](https://packages.debian.org/trixie/libspa-0.2-bluetooth).

### 3. Keep this user's audio session available without a desktop

PipeWire and WirePlumber run as **user services**, separate from the robot's
system service. The following explicitly enables them and allows this user's
services to remain running after SSH logout and to start at boot. This is called
*lingering*. It affects this user's other enabled user services too; record the
initial `Linger=` value for rollback.

```bash
loginctl show-user "$(id -un)" -p Linger
sudo loginctl enable-linger "$(id -un)"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
test -d "$XDG_RUNTIME_DIR" && test -S "$XDG_RUNTIME_DIR/bus"
systemctl --user status --no-pager
```

Expected: the `test` command succeeds and the user manager is reachable. A `degraded`
manager may contain unrelated failed units; inspect the named audio units below.
If the runtime directory/bus is absent or you see “Failed to connect to bus”,
log out and reconnect **directly as the same user**, then repeat the two exports
and checks. Do not create `/run/user` yourself or point it at another user's ID.
Do not run `sudo systemctl --user`; that selects the wrong user context.
See [systemd lingering documentation](https://www.freedesktop.org/software/systemd/man/252/loginctl.html).

### 4. Allow Bluetooth audio in a headless session

Without a desktop, Bluetooth pairing can succeed while no speaker appears in
PipeWire. WirePlumber's active-seat rule can cause this. Disable that rule only
for the dedicated robot account, using **one** version-specific configuration
below. This allows that account to own Bluetooth audio even when no one is
logged into a local screen. Do not run competing audio owners under other users.

Check `wireplumber --version` from step 2. Configuration formats differ:

**WirePlumber 0.5.x (typically Trixie):**

```bash
mkdir -p "$HOME/.config/wireplumber/wireplumber.conf.d"
nano "$HOME/.config/wireplumber/wireplumber.conf.d/90-ninjarobot-headless.conf"
```

If this file already exists, preserve its contents and reconcile the setting;
do not replace unrelated configuration. Put the following in the file, save with
Ctrl+O, press Enter, and exit with Ctrl+X:

```ini
wireplumber.profiles = {
  main = {
    monitor.bluez.seat-monitoring = disabled
  }
}
```

**WirePlumber 0.4.x (typically Bookworm):** use this instead, not the 0.5 fragment:

```bash
mkdir -p "$HOME/.config/wireplumber/bluetooth.lua.d"
nano "$HOME/.config/wireplumber/bluetooth.lua.d/90-ninjarobot-headless.lua"
```

Save this one line:

```lua
bluez_monitor.properties["with-logind"] = false
```

For another version, check its upstream configuration format before continuing.
The [0.5 headless configuration](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html)
and [0.4 upstream configuration](https://raw.githubusercontent.com/PipeWire/wireplumber/0.4.17/src/config/bluetooth.lua.d/50-bluez-config.lua)
are different; a Lua fragment will not configure 0.5.

Now start the user audio services and reload WirePlumber's configuration:

```bash
systemctl --user enable --now pipewire.socket wireplumber.service
systemctl --user start pipewire.service
systemctl --user restart wireplumber.service
systemctl --user is-active pipewire.service wireplumber.service
```

Expected: two `active` lines. If not, inspect the failure locally:

```bash
journalctl --user -u pipewire.service -u wireplumber.service -n 60 --no-pager
```

Correct configuration errors before pairing. Do not publish raw logs without
checking them for device names, identifiers and other private information.

### 5. Enable Bluetooth and pair the speaker

This changes Bluetooth settings, but does not start the Agent or play test audio:

```bash
sudo systemctl enable --now bluetooth.service
rfkill list bluetooth
sudo rfkill unblock bluetooth
bluetoothctl show
```

Expected: a controller is listed. A hard block cannot be fixed by `rfkill unblock`;
check the hardware/OS configuration. If no controller is listed, resolve that
first. Do not change boot files blindly.

Put the speaker into pairing mode and disconnect it from a phone if necessary.
Start the interactive Bluetooth tool:

```bash
bluetoothctl
```

At its `[bluetooth]` prompt, type the following lines **one at a time**:

```text
power on
agent on
default-agent
scan on
```

Wait until your speaker's name appears. Note its address, such as
`AA:BB:CC:DD:EE:FF`. Replace that example in **every** following line with your
speaker's actual address. These are commands inside `bluetoothctl`, not Bash:

```text
scan off
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
info AA:BB:CC:DD:EE:FF
quit
```

Answer any pairing confirmation only after verifying it is your speaker. Expected:
`Paired: yes`, `Trusted: yes`, and `Connected: yes`. Already-paired devices usually
need only `trust`/`connect`; do not repeatedly remove and re-pair them.
The [BlueZ command reference](https://github.com/bluez/bluez/blob/master/doc/bluetoothctl.rst)
describes pairing, trust and connection separately.

### 6. Choose the audio output and set a low volume

Back at the normal shell, list playback outputs without playing anything:

```bash
wpctl status
pw-dump | jq -r '.[] | select(.info.props."media.class" == "Audio/Sink") | [.id, .info.props."node.name", .info.props."node.description"] | @tsv'
```

Expected: a sink (an audio playback output) for your speaker, normally with a
`bluez_output.…` name. Keep that exact **node name** for `output_node` below.
A Bluetooth address and a PipeWire node name are different values.

For volume commands only, enter the current numeric sink ID printed in the first
column. Numeric IDs can change after reconnect; do not save one in robot config.

```bash
read -r -p "Current speaker sink ID from the list: " NINJA_SINK_ID
wpctl set-mute "$NINJA_SINK_ID" 0
wpctl set-volume "$NINJA_SINK_ID" 0.25
wpctl get-volume "$NINJA_SINK_ID"
```

Expected: roughly `Volume: 0.25`, without `MUTED`. Also lower the speaker's physical
volume. Nothing has been played yet. The Agent's configured volume is separate.
[PipeWire target selection](https://docs.pipewire.org/page_man_pw-cat_1.html) uses
the explicit node name; changing the desktop/default route is unnecessary.

If Bluetooth says connected but no sink appears, check the step 4 configuration,
user services, and plugin installation. If a device appears under **Audio → Devices**
in `wpctl status` but has the wrong profile, inspect the available profiles:

```bash
read -r -p "Bluetooth device ID under Audio Devices (not sink ID): " NINJA_AUDIO_DEVICE_ID
pw-cli enum-params "$NINJA_AUDIO_DEVICE_ID" EnumProfile
```

Find an available `a2dp-sink` profile (A2DP is Bluetooth stereo playback), then use
its actual numeric `index`:

```bash
read -r -p "Available A2DP profile index: " NINJA_A2DP_INDEX
wpctl set-profile "$NINJA_AUDIO_DEVICE_ID" "$NINJA_A2DP_INDEX"
wpctl status
```

Do not assume a fixed profile number. Keep the robot's existing USB microphone
for voice input; this guide does not switch it to the speaker's headset profile.

## Configure spoken output

### 1. Edit and validate the robot configuration

The English Piper installation above must be complete. Back up the default private
configuration, then edit it in the terminal. If your service uses `--config`, use
that actual path in all three commands instead. The backup is kept private and
is not overwritten on rerun:

```bash
test -f "$HOME/.config/ninjarobot_pi5/config.toml"
cp -pn "$HOME/.config/ninjarobot_pi5/config.toml" "$HOME/.config/ninjarobot_pi5/config.toml.before-bluetooth"
nano "$HOME/.config/ninjarobot_pi5/config.toml"
```

If the first command fails, stop and find the configuration used by your installation;
do not create an empty replacement. Add or update **one** `[speech_output]` table.
Replace the example node with the exact `bluez_output.…` name from step 6 above.
Do not overwrite unrelated settings or add a duplicate table.

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

For initial speaker testing, set the existing `[voice_input]` table's `enabled`
field to `false` too; remember its previous value. This prevents capture on startup.
Do not add a second `[voice_input]` table. Save with Ctrl+O, Enter, Ctrl+X.

Validate the file without starting devices or printing private settings:

```bash
uv run --frozen --no-sync python -c 'from ninjarobot_pi5_ide.config import load_robot_config; load_robot_config("~/.config/ninjarobot_pi5/config.toml"); print("Configuration valid")'
```

Expected: `Configuration valid`. Correct any reported error locally before starting
the Agent; errors may contain configuration details, so review before sharing.

### 2. If using the installed system service, add its audio-session path

Skip this subsection for a manually launched Agent. The project's existing
`ninjarobot-agent.service` template runs under `User=...`, but does not define
`XDG_RUNTIME_DIR`. `User=` alone does not select that user's PipeWire socket.
Use a separate **drop-in** (a small systemd override) to add audio access while
preserving the existing executable, hardware groups and security restrictions.
This changes `/etc/systemd` and needs `sudo`; it does not install another Agent.

Confirm the service account matches your login, and note its numeric UID (user ID):

```bash
id -un
id -u
systemctl show ninjarobot-agent.service -p User -p LoadState
sudo mkdir -p /etc/systemd/system/ninjarobot-agent.service.d
sudo nano /etc/systemd/system/ninjarobot-agent.service.d/20-local-audio.conf
```

If the file already exists, preserve it and reconcile the entries. In the following
example replace **every `1000`** with the number printed by `id -u`:

```ini
[Unit]
Requires=user@1000.service
Wants=bluetooth.service
After=user@1000.service bluetooth.service

[Service]
Environment="XDG_RUNTIME_DIR=/run/user/1000"
Environment="DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus"
```

Save and reload the unit definitions without starting the robot:

```bash
sudo systemctl daemon-reload
systemctl show ninjarobot-agent.service -p User -p After -p Requires -p DropInPaths
```

Expected: the same user, the matching `user@NUMBER.service` dependency, and your
`20-local-audio.conf` path. Do not remove `ProtectSystem`, `ProtectHome`, hardware
ownership checks or any other safety setting. The user audio manager must already
be enabled and healthy from the preceding steps; the override does not install or
pair the speaker. Keep this override when updating the main unit template.

### 3. Start the one existing Agent and query its own audio environment

**This step can move the robot at startup.** Raise wheels, clear nearby objects,
keep an operator ready to remove power and leave voice input off for the first test.
Choose **one** launch method:

Installed system service:

```bash
sudo systemctl start ninjarobot-agent.service
systemctl is-active ninjarobot-agent.service
```

Manually launched Agent, from the same shell/user where audio was configured:

```bash
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
uv run --frozen --no-sync ninjarobot-agent service start --real
```

Expected: the existing Agent starts normally. If it reports an existing hardware
owner or safety fault, resolve that through the normal installation/recovery
instructions rather than starting a second process or erasing safety state.

Now open the chat terminal:

```bash
uv run --frozen --no-sync ninjarobot-agent chat
```

At the `You>` prompt, enter these commands one at a time:

```text
/voice input status
/speech outputs
/speech status
```

Expected: voice input off, speech disabled, your exact selected speaker listed,
and separate synthesis/playback readiness. These queries run **inside the Agent**,
so they check its actual audio context, including the installed system service.
A sink listed by `pw-dump` in SSH alone is not enough. If this fails only in the
system service, recheck its `User`, UID and drop-in, then restart safely:

```bash
sudo systemctl restart ninjarobot-agent.service
```

The restart carries the same startup hardware risk. Run it from a second shell or
exit chat with `/exit` first. For a manual owner, use `service stop` followed by
`service start --real` instead. Do not confuse `/exit` with stopping the service.

### 4. First spoken reply and independent stop, entirely from terminals

These steps play sound, but need no desktop or browser. In chat enter:

```text
/speech on
Please reply with: Hello, I am NinjaRobot.
```

Expected: text appears and then English speech plays from the selected speaker.
Piper may take time to load the model. After the answer completes, `/speech status`
should report `played`; this does not prove the speaker was audible unless you heard it.

For the stop test, open a **second SSH terminal** as the same account, then run:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen --no-sync ninjarobot-agent chat --session speech-operator
```

Ask for a longer answer in terminal 1. While it speaks, enter in terminal 2:

```text
/speech stop
```

Expected: audio stops promptly while the text reply remains. Buffered Bluetooth
sound may take a short time to drain. `/speech stop` allows later replies to speak;
`/speech off` also keeps future replies silent. Neither command changes persisted
microphone enablement. Finish the first test with `/speech off`.

### 5. Reconnect and verify operation after SSH logout

A trusted speaker is not guaranteed to reconnect automatically. Turn it on, then
run this from a shell, entering its saved Bluetooth address at the prompt:

```bash
read -r -p "Speaker Bluetooth address: " NINJA_BT_ADDRESS
bluetoothctl connect "$NINJA_BT_ADDRESS"
bluetoothctl info "$NINJA_BT_ADDRESS"
```

Expected: `Connected: yes`. Recheck `/speech outputs` and `/speech status` in the
Agent before requesting new speech. Never replay an interrupted utterance merely
because the speaker reconnected. If the node name changed after a profile change,
update only `output_node`, validate configuration and restart safely.

With the robot stationary and speech off, exit chat and log out of SSH. Reconnect
as the same account and check:

```bash
systemctl --user is-active pipewire.service wireplumber.service
uv run --frozen --no-sync ninjarobot-agent service status
uv run --frozen --no-sync ninjarobot-agent chat
```

Then repeat `/speech outputs`, `/speech status`, and one short opted-in reply.
Expected: audio services survived logout and the existing Agent still sees the
speaker. A manual Agent is not made boot-enabled by audio lingering; only its
previously installed boot deployment provides that. Do not reboot as an unattended
test: an enabled Agent may greet/move or capture at boot. When you next perform a
supervised normal boot, reconnect the speaker if needed and repeat these checks.

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
2. Ask for a longer answer. During speech, enter `/speech stop` in the second chat terminal.
   The optional web equivalent is **Spoken replies → Stop speech**.
   Expected: sound stops promptly (Bluetooth may briefly drain buffered sound), text
   stays visible, and a later reply can speak again. Test while the same browser's
   chat request is still open. Stop must not wait for that request to finish.
3. Repeat using `/speech off` in the second chat terminal (or the optional
   **Disable spoken replies** web button). Expected: current speech
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
7. Optional controller regression: from a separate phone/computer, with the robot
   stationary, test the existing Emergency Stop during speech. The browser is not
   required on the Pi and is not required for the terminal-only speaker setup.
   Expected: speech stops and the existing safety indication takes priority.
   Speech must not bypass a latched stop. Remove the cause and use the existing
   reviewed Resume operation; the interrupted utterance must not restart.

The automated timeouts cover stalled synthesis and playback. Do not deliberately
hang or kill unrelated OS audio services to reproduce a timeout manually.

## Microphone coordination tests

These steps use the microphone. Obtain consent; do not retain test recordings.
Use the existing separate robot microphone, not the Bluetooth speaker's headset mic.

1. Enter `/voice input off` in interactive chat, then play a reply. Expected: Voice Input remains off afterwards.
2. Enter `/voice input on` in interactive chat, say “Hey Ninja” followed by a simple request, then
   stop speaking. Expected: the request is transcribed once, the reply plays after
   recording closes, and the wake listener returns afterwards. The robot must not
   treat its own reply as a second command.
3. While it is speaking, enter `/voice input off` in the second interactive chat. Expected: playback cleanup does not
   undo your choice; it remains off. Re-enable only when you choose to do so.
4. With consent, start a bounded recording and arrange for a spoken reminder to become
   due during it. Expected: speech does not truncate recording. The reminder may use
   its already reviewed display/buzzer fallback. Inspect the inbox for honest outcome
   evidence; it must not claim spoken delivery when none occurred.
5. During speech, optionally use the web controller on a separate phone/computer and its **Record Once** control only if you consent to that
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
5. During a third spoken reminder, enter `/speech stop` in the second terminal. Expected: no fallback is played
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
| `audio_session_unavailable` | Check the active login/session and service user. Check the same-user runtime path, lingering and the system-service drop-in above. |
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

### Undo the optional Lite audio setup

First use `/speech off` and keep `[speech_output].enabled = false`. If you only
want silent robot replies, stop here; no OS rollback is needed.

If you also want to undo the OS setup, stop the Agent using its existing launch
method before restarting audio services. Restore any previous content you edited;
do not delete a file that already contained your own settings. For files newly
created by this guide, rename the **applicable** file so it no longer loads.
Run only the command for your WirePlumber version:

WirePlumber 0.5:

```bash
mv -n "$HOME/.config/wireplumber/wireplumber.conf.d/90-ninjarobot-headless.conf" "$HOME/.config/wireplumber/wireplumber.conf.d/90-ninjarobot-headless.conf.disabled"
```

WirePlumber 0.4:

```bash
mv -n "$HOME/.config/wireplumber/bluetooth.lua.d/90-ninjarobot-headless.lua" "$HOME/.config/wireplumber/bluetooth.lua.d/90-ninjarobot-headless.lua.disabled"
```

If the optional system-service drop-in was newly created, disable only that file:

```bash
sudo mv -n /etc/systemd/system/ninjarobot-agent.service.d/20-local-audio.conf /etc/systemd/system/ninjarobot-agent.service.d/20-local-audio.conf.disabled
sudo systemctl daemon-reload
systemctl --user restart wireplumber.service
```

If a `.disabled` destination already exists, `-n` preserves it; inspect both files
and resolve the names manually before assuming rollback happened. Keep the speech
setting disabled and start the existing Agent only under the normal safety precautions.

Disable lingering **only if this guide enabled it and no other user service needs it**:

```bash
sudo loginctl disable-linger "$(id -un)"
```

To disconnect without removing the pairing, enter the speaker's address and run:

```bash
read -r -p "Speaker Bluetooth address: " NINJA_BT_ADDRESS
bluetoothctl disconnect "$NINJA_BT_ADDRESS"
```

Do not purge audio packages, remove unrelated pairings, or disable existing user
services merely to undo speech. Saved models and private robot data can remain.

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
