# NinjaRobotPi5 Phases 3, 4 and 5 audit — 13 September 2026

This draft collects the audit evidence available when the project owner requested
a collected report, with a resumption check on 14 September. It is a substantial audit
checkpoint, not a claim that every possible failure or every physical device has
been tested. It includes confirmed defects, the checks that passed, documentation
discrepancies, and a practical correction plan.

**Audited checkout:** commit `3d7e522` (`implementation complete`). The checkout
was clean when the audit started. No robot runtime code, managed driver, live
configuration, account, or stored user data was changed during this audit.

**Resumption checkout:** `0e1c9b8` (`ingest and review the wiki content`). This
subsequent commit changes wiki documentation and registration, not runtime code.
The three synthetic diagnostics were rerun on 14 September and reproduced the
same findings. A targeted project-help test now fails because the updated wiki
pages no longer match the runtime's old public manifest. This is recorded as A08;
the earlier successful full-suite result must not be read as a pass on this newer
checkout. The report filename retains the original audit date.

## Contents

- [Overall assessment](#overall-assessment)
- [Scope and evidence](#scope-and-evidence)
- [Implementation assessment by phase](#implementation-assessment-by-phase)
- [Confirmed findings](#confirmed-findings)
- [Correction implementation sequence](#correction-implementation-sequence)
- [Documentation discrepancies](#documentation-discrepancies)
- [Validation results](#validation-results)
- [Reproducing the findings safely](#reproducing-the-findings-safely)
- [Remaining acceptance and audit work](#remaining-acceptance-and-audit-work)
- [Documentation and wiki handoff](#documentation-and-wiki-handoff)

## Overall assessment

The new features have a sound foundation: hardware access remains behind the
existing IDE (the software layer that coordinates and protects devices), most
operations have explicit limits, and important cancellation and ownership paths
have automated tests. All **887 main-suite tests passed on the original audited
commit**. Another
**457 standalone driver tests passed**, each driver in its own test process.
Lint, formatting, type checks, compilation and both driver verifiers also passed.

Those passing checks do not establish that the implementation is complete or
free of defects. Additional synthetic tests (tests using temporary data and fake
services) exposed **seven findings**, including a profile-isolation defect in
recipes and several Phase 4 integration failures. These failures were not covered
by the existing successful test suite.

The 14 September resumption adds **A08, an eighth confirmed finding**: runtime
project help withholds the newly published pages because its manifest was not
updated with them. Its targeted suite now reports **1 failed, 12 passed**.

The highest priorities are to prevent a recipe from returning the previous
user's information after a profile switch, make calendar disconnection recoverable,
retain briefing text after an optional speech timeout, and enforce research
references in the final chat answer.

No new Phase 3-only or Phase 5-only runtime defect was confirmed in the paths
reviewed so far. That is a limited inspection result, not certification of those
phases. Physical speech, Bluetooth, sensor and phone-browser acceptance remains
separate from the software checks.

### Finding summary

P1 means high priority, particularly before relying on the affected feature.
P2 means a significant usability or long-running operation problem. No P0
(critical emergency) finding was established in this audit checkpoint.

| ID | Priority | Area | Confirmed problem | Status |
| --- | --- | --- | --- | --- |
| A01 | P1 | M04 recipes and user identity | A running recipe can return the previous user's profile after the active user changes. | Reproduced; correction pending |
| A02 | P1 | T04 calendar disconnection | An interruption can leave a credential stored after disabling the connection; retry then refuses cleanup. | Reproduced; correction pending |
| A03 | P1 | T06 briefing and Phase 3 speech | Optional speech can exhaust the shared deadline and discard an already built text result. | Reproduced; correction pending |
| A04 | P1 | T05 research | The final Agent answer can bypass the evidence renderer and present an invented citation. | Reproduced; correction pending |
| A05 | P2 | T04/T06 reviewed deletion | Calendar cancellation and note deletion previews omit the current readable title; calendar cancellation also omits the current event times. | Reproduced; correction pending |
| A06 | P2 | T04 connection listing | Only the first 20 connections are returned, with no way to request the next page. | Reproduced; correction pending |
| A07 | P2 | T04 information retention | The calendar-operation limit can permanently block further previews without a supported individual cleanup route. | Capacity failure reproduced; cleanup gap confirmed by inspection |
| A08 | P1 | X05 runtime project help | Updated wiki pages no longer match the pinned runtime manifest; the tested Bluetooth query returns no results. | Reproduced on 14 September; correction pending |

## Scope and evidence

The review used Serena symbol inspection, targeted source reads, plan and manual
comparison, existing automated tests, and additional temporary-data diagnostics.
The focus was the new features and their shared boundaries. It was not a new
line-by-line audit of every historical driver or every older robot capability.

### Plans and documentation examined

- [Main refinement plan](NinjarobotPi5_RefinementPlan_260907.md), with the Phase 3–5 delivery context.
- [Phase 4 implementation plan](Phase4_NinjarobotPi5_RefinementPlan_260909.md), including T04–T06 and M03/M04/X01/X05.
- [Phase 5 implementation plan](Phase5_NinjarobotPi5_RefinementPlan_260909.md).
- [Project README](../README.md), [wiki README](../ninjarobot_pi5_wiki/README.md), knowledge map and relevant project knowledge guidance.
- The latest full [Installation Guide](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-13-03/InstallationGuide.md) and [Development Guide](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-13-03/DevelopmentGuide.md), particularly their new feature sections and related operational claims.
- Phase 3, Phase 4 and Phase 5 handoffs and walkthroughs under `docs/validation/`.
- All five documents in [the Phase 5 hardware evaluation](hardware/HardwareOptions_260912.md), covering the shared evaluation and speaker, touch, movable-head and desk-edge proposals.

At the original audit start, the published knowledge map identified the
12 September checkpoint and newer manuals were pending ingestion. At resumption,
commit `0e1c9b8` had registered the `2026-09-13-03` manuals and updated curated
pages. The map records review by `agent:antigravity` against `3d7e522`.
Runtime project help still uses its 12 September manifest; changed page hashes
now cause results to be withheld (A08). Recorded AI review is not equivalent to
human acceptance or physical verification. This audit did not perform that wiki
ingestion/review or alter its results.

### Main implementation areas inspected

Paths below are relative to the indicated package's `src` directory.

| Area | Principal files and boundaries examined |
| --- | --- |
| Phase 3 speech | Agent `speech.py`; IDE `audio_output.py`, speech configuration, microphone/voice reservations and `robot.py` speaking presentation |
| Bluetooth setup and reconnection | IDE `bluetooth_setup.py`, `bluetooth_speaker.py`; selected-device pairing, saved settings, independent user service and retry behavior |
| Chat and controls | Agent `web_static/app.js`, layout regression script, command-help and speech/game control paths |
| Phase 4 memory | Agent `memory_services.py`, ranking tests, `memory_mcp.py` and active-user resolution |
| Phase 4 recipes | Agent `recipes.py`, `recipe_controls.py`, runtime tool execution, profile switching and recipe tests |
| Skills and project help | Agent `skills.py`, `project_help.py`, compatibility and path-confinement tests |
| Notes and shared records | Agent `notes_service.py`, `information_store.py`, `information_tools.py`, `information_controls.py`, migrations and temporary-data tests |
| Calendar | Agent `calendar_service.py`, `calendar_google.py`, `calendar_oauth.py`, account controls and transport tests |
| Research and briefings | Agent `research_service.py`, briefing integration, final-answer handling in `agent_loop.py` and evidence-renderer tests |
| Phase 5 interactions | IDE `distance_game.py`, `distance.py`, `expression_variants.py`, shared-device admission, cleanup and related tests |

Existing robot APIs (interfaces used by other code), driver files and hardware
ownership were treated as compatibility boundaries. No model, private conversation
database, real credential, camera or microphone recording was needed for the audit.

## Implementation assessment by phase

### Phase 3 — Spoken replies and coordinated output

**What is implemented well:**

- Optional Piper synthesis (turning text into sound) runs locally in a separate
  environment. English is supported; Mandarin requires a compatible supplied
  model. Japanese robot speech is not implemented.
- Generated audio is temporary and checked for format, size and duration.
  Playback goes through the IDE rather than allowing Agent hardware access.
- Output uses the configured PipeWire device (the operating system's audio
  route). A missing speaker does not intentionally select an unrelated default
  output. A reported playback success explicitly does not prove the user heard it.
- Speech on/off and stopping are separate controls. Microphone reservations and
  the speaking face cooperate with existing foreground actions and safety state.
- Bluetooth setup scans, presents numbered choices, pairs/trusts/connects the
  selected device, checks its audio output, and preserves existing settings.
- The optional reconnect service runs independently of the Agent. It reconnects
  only an already paired and trusted saved device; it does not pair unknown
  devices or start the robot. Boot/logout operation still depends on the user's
  audio services and explicitly configured user lingering (keeping those services
  available without an interactive login).
- The opening-word mitigation prepends a bounded amount of silence to the same
  audio stream without dropping original samples. This is a reasonable mitigation,
  but some physical speakers suppress silent input. Actual cold-start listening
  remains necessary.

**Limits and findings:** A03 is a cross-phase integration problem: the briefing
controller can lose text even though ordinary speech failure handling is designed
to retain it. Browser dictation is speech input, distinct from Piper robot output.
The automated browser layout script was inspected; a fresh execution had not
completed at this reporting checkpoint.

### Phase 4 — Connection information and reusable documentation

| Feature | Assessment |
| --- | --- |
| M03 — Better memory retrieval | Bounded, user-scoped retrieval, preference handling, duplicate filtering and fallback search have useful synthetic coverage. This is improved search, not a new general learning system. Concurrent recipe delivery exposes the separate A01 isolation gap. |
| M04 — Reviewable recipes | Versioned recipes have explicit review hashes (content fingerprints), a closed list of seven read-only tools, explicit run confirmation, time limits and per-step contract checks. A01 must be fixed. Calendar writes and hardware actions remain outside recipe scope. |
| X01 — Skill compatibility | Version-1 packages remain supported. Version-2 requirements check required tools and minimum versions. Optional capabilities do not grant new authority. No specific defect was established in the inspected compatibility path. |
| X05 — Read-only project help | Fixed public sources, fingerprints, bounded excerpts and path restrictions are appropriate. Subsequent wiki publication did not update the runtime manifest, so changed pages are withheld. A08 blocks the tested lookup; developer wiki search and runtime help are separate paths. |
| T04 — Calendar planning | Explicit account setup, bounded reads, strict time-zone handling, owned-event restrictions, review expiry, version checks and uncertain-write recovery are strong foundations. A02, A05, A06 and A07 remain. |
| T05 — Research with evidence | Bounded provider excerpts, real source records, separate reviewed saving and a conservative renderer exist. A04 means the final conversational answer does not yet enforce that renderer's guarantees. |
| T06 — Notes, checklists and briefings | Owned notes, stable checklist item IDs, revision checks, atomic local confirmation and deterministic requested briefings are useful. A03 affects spoken briefings; A05 affects deletion review. |

Calendar writes use `If-Match` with an ETag (the remote event's version marker)
for updates and deletions. That matches Google's documented conditional-change
mechanism. Insert operations require a separate event-ID strategy rather than
an insert ETag. See [Google's resource-version documentation](https://developers.google.com/workspace/calendar/api/guides/version-resources).

The account helper uses an explicit Desktop authorization flow, a loopback
callback (a local-only return address), a random state check and PKCE (proof that
the same application started and finished authorization). These choices were
compared with [Google's installed-app authorization documentation](https://developers.google.com/identity/protocols/oauth2/native-app).
No real Google authorization or remote calendar write was performed.

### Phase 5 — Optional interactions and hardware evaluation

**B02 expression variations:** Changes are limited to small, repeatable colour
variations of selected existing faces. The setting starts disabled. The inspected
code does not add movement, sound, new safety faces or an automatic idle activity.

**B04 distance game:** The IDE owns the game. Admission reserves the activity
before taking shared devices, and stop/status remain available while it runs.
Samples are rejected when invalid, stale, repeated or too slow. A short median
filter smooths readings; hysteresis (different thresholds when entering and
leaving a band) reduces rapid switching. Tone duration and total sounding time
are bounded. Uncertain cleanup remains a fault rather than falsely reporting a
successful recovery.

The distance adapter retains ownership of a blocking read after the caller is
cancelled. The late result does not become a new game sample. This matters because
cancelling an asynchronous caller does not automatically terminate the underlying
device-reading thread. Relevant tests cover stopped reads, stale data, incoming
foreground output and failure to silence the buzzer.

**B05 hardware evaluation:** Speaker alternatives, touch input, a movable head
and desk-edge sensing are proposals with explicit missing measurements and approval
gates. They are not implemented hardware. In particular, the forward distance
sensor and hand game do not establish protection against falling off a desk.
No purchase, wiring, new motor, power measurement or physical prototype was
performed by this audit. Candidate availability and prices were not refreshed.

## Confirmed findings

### A01 — Recipe results can cross an active-user change

**Priority:** P1. **Estimated effort:** Medium.

**User impact:** A recipe started by one user can finish after the interface
switches to another user and still return the first user's profile. This violates
the project's intended separation of local users. It is not evidence that face
identity is formal authentication, or that a remote attacker bypassed web pairing.

**Evidence:** [recipe_controls.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/recipe_controls.py),
`_recipe_action`, checks scope before each step but does not repeat the check after
the awaited tool call or before returning collected results. The runtime's
`_set_active_user` updates identity and revokes motion/camera permissions without
invalidating these recipe results. The memory provider resolves a user before
awaiting the profile data and can return that original user's result later.

The diagnostic uses the actual memory provider with temporary profiles. It delays
delivery of the original user's profile, changes the active profile through the
runtime method, then releases the result. It reports:

```text
recipe scope changed: True
recipe result: completed
previous owner data returned: True
```

The profile change simulates an already authorized identity transition. No camera
or real face enrollment is used.

**Correction implementation plan:**

1. Bind each recipe request to its starting session, user and identity generation
   (a counter that changes whenever that session changes user).
2. Check the binding immediately before dispatch, after every awaited tool result,
   before recording private result content and before returning or streaming it.
   A switch away and back must still invalidate the original operation.
3. Cancel owned private work when the active identity changes. Cancellation alone
   is insufficient: completed or slow providers must still pass the final binding
   check. Keep other sessions' independent work intact.
4. Add matching result-delivery protection to the memory provider or shared runtime
   boundary, so fixing recipes does not leave another direct caller exposed.
5. Withhold old private results and record a cancelled/stale-owner outcome. Do not
   retry the request automatically under the new user.

**Acceptance tests:** One-step and multi-step recipes; switch during a read and
during receipt persistence; switch away and back; different browser/terminal
sessions; cancellation arriving after provider completion. The old user's data
must not appear in a response, stream or another user's receipt.

**Until corrected:** Finish or cancel a private recipe before switching the
active profile in that interface.

### A02 — Interrupted calendar disconnection is not recoverable by retry

**Priority:** P1. **Estimated effort:** Medium.

**User impact:** A local credential can remain stored after a connection has been
disabled. A retry reports that the connection is disabled instead of completing
credential removal. This does not mean the ordinary calendar service continues
to authorize new calls through that disabled connection.

**Evidence:** [information_tools.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/information_tools.py),
the `calendar.disconnect` branch, disables the database record, awaits stopping
owned work, then removes the token cache and stored credential. If interrupted
between those steps, the next attempt fails the enabled-connection check.

```text
credential_remains: true
retry: calendar connection is disabled or disconnected
```

The test injects cancellation immediately after disabling the record. Credentials
are fake strings in a temporary secret store. Profile-deletion cleanup has a
separate path for disabled connections; that does not make ordinary disconnect
retry correct.

**Correction implementation plan:**

1. Allow an owned disabled connection to enter the cleanup path. Validate ownership
   without requiring the connection to remain enabled.
2. Keep disabling as the first durable step to prevent new use. Persist a cleanup
   state or otherwise make each subsequent step safely repeatable.
3. Cancel/drain owned in-flight work, clear cached tokens and delete the credential.
   Report completion only after those steps are confirmed.
4. Recover incomplete cleanup on startup and explicit retry. Missing credentials
   should count as already cleaned, not cause another failure.
5. Keep local cleanup distinct from revoking access at Google. Do not delete remote
   events or silently change another connection that uses a different credential.

**Acceptance tests:** Inject cancellation or failure after every step; restart
with a disabled record and stored credential; disconnect twice; simulate a failed
secret-file write and concurrent token refresh. No successful cleanup report may
leave its credential behind.

**Until corrected:** Treat an interrupted disconnect as incomplete credential
cleanup. Do not delete a user profile merely to work around this defect.

### A03 — Optional speech can prevent delivery of completed briefing text

**Priority:** P1. **Estimated effort:** Low to Medium.

**User impact:** A local briefing can be ready, but the user receives a timeout
instead of its text because speech took too long.

**Evidence:** [information_controls.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/information_controls.py),
`information_action`, puts briefing construction and optional speech inside the
same deadline: the smaller of 40 seconds and the configured request limit.
The return occurs only after speech completes. Timeout becomes an exception and
the completed `data` is not returned.

The diagnostic shortens only the fake runtime deadline to 0.1 seconds and uses
a delayed fake speaker. It verifies that text construction finished first:

```text
text_built_and_speech_started: true
result: TimeoutError: no briefing returned
```

This accelerated test demonstrates the deadline ordering; it is not a measurement
of real Pi synthesis speed or a claim that production uses a 0.1-second timeout.

**Correction implementation plan:**

1. Separate the completed text result from optional audio delivery. Once built,
   retain it as the primary result.
2. Give audio an explicit remaining budget or an owned, separately bounded output
   task. On an audio timeout, stop the owned playback and return text with an
   accurate audio-failure status.
3. Preserve user cancellation and identity checks. A profile change must withhold
   private text rather than being mistaken for a harmless speaker failure.
4. Record information completion and audio failure separately. Do not mark an
   already delivered briefing as wholly failed merely because it was not spoken.

**Acceptance tests:** Slow synthesis, slow playback, waiting on the chat lock,
disconnection, speech off/stop, user cancellation and profile changes. Test the
CLI (command-line interface), `/info` chat and web path with no real sound.

**Until corrected:** Use `/speech off` before a direct `/info briefing.build`
request when reliable text delivery is more important than spoken output.

### A04 — Final research answers can bypass citation validation

**Priority:** P1. **Estimated effort:** Medium to High.

**User impact:** The user can receive a confident answer with an invented source
reference even though the search service stored valid source records.

**Evidence:** [research_service.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/research_service.py),
`answer`, rejects unknown source IDs and qualifies unsupported interpretations.
However, [agent_loop.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py)
accepts the model's final text directly when the turn finishes without more tool
calls. Calling the evidence renderer is not a mandatory final-response step.

A fake model performed one `research.search` call. The fake provider supplied
one real source for that run, `S1`. The model then returned this unchanged answer:

```text
tool_calls: 1
final_reply: This unsupported claim is proven [S999].
```

The direct renderer tests still pass. They do not cover bypassing the renderer
through the normal Agent loop. The Phase 4 plan explicitly requires cited claims
to reference actual results from the current run.

**Correction implementation plan:**

1. Track which owned research runs belong to the active request and whether the
   final response is presenting research evidence.
2. Route research answers through a structured claims-and-source-ID contract and
   the existing deterministic renderer. Reject unknown or different-run references.
3. Validate before returning or streaming final research claims. Previously emitted
   text cannot be made safe by checking only after the complete answer arrives.
4. Preserve excerpt/interpretation labels, source dates, links and incomplete-result
   warnings. Valid IDs alone must not be described as proof of a claim.
5. Allow a bounded correction attempt within existing limits, or return a clear
   qualified evidence summary. Do not add unlimited model retries or web fetching.

**Acceptance tests:** Ordinary Agent chat, streamed answers, invented IDs, valid
IDs from another run, omitted references, unsupported claims, empty search results,
provider errors, cancellation and private-note saving. Keep ordinary non-research
chat working without forcing it through the research formatter.

**Until corrected:** Prefer the explicit `research.answer` result for reviewed
evidence and verify its links. Do not treat arbitrary chat citations as validated.

### A05 — Destructive previews omit the readable item being removed

**Priority:** P2. **Estimated effort:** Medium.

**User impact:** A user sees technical IDs and a review hash but cannot reliably
recognize what is about to be deleted from the preview alone.

**Evidence:** [calendar_service.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/calendar_service.py),
`propose`, fetches the existing event for cancellation but stores its version
marker rather than a readable before-state. The cancellation body is `{}`.
[notes_service.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/notes_service.py),
`propose`, verifies a note revision but stores a delete change with `content: null`.
The diagnostics confirm that the existing titles, and the calendar times, are
missing from the returned previews.

This is not a finding that arbitrary items can be deleted without confirmation.
Ownership, revision and explicit confirmation checks still exist. The weakness
is whether the operator has enough information to make that confirmation meaningful.

**Correction implementation plan:**

1. Add a bounded readable before-state to delete/cancel previews: note title and
   revision; event title, account/calendar, start/end and time zone.
2. Show clear before/after values for updates where useful. Keep the underlying
   record ID visible to distinguish identical titles.
3. Include those displayed values in the review hash. Do not fetch a changed title
   later and present it as though it belonged to the original approval.
4. Retain current stale-revision, expiry and same-session confirmation rules.
   Escape text in the browser and paginate larger review material.

**Acceptance tests:** Identical titles, Unicode text, all-day events, renamed items,
changed remote versions, expired previews and long content. The user must recognize
the target before confirming, and a changed target must require a fresh preview.

**Until corrected:** Read the exact note or calendar event immediately before
reviewing its deletion, and compare the item ID. Avoid guessing from an ID alone.

### A06 — Connection listing silently stops at 20

**Priority:** P2. **Estimated effort:** Low.

**User impact:** A user with many saved or previously disconnected connections
cannot discover all of them through the public listing operation. A useful active
connection can be hidden behind older records.

**Evidence:** The `calendar.connections` branch in
[information_tools.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/information_tools.py)
uses the store's default page size of 20, then drops `next_after` (the continuation
marker used to retrieve another page). The public operation does not expose an
equivalent next-page input.

```text
stored: 21
returned: 20
cursor_exposed: false
```

**Correction implementation plan:** Add a bounded `after` input and return the
continuation marker and completeness status. Expose the same pagination through
the tool schema, CLI/help and chat instructions. Consider an explicit enabled-only
filter without making disabled records impossible to inspect or clean up.

**Acceptance tests:** 0, 20, 21 and more than 100 connections; disabled records;
stable ordering; wrong-user continuation attempts; and bounded serialized output.
Do not solve this by returning every full record in one oversized message.

### A07 — Calendar-operation capacity has no practical individual cleanup

**Priority:** P2. **Estimated effort:** Medium to High.

**User impact:** After enough calendar previews and receipts accumulate, the
service refuses new calendar operations and tells the user to remove records,
but provides no supported individual calendar-receipt removal operation.

**Evidence:** [information_store.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/information_store.py)
limits each record kind to 1,000 per user. Its startup recovery prunes old research
records and note previews, not calendar operations. The public information controls
do not expose individual calendar-operation deletion. Profile reset is too broad
to be a reasonable normal maintenance action.

The temporary-data diagnostic fills the calendar-operation kind to 1,000 records
and retries creation before and after startup recovery. Both return:

```text
record limit reached; review and remove old records
```

**Correction implementation plan:**

1. Design explicit retention and reviewable maintenance for expired/cancelled
   proposals and historical terminal receipts. Expose capacity before exhaustion.
2. Preserve unresolved dispatched operations for reconciliation. Do not delete
   records that might still represent an unknown remote effect.
3. Preserve compact ownership evidence for robot-created events: calendar update
   and cancellation currently depend on verified creation receipts. Blindly pruning
   all old receipts would make legitimate events unmanageable.
4. Separate necessary event-ownership evidence from disposable preview history,
   or introduce an equivalent compatible archival design. Any migration must be
   repeatable and retain existing data and identifiers.
5. Replace the misleading error with actionable guidance backed by an implemented
   maintenance route. Never recommend resetting all user memory to free capacity.

**Acceptance tests:** Capacity reached with expired previews, verified creations
and uncertain operations; repeated cleanup; restart; interrupted migration;
remaining ability to update an owned event; backup/restore and wrong-user requests.

**Until corrected:** Avoid repeated unnecessary calendar previews. Restart alone
does not free calendar-operation capacity. Keep existing receipts intact.

### A08 — Wiki publication left runtime project help pointing to old hashes

**Priority:** P1 for the affected help feature. **Estimated effort:** Low to Medium.

**User impact:** Publishing new wiki pages does not automatically make them
available to the robot's project-help tool. On the resumption checkout, a
Bluetooth query returns zero results. The older warning also says later sources
are not ingested even though the knowledge map now records their ingestion.

**Evidence:** The subsequent wiki commit updates curated page contents without
changing [project_help_manifest.json](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/project_help_manifest.json).
The content checks in `ProjectHelpProvider.lookup` correctly refuse mismatched
pages. The existing `test_real_public_checkpoint_and_missing_checkout` fails at
`assert result["results"]`; its test file reports **1 failed, 12 passed** on
14 September. A direct read-only lookup produces:

```text
results: 0
public-1: withheld (page changed since the public manifest was prepared).
public-2: withheld (page changed since the public manifest was prepared).
public-3: withheld (page changed since the public manifest was prepared).
public-4: withheld (page changed since the public manifest was prepared).
```

This is an availability and publication-integration defect, not a reason to remove
fingerprint checks. No private-source access or fabricated fallback was observed.
The earlier full-suite pass predates this wiki change.

**Correction implementation plan:**

1. Review the newly registered public sources and curated claims for the exact
   subset allowed in runtime help. Include unresolved audit limitations.
2. Prepare a reviewed update of the fixed public manifest: source versions,
   citation IDs, content hashes, coverage date and honest review states. Do not
   blindly refresh hashes or scan arbitrary private folders.
3. Make coverage warnings reflect the selected manifest and actual publication
   state instead of assuming all later sources remain un-ingested.
4. Treat page publication and the runtime-manifest update as one coordinated
   delivery. Add a check that catches mismatches before reporting help as available,
   while still withholding unexpected page changes at runtime.
5. Preserve path restrictions, read limits, missing-checkout behavior and the
   distinction between developer wiki search and robot help.

**Acceptance tests:** Current-checkout queries for Bluetooth, speech and Phase 4/5
capabilities; stale/tampered pages; missing citations; wrong source hashes; missing
checkout; and private-path rejection. Update the checkpoint test to assert the
reviewed manifest's actual coverage, not simply a hard-coded date.

**Until corrected:** Read the full manuals directly from the wiki README. Do not
interpret an empty runtime result as evidence that a feature is absent. Runtime
manifest correction is pending work, not part of this draft.

## Correction implementation sequence

This is a proposed future implementation plan. The current audit request does
not authorize applying these runtime changes. Preserve existing interfaces where
possible and use new optional fields rather than breaking callers.

| Increment | Objective and likely files | Compatibility and safety | Validation gate |
| --- | --- | --- | --- |
| 1 | A01: `recipe_controls.py`, `runtime.py`, `memory_mcp.py`, scope tests | Keep the existing user model; add request invalidation, not a new identity system. No camera action required. | Delayed private results never cross an identity change; all recipe and memory tests pass. |
| 2 | A02: `information_tools.py`, credential lifecycle and recovery tests | Disabled connections remain unusable; cleanup becomes repeatable. No live Google account needed. | Every injected interruption can be recovered; no orphaned credential after reported success. |
| 3 | A03: `information_controls.py`, briefing/speech integration tests | Preserve existing speech off/stop and IDE ownership. No new player or hardware path. | Completed text survives audio failure; private cancellation still withholds text. |
| 4 | A04: `agent_loop.py`, `research_service.py`, prompt/stream tests | Reuse the existing evidence renderer and budgets; no extra provider or unlimited retry loop. | Final and streamed research answers cannot publish invented IDs as valid evidence. |
| 5 | A05/A06: previews, information schemas, CLI/help, tests | Add readable bound review fields and bounded pagination; retain legacy default first-page behavior where feasible. | Readable exact targets; stale approvals refused; all connections discoverable. |
| 6 | A07: information retention/store, reviewed maintenance controls and migration if needed | Preserve unresolved writes and event-ownership evidence; no destructive automatic reset. | Capacity recovery, restore and owned-event management all pass. |
| 6a | A08: reviewed runtime public manifest, coverage wording and help tests | Preserve current wiki content and hash/path protections. | Current-checkout help succeeds on reviewed sources; tampered sources still fail closed. |
| 7 | Documentation and release evidence | Update complete versioned manuals and walkthroughs once the corrections stabilize. Preserve registered wiki originals. | Valid links, honest limits and evidence; separately approved publication if requested. |

After every runtime increment, run the required driver verifiers, compilation,
lint, formatting, type checks, relevant regression tests and full main suite.
Repeat standalone driver suites if a driver-facing boundary changes. Run the
browser regression when final-answer streaming or UI presentation changes.

Rollback should restore the affected software while retaining user data. If a
data migration is introduced, define its backward-compatibility and restore steps
before deployment. A restored database cannot undo a remote calendar write.

## Documentation discrepancies

The following corrections were identified but **have not been applied at this
reporting checkpoint**. The earlier request authorizes correcting documentation;
the immediate follow-up requested this collected draft before further work.
These items must not be reported as already fixed.

| Document and existing claim | Why it needs correction | Required wording or action |
| --- | --- | --- |
| Root README: “all commands simulate unless you explicitly add `--real`” | Hardware simulation is not a global dry-run for local persistence, Bluetooth setup or confirmed external account operations. Commands can also target an already running service. | Explain that hardware mode belongs to the relevant launcher/service. Local notes persist and confirmed calendar writes affect the real account regardless of hardware simulation. Mark Bluetooth setup as an explicit real OS operation. |
| Root README: “Four-language browser speech” | The browser code uses speech recognition for input. This can be confused with Japanese robot speech, which is not implemented. | Say “browser dictation/speech input” and distinguish it from English/optional Mandarin Piper output. Retain browser-support limitations. |
| Root README speech technology row lists only `whisper.cpp` | It omits the newly implemented output path. | List local microphone transcription separately from Piper speech output through IDE-owned PipeWire playback. |
| Root README and Development Guide: no model-facing “memory mutation tool” | The four `memory.*` tools are read-only, but new note tools persist change proposals. The broad statement is misleading across the information assistant. | Scope the statement to profile/behavior memory tools. Explain that note tools create proposals and only direct reviewed confirmation applies note edits. |
| Root README: recent successes and recipes are “always available” in bounded retrieval | Query matches can fill the final cap before recent fallback items are included. | Describe relevance-first selection and recent fallback items subject to the shared limit; do not promise every category is always present. |
| Installation and Development Guides: every delete has an “exact preview” | The ID and revision are bound, but the current readable deletion target is absent; see A05. | Explain this limitation until readable before-state previews are implemented. Keep the genuine ownership and confirmation guarantees. |
| General text-retention claims alongside spoken replies | Ordinary speech error handling does not guarantee direct briefing text survives the shared timeout; see A03. | Qualify the current briefing limitation and document speech-off as the temporary operational option. |
| Installation and Development Guides: saved notes and calendar receipts persist until “explicit deletion or profile reset” | Notes have a reviewed delete operation; calendar receipts do not have an equivalent individual public cleanup route. | Describe the two retention mechanisms separately and disclose the current calendar capacity limitation. |
| Research descriptions suggesting cited final answers are consistently validated | The explicit renderer validates source IDs, but arbitrary final model text bypasses it; see A04. | Distinguish rendered evidence from unvalidated conversational output until the final-response guard is implemented. |
| Root README and retained manual sections say the latest Phase 4/5 sources are pending ingestion | The resumption commit registers those sources and updates pages, while the runtime manifest remains old. | Date historical deferral statements and describe current ingestion separately from the unresolved runtime-help mismatch, A08. |

Historical handoff statements such as “Phase 4 has not started” describe an older
checkpoint. They should be clearly presented as history rather than rewritten as
though later work had already existed at that date. Current navigation should
identify the latest status and link this audit's unresolved findings.

When applying corrections, create new complete source revisions, for example
`raw/articles/ninjarobotpi5/2026-09-13-04/`, and update the two READMEs to point to
the corrected current manuals. Preserve the registered originals. The detailed
manual-link audit remains unfinished; this report does not assert that every
legacy README/manual link has been validated.

## Validation results

### Checks completed during this audit

Commands ran from the repository root. `--no-sync` used the existing environment
without changing the locked robot dependencies.

| Check | Actual result |
| --- | --- |
| `uv run --frozen --no-sync pytest -q` | 887 passed in 36.82 seconds; one existing Starlette test-client deprecation warning |
| `uv run --frozen --no-sync pytest -q pi5buzzer/tests` | 68 passed |
| `uv run --frozen --no-sync pytest -q pi5camera/tests` | 27 passed |
| `uv run --frozen --no-sync pytest -q pi5disp/tests` | 65 passed |
| `uv run --frozen --no-sync pytest -q pi5mic/tests` | 92 passed; existing `audioop` deprecation warning |
| `uv run --frozen --no-sync pytest -q pi5servo/tests` | 134 passed |
| `uv run --frozen --no-sync pytest -q pi5vl53l0x/tests` | 71 passed |
| `uv run --frozen --no-sync python scripts/verify_immutable_drivers.py` | Passed: 222 tracked files, six drivers, baseline plus 56 previously authorized repairs |
| `uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py` | Passed: all six managed libraries execute from this checkout |
| `uv run --frozen --no-sync python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests` | Passed |
| `uv run --frozen --no-sync ruff check .` | Passed on audited baseline |
| `uv run --frozen --no-sync ruff format --check .` | Passed on audited baseline: 444 Python files |
| `uv run --frozen --no-sync mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src` | Passed: 112 source files |
| `node --check ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js` | Passed |
| Additional audit diagnostics | Reproduced A01–A07 with synthetic data; no live hardware or account calls |
| Lint and formatting of three added diagnostic scripts | Passed |
| Resumption: three saved diagnostic scripts on `0e1c9b8` | Reran on 14 September; A01–A07 reproduced |
| Resumption: `uv run --frozen --no-sync pytest -q ninjarobot_pi5_agent/tests/test_phase4_help_skills.py` | **1 failed, 12 passed**; current-checkout lookup failure documented as A08 |
| Final draft checks, 14 September | All 35 report-local links/contents anchors resolve; no trailing whitespace; `git diff --check` passed. This does not cover every manual link. |

The two warnings predate this audit. They are not failures introduced by audit
changes. The microphone warning still needs consideration before changing Python
versions; no dependency or driver upgrade was performed here.

### Checks not completed or not applicable to this checkpoint

- A fresh full browser layout execution. Playwright 1.55.0 and Chromium 140 were
  prepared in a separate cached validation environment, but downloading a browser
  is not a passed browser test. Earlier handoffs record 16 simulated cases; those
  historical results must not be counted as fresh audit evidence.
- Real mobile keyboard/browser testing, acoustic listening tests, Bluetooth
  pairing/reconnection/boot testing, and real game sensor/display/buzzer tests.
- Live Google consent, calendar writes, provider throttling or real Tavily search.
- New wheel/package builds, fresh installation on a clean Pi, or deployment tests.
- Full wiki ingestion, semantic review, publication and implementation-fingerprint
  refresh. These were intentionally skipped.

## Reproducing the findings safely

The three diagnostic files are retained with the audit so a developer can reproduce
the evidence. They use temporary databases, fake credentials/services and the
existing test fixture. They do not connect to a live Agent, run Piper, pair a
speaker, move a device, or contact Google/Tavily.

From a configured checkout root, run:

```bash
uv run --frozen --no-sync python docs/validation/phase345_audit_260913/probe_recipe_scope.py
uv run --frozen --no-sync python docs/validation/phase345_audit_260913/probe_information.py
uv run --frozen --no-sync python docs/validation/phase345_audit_260913/probe_research.py
```

The scripts report observed behavior. **Exit code zero is not acceptance:** at
the audited commit, the printed results expose the defects described above.
After implementing corrections, replace these diagnostic scenarios with durable
regression tests asserting the safe result. A script may need adapting when the
relevant contract changes.

| Diagnostic | Evidence retained |
| --- | --- |
| [Recipe scope probe](../docs/validation/phase345_audit_260913/probe_recipe_scope.py) | Real memory-provider result returned after a synthetic authorized profile switch |
| [Information probe](../docs/validation/phase345_audit_260913/probe_information.py) | Interrupted disconnect, missing pagination, briefing timeout, unreadable deletion targets and capacity before/after recovery |
| [Research probe](../docs/validation/phase345_audit_260913/probe_research.py) | Actual Agent loop accepting a fake model's invented citation after a real local research-service call with fake search data |

## Remaining acceptance and audit work

### Safe smoke checks — no physical device operation

After corrections, rerun the synthetic diagnostics as regression tests, the main
suite, driver verifiers and relevant public command-help checks. Expected result:
current interfaces remain available, old data upgrades safely, and the corrected
failure scenarios cannot leak private results or falsely report completion.

Use the existing [Phase 4 foundation walkthrough](../docs/validation/refinement_phase4_walkthrough_260913.md)
and [information-assistant walkthrough](../docs/validation/refinement_phase4_information_walkthrough_260913.md)
for operator-facing scenarios. Update them with the correction tests before a
future implementation handoff.

### Device communication and audible output — operator-run only

Use the [Phase 3 follow-up walkthrough](../docs/validation/refinement_phase3_followup_walkthrough_260912.md)
and [Phase 5 walkthrough](../docs/validation/refinement_phase5_walkthrough_260912.md).
These are real device tests and may produce sound or initialize configured devices.

| Test | Expected result | Stop/rollback |
| --- | --- | --- |
| Selected speaker off/on with Agent stopped and running | Only the saved speaker reconnects; Agent is not started by the helper; no old utterance replays. | Stop speech; disable the optional reconnect helper using the walkthrough. Preserve pairing and user settings. |
| Cold, warm, idle and reconnected spoken replies | First words are audible; full text remains accessible; Stop Speech responds promptly. | Use Speech OFF and retain text interaction. Do not compensate with uncontrolled volume increases. |
| Missing selected audio output | Clear unavailable status; no fallback to an unintended speaker. | Restore the selected output only through normal setup. |
| Short hand-distance game | Fresh readings produce bounded tones and display changes; invalid/stale readings stop feedback; stop remains available. | Stop the game and leave its optional configuration disabled if cleanup is uncertain. |
| Game interrupted by existing foreground action or system stop | Existing priority rules win; no delayed tone restarts; faults remain visible until legitimate recovery. | Stop through existing controls; do not bypass a failed safety check. |

### Actuator-moving tests — separate and optional

No wheel movement is needed to reproduce this report's findings. Any later motor
regression must be opt-in, with wheels raised and an operator ready to remove
power. Expected result: original motion arming, stopping and recovery behavior is
unchanged. Roll back the affected optional feature if it interferes. Never test
desk-edge safety with an unrestrained moving robot.

### Account, privacy and power-risk tests

Use a dedicated test calendar only after operator authorization for real account
effects. Verify exact previews, one write per confirmation, remote-version
conflicts, uncertain-result reconciliation and repeatable disconnection. A local
backup is not a rollback for a remote write.

Camera or microphone capture requires separate consent and is unnecessary for
the synthetic identity-switch test. No shutdown or reboot was performed. Optional
boot reconnection acceptance is operator work, with a separate power test plan.

### Audit areas still open

- Finish the current-document link and conflicting-claim sweep, then apply the
  identified direct documentation corrections.
- Complete fresh browser layout checks and review final-answer streaming alongside
  the research correction; existing JavaScript syntax success is insufficient.
- Extend concurrency review beyond the reproduced recipe case to other private
  result-delivery routes, user deletion and switch-away/switch-back behavior.
- Validate each proposed fix through public controls, not only isolated services.
- Record physical acceptance honestly, including device model, OS/audio setup,
  test conditions and observed failures. Owner reports and automated results
  should remain distinguishable.

## Documentation and wiki handoff

This checkpoint adds the audit report and three synthetic diagnostic scripts.
It does **not** fix runtime defects or modify the current manuals. Documentation
corrections are listed explicitly above and remain outstanding.

Wiki impact: the audit contains new, important evidence about implementation
limits and should eventually inform the current feature pages and full manuals.
This audit did not change registered source originals, the knowledge map, curated
pages or review records. It preserved the subsequent wiki update already present
at resumption. No additional ingestion, review, publication, commit, push or release
was performed by this audit. Current runtime-help integration needs A08 even
though the newer source ingestion is now recorded.

The recommended next step is to review A01–A04 first, complete the direct manual
corrections, and then authorize the correction implementation sequence. Keep the
existing Agent → IDE → device-driver framework and existing hardware behavior.
