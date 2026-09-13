# Phase 4 information assistant — walkthrough and manual tests

This guide covers T04 calendar planning, T05 research with evidence, and T06
notes, checklists and requested briefings. The existing memory retrieval,
read-only recipes, project help, robot controls and optional Phase 5 interactions
remain available.

The automated tests use temporary data and simulated providers. They do not prove
that your Google account, internet connection or speaker works. Complete the
local tests first. Calendar writes are optional and affect the selected Google
calendar only after your separate confirmation.

## Contents

1. [Prepare the existing installation](#1-prepare-the-existing-installation)
2. [Create, review and read a note](#2-create-review-and-read-a-note)
3. [Edit a checklist and delete a test note](#3-edit-a-checklist-and-delete-a-test-note)
4. [Build a local briefing](#4-build-a-local-briefing)
5. [Connect Google Calendar on Pi OS Lite](#5-connect-google-calendar-on-pi-os-lite)
6. [Read a schedule and suggest a time](#6-read-a-schedule-and-suggest-a-time)
7. [Review a calendar change](#7-review-a-calendar-change)
8. [Research with evidence and save a result](#8-research-with-evidence-and-save-a-result)
9. [Recovery, privacy and regression checks](#9-recovery-privacy-and-regression-checks)
10. [Record acceptance](#10-record-acceptance)

## 1. Prepare the existing installation

Run the commands on the Pi as your normal robot user. Keep the robot idle.
Restarting your existing real service can run its existing startup behavior;
follow your usual raised-wheel precautions. These new information features do
not require motors, camera, microphone or new boot services.

In a terminal, enter the checkout and activate its existing environment:

~~~bash
cd ~/NinjaRobotPi5
source .venv/bin/activate
nr() { ninjarobot-agent "$@"; }
nr information --help
nr calendar-connect --help
nr service status
~~~

Expected: both new command help pages appear. If they do not, this terminal is
using an old installation. Do not reinstall individual Pi5 drivers to fix a
missing Agent command. Follow the normal project installation/upgrade procedure.

Back up before the first updated start. Use a fresh archive name and keep it
private; it includes notes, calendar credentials and other existing private data:

~~~bash
nr deployment backup --output "$HOME/ninjarobot-before-information-$(date +%Y%m%d-%H%M%S).tar.gz"
~~~

Load the new code with your existing service manager. For a service you normally
start through the CLI (command-line interface), run:

~~~bash
nr service stop
nr service start --real
nr service status
~~~

If you use the installed system service, use its existing stop/start procedure
instead. Do not run two service owners. The updated service adds database
revision 7 automatically; it does not remove old records.

Use the same local-cli session throughout these tests:

~~~bash
nr memory profiles
nr chat --session local-cli "/speech off"
nr chat --session local-cli "/disarm"
nr information notes.list --session local-cli
~~~

Expected: your existing profile is present, speech is off, motion is unarmed,
and notes.list returns your own notes. If no profile exists, finish the existing
profile setup separately. Private information features require memory enabled
and an existing local profile.

## 2. Create, review and read a note

Create a harmless test checklist. This command saves a five-minute preview,
not the final note:

~~~bash
nr information notes.create --session local-cli --arguments   '{"content":{"title":"Phase 4 packing test","body":"A harmless manual-test note.","items":[{"text":"Pack charger"},{"text":"Pack notebook"}]}}'
~~~

Expected: executed is false. The output contains record_id for the preview,
payload.change with the exact content, payload.review_hash and expires_at.
Read the content before proceeding.

Copy the two returned values into these shell variables, replacing the sample
words. These are local record identifiers, not passwords:

~~~bash
NINJA_PREVIEW_ID='replace-with-preview-record_id'
NINJA_REVIEW_HASH='replace-with-payload-review_hash'
~~~

Apply exactly that preview:

~~~bash
nr information notes.confirm --session local-cli --confirm --arguments   "{"preview_id":"$NINJA_PREVIEW_ID","review_hash":"$NINJA_REVIEW_HASH"}"
nr information notes.list --session local-cli
~~~

Expected: a saved note appears once, with a note- identifier and revision 1.
Copy its identifier for the remaining steps:

~~~bash
NINJA_NOTE_ID='replace-with-saved-note-record_id'
nr information notes.read --session local-cli --arguments   "{"record_id":"$NINJA_NOTE_ID"}"
~~~

Repeat the same confirmation once. Expected: it is refused as consumed; no second
note appears. Omitting --confirm must also be refused. If five minutes elapsed,
make a new preview and review the newly returned values.

Large notes return page, pages and content_chunk instead of a large message.
Read every page of the same revision before approving an edit:

~~~bash
nr information notes.read --session local-cli --arguments   "{"record_id":"$NINJA_NOTE_ID","page":2}"
~~~

Use page 2 only when the response says there are at least two pages.
For a large preview, use notes.preview and its preview record_id instead.
The review_hash is at the top level of a paged response. Joining content_chunk
in page order reconstructs the exact JSON record.

### The same workflow in web chat

The web controller's existing chat accepts the same deterministic actions.
For example, type:

~~~text
/info notes.list
/info notes.create {"arguments":{"content":{"title":"Web test","body":"Created from chat"}}}
/info notes.confirm {"arguments":{"preview_id":"COPY_PREVIEW_ID","review_hash":"COPY_REVIEW_HASH"},"confirmed":true}
~~~

Review the returned preview before typing the last command. Use the same web
session that created it. A CLI preview cannot be confirmed from a different chat
session. No new dashboard panel or browser extension is needed.

Natural-language requests can ask the model to prepare these changes, but the
model has no confirmation tool. Always distinguish a preview from a completed
save. Direct commands work without a conversation model connection.

## 3. Edit a checklist and delete a test note

Read the current note and copy the stable item_id beside Pack charger.
Do not use its position in the list:

~~~bash
NINJA_ITEM_ID='replace-with-Pack-charger-item_id'
nr information checklists.set_item --session local-cli --arguments   "{"record_id":"$NINJA_NOTE_ID","revision":1,"item_id":"$NINJA_ITEM_ID","completed":true}"
~~~

Review the new preview. Replace NINJA_PREVIEW_ID and NINJA_REVIEW_HASH with
its values, then use notes.confirm as in section 2. Expected: only Pack charger
is checked and the note revision increases to 2.

For a full edit, read the current note first. Supply its current revision and
the complete replacement content to notes.update. Preserve unchanged item IDs.
Omitted content is intentionally removed by a full replacement; use
checklists.set_item when changing only one checkbox.

Try another edit using the old revision 1. Expected: it is refused. Read the
latest revision before making another preview; never guess a revision number.

Keep the packing note until the briefing test is finished. To remove only this
test note afterwards:

~~~bash
nr information notes.delete --session local-cli --arguments   "{"record_id":"$NINJA_NOTE_ID","revision":2}"
~~~

Use the actual current revision if it differs. Review the deletion preview, then
confirm its new preview ID and hash. Expected: notes.list no longer includes it.
Deleting a note does not delete reminders or calendar events.

## 4. Build a local briefing

While the packing note still exists, request today's briefing explicitly:

~~~bash
nr information briefing.build --session local-cli --arguments   "{"timezone":"Asia/Tokyo","note_ids":["$NINJA_NOTE_ID"]}"
~~~

Replace Asia/Tokyo if needed with your actual named time zone. Expected:

- The interval is today's midnight through tomorrow's midnight in that zone.
- Existing local reminders in that interval show IDs, titles and due times.
- Only selected unfinished checklist items appear.
- Each section says available, incomplete or unavailable.
- saved is false. Building a briefing creates no note or reminder.

No Google connection or model connection is needed for this local-only command.
If there are no reminders, an empty reminder section is correct.

For an optional speaker test, use your already configured speaker:

~~~bash
nr chat --session local-cli "/speech on"
nr information briefing.build --session local-cli --arguments   "{"timezone":"Asia/Tokyo","note_ids":["$NINJA_NOTE_ID"]}"
nr chat --session local-cli "/speech off"
~~~

Expected: a short summary is spoken, with full detail in text. Output failure must
leave the text usable. Stop Speech retains its existing behavior. Do not pair or
change audio settings as part of this test unless you intend to do so.

To save a briefing, explicitly create a note containing the summary you want to
keep, then review and confirm it. There is no automatic daily briefing, startup
notification or silent copying of every calendar event into notes.

## 5. Connect Google Calendar on Pi OS Lite

This optional step sends authorization requests to Google. No Pi desktop is
required. OAuth means Google's browser-based permission process. PKCE adds a
one-use proof so a copied callback code alone cannot complete the login.

### Prepare a Google Desktop app client

On your computer, use Google's
[installed-app authorization guide](https://developers.google.com/identity/protocols/oauth2/native-app).
Create/select a Google Cloud project, enable Google Calendar API, configure the
consent screen and any required test user, then create an OAuth client of type
Desktop app. Download its client JSON file. Workspace administrators may restrict
this process; follow the account's rules.

Create an empty test calendar in Google Calendar before write testing. In its
settings, copy the Calendar ID from Integrate calendar. Use that exact ID,
not a display name or the alias primary.

Transfer the Desktop client file from your computer to the Pi. Replace
PI_USER, PI_HOST and the local download path:

~~~bash
ssh PI_USER@PI_HOST 'mkdir -p ~/.config/ninjarobot_pi5'
scp ~/Downloads/client_secret.json PI_USER@PI_HOST:~/.config/ninjarobot_pi5/google-desktop-client.json
ssh PI_USER@PI_HOST 'chmod 600 ~/.config/ninjarobot_pi5/google-desktop-client.json'
~~~

The file is private configuration. Do not put it in the repository or chat.

### Open a private callback tunnel

On your computer, open a terminal and leave this command running:

~~~bash
ssh -N -L 127.0.0.1:8765:127.0.0.1:8765 PI_USER@PI_HOST
~~~

This forwards only your computer's loopback port to the Pi's loopback port.
Do not use router forwarding, a public callback address or the robot web port.

In a second terminal connected to the Pi, activate the existing environment
as in section 1 and run:

~~~bash
nr calendar-connect   --client-file ~/.config/ninjarobot_pi5/google-desktop-client.json   --calendar-id 'COPY_EXACT_CALENDAR_ID'   --account-label 'My test Google account'   --session local-cli
~~~

Open the printed Google URL in your computer's browser and authorize the intended
account. Keep the tunnel open until the Pi command returns. The helper waits up
to five minutes. Expected: the browser reports authorization received and the Pi
prints a connection_id with write_enabled false. It never prints access or
refresh tokens. Account label is your descriptive label, not proof of identity;
verify the actual account on Google's consent screen.

After completion, Ctrl+C in the tunnel terminal closes the tunnel. No callback
listener remains active. Saved refresh credentials live in the existing
owner-only Agent secret file; ordinary database records contain a reference only.

List your connections:

~~~bash
nr information calendar.connections --session local-cli
~~~

Copy the returned ID:

~~~bash
NINJA_CONNECTION_ID='replace-with-connection_id'
~~~

If authorization is revoked, expired or prohibited, reads report unavailable.
Rerun explicit setup when appropriate. The Agent never expands permissions
automatically. Disconnecting locally does not revoke Google's grant; use your
Google account's connected-app settings if you also want remote revocation.

## 6. Read a schedule and suggest a time

Use real dates you want to inspect. Include an explicit UTC offset matching the
named time zone. This example is 15 September 2026 in Japan:

~~~bash
nr information calendar.list_events --session local-cli --arguments   "{"connection_id":"$NINJA_CONNECTION_ID","start":"2026-09-15T00:00:00+09:00","end":"2026-09-16T00:00:00+09:00","timezone":"Asia/Tokyo"}"
nr information calendar.suggest_time --session local-cli --arguments   "{"connection_id":"$NINJA_CONNECTION_ID","start":"2026-09-15T09:00:00+09:00","end":"2026-09-15T17:00:00+09:00","timezone":"Asia/Tokyo","minutes":30}"
~~~

Expected: results identify the calendar, time zone, checked interval and coverage.
An all-day event retains date values; its end date is exclusive.
Suggestions reserve nothing and are offered only after a complete read.
Overlapping events and all-day busy periods must be excluded.

Reads stop at 31 days, five pages, 200 events, 1 MiB or 15 seconds.
The model view is smaller and may ask you to narrow the interval.
Incomplete or unavailable results must never be described as an empty calendar.

## 7. Review a calendar change

Write testing affects your Google calendar. Use the empty test calendar you
created. Re-run calendar-connect with --write to authorize the specific write
scope. This creates a new connection; it does not upgrade the old read-only one:

~~~bash
nr calendar-connect   --client-file ~/.config/ninjarobot_pi5/google-desktop-client.json   --calendar-id 'COPY_EXACT_TEST_CALENDAR_ID'   --account-label 'Disposable calendar test'   --write --session local-cli
~~~

Set NINJA_CONNECTION_ID to this new write-enabled connection ID.
Prepare a harmless event with a suitable date:

~~~bash
nr information calendar.propose_change --session local-cli --arguments   "{"action":"create","connection_id":"$NINJA_CONNECTION_ID","event":{"title":"NinjaRobot manual test","start":"2026-09-15T10:00:00+09:00","end":"2026-09-15T10:30:00+09:00","timezone":"Asia/Tokyo"}}"
~~~

Expected: no event appears yet. Review account label, exact calendar ID, event
content, time and expiration. Copy record_id and payload.review_hash:

~~~bash
NINJA_OPERATION_ID='replace-with-preview-record_id'
NINJA_CALENDAR_HASH='replace-with-payload-review_hash'
nr information calendar.confirm --session local-cli --confirm --arguments   "{"operation_id":"$NINJA_OPERATION_ID","review_hash":"$NINJA_CALENDAR_HASH"}"
nr information calendar.operation_status --session local-cli --arguments   "{"operation_id":"$NINJA_OPERATION_ID"}"
~~~

Expected: payload.state is verified and exactly one matching event appears in
Google Calendar. Verification uses a separate read of the saved event ID.
Repeating this confirmation must be refused.

If state is uncertain, do not create another event. Read Google Calendar and
reconcile the saved operation:

~~~bash
nr information calendar.reconcile --session local-cli --arguments   "{"operation_id":"$NINJA_OPERATION_ID"}"
~~~

Reconciliation reads only; it never repeats the write. Absence alone does not
prove a timed-out create never happened.

To stop a pending operation before approving it:

~~~bash
nr information calendar.cancel --session local-cli --arguments   "{"operation_id":"$NINJA_OPERATION_ID"}"
~~~

This cancels local authorization/work. It does not delete a remotely created
event. Cancellation after dispatch can leave an uncertain external outcome.

### Update or remove the event created by this integration

Copy payload.event_id from the verified create receipt:

~~~bash
NINJA_EVENT_ID='replace-with-verified-event_id'
nr information calendar.propose_change --session local-cli --arguments   "{"action":"update","connection_id":"$NINJA_CONNECTION_ID","event_id":"$NINJA_EVENT_ID","event":{"title":"Updated NinjaRobot test","start":"2026-09-15T11:00:00+09:00","end":"2026-09-15T11:30:00+09:00","timezone":"Asia/Tokyo"}}"
~~~

Review and confirm the new operation ID and hash. Unspecified Google fields are
preserved; the supported title, description, location and dates are replaced by
the exact draft. An ETag (Google's object-version marker) prevents overwriting
an event changed since preview. A conflict needs a new preview, not an automatic
retry.

For cleanup, preview cancellation of that event:

~~~bash
nr information calendar.propose_change --session local-cli --arguments   "{"action":"cancel","connection_id":"$NINJA_CONNECTION_ID","event_id":"$NINJA_EVENT_ID"}"
~~~

Review and confirm this new operation. Expected: the event is removed remotely
and the operation becomes verified. Only individually verified events created
by this same connection are eligible. Attendees, invitations and recurring
events are not supported. Local reminders are unaffected.

Disconnect the test connection when finished:

~~~bash
nr information calendar.disconnect --session local-cli --confirm --arguments   "{"connection_id":"$NINJA_CONNECTION_ID"}"
~~~

Expected: further access is disabled and its local credential is removed.
Remote events remain unchanged by disconnect.

## 8. Research with evidence and save a result

Research uses the existing approved Tavily MCP server with ID tavily.
MCP is the existing external-tool connection format. It does not introduce
unrestricted page fetching.

If Tavily is already configured:

~~~bash
nr mcp inspect tavily
nr mcp health tavily
nr mcp tools tavily
~~~

Otherwise follow the
[full MCP guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-13-03/NinjaRobot_MCP_Skill.md#add-tavily-web-search)
for explicit key entry and setup, then restart the existing Agent once.
Do not paste keys into chat. Provider/model usage can incur charges.
Call and time limits are not a monetary spending cap.

Run a public test query:

~~~bash
nr information research.search --session local-cli --arguments   '{"queries":["Official Raspberry Pi 5 documentation"]}'
~~~

Expected: a run_id, actual source IDs such as S1, URLs, provider excerpts,
retrieval times, and publication dates only when provided. These are snippets,
not downloaded full pages. Missing/failed queries are reported. No note is
saved by searching.

Copy the run ID and use source IDs actually returned:

~~~bash
NINJA_RESEARCH_ID='replace-with-run_id'
nr information research.answer --session local-cli --arguments   "{"run_id":"$NINJA_RESEARCH_ID","claims":[{"text":"This may be useful documentation for Pi 5 owners.","source_ids":["S1"]}]}"
~~~

Expected: the non-literal interpretation is explicitly qualified and references
contain actual URLs and dates. Try S999 instead: it must be rejected.
Literal excerpts are also labeled as provider evidence, not independently
verified facts. Conflicting sources need explanation or another search;
citation membership alone cannot prove a claim.

To save the useful summary, make an explicit save request:

~~~bash
nr information research.save_note --session local-cli --arguments   "{"run_id":"$NINJA_RESEARCH_ID","title":"Pi 5 research test","summary":"Replace this with the useful summary you reviewed.","citations":["S1"]}"
~~~

Review and confirm the returned note preview through notes.confirm.
Repeating research.save_note for this run returns the same preview, even after
confirmation; it does not duplicate the note. Later edits use notes.update.
Search runs and note previews older than seven days are cleaned at service
startup. Saved notes remain until you delete them or their user profile.

For natural-language research, use the updated current-web-answer skill, or ask
the Agent to research a public question and cite sources. An installed private
copy of an older skill is not silently overwritten; inspect it with the existing
skill commands if it shadows the bundled version.

## 9. Recovery, privacy and regression checks

Run these checks with harmless test data:

| Check | Expected result |
| --- | --- |
| Confirm a preview with a different hash or session | Refused; no write. |
| Wait over five minutes before confirmation | Refused; create and review a fresh preview. |
| Restart with an unconfirmed preview | It expires; nothing executes at startup. |
| Interrupt a dispatched calendar write | Outcome may remain uncertain; reconcile by saved ID. |
| Edit the remote test event after preview | The old version cannot silently overwrite it. |
| Use read-only credentials for a change | Refused before a remote write. |
| Request a briefing with a disconnected calendar ID | Local reminders/checklists remain usable; calendar section unavailable. |
| Read another user's note ID | Refused. Switching users also withholds delayed private results. |
| Cancel a long request with /tasks cancel TASK_ID | Further work stops; an already dispatched calendar effect may remain. |
| Read large notes from web chat | Pages remain within chat limits; note text is displayed as text. |
| Run /time, /tasks, /project and an existing read-only recipe | Existing behavior remains available. |
| Restart after making a backup and restoring it offline | Saved notes return; pending approvals expire on startup. |

Backups include the existing secret file as well as the database. Restoring an
old backup may restore old credentials and local connection records. It cannot
undo external Google changes. Revoke access through Google when remote
revocation is needed; do not share backup archives.

Notes and calendar receipts are user-owned and bounded to 1,000 records per
record kind. Calendar receipts remain until profile deletion/reset; they are
needed to verify which events this integration created. This is not a general
account-wide calendar editor. Broad identity redesign and automatic learning
remain outside this delivery.

Do not delete your real user profile to test privacy cleanup. Automated tests
cover temporary users and backup recovery. Use disposable test profiles only if
you intentionally want a separate manual deletion test.

## 10. Record acceptance

Record pass/fail and the actual date for notes, checklists, local briefing,
Google login, calendar read/create/update/cancel, research, saved references,
speech and recovery. Do not put tokens or private calendar contents into a
report you intend to share.

- Safe smoke: help, list/read, local text briefing. Expected: no device movement.
  Rollback: stop using the new commands; retain the private backup.
- Device communication: only your separately chosen service startup and speaker
  test. Expected: normal existing startup and optional short speech.
  Rollback: /speech off, then use the existing service-stop procedure if needed.
- Actuator movement: not required for this delivery. Any separate regression
  test needs raised wheels and an operator ready to remove power.
- Power risk: no shutdown, reboot or power-loss test is required.

See the [implementation handoff](refinement_phase4_information_handoff_260913.md)
for software evidence and limitations. Wiki ingestion, review and publication
remain skipped; read the new full manuals directly.
