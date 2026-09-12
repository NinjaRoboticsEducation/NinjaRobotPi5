"""Model-readable command documentation with no device or configuration access."""

from datetime import UTC, datetime

from ninjarobot_pi5_ide import RiskLevel

from .command_help import help_text
from .models import (
    ProviderHealth,
    ProviderHealthStatus,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
)
from .tools import CancellationToken


class CommandHelpProvider:
    provider_id = "command-help"

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.provider_id,
            status=ProviderHealthStatus.READY,
            checked_at=datetime.now(UTC),
            detail="Local command reference",
        )

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        return (
            ToolDefinition(
                name="command_help.search",
                version="1.0.0",
                description="Read instructions for robot functions and slash commands. "
                "This tool cannot execute commands or change settings.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"query": {"type": "string", "maxLength": 500}},
                },
                output_schema={"type": "object"},
                risk=RiskLevel.READ_ONLY,
                default_timeout_seconds=5.0,
                idempotent=True,
                cancellable=True,
                confirmation_required=False,
                source=self.provider_id,
            ),
        )

    async def call(
        self, invocation: ToolInvocation, cancellation: CancellationToken
    ) -> ToolExecutionResult:
        call = invocation.call
        if call.name != "command_help.search":
            raise KeyError("unknown command help tool")
        if cancellation.cancelled:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.CANCELLED,
                error="Help cancelled.",
                definitely_not_executed=True,
            )
        query = call.arguments.get("query", "")
        if set(call.arguments) - {"query"} or not isinstance(query, str) or len(query) > 500:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.FAILED,
                error="Provide a query of at most 500 characters.",
                definitely_not_executed=True,
            )
        return ToolExecutionResult(
            call_id=call.call_id,
            tool_name=call.name,
            status=ToolExecutionStatus.SUCCEEDED,
            data={"instructions": help_text(query), "executed": False},
        )
