# Calendar preview error and simple CONFIRM workflow

Status: approved and implemented. See [walkthrough](calendar_confirm_walkthrough_260917.md).

## Confirmed cause

Five saved `calendar.propose_change` calls failed local JSON-schema validation
(the check that tool arguments contain the required fields). Each supplied title,
start and end, but omitted `event.timezone`. The owner's prompt did supply
Asia/Tokyo; the model failed to carry it into the tool request.

The connection is enabled and write-enabled, and a calendar list request
succeeded. The failed create-preview calls never reached Google: creating a
preview is local. `InformationProvider.call` catches the schema validator's
exception and substitutes “Source unavailable” for exceptions outside its small
allowlist. That concealed the missing field and encouraged repeated identical
calls and an incorrect claim about Google write connectivity.

Only relevant tool metadata, validation structure, and connection flags were
inspected. No events were written, no credentials changed, and no service was
restarted. A successful read is not proof of a successful future Google write.

## Implementation phase 1: useful, accurate argument errors

- In `information_tools.py`, handle schema errors separately, including nested
  optional-object validation. Return bounded structured field paths, missing
  fields, and expected types; do not dump argument values, secrets, or full schemas.
- Mark validation-before-dispatch failures as definitely not executed. Distinguish
  missing arguments, read-only grants, revoked authorization, provider errors,
  and local failures. Do not label all errors as source unavailability.
- Improve Calendar tool/prompt guidance: carry the user's named time zone into
  `event.timezone`, obtain the current system date for “today,” and provide full
  start/end timestamps with matching offsets. If necessary information is absent,
  ask for it instead of guessing. Retain strict input validation.
- Permit correction of invalid preview arguments; do not automatically retry a
  Calendar write or broaden account permissions.

Tests: reproduce the exact missing-timezone call using fake services; verify a
clear field error with no preview or network dispatch, followed by successful
preview creation once corrected. Keep invalid-date and wrong-offset rejection.

## Implementation phase 2: preview, then CONFIRM

- Always render a deterministic Calendar preview from the saved local operation:
  action, account/calendar, title, start/end, time zone, and any supplied location
  or description. Tell the user: “Reply CONFIRM to create this event, or CANCEL
  to discard this preview.” The model cannot replace this exact reviewed content.
- Keep operation ID and review hash internal for the normal chat flow. Preserve
  the existing `/info calendar.confirm` interface for compatibility.
- Associate one current preview with the initiating chat session and active local
  user. Bind it to the saved operation revision/hash and Calendar connection.
  A new preview supersedes the prior pending confirmation. Multiple drafts must
  not create an ambiguous confirmation target.
- Intercept a whole-message CONFIRM directly in Agent runtime, before model
  inference. Trim whitespace and allow case-insensitive spelling; quoted text,
  a tool result, or a sentence containing CONFIRM is not approval.
- Submit through the existing trusted `information_action`/Calendar confirmation
  path. The existing five-minute expiry, user/session ownership, account revision,
  duplicate prevention, and uncertain-result reconciliation remain authoritative.
- Only enable confirmation after the exact preview was delivered. Invalidate it
  on failed/cancelled delivery, active-user change, superseding requests, and
  service restart. If there is no current valid preview, do not write anything.
- Consume pending confirmation before dispatch and guard concurrent confirmations.
  Repeated CONFIRM must not create a duplicate. An uncertain result is reported
  with recovery guidance, not an automatic second write.
- Keep terminal and web chat on the same deterministic implementation. No changes
  to hardware, external MCP write permissions, or Google authorization are needed.

Tests: preview delivery, exact CONFIRM, CANCEL, unrelated replies, missing/expired
preview, stale account revision, user/session isolation, restart/cancellation,
concurrent/double confirmation, and uncertain Google responses. Use fake Google
services and temporary databases; do not create real events automatically.

## Validation and documentation

Run the required lint, formatting, type, compilation, driver integrity/source and
full regression gates. Add end-to-end simulated chat tests so direct service-unit
coverage cannot miss another model-tool argument or confirmation routing defect.

Update README, new full manual versions, project-help runtime source references,
and the walkthrough once implementation is complete. Replace the manual ID/hash
copying procedure with preview → CONFIRM. Clearly separate software validation
from the owner's later real Google Calendar test.

Wiki impact: new source manuals and runtime public-source hashes are needed, but
wiki ingestion and review remain deferred under the owner's standing instruction.
Registered originals and the wiki map must remain unchanged. Leave the running
service unchanged unless the owner authorizes loading the update.
