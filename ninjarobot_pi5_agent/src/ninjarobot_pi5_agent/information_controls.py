"""Direct controller authority, policy checks and ordinary task receipts."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from ninjarobot_pi5_ide import RiskLevel

from .models import ToolDefinition
from .policy import PolicyContext
from .task_models import TaskStatus, TaskStep
from .tools import CancellationToken

if TYPE_CHECKING:
    from .runtime import AgentRuntime


async def information_action(
    runtime: AgentRuntime,
    session: str,
    payload: dict[str, Any],
    cancellation: CancellationToken | None = None,
) -> dict[str, Any]:
    from .runtime import CURRENT_TASK

    runtime._ensure_started()
    provider = runtime.information
    if provider is None or runtime.tasks is None:
        raise ValueError("information services unavailable")
    if (
        set(payload) - {"operation", "arguments", "confirmed"}
        or len(json.dumps(payload).encode()) > 50000
    ):
        raise ValueError("invalid or oversized information request")
    operation = payload.get("operation")
    arguments = payload.get("arguments", {})
    if not isinstance(operation, str) or not isinstance(arguments, dict):
        raise ValueError("operation and object arguments are required")
    definition = ToolDefinition(
        name="information.controller",
        version="1.0.0",
        description="Direct reviewed information operation",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk=RiskLevel.LOW,
        default_timeout_seconds=40,
        idempotent=False,
        cancellable=True,
        source="local-information",
        confirmation_required=operation
        in {"notes.confirm", "calendar.confirm", "calendar.connect", "calendar.disconnect"},
    )
    decision = runtime.policy.evaluate(
        definition, PolicyContext(session_id=session, confirmed=payload.get("confirmed") is True)
    )
    if not decision.allowed:
        raise PermissionError(decision.reason)
    if len(runtime._recipe_workers) >= 4:
        raise ValueError("local controls busy; retry when current work finishes")
    scope, user = await runtime.task_scope(session)
    await provider.user(session)
    runtime._begin_operation()
    worker = asyncio.current_task()
    assert worker is not None
    tracked = worker in runtime._recipe_workers
    runtime._recipe_workers.add(worker)
    cancel = cancellation or CancellationToken()
    task = None
    token = None
    status = TaskStatus.FAILED
    speech_watcher = None
    try:
        task = await runtime.tasks.begin_request(
            scope=scope,
            user_id=user,
            session_id=session,
            title=f"Information: {operation}",
            limits={"max_tool_calls": 3, "timeout_seconds": 40},
        )
        runtime._recipe_requests[task.task_id] = cancel
        token = CURRENT_TASK.set(task)
        seconds = min(40.0, float(runtime.loop.execution_limits()["request_seconds"]))
        async with asyncio.timeout(seconds):
            data = await provider.action(session, operation, arguments, cancel, trusted=True)
            if (
                operation == "briefing.build"
                and runtime.speech is not None
                and runtime.speech.enabled
            ):

                async def stop_speech_on_cancel() -> None:
                    await cancel.wait()
                    worker.cancel()

                speech_watcher = asyncio.create_task(stop_speech_on_cancel())
                async with runtime._chat_lock:
                    if await runtime.task_scope(session) != (scope, user) or cancel.cancelled:
                        raise ValueError("active user changed or briefing was cancelled")
                    data["speech"] = await runtime.speech.speak(data["spoken_summary"])
        if await runtime.task_scope(session) != (scope, user):
            raise ValueError("active user changed; private result withheld")
        state = data.get("state", data.get("payload", {}).get("state"))
        status = TaskStatus.UNCERTAIN if state == "uncertain" else TaskStatus.COMPLETED
        await runtime.tasks.record_request(
            scope,
            task.task_id,
            step=TaskStep(
                description=operation,
                status=status,
                evidence="Review the owned information record for the exact result; no "
                "credentials stored in this receipt.",
            ),
        )
        return {"task_id": task.task_id, **data}
    except asyncio.CancelledError:
        cancel.cancel()
        status = (
            TaskStatus.UNCERTAIN
            if operation in {"calendar.confirm", "notes.confirm"}
            else TaskStatus.CANCELLED
        )
        raise
    except Exception:
        if operation in {"calendar.confirm", "notes.confirm"}:
            status = TaskStatus.UNCERTAIN
        raise
    finally:
        if speech_watcher is not None:
            speech_watcher.cancel()
            await asyncio.gather(speech_watcher, return_exceptions=True)
        if token is not None:
            CURRENT_TASK.reset(token)
        try:
            if task is not None:
                runtime._recipe_requests.pop(task.task_id, None)
                await runtime.tasks.record_request(scope, task.task_id, status=status)
        finally:
            if not tracked:
                runtime._recipe_workers.discard(worker)
            runtime._end_operation()
