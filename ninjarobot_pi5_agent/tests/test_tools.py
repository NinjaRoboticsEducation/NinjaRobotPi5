from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from ninjarobot_pi5_ide.testing import FakeIDEClient

from ninjarobot_pi5_agent import (
    CancellationToken,
    IDEToolProvider,
    ProviderHealth,
    ProviderHealthStatus,
    ToolCall,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
    ToolRegistry,
    ToolRegistryError,
    ToolTrust,
)
from ninjarobot_pi5_ide import CapabilityDescriptor, RetrySafety, RiskLevel


def descriptor(
    name: str = "distance.read",
    *,
    risk: RiskLevel = RiskLevel.READ_ONLY,
    cancellable: bool = True,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name=name,
        version="1.0.0",
        description="Test capability.",
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={"type": "object"},
        risk=risk,
        resources=("test",),
        default_timeout_seconds=1.0,
        idempotent=True,
        cancellable=cancellable,
        confirmation_required=False,
    )


def test_ide_provider_namespaces_and_executes_capabilities() -> None:
    async def exercise() -> None:
        ide = FakeIDEClient((descriptor(),))
        provider = IDEToolProvider(ide)
        registry = ToolRegistry((provider,))
        await registry.start()

        assert [tool.name for tool in registry.list_tools()] == ["robot.distance.read"]
        invocation = ToolInvocation(
            call=ToolCall(
                call_id="call-1",
                name="robot.distance.read",
                arguments={},
            ),
            session_id="session-1",
        )

        result = await registry.call(invocation)

        assert result.status is ToolExecutionStatus.SUCCEEDED
        assert result.action_id == "agent-call-1"
        assert ide.requests[0].capability == "distance.read"
        assert ide.requests[0].session_id == "session-1"
        await registry.close()
        assert ide.closed

    asyncio.run(exercise())


def test_ide_provider_can_delegate_selected_capabilities() -> None:
    async def exercise() -> None:
        ide = FakeIDEClient((descriptor(), descriptor("behavior.preview")))
        provider = IDEToolProvider(
            ide,
            excluded_capabilities={"behavior.preview"},
        )
        await provider.start()

        assert [tool.name for tool in await provider.list_tools()] == ["robot.distance.read"]
        await provider.close()

    asyncio.run(exercise())


class _StaticProvider:
    def __init__(
        self,
        provider_id: str,
        definitions: tuple[ToolDefinition, ...],
        *,
        delay_seconds: float = 0,
    ) -> None:
        self._provider_id = provider_id
        self._definitions = definitions
        self._delay_seconds = delay_seconds
        self.closed = False

    @property
    def provider_id(self) -> str:
        return self._provider_id

    async def start(self) -> None:
        return None

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        return self._definitions

    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult:
        del cancellation
        if self._delay_seconds:
            await asyncio.sleep(self._delay_seconds)
        return ToolExecutionResult(
            call_id=invocation.call.call_id,
            tool_name=invocation.call.name,
            status=ToolExecutionStatus.SUCCEEDED,
            data={"ok": True},
            retry_safety=RetrySafety.SAFE,
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self._provider_id,
            status=ProviderHealthStatus.READY,
            checked_at=datetime(2026, 7, 28, tzinfo=UTC),
        )

    async def close(self) -> None:
        self.closed = True


def external_tool(
    name: str = "mcp.tavily.tavily-search",
    *,
    risk: RiskLevel = RiskLevel.READ_ONLY,
    timeout: float = 1.0,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        version="1.0.0",
        description="Search public web content.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk=risk,
        default_timeout_seconds=timeout,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
        source="tavily",
        trust=ToolTrust.EXTERNAL_UNTRUSTED,
    )


def test_registry_rejects_collisions_and_unsafe_external_tools() -> None:
    async def exercise() -> None:
        first = _StaticProvider("first", (external_tool(),))
        duplicate = _StaticProvider("duplicate", (external_tool(),))
        registry = ToolRegistry((first, duplicate))

        with pytest.raises(ToolRegistryError, match="duplicate tool name"):
            await registry.start()
        assert first.closed
        assert duplicate.closed

        unsafe = _StaticProvider(
            "unsafe",
            (external_tool(risk=RiskLevel.MOTION),),
        )
        registry = ToolRegistry((unsafe,))
        with pytest.raises(ToolRegistryError, match="must be read-only"):
            await registry.start()
        assert unsafe.closed

    asyncio.run(exercise())


def test_registry_returns_conservative_timeout_result() -> None:
    async def exercise() -> None:
        definition = external_tool(timeout=0.01)
        provider = _StaticProvider("slow", (definition,), delay_seconds=0.1)
        registry = ToolRegistry((provider,))
        await registry.start()
        invocation = ToolInvocation(
            call=ToolCall(call_id="call-1", name=definition.name, arguments={}),
            session_id="session-1",
        )

        result = await registry.call(invocation)

        assert result.status is ToolExecutionStatus.TIMED_OUT
        assert not result.definitely_not_executed
        assert result.retry_safety is RetrySafety.UNKNOWN
        await registry.close()

    asyncio.run(exercise())


def test_registry_keeps_running_when_optional_provider_is_unavailable() -> None:
    class _UnavailableProvider(_StaticProvider):
        async def start(self) -> None:
            raise RuntimeError("network unavailable")

    async def exercise() -> None:
        optional = _UnavailableProvider("mcp-optional", (external_tool(),))
        registry = ToolRegistry(
            (optional,),
            optional_provider_ids={"mcp-optional"},
        )

        await registry.start()

        assert registry.list_tools() == ()
        health = await registry.health()
        assert health[0].status is ProviderHealthStatus.UNAVAILABLE
        assert "RuntimeError" in (health[0].detail or "")
        await registry.close()

    asyncio.run(exercise())
