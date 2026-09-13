# Calendar preview

Use calendar.connections to identify the user's authorized calendar, and
calendar.list_events for a bounded interval with an explicit time zone.
Prepare calendar.propose_change only for the user's requested exact change.
Show account, calendar, content, version and expiration. A preview is not a write.
The user must confirm the returned operation ID/hash in the same session through
the direct calendar.confirm controller. This skill has no confirmation tool.
Do not edit attendees, recurring events or events created outside this connection.
