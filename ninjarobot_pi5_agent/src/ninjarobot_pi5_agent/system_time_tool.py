"""Read-only access to the clock on the machine running the Agent."""

from datetime import UTC, datetime

from ninjarobot_pi5_ide import RiskLevel

from .models import (
    ProviderHealth,
    ProviderHealthStatus,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
)
from .system_time import system_time_snapshot
from .tools import CancellationToken


class SystemTimeProvider:
    provider_id = "system-time"

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.provider_id,
            status=ProviderHealthStatus.READY,
            checked_at=datetime.now(UTC),
            detail="Local system clock",
        )

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        return (
            ToolDefinition(
                name="system.time.get",
                version="1.0.0",
                description="Read the current date, time, UTC offset and OS timezone on the Pi. "
                "Use for current-time questions and before interpreting relative reminder times. "
                "This never changes the clock or schedules a task.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {},
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
        if call.name != "system.time.get":
            raise KeyError("unknown system time tool")
        if cancellation.cancelled:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.CANCELLED,
                error="Clock read cancelled.",
                definitely_not_executed=True,
            )
        if call.arguments:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.FAILED,
                error="system.time.get accepts no arguments.",
                definitely_not_executed=True,
            )
        return ToolExecutionResult(
            call_id=call.call_id,
            tool_name=call.name,
            status=ToolExecutionStatus.SUCCEEDED,
            data=system_time_snapshot(),
        )
