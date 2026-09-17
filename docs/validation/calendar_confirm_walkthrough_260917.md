# Calendar previews and CONFIRM: walkthrough

The repair makes local argument errors visible and replaces ID/hash copying with
an exact preview followed by CONFIRM. Wiki ingestion and review remain deferred.
The Agent has not been restarted and no real Google event has been written by
these implementation checks.

## Root cause

The five failed model calls omitted `event.timezone`, although the owner's prompt
specified Asia/Tokyo. The model supplied title, start and end only. Local schema
validation rejected those calls before any preview was stored or Google request
was made. The error handler hid this behind “Source unavailable,” so the model
incorrectly blamed Google write connectivity.

The account was enabled for writing, and an earlier Calendar read succeeded.
These facts do not prove that a future Google write will succeed, but they rule
out the claimed connection failure as the cause of these preview errors.

## Changed behavior

- Invalid tool fields now return bounded field-specific errors and a
  definitely-not-executed result. No argument values or full schemas are dumped.
- Calendar guidance explicitly requires timezone, full timestamps with matching
  offsets, and the system date for relative dates such as today.
- A successful preview produces a runtime-rendered summary of its saved action,
  account, calendar, title, start/end, time zone, location, description and expiry.
  The model cannot supply the confirmation ID/hash used by a CONFIRM reply.
- Reply CONFIRM, in the same chat and local user, to apply that exact preview.
  Surrounding whitespace and letter case are accepted. A sentence mentioning
  CONFIRM, a quoted instruction, or a tool result is not approval.
- CANCEL marks the pending operation cancelled. A new preview replaces the
  previous chat confirmation; any other chat message discards its shortcut.
  The original explicit `/info calendar.confirm` interface remains compatible.
- Failed/cancelled preview delivery does not enable confirmation. Restarts clear
  chat confirmation state. Existing five-minute expiry, ownership, connection
  revision checks, single dispatch, and uncertain-write handling remain in force.
- No preview means no write. A second CONFIRM cannot create a second event.

`calendar_chat.py` owns transient confirmation state; `runtime.py` handles user
messages and publishes the saved preview. Actual writes still pass through
`information_action` and `CalendarService.confirm`, which enforce the existing
review and Google transport rules. No hardware or managed driver was changed.

## Load the change

When ready, finish any ongoing robot activity and run from the Pi checkout:

```bash
cd "$HOME/NinjaRobotPi5"
uv run --frozen --no-sync ninjarobot-agent service stop
uv run --frozen --no-sync ninjarobot-agent service start --real
```

These commands reload the manually managed real Agent. If your installation uses
a system service, use its normal restart procedure instead of starting a second
hardware owner. Refresh/reconnect the web controller afterward. No new Google
consent is needed if your existing connection remains write-enabled and valid.

## Manual test 1: the original preview request

In web chat, ask:

> Prepare a Calendar event titled NinjaRobot manual test for today, from 15:00 to
> 16:00 in Asia/Tokyo. Show me the preview first.

If those times have already passed, choose a suitable future date for the test.
Expected: the robot retrieves the system date as needed and shows an exact
Calendar preview with an explicit date, `+09:00` offset, and Asia/Tokyo. It asks
for CONFIRM or CANCEL. It should not say that the preview itself sent a write
request to Google. Check Google Calendar: no new event should exist yet.

If model arguments are incomplete, expect a clear field error or a corrected
preview, not a claim that the account is disconnected. Do not proceed until the
visible date, times, account and title are exactly what you intend.

## Manual test 2: create with one word

This step creates a real event. Only proceed if you approve the displayed preview.
In the same chat, type:

```text
CONFIRM
```

Expected: a verified result and exactly one matching event in Google Calendar.
You should not need operation IDs, review hashes or JSON commands. Type CONFIRM
again: expect “No current Calendar preview,” with no duplicate event.

If the result is uncertain, do not prepare a replacement event. Check the saved
operation and Google Calendar first; the response includes recovery guidance.
Remove your test event in Google Calendar when you are finished.

## Manual test 3: cancel and expiry

1. Ask for another preview, then reply CANCEL. Expect no Google write. A subsequent
   CONFIRM must not create the cancelled event.
2. Ask for a preview, wait more than five minutes, then reply CONFIRM. Expect a
   refusal and a request for a fresh preview, with no event created.
3. Ask for a preview, send `/help`, then reply CONFIRM. The intervening message
   discards the shortcut; a new preview is required.
4. Ask for a preview in one chat, then send CONFIRM from a different terminal or
   browser chat. It must not approve the original chat's pending event.
5. Repeat the ordinary preview → CONFIRM test in terminal chat as well as web
   chat. Both use the same runtime confirmation implementation.

## Validation record

| Check | Result |
| --- | --- |
| Full regression suite | 956 passed in 41.99 seconds; one existing Starlette warning |
| Focused information/chat tests | 18 passed |
| Ruff lint and formatting | Pass; 452 files |
| mypy | Pass; 114 source files |
| Python compilation | Pass |
| Driver integrity / workspace sources | Pass; no managed driver changes; all six use this checkout |

Automated tests use fake model/Google responses and temporary databases. They
cover the missing timezone and correction, a natural model-tool conversation,
preview delivery, simple and duplicate confirmation, cancellation, expiry,
changed user, different session, changed account revision, superseded previews,
and uncertain results. Actual Google acceptance remains a manual test.

No camera/microphone capture, motor movement, power-off, or boot changes are
required. Existing device smoke tests remain optional and separate from this
account/interaction repair. Do not energize hardware just to test Calendar writes.

## Rollback

Stop the Agent and restore this patch's runtime files and matching public-source
manifest, then restart. Preserve private credentials, user data and Google events.
The previous explicit confirmation command remains supported. Rolling back code
cannot undo a real Calendar event; delete only your intended test event directly
in Google Calendar.

Full manual sources are now in the `2026-09-17-02` folders and are marked
unpublished by runtime project help. Registered source originals and the wiki
map remain unchanged. Perform wiki ingestion/review only after manual acceptance.


The new single-word shortcut applies to event creation. Existing event updates
and cancellations retain their explicit reviewed confirmation interface; no
additional write operation was enabled by this refinement.
