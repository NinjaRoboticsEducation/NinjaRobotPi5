# Pi5 web server reconnection implementation plan

Keep the NinjaRobotPi5 service and its healthy ngrok tunnel running after a
browser disconnects, stop browser-started activity, and display a fresh pairing
QR code so another person can connect safely.

Date: 8 November 2026. Status: researched implementation proposal. No runtime
changes or hardware acceptance have been performed.

The owner confirmed both behavioral choices during preparation: stop
browser-started movement, programs, audio, and capture while keeping the server
running; preserve Pi5's existing 10-second reconnection window.

## Contents

- [Scope and acceptance contract](#scope-and-acceptance-contract)
- [Evidence and current behavior](#evidence-and-current-behavior)
- [Target lifecycle](#target-lifecycle)
- [Phased implementation](#phased-implementation)
- [Validation commands](#validation-commands)
- [Manual acceptance](#manual-acceptance)
- [Documentation and rollback](#documentation-and-rollback)
- [Research validation and limitations](#research-validation-and-limitations)

## Scope and acceptance contract

Implement this inside the existing Agent/IDE architecture. Preserve the path
`user/model -> ninjarobot_pi5_agent -> ninjarobot_pi5_ide -> pi5* driver`.
The Agent must not import drivers or write to the display directly.

1. Closing a tab/window, navigating away, or losing browser connectivity does
   not stop `AgentIPCServer`, `WebServerManager`, or `RemoteAccessService`.
   A healthy ngrok endpoint retains its URL and process. No restart is needed.
2. Once a disconnect is observed, deny further work from that connection and
   immediately initiate cancellation, actuator stop, audio stop, and capture
   cleanup. Do not wait for the reconnection grace period to stop outputs.
3. Keep the disconnected lease reserved for its existing reconnect token until
   `min(previous heartbeat deadline, disconnect time + 10 seconds)`.
   A competing browser remains locked during this interval. An explicit
   existing `release` message relinquishes the reservation immediately.
4. If the same browser reconnects during grace, preserve its existing chat
   identity and pairing cookie, but do not resume interrupted work or restore
   AI movement/camera grants automatically. Preserve existing explicit D-pad
   activation behavior after successful lease activation.
5. After reservation expiry or explicit release, complete cleanup before
   admitting a new controller. Show a fresh one-use remote pairing QR on the
   robot display if the tunnel is ready and safety permits presentation.
6. Keep the QR available while waiting: renew its pending token before expiry,
   maintain its quiet border, and prevent late face/animation callbacks from
   painting over it. A successfully authenticated exclusive controller clears
   the QR and restores idle without replaying the startup Greeting.
7. Missed heartbeats retain the existing 15-second timeout and watchdog polling
   interval of at most 1 second, plus scheduling and cleanup latency. These
   are software deadlines, not hard real-time guarantees.
8. Preserve HTTPS, one-use fragment pairing, cookie authorization, Host/Origin
   checks, ngrok transport checks, exclusive control, and safety latches.
9. Tunnel failure remains distinct from browser loss. Existing local fallback
   and tunnel recovery continue; never display an obsolete remote URL after
   loss, replacement, explicit deactivation, or shutdown.
10. Availability means availability while the Pi and Agent process remain
    running. This change does not install boot startup, defeat operator
    shutdown, or promise availability during power/network/provider outages.

Non-goals: Pi0 changes, Education platform changes, a new `/ws/session`
protocol, simultaneous controllers, automatic replay, new ngrok accounts/plans,
dependency upgrades, systemd installation, managed `pi5*` driver changes, or
database migration. Independently confirmed persistent reminders/tasks are not
deleted by browser loss. Cancel the departing browser's active execution;
retain saved data and explicit future tasks.

Risk: medium/high implementation risk because cancellation and presentation
interact with motors, audio, camera, and microphone. This task only researches
and writes the plan. Actual implementation requires plan approval; device
operations and deployment require their own explicit authorization.

## Evidence and current behavior

### Provenance and wiki retrieval

Inspected Pi5 checkout: `ccdd5d5692d630704eb36cc223052acb53020aee`.
Pi5 Git status was clean before this document. The parent Education checkout
contains many unrelated edits; preserve them. Paths below are relative to Pi5.

The native command `python3 scripts/wiki.py search 'ngrok'` could not run because
the separate wiki environment is missing. `source status` and `lint` reported
the same limitation. No dependencies were installed. Librarian query
`ninjarobot-pi5 'ngrok reconnection'` returned zero pages; broadening to `remote`
returned `concepts/development-history` and `concepts/features-and-tools`.
Both are draft, with passed AI semantic-review metadata and unverified trust.
The mirror reports unknown upstream freshness. Direct reads of the robot-local
wiki, current source manuals, catalog records, and code supplied the detail.
A zero search result is not evidence that a feature is absent.

| Evidence | Provenance and interpretation |
| --- | --- |
| [Architecture](../ninjarobot_pi5_wiki/wiki/concepts/architecture.md) | [ninjarobot-pi5:concepts/architecture]; draft, AI review dated 4 November; Agent/IDE boundary and transport context |
| [Features](../ninjarobot_pi5_wiki/wiki/concepts/features-and-tools.md) | [ninjarobot-pi5:concepts/features-and-tools]; source `src-20261104-developmentguide`; web/device context |
| [Installation](../ninjarobot_pi5_wiki/wiki/concepts/installation.md) | [ninjarobot-pi5:concepts/installation]; source `src-20261104-installationguide`; remote transport and physical acceptance limits |
| [Knowledge limitations](../ninjarobot_pi5_wiki/wiki/analyses/knowledge-limitations.md) | Draft, passed AI review metadata; separates software evidence from human/hardware verification |
| [Development guide](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-04-03/DevelopmentGuide.md) | Registered/ingested `src-20261104-developmentguide`; “Remote access and pairing boundary”, “QR onboarding and startup liveliness”, HTTPS web interface |
| [Knowledge map](../ninjarobot_pi5_wiki/project-knowledge.json) | Reviewed checkout `94e3cdfb789a1e061dab6fb93eeecdeba6e29e2a`; names 4 November manuals as current |

The four current manual hashes were recomputed and match the map. The
DevelopmentGuide hash is
`sha256:6d4574560831e69657ce128f16f972a885ba6fbf98c463a433a38a2459b41f4b`.
The 4 November guide/catalog/page records disagree with the wiki README's claim
that these successors are still unpublished and the map remains at 3 November.
Treat that README paragraph as documentation drift. This inspection does not
establish full wiki freshness or successful native lint.

The supplied Pi0 explanation is the behavioral reference, not proof of Pi5 APIs.
Do not transplant Pi0's 35-second heartbeat, `/ws/session`, `AppState.public_url`,
or direct face cleanup names. The Education wiki was queried for Pi5 context;
its product-page material is not a server contract.

### Code-verified findings

Line numbers identify this snapshot and will move during implementation.
Serena symbol inspection covered leases, remote service, pairing, and onboarding.
Targeted reads covered service wiring, browser code, IDE presentation, and tests.

| File and symbols | Verified behavior and consequence |
| --- | --- |
| [web_control.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_control.py), `ControllerLeaseManager`, lines 48–192 | Heartbeat 5 seconds, timeout 15 seconds, grace 10 seconds. `disconnect()` marks disconnected/shortens expiry, without invoking cleanup. `_watch()` revokes expired leases. |
| Same file: `acquire()`, `release()`, `_watch()` | Clears/replaces active lease under its lock, then awaits revocation outside it. Another acquire can overlap cleanup. Expired-acquire path installs a replacement before awaiting old cleanup. |
| Same file: `WebRobotController.lease_revoked()`, lines 556–576 | Cancels movement, calls `robot.servo.stop`, stops transcription, disarms control/chat/voice motion, revokes chat camera, drops chat mapping. No QR restoration or comprehensive browser-work ownership. |
| [web_app.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_app.py), `create_web_app.websocket_controller()`, lines 444–642 | Authenticates, acquires, activates, invokes connected callback, subscribes events, handles `/ws`. Finalization cancels request tasks, unsubscribes, then calls `disconnect()`. |
| Same handler | Validates before creating request tasks. Queued work may wait on `operation_lock` after validation. Revalidation immediately before dispatch is needed. Accepted/activated setup precedes the main cleanup `try/finally`. |
| [service_main.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/service_main.py), lines 378–531 | `on_revoke` is wired directly to `web_controller.lease_revoked`. Connected callbacks update remote/onboarding state; no symmetric loss-to-QR callback. `server.serve()` is independent of browser presence. |
| [remote_access.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/remote_access.py), `RemoteAccessService` | Supervisor checks tunnel health, not browser count. `deactivate()` closes endpoint and revokes pairing; browser loss must not call it. Connected status lacks a corresponding browser-waiting transition. |
| [pairing.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/pairing.py), `exchange()`, `rotate()` | Exchange consumes the QR token. `rotate(invalidate_sessions=False)` creates a pending token while preserving valid cookies. Consumed QR or bare URL cannot onboard a new browser. |
| [onboarding.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/onboarding.py), `show_remote_access()`, lines 231–254 | Existing owner IPC action rotates a non-revoking token, sets post-startup remote scope, displays QR. `controller_connected()` clears additional QR to Idle without repeating Greeting. |
| Same file: `_refresh_pairing()`, `_monitor_remote_events()` | Existing refresh/fallback/recovery are reusable. Refresh defaults to 75% of token lifetime with 15-second minimum. State/generation checks need extension for controller and shutdown races. |
| [robot.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/robot.py), `show_onboarding_qr()`, lines 265–272 | Stops current idle task and renders QR. No durable presentation reservation; later behavior completion or idle restoration can restart faces. |
| Same file: `stop()`, lines 600–619 | Non-latching full stop suppresses idle and dispatches device stop concurrently with behavior cancellation. Broader than lease-scoped cleanup; do not blindly substitute it. |
| [integrated.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/integrated.py), `RobotIDEClient` | Typed methods already cover QR/status, idle, speech, and microphone. Extend this boundary; Agent must not access assembly/drivers directly. |
| [qr_display.py](../ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/qr_display.py), `render_pairing_qr()` | Validates bounded HTTPS pairing URL; integer modules, correction M, four-module white border. No new QR dependency needed. |
| [app-shared.js](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-shared.js), `connect()`, `initShared()` | Reconnect token in sessionStorage; chat ID survives lease changes. Close retries after 1.5 seconds except release/4423. `pagehide` only clears heartbeats; no matching socket close/pageshow recovery there. |

The server/tunnel already persist in code. The feature is safe loss cleanup,
serialized handoff, automatic QR restoration, and durable presentation ownership.

### Existing tests to extend

- `ninjarobot_pi5_agent/tests/test_web.py`: exclusive/reconnectable lease,
  heartbeat revocation, chat identity, pairing, access gates, power-off.
- `ninjarobot_pi5_agent/tests/test_onboarding.py`: simultaneous first connection,
  additional non-revoking QR, refresh, no repeated Greeting, fallback/recovery.
- `ninjarobot_pi5_agent/tests/test_remote_access.py`: lifecycle, recovery,
  permanent failure, TLS, process ownership, free-tier transport fallback.
- `ninjarobot_pi5_agent/tests/test_pairing.py`: one-use tokens, expiry,
  exact origin, forged transport rejection.
- `ninjarobot_pi5_ide/tests/test_qr_display.py`, `test_behavior_runtime.py`,
  `test_display.py`: rendering, cancellation, display-write races.
- `tests/test_web_mic_lifecycle.py`, `tests/check_web_mic.cjs`, and keyboard
  tests: existing Node-based browser lifecycle testing pattern.

## Target lifecycle

“Connection generation” is a monotonically increasing number for every accepted
WebSocket attachment, including reconnects that reuse a lease ID. It prevents
an old socket's delayed finalizer from disconnecting its replacement.

~~~text
CONNECTED
  clean loss -> QUIESCING -> RESERVED (up to 10 seconds)
                                | matching reconnect -> CONNECTED
                                | expiry
                                v
                           QUIESCING -> WAITING + fresh pairing QR

  heartbeat expiry -> QUIESCING -> WAITING + fresh pairing QR
  explicit release -> QUIESCING -> WAITING + fresh pairing QR

WAITING + paired exclusive lease -> clear QR -> CONNECTED (no repeated Greeting)
any state + actual tunnel loss -> existing local fallback/recovery
any state + shutdown/deactivation -> CLOSED/DISABLED (no reconnect QR)
~~~

QUIESCING blocks activation until mandatory cleanup completes. Do not hold the
small lease state lock while awaiting hardware/network I/O. Store a transition
task/future and generation under that lock; concurrent calls observe or join it.
Use one ordering: lease state, release state lock, then lifecycle/presentation
coordination. Callbacks must not recursively mutate leases under the state lock.

Immediate reconnect waits for quiescence. Expiry and release use one idempotent
finalizer. No new lease is usable while old cleanup can still stop its devices
or replace its display. For a silent network loss, the watchdog also cancels
that generation's socket, event forwarding, and requests even if
`receive_text()` is still blocked. Revoking a lease alone is insufficient.

## Phased implementation

### Phase 0 — Baseline and regression fixtures

Objective: reproduce missing behavior without devices, credentials, ngrok
processes, or model calls. Files: existing tests above and a focused new
`ninjarobot_pi5_agent/tests/test_web_reconnection.py` if useful.
Risk: none with fakes. No runtime changes.

1. Read current instructions and manuals; record checkout and dirty files.
   Re-check this plan's symbols.
2. Run offline baseline gates below in an already provisioned environment.
   Do not install hardware dependencies implicitly.
3. Build fake tunnel, clock, IDE, presentation, and events. Use controlled
   barriers for races rather than sleep-based assertions.
4. Add failing regressions: no automatic QR after expiry; delayed clean-loss
   stop; acquire overlapping old cleanup; stale finalizer; late idle repaint;
   expired silent socket retaining work.
5. Inventory browser-started movement, behavior, distance game, chat/model
   request, speech, camera capture, push-to-talk, and browser-enabled voice
   listening. Distinguish saved tasks from active execution and local services.

Gate: baseline recorded; regressions fail for intended reasons; no managed-driver
changes. Documentation: begin `docs/validation/web_reconnection_261108.md` during
implementation. Rollback: remove only new regression work if design is abandoned.

### Phase 1 — Serialize leases and stop on connection loss

Objective: separate immediate quiescence from reservation expiry.
Files: `web_control.py`, `web_app.py`, `service_main.py`, `runtime.py` where needed,
Agent tests. Risk: high cancellation semantics; automated tests use fake IDEs.

1. Add connection generation and idempotent loss transition to the existing
   manager. Preserve public lease/token fields. Inject a monotonic clock for
   tests. Internal disconnect/cleanup take generation; stale calls are no-ops.
2. On clean loss, deny commands first, initiate output stop/revoke grants,
   then cancel/drain connection tasks. Preserve reservation to existing deadline.
3. On timeout/release/expiry in acquire, reserve quiescence before clearing
   ownership. Finish mandatory cleanup before publishing a free slot or
   activating a replacement.
4. Put all post-acquisition setup under exception-safe cleanup: accept,
   activation, connected callback, event subscription, and request loop.
   Initialize optional resources before try; cleanup handles partial setup.
   Snapshot task sets before awaiting cancellation.
5. Register socket/request cleanup with lifecycle. Timeout must close stale
   socket and cancel tasks without another received message. Avoid a revoke
   task awaiting itself through the socket finalizer.
6. Revalidate lease/generation inside `operation_lock` immediately before
   dispatch. Stop/emergency paths stay prompt. Reject stale queued requests.
7. Disarm permissions before waiting for slow movement cleanup. Preserve
   finally cleanup; never silently classify failed cleanup as successful.

Proposed internal data contract; illustrative, not currently implemented:

~~~python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ControllerLoss:
    lease_id: str
    generation: int
    reason: Literal["disconnect", "heartbeat_timeout", "release", "shutdown"]
    reservation_ends_at: float | None


# Hooks run outside the lease state lock and are generation-aware/idempotent:
# quiesce(loss): deny old work, stop outputs, cancel/drain tasks, report faults.
# available(loss): after cleanup AND reservation expiry, request waiting QR.
# attach(lease, generation): activate only after preceding transition finishes.
~~~

Use explicit cleanup budgets. Proposed initial budget: 5 seconds for request
drain and each device stop, with independent stops dispatched concurrently where
safe. Validate against device limits in Phase 0. Timeout invokes existing IDE
fault/safety handling, denies new actuator control, and reports sanitized degraded
state; it must not kill the watchdog/server. Cancelling an asyncio wrapper does
not prove a driver thread stopped: join or invalidate its results in the IDE.

Gate: stop initiated before grace expiry; timeout closes silent socket; one
cleanup for concurrent timeout/release/finally; stale generation cannot affect
replacement; failed cleanup visible and watchdog survives. Existing lease/chat/
pairing/power-off tests pass. Documentation: state/timing evidence.
Rollback: revert Phase 1 coherently, without retaining partial callback wiring.

### Phase 2 — Activity ownership and durable waiting display

Objective: stop departing-browser work and hold QR presentation without clearing
safety state or stopping the service.

Files: Agent `web_control.py`, `runtime.py`, `speech.py`, `voice_service.py` where
ownership is missing; IDE `integrated.py` and `robot.py`; protocols/fakes/tests.
Risk: high physical outputs. No `pi5*` edits.

1. Track active work by lease and generation. Pass cancellation tokens through
   chat, behavior, capture paths where missing. Extend existing lease-tagged
   movement/microphone tracking rather than duplicate it.
2. Stop browser-owned game/behavior, buzzer, speech generation/playback, camera,
   transcription, and active chat/tool work. Revoke AI camera/motion and
   lease-derived voice motion. Late completions must not restart output.
3. Browser voice ON currently invokes a service method without a lease argument.
   Record ownership internally. Stop that listener on loss without rewriting
   stored preferences (`persist=False`). Do not accidentally stop a separately
   started terminal/boot listener. Preserve saved tasks and data.
4. Add typed IDE enter/leave waiting operations with checked generation. Reuse
   renderer and display queue/locks. Enter waiting before draining work so
   `finally: restore_idle_face()` cannot repaint. Suppress ordinary idle, speech
   faces, and background display effects until current generation releases hold.
5. Reuse safe stop primitives inside IDE. Existing `robot.behavior.stop` maps
   to assembly-wide non-latching stop: assess ownership before reuse. Global
   stop may be necessary for safety uncertainty but should not routinely cancel
   unrelated terminal work. Never auto-clear a latch.
6. Do not call `resume_system()` or `resume_motion()` merely to clear QR.
   Keep waiting-display hold distinct from `_idle_suppressed` and safety holds.
7. Safety warnings and active-capture privacy indicators outrank ordinary QR.
   After safety stop, retain warning/report QR deferred; explicit existing
   recovery is required. Browser reconnection is not safety authorization.
8. Missing/failed display degrades presentation without killing tunnel/server.
   Report safe error code and preserve disarming. Existing owner-only pairing
   URL command is fallback; never publish its token in status/events/logs.

Illustrative state guard to incorporate into IDE-owned presentation. Rendering
still needs serialization with display and safety writes:

~~~python
from dataclasses import dataclass


@dataclass
class WaitingPresentation:
    generation: int = 0
    active: bool = False

    def enter(self, generation: int) -> bool:
        if generation < self.generation:
            return False
        self.generation = generation
        self.active = True
        return True

    def leave(self, generation: int) -> bool:
        if generation != self.generation:
            return False
        self.active = False
        return True
~~~

Gate: browser work cannot restart; late speech/behavior/camera completion cannot
overwrite QR; safety display wins; reconnect never resumes movement; independent
services/data preserved. Documentation: ownership and priority matrix.
Rollback: revert Agent/IDE protocol changes and corresponding fakes together.

### Phase 3 — Automatic secure pairing QR and status

Objective: wire availability to existing pairing/onboarding behavior.
Files: `service_main.py`, `onboarding.py`, `remote_access.py`, tests.
No token-format change expected in `pairing.py`.
Risk: authorization/presentation; offline fake tunnel tests only.

1. Replace direct revoke wiring with lifecycle hooks. Immediate quiescence
   handles safety; post-grace availability handles QR. Carry reason/generation
   internally without publishing credentials.
2. Add a non-activating `RemoteAccessService.controller_disconnected()` or
   equivalent. When enabled/current endpoint ready, update remote status to
   WAITING_FOR_CONNECTION and pairing to PAIRING. Do not persist settings,
   connect/close backend, or announce a new tunnel.
3. Add automatic waiting entry point to `OnboardingCoordinator`, reusing
   `show_remote_access()` non-revoking rotation and existing refresh. Preserve
   terminal command. Check closed/deactivated, endpoint generation, lease
   generation, and safety state before and after awaits.
4. Use `pairing.rotate(invalidate_sessions=False)`. Preserve paired cookies and
   chat identity. Do not use `remote_access.rotate_pairing()`, which deliberately
   revokes sessions. Do not show consumed QR or bare URL.
5. During reserved grace, hold a safe non-credential waiting presentation.
   Defer new-user QR until reservation ends, avoiding a QR invitation while
   takeover is still locked.
6. Successful exclusive activation cancels stale refresh/render, releases hold,
   restores idle. HTTP access/authentication alone never clears QR.
   `_greeting_attempted` remains monotonic.
7. If pairing is consumed but no successful socket follows, remain waiting and
   refresh a new pending token. Expired/invalid tokens and locked browsers
   cannot clear display.
8. Serialize rotation/render/state publication. Authentication during render
   wins afterward. Refresh exceptions must not silently kill supervision.
9. Handle `remote_disabled` explicitly as well as existing error/ready events:
   remove obsolete remote QR and cancel refresh without enabling local access.
   Preserve local fallback for actual tunnel failure, not explicit deactivation.
10. Endpoint replacement invalidates old credentials through existing pairing.
    Also quiesce old remote socket/controller: initial handshake authorization
    alone is not sufficient after tunnel revocation. Show new endpoint only
    after access gate transition.
11. Mark coordinator closed before shutdown lease revocation. Late callbacks
    cannot render QR or restart backend. Runtime activation of remote access
    must also establish effective onboarding/waiting supervision when startup
    began with remote/onboarding disabled; do not rely solely on boot flags.

Existing primitive to reuse, only inside serialized generation-checked waiting:

~~~python
pairing_url = pairing.rotate(invalidate_sessions=False)
await ide.show_onboarding_qr(pairing_url)
# Never log pairing_url or include it in public status/events.
~~~

These lines are not a complete patch: Phases 1–2 provide cancellation, ownership,
generation checks, safety precedence, and shutdown protection.

Gate: A leaves, grace expires, fresh QR, B pairs/acquires; healthy tunnel connect
count stays one and close count zero. Test multiple token lifetimes, URL change,
deactivation during render, runtime remote activation, display fault, shutdown.
Documentation: pairing lifecycle and sanitized events.
Rollback: revert phase wiring/status changes together; manual QR remains fallback.

### Phase 4 — Browser departure and recovery

Objective: prompt cleanup when browser cooperates, reliable restoration, no
dependence on unload events for correctness.

Files: `web_static/app-shared.js`; `app-agent.js`/`app-gamepad.js` cleanup hooks
as needed; four locales (`en`, `ja`, `zh-TW`, `zh-CN`) if text changes.
Add `tests/check_web_connection_lifecycle.cjs` and pytest wrapper using current
microphone test pattern. Risk: medium.

1. Keep exactly one current socket and reconnect timer. Ignore stale socket
   callbacks. Reject pending request promises on loss so UI does not hang.
2. On `pagehide`, clear heartbeats/retries, stop local media through existing
   page hooks, release held movement input, best-effort close socket. Do not
   automatically send `release`: that would discard confirmed grace semantics.
3. On `pageshow`, including back/forward-cache restoration, reconnect if no
   current live/connecting socket. Preserve token and chat ID. Stale reconnect
   token after full expiry still permits fresh lease under normal authorization.
4. Do not interpret visibility hidden alone as definite departure: tab switching
   is not navigation. Keep existing microphone privacy behavior. Server timeout
   remains authoritative if browser never sends lifecycle events.
5. Preserve agent/gamepad navigation, reload, Back/Forward. Do not replay held
   keys, microphone recording, camera grants, or chat requests on reconnect.
6. Unauthorized pairing stops blind retries and tells user to scan current QR.
   Keep 423 lock feedback distinct from network failure; add bounded/manual
   retry for a paired browser that lost an acquisition race.

Gate: one socket/timer, closed-page suppression, BFCache recovery, stale event
rejection, no action replay; existing microphone/keyboard tests pass.
Documentation: browser behavior/limitations. Rollback: revert browser changes
together; server safety must remain independent of client goodbye.

### Phase 5 — Integrated validation

Objective: repeated safe handoff and persistence before operator acceptance.
Files: integrated fake tests and `docs/validation/web_reconnection_261108.md`.
Risk: none for fakes; physical tests separately authorized.

| Scenario | Required result |
| --- | --- |
| Close during movement | Stop initiated immediately; competitor locked through grace; QR after expiry |
| Silent network loss | Timeout cancels socket/work; no client goodbye needed |
| Same token during grace | Wait for cleanup, reconnect, no replay/Greeting |
| New browser during grace | 423/4423, no takeover or QR clearing |
| New browser after grace | Fresh QR exchange/cookie/lease, idle |
| Explicit release | Handoff after cleanup without extra grace |
| Expired acquire races watchdog | One finalization, no early replacement activation |
| Stale socket finalizer | New generation unaffected |
| Queued request after loss | Revalidation denies execution |
| Chat/game/behavior/audio/capture | Browser work stops; no late output restart |
| Cleanup/display exception | Server/watchdog survive; degraded state honest; unsafe control denied |
| Consumed QR, no socket | Fresh pending QR appears; no false connected state |
| Several token lifetimes | Valid QR persists; existing cookies preserved |
| Tunnel replaced/disabled | Old QR removed/unusable, old socket revoked, no stale repaint |
| Safety stop during render | Warning wins; reconnect never clears latch |
| Connected callback fails | Lease/tasks/subscription/permissions cleaned |
| Shutdown during cleanup | No new QR/tunnel task; owned tasks terminate |
| 100 fake handoffs | Stable tasks/subscriptions; one tunnel; no credential leakage |
| Independent persistent task | Data retained; scoped cleanup preserves unrelated task |
| Remote enabled after startup | Reconnection supervisor and QR function despite original disabled flags |

Use barriers for concurrency and fake monotonic time for deadlines.
Check task/subscriber counts every cycle. Update fakes when protocols change;
never weaken production authorization to make tests pass.

Gate: focused tests and complete repository checks pass; no driver changes;
manual results recorded honestly. Rollback: revert coherent feature patch and
use prior manual QR, preserving configuration/data.

## Validation commands

Run from Pi5 root in its approved, provisioned environment. These commands are
future implementation gates, not results claimed by this plan. `--no-sync`
prevents implicit dependency installation. Missing environment requires separate
approved setup. Never add `--run-hardware` or `--run-provider-live` here.

Before and after each implementation phase, verify driver integrity:

~~~bash
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py
~~~

Expected: unchanged authorized hashes and workspace mapping. Never regenerate
baselines to hide a failure.

Run focused tests after behavior changes; add new reconnection test once created:

~~~bash
uv run --frozen --no-sync pytest -q \
  ninjarobot_pi5_agent/tests/test_web.py \
  ninjarobot_pi5_agent/tests/test_onboarding.py \
  ninjarobot_pi5_agent/tests/test_pairing.py \
  ninjarobot_pi5_agent/tests/test_remote_access.py \
  ninjarobot_pi5_agent/tests/test_service_main.py \
  ninjarobot_pi5_ide/tests/test_qr_display.py \
  ninjarobot_pi5_ide/tests/test_behavior_runtime.py \
  ninjarobot_pi5_ide/tests/test_display.py \
  tests/test_web_mic_lifecycle.py \
  tests/test_keyboard_controls.py
~~~

Expected: fake/offline tests pass; hardware/live skips remain identified.
Run new Node lifecycle coverage through its pytest wrapper.

Complete repository gates at each approved phase:

~~~bash
uv run --frozen --no-sync python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync mypy \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen --no-sync pytest -q
git diff --check
git status --short
~~~

Expected: compilation, lint, formatting, typing, tests, whitespace pass; only
approved files changed. Explain baseline failures separately. Managed-driver
suites, if relevant, run in separate pytest processes due duplicate module names.

Ruff excludes DevelopmentPlanDoc and does not lint Markdown. Verify this document
separately: one H1, balanced fences, valid relative links, valid code-example
syntax, whitespace, complete phase gates. Do not claim Ruff checked prose.

## Manual acceptance

These are instructions for later approved testing, not actions run during planning.
Use separate browsers/devices or profiles so identity/cookie sharing does not
mask a second-controller bug. QR fragments are credentials; redact screenshots.

### Safe simulation and browser smoke

1. Use fake IDE/tunnel, no providers. A connects, closes tab/window, navigates
   away, reloads, and uses Back/Forward. Capture safe transition timestamps.
2. Reconnect A inside grace; expect identity retained and no action replay.
3. Let grace expire; B scans fresh QR and gains exclusive control.
4. Simulate lost heartbeats without close. Expect revocation at configured
   deadline plus watchdog/cleanup delay.
5. Repeat in Chrome, Safari/iOS, Android browser, and installed web app where
   supported, including app suspension and delayed close notifications.

Expected: one socket/controller, no stuck reservation, prompt simulated stop.
Rollback: stop simulation and inspect lifecycle; no OS/configuration changes.

### Pi5 display and network communication

Requires approved remote exposure and operator; begin with no actuator/capture
commands. Use the already configured service, never paste credentials.

1. Record service PID, safe remote status, endpoint identity.
2. Connect A using startup QR; confirm Greeting runs once.
3. Close A, wait through grace/cleanup, scan QR with B.
4. Confirm same service/tunnel, one controller, Idle, no second Greeting.
5. Leave QR through multiple token lifetimes; verify latest scan works.
6. Test approved network interruption/recovery; expect local fallback or new
   valid endpoint QR, never old endpoint advertised.
7. Explicitly deactivate; QR disappears and refresh stays stopped.

Rollback: existing owner remote deactivate, diagnose locally; never router
port-forward or bypass pairing. Check every supported hardware profile because
display behavior must not silently depend on a single HAT.

### Actuator, audio, and capture checks

Requires explicit approval, raised wheels/safe servo clearance, and operator
ready to remove power. Camera/microphone require consent; retain no test media.

1. Start one bounded browser activity at a time; disconnect while active.
2. Confirm movement, expression/game, buzzer/speech, recording, and chat work
   stop on detected loss, before grace completion.
3. Reconnect; no previous action or grant resumes.
4. Apply existing safety stop; verify reconnection cannot erase warning/latch.
5. Test scan/idle stability after cleanup and independently configured services.

Unexpected motion/capture: use existing stop, remove power if necessary, record
failure. Do not continue on timeout, cleanup fault, or unsafe state.

### Power-risk boundary

No real power-off required for feature acceptance. Automated tests cover command
construction, nonce, and authorization. Any physical shutdown test is separately
approved with recovery procedure. Browser closure never invokes poweroff.

## Documentation and rollback

### Phase 6 — Document verified behavior

After implementation validation, create new dated source versions under
`ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/` and
`raw/notes/ninjarobotpi5/`, starting from current map. Preserve registered originals.

Update DevelopmentGuide, InstallationGuide, DevelopmentLog, and root README:
timing, ownership, QR refresh, pairing security, graceful reconnect, safety
precedence, limitations, troubleshooting, actual tests. Reconcile outdated wiki
README checkpoint statement against catalog/map. No dependency/service change
is planned, so THIRD_PARTY_NOTICES needs review but no expected content change.

Prepare a schema-v2 semantic plan for these robot-local pages:

- `wiki/overview.md`
- `wiki/concepts/architecture.md`
- `wiki/concepts/features-and-tools.md`
- `wiki/concepts/installation.md`
- `wiki/concepts/development-history.md`
- `wiki/analyses/knowledge-limitations.md`
- `wiki/references/development-guide.md`
- `wiki/references/installation-guide.md`
- `wiki/references/development-log.md`

Review affected fingerprints and map new files deliberately. Preserve manual
anchors. Show exact semantic diff and obtain approval under Pi5 AGENTS.md before
applying. Record actual AI review, not invented human verification.

When approved wiki environment is available, validate:

~~~bash
python scripts/wiki.py check
python scripts/wiki.py lint
python scripts/wiki.py link check
python scripts/wiki.py index check
python scripts/wiki.py stats
~~~

Expected: structural/hash/link checks pass; review gaps reported honestly.
Run strict lint once sourced-page reviews are current. Query remote reconnection
after ingestion and verify new behavior is retrievable.

No Education PlatformWiki changes are required: no Education route/contract
changes. Do not edit Librarian mirror directly. Any requested sync is separate.
Planning-only impact: this proposal records future work; canonical wiki remains
unchanged to avoid presenting planned functionality as implemented.

### Rollout and recovery

1. Review coherent Agent/IDE/browser patch and successful gates.
2. Perform separately approved manual acceptance before normal operation.
3. Record deployed revision and configuration references without secret values.
4. Roll back only feature commits/patch; preserve user files/data/credentials.
   Restart running service only with operator authorization.
5. Existing owner command `/show remote access` is temporary manual fallback:
   non-revoking fresh QR. It is not a substitute for automatic-cleanup acceptance.
6. Recover wiki using transaction history, preserving original sources and
   unrelated later edits. Do not reset parent checkout or driver baselines.

## Research validation and limitations

Performed: repository instructions/status and commit inspection, native wiki
query attempts, successful Librarian retrieval, direct source/catalog/page
reads, four current-manual hash comparisons, Serena and targeted code/test
inspection, and upstream browser/WebSocket guidance review.

Not performed: dependency installation, runtime implementation, full repository
tests/lint/type checks, native wiki lint (environment missing), live ngrok,
browser UI/device execution, motion/audio/capture, deployment, or power-off.
This plan is not hardware certification. Final document checks are recorded in
the task handoff.

Upstream sources consulted on 8 November 2026:

- [Starlette WebSockets](https://www.starlette.io/websockets/): receive methods
  can raise WebSocketDisconnect; retain exception-safe lifecycle cleanup.
- [MDN pagehide](https://developer.mozilla.org/en-US/docs/Web/API/Window/pagehide_event):
  departure event is not reliable on mobile; retain server heartbeat detection.
- [ngrok HTTP/S endpoints](https://ngrok.com/docs/gateway/endpoints/http):
  WebSockets are supported; no separate tunnel protocol is needed.

Remaining implementation verification: actual stop latency and driver-thread
draining, phone scan readability, OS/browser suspension timing, and every
supported hardware profile. User behavior choices are resolved. A new
material architecture, privacy, dependency, or safety change requires plan
revision before implementation.

## Troubleshooting

| Symptom | First check |
| --- | --- |
| QR missing after close | Grace expired? Cleanup succeeded? Current remote URL ready? Safety warning owns display? |
| QR visible but pairing rejected | Token consumed/expired? Old endpoint? Refresh loop alive? |
| Reconnected user loses control | Stale-generation finalizer or cleanup overlapping activation |
| QR replaced by face | Missing presentation hold or late behavior/speech/camera completion |
| Server/tunnel stops with browser | Disconnect path incorrectly invokes stop/deactivate |
| Control available after failed stop | Safety admission bug; stop acceptance and inspect cleanup fault handling |
| Second user locked indefinitely | Reservation deadline/watchdog or stranded transition |
| Back/Forward page unusable | Missing pageshow recovery, stale socket callback, duplicate retry timer |

Use the [Pi5 policy](../AGENTS.md), [knowledge workflow](../ninjarobot_pi5_wiki/docs/PROJECT_WORKFLOW.md),
and [current development guide](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-04-03/DevelopmentGuide.md)
for the governing validation and recovery procedures.

