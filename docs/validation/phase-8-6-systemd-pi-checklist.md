# Phase 8.6 systemd and Boot Lifecycle Raspberry Pi Checklist

The deployment tests validate rendering, strict robot/versioned-MCP preflight,
`systemd-analyze verify`, fixed privilege targets, disabled-by-default
installation, start-limit recovery, IPC readiness, backup/rollback, and data
preservation. The following real Pi tests remain mandatory.

## Safe installation and smoke tests

1. Raise both wheels, open `ninjarobot-agent`, and select **12. Startup Agent
   Deployment**.
2. Select **3. Show startup Agent status**. Record installed, enabled, running,
   ready, and the structured systemd result/restart/exit fields.
3. Select **1. Install and deploy automatic startup Agent**, type `ENABLE`, and
   wait for the bounded readiness result.
4. Confirm all three artifacts are true and the result reports
   `running_now: true` and `ready: true`. Inspect the installed paths only with
   appropriate administrator access if advanced evidence is required.
5. Select **3. Show startup Agent status** and confirm installed, enabled,
   running, and ready remain true.

Expected: the service runs as the non-root robot user with one real-hardware
agent process, journald receives output, and clean stop is not restarted.

Rollback: `ninjarobot-agent deployment disable`; if necessary run
`sudo systemctl disable --now ninjarobot-agent.service`.

## Boot, device, and no-network tests

1. Keep the wheels raised and physical cutoff reachable after the confirmed
   Interactive Tool deployment.
2. Reboot with network available, then without network/ngrok, and inspect
   `deployment status` and `deployment logs --lines 200`.
3. Verify display, SPI, I2C, GPIO, camera/video, microphone/audio, state,
   configuration, and secrets access under the service account.
4. Confirm one process owns the IDE, voice, web, ngrok, and QR lifecycle; no
   competing voice/ngrok daemon exists.
5. Cause a bounded crash and verify `Restart=on-failure` plus start-rate limits;
   then issue a clean stop and confirm it remains stopped.

Expected: local QR/web recovery does not wait forever for internet; a crash
restarts with clean ownership; intentional stop/power-off does not restart.

Rollback: disable the unit and use terminal/manual service startup.

## Actuator and power-risk tests

Follow the Phase 8.5 raised-wheel Greeting test after reboot. Then follow the
Phase 8.4 paired-controller power-off test. Confirm the web path stops hardware
and resources before invoking exactly
`sudo -n /usr/libexec/ninjarobot-poweroff`; no other passwordless sudo command
works for the service user.

Expected: Greeting occurs once after pairing, orderly shutdown powers off the
Pi, and systemd does not restart the agent during the shutdown transaction.

Rollback: use Emergency Stop/physical cutoff for unsafe motion. If helper
authorization fails after cleanup, run `sudo systemctl poweroff` locally.

## Upgrade, rollback, and uninstall

1. Install a newer checkout/environment, run `deployment backup`, then
   `deployment upgrade --confirm`; confirm enabled state is preserved.
2. Stop the service and test
   `deployment rollback --backup <archive> --confirm`.
3. Run `deployment uninstall --confirm` and verify unit/helper/sudoers removal.

Expected: profiles, memories, face data, behavior assets, secrets,
configuration, databases, and backups remain. Rollback overlays only approved
user-data paths and never extracts links/devices/path traversal.

Record OS/systemd versions, service user/groups, rendered unit hash, boot and
restart outcomes, hardware access, power-off result, and recovery actions.
