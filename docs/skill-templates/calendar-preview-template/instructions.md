# Calendar preview

Use calendar.connections to identify the user's authorized calendar, and
calendar.list_events for a bounded interval with an explicit time zone.
Prepare calendar.propose_change only for the user's requested exact change.
Show account, calendar, content, version and expiration. A preview is not a write.
The runtime displays the saved create/update/delete preview. Ask the user to reply
CONFIRM as a standalone message in that same chat, or CANCEL to discard it.
Never ask for operation IDs, hashes or /info calendar.confirm. This skill has no
confirmation tool. An edit shows existing and proposed details; deletion explicitly
identifies the event being removed.
Do not edit attendees, recurring events or events created outside this connection.
