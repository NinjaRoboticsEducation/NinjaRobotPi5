# Calendar connection and project help repair plan

Status: approved by the owner on 17 September 2026; implemented. See the
[walkthrough and validation record](calendar_wiki_walkthrough_260917.md).
Date: 17 September 2026. No runtime, private configuration, credentials, or
calendar events were changed during diagnosis. The running Agent was not restarted.

## Confirmed causes

1. The external `google-calendar` server is enabled and allows
   `list_today_events`, but its local configuration omits the reviewed read-only
   declaration. `MCPToolProvider._refresh_catalog` deliberately skips unreviewed
   tools. Live status confirms the provider is ready with zero exposed tools.
   The current tutorial's configuration example also omits this declaration.
2. The existing `authorize.py` saves a read-only Google token. It neither registers
   a connection with the built-in Calendar service nor grants permission to create
   events. Both credential files exist with owner-only access; token contents
   were not printed. A refresh token exists, but its validity against Google has
   not been tested by this audit.
3. The example Calendar server and the built-in Phase 4 Calendar service use
   separate connection mechanisms. A model can consequently see no built-in
   connections even after the example has been authorized.
4. Runtime project help pins only four public pages to September 12 hashes.
   All four differ from the current files. The current document map instead
   names the September 16 manuals. The reader withholds changed files by design.
5. Even with matching hashes, the reader searches a narrow page set and returns
   1,500-character excerpts. It verifies manual sources but does not retrieve
   their complete procedural sections. This is insufficient for setup questions.
6. The locally customized authorization script extracts a code and bypasses
   callback state validation. Its replacement should use the existing protected
   authorization flow rather than preserve that shortcut.

## Phase 1: reliable Calendar connection

Objective: one guided authorization establishes a usable, user-owned connection.

- Correct the reviewed read-only declaration for the inspected external example;
  preserve other servers and all secrets. Explain excluded tools in provider
  diagnostics instead of describing a zero-tool catalog as fully ready.
- Reuse `calendar_oauth.py`, `calendar_google.py`, `calendar_service.py`,
  `information_tools.py`, and `agent_cli.py` for the supported connection flow.
  Keep the legacy read-only MCP tool compatible; do not classify writes as reads.
- Provide a repository-owned setup entry point. After authorization, register
  the selected primary calendar through the running Agent's local connection
  interface, without a separate manual connection command or calendar-ID entry.
  Resolve and verify account/calendar binding before registration. Preserve an
  explicitly selected calendar and active-user ownership across authorization.
- Make the existing external `authorize.py` path a compatible wrapper for this
  guided setup, with a backup of the previous script. Avoid unrelated external
  project edits. Provide actionable instructions if the Agent is stopped.
- Accept existing read-only authorization only when its actual grants satisfy
  the requested operation; never infer write access from file presence. Obtain
  new Google consent for event creation. Validate callback state, use the existing
  proof-key protection, keep secrets outside chat, and store credentials privately.
- Use the existing exact event preview and user confirmation before creating an
  event. The preview must name the calendar, title, date, time, and time zone.
  Preserve duplicate prevention, uncertain-result reconciliation, and revocation
  checks. No automatic real event creation is authorized by this plan alone.
- Update tool guidance so the model checks actual available tools/connections,
  rather than guessing an MCP name or treating empty built-in connections as
  proof that every external Calendar tool is unavailable.

Compatibility: retain current tools, existing accounts, private settings, and the
read-only external-tool boundary. Do not expand event deletion or editing scope.
Hardware risk: none; account permissions and private data are affected.

Validation gate: fake-server tests for missing review declarations, authorization
failure/cancellation, safe repeated setup, scope checks, account switching,
primary-calendar selection, revoked credentials, preview/confirmation, and
uncertain or duplicate writes. Do not create real test events without reviewing
and confirming their exact contents with the owner.

## Phase 2: useful project help without extra setup

Objective: terminal and web chat retrieve current public project documentation.

- Replace the four-page historical checkpoint dependency with discovery from the
  local current public document map and an explicitly limited set of public wiki
  pages and full manuals. Validate registered source hashes and expose draft,
  stale, or unreviewed status honestly. Do not silently refresh verification hashes.
- Search headings and content in bounded sections. Rank relevant sections rather
  than common words in introductory text. Support continuation reads so a long
  installation procedure is not cut off at 1,500 characters.
- Return file/section citations and enough context to answer setup, feature,
  architecture, and documented troubleshooting questions. Keep response sizes
  within the Agent's existing model input budget.
- Preserve traversal and symbolic-link rejection, file/total size limits, and
  public-file allowlisting. No arbitrary private file access, shell execution,
  credential access, or wiki editing through chat.
- Retain `project_help.search`, `project_help.read`, and `/project` compatibility.
  Teach the project-help skill to retrieve missing procedural sections before
  saying instructions are unavailable. Both chat routes use the same provider.
- Report missing checkout or stale evidence explicitly. A package installed
  without local documentation must not pretend it searched the project.

Likely files: `project_help.py`, its manifest, `service_main.py`, project-help
skill/prompt routing, and related tests. No hardware or driver changes.
Validation gate: reproduce the present four-page failure; verify Calendar setup,
Bluetooth setup, architecture, and troubleshooting retrieval against current
sources. Test changed hashes, malformed maps, private paths, symbolic links,
large documents, multi-section instructions, and bounded output.

## Phase 3: validation and handoff

Run driver integrity and workspace-source checks, compilation, Ruff lint and
format checks, mypy, the complete root test suite, and relevant targeted tests.
The previously known public-help checkpoint failure is now directly in scope
and must be repaired rather than excluded. Use fake Google services for automated
coverage; keep tests away from live credentials and hardware.

After implementation, update README and new versions of the Installation Guide,
Development Guide, MCP tutorial, and Development Log. Add a walkthrough covering
Raspberry Pi OS Lite authorization, reconnection, schedule reads, reviewed event
creation, and natural-language project help in terminal and web chat. Preserve
registered source originals. Update third-party notices if dependencies change.

Wiki impact: Calendar setup and project-help documentation change. Perform one
source-documentation update at the end; defer wiki ingestion and semantic review
under the owner's standing instruction. Any new runtime public-document export
must distinguish unpublished sources from reviewed wiki evidence.

Leave the running Agent untouched during implementation. Coordinate loading the
update with the owner before interrupting their running service. Report software
checks separately from account authorization and live user acceptance.

## Upstream reference

Google separates read-only Calendar access from event-writing permission:
[Calendar API authorization scopes](https://developers.google.com/workspace/calendar/api/auth).
OAuth permission expansion requires user consent; a local script cannot grant
it merely by changing its requested scope.
