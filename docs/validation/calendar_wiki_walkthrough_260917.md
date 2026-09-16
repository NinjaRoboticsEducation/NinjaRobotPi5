# Calendar and current project help: walkthrough and validation

The approved repair is implemented. The Agent remains stopped, as requested.
The original credentials and legacy token have not been changed. No event was
read, created, edited, or deleted during implementation. Wiki ingestion and
semantic review were not run; the owner will do them after manual validation.

## What was repaired

The legacy Google Calendar MCP server was configured but exposed zero tools:
`allowed_tools` named its reader, but the required `read_only_tools` review
was missing. The setup example and local configuration now include both.
Catalog-only inspection confirms `mcp.google-calendar.list_today_events` exists.
A provider with zero exposed tools now reports degraded status with an explanation.

The previous example authorizer wrote a separate read-only token. The supported
`calendar-connect` flow now discovers the primary calendar after protected browser
consent and registers it with the built-in Calendar service. Optional explicit
calendar ID, label, credentials file, and session overrides remain compatible.
Reauthorizing the same calendar preserves its connection ID, updates its revision,
and removes the superseded private grant. Existing previews for the old revision
cannot authorize a new write. Actual event creation still requires an exact
preview followed by direct user confirmation; external MCP writes remain blocked.

The local example's `authorize.py` now delegates to this guided setup. Its original
file is preserved as `authorize.py.before-calendar-260917`; the MCP configuration
backup is `mcp.toml.before-calendar-260917` in the existing private configuration
folder. The wrapper requests read plus reviewed event creation by default;
`--read-only` remains available. It does not migrate or overwrite the separate
legacy reader token. Prefer built-in tools after the new connection is established.

Project help previously pinned four pages to outdated September 12 hashes and
could not read procedural manual sections. Default retrieval now reads the four
full public manuals from the current document map plus this release's explicitly
listed unpublished successor sources. It ranks sections, removes duplicate
excerpts, returns citations and continuation IDs, and bounds each section to
3,000 characters. It rejects private paths, symbolic links, altered source hashes,
and oversized files. The old explicit-manifest interface remains supported.

The runtime-only `project_help_sources.json` is not wiki ingestion or an approval
of wiki claims. New sources are labeled unpublished. Later registered versions
supersede them automatically. In a checkout with no wiki, project help reports
that documentation is unavailable rather than claiming to have searched it.

## Load the update safely

These changes do not need motor, camera, microphone, or power-off testing. They
change account access, local documentation retrieval, and chat guidance.

1. Read the current [Installation Guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-17/InstallationGuide.md).
   Its opening section contains the full Lite command-line setup procedure.
2. When ready, start your usual Agent from the Pi checkout. For the manually
   managed installation used here:

   ```bash
   cd "$HOME/NinjaRobotPi5"
   uv run --frozen --no-sync ninjarobot-agent service start --real
   ```

   This starts the real hardware service. Do not launch a second instance if
   your installation instead uses system-managed startup.
3. Refresh and reconnect the web controller. No memory clearing or additional
   project-help configuration is required.

## Test 1: existing read-only MCP reader

From the checkout:

```bash
uv run --frozen --no-sync ninjarobot-agent mcp tools google-calendar
```

Expect the tool `mcp.google-calendar.list_today_events`. This command discovers
its schema; it does not read your events. In chat, explicitly ask to use the
available read-only Google Calendar reader for today's schedule. An expired
legacy token can still fail a real read; discovery alone does not validate it.
The recommended durable path is the new built-in connection in Test 2.

## Test 2: authorize and register the primary calendar

1. On your computer, open the tunnel, replacing the login and host:

   ```bash
   ssh -L 8765:127.0.0.1:8765 YOUR_PI_USER@YOUR_PI_HOST
   ```

2. In that SSH session on the Pi, run:

   ```bash
   cd "$HOME/NinjaRobotPi5"
   uv run --frozen --no-sync ninjarobot-agent calendar-connect --write
   ```

   Credentials are read from
   `$HOME/.config/ninjarobot_pi5/google-calendar/credentials.json`. The Agent must
   be running; if it is stopped, setup exits before opening an authorization flow.
   The compatibility alternative is `uv run python authorize.py` in the existing
   `$HOME/ninjarobot-mcp/google-calendar-readonly` folder, with the same SSH tunnel.
3. Open the printed Google URL on your computer. Select the intended account and
   grant the event and calendar-list permissions. Do not paste secrets into chat.
   The browser should report receipt of authorization. Return to the Pi terminal.
4. Expect a connection ID and resolved calendar ID with `write_enabled: true`.
   Do not enter a second account configuration. The Agent sees the connection
   immediately; another restart is unnecessary.
5. In terminal or web chat run `/info calendar.connections`. Use the same local
   user profile as setup. Ask “What is on my Google Calendar today?” Compare the
   answer with Google Calendar, including the time zone.
6. Optionally repeat authorization for the same calendar. Expect the same
   connection ID and one connection for that calendar, not a duplicate. Selecting
   a different Google account creates a distinct connection rather than replacing
   the wrong account. Ask the Agent to use a specific connection if several exist.

Google's new consent is required to add write permissions. Existing read-only
credentials are not upgraded silently. The default primary calendar requires
ownership for the selected write permission.

## Test 3: preview and explicitly confirm an event

This test can create a real event only at step 3. Choose a harmless future test
appointment and check the calendar and time zone carefully.

1. Ask: “Prepare a Calendar event titled NinjaRobot manual test for [date], from
   [start] to [end] in Asia/Tokyo. Show me the preview first.” Supply real times.
2. Check the preview's title, account, calendar ID, time zone, start and end. Verify
   the event has not yet appeared in Google Calendar. Keep its operation ID and
   review hash (the fingerprint of the exact preview).
3. Only if you approve the preview, enter this in the same chat session:

   ```text
   /info calendar.confirm {"arguments":{"operation_id":"PASTE_OPERATION_ID","review_hash":"PASTE_REVIEW_HASH"}}
   ```

   Expect a verified result and exactly one event in Google Calendar. Previews
   expire after five minutes; if expired, prepare and review a new one.
4. If the result is uncertain, ask for that operation's status or use the existing
   reconciliation control. Do not ask for a second creation to compensate for an
   unknown result. Remove your test event in Google Calendar when finished.

## Test 4: complete project instructions in both chat interfaces

Ask each question in terminal chat and web chat:

1. “Retrieve the project documentation and give me step-by-step instructions for
   authorizing Google Calendar on Raspberry Pi OS Lite.” Expect SSH tunnel,
   credentials path, Agent-start prerequisite, browser consent, primary-calendar
   registration, and citations. No credentials should be requested in chat.
2. “How do I pair a Bluetooth speaker?” Expect relevant current setup instructions.
3. “Explain the NinjaRobot hardware architecture.” Expect the Agent-to-IDE-to-driver
   boundary, with citations.
4. “How do I troubleshoot invalid distance sensor readings?” Expect documented
   checks rather than a claim that documentation proves current hardware health.
5. For a deterministic retrieval check without relying on model selection, enter
   `/project Google Calendar authorization`. Expect current manual sections with
   `document_id` and `next_document_id`, source paths, and unpublished labels.

Long procedures may require several reads. The project-help skill explicitly
instructs the model to follow continuation IDs. Model behavior still needs this
manual acceptance check; automated retrieval does not certify every generated answer.

## Validation record

| Check | Result |
| --- | --- |
| Complete root suite | 944 passed in 41.34 seconds; one existing Starlette deprecation warning |
| Ruff lint and formatting | Pass; 451 files |
| mypy | Pass; 113 source files |
| Python compilation | Pass |
| Managed-driver integrity | Pass; 222 files and 56 existing authorized repairs |
| Workspace driver sources | Pass; all six libraries use this checkout |
| Package build | Source archive and wheel built; new retrieval module, manifest, and skill included |
| Local documentation links | 197 checked; no missing file targets |
| Whitespace | `git diff --check` passed |
| Local MCP discovery | Expected read-only Calendar tool exposed; no event read performed |

The previously failing real-public-checkpoint test now passes. Tests use
fake HTTP services and temporary files; they do not authorize real Google accounts.
No new dependencies or driver changes were required. Existing Google service
notices remain applicable. Hardware/actuator-moving and power-risk checks are not
required for these changes.

## Rollback and remaining acceptance

Stop the Agent before reverting runtime changes. Restore only this task's code,
public-source manifest, and documentation as needed. To undo the local example
changes, restore the two named backup files; doing so restores the earlier missing
read declaration and the legacy authorization behavior. Preserve credentials,
private database records, and user memory. Reverting code does not undo a real
Google event; manage that event explicitly in Google Calendar.

Pending owner checks: new Google consent, live schedule reads, preview/confirmed
creation, and natural-language instructions in both interfaces. The Agent was left
stopped. No automated result is claimed as live account acceptance.
