"""Direct user recipe controls through current runtime policy and task receipts."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator

from .models import ToolExecutionStatus
from .recipes import Recipe, RecipeStore, resolve_arguments, review
from .task_models import TaskStatus, TaskStep
from .tools import CancellationToken

if TYPE_CHECKING:
    from .runtime import AgentRuntime


async def recipe_action(
    runtime: AgentRuntime,
    session_id: str,
    payload: dict[str, Any],
    cancellation: CancellationToken | None = None,
) -> dict[str, Any]:
    runtime._ensure_started()
    if len(runtime._recipe_workers) >= 4:
        raise ValueError("recipe controls are busy; retry after current work finishes")
    worker = asyncio.current_task()
    assert worker is not None
    runtime._begin_operation()
    already_tracked = worker in runtime._recipe_workers
    runtime._recipe_workers.add(worker)
    try:
        return await _recipe_action(runtime, session_id, payload, cancellation)
    finally:
        if not already_tracked:
            runtime._recipe_workers.discard(worker)
        runtime._end_operation()


async def _recipe_action(
    runtime: AgentRuntime,
    session_id: str,
    payload: dict[str, Any],
    cancellation: CancellationToken | None = None,
) -> dict[str, Any]:
    from .runtime import CURRENT_TASK

    runtime._ensure_started()
    if runtime.tasks is None:
        raise ValueError("local tasks are unavailable")
    allowed = {"operation", "recipe", "recipe_id", "version", "review_hash", "inputs", "confirmed"}
    if set(payload) - allowed or len(json.dumps(payload).encode()) > 20000:
        raise ValueError("invalid or oversized recipe request")
    operation = payload.get("operation", "list")
    recipe_id = payload.get("recipe_id", "")
    version = payload.get("version", 0)
    if not isinstance(recipe_id, str) or type(version) is not int or version < 0:
        raise ValueError("invalid recipe identifier/version")
    if operation not in {
        "list",
        "show",
        "preview",
        "save",
        "run",
        "enable",
        "disable",
        "delete",
        "rollback",
    }:
        raise ValueError("unknown recipe operation")
    scope, user_id = await runtime.task_scope(session_id)
    store = RecipeStore(runtime.store.path)
    if operation in {"preview", "save"}:
        recipe = Recipe.model_validate_json(json.dumps(payload.get("recipe")))
        preview = review(recipe, runtime.tools.list_tools())
        receipts = {task.task_id: task for task in await runtime.tasks.list(scope)}
        for task_id in recipe.source_task_ids:
            task = receipts.get(task_id)
            if task is None or task.kind != "request" or task.status is not TaskStatus.COMPLETED:
                raise ValueError("source receipts must be owned successful requests")
            if any(step.status is not TaskStatus.COMPLETED for step in task.steps):
                raise ValueError("source receipt contains an unproven result")
        if operation == "preview":
            return preview
        if payload.get("review_hash") != preview["review_hash"]:
            raise ValueError("save requires the exact preview review_hash")
        return await store.action(scope, user_id, "save", version=version, preview=preview)
    if operation in {"delete", "rollback", "run"} and payload.get("confirmed") is not True:
        raise PermissionError("this direct recipe operation requires explicit confirmation")
    if operation == "run" and version < 1:
        raise ValueError("run requires an explicit saved version")
    if operation != "run":
        return await store.action(scope, user_id, operation, recipe_id=recipe_id, version=version)
    saved = await store.action(scope, user_id, "show", recipe_id=recipe_id, version=version)
    if not saved["enabled"]:
        raise ValueError("recipe is disabled")
    recipe = Recipe.model_validate_json(json.dumps(saved["recipe"]))
    if review(recipe, runtime.tools.list_tools())["review_hash"] != saved["review_hash"]:
        raise ValueError("tool contracts changed; preview and save a new version")
    inputs = payload.get("inputs", {})
    if not isinstance(inputs, dict):
        raise ValueError("recipe inputs must be an object")
    resolve_arguments(recipe, recipe.steps[0], inputs, [])
    limits = runtime.loop.execution_limits()
    if len(recipe.steps) > int(limits["tool_attempts_including_retries"]):
        raise ValueError("recipe exceeds the current task tool budget")
    seconds = min(recipe.max_seconds, float(limits["request_seconds"]))
    task = await runtime.tasks.begin_request(
        scope=scope,
        user_id=user_id,
        session_id=session_id,
        title=f"Recipe {recipe.id} v{version}: {recipe.name}",
        limits={"max_tool_calls": len(recipe.steps), "timeout_seconds": seconds},
    )
    cancel = cancellation or CancellationToken()
    runtime._recipe_requests[task.task_id] = cancel
    token = CURRENT_TASK.set(task)
    status = TaskStatus.COMPLETED
    results: list[dict[str, Any]] = []
    public_results: list[dict[str, Any]] = []
    try:
        async with asyncio.timeout(seconds):
            for step in recipe.steps:
                if cancel.cancelled:
                    status = TaskStatus.CANCELLED
                    break
                if await runtime.task_scope(session_id) != (scope, user_id):
                    raise ValueError("active user changed; run stopped")
                current = await store.action(
                    scope, user_id, "show", recipe_id=recipe_id, version=version
                )
                if (
                    not current["enabled"]
                    or current["review_hash"] != saved["review_hash"]
                    or current.get("saved_id") != saved.get("saved_id")
                ):
                    raise ValueError("recipe was disabled; later steps stopped")
                if (
                    review(recipe, runtime.tools.list_tools())["review_hash"]
                    != saved["review_hash"]
                ):
                    raise ValueError("tool contracts changed during the run")
                arguments = resolve_arguments(recipe, step, inputs, results)
                Draft202012Validator(runtime.tools.get(step.tool).input_schema).validate(arguments)
                result = await runtime.execute_tool(
                    tool_name=step.tool,
                    arguments=arguments,
                    session_id=session_id,
                    requested_by="reviewed-recipe",
                    cancellation=cancel,
                )
                public_results.append(
                    {
                        "tool": step.tool,
                        "status": result.status.value,
                        "result": json.dumps(result.data, ensure_ascii=False)[:1200],
                    }
                )
                if result.status is not ToolExecutionStatus.SUCCEEDED:
                    status = TaskStatus.CANCELLED if cancel.cancelled else TaskStatus.FAILED
                    break
                results.append(result.data or {})
    except asyncio.CancelledError:
        cancel.cancel()
        status = TaskStatus.CANCELLED
        raise
    except Exception as exc:
        cancel.cancel()
        status = TaskStatus.FAILED
        await runtime.tasks.record_request(
            scope,
            task.task_id,
            step=TaskStep(
                description="Recipe stopped before subsequent steps",
                status=status,
                evidence=str(exc)[:1000],
            ),
        )
        public_results.append({"error": str(exc)[:500]})
    finally:
        await runtime.tasks.record_request(scope, task.task_id, status=status)
        runtime._recipe_requests.pop(task.task_id, None)
        CURRENT_TASK.reset(token)
    recorded = next(
        (item for item in await runtime.tasks.list(scope) if item.task_id == task.task_id), None
    )
    if recorded is not None:
        status = recorded.status
    return {
        "recipe_id": recipe_id,
        "version": version,
        "task_id": task.task_id,
        "status": status.value,
        "results": public_results,
        "note": "No automatic retries, continuation or reversal. See /tasks for receipts.",
    }
