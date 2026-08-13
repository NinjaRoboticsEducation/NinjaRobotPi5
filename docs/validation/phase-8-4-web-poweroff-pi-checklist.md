# Phase 8.4 Web and Power-Off Raspberry Pi Checklist

Phase 8.4 has passed fake-only software validation. Do not perform the final
power-risk test until Phase 8.6 has placed the reviewed helper at
`/usr/libexec/ninjarobot-poweroff` and activated its narrow authorization
policy.

## Preconditions

- Use a backed-up Raspberry Pi 5 and a stable robot power supply.
- Disconnect or raise the robot so wheels cannot leave the work surface.
- Keep the physical emergency disconnect reachable.
- Complete managed-driver verification and the full repository gate.
- Pair the test browser through the one-use pairing workflow. An unpaired
  browser must not receive web power-off authorization.

## Safe smoke tests

1. Open the dashboard in English, Japanese, Traditional Chinese, and Simplified
   Chinese, select each language, and reload.
2. Open the hamburger with touch and keyboard, cycle focus with Tab/Shift+Tab,
   close with Escape, and close through the backdrop.
3. Confirm camera, browser microphone, chat, activity, Greeting, Celebrate,
   Resume, AI camera, voice, and manual recording controls remain present.
4. Select **Power off NinjaRobot**, then select **Cancel**.

Expected: language persists; labels and accessibility text change together;
focus stays inside open dialogs; cancellation changes no service or hardware;
and power-off is disabled for an unpaired controller.

Rollback: reload or close the dashboard, or stop the agent locally. No
hardware state should change in this section.

## Device communication tests

1. With motion disarmed, exercise camera preview, one manual USB recording,
   browser speech recognition, voice enable/disable, and the activity log.
2. Confirm the selected locale reaches local transcription.
3. Verify a second browser receives `423 Locked` while the first lease is
   active.
4. Attempt power-off with an unpaired browser and expired/replayed nonces.

Expected: media ownership remains serialized, temporary media clears, the
second controller cannot act, and invalid shutdown requests stop nothing.

Rollback: disable voice, close preview, release the browser lease, and use the
terminal interface if the browser is unavailable.

## Actuator-moving tests

1. Keep wheels raised and explicitly arm AI motion only for the intended
   controller session.
2. Press/release each D-pad direction, including pointer cancel, lost capture,
   browser blur, and network disconnect.
3. Run Greeting and Celebrate, press Emergency Stop, then use confirmed Resume.

Expected: movement stops on every release/cancel path; Emergency Stop remains
visible outside the menu; Resume restores Idle but leaves AI chat motion
disarmed.

Rollback: press Emergency Stop, use the physical disconnect if software does
not respond, and do not continue until every output is safe.

## Power-risk test — only after Phase 8.6

1. Stop unrelated work and flush operator-owned files.
2. From the paired active controller, select Power Off and confirm once.
3. Observe hardware stop, voice stop, tunnel/web closure, service/store/IDE
   cleanup, and final Raspberry Pi power-off in that order.
4. Repeat with the helper deliberately unavailable or denied.

Expected: the nonce works once; modules become safe before the fixed helper;
systemd does not restart an intentional shutdown; and helper denial leaves
hardware stopped with `sudo systemctl poweroff` in the local service log.

Rollback: if the OS remains running, execute `sudo systemctl poweroff` locally.
If actuators are unsafe, use the physical disconnect. After boot, inspect logs
and filesystem/database integrity before reenabling auto-start.

## Pass/fail record

Record Pi/Raspberry Pi OS and browser versions, locale results, controller
origin, helper/policy version, cleanup order, power result, and recovery. The
hardware pass requires every applicable section to succeed without an
anonymous or replayable shutdown path.
