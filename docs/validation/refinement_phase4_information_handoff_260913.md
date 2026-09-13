# Phase 4 information assistant — implementation handoff

T04 calendar planning, T05 research with evidence and T06 notes/checklists/
requested briefings are implemented. This completes the previously deferred
information work alongside the earlier M03, M04, X01 and X05 delivery.
Live Google account and speaker acceptance remain for the owner.

Start with the [step-by-step walkthrough](refinement_phase4_information_walkthrough_260913.md).
No real account authorization, external calendar write, hardware test, live
service restart or deployment was performed during development.

## Delivered behavior

| Area | Implemented behavior | Important limit |
| --- | --- | --- |
| Private notes | Owned, revision-checked notes and stable checklist IDs; paged reads; exact preview and direct confirmation for edits and deletion | 16 KiB body, 100 checklist items; full content has a further serialized size bound |
| Local controls | information CLI and /info chat commands share service logic, policy and normal task receipts | Same user/session and five-minute approval; models cannot confirm |
| Google setup | Explicit Desktop OAuth with PKCE, state checking and private loopback callback over SSH; refresh credentials in the existing secret store | Read-only default; explicit new write connection; no Pi desktop or persistent callback listener |
| Calendar reads | Explicit time-zone intervals, bounded pages/retries/bytes/time, all-day date preservation, conservative free-slot suggestions | 31 days, five pages, 200 events, 1 MiB, 15 seconds; incomplete does not mean free |
| Calendar changes | Exact create/update/cancel previews; one-use dispatch, remote version checks and verification; uncertain-result reconciliation | Only individually verified events created by the same connection; no attendees or recurring events; no write retries |
| Research | Existing approved Tavily search, three queries within 30 seconds, real source IDs/dates/URLs, bounded evidence rendering and requested note saves | Provider snippets only; interpretations qualified, no independent truth guarantee; usage limits are not a money cap |
| Briefings | Requested local tasks/checklists plus explicitly selected optional calendar/research; useful text offline and short optional speech | No startup briefing, proactive suggestions, automatic saving or changes to alarms |
| Existing framework | Current Agent policy, SQLite database, task receipts, CLI/IPC/web chat and speech service | No new hardware path, dependency, boot service or generic MCP write permission |

The research skill is now a compatible version-2 package. Existing version-1
skills remain supported. Private installed skill copies remain authoritative;
they are not overwritten. Existing saved recipes retain their narrow read-tool
allowlist and cannot acquire calendar write authority through this delivery.

## Code and data design

The new information_store module uses the existing private database and migration
7. Every read and write includes the resolved user, and verifies that the user
still exists. User deletion/reset cascades through information records. No model
argument can select another owner.

NotesService commits a note edit and consumption of its approval in one short
database transaction. Concurrent confirmation cannot create duplicates. Reads
return numbered pages when full content would exceed chat size limits.

CalendarService owns exact account/calendar/version/body/session/expiry-bound
approvals. It saves a dispatch receipt before sending a write. Creates use one
saved remote event ID. Updates use PATCH (change only specified fields) with
If-Match (require the previewed remote version), preserving unrelated Google
event fields. PATCH consumes more Google request quota than an ordinary update;
the limited scope is intentional. See Google's
[patch contract](https://developers.google.com/workspace/calendar/api/v3/reference/events/patch)
and [resource version guidance](https://developers.google.com/workspace/calendar/api/guides/version-resources).

GoogleCalendarBackend uses fixed Google hosts, encoded path segments, no
redirects, bounded asynchronous requests and serialized refresh. Tokens are
not returned to models or placed in ordinary receipts. Account disconnect
disables local access, cancels owned work and deletes its local credential.
A deleted user's delayed callback cannot recreate their database records.

The authorize helper binds only 127.0.0.1, checks its one-use state and PKCE
proof, and closes callback workers on completion/cancellation. It requires a
Desktop app client file and an explicitly opened SSH tunnel. The implementation
follows the [installed-app flow](https://developers.google.com/identity/protocols/oauth2/native-app);
real account and administrator policies still require manual acceptance.

ResearchService normalizes only actual approved-provider results. It never fetches
arbitrary URLs. The answer renderer rejects unknown references and labels
non-literal claims as interpretations not independently established by excerpts.
A reference proves source membership, not factual correctness. Source disagreement
still needs model/user judgment and, when useful, another search. External text
has no permission to invoke hardware or confirm changes.

BriefingService fixes the local date once, reads only selected notes, bounds
optional sources concurrently, and retains local results when a provider fails.
Model-facing results are bounded before becoming model messages. Direct chat
also avoids oversized replies. Briefing speech uses the existing speech service,
honors speech off/cancellation, and gives a short summary rather than reading a
large evidence bundle aloud.

## Persistence, recovery and privacy

- Notes and calendar receipts remain until explicit deletion or profile reset.
  Records are capped at 1,000 per user per kind; the system refuses further
  writes at that limit instead of silently deleting private records.
- Research runs and note previews older than seven days are cleaned on service
  startup. A continuously running service does not claim timed background cleanup.
  Explicitly saved notes retain their useful citations until deletion.
- Startup expires unused approvals. Dispatched calendar records become uncertain.
  Reconciliation is an explicit read-only action; startup sends no calendar writes.
- Cancellation before dispatch prevents further dispatch. Once sent, a remote
  effect may exist even if the response is lost. Local cancellation, user deletion,
  disconnect and backup restoration do not undo remote changes.
- The existing backup inventory already includes the whole database and secret
  file. A new round-trip test checks saved notes and expiration of restored
  authority. Restore still requires closed database clients and the existing
  offline ownership boundary.
- Restoring an old private backup can restore earlier connection credentials.
  Revoke the Google grant separately when remote revocation is required.
- This remains the project's existing local-user identity boundary. It does not
  implement the deferred broad authentication/guest/retention redesign.
- Ordinary task receipts contain operation/status evidence, not raw credentials.
  Information deliberately sent through conversational tools remains subject to
  the existing transcript, selected-model and conversation-retention settings.

## Validation evidence

Final software gate results are recorded below after the consolidated check.
The checks use the existing frozen environment without reinstalling Pi drivers.

~~~bash
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py
uv run --frozen --no-sync python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen --no-sync pytest -q
node --check ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js
git diff --check
~~~

Checkpoint evidence: 884 tests passed; lint passed; 444 Python files formatted;
112 source files passed type checking. Driver verification passed for all 222
baseline files plus the existing 56 authorized repairs, and all six libraries
resolve to this checkout. No new driver repairs were needed.

The Agent source distribution and wheel built successfully in an isolated build
environment. An initial attempt without build isolation failed because hatchling,
the existing build backend, was absent from the runtime environment. The isolated
build succeeded without changing runtime dependencies or live configuration.

Coverage includes owner isolation, stale revisions, concurrent/repeated approval,
restart expiration, backup restore, wrong hashes/sessions, daylight-saving offsets,
all-day end dates, calendar pagination, read-only refusal, lost-response recovery,
remote-version conflicts, dispatch cancellation, fixed transport hosts, byte
limits, credential deletion, fake OAuth state/PKCE callbacks, note paging and
direct chat controls. All network responses and credentials in these tests are
synthetic. No live robot or account effects were used.

The suite reports the existing Starlette TestClient/httpx deprecation warning.
It is not a test failure and was present before this delivery.

## Documentation and wiki impact

New complete manual sources are under the 2026-09-13-03 directories in wiki raw.
Both READMEs link to them. Installation, architecture, tool/skill guidance,
development history, the Phase 4 plan and this walkthrough have been updated.

At the owner's explicit instruction, no wiki ingestion, semantic review,
publication, fingerprint refresh or knowledge-map promotion was performed.
Registered originals and published pages remain untouched. The published map
and runtime project-help checkpoint still refer to earlier evidence; consult the
new sources directly until the owner authorizes publication.

## Remaining manual acceptance

Follow the walkthrough and record actual pass/fail results:

1. Existing Pi installation and profile, local note/checklist review, paging,
   stale-edit refusal and local-only briefing.
2. Optional real Google authorization through SSH, schedule reads, a disposable
   calendar create/update/cancel, consent expiration and read-only refusal.
3. Configured Tavily query, dated references, qualified claims and one saved note.
4. Optional speaker playback, Stop Speech, failed-output text retention and
   existing /time, /tasks, /project and read-only recipe regressions.
5. Privacy and recovery with disposable data only; never erase real user profiles
   merely to demonstrate a test.

Safe smoke requires no actuator movement. Device communication is limited to
separately chosen existing startup and optional speech. No power-risk test is
needed. The next safe action is the local walkthrough before enabling any
external write connection.
