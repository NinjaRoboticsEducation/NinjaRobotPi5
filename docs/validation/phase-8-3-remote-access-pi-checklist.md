# Phase 8.3 Raspberry Pi Remote-Access Validation

Status: software/fake-tunnel pass; live ngrok account, public network, and
long-run recovery validation pending operator execution.

## 1. Scope of validation

Validate explicit ngrok setup, private credentials, end-to-end TLS, one-use
passwordless pairing, remote WebSocket lease control, replay/origin/Host
rejection, tunnel failure/recovery, account limitations, and complete removal.

## 2. Safety notes

- Keep AI motion disarmed and the wheels raised during remote controller tests.
- Do not expose/forward local port 8443 through the router.
- Never paste the authtoken, pairing fragment, session cookie, remote marker,
  private config, or provider response body into logs or issue reports.
- Anyone holding a current pairing URL temporarily possesses the remote pairing
  credential; rotate immediately after accidental sharing.
- ngrok is an external service and may impose interstitials, limits, or charges.

## 3. Safe smoke tests

```bash
uv sync --frozen --extra hardware
uv run python scripts/verify_immutable_drivers.py
uv run --frozen pytest -q \
  ninjarobot_pi5_agent/tests/test_pairing.py \
  ninjarobot_pi5_agent/tests/test_remote_access.py \
  ninjarobot_pi5_agent/tests/test_web.py
uv run --frozen ninjarobot-agent remote status
```

Expected: tests and driver verification pass. Before setup, status is disabled
or reports the missing executable/token without downloading anything.

## 4. Communication/interface tests

With the agent service running, explicitly configure and activate:

```bash
uv run --frozen --extra hardware ninjarobot-agent remote configure
uv run --frozen --extra hardware ninjarobot-agent remote activate
uv run --frozen ninjarobot-agent remote status
uv run --frozen ninjarobot-agent remote pairing-url
```

Expected: the token prompt is hidden/double-entry; private files are mode 0600;
status exposes only the HTTPS origin and safe state; pairing URL contains a
fragment but no authtoken. Open it from a device outside the LAN. Complete any
provider interstitial, then expect one automatic pairing exchange and the
normal dashboard without a username/password prompt.

Confirm a second anonymous browser receives a pairing page/401 rather than
assets or a WebSocket. Reusing the consumed URL must fail. A wrong Origin,
modified Host, copied cookie on another origin, expired link, or client-supplied
transport marker must fail. Rotate pairing and confirm the first browser loses
authorization, then pair the intended browser again.

Disconnect the network for one minute. Expected: local terminal/LAN web/hardware
remain available, safe status reports a network/tunnel category, and recovery
uses bounded backoff. Restore networking; expected: a new exact endpoint and
pairing code appear without replaying any completed physical action.

Leave the tunnel active for at least two hours and record process count, CPU,
RSS, reconnects, and browser lease behavior. Expected: one ngrok process, one
endpoint, bounded logs/state, no duplicate controller, and no secret values.

## 5. Actuator-moving tests

Phase 8.3 adds no actuator behavior. Keep motion disarmed and verify that remote
movement/chat motion remains denied until the existing **Arm AI motion** action
is explicitly confirmed. If testing an armed remote move, raise wheels, clear
space, use stable power, and keep an accessible cutoff; expect one bounded IDE
action and immediate revocation when the controller lease is lost.

## 6. Expected outcomes

- Unattended startup never downloads or updates ngrok.
- Upstream traffic stays HTTPS and validates the NinjaRobot local CA.
- Anonymous remote users cannot fetch assets, open control WebSockets, arm
  motion, use camera/microphone, or invoke later power controls.
- Pairing tokens are one-use/short-lived and session cookies are revocable.
- Host spoofing cannot bypass the ngrok-injected transport marker.
- Tunnel/account failure cannot stop local robot operation.
- Status, events, SQLite, shell output, and service logs contain no secrets.

## 7. Pass/fail checklist

- [ ] Explicit install/configuration succeeds with mode-0600 private files.
- [ ] No unattended install/download occurs.
- [ ] Public origin is HTTPS and upstream CA verification succeeds.
- [ ] First pairing succeeds without browser login credentials.
- [ ] Replay, expiry, wrong-origin, Host spoof, and anonymous WebSocket fail.
- [ ] Rotation and deactivation revoke existing browser sessions.
- [ ] Exclusive controller lease remains enforced after pairing.
- [ ] Network loss preserves local operation and later recovers cleanly.
- [ ] Two-hour soak has one process/endpoint and bounded resources.
- [ ] Logs/status/database contain no token, fragment, cookie, or marker value.
- [ ] Credential removal leaves user profiles/memory/behaviors untouched.

Any anonymous remote control path, secret leak, TLS-verification bypass, or
duplicate endpoint/process is a v1.0.0 release blocker.

## 8. Rollback steps

```bash
uv run --frozen ninjarobot-agent remote deactivate
uv run --frozen ninjarobot-agent remote remove-credentials --confirm
```

Expected: exact endpoint/process stopped, browser sessions revoked, private
credentials/config removed, and the installed executable retained. If the
service is unavailable, set `[remote_access].enabled = false` in the private
robot config, validate it, restart locally, and then run credential removal.
Do not delete profiles, memory databases, safety state, or managed-driver files.
