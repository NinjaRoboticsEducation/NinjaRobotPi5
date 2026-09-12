"""Model-facing local task reads and proposals; no model confirmation endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaError

from ninjarobot_pi5_ide import RiskLevel

from .models import (
    ProviderHealth,
    ProviderHealthStatus,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
)
from .task_controls import ScopeResolver, TaskControls
from .task_service import TaskService
from .tools import CancellationToken


class TaskToolProvider:
    provider_id = "local-tasks"

    def __init__(self, service: TaskService, scope: ScopeResolver) -> None:
        self._service = service
        self._scope = scope
        self._controls = TaskControls(service, scope)
        self._definitions = (
            ToolDefinition(
                name="tasks.list",
                version="1.0.0",
                description="Read a compact page of the active user's tasks. Use status=scheduled "
                "for scheduled reminders. Report task_id and title. Fetch next_after only "
                "when needed; do not combine every page into one response.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                        "after": {"type": "string", "maxLength": 150},
                        "kind": {"enum": ["all", "reminder", "request"]},
                        "status": {
                            "enum": [
                                "all",
                                "scheduled",
                                "draft",
                                "queued",
                                "running",
                                "completed",
                                "failed",
                                "cancelled",
                                "missed",
                                "uncertain",
                            ]
                        },
                    },
                },
                output_schema={"type": "object"},
                risk=RiskLevel.READ_ONLY,
                default_timeout_seconds=5.0,
                idempotent=True,
                cancellable=True,
                confirmation_required=False,
                source=self.provider_id,
            ),
            ToolDefinition(
                name="tasks.reminder.preview",
                version="1.0.0",
                description="Propose an exact local reminder; this does NOT schedule it. "
                "Ask for a missing date/time zone. Show the returned review unchanged. "
                "Only the user's direct /tasks confirm command can schedule the reviewed effect. "
                "No calendar account, phone call or model is required after confirmation.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string", "minLength": 1, "maxLength": 160},
                        "due_at": {
                            "type": "string",
                            "description": "ISO timestamp with UTC offset",
                        },
                        "timezone": {"type": "string", "description": "IANA zone, e.g. Asia/Tokyo"},
                        "repeat": {"enum": ["none", "daily", "weekly"]},
                        "notification_language": {"type": "string", "enum": ["en", "zh"]},
                        "notification": {
                            "enum": ["text", "display_buzzer", "speech"],
                            "description": "text means a silent local task inbox notice; "
                            "display_buzzer means a short screen message and buzzer tone",
                        },
                    },
                    "required": ["title", "due_at", "timezone"],
                },
                output_schema={"type": "object"},
                risk=RiskLevel.LOW,
                default_timeout_seconds=5.0,
                idempotent=False,
                cancellable=True,
                confirmation_required=False,
                source=self.provider_id,
            ),
        )

    async def start(self) -> None:
        pass  # AgentRuntime owns the database/worker lifecycle.

    async def close(self) -> None:
        pass

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        return self._definitions

    async def health(self) -> ProviderHealth:
        state = self._service.status()
        return ProviderHealth(
            provider=self.provider_id,
            status=ProviderHealthStatus.READY
            if state["running"] and state["error"] is None
            else ProviderHealthStatus.DEGRADED,
            checked_at=datetime.now(UTC),
            detail="Local reminders use no model or external account.",
        )

    async def call(
        self, invocation: ToolInvocation, cancellation: CancellationToken
    ) -> ToolExecutionResult:
        call = invocation.call
        if cancellation.cancelled:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.CANCELLED,
                error="Cancelled before local task access.",
                definitely_not_executed=True,
            )
        definition = next((item for item in self._definitions if item.name == call.name), None)
        if definition is None:
            raise KeyError("unknown local task tool")
        try:
            Draft202012Validator(definition.input_schema).validate(call.arguments)
            if call.name == "tasks.list":
                scope, _ = await self._scope(invocation.session_id)
                data = await self._service.model_page(scope, **call.arguments)
            else:
                data = await self._controls.preview(invocation.session_id, call.arguments)
        except SchemaError:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.FAILED,
                error="Invalid task arguments. Check the tool schema. "
                "For reminders use title, due_at, "
                "timezone, repeat and notification. Ask the user for missing details.",
                definitely_not_executed=True,
            )
        except (ValueError, TypeError, KeyError) as error:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.FAILED,
                error=("Task request rejected: " + str(error))[:1000],
                definitely_not_executed=True,
            )
        return ToolExecutionResult(
            call_id=call.call_id,
            tool_name=call.name,
            status=ToolExecutionStatus.SUCCEEDED,
            data=data,
        )
