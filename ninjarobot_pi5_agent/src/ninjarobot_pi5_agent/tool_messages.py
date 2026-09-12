"""Bound model-facing tool data without changing recorded execution outcomes."""

from __future__ import annotations

import json

from .models import MessageRole, ModelMessage, ToolExecutionResult


def tool_message_content(result: ToolExecutionResult) -> str:
    """Keep valid JSON and outcome metadata; never suggest replaying an effect.

    The execution ledger retains the original result. Providers should return
    compact projections; this is a final guard for unexpectedly large tool data.
    """
    record = result.model_dump(mode="json")
    content = json.dumps(record, sort_keys=True, ensure_ascii=False)
    if len(content) <= 20_000:
        return content
    record["data"] = {
        "omitted": True,
        "reason": "Tool data exceeded the model message budget.",
        "guidance": "Execution status above is unchanged. Do not repeat an action "
        "to recover output. Use a narrower read-only query or ask the user.",
    }
    return json.dumps(record, sort_keys=True, ensure_ascii=False)


def repair_tool_history(messages: tuple[ModelMessage, ...]) -> tuple[ModelMessage, ...]:
    """Repair interrupted provider context only; never edit history or replay tools.

    A crash after a tool effect but before its result was stored leaves an open
    call. Explicit uncertainty closes that call for providers requiring matched
    pairs, without claiming that the action failed or did not execute.
    """
    repaired: list[ModelMessage] = []
    pending: dict[str, str] = {}

    def finish_pending() -> None:
        for call_id, name in pending.items():
            repaired.append(
                ModelMessage(
                    role=MessageRole.TOOL,
                    name=name,
                    tool_call_id=call_id,
                    content=json.dumps(
                        {
                            "status": "outcome_unavailable",
                            "notice": "The previous turn ended without a stored tool result. "
                            "The action may have executed. Do not repeat it to recover output. "
                            "Use a read-only status check or ask the user before another action.",
                        }
                    ),
                )
            )
        pending.clear()

    for message in messages:
        if message.role is MessageRole.TOOL:
            if message.tool_call_id in pending:
                repaired.append(message)
                del pending[message.tool_call_id]
            else:
                repaired.append(
                    ModelMessage(
                        role=MessageRole.ASSISTANT,
                        content="An old tool result has no matching request in this context. "
                        "Its outcome must not be inferred or used to repeat an action.",
                    )
                )
        else:
            finish_pending()
            repaired.append(message)
            if message.tool_calls:
                pending.update((call.call_id, call.name) for call in message.tool_calls)
    finish_pending()
    return tuple(repaired)
