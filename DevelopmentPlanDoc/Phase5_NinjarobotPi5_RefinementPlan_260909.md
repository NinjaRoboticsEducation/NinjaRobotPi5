# Phase 5 implementation plan — Optional interactions and hardware evaluation

**Implementation checkpoint — 13 September 2026:** The owner approved Phase 5
before Phase 4. B02/B04 software and B05 hardware evaluation documents are present;
see the [handoff](../docs/validation/refinement_phase5_handoff_260913.md) and
[manual walkthrough](../docs/validation/refinement_phase5_walkthrough_260912.md).
Both optional settings default off. No managed driver or new hardware was changed.
Physical acceptance remains outstanding; Phase 4 is not started. The original
planning text below is retained as design history, not a newer status claim.


This plan adds gentle variety to existing expressions, an explicitly requested
distance-and-sound game, and a structured evaluation of possible future hardware.
The aim is a more engaging robot that stays predictable, easy to stop and useful
on a desk. The current NinjaRobotPi5 framework and device interfaces remain the
foundation.

**Status: proposed implementation instructions, prepared 9 September 2026.**
No Phase 5 implementation, physical testing, hardware purchase or driver change
is authorized by preparing this document. Review the preceding phase's handoff
and obtain the owner's implementation approval before starting. Any new physical
test needs its own appropriate operator consent and safety setup.

This is the **B02, B04 and B05** scope of the
[master refinement plan](NinjarobotPi5_RefinementPlan_260907.md#7-development-phases-and-acceptance-gates),
with X03 documentation work. It is separate from older July files whose titles
also contain “phase 5.” The companion
[Phase 4 plan](Phase4_NinjarobotPi5_RefinementPlan_260909.md) describes connected
information and reusable help.

## Contents

- [Starting point and scope](#starting-point-and-scope)
- [Architecture and files to extend](#architecture-and-files-to-extend)
- [Delivery sequence](#delivery-sequence)
- [B02 — Small variations in existing expressions](#b02--small-variations-in-existing-expressions)
- [B04 — Distance-controlled sound and display game](#b04--distance-controlled-sound-and-display-game)
- [Shared-device priority and cancellation](#shared-device-priority-and-cancellation)
- [B05 — Hardware evaluation without a hardware build](#b05--hardware-evaluation-without-a-hardware-build)
- [Automated validation](#automated-validation)
- [Manual walkthrough requirements](#manual-walkthrough-requirements)
- [Documentation and rollback](#documentation-and-rollback)
- [Completion checklist](#completion-checklist)

## Starting point and scope

The code inspected for this plan was commit
`cab1d3648a4d78a909a540e14bb7611fe0ae562a`. Serena symbol inspection and direct
source reads were used. Recheck the checkout before implementation and preserve
unrelated user changes.

Phase 0–2 software, local tasks and the approved face-recognition cleanup exist.
The owner reports Phase 2 manual acceptance. Phase 3 H02/B01 software adds optional
local spoken replies and IDE-owned output coordination. Its
[handoff](../docs/validation/refinement_phase3_handoff_260909.md) records 772 passing
tests and the managed-driver gate; these are earlier results, not a fresh test run
for this plan. Actual Bluetooth output, reconnect, microphone and boot-account
acceptance remain separately recorded physical work.

Phase 4 and Phase 5 have not started in the inspected checkout. The game can be
implemented using the existing buzzer, display and distance sensor without a
Bluetooth speaker or a calendar account. Nevertheless, respect the owner's phase
approval sequence; this technical independence is not permission to skip it.

The platform remains Raspberry Pi OS Lite, 64-bit, without a desktop. A terminal
interface is mandatory; a web controller on another device is optional.

### What users should experience

| Refinement | Result | Boundary |
| --- | --- | --- |
| B02 | Familiar expressions feel slightly less repetitive when variation is explicitly enabled. | Stable meaning, existing assets and bounded effects. No random movement or new personality system. |
| B04 | “Let's play the distance game” starts a short session. A hand nearer the front sensor produces a higher tone and a simple existing face or graphic. | Explicit start, finite duration, stop at any time, no wheel commands, camera or microphone requirement. |
| B05 | A clear comparison shows whether a speaker alternative, touch input, movable head or desk-edge sensing is worth a later project. | Evaluation and specifications only. No purchase, wiring, driver replacement or claim of fall prevention. |

The following stay out of scope: camera attention B03, spoken barge-in H03
(interrupting speech naturally by talking), desktop profiles/quiet hours H05,
proactive suggestions T08, broad identity changes M05, automated upgrades X02 and
the separate X04 evaluation platform. Feature-specific regression tests are still
required. Do not add new listening/thinking/approval faces: the confirmed H01
change is logging, not a redesigned display or web lifecycle.

### Knowledge limitations

Read the [owner confirmation](NinjarobotPi5_RefinementConfirmation_260907.md),
[progress record](../docs/validation/refinement_progress_260907.md),
[wiki README](../ninjarobot_pi5_wiki/README.md),
[document map](../ninjarobot_pi5_wiki/project-knowledge.json), and
[architecture page](../ninjarobot_pi5_wiki/wiki/concepts/architecture.md).
The map still points at an older published checkpoint; prepared Phase 3 manuals
have not been ingested. Compare important claims with current code. An AI review
record is not a record of a real sensor, speaker or wheel test.

## Architecture and files to extend

Preserve the sole hardware route:

```text
User/model -> Agent policy and tool registry -> IDE capability and scheduler
                                             -> existing pi5* driver -> device
```

The IDE is the existing layer that coordinates robot devices. A scheduler grants
temporary ownership of shared devices so that two actions cannot fight over them.
All game coordination, sensor freshness checks, output ownership and cleanup belong
there. The Agent selects a typed game action and reports its outcome. It must not
import drivers or directly read GPIO, I2C, SPI or PWM — the electrical control and
communication interfaces used by the hardware.

Reuse Python 3.11-compatible `asyncio`, strict Pydantic models, the existing
capability descriptors (typed descriptions of available actions),
`ResourceScheduler`, fake devices and pytest. Pydantic
validates incoming data; `asyncio` coordinates cancellable work in the existing
event loop. No game engine, second daemon, web framework or new runtime hardware
dependency is needed.

### Current implementation anchors

IDE paths below are relative to `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/`.

| Existing file/symbol | Current behavior and implementation implication |
| --- | --- |
| `robot.py`: `RobotAssembly` | Owns devices, behavior execution, safety state, foreground counts and idle faces. Add game ownership here or through one helper owned here. |
| `robot.py`: `ensure_action_allowed` | A synchronous safety gate. It cannot await game cancellation, and it does not replace admission checks before resource acquisition. |
| `integrated.py`: `RobotIDEClient.execute`, `build_robot_client` | Registers capabilities and routes actions. Add game descriptors and minimal pre-dispatch coordination without bypassing policy. |
| `scheduler.py`: `ResourceScheduler.run` / `interrupt` | Ordinary operations acquire resource locks. Trusted interrupts cancel intersecting owners without waiting for those locks. Reuse this mechanism. |
| `engine.py`: `_execute_reserved` | Calls the execution guard inside the scheduled operation. Cancelling the game only here can be too late: a conflicting action may already be waiting for its locks. |
| `distance.py`: `VL53L0XDistanceAdapter.execute` | Reads the shared sensor in `asyncio.to_thread` and rejects invalid/sentinel readings. It does not yet provide all freshness and in-flight cancellation guarantees required by a live game. |
| `buzzer.py`: `BuzzerDevice.play` / `stop` | Bounded tones and an existing stop path. Use these rather than driver calls or a second tone worker. A stop failure cannot be reported as confirmed silence. |
| `display.py`, `behavior_models.py`, `behavior_runtime.py` | Existing display operations, strict behavior definitions and finite effects. Reuse approved faces/graphics and canonical behavior contracts. |
| `audio_output.py`, `integrated.py`: speech priority wrapper | Existing speech foreground exclusion and stale-output cancellation. Extend the shared coordination; do not add another independent priority system. |
| `safety.py`, `microphone.py`, `voice_input.py` | Existing system stop and capture ownership. Preserve their authority and restore only the state actually owned by the game. |

Agent files under `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/` include
`tools.py`, `policy.py`, `skills.py`, `bundled_skills/`, `runtime.py`, controller/IPC
dispatch and web controls. Use them to expose a game through the existing registry,
provide a trusted stop, and package a non-executable game skill. Source inspection
must trace all direct/legacy IDE entry points as well as model-facing calls.

Proposed **new** IDE files are `expression_variants.py`, `distance_game.py` and,
only if needed for separation, `distance_game_models.py`. A helper is acceptable;
a second hardware-owning service is not. New test and documentation filenames in
this plan are proposed deliverables, not available commands or modules today.

## Delivery sequence

Run focused tests and the full gate after every increment. Each step includes
its documentation changes; prepare consolidated manual versions at the authorized
checkpoint and follow the owner's wiki deferral instructions.

| Step | Objective and likely files | Compatibility and validation gate | Effort / risk |
| --- | --- | --- | --- |
| 5.0 | Confirm accepted baseline, current resource graph, optional configuration and stop paths. | Record existing tests and outstanding physical acceptance. No live hardware action. | Low / none |
| 5.1 | B02 optional variant selector in `expression_variants.py`, configuration and existing expression call sites. | Canonical behavior unchanged when disabled; no extra state faces, assets, motion or louder output. Pure selection tests. | Medium / display and buzzer only when opted in |
| 5.2 | Harden IDE distance-read lifecycle and add game models/pure mapping. Extend `distance.py`; leave driver files untouched. | One in-flight read; stale/invalid data rejected; no lock release that permits overlapping driver calls after cancellation. Fault tests. | High / shared sensor reliability |
| 5.3 | Add bounded game capability, resource ownership and independent stop in `distance_game.py`, `robot.py`, `integrated.py`. | No servo resource/commands; cancellation before conflicting admission; speech/privacy/safety preserved. Scheduler race tests. | High / display, buzzer and sensor |
| 5.4 | Agent game skill, trusted start/stop/status controls, text/web help and task outcome. | Conversation requests one bounded run; stop works during busy chat; no automatic capture or re-start. Interface tests. | Medium / same game effects |
| 5.5 | B05 evaluation records and separate option specifications. | Evidence, compatibility, unanswered questions and decision gates. No new hardware build. | Medium for desk research; hardware follow-up may be Very High / none until separately approved |
| 5.6 | Combined fake-device gate, consented Pi walkthrough, consolidated documents and handoff. | Software and physical acceptance reported separately; pause for owner decision. | Medium / manual categories below |

The original master estimate for B04 is Medium. The inspected distance-thread and
resource-admission gaps make 5.2/5.3 the highest uncertainty in this plan. Budget
time for those correctness fixes; do not reduce them to a loop that repeatedly
calls the sensor. If safe recovery requires a managed-driver change, stop that
part and request a specific independently tested authorization.

## B02 — Small variations in existing expressions

### Intended behavior

Keep the current personality and meaning of each expression. At an existing,
explicit expression opportunity, select one of a few reviewed alternatives with
the same meaning. Examples are a slightly shorter existing happy face or a small
change in an already requested short buzzer cue. Do not change warnings, emergency
stop, privacy indicators, pairing displays, startup, onboarding, or idle silence.

Make variation disabled by default for old and new configurations initially.
A proposed `interaction_variations.enabled=false` setting is sufficient. Do not introduce the deferred
desktop profile, global intensity controls or speech-rate project under B02.
When enabled, variation applies only to reviewed expression hooks, not arbitrary
user-authored behaviors or existing named-behavior definitions.

### Implementation steps

1. Inventory current canonical faces, behavior definitions and buzzer cues. Build
   a small mapping from an allowed expression purpose to two or three approved
   variants. Store descriptors in the IDE, outside managed asset directories.
2. Define duration, tone-count, frequency and volume bounds no greater than the
   existing reviewed cue. Silence stays silent. Avoid flashing or rapidly changing
   brightness. Do not vary any servo operation, capture operation or stop sequence.
3. Select a variant once per accepted expression request, then keep that selection
   throughout execution and retry accounting. Deduplicate repeated presentation
   callbacks for the same request so one response does not generate several cues.
4. Use an injected deterministic selector in tests. If stable per-request variety
   is desired in production, derive a choice from a stable digest of request ID
   and purpose; never use Python's process-randomized `hash()` for persistence.
   Do not hash or save biometric/user-private material to choose a face.
5. Keep canonical fallback when disabled, the set is empty, a variant lookup is
   invalid or a variant is unavailable. Keep strict configuration validation.
   If physical output has already started
   and fails, follow existing failure handling; do not blindly replay another cue.
6. Route every effect through existing IDE-owned behavior/output methods. Preserve
   the current foreground and safety checks and Phase 3 stale-generation guard,
   which stops an old response from displaying after a newer action takes over.
7. Record a variant identifier and reason in bounded diagnostics if needed, not a
   new lifecycle UI. Make the setting inspectable and reversible through normal
   configuration; changing it must not execute an expression.

This standalone example shows selection only. It does not authorize or perform
an output, and the supplied variant IDs must come from the reviewed mapping:

```python
from hashlib import sha256


def choose_variant(
    *, enabled: bool, request_id: str, purpose: str,
    canonical: str, allowed: tuple[str, ...],
) -> str:
    if not enabled or not allowed:
        return canonical
    key = f"{purpose}:{request_id}".encode("utf-8")
    index = int.from_bytes(sha256(key).digest()[:8], "big") % len(allowed)
    return allowed[index]
```

Test disabled behavior against current fixtures, selection stability, only allowed
IDs, safety/privacy exclusion, unchanged canonical definitions, bounded cue counts,
no servo/capture calls, cancelled output and invalid configuration fallback. A
visual preference needs an operator's judgment; an automated test cannot prove
that a variation feels pleasant.

## B04 — Distance-controlled sound and display game

### User flow and proposed contract

The user explicitly asks to play. Explain once: “For 30 seconds, move your hand in
front of the distance sensor. Closer gives a higher tone. The wheels stay still.
Use Stop Game to end.” A vague request such as “Let's play” can select this as the
available game after a short clarification when needed. It must not arm movement.

Proposed IDE capabilities are `game.distance.run`, `game.distance.stop` and
`game.distance.status`. Final names must pass the current capability/tool-name
validators. Run is a cancellable, non-idempotent low-risk physical output action:
repeating it starts another experience. Stop is idempotent, meaning repeated stops
have the same intended effect. Status is read-only and never samples hardware.

Add an optional IDE `distance_game` configuration with `enabled=false` and
`volume=16` as proposed defaults. Old configurations continue to load. Enabling
the feature makes it available but never starts it; the user must still request
each game. Validate volume within 1–32 and preserve existing tone defaults.

Recommended strict input for the first version:

| Field | Proposed rule |
| --- | --- |
| `duration_seconds` | Default 30; integer 5–60; server clamps outer lifetime through validated policy, not a model prompt. Reject out-of-range input. |
| `mode` | Only `distance_tone`; reject arbitrary scripts or expressions. |
| Tone frequencies, volume, sensor pins, paths | Not model-configurable. Use reviewed IDE constants, the existing adapter's safety bounds and a new bounded operator game-volume setting. |
| Required capabilities | Existing distance sensor, display and buzzer ready; no camera, microphone, servo or Bluetooth requirement. |
| Duplicate request | Return existing request outcome/status or reject busy; never create an unbounded queue of games. |

Before acquiring game resources, refuse startup during movement, a system stop,
manual capture or higher-priority foreground ownership. Do not queue the game to
start unexpectedly when that activity ends. Atomically coordinate this admission
with incoming movement so simultaneous starts cannot both pass the idle check.
Ordinary automatic speech is the explicitly interruptible exception described in
the priority table; the game does not preempt safety, privacy or movement.

Keep one active game owned by the IDE with a run ID, trusted session/request ID,
start/deadline, state, stop reason and sample counters. Return a bounded result:
duration, valid/invalid sample counts and finished/cancelled/unavailable/faulted
reason. Map it to existing IDE action and Agent task outcomes instead of inventing
an unrelated lifecycle. Do not store a per-frame sensor history by default.

### Sensor validation and freshness

The current adapter rejects boolean/integer misuse and the driver sentinel 8191,
but a live loop needs stricter handling:

1. Require the adapter's validated positive distance and raw value, reject
   non-finite timestamps, and bound values to the game’s chosen working range.
   “Non-finite” means values such as infinity or not-a-number. Do not use a sensor
   error sentinel as a far-away hand.
2. Record monotonic request-start and completion times in the IDE. A monotonic
   clock measures elapsed time without jumping when the system clock is corrected.
   The driver's wall-clock timestamp is additional evidence, not the sole freshness
   authority. Check elapsed read duration, repeated/backward/future timestamps and
   clock-jump conditions conservatively.
3. Treat the measurement as unusable when it arrives after its read budget or is
   too old for the current output. Do not re-stamp a cached reading as fresh simply
   because it was retrieved now. Document the limitation that the current driver
   timestamp describes its read completion, not an independently verified instant
   of physical measurement.
4. On the first invalid or stale sample, stop tone output immediately, clear the
   smoothing history, and show a neutral/lost-reading indication only while the
   game still owns the display. Require fresh readings before any sound resumes.
5. If readings remain invalid for a proposed two seconds, finish with a clear
   unavailable reason. The operator can correct the problem and explicitly start
   a new game. Do not resume automatically after a safety stop or service restart.

Suggested initial tuning values are a 200 ms sample interval, a 250 ms maximum
read latency, a 400 ms maximum usable age, a three-reading median and 20 mm band
margin. These are proposed testable values, not measured claims about this Pi.
Measure the existing adapter's realistic latency before release; expose only
reviewed operator settings if tuning is necessary. A slower measured sensor must
not be made to “pass” by using old data without explanation.

### In-flight reads and cancellation

`asyncio.to_thread(sensor.get_data)` runs blocking sensor work in another thread.
Cancelling the awaiting coroutine does **not** reliably stop that thread. The
current `execute` lock can unwind while the thread continues. A new game loop must
not create overlapping sensor reads or close/reopen the device underneath one.

Implement a small single-flight lifecycle in the existing IDE distance adapter:

1. Maintain one owned in-flight read future and a generation identifier. Start
   another read only after that future is actually finished. Repeated timeouts
   must not accumulate workers.
2. Separate caller cancellation from underlying ownership. A caller can stop
   waiting, but the adapter retains the read and observes its completion without
   an unhandled exception. Use a bounded join policy and an explicit state, not
   an unconditional forever-wait in the game stop path.
3. If a read outlives its deadline, mark the sensor temporarily unavailable to
   every consumer. A late result from an old generation is discarded. Movement
   that depends on the same sensor cannot proceed with that result.
4. Serialize suspend, health recovery and close with this lifecycle. No new driver
   `get_data`, close, reinitialize or recovery call may overlap the pending read.
   Continue to service independent buzzer stop and safety actions.
5. Keep unavailable state until the read drains and the existing explicit recovery
   checks succeed. Do not silently remove sensor safety requirements from movement.
   Preserve public `distance.read` arguments and existing result fields; keep new
   freshness metadata internal or add it only through a reviewed additive contract.
6. Test permanent as well as short stalls. Python cannot safely kill an arbitrary
   blocked I2C thread. If the driver/OS call never returns, report that recovery
   is incomplete and require operator/service recovery; do not claim a confirmed
   clean close or release the device for reuse. A stronger driver timeout repair
   would require separate managed-file approval and tests.

See the [Python asynchronous task documentation](https://docs.python.org/3/library/asyncio-task.html)
for timeout, cancellation and thread behavior; implement against the project's
supported Python versions. This lifecycle work should improve the shared adapter
without changing the sensor's public meaning or managed driver implementation.

### Distance-to-feedback algorithm

Begin with three simple bands, subject to operator tuning: near below 150 mm,
middle below 300 mm, and far up to 600 mm. Millimetres measure hand distance from
the sensor face. Values below a reviewed minimum, such as 50 mm, and values above
600 mm are outside the game area and cause silence rather than being clamped into
a misleading band. These values are game choices, not universal sensor limits.

Use a median of up to three consecutive fresh valid samples to reduce brief jumps.
Add hysteresis, a small boundary margin that prevents rapid switching when a hand
rests near a threshold. Clear the history after invalid input or a read gap.

This pure example classifies an already validated and smoothed reading. It does
not read the sensor or play a tone. Real timestamp checks belong before this step:

```python
from math import isfinite
from typing import Literal

Band = Literal["near", "middle", "far"]


def next_band(distance_mm: float, previous: Band | None) -> Band | None:
    if not isfinite(distance_mm) or not 50.0 <= distance_mm <= 600.0:
        return None
    margin = 20.0
    if previous == "near" and distance_mm < 150.0 + margin:
        return "near"
    if previous == "middle" and 150.0 - margin <= distance_mm < 300.0 + margin:
        return "middle"
    if previous == "far" and distance_mm >= 300.0 - margin:
        return "far"
    if distance_mm < 150.0:
        return "near"
    return "middle" if distance_mm < 300.0 else "far"
```

Map bands to reviewed short tones, for example 880/660/440 Hz (cycles per second)
from near to far, each no longer than 60 ms. Use no more than three pulses per
second with a new operator-only game volume, proposed default 16 and range 1–32,
also bounded by the existing adapter's `MAX_SAFE_VOLUME` of 128. The current
`BuzzerConfig` contains only enable/wiring fields; there is no global configured
volume ceiling to reuse. Add this setting to an optional game configuration,
without changing the default volume of existing tones. Do not raise volume
automatically because the user moved closer. The suggested tones fit the current
20–20,000 Hz range and 50 ms minimum duration; recheck those constants before
implementation. Select existing safe faces or a simple distance bar in the IDE;
do not add image assets to `pi5disp`.

A proposed 10-second cumulative tone budget within a maximum 60-second session
provides another output bound. Maintain it in the IDE and stop tone production
when exhausted. The display may continue silently with an explanation. Store
timestamps of pulses to enforce rate limits even after rapid band changes.

The implementation loop should follow this order:

```text
validate explicit request and policy
admit one game and claim its existing resources
enter existing foreground output ownership
repeat only until deadline or cancellation:
    obtain one fresh reading through the shared IDE adapter
    if invalid/stale: silence, reset filter, show owned neutral state
    otherwise: filter, classify, emit at most one bounded eligible pulse
    refresh display only when needed and still owned
    wait only the remaining sample interval; never build a backlog
finally:
    request silence, cancel and observe owned work
    retain any unresolved sensor ownership as unavailable
    restore an idle face only if this generation still owns it
    release foreground reservations and record the true outcome
```

Use the existing asynchronous tone method; do not spawn a task for every sample
or send long melodies that continue after the hand disappears. Account for tone
and display time when scheduling the next sample. A pending tone must be stopped
when a sample becomes stale even if no new read completes. One small freshness
watchdog, owned and cancelled with the session, can enforce this. It must not
become a second sensor reader.

## Shared-device priority and cancellation

### Resource ownership

The game owns exactly the shared `distance_sensor`, `display` and `buzzer`
resources required by its descriptor. It must never claim `servo_bus` or issue
servo commands. Buzzer and display operations inside this reservation call the
owned IDE device methods; do not recursively submit the same operations to the
scheduler while holding their locks, which would deadlock — wait forever for
resources already held by the caller.

The current generic `behavior.run` descriptor reserves servo and distance resources
even for some nonmoving behaviors. Do not weaken that existing safety contract
just to fit the game. Add a dedicated game capability with precise resources.

### Priority decisions to implement and test

This table specifies the new game's behavior within existing safety semantics;
it does not replace all existing output priorities.

| Incoming action or condition | Required game response |
| --- | --- |
| System emergency stop, shutdown preparation or safety fault | Cancel immediately, silence through the trusted path, preserve the safety display. No automatic restart. The safety operation remains authoritative. |
| Explicit Stop Game or cancel of its owning task/session | Stop only the game and its outputs. No servo command. Repeated stop succeeds or reports an unresolved device fault truthfully. |
| Existing global behavior/movement stop | Include active-game cancellation in global stop coordination, while preserving existing movement-stop behavior. Do not make the new game stop call the global servo stop internally. |
| A newly authorized movement or conflicting foreground behavior | Cancel game and resolve shared-device ownership **before** ordinary resource acquisition or dispatch. If sensor ownership remains unsafe, reject the new action clearly. |
| Camera/microphone privacy presentation or existing manual device capture | End the game before the higher-priority presentation/capture path takes over. Never overwrite its display or change microphone consent/settings. |
| A newly delivered reminder requiring shared outputs | Yield the game to the existing reminder delivery path. Preserve the reminder's existing fallback, cancellation and delivery evidence. |
| Spoken reply already playing when game starts | Use the existing foreground exclusion to stop/drain it before the game. Do not use speech to announce the game while simultaneously claiming its output timeline. |
| Ordinary automatic reply speech during game | Existing foreground exclusion rejects/suppresses speech; retain text. A later explicit higher-priority user action may cancel the game through normal admission. No stale replay after the game. |
| Explicit Stop Speech | Stop speech as currently specified; do not repurpose it as the sole game-stop control. Provide distinct Stop Game and existing global Stop. |
| Idle face or B02 variant callback | Suppress while game owns foreground; restore only the current allowed idle scene after cleanup. |
| Another game request | Return busy/already-running evidence; no queue of repeated games. |

### Avoid the admission deadlock

Checking “no movement is active” only at game startup is insufficient. A movement
can arrive one millisecond later. `RobotAssembly.ensure_action_allowed` is
synchronous, and the engine's current guard runs after locks are acquired.
Add a minimal asynchronous admission step in the existing IDE routing before
ordinary scheduler acquisition. It should:

1. Perform ordinary validation/policy checks before allowing a rejected or malformed
   request to disrupt an active game.
2. Recognize an authorized conflicting action from its actual capability/resource
   requirements, not from the model's description of whether it moves.
3. Mark a transition so another game cannot enter while cancellation is draining.
   Serialize admission decisions with a short coordination lock, but never hold
   that lock while awaiting a stop that needs it.
4. Request game cancellation through the existing trusted interrupt mechanism,
   await bounded output cleanup, and recheck safety and ownership immediately
   before dispatch. A safety stop during this wait must still win.
5. Cover Agent tools, direct IDE calls, named and inline behavior execution,
   low-level servo actions and legacy `RobotAssembly.move_servo_endpoint` paths.
   A small shared helper is preferable to inconsistent checks at each route.
6. Preserve the existing synchronous execution guard as a final safety check.
   Do not replace it with an async function that its caller never awaits.

`ResourceScheduler.interrupt` already bypasses ordinary queues and cancels owners
whose resources overlap. Use it for an independently available trusted game stop;
do not wait behind the game's resource lock, chat lock or ordinary worker slots.
Register stop/status as permitted inspection/cleanup under system stop where
appropriate. An arbitrary caller may not use the trusted interrupt route to issue
unreviewed operations.

### Cleanup and failure rules

Maintain one tracked session task and any bounded watchdog/cleanup tasks. Cancel
and observe each on stop, expiry, client disconnect, service shutdown and startup
failure. Keep foreground enter/exit balanced even when acquisition fails partway.
Protect essential cleanup against repeated cancellation without hiding an endless
wait; retain ownership/unavailable state when a device cannot be proved released.

A game stop should target a fake-device response under 250 ms and physical silence
under a proposed 500 ms in normal conditions. Measure and publish actual Pi
results before making a guarantee. The descriptor's timeout must include the
maximum session plus a bounded cleanup allowance. If a driver call is stuck,
silence and cleanup cannot be promised simply because the coroutine was cancelled.
Report the fault, follow the existing safety-stop path where needed, and do not
accept conflicting output while its ownership is unresolved.

Never restore a happy/idle face over emergency, pairing or privacy output. A
generation identifier and current ownership check must guard every delayed display
write and final restoration. On normal stop, leave the buzzer silent and restore
only the prior permitted idle behavior. Ending the game does not enable a previously
disabled microphone or resume interrupted movement/speech.

### Agent and controls

Add a bundled non-executable game skill with only required game run/stop/status
tools and strict input. If Phase 4's X01 version-2 support exists, declare its
capability requirements there; otherwise a compatible version-1 package is enough
until that upgrade is approved. Do not require Phase 4 databases for the core game.

Expose an explicit trusted stop in the existing terminal interface and web control
channel. Wire it like the independent Phase 3 stop controls so a busy conversation
cannot block it. Keep tool execution bounded and attach a current request receipt
to the game run; status reads the session state rather than touching the sensor.
The natural-language model is not responsible for sampling, pitch choice or timing.

Do not add a voice listener to make “stop” available. Existing explicit microphone
consent and sequential speech/input behavior remain unchanged; users always have
a terminal or button stop that does not require speech recognition.

## B05 — Hardware evaluation without a hardware build

B05 produces decision-ready documents. Its implementation deliverable is an
evaluation, not a new speaker driver, head mechanism or desk-edge safety system.
The Phase 3 Bluetooth speaker path is already the initial speech choice; another
speaker evaluation must not delay acceptance of that path.

### Required documents

At implementation time, create a dated index and four option specifications under
`DevelopmentPlanDoc/hardware/` (a proposed directory):

- `HardwareOptions_<date>.md`: comparison, evidence, recommendation and unanswered
  questions.
- `SpeakerOutput_<date>.md`: retain Bluetooth versus a separately evaluated wired
  output, with Lite boot/session requirements.
- `TouchInput_<date>.md`: candidate input behavior, debounce (ignoring contact
  chatter), permissions and placement.
- `MovableHead_<date>.md`: purpose, mechanics, power, controls and independent
  emergency-stop implications.
- `DeskEdgeSensing_<date>.md`: detection geometry, failure modes and a proposed
  supervised validation approach.

Each specification must contain:

1. The user problem, measurable benefit, explicit non-goals and “do nothing” option.
2. A current primary-source link for each proposed device/library, date checked,
   supported Pi OS/Python versions, license and availability uncertainty.
3. A diagram or clear description of placement and signal/power connections,
   **labeled proposed**, not instructions to wire hardware immediately.
4. Electrical needs and the current pin/address inventory: supply voltage, current
   including peaks, connector, GPIO or bus address, and likely conflicts with
   display, buzzer, wheels, microphone, camera, distance sensor and UPS. UPS means
   the existing backup-power system. Unknown values block a build recommendation.
5. Software ownership through Agent -> IDE -> device driver, required capabilities,
   graceful unavailable behavior and effect on existing interfaces.
6. Failure modes, stop/recovery behavior, privacy implications and operator setup.
7. Reversible prototype plan, fake tests, supervised physical tests, pass criteria
   and rollback. Do not prototype electrically until separately approved.
8. Costed bill of materials, meaning a parts list, only after checking actual
   options and region. Show currency, date, shipping/power/enclosure assumptions
   and unknowns. Do not invent prices or purchase anything during planning.
9. Recommendation: proceed to a separately approved prototype, gather evidence,
   or defer. Record why and name any managed-file/boot/power changes requiring
   additional approval.

### Evaluation questions by option

| Option | Questions and meaningful measurements | Boundary or likely adaptation |
| --- | --- | --- |
| Speaker output | Does Bluetooth reconnect under the real service user on Lite? Is latency acceptable? Does a wired option reduce pairing/session failures? What are power, cable and placement costs? | Continue the IDE audio-output contract. No second player or Agent device access. Test at modest operator-selected volume. |
| Touch input | Is the gesture discoverable? Can accidental touch trigger it? What distinguishes short/long presses? How does it behave with gloves, electrical noise and startup? | Default proposal is a harmless acknowledgement or request for an existing control, never motion, recording, approval of a calendar write or shutdown without the relevant policy. |
| Movable head | Does head motion add useful expression? What are load, range, pinch points, cable routing, mechanical stops, power peaks and crash behavior? | Separate mechanism and driver project. Never reuse wheel endpoints or change existing servo semantics to simulate a head. |
| Desk-edge sensors | Which edge directions are covered? How do dark, reflective, glass, uneven or angled surfaces and sunlight affect readings? What is the braking distance including latency? | Current forward-facing obstacle distance is not desk-edge protection. Invalid data must stop relevant motion in any future approved design; detection coverage must be demonstrated. |

The existing VL53L0X is an optical distance sensor. Its general capabilities are
described by [STMicroelectronics](https://www.st.com/en/imaging-and-photonics-solutions/vl53l0x.html).
That specification alone does not prove a particular mounting can detect every
desk edge or prevent a fall. Do not recommend unsupervised tabletop movement based
on the current single forward reading.

### Comparison and decision gates

Use a transparent scorecard after gathering evidence. Suggested weights are:
user benefit 25%, compatibility 25%, reliability/recovery 25%, installation effort
15% and total cost 10%. Score 1–5 with a written reason and primary evidence for
each entry. Mark unknowns as unknown, not zero or an invented average. A serious
safety or compatibility failure overrides the total score.

Gate A accepts the problem and requirements. Gate B accepts an evidence-backed
option and its proposed interfaces. Gate C authorizes a particular reversible
prototype and budget. Gate D accepts supervised test evidence before normal use.
**Phase 5 can finish B05 at Gate B with a documented decision to defer.** It must
not claim a hardware option implemented, bought or validated because its document
exists. Gates C/D are separate work and may need managed-driver or wiring approval.

## Automated validation

### Feature tests

Use fake devices and clocks only. Tests should fail if forbidden operations occur,
not merely check that the happy-path result says success.

| Area | Required cases and assertions |
| --- | --- |
| B02 selection | Disabled equals baseline; enabled only selects allowed variants; no privacy/safety/idle changes; no movement; stable selection and bounded output. |
| Input validation | Duration boundaries, wrong types, unknown fields, unsupported mode, unavailable device, duplicate run, stopped system and unauthenticated controls. |
| Sensor values | Near/middle/far, boundaries and hysteresis; 0/negative/8191, booleans, invalid flags, out-of-game range, NaN/infinity timestamps, missing data, old/future timestamps and clock jumps. |
| Sensor lifecycle | Read stalls before/after deadline; cancellation while thread is active; repeated timeout creates only one worker; no concurrent close/reopen/read; late result discarded; other consumers blocked until safe. |
| Timing and output | Finite session, bounded pulses/volume/bytes, sample gaps silence output, invalid clears filter, no task backlog, no automatic restart. |
| Resource exclusion | Game descriptor never holds `servo_bus`; direct and model-initiated conflicting movement cancels game before locks; unknown/denied motion cannot execute; unresolved sensor fault rejects motion. |
| Stop races | Stop during startup/read/tone/display/cleanup; concurrent game and movement admission; queue/worker saturation; repeated stop; emergency during cancellation; disconnect and shutdown. |
| Presentation | No stale face after privacy/safety takeover; balanced foreground reservations; no microphone re-enable; existing reminder/speech cancellation and fallback preserved. |
| Failure reporting | Buzzer off fails, display fails, sensor never returns, cleanup expires and optional skill missing. Never label unconfirmed silence/cleanup as successful. |
| Controls and packaging | Stop independent of busy chat; CLI (command-line interface)/web use same service checks; skill is non-executable and included in packaging; existing skills still load. |

Use a fake movement adapter that raises immediately on any unexpected invocation
in game-only tests. In arbitration tests, permit a recorded movement **only after**
the game has been cancelled and its required resources are safe. This demonstrates
that the incoming movement still follows existing policy without operating motors.

Create pure function tests first, then adapter lifecycle, scheduler integration,
Agent/IPC/web tests and combined journeys. IPC is the existing local
communication channel between controller and service. Parameterize boundary cases; use events
and a fake clock instead of real multi-second sleeps. A normal timeout test must
not leave a real thread blocked when the test process exits.

### Full gate after every increment

From the repository root in the reviewed development environment, run:

```bash
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py
uv run --frozen --no-sync python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen --no-sync pytest -q
node --check ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js
git diff --check
```

Expected result: all applicable checks pass, existing driver authorization records
are unchanged, and no physical device was exercised. `--no-sync` preserves the
working environment; dependencies must already match the reviewed lock. No new
runtime dependency is expected. Do not hide a missing dependency with this flag.

Run affected managed-driver suites in separate pytest processes if integration
changes require them; suite names can collide in one combined process. Preserve
the immutable baseline and report pre-existing failures separately. A required
managed-file repair needs explicit file-specific approval, independent tests and
the existing authorization ledger process. Do not regenerate hashes to make it pass.

The preceding commands are requirements for future implementation. This planning
document does not report new runtime test passes or hardware validation.

## Manual walkthrough requirements

At handoff, create `docs/validation/refinement_phase5_walkthrough_<date>.md` and
`docs/validation/refinement_phase5_handoff_<date>.md`. Supply actual implemented
terminal commands and optional web equivalents, expected output, consent, stop and
rollback. The proposed `game.distance.*` names in this plan are not currently
available commands. Reuse the existing service/account setup; never instruct the
operator to run two hardware-owning Agent/IDE instances together.

### Safe smoke — no hardware access

1. Run the documented simulated configuration with temporary state and fake devices.
   Expected: game status says idle and no device imports or reads occur.
2. Start a simulated five-second game. Feed near/middle/far and invalid fixtures.
   Expected: the correct bounded bands, silence on invalid data and finite result.
3. Use Stop Game from a second controller while the first is busy. Repeat it.
   Expected: prompt stop acknowledgement, no output task remains, no servo call.
4. Simulate incoming motion and a stalled read. Expected: motion waits for safe
   cancellation or is rejected; it never inherits unsafe sensor access.
5. Toggle variation in a temporary configuration. Expected: disabled behavior is
   canonical; enabled behavior stays within the reviewed set.

Rollback: stop the simulated service and remove only its explicitly temporary
test state through the documented fixture procedure. Do not delete private user
configuration, memories or tasks.

### Device communication — real sensor, display and buzzer

These steps require an operator's consent because the game reads a sensor and
produces visible/audible output. No camera or microphone capture is needed. Use a
stable floor/work area with wheels raised for precaution; do not place an active
robot near a desk edge. Have the normal stop control and power disconnection ready.

1. Follow the existing diagnostic commands to confirm configured display, buzzer
   and distance availability without starting movement. Expected: ready or a
   precise unavailable explanation. Correct setup first; do not bypass checks.
2. Disable optional speech for the first test and select a modest reviewed buzzer
   volume. Start the shortest real game. Expected: wheels remain still and the
   display explains the game.
3. Move a hand slowly through the documented bands without touching electronics.
   Expected: nearer produces higher short tones, boundary jitter is controlled,
   and output stays within the documented duration and volume.
4. Move the hand outside the game area. Expected: silence within the measured
   freshness bound and a neutral indication; a prolonged invalid reading ends the
   game. Do not pull live I2C wires to simulate a failure.
5. Stop during a tone using the independent terminal/button control. Expected:
   measured silence and no late face/tone. Record elapsed time and any uncertainty.
6. Allow one short game to expire. Start another only by explicit request.
   Expected: no queued game, automatic replay or lingering sound.
7. With Phase 3 already physically accepted, play a short approved spoken reply
   and then explicitly start the game. Expected: foreground coordination prevents
   overlap and no delayed speech restarts afterward. Test a due display/buzzer
   reminder as a separate consented case; it should end the game and preserve
   existing notification behavior.
8. Check B02's optional variants using existing harmless expression commands.
   Expected: familiar meaning, no new startup/idle sounds and no stronger cue.

Rollback: Stop Game, disable variations/new game exposure in the reviewed
configuration, and restore prior speech settings only if desired. If silence or
cleanup cannot be confirmed, use the established emergency-stop procedure and
operator power removal if necessary; do not keep retrying outputs on a faulted
device. Record physical results without claiming unperformed cases passed.

### Actuator-moving — optional, separate consent

No wheel movement is required to demonstrate the game. Use fake movement for
automated and ordinary acceptance. If the owner separately requests a real
arbitration regression, raise wheels, clear the area, arm through the existing
policy and keep an operator ready to remove power. Start a short game, then issue
one existing bounded movement command. Expected: game ends first; movement obeys
unchanged interlocks and stops normally. A sensor fault rejects movement.

Rollback: existing Stop Movement/emergency stop, disarm, and disable the new game.
Never perform this check at a desk edge or treat it as proof of fall protection.

### Camera, microphone and power risk

Capture is not necessary. Test privacy takeover with fakes first; any real capture
requires separate explicit consent and no retained test media. Do not enable a
listener merely to provide a game-stop mechanism.

No live shutdown, boot-file editing, UPS test, new wiring or new hardware build is
required for Phase 5 acceptance. Power-related coverage stops at construction and
authorization of the existing command path. B05 physical prototypes have their
own later approval and rollback instructions.

## Documentation and rollback

Wiki impact is substantial after implementation, but this task writes plans only.
The owner's deferred wiki ingestion/review workflow remains deferred. Do not apply
a semantic diff or update registered raw originals while preparing this plan.

At the authorized phase checkpoint:

1. Update `README.md`, the master plan/progress and the new walkthrough/handoff
   with optional defaults, real controls, required capabilities and measured limits.
2. Create new Installation Guide, Development Guide, MCP and Skills Guide and
   Development Log source versions. Explain game limits, stop paths, configuration,
   Lite terminal use, sensor recovery and B05's evaluation-only status. Preserve
   both registered originals and prepared Phase 3 Lite corrections.
3. Document the resource/admission changes and any unresolved blocked-driver
   limitation. Include the affected test list and exact gate results. Distinguish
   software evidence, operator observations and hardware questions still open.
4. Keep B05 recommendations separate from supported hardware claims. Update
   `THIRD_PARTY_NOTICES.md` only if an actual dependency/service change occurs;
   linking a datasheet does not mean its driver is installed or supported.
5. When wiki work resumes, prepare affected source/page/reference and fingerprint
   changes, show the exact semantic diff and obtain approval before application.
   Run `python scripts/wiki.py check`, wiki lint and document-link checks afterward.
   Do not turn an unreviewed prototype proposal into current operating instructions.
6. Make rollback additive: disable variant selection and game exposure, cancel
   active sessions, preserve previous configuration and private data, and keep
   reliability fixes that have passed their own compatibility gate. A rollback
   must not reopen a driver with an unresolved read merely to restore old behavior.
7. Pause after handoff for owner acceptance. B05 build decisions and deferred
   refinements remain separate future work.

## Planning validation

The two plan documents were checked for valid local links and heading anchors.
All four illustrative Python blocks across the plans were parsed and executed
with 30 focused checks, including invalid calendar times, a repeated daylight-saving
hour, citation membership, stable variant selection and distance-band boundaries.
The two Bash gate blocks were checked for shell syntax without running their
commands. New-document whitespace was checked separately from the tracked diff.
These checks validate the planning artifacts; they do not validate the future
implementation. No robot code, managed driver, account, live configuration or wiki
publication state was changed, and the runtime suite was not rerun for this task.

## Completion checklist

- [ ] B02 is optional, bounded and uses existing reviewed assets without changing
  canonical behavior, safety/privacy presentation, startup or silent idle.
- [ ] B04 starts only on request, ends on time, handles bad data, and has a trusted
  stop available while ordinary conversation or scheduling is busy.
- [ ] The game owns no servo resource and issues no wheel, camera, microphone or
  system-power command.
- [ ] Shared distance access remains single-flight across cancellation, timeout,
  close and recovery; unresolved reads prevent unsafe device reuse.
- [ ] Incoming authorized conflicts cancel the game before resource acquisition;
  denied actions, queue saturation and safety races are tested.
- [ ] Output ownership, late callbacks, reminder behavior and Phase 3 speech/input
  semantics remain correct; stop failure is reported honestly.
- [ ] Full and focused software gates pass without managed-driver modifications.
- [ ] Physical acceptance is recorded separately with measured timing and explicit
  missing cases. No fall-prevention or untested hardware claim is made.
- [ ] B05 provides four evidence-backed option specifications and decisions;
  purchases/prototypes remain separately authorized.
- [ ] Manuals, walkthrough, handoff and deferred wiki status are accurate and the
  owner has a clear next decision.

For existing installation or speaker recovery, use the
[Phase 3 Lite walkthrough](../docs/validation/refinement_phase3_walkthrough_260909.md).
For approved knowledge publication, follow the
[wiki maintenance workflow](../ninjarobot_pi5_wiki/docs/PROJECT_WORKFLOW.md).
