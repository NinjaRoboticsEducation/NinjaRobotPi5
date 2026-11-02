# Multi-HAT runtime remediation validation — 2 November 2026

Implementation follows the owner-refined
[phased plan](../../DevelopmentPlanDoc/NinjaSunFounderIntegrationImplementation_261102.md).
The owner authorized execution and the narrow Phase 4 managed-driver exception.
Only the SunFounder backend and its existing backend test file changed inside
managed libraries. The immutable baseline was preserved; approved hashes were
recorded after the isolated driver suite passed.

Previous approved hashes (before this repair):

| Managed file | Previous approved SHA-256 |
| --- | --- |
| SunFounder backend | `e5160ebdada065ed1233c2147539f54a1ff519c72b02dc75495abc8d26927157` |
| Backend tests | `4a018435db19d557366944a08f6cdafd6138676d8602c40ecc5800e03841ec48` |

Current hashes, owner authorization date and reason are recorded in
`authorized_driver_changes.json`. The backend was absent from the original import
baseline; its baseline entry therefore remains null.

## Software scope and evidence

- Phase 0: clean starting worktree; baseline driver/workspace verification,
  compilation, Ruff lint/format, mypy and root pytest exercised.
- Phase 1: explicit `proxy_headers=False`; loopback and forged-LAN classification
  checks plus existing pairing, remote and web tests (54 passed).
- Phase 2: distinct battery reason, bounded persisted fault detail, finite/plausible
  telemetry checks and sysfs-informed Fusion preset; legacy Pi reason preserved.
  The old cutoff assertion was updated to expect the new battery reason.
- Phase 3: embedded ALSA health/playback alignment, kernel speaker control without
  raw I2C write, speech reason/stage, transient stop cleanup. Persistent-stop
  boundary tests now request a persistent latch explicitly; a transient stop is
  intentionally allowed to release its local gate. Focused regression: 117 passed.
- Phase 4: independent initialization and all-channel packet fixtures for both
  register layouts; isolated pi5servo suite: 141 passed. IDE config/import/setup
  regression: 70 passed. Complete root gate: 1,096 passed.
- Phase 5: combined catalogs, destination-bound credentials, route-aware selection
  through CLI/IPC/runtime/persistence, keyless local onboarding, duplicate-name
  handling and partial source failure tests. Complete root gate: 1,103 passed.
  Further metadata alignment is covered by the final root gate below.

Required root gate sequence:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python scripts/verify_workspace_driver_sources.py
uv run --frozen python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
git diff --check
```

Failures encountered during implementation were repaired before handoff: Ruff
line wrapping, an optional ALSA-device type annotation, expected old battery/stop
semantics, and provider-menu/selection fixtures. No baseline failure was attributed
to the patch. Some early gate attempts failed; passing results below refer to the
repaired final tree. Root pytest emits an existing Starlette/httpx deprecation
warning, which does not affect the passing result.

Final results (all required commands above exited successfully):

| Gate | Result |
| --- | --- |
| Immutable drivers | PASS; baseline unchanged, two approved repair hashes updated |
| Workspace driver sources | PASS; all six libraries execute from this checkout |
| Compilation | PASS |
| Ruff lint and formatting | PASS |
| Mypy | PASS; 121 source files |
| Root pytest | 1,104 passed; one existing deprecation warning |
| pi5buzzer (separate process) | 68 passed |
| pi5camera (separate process) | 27 passed |
| pi5disp (separate process) | 65 passed |
| pi5mic (separate process) | 92 passed; one warning |
| pi5servo (separate process) | 141 passed |
| pi5vl53l0x (separate process) | 71 passed |
| Diff whitespace | PASS |
No live hardware command is part of these automated tests.

## Documentation disposition

New complete successor sources are under `raw/articles/ninjarobotpi5/2026-11-02/`
and `raw/notes/ninjarobotpi5/2026-11-02/`. Earlier registered originals are unchanged.
README links identify successors as pending owner acceptance. The registered map,
source catalog, compiled wiki pages and review records were not updated. No wiki
ingestion, semantic review, normalization or fingerprint refresh was performed.
No dependency was added, so third-party notices need no dependency update.

## Raspberry Pi validation — operator checklist

Actuator, audio, remote-access and power-risk acceptance results are **NOT RUN**.
Read-only host preflight was performed: `aarch64`, `/dev/i2c-1` present,
Fusion sysfs absent, no `fusion_hat` row found in `/proc/modules`, and
`vcgencmd get_throttled` returned `throttled=0x0` at the observation time.
This idle snapshot does not establish loaded power quality or board identity. Check kernel ownership before initializing
Fusion motion; direct userspace I2C must not compete with a loaded kernel owner.
Address selection from sysfs is a preset convenience, not proof of compatibility.
Avoid blanket I2C scans: probes can issue device transactions.

### Safe smoke

1. Start with actuators disconnected or disabled in configuration. Inspect the
   selected profile and config diff. Existing private calibration takes precedence.
2. In the Agent menu list Ollama models. Expect local/cloud labels; local selection
   needs no key. Confirm saved `base_url` and model after service restart, without
   printing secrets. Listing must not download or run a model.
3. In chat inspect `/speech status` and `/speech outputs`. Expect separate engine
   and playback readiness; missing Piper assets must remain actionable.

Rollback: stop the service and restore backed-up configuration and prior revision.
Do not delete model files, calibration, secrets or conversation data.

### Device communication

1. Inspect `/sys/class/fusion_hat/` and the deployed driver configuration without
   instantiating a servo backend. Resolve kernel/userspace ownership first.
2. Read `vcgencmd get_throttled` at idle. Bit zero is current Pi undervoltage;
   historical warnings are different. Compare battery voltage through a verified
   reader with a meter before accepting conversion or cutoff suitability.
3. With explicit audio consent, test speech as the service user. Expect speech
   through the selected embedded speaker without the onboard buzzer. A transient
   non-latching stop should not permanently disable subsequent speech; a persistent
   system latch must continue blocking it.
4. With approved remote activation, scan a fresh QR over cellular data. Expect
   pairing and authenticated WebSocket control. Stale URLs and forged LAN headers
   must remain rejected. Never publish QR tokens, cookies or marker secrets.

Rollback: disable the affected feature and retain diagnostic reason fields only.

### Actuator-moving

Require explicit operator approval, raised wheels, clear joints and an operator
ready to remove power. Use existing calibration tools for each connected servo.
Test one channel at a time, including P0, P1, an auxiliary channel and P11 where
physically installed. Expect only the addressed output to move and stop to remove
pulses. Then test Agent actions with existing arming and distance protection.
Positional and continuous-rotation servos have different physical semantics;
never interpret a wheel-servo command as measured angular position.

Rollback: immediate stop; remove power if stopping fails. Restore known-good
software/configuration before further movement. No automatic retry after a stop.

### Power-risk

Keep power-off tests manual and separate from movement tests. Automated coverage
stops at authorization, command construction and helper validation. Obtain the
operator's authorization before a real shutdown; preserve battery protection.
Expected result: supported authorized shutdown path only. Rollback: prior helper
and service configuration; do not alter live boot/system files through tests.
