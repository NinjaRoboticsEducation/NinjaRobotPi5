# Phase 4 implementation plan — Connection information and reusable documentation

**Approved narrowed delivery — 13 September 2026:** Implement only M03, M04,
X01 and X05. T04 calendar planning, T05 new research and T06 notes/checklists/
briefings are deferred by the owner. Their original design sections below are
retained for future planning, not acceptance criteria for this delivery.

The four approved areas are implemented. See the
[walkthrough](../docs/validation/refinement_phase4_walkthrough_260913.md) and
[handoff](../docs/validation/refinement_phase4_handoff_260913.md) for commands,
validation and practical limits. No account integration or hardware refactor
was needed. Wiki ingestion, review and publication remain skipped.

Implementation adaptations for the narrowed scope:

1. M03 reuses the existing memory store and its bounded keyword search.
2. M04 uses explicit user-authored structured recipes, reviewed versions and
   existing request receipts. Only seven existing/local read tools are allowed.
   There is no calendar/research/notes dependency, automatic private-parameter
   extraction, external write, or background learning.
3. X01 implements explicit v2 parsing, current catalog checks and optional
   fallbacks. V1 remains compatible. Deferred-feature templates declare missing
   capabilities and cannot masquerade as implemented services.
4. X05 uses a dependency-free fixed public manifest. Existing curated pages and
   cited sources are pinned to 12 September; draft coverage is labeled. Larger
   source manuals may be hashed up to 128 KiB, inside the overall 256 KiB budget,
   but are not returned in full. No wiki subprocess or new publication runs.
5. The final gate passes 868 tests, lint, types, compilation, driver integrity
   and packaging. Consolidated documentation and manual acceptance are in the handoff.
   Physical Phase 5 acceptance remains separate.

The original proposal and technical references follow for design context.

The [master plan](NinjarobotPi5_RefinementPlan_260907.md#7-development-phases-and-acceptance-gates)
calls this phase **“Connected information and reusable help.”** The title requested
for this document refers to that same scope: **T04, T05, T06, M03, M04, X01 and
X05**, with X03 documentation work throughout. It does not mean another Bluetooth
setup project. See the companion
[Phase 5 plan](Phase5_NinjarobotPi5_RefinementPlan_260909.md) for optional interaction.

## Contents

- [Starting point and evidence](#starting-point-and-evidence)
- [Architecture and implementation choices](#architecture-and-implementation-choices)
- [Delivery sequence](#delivery-sequence)
- [Shared data and privacy rules](#shared-data-and-privacy-rules)
- [T04 — Calendar planning and reviewed changes](#t04--calendar-planning-and-reviewed-changes)
- [T05 — Research with evidence](#t05--research-with-evidence)
- [T06 — Notes, checklists and requested briefings](#t06--notes-checklists-and-requested-briefings)
- [M03 — Better retrieval from existing memory](#m03--better-retrieval-from-existing-memory)
- [M04 — Reviewable task recipes](#m04--reviewable-task-recipes)
- [X01 — Compatible skill requirements and templates](#x01--compatible-skill-requirements-and-templates)
- [X05 — Read-only project help](#x05--read-only-project-help)
- [Validation and manual acceptance](#validation-and-manual-acceptance)
- [Documentation, release and rollback](#documentation-release-and-rollback)
- [Completion checklist](#completion-checklist)

## Starting point and evidence

The inspected checkout was commit
`cab1d3648a4d78a909a540e14bb7611fe0ae562a`. Recheck the code and working tree before
implementation; this is a dated plan, not a promise that later files are identical.
Serena symbol inspection and direct source reads were used to compare the plans
with the actual implementation.

| Area | What exists now | Consequence for this phase |
| --- | --- | --- |
| Foundation and local tasks | Phase 0–2 software, local reminders, task receipts (stored outcomes and evidence), memory controls, usage limits and the approved face-recognition cleanup. The owner reports Phase 2 manual testing. | Extend these services. Do not build another task scheduler or database. |
| Spoken replies | Phase 3 H02/B01 software: optional local Piper speech, IDE-owned output, cancellation, microphone coordination and spoken reminders. | Send final summaries through the existing reply path. Do not start a second speech player or change microphone behavior. |
| Phase 3 acceptance | The handoff records 772 passing tests, static checks and preserved managed drivers. Bluetooth audibility, reconnect, microphone and boot-account checks remain physical acceptance items. | These are earlier results, not tests run for this planning task. Keep the outstanding acceptance visible. |
| Calendar | The MCP guide contains an operator-created read-only Google Calendar example. There is no shipped native calendar-write service. | Begin with optional reads and add a separate, reviewed write boundary. |
| Search | A bundled `current-web-answer` skill uses an explicitly configured Tavily MCP tool. | Build research receipts and note saving around this capability. Search credentials and service terms are still required. |
| Memory and skills | SQLite search, user-scoped memory, stored behavior recipes and strict version-1 non-executable skill packages exist. | Improve these mechanisms without replacing them or treating old behavior summaries as executable general recipes. |
| Wiki | Developer retrieval exists. A runtime project-help provider does not. Published pointers still describe an older checkpoint; newer Phase 3 manuals are prepared but not ingested. | Expose publication and review limits honestly. Do not equate the newest folder name with an approved current source. |
| Remaining scope | T07 has time/call/turn limits, not a monetary spending cap. Traditional Chinese display-font work and deferred refinements remain separate. | Do not promise free cloud use or quietly add unrelated implementation. |

Read the [Phase 2 handoff](../docs/validation/refinement_phase2_handoff_260909.md),
[Phase 3 handoff](../docs/validation/refinement_phase3_handoff_260909.md),
[progress record](../docs/validation/refinement_progress_260907.md), and
[owner confirmation](NinjarobotPi5_RefinementConfirmation_260907.md) first.
The default target remains Raspberry Pi OS Lite, 64-bit, without a desktop.

For knowledge context, read the [wiki README](../ninjarobot_pi5_wiki/README.md),
[document map](../ninjarobot_pi5_wiki/project-knowledge.json), and
[architecture page](../ninjarobot_pi5_wiki/wiki/concepts/architecture.md).
Prepared, unregistered Phase 3 evidence includes the
[Installation Guide](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-09-03/InstallationGuide.md),
[Development Guide](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-09-03/DevelopmentGuide.md),
and [MCP and Skills Guide](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-09-02/NinjaRobot_MCP_Skill.md).
AI review metadata means a coding-agent review, not human or physical acceptance.

## Architecture and implementation choices

Preserve the existing route:

```text
User -> Agent conversation and deterministic policy -> registered tool provider
                                                    -> local information service
                                                    -> reviewed external connector
                                                    -> IDE -> existing driver -> device
```

“Deterministic” means a normal program makes the permission decision using fixed
rules; a language model cannot grant permission. The IDE is the existing layer
that coordinates robot hardware. Information services belong in the Agent, not
in the IDE or any `pi5*` driver. External text remains untrusted input even when
returned by a trusted, locally implemented connector.

### Reuse these building blocks

| Building block | Recommendation and reason |
| --- | --- |
| Python and `asyncio` | Keep the supported Python 3.11–3.13 range. Use the existing asynchronous lifecycle, cancellation tokens and deadlines. Do not introduce another event loop. |
| Pydantic | Reuse strict data validation: reject unexpected fields and invalid sizes before storage or execution. |
| SQLite and FTS5 | Keep the private database. FTS5 is SQLite's optional full-text search extension. Preserve the existing fallback when it is unavailable. |
| HTTPX | Reuse the current HTTP client for a bounded Google Calendar adapter. Inject a fake client in tests; keep network timeouts and response-size limits explicit. |
| Google authentication libraries | Use official libraries for OAuth, the user's limited account authorization. Make calendar dependencies optional, lock reviewed versions and document licenses before implementation. Do not invent or hand-code token exchange. |
| Existing MCP client | MCP means Model Context Protocol, the tool-connection format already used here. Retain reviewed read-only search and calendar integrations. Never mark a write tool as read-only to get it into the catalog. |
| Existing skills and registry | Package focused instructions and declarative requirements. Do not install arbitrary Python, shell scripts or dependencies from a skill. |
| Existing tests | Use pytest, fake clocks, temporary databases, fake providers and existing web/IPC fixtures. IPC means the local communication channel between controller and service. |

No new agent framework, vector database, distributed worker service, or replacement
robot architecture is justified by this scope. Embeddings, which represent text
as numbers for similarity search, remain a later evidence-based decision.

### Existing files to read before editing

Paths in this table are relative to `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/`.
Names marked **new** below are proposals, not files that already exist.

| Existing files | Integration responsibility |
| --- | --- |
| `tools.py`, `models.py`, `policy.py` | `ToolProvider`, `ToolRegistry`, strict results and authorization. The registry rejects external-untrusted write tools. |
| `mcp_client.py`, `mcp_config.py` | `MCPToolProvider._refresh_catalog`, reviewed read-only names, retry rules and bounded provider startup. |
| `task_models.py`, `task_service.py`, `task_tools.py`, `task_controls.py` | Existing `LocalTask` and `TaskService` receipts, ownership, cancellation and restart outcomes. |
| `memory_migrations.py`, `memory_store.py`, `memory_services.py`, `memory_controls.py` | Transactional schema changes, scoped retrieval and user review/edit/delete. |
| `skills.py`, `bundled_skills/` | Strict version-1 package parsing, simulation examples, allowlisted tools and installation boundaries. |
| `runtime.py`, `service_main.py` | One lifecycle owner for each optional service and provider; startup failure isolation and shutdown. |
| Controller/IPC modules, `web_app.py`, `web_control.py`, `web_static/` | Authenticated user actions, concrete previews, independent cancellation and text results. Trace current dispatch before adding commands. |
| `deployment.py` | Private-data backup and restore implications. No automatic service or OS changes. |

### Compatibility contracts

1. Existing configurations load with new features disabled or conservative local
   defaults. Missing account credentials must not stop robot startup.
2. Existing tool names, task statuses, command syntax and database records remain
   readable. Add interfaces rather than silently changing a current interface.
3. Keep `LocalTask.kind` as the existing `reminder` or `request`. The existing
   required `due_at` field does not make a request a scheduled calendar write.
   Attach feature details to request records instead of overloading reminders.
4. A requested note save is a local write. A calendar change is an external write.
   Neither is truthfully classified as read-only. Use existing applicable risk
   classes plus service-specific checks; do not invent an unsupported enum value.
5. Existing emergency stop, movement stop, microphone stop and speech stop must
   remain responsive while research or an approval preview is open.
6. Guest or ambiguous identity cannot expose another user's private data. Face
   recognition is not account authentication. Deny private persistence until the
   existing trusted ownership context is available; offer temporary session text.
7. Retain the current architecture boundary and managed-driver baseline. This
   phase has no reason to change device drivers, boot files or hardware ownership.

## Delivery sequence

Each row is a reviewable implementation increment. Run the relevant focused tests
and the full gate in [validation](#validation-and-manual-acceptance) after each
increment. Stop and repair failures before continuing. Effort is relative to the
existing framework and includes tests and documentation, not account waiting time.

| Step | Objective and likely files | Contract, gate and documentation | Effort / risk |
| --- | --- | --- | --- |
| 4.0 | Confirm accepted Phase 3 baseline; inventory providers, schemas and pending wiki sources. | Record before-change gate and acceptance gaps. No runtime change. | Low / none |
| 4.1 | Add shared owned information records and T06 notes/checklists. **New:** `information_models.py`, `information_store.py`, `information_tools.py`; extend migrations and controls. | Old database upgrades twice safely; wrong-user requests fail; edit/delete/backup work. Document local persistence. | Medium / private local data |
| 4.2 | T04 bounded calendar reads. **New:** `calendar_service.py`, `calendar_tools.py`, `calendar_google.py`; extend configuration and startup. | Fake accounts first; no credential or network requirement for normal startup; exact time-zone and pagination tests. Draft headless account setup. | High / account and network |
| 4.3 | T04 reviewed create, then separately tested update/cancel. Extend calendar records and trusted controls. | Exact preview, single-use approval, timeout reconciliation and stale-version tests. No attendee invitations. Document consequences and recovery. | High / external writes |
| 4.4 | T05 research receipts and T06 requested briefing. **New:** `research_service.py`, `briefing_service.py`; extend tools and bundled examples. | Cited partial results, limits, untrusted input and independent note saving. Document offline behavior. | Medium / network and private data |
| 4.5 | M03 ranking and bounded context in current memory store/services. | Search quality fixtures plus user isolation, deletion and fallback tests. Record measured changes. | Medium / private retrieval |
| 4.6 | M04 versioned linear recipes. **New:** `recipe_models.py`, `recipe_service.py`, `recipe_tools.py`; extend controls and migrations. | Preview, explicit save/run, version pinning, cancellation, uncertain steps and rollback. No automatic learning or replay. | High / effects inherited from each step |
| 4.7 | X01 version-2 requirements and templates in existing skills. | Every bundled version-1 package still loads; extra fields and unavailable requirements fail safely; examples only simulate. | Medium / extension boundary |
| 4.8 | X05 fixed read-only help adapter. **New:** `project_help.py`, selected-source manifest and fixtures. | Traversal, secret exclusion, stale evidence, startup isolation and no query-time installation. Document publication limits. | Medium / information boundary |
| 4.9 | Combined acceptance, consolidated manuals and handoff. | Honest software/physical/account results; no deferred feature silently enabled. Pause for owner acceptance. | Medium / manual effects only with consent |

Within this sequence, calendar reads can be developed independently of notes;
calendar writes must wait for the receipt/approval storage. Briefings depend on
notes, local tasks and optional reads. Recipes depend on reliable task results.
X05 can use fixtures before wiki publication, but current operational advice
requires a reviewed current source set. Phase 5 hardware purchases are not a
dependency for any Phase 4 feature.

## Shared data and privacy rules

Use the existing private SQLite database and migration runner. Add the next unused
migration number; never edit an already applied migration. The current store has
no general `MemoryKind.NOTE`: add explicit information tables rather than
misclassifying notes as preferences or behavior recipes.

Recommended new tables and fields:

| Proposed table | Minimum contents | Ownership and lifecycle |
| --- | --- | --- |
| `information_notes` | ID, user ID, title, bounded body, kind, revision, created/updated times, source references. | Persistent only for a resolved user; optimistic revision check for edits. |
| `information_checklist_items` | Note ID, stable item ID, order, text, completed flag and update time. | Inherit parent owner; deletion removes children. |
| `research_runs` / `research_sources` | Task ID, owner, requested question, retrieval time, source IDs, URLs, excerpts and partial-result flags. | Short bounded excerpts; no raw browser archive. Explicit saving creates a note. |
| `calendar_connections` | Owner, stable connector/account/calendar identifiers and allowed scopes; private credential reference. | Tokens remain in the approved private credential store, never tool results or prompts. |
| `calendar_operations` | Task/owner/session IDs, action, exact normalized payload, digest, expiry, approved state, remote ID/version and result evidence. | Pending approval expires; dispatched unknown outcomes survive restart for reconciliation. |
| `task_recipe_versions` / `task_recipe_runs` | Owner, stable recipe ID, version, typed steps, permissions, feedback, active-version pointer and run/task references. | Immutable saved versions; rollback changes the active pointer, never rewrites history. |

“Optimistic revision check” means refusing an edit if someone changed the record
after its preview. Use foreign keys, which keep linked records consistent, and
enable their enforcement on every database connection. Index owner plus record
ID, owner plus update time, and pending-operation status. All reads and writes
must include the trusted owner; model-supplied user IDs are not authorization.

Implementation order:

1. Add strict models and explicit byte/count limits. Suggested starting limits:
   note body 16 KiB (16,384 bytes), 100 checklist items, eight recipe steps, ten
   research sources and at most 4 KiB per stored source excerpt. These are proposed
   product limits; make them documented constants and test boundaries.
2. Add parameterized SQL (the database query language), which passes data separately
   from database commands.
   Keep transactions short. Do not hold a database write transaction open across
   network calls, model calls or user approval.
3. Test upgrade from a copy of each relevant old schema, repeated upgrade,
   failed-transaction recovery and simultaneous edits. Never use the live database.
4. Link request receipts through the current `TaskService`. Keep extended details
   out of its 1,000-character result field; return a bounded summary plus owned
   record IDs. The existing reminder claim loop must not dispatch calendar writes.
5. Extend user delete/reset, search-index cleanup, backup and restore together.
   A cache is a temporary copy: key it by user and source revision, and invalidate
   it on edit, deletion, account disconnect and user switch. Recheck the trusted
   owner before delivering a delayed result or speaking its private content; a
   user switch during a network call must not disclose the old user’s data.
6. Record minimal action metadata in logs. Avoid raw note bodies, calendar titles,
   authorization tokens and complete search questions in ordinary diagnostics.
7. On deletion during an in-flight external action, revoke future local access and
   stop further dispatch. Explain that deleting local history does not undo a
   calendar change already sent. Do not recreate a deleted user's records when a
   delayed callback finishes. Keep any necessary recovery record under a reviewed
   minimal-retention policy, never silently keep the full content.

This is the minimum privacy work required by the new data. It does not implement
the broader deferred M05 identity/retention redesign.

## T04 — Calendar planning and reviewed changes

### User experience and first connector

Start with Google Calendar because the current guide already demonstrates its
read-only use. Keep existing reviewed MCP reads compatible. The recommended new
write-capable path is a locally owned `CalendarService`, a `ToolProvider`, and an
injected `CalendarBackend` protocol — a small interface implemented by a Google
adapter and a fake test adapter. Do not enable generic MCP writes or maintain two
separate write implementations.

Register the locally reviewed implementation as a trusted provider; this does not
make its remote event content trusted. Keep returned external text in an explicit
untrusted-data envelope, following the current MCP result convention. Never mark
an arbitrary external server trusted merely to allow a write. Use fixed provider
hosts, encoded calendar/event path segments, disabled cross-host redirects and
bounded responses so account tokens cannot be forwarded to an injected address.

Reads/status can use `RiskLevel.READ_ONLY` with owner/account checks. Persisting a
preview is a local write and should use `RiskLevel.LOW`. The trusted commit handler
uses the existing privacy/confirmation policy plus the exact operation approval;
both controller and recipe continuation call that same handler. This adds no new
risk enum and grants the model no reusable approval flag.

The first experience is “Show my calendar tomorrow.” It identifies the selected
account/calendar, exact local date and time zone, checked interval and any missing
pages. The second is “Suggest a time for a 30-minute planning session.” A suggestion
does not reserve a time. The third is a concrete event preview with a separate
trusted confirmation action.

Proposed model-facing tools are `calendar.list_events`, `calendar.propose_change`
and `calendar.operation_status`. These names must be checked against the existing
tool-name validator and registry before implementation. **Do not expose an
unrestricted model-facing `commit(confirmed=True)` tool.** Commit belongs to the
authenticated controller action or a deterministic recipe continuation after the
same trusted confirmation. Tool output from event descriptions is untrusted data.

### Reads and account setup

1. Keep the integration optional and disabled by default. Configure a specific
   account/calendar allowlist and least-privilege read scope. Health reports
   disconnected/revoked/available without opening a browser or refreshing a token
   through an unbounded startup path.
2. Provide a separate, explicitly invoked account setup command for Pi OS Lite.
   Use an official OAuth flow with a browser on the user's computer and, where
   supported, an SSH tunnel to a loopback callback on the Pi. SSH is the existing
   encrypted terminal connection. Do not require a Pi desktop, expose the callback
   publicly, or use the retired copy-and-paste authorization-code flow. Document
   exact commands only after implementing and testing that helper. Keep credentials
   readable only by the intended service user.
3. Add an async bounded HTTP adapter and an injected token provider. If an official
   authentication helper is blocking, serialize its work off the event loop and
   bound its underlying HTTP timeout; cancellation alone cannot stop a thread.
4. Require an explicit start/end interval, an installed IANA time zone such as
   `Asia/Tokyo`, and timezone-aware instants. IANA is the standard time-zone name
   database. Reuse the reminder time-validation approach and test daylight-saving
   transitions. All-day dates remain dates, with an exclusive end date.
5. For ordinary schedule expansion, use Google's `singleEvents=true` and
   `orderBy=startTime`, follow `nextPageToken`, and cap interval, pages, event count,
   bytes and total time. Suggested starting budgets: 31 days, five pages, 200 events,
   1 MiB response total and 15 seconds. Mark truncation as incomplete; an incomplete
   result does not prove that a time slot is free.
6. Distinguish empty calendar, no permission, revoked authorization, service outage,
   stale cache and incomplete results. Read retries require an overall deadline;
   at most two retries with a short increasing delay is a reasonable starting point.

Google's interval and pagination semantics are documented in
[events.list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list).
Use the [installed-app authorization guidance](https://developers.google.com/identity/protocols/oauth2/native-app)
when implementing the headless setup helper. Verify current scope and library
behavior at implementation time.

### External-write contract

Implement event creation first. Add update and cancellation only after creation's
failure and concurrency tests pass. Initially restrict writes to a user-selected
calendar and individually identified events created by this integration. Reject
attendees, invitations, recurring-series edits and arbitrary changes to someone
else's events. These require later, separately reviewed scope.

Use a strict draft similar to this example. It illustrates validation and hashing,
not the finished public schema or authorization system:

```python
import hashlib
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalendarCreateDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    action: Literal["create"] = "create"
    connection_id: str = Field(min_length=1, max_length=100)
    calendar_id: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=200)
    start: datetime
    end: datetime
    timezone: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_interval(self) -> "CalendarCreateDraft":
        try:
            zone = ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use an installed IANA time zone") from exc
        for value in (self.start, self.end):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("An explicit UTC offset is required")
            local = value.astimezone(UTC).astimezone(zone)
            if local.utcoffset() != value.utcoffset():
                raise ValueError("The offset must match the selected time zone")
        if self.end.astimezone(UTC) <= self.start.astimezone(UTC):
            raise ValueError("End must follow start")
        return self


def draft_digest(draft: CalendarCreateDraft) -> str:
    # Persist this exact normalized payload with the approval record.
    return hashlib.sha256(draft.model_dump_json().encode("utf-8")).hexdigest()
```

The real draft must also bind its schema version and any supported description
or location. Reject unsupported fields; do not silently drop something the user
thought they approved. Account and calendar authorization is checked separately
against the trusted owner. A digest is a content fingerprint, not a permission
token. The server must retain the payload; never reconstruct it from a later
model message.

Recommended operation lifecycle:

```text
draft -> pending approval -> approved -> dispatching -> verified
              |                 |           |            |
         expired/cancelled  expired/cancelled uncertain    completed task
                                            |
                                      read reconciliation
```

These are proposed operation-detail states. Map them to existing task states:
draft while awaiting approval, running during dispatch, uncertain without proof,
completed after verification, and failed/cancelled as appropriate. Do not replace
the existing task-status enumeration just to match this diagram.

For each change:

1. Persist exact action, owner, session/controller identity, account, calendar,
   normalized content, remote event ID, applicable remote version and a short
   expiry. A proposed five-minute expiry should be checked using trusted time;
   expire pending approvals on restart or a suspicious clock change.
2. Present the account/calendar, local times with zone, event changes, consequences
   and expiry in the existing CLI (command-line interface) and web controls.
   A user can cancel or edit it.
   Editing invalidates the previous approval and produces a new preview.
3. The trusted controller validates its current session/lease and owner, then
   atomically consumes the matching pending approval. An SQL conditional update
   must change exactly one row. Two simultaneous confirmations dispatch once.
   `PolicyContext.confirmed` alone is insufficient because it is not bound to the
   payload/account/version.
4. Persist a dispatch receipt **before** the network call. Generate and save the
   remote create ID once, using the provider's permitted alphabet. For Google,
   a UUID (random unique identifier) expressed as 32 lowercase hexadecimal
   characters fits the documented ID restrictions.
   A request identifier means “same operation,” not permission to retry it blindly.
5. Dispatch outside the database transaction. Do not hold the ordinary chat lock
   while waiting for approval. Calendar Cancel and status must remain accessible.
6. Verify the remote object through a bounded read: correct ID, calendar and key
   fields. A successful HTTP response alone is not proof of the requested outcome.
   An update uses the previewed ETag, the provider's object version, with `If-Match`.
7. A connection loss after dispatch becomes `uncertain`. Reconcile using the saved
   remote ID; do not create another event. A conflict response requires a matching
   read before success can be claimed. A changed version requires a new preview.
8. Cancellation before dispatch prevents the write. Cancellation after dispatch
   stops further steps but may not undo the external effect. Report that distinction
   and offer a separately reviewed compensating change if necessary.

On restart, discard unconsumed approval authority and reconcile dispatched records.
A missing object on the first recovery read does not conclusively prove the write
never happened. Keep it uncertain if evidence is insufficient. Stop on account
revocation, forbid automatic scope expansion, and never automatically retry a write
because a provider calls it safe.

Google documents creation rules in
[events.insert](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert),
version preconditions in
[resource version handling](https://developers.google.com/workspace/calendar/api/guides/version-resources),
and conflict/rate-limit responses in
[error handling](https://developers.google.com/workspace/calendar/api/guides/errors).
Do not promise that `sendUpdates=none` suppresses every email; the initial feature
rejects attendees instead.

Calendar events and local alarms remain separate. Creating, changing or deleting
an event must not silently change T02 reminders. Offer a distinct reminder preview
only when the user requests one.

### Required calendar tests

Cover read-only credentials; wrong owner/account/calendar; all-day and overlapping
events; repeated and nonexistent local times; partial pagination; revoked tokens;
bounded rate-limit handling; altered/expired previews; forged confirmation; two
controllers confirming together; restart before and after dispatch; write accepted
then connection lost; duplicate-ID conflict; remote-version conflict; cancellation
during dispatch; and no accidental attendee notification. Assert remote write
counts, persisted state and user-visible wording, not just mocked return values.

## T05 — Research with evidence

The user should get an answer they can check and save. Extend the existing approved
search provider and `current-web-answer` skill; do not add unrestricted browsing or
a second model loop.

Implementation steps:

1. Start a current `request` task with the user's question, optional comparison
   criteria, allowed provider, time/call limits and owner. A suggested first budget
   is three search calls within 30 seconds, still capped by the current task limits.
   Count connector pagination/retries against their own bounded request budget
   as well as the outer task deadline; one model tool call must not conceal
   unbounded downstream requests. Cancellation must reach every owned request.
2. Normalize each result to a source ID, title, URL, fetched-at time, published-at
   time when supplied, excerpt and provider. Distinguish provider snippets from
   pages actually fetched. A retrieval date is not an article's publication date.
3. Keep source IDs bound to actual results in the current run. Require cited claims
   to reference those IDs. Render a reference list with dated links; explain missing
   dates, contradictory sources, failed queries and incomplete comparisons.
4. Treat all result text as data. A webpage instruction to reveal credentials,
   approve a calendar action or call a robot tool must have no authority. Do not
   include secrets or unrelated private memory in search queries.
5. Initially use provider-returned excerpts. If full-page fetching is later needed,
   add a reviewed adapter with public-address checks on every redirect, byte and
   content-type limits, and no local/file URLs. This prevents SSRF, a trick that
   makes a server fetch private network addresses. Do not add a generic URL fetcher
   as an incidental convenience.
6. Save a research note only on an explicit user request. Store the useful summary,
   citations and incompleteness flags in the owned information store. Retrying Save
   for the same run must not create duplicate notes. Re-editing produces a revision.
7. Finish the task with verified evidence: answer produced, note ID if saved, and
   partial or failed steps. “Search finished” does not mean “saved successfully.”

A minimal internal evidence record can start here; production validation must
also enforce string/byte limits and accepted public URL schemes:

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    title: str
    url: str
    retrieved_at: datetime
    excerpt: str
    published_at: datetime | None = None


def unknown_citations(cited_ids: set[str], sources: list[ResearchSource]) -> set[str]:
    return cited_ids - {source.source_id for source in sources}
```

Citation membership detects invented references; it does not prove a claim is
supported. Add evaluation examples where the cited excerpt does not support the
answer, and require qualified wording or another search. Avoid retaining entire
copyrighted articles in notes by default.

Tests must include no search provider, offline results, duplicate URLs, unknown
citations, unsupported claims, source disagreement, prompt injection, cancellation,
oversized responses, same-run save retries and private-note access by another user.
Paid search/model use remains subject to provider billing. Existing call limits
are **not** a monetary cap; document optional provider-side controls and disable
paid integrations when a strict unimplemented spending guarantee is required.

## T06 — Notes, checklists and requested briefings

### Notes and checklists

Proposed tools are `notes.create`, `notes.list`, `notes.read`, `notes.update`,
`notes.delete` and `checklists.set_item`. Final names and input shapes must fit the
current registry. Read tools are read-only; edits are local writes with explicit
user intent. Destructive deletion needs a concrete preview/confirmation through
the current trusted controls. Stable item IDs prevent “check item two” from editing
the wrong item after a reordered list.

Add a small local service, tool adapter and shared controller handlers. All routes
must reuse the same owner and revision checks. Provide list/read/edit/delete in the
existing text interface as well as the web controller. Do not require a browser
or a cloud model to read a saved note. Keep note contents escaped when displayed
in HTML so saved text cannot become a script.

### Briefings

Propose a `briefing.build` tool that runs **only on request**. It combines selected
local tasks, checklist items, optional permitted calendar results and optional
requested research. It does not schedule itself at boot, notify proactively, or
activate T08. Determine “today” once from the user's explicit time zone and keep
that interval fixed throughout the build.

Build an evidence bundle before generating prose. Give each section its source
IDs, checked-at time, coverage interval and available/incomplete/unavailable state.
Read independent sources concurrently with a small limit and per-source deadlines;
retain useful local results when the calendar fails. Bound total content before
sending it to the existing model. A deterministic text summary must still work
without a model connection.

Use the existing response/speech pathway, respecting speech off, output failure
and cancellation. Long briefings get a short spoken summary and the full cited
text. Saving a briefing is a separate requested note operation; generating one
does not copy every private event into permanent memory.

Acceptance includes a local-only briefing without network/model access, a mixed
briefing with a calendar outage, no unsolicited startup output, escaped note text,
revision conflicts, item reordering, deletion and absence of other users' data.

## M03 — Better retrieval from existing memory

`MemoryStore._search_sync` already performs owner-scoped FTS search with a fallback.
`MemoryRetrievalService.context` adds profile/preferences and relevant history.
Improve that implementation rather than replacing it. Keep the owner predicate
inside the database query **before** ranking and limiting.

Implementation steps:

1. Create a small, synthetic evaluation set: corrected preferences, older relevant
   memories, recent irrelevant text, unsuccessful behavior history, empty queries,
   Japanese/Chinese text and two users with matching words. Do not copy real chat.
2. Retrieve a bounded candidate set using the existing tokenization and kinds.
   Keep quoted query terms and parameterized SQL. FTS query syntax is not SQL,
   but still needs escaping and length/count bounds.
3. Re-rank candidates using explicit relevance, confirmed/current preference
   status and a modest recency tie-break. Never promote a stale or contradicted
   preference above its confirmed replacement just because it is recent.
4. Return a reason such as “matched current preference” and source/confirmation
   metadata for review. Limit the context by characters/bytes and item count before
   model submission; do not send every note and calendar event automatically.
5. Query notes only in explicitly relevant information workflows or with a clear
   user request. Preserve their distinct ownership and provenance instead of
   inserting their bodies into all conversations.
6. Compare top results against the fixtures and record misses and latency. Only
   then consider a bounded character-substring fallback for unsegmented Japanese
   or Chinese. Do not claim full multilingual meaning-based search.

SQLite's `bm25` score ranks better matches with **smaller** values. A larger-is-better
generic scoring recipe would reverse those results. Use consistent ordering and
test it against actual SQLite. See [the FTS5 documentation](https://www.sqlite.org/fts5.html).
Unicode token support alone does not guarantee useful word splitting for Chinese
or Japanese.

Required checks: FTS and fallback return only the owner’s records; edited/deleted
records leave no cached copies; ranking preserves corrected facts; pathological
queries are bounded; empty results do not produce invented memories; and retrieval
stays useful on a Pi-sized synthetic dataset. Record dataset size and measured
latency rather than asserting a hardware benchmark that was not run.

## M04 — Reviewable task recipes

A recipe is a saved, inspectable sequence such as “read tomorrow's calendar, make
a checklist and save the summary.” The existing behavior-derived memory recipes
are useful evidence but are not already a versioned general task executor.

Start with a **linear list of at most eight typed steps**. Do not add loops,
arbitrary expressions, shell execution, background learning or model-generated
Python. Each step names an allowed registered tool and validated parameters. Any
reference to an earlier result uses a small explicit field-reference format;
resolve only declared fields and reject cycles, future references and arbitrary
attribute access. Never use `eval`.

Recommended sequence:

1. On “save this as a recipe” or “suggest a recipe for this repeated task,” collect
   selected owned successful request receipts. Missing or uncertain results cannot
   prove a workflow succeeded. Do not automatically promote repeated behavior.
2. Draft name, purpose, input fields, steps, required capabilities, maximum budget,
   expected results and external/local/physical effects. Remove captured private
   values from defaults unless the user explicitly elects to retain them.
3. Simulate with fake providers and show a human-readable preview. The user saves
   a numbered version; a stored recipe is not permission to run it.
4. At run time, pin the selected version and validate current tool versions,
   enabled providers, owner, input and budget. Create a normal request task with
   step receipts. Existing Agent policy still approves every proposed action.
5. Pause at consequential actions for the exact per-run approval. Calendar steps
   use T04's bound confirmation. Earlier approval of a recipe does not authorize
   future dates, new accounts or altered remote objects.
6. Record each result before the next step. Retry only reviewed read-only or
   explicitly proven safe operations within the remaining budget. An uncertain
   write pauses the run; it must not advance or be automatically repeated.
7. Cancellation stops later steps. Report completed side effects; do not silently
   reverse them. A separate user-approved change can compensate where supported.
8. Record requested feedback and offer a new draft version. Rollback selects a
   prior saved version for future runs; existing runs keep their pinned version.
   Disabled/deleted recipes cannot start new runs. Restart requires review of
   interrupted runs rather than automatic continuation of external effects.

Keep general information recipes separate from hardware behavior definitions.
Initially exclude motion, capture, shutdown, credential changes and arbitrary
external writes from recipe steps. The existing behavior skill and armed-session
controls remain available through their established interfaces.

Tests: save without run, draft rejected on unknown tools, invalid references,
budget exhaustion, changed tool schema, wrong user, concurrent version edits,
rollback, cancellation between steps, uncertain calendar write, account revocation,
restart and deletion during a run. Verify receipts and actual fake-provider calls.

## X01 — Compatible skill requirements and templates

The current `SkillManifest` accepts only schema version 1 and rejects unknown
fields. Adding new keys to existing version-1 JSON (structured text data) would
break installation.
Introduce an explicit version-2 model and dispatch by `schema_version`; preserve
the existing model and all version-1 defaults unchanged.

Version 2 should declare minimum supported Agent/tool contract versions, required
capabilities, optional capabilities with defined fallback, and requested effect
categories. These declarations describe requirements; they grant no permissions.
Effective access is the intersection of the skill's allowed tools, enabled provider
catalog, current user scope, task budget and deterministic policy.

Implementation steps:

1. Add version parsing and a migration-free in-memory normalized representation.
   Do not rewrite installed user packages. Reject unknown future schema versions
   with a readable message rather than treating them as version 1.
2. Keep the three permitted files: `skill.json`, `instructions.md`, `examples.json`.
   Reuse byte limits, traversal/symlink defenses and non-executable installation.
   Static keyword screening is only an extra check, never the permission boundary.
3. Validate requirements at preview/install, enable and run time because available
   providers can change. An absent optional provider uses the declared fallback;
   an absent required provider produces a concrete unavailable reason.
4. Keep existing bounds: at most 12 model turns, 20 tool calls and 600 seconds.
   A skill can reduce a task's limits, never increase the outer budget.
5. Preserve `external_content="untrusted"` and
   `physical_motion="session_armed"`. Add effect descriptions without weakening
   these invariants or allowing a package to manufacture approval.
6. Supply version-2 templates for cited research, local briefing, calendar preview
   and project help. Include success, missing-capability, cancellation and denied
   effect examples with `simulation_only=true`. Tests must assert the expected
   tool sequence and forbidden calls, not just validate JSON syntax.
7. Document how to package, inspect, simulate, install, enable, disable and remove
   a skill using the existing CLI. Clearly distinguish these runtime Agent skills
   from developer skills under the root `.agents/skills/` directory.

A recipe is a user's owned saved workflow; a skill is an installed instruction
package. A skill may help draft a recipe, but neither becomes executable code or
overrides the other's policy checks.

## X05 — Read-only project help

The runtime robot should answer “How do I connect the Bluetooth speaker on Lite?”
with a bounded, cited answer and accurate version information. Developer wiki
skills are not automatically runtime tools.

### Adapter and source policy

Create a local `ProjectHelpProvider` following the existing `ToolProvider`
interface. Propose `project_help.search` and `project_help.read`, where `read`
accepts an opaque allowed document ID, not an arbitrary filesystem path. Return
title, section, relative source path, content hash, source version, page/review
state, excerpt and any stale/missing-source warning.

Use an operator-reviewed public source manifest derived from the published
document map and selected wiki pages. Exclude private state, credentials, source
code secrets, raw uploads and unregistered material. Do not scan the entire
repository or choose the lexically newest dated raw directory. A missing approval
or publication status is a reason to label or withhold advice, not to guess.

The current prepared Lite manuals are newer than published pointers. Before
claiming current setup coverage, publish and review the relevant versions through
the authorized wiki workflow. While that remains deferred, fixtures can exercise
the provider and runtime responses must state the old coverage. Draft historical
information may be shown with an explicit warning; unreviewed operational commands
must not be presented as verified current instructions.

### Implementation steps and limits

1. Implement a dependency-free fallback that reads only manifest-approved UTF-8
   text and performs bounded keyword search. UTF-8 is the text encoding used by
   the manuals. This makes project help usable without installing the wiki engine.
2. Optionally use the existing wiki engine in its **separate environment** through
   a fixed read-only worker. Inspect its actual CLI entry point before constructing
   the command. Do not expose the generic `scripts/wiki.py` argument forwarding:
   that launcher also supports setup and maintenance operations.
3. Pass an explicit minimal subprocess environment with no model/search tokens or
   inherited private configuration. Use an argument list without a shell, bound
   output and execution time, and terminate the owned process group on cancellation.
   No setup, prepare, ingestion, review, plan apply or dependency download at query
   time. Optional worker failure must leave the robot service operational.
4. Reject absolute paths, traversal, symlink components, non-regular files,
   unexpected encodings and oversized documents. On Linux, use directory-relative
   opens that reject symlinks at each component and validate the opened file, so
   a path swap between check and read cannot escape confinement.
5. Suggested initial limits: query 300 characters; six excerpts; 64 KiB per opened
   page, 256 KiB total; at most two approved link levels; three seconds for local
   search, ten seconds overall. Return bounded sections for larger manuals using
   an approved section index; never silently load an unlimited full manual.
6. Check source hashes and semantic-review metadata, not just the search stale
   flag. A semantic review checks whether claims match their cited evidence.
   Cache keys include manifest, source and page hashes; invalidate on change.
   Modification times alone do not prove freshness.
7. Treat retrieved text as evidence. A manual may describe `sudo`, pairing or
   shutdown commands; the help provider returns explanatory text and cannot run
   them. No model prompt can turn `read` into a maintenance operation.
8. Generate a short answer with source links, date and review limitations. If
   evidence is absent, conflicting or outdated, say so and point to the operator
   workflow. Do not invent current hardware health from documentation.

Test a known capability question, current-versus-draft setup question, unavailable
engine, changed source hash, broken citation, path traversal, symlink swap,
oversized file, private path, malicious document, subprocess timeout, inherited
secret exclusion and stopped robot service startup. No query may mutate the wiki.

## Validation and manual acceptance

### Automated gate after each increment

Run from the repository root in a prepared development environment. The commands
below are future implementation gates, not results claimed by this plan.
`--no-sync` preserves the working environment instead of reinstalling hardware
packages. If dependencies change, first prepare an isolated, explicitly reviewed
test environment from the updated lock; do not use this flag to conceal missing
or incorrect dependencies.

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

Expected result: all applicable checks pass, existing driver authorizations remain
unchanged, and tests use fake accounts/devices. If the baseline already fails,
record and reproduce it; do not call it a new regression or silently bypass it.
Run managed-driver tests separately if their integration is affected, because
standalone suites reuse test module names. Do not alter the immutable baseline.

Add focused suites for information storage, calendar operations, research,
briefings, retrieval, recipes, skill compatibility and project help. These are
proposed test areas, not currently runnable new filenames. Include packaging
tests that bundled templates/manifests are included and optional calendar/wiki
dependencies remain optional. Measure cancellation responsiveness while an
external call or approval is pending using an injected clock and blocked fake.

### Future walkthrough requirements

Create `docs/validation/refinement_phase4_walkthrough_<date>.md` and a matching
handoff when implementation is ready. Replace proposed tool names with the actual
CLI/web controls and supply copyable Pi OS Lite commands, expected output and
recovery for each step. No hypothetical new command in this plan is available yet.

| Step | Manual action after implementation | Required observation and recovery |
| --- | --- | --- |
| 1 | Start the existing Agent through the already documented manual or service path, using only one hardware owner. Leave calendar/search disabled. | Existing chat, tasks and speech controls behave as before. Restore prior configuration if startup regresses. |
| 2 | Create a harmless note/checklist, edit an item, restart, read it, then delete it. | Stable IDs/revisions, persistence and deletion work. Test another controlled user without sharing personal content. |
| 3 | Request a local-only briefing with the network unavailable. | Local tasks remain useful; external sections say unavailable; no startup briefing is generated. |
| 4 | Explicitly connect a test calendar using the headless setup helper with read scope. Read an exact day. | Correct account, time zone and complete/incomplete result. Revoke/disconnect through documented controls if incorrect. |
| 5 | Request a harmless event preview, change its time, then reject it. | No remote event exists. Old preview cannot be confirmed after the edit. |
| 6 | With explicit write authorization on the test calendar, confirm one preview once and inspect the remote event. | One matching event and verified receipt. Removal is a separate reviewed action. Never test using invitations or real commitments. |
| 7 | Exercise uncertain-write and restart scenarios with the supplied fake backend. | No duplicate write; state says uncertain until verified. Do not deliberately corrupt a real account to simulate failure. |
| 8 | Ask for a sourced comparison; request saving; read the saved note. | Real citations, dates and limitations survive saving. Provider charges are understood before enabling paid search. |
| 9 | Save a recipe, inspect it, run with new inputs, cancel, then select a prior version. | Saving alone does nothing; each effect is checked; completed effects and rollback meaning are clear. |
| 10 | Load an old skill and a new template, then disable a required connector. | Version-1 compatibility; clear missing capability; no automatic installation or permission expansion. |
| 11 | Ask a project-help question with known and deliberately stale fixture sources. | Correct citations and visible coverage limits; no wiki changes or secret exposure. |
| 12 | During blocked fake research, use task cancel and existing Stop Speech/Stop Movement controls. | Controls remain responsive; text/status remains accessible; no delayed output after cancellation. |

Separate acceptance classes:

- **Safe smoke:** fake providers, temporary owned data and disabled speech; no
  device communication. Expected result is correct state and text. Roll back by
  disabling new optional providers and preserving the previous private backup.
- **Device communication:** optional existing speaker reconnect/status checks
  using the Phase 3 walkthrough. Audible output requires operator consent;
  restore speech off if it fails. Phase 4 does not change Bluetooth setup.
- **Actuator-moving:** not required by Phase 4. Any independently requested
  regression test uses raised wheels and an operator ready to remove power.
- **Power-risk:** no live power-off, boot-file or service deployment test required.
  Test command construction only; preserve the existing power policy.

Account write tests are a separate explicit external-effect category. Simulation
passes cannot be presented as real account acceptance, and real account acceptance
does not establish physical robot acceptance.

## Documentation, release and rollback

Wiki impact: substantial once implemented. Update manuals and feature evidence
for account setup, privacy, notes, recipes, skill versions and runtime project help.
During this planning task, the two proposal documents are the only deliverables;
no wiki ingestion, semantic review or publication is performed.

At the authorized implementation checkpoint:

1. Update `README.md`, progress and walkthrough/handoff with implemented behavior,
   defaults, optional services and known limits. Keep proposals labeled as such.
2. Create new source versions of Installation Guide, Development Guide, MCP and
   Skills Guide and Development Log. Preserve registered originals. Start from
   the latest reviewed content and explicitly reconcile the prepared Phase 3 Lite
   corrections with published pointers so that they are not lost.
3. Update `THIRD_PARTY_NOTICES.md` and locked optional dependencies if a new
   authentication package or service is introduced. Record source, version,
   license, download verification and preview-first installation instructions.
4. When the owner resumes wiki work, prepare the specific semantic diff, source
   and manual-pointer changes; obtain approval before applying it. Review actual
   implementation fingerprints and new files. Do not blanket-refresh hashes.
5. After authorized publication, run `python scripts/wiki.py check`, wiki lint
   and local-link checks. Record actual AI review and outstanding human checks.
   Until then, the X05 current-knowledge claim remains limited as described above.
6. Explain rollback before release: disable optional connectors, stop new recipe
   runs, preserve/reconcile in-flight external receipts, and back up private data
   through the existing procedure. Disabling a connector does not undo remote
   events. Avoid automatic reverse database migration or deletion of new notes.
7. Verify older application compatibility against the expanded database. If older
   code rejects new configuration keys, remove only the documented new keys in
   a reviewed private configuration copy. Preserve data before any downgrade.

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

- [ ] Deferred by owner: T04 reads, exact previews, scoped writes, verification and uncertain recovery
  pass without weakening generic MCP read-only policy.
- [ ] Deferred by owner: T05 produces dated, supported citations, partial outcomes and requested
  private note saving.
- [ ] Deferred by owner: T06 provides owned notes/checklists and an on-request, useful offline briefing.
- [x] M03 improves measured retrieval without leaking users or flooding context.
- [x] M04 supports reviewed versions, bounded runs, feedback and rollback without
  automatic policy learning or repeated uncertain effects.
- [x] X01 keeps version-1 packages working and verifies version-2 requirements.
- [x] X05 is bounded, read-only, optional and honest about source publication.
- [ ] Existing alarms, speech, hardware paths, APIs and driver hashes remain intact.
- [ ] Every implementation increment has recorded lint, type, test and relevant
  packaging/privacy results; remaining physical/account checks are explicit.
- [ ] Consolidated documentation and deferred wiki status are accurate. The owner
  receives a step-by-step walkthrough and accepts the phase before further work.

Use the [Phase 3 troubleshooting and setup instructions](../docs/validation/refinement_phase3_walkthrough_260909.md)
for existing speech issues and the
[wiki maintenance workflow](../ninjarobot_pi5_wiki/docs/PROJECT_WORKFLOW.md) for
authorized knowledge publication. H03, H05, T08, M05, B03, X02 and X04 remain
deferred; ordinary regression tests in this plan do not expand those projects.
