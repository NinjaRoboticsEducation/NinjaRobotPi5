# System time and reminder scheduling fix

The reminder scheduler already used the Pi clock, but the model had no current
clock in its context and no tool for reading it. That allowed an incorrect date
or time to be guessed before a reminder was proposed.

## Implementation and compatibility

Every model turn now receives a fresh trusted `system_time` snapshot, containing
UTC (the common worldwide time reference), local time, calendar date, weekday,
OS timezone and current offset. The `system.time.get` read-only tool can request
another snapshot. `/time` reads the same clock directly without a model call.

The snapshot reads the host clock and `/etc/localtime`, the OS timezone file,
on every request. It is not cached when the Agent starts. Clock corrections,
midnight, timezone changes and daylight-saving changes therefore appear on the
next read. A process `TZ` override does not replace the Pi's OS timezone. If the
regional timezone cannot be identified, the Agent must ask for one before
scheduling rather than invent it. A missing timezone file is explicitly reported
and the snapshot falls back to UTC.

No clock-setting permission, background clock service, network dependency, driver
change or scheduling API change was added. Existing preview, explicit confirmation,
future-time validation, task ownership and delivery rules remain in force.
Access to the current time does not authorize creating a reminder.

This follows the existing refinement's bounded task-query design: fix model
context and read-only capabilities, then validate scheduling and update documents.
Changes are confined to the Agent's clock/provider modules, prompt composition,
runtime `/time` control, shared help and provider registration.

## Step-by-step manual test

1. Keep the robot stationary. Restart the Agent through its existing management
   method to load the new code. If startup behavior could move your robot, raise
   its wheels first. Do not start a second Agent or change its boot configuration.
2. In a Pi terminal, inspect the actual clock:

   ```bash
   date --iso-8601=seconds
   timedatectl show --property=Timezone --property=NTPSynchronized
   ```

   Expected: the intended timezone and current time. During implementation this
   Pi reported `Timezone=Asia/Tokyo` and `NTPSynchronized=yes`. These are observed
   setup facts, not a guarantee that network synchronization remains available.
3. Open chat with the running service:

   ```bash
   uv run --frozen --no-sync ninjarobot-agent chat
   ```

4. Enter this in chat, not the Linux shell:

   ```text
   /time
   ```

   Expected: local date/time with its UTC offset and `Asia/Tokyo` on this Pi.
   Compare with `date` from step 2; allow the seconds spent switching terminals.
   Repeat after a minute. The result must advance without restarting the Agent.
   This command also works in web chat and does not require the model provider.
5. Ask: “What is the current time on this Raspberry Pi?” Expected: the answer uses
   the current clock snapshot or `system.time.get`, not a remembered timestamp or
   a claim that system time is inaccessible. Model response latency may add seconds.
6. Ask: “Remind me in five minutes to check the kettle.” Expected: a preview with
   an explicit date, local time, timezone, message and task ID approximately five
   minutes after the clock read. Review it before confirming; the model's response
   does not itself schedule the reminder.
7. If the preview is correct, enter `/tasks confirm ID`, replacing `ID` with the
   returned task ID. Then use `/tasks` and ask for scheduled tasks. Expected: the
   same due time and task ID. If it is wrong, do not confirm; report the preview
   and `/time` output, without private conversation history.
8. Cancel the test with `/tasks cancel ID`, or leave the Pi and Agent running to
   verify delivery. Only approve an audible/display notification if you want that
   physical effect. A silent local inbox reminder is sufficient for this test.

Do not change the real OS clock just to test daylight saving or date boundaries:
automated tests cover those cases using synthetic dates and temporary timezone
links. If the Pi clock itself is wrong, this feature will accurately report that
wrong OS clock; it does not secretly reconfigure system time or network time sync.

## Validation and documentation impact

Focused tests cover midnight, fresh reads, OS timezone changes, daylight-saving
transitions, ignoring process timezone overrides, missing timezone information,
read-only tool validation/cancellation, direct `/time`, prompt refresh and offsets
accepted by the existing reminder validator. Final main suite: **796 passed** in 32.27 seconds. Lint, formatting
(420 Python files), type checking (98 source files), compilation, both driver
verifiers and `git diff --check` passed. All 148 local links across seven current
documents resolved. The existing Starlette/HTTPX test-client deprecation warning
remains; no new warning or driver change was introduced. No hardware actions or task creation on this Pi are used
by these tests.

Current manuals have new source revisions under `raw/.../2026-09-12-02/` and both
READMEs identify them as pending ingestion. The owner's ingested/reviewed
`2026-09-12/` originals and document map remain unchanged. No wiki ingestion,
semantic review or fingerprint refresh was performed for this fix.

Rollback: revert this reviewed Agent change and restart through the usual service
owner. No OS time settings, user task records, hardware drivers or boot files need
to be restored. There are no actuator-moving, camera/microphone or power-off tests
for this change.
