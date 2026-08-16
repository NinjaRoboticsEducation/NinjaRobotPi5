# Boot automatic-start and QR runtime validation

Use this checklist on the Raspberry Pi 5 after updating the public clone. It
validates the repaired systemd-owned `lgpio` runtime directory and truthful QR
startup readiness without mixing software checks with actuator or power risks.

## Safety and privacy

> [!CAUTION]
> Raise both drive wheels before starting. Keep clear of the servos and be ready
> to disconnect robot power. Do not test Power Off until every earlier section
> passes.

- Do not paste the ngrok authtoken, pairing URL, TLS key, captured media, or
  private configuration into a report.
- QR and Greeting checks use the display and buzzer. They do not require AI
  motion to be armed.
- The commands below inspect or deploy software. Only the explicitly marked
  reboot and power sections affect the operating-system lifecycle.

## 1. Update the public clone

From the public test checkout, preserve any intended local work, then update:

```bash
cd "$HOME/NinjaRobotPi5_Public/NinjaRobotPi5"
git status --short
git pull --ff-only
uv sync --frozen --extra hardware
```

Expected result: the worktree is clean before the pull, the pull completes by
fast-forward, and locked dependencies synchronize without an error. If the
worktree is not clean, stop and review those files; do not discard them.

Verify repository integrity without opening hardware:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python scripts/verify_workspace_driver_sources.py
```

Expected result: both commands pass and every managed driver resolves to this
public checkout.

## 2. Reinstall the deployed unit

Run `ninjarobot-agent`, select **Startup Agent deployment**, then select
**Install and deploy automatic startup Agent**. Read the safety prompt and enter
`ENABLE`.

Expected result: installation succeeds with `running_now: true` and
`ready: true`. This action is necessary even if startup was already enabled,
because `/etc/systemd/system/ninjarobot-agent.service` is a deployed copy and is
not changed by `git pull` alone.

Return to **Show startup Agent status** and verify:

- `installed`, `enabled`, `running`, and `ready` are `true`;
- `systemd.ActiveState` is `active` and `systemd.Result` is `success`;
- all three deployment artifacts are `true`;
- the recorded working directory and Python executable point into the public
  clone.

Rollback on failure: select **Disable and stop automatic startup Agent**. This
preserves profiles, memory, behaviors, configuration, secrets, and calibration.

## 3. Safe smoke check before reboot

Keep the wheels raised. The display should show the ngrok pairing QR when the
tunnel is ready. If remote access is disabled or genuinely unavailable, it
should show the local HTTPS pairing QR instead.

Inspect the bounded deployment journal only if the QR is absent:

```bash
ninjarobot-agent deployment logs --lines 200
```

Expected result: the journal includes `Startup pairing QR is displayed` and has
no `xCreatePipe`, `.lgd-nfy`, `Read-only file system`, traceback, or repeated
restart error. The earlier ngrok wait message is normal while a tunnel starts.

## 4. Reboot and validate automatic startup

> [!WARNING]
> This step reboots the Raspberry Pi. Keep wheels raised and close unrelated
> hardware tools first.

Reboot once:

```bash
sudo reboot
```

After SSH reconnects, do not manually start the Agent. Wait up to 90 seconds,
then open `ninjarobot-agent` and inspect **Agent Service Status** followed by
**Startup Agent deployment → Show startup Agent status**.

Expected result:

- systemd started the Agent without manual intervention;
- `running` and `ready` are `true`;
- the display shows the remote QR, or the local fallback QR only when ngrok is
  unavailable;
- the service has not entered a restart loop.

If the result fails, do not repeatedly reboot. Save the redacted output of
**Show startup Agent status**, run the bounded deployment-log command from the
previous section, and disable the deployment before troubleshooting.

## 5. Device communication check

Scan the displayed QR and complete browser pairing. Do not arm AI motion.

Expected result: the QR clears, Greeting face and sound run exactly once, and
the display transitions to a stable Idle face. Refreshing or reconnecting the
same browser must not replay Greeting. Camera, microphone, servo movement, and
distance sensing are outside this startup repair and need no validation here.

Rollback on display or buzzer failure: use the Interactive Tool to stop the
Agent, then disable automatic startup. Inspect wiring and the deployment log
without opening a standalone driver while the Agent owns hardware.

## 6. Optional actuator-moving regression

This repair does not alter actuator code. If release acceptance requires a
motion regression, keep both wheels raised, explicitly use **Arm AI motion**,
run one short known behavior, then disarm motion.

Expected result: the known behavior executes once and returns to Idle. Stop
immediately if motion is unexpected, noisy, or fails to stop.

## 7. Power-risk regression

> [!CAUTION]
> Run this last. It deliberately powers off the Raspberry Pi and requires the
> validated Pi 5/X1208 shutdown setup from the Installation Guide.

Only continue when startup status reports `full_poweroff.ready: true`. In the
paired Web interface, open **Power off NinjaRobot**, choose **Cancel** once,
then repeat and confirm **Power off**.

Expected result: the Agent and Raspberry Pi OS shut down cleanly, the X1208
removes the Pi power rail, SSH becomes unreachable, and the Pi remains off.
Reconnect external power according to the X1208 instructions to recover.

## Pass/fail report

Record only these non-secret results:

```text
Public clone commit:
Deployment reinstall: PASS / FAIL
Pre-reboot QR: remote / local fallback / FAIL
Post-reboot automatic start: PASS / FAIL
Post-reboot deployment ready: PASS / FAIL
No lgpio read-only error: PASS / FAIL
Greeting once then Idle: PASS / FAIL
Optional raised-wheel motion: PASS / NOT RUN / FAIL
Power-off regression: PASS / NOT RUN / FAIL
Notes (no tokens, URLs, media, or private config):
```
