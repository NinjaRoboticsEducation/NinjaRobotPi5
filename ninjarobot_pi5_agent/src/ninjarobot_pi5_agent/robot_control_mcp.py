"""Trusted in-process MCP façade for deterministic NinjaRobot behaviors."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

from ninjarobot_pi5_ide import (
    ActionRequest,
    ActionResult,
    CapabilityDescriptor,
    IDEClient,
    RetrySafety,
)

from .models import (
    ProviderHealth,
    ProviderHealthStatus,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
    ToolTrust,
)
from .tools import CancellationToken, _normalize_ide_result

ROBOT_CONTROL_PROVIDER_ID = "robot-control-mcp"
ROBOT_CONTROL_DELEGATED_CAPABILITIES = frozenset(
    {
        "behavior.preview",
        "behavior.execute_expression",
        "behavior.execute_movement",
        "behavior.stop",
    }
)
_MAX_ERROR_LENGTH = 1900
_RAW_TO_PUBLIC = {
    "behavior_catalog": "robot.behavior.catalog",
    "behavior_preview": "robot.behavior.preview",
    "behavior_execute_expression": "robot.behavior.execute_expression",
    "behavior_execute_movement": "robot.behavior.execute_movement",
    "stop_robot": "robot.behavior.stop",
}
_RAW_TO_CAPABILITY = {
    "behavior_catalog": "behavior.list",
    "behavior_preview": "behavior.preview",
    "behavior_execute_expression": "behavior.execute_expression",
    "behavior_execute_movement": "behavior.execute_movement",
    "stop_robot": "behavior.stop",
}


class _ActionEnvelope(BaseModel):
    """Structured MCP output carrying the IDE's authoritative action result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: ActionResult


@dataclass(frozen=True, slots=True)
class _RobotCallContext:
    invocation: ToolInvocation


_CALL_CONTEXT: ContextVar[_RobotCallContext | None] = ContextVar(
    "ninjarobot_robot_mcp_call",
    default=None,
)


class _RobotControlBridge:
    """Execute MCP handlers only through one service-owned IDE client."""

    def __init__(
        self,
        ide: IDEClient,
        descriptors: dict[str, CapabilityDescriptor],
    ) -> None:
        self._ide = ide
        self._descriptors = descriptors

    async def execute(self, capability: str, arguments: dict[str, Any]) -> _ActionEnvelope:
        context = _CALL_CONTEXT.get()
        if context is None:
            raise RuntimeError("robot-control MCP call is missing trusted session context")
        invocation = context.invocation
        descriptor = self._descriptors[capability]
        action_id = f"agent-{invocation.call.call_id}"
        request = ActionRequest(
            action_id=action_id,
            capability=capability,
            arguments=arguments,
            requested_by=invocation.requested_by,
            session_id=invocation.session_id,
            idempotency_key=invocation.call.call_id,
        )
        try:
            result = await self._ide.execute(request)
        except asyncio.CancelledError:
            if descriptor.cancellable:
                await asyncio.shield(self._ide.cancel(action_id))
            raise
        return _ActionEnvelope(action=result)


def _create_server(bridge: _RobotControlBridge) -> FastMCP[None]:
    """Create the fixed built-in MCP catalog; no user server metadata is trusted."""
    server: FastMCP[None] = FastMCP(
        "NinjaRobot Control",
        instructions=(
            "Compile and execute bounded robot behavior stages through the NinjaRobot IDE. "
            "Never use GPIO numbers or bypass motion authorization."
        ),
    )

    @server.tool(
        name="behavior_catalog",
        description="List validated built-in and user-created robot behaviors.",
        annotations=ToolAnnotations(
            title="List robot behaviors",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def behavior_catalog(
        category: Literal["all", "expression", "movement"] = "all",
    ) -> _ActionEnvelope:
        return await bridge.execute("behavior.list", {"category": category})

    @server.tool(
        name="behavior_preview",
        description=(
            "Validate and translate a compact expression or movement into canonical IDE "
            "format without touching hardware."
        ),
        annotations=ToolAnnotations(
            title="Preview robot behavior",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def behavior_preview(
        category: Literal["expression", "movement"],
        name: str,
        description: str,
        stages: list[dict[str, Any]],
    ) -> _ActionEnvelope:
        return await bridge.execute(
            "behavior.preview",
            {
                "category": category,
                "name": name,
                "description": description,
                "stages": stages,
            },
        )

    @server.tool(
        name="behavior_execute_expression",
        description=(
            "Execute a finite validated face, text, tone, or melody composition. "
            "Stages run in order and operations in one stage begin together."
        ),
        annotations=ToolAnnotations(
            title="Execute robot expression",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def behavior_execute_expression(
        name: str,
        description: str,
        stages: list[dict[str, Any]],
    ) -> _ActionEnvelope:
        return await bridge.execute(
            "behavior.execute_expression",
            {
                "category": "expression",
                "name": name,
                "description": description,
                "stages": stages,
            },
        )

    @server.tool(
        name="behavior_execute_movement",
        description=(
            "Execute a finite validated robot movement that may combine approved faces, "
            "tones, melodies, and named movement presets. Motion authorization is required."
        ),
        annotations=ToolAnnotations(
            title="Execute robot movement",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def behavior_execute_movement(
        name: str,
        description: str,
        stages: list[dict[str, Any]],
    ) -> _ActionEnvelope:
        return await bridge.execute(
            "behavior.execute_movement",
            {
                "category": "movement",
                "name": name,
                "description": description,
                "stages": stages,
            },
        )

    @server.tool(
        name="stop_robot",
        description="Immediately perform the existing Level 2 full robot stop.",
        annotations=ToolAnnotations(
            title="Stop robot",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def stop_robot() -> _ActionEnvelope:
        return await bridge.execute("behavior.stop", {})

    return server


class RobotControlMCPProvider:
    """Expose the built-in MCP server as trusted, policy-classified agent tools."""

    def __init__(self, ide: IDEClient) -> None:
        self._ide = ide
        self._server: FastMCP[None] | None = None
        self._definitions: dict[str, ToolDefinition] = {}
        self._raw_names: dict[str, str] = {}
        self._started = False
        self._closed = False

    @property
    def provider_id(self) -> str:
        return ROBOT_CONTROL_PROVIDER_ID

    async def start(self) -> None:
        """Build and verify the fixed MCP catalog against current IDE capabilities."""
        if self._closed:
            raise RuntimeError("robot-control MCP provider is closed")
        if self._started:
            return
        await self._ide.start()
        descriptors = {item.name: item for item in await self._ide.capabilities()}
        missing = sorted(set(_RAW_TO_CAPABILITY.values()) - descriptors.keys())
        if missing:
            raise RuntimeError(
                "robot-control MCP requires missing IDE capabilities: " + ", ".join(missing)
            )
        server = _create_server(_RobotControlBridge(self._ide, descriptors))
        discovered = {tool.name: tool for tool in await server.list_tools()}
        if set(discovered) != set(_RAW_TO_PUBLIC):
            raise RuntimeError("robot-control MCP catalog does not match its fixed manifest")
        definitions: dict[str, ToolDefinition] = {}
        raw_names: dict[str, str] = {}
        for raw_name, public_name in _RAW_TO_PUBLIC.items():
            capability = _RAW_TO_CAPABILITY[raw_name]
            descriptor = descriptors[capability]
            mcp_tool = discovered[raw_name]
            definitions[public_name] = ToolDefinition(
                name=public_name,
                version=descriptor.version,
                description=mcp_tool.description or descriptor.description,
                input_schema=descriptor.input_schema,
                output_schema=descriptor.output_schema,
                risk=descriptor.risk,
                default_timeout_seconds=descriptor.default_timeout_seconds,
                idempotent=descriptor.idempotent,
                cancellable=descriptor.cancellable,
                confirmation_required=descriptor.confirmation_required,
                source=self.provider_id,
                trust=ToolTrust.TRUSTED,
            )
            raw_names[public_name] = raw_name
        self._server = server
        self._definitions = definitions
        self._raw_names = raw_names
        self._started = True

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        self._ensure_started()
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult:
        """Execute through FastMCP while carrying trusted session context out-of-band."""
        self._ensure_started()
        server = self._require_server()
        try:
            raw_name = self._raw_names[invocation.call.name]
            definition = self._definitions[invocation.call.name]
        except KeyError as exc:
            raise KeyError(f"unknown robot-control MCP tool: {invocation.call.name}") from exc
        try:
            Draft202012Validator(definition.input_schema).validate(invocation.call.arguments)
        except JSONSchemaValidationError as exc:
            return ToolExecutionResult(
                call_id=invocation.call.call_id,
                tool_name=invocation.call.name,
                status=ToolExecutionStatus.FAILED,
                error=_bounded_error(f"Robot-control MCP input validation failed: {exc.message}"),
                definitely_not_executed=True,
                retry_safety=RetrySafety.SAFE,
            )
        context_token: Token[_RobotCallContext | None] = _CALL_CONTEXT.set(
            _RobotCallContext(invocation=invocation)
        )
        call_task = asyncio.create_task(server.call_tool(raw_name, invocation.call.arguments))
        cancel_task = asyncio.create_task(cancellation.wait())
        try:
            done, _ = await asyncio.wait(
                {call_task, cancel_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_task in done and not call_task.done():
                call_task.cancel()
                outcome = (await asyncio.gather(call_task, return_exceptions=True))[0]
                if isinstance(outcome, Exception):
                    return ToolExecutionResult(
                        call_id=invocation.call.call_id,
                        tool_name=invocation.call.name,
                        status=ToolExecutionStatus.FAILED,
                        error=(
                            "Robot-control MCP cancellation could not be confirmed: "
                            f"{type(outcome).__name__}."
                        ),
                        definitely_not_executed=False,
                        retry_safety=RetrySafety.UNKNOWN,
                    )
                return ToolExecutionResult(
                    call_id=invocation.call.call_id,
                    tool_name=invocation.call.name,
                    status=ToolExecutionStatus.CANCELLED,
                    error="The robot-control MCP call was cancelled.",
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.UNKNOWN,
                )
            _content, structured = await call_task
            envelope = _ActionEnvelope.model_validate(structured, strict=False)
            return _normalize_ide_result(invocation.call, envelope.action)
        except asyncio.CancelledError:
            call_task.cancel()
            await asyncio.gather(call_task, return_exceptions=True)
            raise
        except Exception as exc:
            return ToolExecutionResult(
                call_id=invocation.call.call_id,
                tool_name=invocation.call.name,
                status=ToolExecutionStatus.FAILED,
                error=_bounded_error(
                    f"Robot-control MCP rejected the call: {type(exc).__name__}: {exc}"
                ),
                definitely_not_executed=False,
                retry_safety=RetrySafety.UNKNOWN,
            )
        finally:
            _CALL_CONTEXT.reset(context_token)
            cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)

    async def health(self) -> ProviderHealth:
        status = (
            ProviderHealthStatus.READY
            if self._started and not self._closed
            else ProviderHealthStatus.UNAVAILABLE
        )
        return ProviderHealth(
            provider=self.provider_id,
            status=status,
            checked_at=datetime.now(UTC),
            detail=(
                f"{len(self._definitions)} trusted robot-control MCP tools available."
                if status is ProviderHealthStatus.READY
                else "Robot-control MCP provider is not running."
            ),
        )

    async def close(self) -> None:
        """Release only MCP metadata; the IDE remains owned by its primary provider."""
        self._closed = True
        self._server = None
        self._definitions.clear()
        self._raw_names.clear()

    def _require_server(self) -> FastMCP[None]:
        if self._server is None:
            raise RuntimeError("robot-control MCP server is unavailable")
        return self._server

    def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("robot-control MCP provider is closed")
        if not self._started:
            raise RuntimeError("robot-control MCP provider is not started")


def _bounded_error(message: str) -> str:
    """Keep diagnostic text inside the agent result contract."""
    if len(message) <= _MAX_ERROR_LENGTH:
        return message
    return message[: _MAX_ERROR_LENGTH - 3] + "..."
