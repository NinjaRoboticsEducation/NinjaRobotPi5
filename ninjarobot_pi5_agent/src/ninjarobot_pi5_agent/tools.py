"""Unified agent tool registry and the sole robot-to-IDE bridge."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Protocol

from ninjarobot_pi5_ide import (
    ActionRequest,
    ActionResult,
    ActionStatus,
    IDEClient,
    RetrySafety,
)

from .models import (
    ProviderHealth,
    ProviderHealthStatus,
    ToolCall,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
    ToolTrust,
)


class ToolRegistryError(RuntimeError):
    """Raised when providers expose an unsafe or ambiguous tool catalog."""


class CancellationToken:
    """Cooperative cancellation signal shared across agent tool layers."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()

    def cancel(self) -> None:
        """Request cancellation; repeated requests are harmless."""
        self._event.set()

    async def wait(self) -> None:
        """Wait until cancellation is requested."""
        await self._event.wait()


class ToolProvider(Protocol):
    """Lifecycle and execution surface implemented by every tool source."""

    @property
    def provider_id(self) -> str:
        """Return the stable provider identifier."""

    async def start(self) -> None:
        """Acquire provider resources."""

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        """Return the current validated tool catalog."""

    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult:
        """Execute one invocation and return a terminal result."""

    async def health(self) -> ProviderHealth:
        """Return a side-effect-free provider health report."""

    async def close(self) -> None:
        """Release resources idempotently."""


class IDEToolProvider:
    """Expose IDE capabilities without importing any managed hardware library."""

    def __init__(
        self,
        ide: IDEClient,
        *,
        provider_id: str = "ide",
        excluded_capabilities: Iterable[str] = (),
    ) -> None:
        self._ide = ide
        self._provider_id = provider_id
        self._excluded_capabilities = frozenset(excluded_capabilities)
        self._definitions: dict[str, ToolDefinition] = {}
        self._capability_names: dict[str, str] = {}
        self._started = False
        self._closed = False

    @property
    def provider_id(self) -> str:
        """Return the stable provider identifier."""
        return self._provider_id

    async def start(self) -> None:
        """Start the IDE and snapshot its capability catalog."""
        if self._closed:
            raise RuntimeError("IDE tool provider is closed")
        if self._started:
            return
        await self._ide.start()
        descriptors = await self._ide.capabilities()
        definitions: dict[str, ToolDefinition] = {}
        capability_names: dict[str, str] = {}
        for descriptor in descriptors:
            if descriptor.name in self._excluded_capabilities:
                continue
            tool_name = f"robot.{descriptor.name}"
            definitions[tool_name] = ToolDefinition(
                name=tool_name,
                version=descriptor.version,
                description=descriptor.description,
                input_schema=descriptor.input_schema,
                output_schema=descriptor.output_schema,
                risk=descriptor.risk,
                default_timeout_seconds=descriptor.default_timeout_seconds,
                idempotent=descriptor.idempotent,
                cancellable=descriptor.cancellable,
                confirmation_required=descriptor.confirmation_required,
                source=self._provider_id,
                trust=ToolTrust.TRUSTED,
            )
            capability_names[tool_name] = descriptor.name
        self._definitions = definitions
        self._capability_names = capability_names
        self._started = True

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        """Return IDE capabilities with the reserved ``robot`` namespace."""
        self._ensure_started()
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult:
        """Execute through ``IDEClient`` and preserve IDE retry evidence."""
        self._ensure_started()
        call = invocation.call
        try:
            capability = self._capability_names[call.name]
            definition = self._definitions[call.name]
        except KeyError as exc:
            raise KeyError(f"unknown IDE tool: {call.name}") from exc

        action_id = f"agent-{call.call_id}"
        request = ActionRequest(
            action_id=action_id,
            capability=capability,
            arguments=call.arguments,
            requested_by=invocation.requested_by,
            session_id=invocation.session_id,
            idempotency_key=call.call_id,
        )
        execute_task = asyncio.create_task(self._ide.execute(request))
        cancel_task = asyncio.create_task(cancellation.wait())
        try:
            done, _ = await asyncio.wait(
                {execute_task, cancel_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_task in done and not execute_task.done():
                if not definition.cancellable:
                    result = await execute_task
                else:
                    result = await self._ide.cancel(action_id)
                    execute_task.cancel()
                    await asyncio.gather(execute_task, return_exceptions=True)
            else:
                result = await execute_task
            return _normalize_ide_result(call, result)
        except asyncio.CancelledError:
            if definition.cancellable and not execute_task.done():
                await self._ide.cancel(action_id)
            execute_task.cancel()
            await asyncio.gather(execute_task, return_exceptions=True)
            raise
        finally:
            cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)

    async def health(self) -> ProviderHealth:
        """Map the IDE health snapshot without executing robot actions."""
        self._ensure_started()
        report = await self._ide.health()
        if report.status.value == "ready":
            status = ProviderHealthStatus.READY
        elif report.status.value == "unavailable":
            status = ProviderHealthStatus.UNAVAILABLE
        else:
            status = ProviderHealthStatus.DEGRADED
        return ProviderHealth(
            provider=self._provider_id,
            status=status,
            checked_at=report.checked_at,
            detail=report.detail,
        )

    async def close(self) -> None:
        """Close the owned IDE client once."""
        if self._closed:
            return
        self._closed = True
        if self._started:
            await self._ide.close()

    def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("IDE tool provider is closed")
        if not self._started:
            raise RuntimeError("IDE tool provider is not started")


class ToolRegistry:
    """Own providers, reject name collisions, and enforce call timeouts."""

    def __init__(
        self,
        providers: Iterable[ToolProvider],
        *,
        optional_provider_ids: set[str] | None = None,
    ) -> None:
        self._providers = tuple(providers)
        self._optional_provider_ids = frozenset(optional_provider_ids or set())
        self._tools: dict[str, ToolDefinition] = {}
        self._tool_providers: dict[str, ToolProvider] = {}
        self._provider_start_errors: dict[str, ProviderHealth] = {}
        self._started = False
        self._closed = False

    async def start(self) -> None:
        """Start all providers transactionally and build one tool catalog."""
        if self._closed:
            raise RuntimeError("tool registry is closed")
        if self._started:
            return
        started: list[ToolProvider] = []
        try:
            for provider in self._providers:
                try:
                    await provider.start()
                except Exception as exc:
                    if provider.provider_id not in self._optional_provider_ids:
                        raise
                    self._provider_start_errors[provider.provider_id] = unavailable_provider_health(
                        provider.provider_id,
                        f"Optional provider unavailable ({type(exc).__name__}).",
                    )
                    continue
                started.append(provider)
                for definition in await provider.list_tools():
                    if definition.name in self._tools:
                        raise ToolRegistryError(f"duplicate tool name exposed: {definition.name}")
                    if (
                        definition.trust is ToolTrust.EXTERNAL_UNTRUSTED
                        and definition.risk.value != "read_only"
                    ):
                        raise ToolRegistryError(
                            f"external tool must be read-only: {definition.name}"
                        )
                    self._tools[definition.name] = definition
                    self._tool_providers[definition.name] = provider
        except BaseException:
            for provider in reversed(started):
                await provider.close()
            self._tools.clear()
            self._tool_providers.clear()
            self._provider_start_errors.clear()
            raise
        self._started = True

    def list_tools(self) -> tuple[ToolDefinition, ...]:
        """Return a stable alphabetical catalog."""
        self._ensure_started()
        return tuple(self._tools[name] for name in sorted(self._tools))

    def get(self, name: str) -> ToolDefinition:
        """Return one tool definition or raise a clear unknown-tool error."""
        self._ensure_started()
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken | None = None,
    ) -> ToolExecutionResult:
        """Call the owning provider with the catalog timeout."""
        self._ensure_started()
        definition = self.get(invocation.call.name)
        provider = self._tool_providers[definition.name]
        token = cancellation or CancellationToken()
        try:
            async with asyncio.timeout(definition.default_timeout_seconds):
                return await provider.call(invocation, token)
        except TimeoutError:
            token.cancel()
            return ToolExecutionResult(
                call_id=invocation.call.call_id,
                tool_name=definition.name,
                status=ToolExecutionStatus.TIMED_OUT,
                error="The tool exceeded its configured timeout.",
                definitely_not_executed=False,
                retry_safety=RetrySafety.UNKNOWN,
            )

    async def health(self) -> tuple[ProviderHealth, ...]:
        """Return every provider health report."""
        self._ensure_started()
        reports: list[ProviderHealth] = []
        for provider in self._providers:
            failed = self._provider_start_errors.get(provider.provider_id)
            reports.append(failed if failed is not None else await provider.health())
        return tuple(reports)

    async def close(self) -> None:
        """Close providers in reverse order; repeated calls are safe."""
        if self._closed:
            return
        self._closed = True
        for provider in reversed(self._providers):
            await provider.close()

    def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("tool registry is closed")
        if not self._started:
            raise RuntimeError("tool registry is not started")


def _normalize_ide_result(call: ToolCall, result: ActionResult) -> ToolExecutionResult:
    status_map = {
        ActionStatus.SUCCEEDED: ToolExecutionStatus.SUCCEEDED,
        ActionStatus.CANCELLED: ToolExecutionStatus.CANCELLED,
        ActionStatus.FAILED: ToolExecutionStatus.FAILED,
        ActionStatus.REJECTED: ToolExecutionStatus.DENIED,
    }
    status = status_map.get(result.status, ToolExecutionStatus.FAILED)
    error = result.error.message if result.error is not None else None
    if error is None and status is not ToolExecutionStatus.SUCCEEDED:
        error = f"IDE returned non-terminal action status: {result.status.value}"
    return ToolExecutionResult(
        call_id=call.call_id,
        tool_name=call.name,
        status=status,
        data=result.data,
        error=error,
        definitely_not_executed=(
            result.error.definitely_not_executed if result.error is not None else False
        ),
        retry_safety=result.retry_safety,
        action_id=result.action_id,
    )


def unavailable_provider_health(provider_id: str, detail: str) -> ProviderHealth:
    """Build a timestamped unavailable report for provider startup failures."""
    return ProviderHealth(
        provider=provider_id,
        status=ProviderHealthStatus.UNAVAILABLE,
        checked_at=datetime.now(UTC),
        detail=detail,
    )
