# Phase 8.5 QR Onboarding Raspberry Pi Checklist

Phase 8.5 software tests validate exact QR decoding and exactly-once Greeting.
Complete these checks on Raspberry Pi 5 before public-release acceptance.

## Preconditions

- Back up the SD card and complete the repository/immutable-driver gate.
- Use the reviewed 240×320 ST7789V wiring and stable robot power supply.
- Raise driven wheels, clear servo travel, and keep the physical power cutoff
  reachable because Greeting may move actuators.
- Trust the NinjaRobot local CA in the test browser.
- Test once without ngrok and once with configured ngrok remote access.

## Safe smoke tests

1. Start the real-hardware agent with onboarding enabled and remote access
   disabled.
2. Confirm no Greeting, buzzer, or servo action occurs at service start.
3. Confirm the display shows a centered black-on-white QR with an undisturbed
   white border.
4. Scan it and verify the browser reaches the local `.local` HTTPS controller.
5. Load `/health`, `/assets/app.js`, and `/` without completing pairing from a
   second browser.

Expected: only the one-use QR link exchanges a session; probes/static loads do
not trigger Greeting; unpaired assets and WebSocket control are denied while
onboarding is active.

Rollback: stop the agent locally. No actuator should have moved yet.

## Remote/fallback communication tests

1. Enable ngrok and restart. Confirm **Connecting…** appears while the tunnel
   starts, Local Web is not prematurely rejected, then the remote pairing QR
   replaces it and Local Web status no longer exposes a URL.
2. Keep the remote tunnel healthy without connecting a browser beyond the
   token lifetime; confirm the QR refreshes and the newest scan works.
3. Force a real ngrok configuration/network/tunnel failure. Confirm the display
   changes to a local `.local` QR while retry continues.
4. Restore ngrok before connecting. Confirm the remote QR replaces the local
   QR and the old local code/session cannot authorize the new endpoint.

Expected: a healthy ngrok endpoint waits indefinitely; local fallback happens
only on actual failure; endpoint replacement invalidates old pairing access;
no URL/token appears in normal status or event logs.

Rollback: deactivate ngrok locally, then explicitly start Local Web and use its
newly displayed local code.

## Actuator-moving Greeting test

1. With wheels raised and workspace clear, scan the current QR and complete
   browser pairing.
2. Observe the accepted WebSocket connection, display clearing, Greeting, and
   transition to silent Idle.
3. Refresh/reconnect the same browser and attempt a simultaneous second
   browser connection.

Expected: Greeting executes exactly once per service process and only after
the first paired exclusive controller lease; reconnect and `423 Locked`
attempts do not replay it. Idle begins only after successful Greeting.

Rollback: press Emergency Stop or use the physical cutoff if motion is unsafe.

## Failure and recovery tests

Inject one failure at a time in QR rendering/display write and Greeting. Confirm
the stable **Error** display, degraded startup status, redaction-safe event,
revoked AI/voice motion, attempted servo stop, and absence of a false Idle or
success report. Recover locally, correct the fault, and restart the service;
the failed process must not retry Greeting autonomously.

## Pass/fail record

Record Pi/Raspberry Pi OS, display and browser models, QR decode result, remote
and local URLs without fragments, fallback/recovery timing, Greeting count,
Idle result, and any safety intervention. Hardware acceptance fails if a probe
triggers Greeting, an old endpoint remains authorized, or Greeting repeats.
