# NinjaRobotPi5 integration implementation plan

Date: 2026-11-02. Status: draft for owner approval; no implementation authorized.
Evidence: [integration audit](NinjaSunFounderIntegrationAudit_261102.md).
This plan covers remote access, power diagnostics, speech, PWM servo profiles,
and combined local/cloud Ollama selection. PWM means pulse-width modulation,
the signal used to command positional and continuous-rotation servos.

## Non-negotiable contracts

All `pi5*` libraries remain byte-for-byte unchanged, including tests and metadata.
Preserve the immutable baseline and authorization records. No monkey-patching,
protocol duplication in the IDE, alternate direct servo writer, or vendor-library
bypass is permitted. The hardware path remains Agent → IDE → driver → device.
The IDE is the deterministic coordination and safety layer.

Preserve DFR0566/X1208 behavior, existing commands, calibration and private data.
Support arbitrary configured servo roles without assuming P0/P1 are wheels.
Bare DC motors are excluded. Fusion all-port motion remains blocked by the
published-register discrepancy until compatibility is independently established.
A corrected driver release is outside this plan, requiring a future scope decision.
Do not claim this plan alone can deliver certified Fusion motion.

The owner approves implementation phases separately. This document is a proposal,
not authorization to run hardware, install services, expose a tunnel, or push Git.
Code examples below illustrate proposed contracts, not paste-ready patches.

## Phase 0: Establish reproducible evidence and freeze boundaries

Objective: preserve existing behavior and establish what each later phase proves.
Inspect Git status, current commit, configuration schemas and relevant symbols
with Serena. Preserve unrelated edits. Record redacted package/OS versions and
hashes for every managed driver. Run both driver verifiers before any edit.

Files: existing tests, `docs/validation/`, Agent/IDE configuration and service
builders. Do not collect private configuration wholesale. Use sanitized fixtures.
Inspect deployed systemd user/service context, PipeWire socket ownership, Ollama
endpoint and ngrok policy branch without printing tokens or conversation content.

Write independent Fusion expected-packet fixtures under root or IDE tests, outside
`pi5servo`. Derive addresses and units from matching firmware documentation, not
from current implementation. Mismatches are release blockers, not expected-pass
assertions. Never execute real initialization as a test of board identity.

Acceptance: baseline failures reproduced and classified; immutable files verified;
current-versus-proposed behavior documented. Risk: read-only software inspection.
Documentation: validation evidence, supported/blocked capabilities and provenance.

## Phase 1: Repair ngrok request classification

Objective: preserve the real transport peer while validating forwarded requests.
Files: Agent `web_app.py`, `pairing.py`, `remote_access.py`, associated tests.
Sequence:

1. Reproduce the missing-marker path through actual Uvicorn proxy middleware.
2. Make proxy handling explicit. Prefer retaining the transport peer for this
   application and interpreting forwarding headers only at the trusted boundary.
3. Preserve exact active-origin matching, marker validation, pairing tokens,
   session cookies, WebSocket origins and controller leases.
4. Publish a QR URL only after the active origin is installed; revoke stale
   sessions and URLs on reconnect according to existing contracts.

Candidate server setting, subject to full request and WebSocket regression:

```python
config = uvicorn.Config(app, proxy_headers=False, **existing_server_options)
# Pairing evaluates the actual peer, then validates forwarded metadata.
```

Do not allow arbitrary hosts or trust all forwarding sources. Tests must cover
valid marker, invalid marker, marker-free loopback, external forged headers,
IPv4/IPv6, invalid ports, stale origin, reconnect and WebSocket authentication.
Acceptance: full middleware reproduction passes and all rejection cases remain
rejected. Risk: network security. Rollback: restore previous application version
and disable remote access using existing controls. Documentation: secure remote
workflow and troubleshooting, without including real QR tokens.

## Phase 2: Separate power causes and preserve recovery safety

Files: IDE `safety.py`, `models.py` as needed, Agent status/presentation, tests.
Objective: identify Pi undervoltage separately from low HAT battery or unreadable
telemetry. Preserve current Pi bit-zero handling and stop latching. Do not relax
cutoffs, debounce away real failures, or treat stale data as healthy.

Proposed additive internal observation:

```python
@dataclass(frozen=True)
class PowerObservation:
    source: str       # pi_rail or hat_battery
    state: str        # healthy, low, unknown
    observed_at: float
    voltage: float | None = None
    threshold: float | None = None
```

Add distinct stop reasons while retaining decoding of old persisted reasons.
Record a bounded diagnostic snapshot, not an unbounded telemetry log. Verify
battery conversion against firmware and measurements before interpreting it.
Keep the old protection until equivalent behavior is proven; report uncertainty.
Recovery must recheck the active fault and preserve explicit `/resume` semantics.

Tests: current bit zero, historical bit 16 only, malformed output, timeout,
battery low/warning/normal, unavailable reader, cancellation, repeated stop,
resume during fault, persisted legacy reason and Agent explanation.
Acceptance: each cause has correct provenance and no automatic rearming occurs.
Risk: safety critical. Rollback: prior version/config snapshot, motion disabled
until status is understood. Documentation: diagnostic meaning and safe recovery.

## Phase 3: Make speech readiness and lifecycle diagnosable

Files: Agent `speech.py`; IDE `audio_output.py`, `integrated.py`; service builders
located during Phase 0. Keep microphone capture consent unchanged.

Sequence: distinguish safety block, foreground ownership, missing Piper/model,
missing sink, synthesis timeout, playback failure and cancellation. Return stable
reason codes while preserving text replies. Inspect actual service-user audio
access. Choose one verified profile-specific amplifier path; eliminate unverified
multi-path writes and independent competing ownership. Do not add device protocol
logic that violates the immutable driver boundary; surface unsupported capability.

```python
# Illustrative result; retain existing fields for compatible clients.
result = {"played": False, "status": "output_unavailable",
          "reason": "safety_stopped", "stage": "playback_health"}
```

Tests: fake synthesis and playback, missing model metadata, wrong language,
disconnected speaker, cold start, reconnect, queued cancellation, shutdown,
foreground interruption and safety stop. No automated sound or media capture.
Acceptance: `/speech status` explains each failure stage and successful output
works under the actual service account in an operator-approved manual test.
Risk: audio privacy/lifecycle. Rollback: disable speech, retain text operation.
Documentation: separate tone test from complete synthesis/playback test.

## Phase 4: Explicit servo profiles and safe switching

Files: IDE `config.py`, `config_import.py`, `hardware_setup.py`, `servo.py`,
`safety.py`; Agent `setup_wizard.py`. No managed-library edits.

Add robot-level endpoint metadata through a backward-compatible schema. Keep
existing calibration files authoritative. Default old configurations to their
existing behavior; new general-purpose robots need no wheel roles.

```python
# Proposed metadata, not new pi5servo configuration syntax.
servo_role = {
    "endpoint": "hat_pwm3", "kind": "positional", "role": "head_pan"
}
```

Require explicit positional versus continuous-rotation selection and role mapping.
Only differential-drive actions require left/right wheel roles. Never infer roles
from sorted calibrations. Validate endpoint range, existing calibration, electrical
limits, common frequency/timer constraints and reserved pins before constructing
hardware. Unknown compatibility must prevent actuator initialization.

Make import previewable, idempotent and atomic with rollback. Track profile-owned
settings so switching removes obsolete defaults without overwriting user choices.
Validate all six directed switches between the three profiles, plus same-profile
reimport, corrupt/partial configuration, one/no servos and arbitrary auxiliary roles.
Acceptance: legacy fixtures unchanged; explicit roles preserved; unsupported Fusion
motion clearly blocked. Risk: motion and configuration. Documentation: onboarding,
role semantics, blocked capabilities and profile rollback.

## Phase 5: Unified Ollama model discovery and routing

Objective: display downloaded local models and cloud catalog models together,
without an API key silently changing the execution destination.
Files: Agent `cloud_registry.py`, `ollama.py`, `model_selection.py`,
`provider_auth.py`, `agent_cli.py`, `setup_wizard.py`, `runtime.py`, `ipc.py`;
IDE provider configuration schema and serialization only where necessary.

### Routing and migration

Introduce explicit local/cloud route identity. Prefer reusing existing provider
registrations with stable internal local/cloud IDs and grouping both under Ollama
in the menu. Keep legacy `ollama` IDs readable; never silently change an existing
cloud user's execution location. Preview migration of legacy ambiguous records,
persist the effective route on deliberate selection, and retain rollback data.
Route identity must survive CLI, inter-process communication (IPC), runtime
selection, saved defaults, restart and benchmark lookup.

```python
@dataclass(frozen=True)
class ModelChoice:
    provider_id: str
    model: str
    route: str  # local or cloud; validated enum in production

# Credentials follow destination, never determine destination.
base_url = LOCAL_URL if choice.route == "local" else CLOUD_URL
credentials = None if choice.route == "local" else cloud_credentials
```

Do not deduplicate by name alone. The same name at different destinations is two
choices. Keep returned model identifiers intact; audit existing `-cloud` rewriting
against current API behavior before changing it. Distinguish local-daemon cloud
proxies from proven local inference; unknown execution location must be labeled.
Do not auto-fallback between local and cloud on failure or leak cloud credentials
to local endpoints. Preserve endpoint allowlists and bounded resource limits.

### Discovery and presentation

Query local `/api/tags` independently of cloud credentials. Query the official
cloud catalog with applicable authentication. Use existing HTTP clients, bounded
timeouts and deterministic close; no new dependency is needed initially.

```python
results = await asyncio.gather(
    discover_local(), discover_cloud(), return_exceptions=True
)
# Classify each result separately; retain healthy-source entries.
# Re-raise cancellation. Show sanitized source-level failures, not credentials.
```

Do not convert both failures to a misleading empty catalog. Display local daemon
unavailable, cloud authentication required, or empty local inventory separately.
Offer refresh and back. Remove the mandatory key step for local-only use from
both onboarding and the interactive selector. Selecting a cloud entry can prompt
for credentials; selection cancellation preserves the old route/model.

No model pulls, generation, benchmarks or daemon startup during listing. Model
listing is not proof of tool-call capability or adequate Pi memory. Existing
hardware policy remains authoritative for every selected model.

### Required regression matrix

| Scenario | Required result |
| --- | --- |
| No key, local daemon available | Local entries selectable without key prompt |
| Key present, both endpoints healthy | Both catalogs shown with distinct routes |
| Invalid key/cloud timeout | Local entries retained; cloud reason shown |
| Local daemon down | Cloud entries retained; local failure shown |
| Same name at both destinations | Two choices, exact destination preserved |
| Add/remove key after local selection | Local destination unchanged |
| Restart after selection | Selected destination and name restored |
| Selection validation fails or is cancelled | Prior selection remains active |
| Local request with cloud key stored | No cloud Authorization header sent |
| Legacy cloud configuration | Explicit migration preserves effective cloud route |
| Unknown fields/malformed/large catalog | Bounded safe rejection, no partial save |
| Local/cloud benchmark name collision | No acceptance inheritance across routes |

Use `httpx.MockTransport` or existing injected clients; assert destination and
headers, not only displayed model names. Extend cloud registry, Ollama, model
selection, setup wizard, interactive CLI and IPC tests. Acceptance: all matrix
rows pass and local-only operation is usable offline with a preinstalled model.
Manual inference is optional, explicit and non-hardware; no automatic downloads.
Risk: privacy, compatibility, Pi resource usage. Rollback: restore prior config
and application together; never delete downloaded models or stored secrets.
Documentation: local daemon setup versus cloud authentication, routing labels,
partial discovery failures and migration. Update notices only if dependencies change.

## Phase 6: Integrated regression, documentation and release decision

Run complete gates after each implementation phase, not only at the end. From
the repository root:

```bash
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python scripts/verify_workspace_driver_sources.py
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen pytest -q
git diff --check
```

Run each managed driver's tests in a separate pytest process; never combine
standalone suites with duplicate module names. Run applicable installer dry-run,
packaging, service and security tests. No automated test may touch live hardware,
boot files, system units, private configuration, external accounts or power commands.
A failure stops the phase: reproduce, classify baseline versus introduced, repair
within scope, and rerun relevant gates. Never refresh integrity hashes to pass.

Record exact commands, exit codes, test counts, skipped tests and environment in
`docs/validation/`. Passing mocked tests does not certify physical compatibility.

Update README for changed public behavior. Find current manuals through
`project-knowledge.json`, create new InstallationGuide/DevelopmentGuide/DevelopmentLog
source versions, and prepare affected architecture, installation and features pages.
Present the exact semantic wiki diff for approval before applying it. Record AI
review honestly. Run `python scripts/wiki.py check` and wiki lint after updates;
if its environment is absent, report the blocker rather than installing implicitly.
Review changed fingerprints and new unmapped files individually.

### Manual acceptance categories

| Category | Procedure and expected result | Rollback |
| --- | --- | --- |
| Safe smoke | Read-only status, profile and model catalog; no actuator initialization on unsupported profile | Stop service and restore config |
| Communication | Verified supported board/sensor identity and plausible telemetry, no motion | Stop on identity/protocol mismatch |
| Actuator-moving | Explicit approval, raised wheels, operator ready to remove power; calibrated channels and stop work | Immediate stop, remove power if needed |
| Power-risk | Separate operator-run shutdown validation after command-only tests | No automated execution; restore prior service config |

Also validate original display, buzzer, distance protection, camera/microphone
consent, wheel behavior, auxiliary servos, web leases, remote pairing and speech.
Keep Fusion physical motion blocked until its driver compatibility gate is met.

## Completion criteria and next decision

Every phase has reviewed evidence and passing applicable gates; compatibility and
privacy promises hold; all driver hashes are unchanged; documentation is current.
Report hardware tests not run and capabilities still blocked. Do not label the
entire multi-HAT upgrade complete while Fusion driver compatibility is unresolved.
The next safe action is owner review of this plan, then Phase 0 and independent
Agent/IDE work. No driver exception is assumed or requested by this draft.
