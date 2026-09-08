"""Shared, deterministic task controls for chat and controller interfaces."""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .task_models import LocalTask, TaskStatus
from .task_service import TaskService

ScopeResolver = Callable[[str], Awaitable[tuple[str, str | None]]]


def task_summary(task: LocalTask) -> str:
    if task.kind == "request":
        steps = "\n".join(
            f"- {step.description}: {step.status.value}; {step.evidence}"
            for step in task.steps[-8:]
        )
        return f"{task.task_id}: {task.status.value}\nRequest: {task.title}\n{steps}\n{task.result}"
    due = task.due_at.astimezone(ZoneInfo(task.timezone)).isoformat()
    effect = (
        "save a notice in the local task inbox (no sound or display)"
        if task.notification == "text"
        else "show the message on the robot and play a short buzzer tone"
    )
    summary = (
        f"{task.task_id}: {task.status.value}\nMessage: {task.title}\n"
        f"Due: {due} [{task.timezone}]\nRepeat: {task.repeat}\nEffect: {effect}."
    )
    if task.status is TaskStatus.DRAFT:
        summary += (
            f"\nNot scheduled yet. To approve exactly this, type /tasks confirm {task.task_id}"
        )
    if task.result:
        summary += f"\nResult: {task.result}"
    return summary


class TaskControls:
    def __init__(
        self,
        service: TaskService,
        scope: ScopeResolver,
        cancel_request: Callable[[LocalTask], None] | None = None,
    ) -> None:
        self.service = service
        self.scope = scope
        self._cancel_request = cancel_request

    async def preview(self, session_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        scope, user_id = await self.scope(session_id)
        task = await self.service.preview(
            scope=scope, user_id=user_id, session_id=session_id, **arguments
        )
        return {"task": task.model_dump(mode="json"), "review": task_summary(task)}

    async def list(self, session_id: str) -> dict[str, Any]:
        scope, _ = await self.scope(session_id)
        return {"tasks": [item.model_dump(mode="json") for item in await self.service.list(scope)]}

    async def command(self, session_id: str, text: str) -> str | None:
        """Direct user commands work even when the selected model is offline."""
        if not text.startswith(("/tasks", "/remind")):
            return None
        try:
            parts = shlex.split(text)
            if parts[0] == "/tasks":
                scope, _ = await self.scope(session_id)
                if len(parts) == 1:
                    items = await self.service.list(scope)
                    summaries: list[str] = []
                    for item in items:
                        summary = task_summary(item)
                        if sum(map(len, summaries)) + len(summary) > 15_000:
                            summaries.append(
                                "More records are available through the task list tool."
                            )
                            break
                        summaries.append(summary)
                    return "\n\n".join(summaries) or "No saved local tasks."
                if len(parts) in {3, 4} and parts[1] in {"confirm", "cancel", "snooze"}:
                    if len(parts) == 4 and parts[1] != "snooze":
                        raise ValueError("only snooze accepts a minute count")
                    item = await self.service.change(
                        scope, parts[2], parts[1], minutes=int(parts[3]) if len(parts) == 4 else 5
                    )
                    if item.kind == "request" and parts[1] == "cancel" and self._cancel_request:
                        self._cancel_request(item)
                    return task_summary(item)
            elif parts[0] == "/remind" and len(parts) >= 3:
                if not re.fullmatch(r"[0-9]{1,7}", parts[1]) or not 10 <= int(parts[1]) <= 86400:
                    raise ValueError("timer length must be 10 through 86400 seconds")
                arguments = {
                    "title": " ".join(parts[2:]),
                    "due_at": (datetime.now(UTC) + timedelta(seconds=int(parts[1]))).isoformat(),
                    "timezone": "UTC",
                    "notification": "text",
                }
                return str((await self.preview(session_id, arguments))["review"])
            elif parts[0] == "/remind-json":
                # JSON preserves exact strings, zone, recurrence and notification effect.
                arguments = json.loads(text[len("/remind-json") :].strip())
                if not isinstance(arguments, dict):
                    raise ValueError("reminder specification must be a JSON object")
                allowed = {"title", "due_at", "timezone", "repeat", "notification"}
                if (
                    not {"title", "due_at", "timezone"} <= arguments.keys()
                    or arguments.keys() - allowed
                ):
                    raise ValueError(
                        "provide title, due_at, timezone and optional repeat/notification"
                    )
                return str((await self.preview(session_id, arguments))["review"])
            return (
                "Use /remind SECONDS MESSAGE for a silent local inbox reminder, /tasks to list, "
                "/tasks confirm ID, /tasks cancel ID, or /tasks snooze ID MINUTES. "
                "For an exact date, time zone, repeat rule or display/buzzer effect, use "
                '/remind-json {"title":"Tea","due_at":"2026-09-09T16:00:00+09:00",'
                '"timezone":"Asia/Tokyo","repeat":"none","notification":"text"}. '
                "Replace the example date with your intended date. Preview first, then confirm."
            )
        except (ValueError, TypeError, KeyError) as error:
            return f"Reminder not changed: {error}"
