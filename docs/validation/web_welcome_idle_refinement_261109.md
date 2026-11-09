# Connected welcome and Idle refinement

This 9 November follow-up implements the owner's revised welcome contract after
physical testing of the previous reconnection feature. Every new exclusive
browser lease gets Greeting, followed by repeating silent Idle. A reload or
Agent/Game Pad navigation reconnecting the same lease during grace does not
repeat its completed welcome. A replacement user after expiry/release gets a new
lease and therefore a fresh Greeting.

## Findings and scope

Code inspection confirmed three relevant defects or limitations:

1. `web_app.py` awaited `on_authenticated_controller` (including the full hardware
   Greeting) before sending the lease or servicing heartbeats. A slow welcome
   could expire a valid attachment and run the reserved-loss presentation, whose
   text is “Connecting…”. The standard asset has two two-second visual stages;
   actual driver initialization and scheduling can add time. No current robot
   logs or timing measurements were inspected here, so timeout is a demonstrated
   code vulnerability rather than a measured explanation for the owner's run.
2. `onboarding.py` used `_greeting_attempted` as a service-wide once-only guard and
   intentionally skipped Greeting for additional QR connections. That behavior
   matched the earlier plan but conflicts with the owner's updated requirement.
3. Every delayed `remote_ready` event called endpoint invalidation unconditionally.
   A controller already authenticated to the newly ready healthy tunnel could be
   revoked by that same delayed event, producing the loss-time “Connecting…” text.
   This is a confirmed race in code, not a claim about which event occurred on the
   physical robot. Ready/error/disabled events also carry their generation, so
   old events cannot switch the new connection back to fallback or waiting.
   Endpoint generations now distinguish valid attachments from
   genuinely replaced or disabled tunnels, even when a URL is reused.

The display text is not simply renamed: it remains appropriate during an actual
connection reservation. The fixes prevent false disconnects and explicitly
restore Idle after a successful welcome. No hardware transport, driver, boot
configuration, dependency, pairing security boundary or safety threshold changes.

## Implementation and phase gates

| Phase | Modules | Contract and validation |
| --- | --- | --- |
| Welcome lifecycle | `onboarding.py`, `service_main.py` | Lease identity determines welcome; duplicate callbacks/same-lease reconnect do not repeat; first successful startup completes once, including after a cancelled welcome |
| Transport and remote status | `web_app.py`, `remote_access.py`, `service_main.py` | Cancellable connection-owned welcome runs alongside heartbeat receive; normal actions await welcome and then revalidate lease; stops remain prompt; current endpoint generation survives stale ready events |
| Documentation and final checks | README and `2026-11-09-02` raw successors | Updated per-controller welcome, manual acceptance and actual results; preserve all previous sources and leave ingestion/review to owner |

Tests use fake time, blocked welcome barriers, simulated controllers and a fake
tunnel. The WebSocket regression advances the clock past the original lease
expiry while a welcome remains blocked, sends heartbeats successfully and proves
queued behavior waits until welcome completes. Additional tests cover 100 new
controller welcomes, same-lease reconnect, duplicate callbacks, cancelled first
welcome, delayed ready events, deactivation and same-URL endpoint replacement.

## Manual acceptance

No live recording, sound, movement, ngrok, installation, service restart or power
action ran in repository validation. The shared Agent/IDE changes apply to
DFR0566 + X1208, Fusion HAT+ and PCA9685; physical acceptance remains pending.

1. When safe, restart your existing configured Agent to load the updated code.
   Keep wheels raised and mechanisms unloaded; an operator must be ready to stop
   the robot. The existing Greeting includes sound; use a suitable volume.
2. Scan the current ngrok QR using browser A. Expect one Greeting, then continuous
   silent Idle. Leave it untouched longer than 15 seconds: it must remain connected
   and must not switch to “Connecting…”. Confirm the browser indicates control.
3. Ask for a harmless expression and confirm the robot returns to Idle afterward.
   Navigate between Agent and Game Pad inside grace: no unnecessary new Greeting.
4. Close A. After the reconnect reservation and cleanup, scan with browser/profile
   B. Expect a new Greeting and then repeating Idle. Repeat A/B handoff several
   times; service PID and healthy endpoint remain unchanged.
5. Disconnect during a welcome, then reconnect. The next successful welcome must
   finish in Idle; no old callback may repaint it after successful connection.
6. Separately test existing emergency stop. Its warning and latch take precedence;
   reconnect does not clear them or restore AI motion/camera permission.

| Validation category | Expected outcome / safety boundary |
| --- | --- |
| Safe smoke | Offline tests and static checks pass |
| Device communication | Authorized QR pairing, stable connection and repeating Idle; pending operator test |
| Actuator movement | No new actuator test needed; existing safety protections unchanged; Greeting runs only after operator connects |
| Audio/capture | Greeting sound is expected; no microphone/camera capture required |
| Power risk | No shutdown test needed; browser departure never powers off Pi |

Rollback: stop the service when safe and restore the coherent application revision,
then restart it and reload the browser. Preserve private settings, conversations,
paired credentials and task data. No driver or boot rollback is needed.

## Documentation and evidence status

The registered map still points to the 4 November manuals. New raw successors
`2026-11-09-02` supersede the 9 November reconnection description for this revised
welcome contract. Both READMEs link to them. The MCP manual and third-party
notices require no semantic change: tool contracts and dependencies are unchanged.
No ingestion, semantic review, registration or fingerprint refresh is performed.

## Automated results

- Full root suite: **1,157 passed**, one existing Starlette dependency warning,
  56.25 seconds.
- Separate managed-driver processes: servo **159**, buzzer **68**, camera **27**,
  display **65**, microphone **92**, distance **71** passed. Existing microphone
  `audioop` deprecation warning remains.
- Ruff lint and format passed (**480 files**); mypy passed (**122 source files**).
- Compileall, immutable-driver verification, workspace-source verification and
  `git diff --check` passed. No managed-driver baseline or authorization edit.
- Changed documentation relative links passed; registered manual hashes unchanged.
- Wiki search/check/lint unavailable: separate wiki environment missing. No setup,
  ingestion, semantic review or fingerprint refresh ran.
- Physical robot/browser/network/audio acceptance: not performed in this task.

Two earlier assertions expected only the post-pairing Idle restore. They now
include the explicit Idle restore following the initial welcome. Existing pairing,
exclusive control, motion/safety, expression and shutdown regressions remain in
the passing full suite.
