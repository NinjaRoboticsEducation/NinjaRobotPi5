# Phase 3 follow-up walkthrough and manual tests

This guide covers the speaker wizard, independent reconnection, spoken replies,
command help, task queries and updated web controls. Use Raspberry Pi OS Lite
(64-bit). A desktop on the Pi is not required. These are operator tests, not
claims that physical acceptance has already passed.

## 1. Prepare safely

Use the normal Linux account that runs the Agent. Keep the robot stationary and
its wheels raised before starting the Agent: existing startup behavior can use
hardware. Leave AI motion and microphone permissions off during these tests.
Do not start a second Agent if one already owns the robot.

Open a terminal on the Pi and enter:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen --no-sync ninjarobot-agent service status
systemctl show ninjarobot-agent.service -p LoadState -p ActiveState -p User
```

Expected: you can identify whether the Agent is manually managed or a system
service. A missing system service is normal for a manual installation.

Install the optional Bluetooth Python support without removing existing packages:

```bash
uv sync --frozen --inexact --package ninjarobot-pi5-ide --extra bluetooth
uv run --frozen --no-sync ninjarobot-ide-tool bluetooth --help
```

Expected: `connect`, `status`, `service` and `disconnect` are listed. This installs
software but does not start the Agent, pair devices or play audio. New complete
hardware installations also include this extra.

If PipeWire (the audio service), WirePlumber (its device manager), BlueZ (Bluetooth)
or the local voice are not installed, first follow the existing
[Lite audio prerequisites](refinement_phase3_walkthrough_260909.md#pair-and-select-the-bluetooth-speaker)
and [English voice setup](refinement_phase3_walkthrough_260909.md#install-the-optional-english-voice).
The wizard does not silently install OS packages or change privileged settings.
The earlier guide's `bluetoothctl` instructions remain a manual troubleshooting
alternative; use the wizard below for normal pairing.

## 2. Connect and save the speaker

This step changes Bluetooth pairing/trust, starts already-installed user audio
services and saves the selected speaker. It does not initialize robot devices.

Put the speaker in pairing mode, then run:

```bash
uv run --frozen --no-sync ninjarobot-ide-tool bluetooth connect
```

Alternatively, run `ninjarobot-ide-tool` and choose **8 — Bluetooth Speaker
Connection**. Existing menu numbers, including **7 — Quit**, are preserved.
If you already ran hardware in that IDE session, exit and reopen the tool first.

1. Wait for the ten-second scan. Known devices may also appear.
2. Enter the number beside your speaker. Use `r` to rescan or `q` to cancel.
3. Follow any PIN or number-confirmation prompt for that selected device.
4. Wait for **Connected and saved**. The wizard verifies an audio output, not
   just a Bluetooth connection. Existing voice, volume and microphone settings
   are preserved. An existing configuration receives a private
   `config.toml.before-speaker` backup if that backup does not already exist.
5. Review the displayed user service. Enter `y` to enable automatic reconnection
   independently of the Agent. Entering `n` saves the speaker but does not enable
   the reconnect service. No sound test runs automatically.

For a non-default configuration, put `--config` before `bluetooth` on every IDE
command, for example:

```bash
uv run --frozen --no-sync ninjarobot-ide-tool --config "$HOME/my-robot.toml" bluetooth connect
```

Use your actual file path. The wizard writes that same file. A concurrent change
detected during setup causes a save refusal instead of replacing the changed
configuration. If pairing succeeded but a later step failed, keep the existing
bond and retry after correcting the reported issue.

## 3. Check independent reconnection

Inspect the saved selection and user service:

```bash
uv run --frozen --no-sync ninjarobot-ide-tool bluetooth status
systemctl --user status ninjarobot-speaker-reconnect.service --no-pager
loginctl show-user "$USER" -p Linger
```

Expected: the selected address is correct and the reconnect service is active.
`Linger=yes` allows user services to keep running after logout and start at boot.
If it says `no` and you want that behavior, this explicit OS change enables it:

```bash
sudo loginctl enable-linger "$USER"
```

This does not enable the Agent at boot. The Pi, Bluetooth and user audio services
must remain powered and available. The helper retries with a delay up to 60 seconds;
it cannot force a speaker away from another connected phone or computer.

Test these cases separately:

1. With the Agent stopped, switch the speaker off for at least ten seconds, then
   on. Wait up to 90 seconds. Run the status command above and `bluetoothctl info`
   with your saved address. Expected: `Connected: yes` without starting the Agent.
2. Start the Agent through your normal existing method and repeat the speaker
   power cycle. Expected: connection returns and a **new** spoken request works.
   An interrupted reply must not replay automatically.
3. Optional later boot test: during a planned reboot, check the helper after
   login. Test both speaker-before-Pi and Pi-before-speaker power orders.
   This guide does not require a reboot during software validation.

To enable the helper later, preview first, then apply:

```bash
uv run --frozen --no-sync ninjarobot-ide-tool bluetooth service
uv run --frozen --no-sync ninjarobot-ide-tool bluetooth service --apply
```

To disconnect deliberately and keep it disconnected across reboots:

```bash
uv run --frozen --no-sync ninjarobot-ide-tool bluetooth disconnect
```

This disables the helper before disconnecting the saved speaker. A disconnect
made using another Bluetooth application may be undone while the helper remains
enabled. Use `bluetooth service --apply` to restore automatic reconnection.

## 4. Test complete spoken replies

These steps produce sound. Start with a comfortable speaker volume. Restart an
already-running Agent through its normal management method to load the updated
code and saved output. For a manually managed Agent, use its existing service
stop/start commands; for a system-managed Agent, use the installed system service.
Do not mix the two owners. Follow the original
[Agent startup instructions](refinement_phase3_walkthrough_260909.md).

Open chat, with a second chat terminal available for stopping speech:

```bash
uv run --frozen --no-sync ninjarobot-agent chat
```

Enter these inside chat, not in the Linux shell:

```text
/speech status
/speech outputs
/speech on
Please reply exactly: One, two, three. Hello, I am NinjaRobot.
```

Expected: the entire written and spoken sentence starts with **One, two, three**.
`/speech status` distinguishes voice readiness from speaker readiness. A successful
playback process does not prove what you heard; record your listening result.

Repeat immediately, after 60 seconds of silence, and after switching the speaker
off and on. Compare the first three words in each case. The implementation adds
0.5 seconds of silence at the beginning of the same Bluetooth audio stream.
Tests verify that every original audio sample remains intact. Some speakers gate
silent input, so this is a startup buffer, not a guarantee of a physical fix.

If opening words are still lost, record whether the failure is cold-only or every
reply. In the private `[speech_output]` section, the optional
`bluetooth_lead_in_seconds` setting accepts `0.0` through `2.0`. Back up the file,
try `1.0`, restart safely and repeat the same sentence. Set `0.0` for a comparison
without the buffer. Do not add duplicate sections or increase message/audio limits.
Report the comparison instead of repeatedly increasing the delay.

During a longer reply, enter in the second chat terminal:

```text
/speech stop
```

Expected: sound stops, the text remains and a later reply can still speak.
Then test `/speech off`: current speech stops and later replies stay silent.
Switch off the speaker during speech: no other output should play the remainder,
and reconnection must not replay the interrupted reply.

## 5. Test command help

In chat, enter:

```text
/help speech
/guide 1
/guide 4
Can you turn on the audio and voice out your answer?
How do I connect a Bluetooth speaker?
```

Expected: simple instructions, exact commands, and no claim that help changed a
setting. `/help` and `/guide` work without a model call. Natural-language help uses
the new read-only command-help skill when the model and help tool are available.
Enabling speech is a separate direct `/speech on` or web-button action. Help must
not enable a microphone, arm movement or create a task.

## 6. Test web controls and layout

Use the existing secure web controller on your phone or computer; do not expose
its port through router forwarding. Reload the page after the update.

1. Confirm **A — Speech ON**, **B — Speech OFF**, Emergency Stop and Resume appear.
   The speech dropdown and Guided Checks menu section should be absent.
2. Press A. Check `/speech status` in chat: enabled should be true. Press B:
   enabled should be false. Neither button enables voice input. State changes
   made in chat should appear in the web controls within about five seconds.
3. Type a long, multi-line prompt without sending it. Open and close the menu,
   send the prompt and receive a long reply. Controls must retain usable sizes;
   long replies scroll inside the transcript. On a short screen or with the
   keyboard open, scroll the main controller to reach all panels.
4. On a portrait phone, open and close the keyboard. It must not trigger a false
   landscape warning. Physically rotating a small touch device to landscape
   should still show the existing portrait safety restriction.
5. During a long reply, press B. It must work without waiting for chat to finish.
6. Repeat in your normal Android Chrome or iPhone Safari browser and record the
   device, browser version and any hidden or unreachable controls.

Greeting and Celebrate remain available as robot behaviors; their A/B shortcuts
were replaced. No behavior definition or managed driver was removed.

## 7. Test scheduled-task answers

Use the same chat/profile for all steps. Preview a silent local task:

```text
/remind 600 Phase 3 test reminder
```

Review its exact time and message. Copy the returned task ID into
`/tasks confirm ID` only if you want to schedule it. Then ask:

```text
/tasks
Is there any scheduled task in your memory?
```

Expected: the model's answer includes each matching task's ID and content, without
a message-length error. Draft reminders are not described as scheduled. Confirmed
reminders require the Pi and Agent running at delivery time. A different profile
must not see another user's tasks.

For multiple records, ask for the next page. The model tool returns ten records
by default, at most twenty, and a next-page value. It excludes internal execution
records from each summary. Pages are live views, so concurrent changes can alter
what is visible. Use `/tasks cancel ID` to cancel each test reminder you created;
do not delete your task database.

## Acceptance record and rollback

Record pass/fail separately for: safe command/help checks; speaker connection;
reconnection with Agent stopped; reconnection with Agent running; cold/warm first
words; stop/off; mobile keyboard/layout; task ID/content and ownership.

No new actuator-moving test is required for this follow-up. Keep existing motor
acceptance separate and operator-controlled. No camera/microphone capture or
power-off test was run or is required here.

Rollback: turn speech off; use `bluetooth disconnect` to disable reconnect; restore
only reviewed private configuration fields or your private backup while the Agent
is stopped, then restart through its normal owner. Do not remove pairing records,
voice models, task data or managed driver files to undo these changes. If you
changed lingering, disable it only after checking that no other user services need
it. Report failures with their test step; omit private configuration and chat data.
