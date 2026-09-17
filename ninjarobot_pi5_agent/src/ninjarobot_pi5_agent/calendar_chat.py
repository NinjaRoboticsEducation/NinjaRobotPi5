"""Ephemeral, session-bound approval of exactly delivered Calendar previews."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent_loop import AgentReply
    from .runtime import AgentRuntime


class CalendarChat:
    def __init__(self) -> None:
        self.drafts: dict[str, tuple[str, str]] = {}
        self.pending: dict[str, tuple[str, str, str]] = {}
        self.generation: dict[str, int] = {}

    def clear(self, session: str) -> None:
        self.generation[session] = self.generation.get(session, 0) + 1
        self.drafts.pop(session, None)
        self.pending.pop(session, None)

    async def capture(self, runtime: AgentRuntime, session: str, result: dict[str, Any]) -> None:
        self.clear(session)
        if (
            runtime.information is None
            or result.get("kind") != "calendar_operation"
            or result.get("payload", {}).get("action") != "create"
        ):
            return
        self.drafts[session] = (await runtime.information.user(session), result["record_id"])

    async def deliver(self, runtime: AgentRuntime, session: str, callback: Any) -> str:
        draft = self.drafts.pop(session, None)
        if draft is None or runtime.information is None:
            return ""
        user, ident = draft
        generation = self.generation.get(session, 0)
        if user != await runtime.information.user(session):
            return ""
        record = await runtime.information.store.action(user, "get", record_id=ident)
        data = record["payload"]
        if data["state"] != "pending" or data["session"] != session:
            return ""
        body = data["body"]
        start, end = body.get("start", {}), body.get("end", {})
        text = (
            "\n\nCalendar preview — nothing has been sent to Google.\n"
            f"Action: {data['action']}\nAccount: {data['account_label']}\n"
            f"Calendar: {data['calendar_id']}\nTitle: {body.get('summary', '(existing event)')}\n"
            f"Start: {start.get('dateTime', start.get('date', 'unchanged'))}\n"
            f"End: {end.get('dateTime', end.get('date', 'unchanged'))}\n"
            f"Time zone: {start.get('timeZone', 'all-day calendar date')}\n"
            f"Location: {body.get('location', '')}\nDescription: {body.get('description', '')}\n"
            "Reply CONFIRM to apply this exact change, or CANCEL to discard this preview. "
            f"Expires: {data['expires_at']}. Any other message discards this confirmation."
        )
        await runtime._identity_reply(session, text, on_text_delta=callback)
        # Enable only after delivery; failed/cancelled streams never arm a write.
        if user == await runtime.information.user(session) and generation == self.generation.get(
            session, 0
        ):
            self.pending[session] = (user, ident, data["review_hash"])
        return text

    async def respond(
        self, runtime: AgentRuntime, session: str, word: str, callback: Any, cancellation: Any
    ) -> AgentReply:
        from .information_controls import information_action

        selected = self.pending.pop(session, None)
        self.drafts.pop(session, None)
        text = "No current Calendar preview is available. Ask for a new preview first."
        if selected and runtime.information is not None:
            user, ident, review_hash = selected
            if user != await runtime.information.user(session):
                text = "The local user changed. Ask for a new Calendar preview."
            elif word == "CANCEL":
                await information_action(
                    runtime,
                    session,
                    {
                        "operation": "calendar.cancel",
                        "arguments": {"operation_id": ident},
                    },
                    cancellation,
                )
                text = "Calendar confirmation discarded. No event was sent to Google."
            else:
                try:
                    result = await information_action(
                        runtime,
                        session,
                        {
                            "operation": "calendar.confirm",
                            "confirmed": True,
                            "arguments": {"operation_id": ident, "review_hash": review_hash},
                        },
                        cancellation,
                    )
                    state = result.get("payload", result).get("state")
                    text = (
                        "Calendar change verified in Google Calendar."
                        if state == "verified"
                        else "Calendar result is uncertain. Do not repeat the creation; inspect "
                        f"the saved operation {ident} before taking further action."
                    )
                except (ValueError, KeyError, PermissionError) as exc:
                    text = (
                        f"Calendar confirmation refused: {str(exc)[:400]}. Request a new preview."
                    )
        return await runtime._identity_reply(session, text, on_text_delta=callback, user_text=word)
