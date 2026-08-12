"""Trusted, read-only, session-scoped memory tool provider."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

from ninjarobot_pi5_ide import RetrySafety, RiskLevel

from .memory_services import MemoryRetrievalService
from .models import (
    MemoryKind,
    ProviderHealth,
    ProviderHealthStatus,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
    ToolTrust,
)
from .persistence import ConversationStore
from .tools import CancellationToken

MEMORY_MCP_PROVIDER_ID = "memory-mcp"
_RAW_TO_PUBLIC = {
    "profile_get": "memory.profile.get",
    "memory_search": "memory.search",
    "behavior_successful": "memory.behavior.successful",
    "behavior_failed": "memory.behavior.failed",
}


class _MemoryEnvelope(BaseModel):
    """Structured FastMCP output containing one bounded memory response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _MemoryCallContext:
    invocation: ToolInvocation


_CALL_CONTEXT: ContextVar[_MemoryCallContext | None] = ContextVar(
    "ninjarobot_memory_mcp_call",
    default=None,
)


class _MemoryBridge:
    """Resolve all memory reads from trusted service-owned session state."""

    def __init__(
        self,
        retrieval: MemoryRetrievalService,
        conversations: ConversationStore,
    ) -> None:
        self._retrieval = retrieval
        self._conversations = conversations

    async def profile_get(self) -> _MemoryEnvelope:
        user_id = await self._active_user()
        return _MemoryEnvelope(data=await self._retrieval.profile_payload(user_id))

    async def search(
        self,
        query: str,
        limit: int,
        kinds: list[str],
    ) -> _MemoryEnvelope:
        user_id = await self._active_user()
        parsed_kinds = tuple(MemoryKind(kind) for kind in kinds)
        return _MemoryEnvelope(
            data={
                "items": await self._retrieval.search_payload(
                    user_id,
                    query,
                    kinds=parsed_kinds,
                    limit=limit,
                )
            }
        )

    async def list_behaviors(
        self,
        kind: MemoryKind,
        limit: int,
    ) -> _MemoryEnvelope:
        user_id = await self._active_user()
        return _MemoryEnvelope(
            data={
                "items": await self._retrieval.list_payload(
                    user_id,
                    kind,
                    limit=limit,
                )
            }
        )

    async def _active_user(self) -> str:
        context = _CALL_CONTEXT.get()
        if context is None:
            raise RuntimeError("memory MCP call is missing trusted session context")
        sessions = await self._conversations.sessions()
        for session in sessions:
            if session.session_id == context.invocation.session_id:
                return session.user_id
        raise KeyError(f"unknown session: {context.invocation.session_id}")


def _create_server(bridge: _MemoryBridge) -> FastMCP[None]:
    """Create a fixed read-only catalog with no model-controlled user identity."""
    server: FastMCP[None] = FastMCP(
        "NinjaRobot Memory",
        instructions=(
            "Retrieve bounded memories for the active NinjaRobot session. "
            "This server is read-only and never accepts a user identifier."
        ),
    )
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.tool(
        name="profile_get",
        description="Read the active user's non-secret profile.",
        annotations=annotations,
    )
    async def profile_get() -> _MemoryEnvelope:
        return await bridge.profile_get()

    @server.tool(
        name="memory_search",
        description="Search bounded memories belonging to the active user.",
        annotations=annotations,
    )
    async def memory_search(
        query: str,
        limit: int = 6,
        kinds: list[str] | None = None,
    ) -> _MemoryEnvelope:
        return await bridge.search(query, limit, kinds or [])

    @server.tool(
        name="behavior_successful",
        description="List confirmed successful behaviors for the active user.",
        annotations=annotations,
    )
    async def behavior_successful(limit: int = 6) -> _MemoryEnvelope:
        return await bridge.list_behaviors(MemoryKind.SUCCESSFUL_BEHAVIOR, limit)

    @server.tool(
        name="behavior_failed",
        description="List bounded technical failures for the active user.",
        annotations=annotations,
    )
    async def behavior_failed(limit: int = 6) -> _MemoryEnvelope:
        return await bridge.list_behaviors(MemoryKind.FAILED_BEHAVIOR, limit)

    return server


class MemoryMCPProvider:
    """Expose bounded memory reads; no model-accessible mutation tools exist."""

    def __init__(
        self,
        retrieval: MemoryRetrievalService,
        conversations: ConversationStore,
    ) -> None:
        self._retrieval = retrieval
        self._conversations = conversations
        self._server: FastMCP[None] | None = None
        self._started = False
        self._closed = False
        self._definitions = _definitions()
        self._raw_names: dict[str, str] = {}

    @property
    def provider_id(self) -> str:
        return MEMORY_MCP_PROVIDER_ID

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("memory MCP provider is closed")
        if self._started:
            return
        server = _create_server(_MemoryBridge(self._retrieval, self._conversations))
        discovered = {tool.name for tool in await server.list_tools()}
        if discovered != set(_RAW_TO_PUBLIC):
            raise RuntimeError("memory MCP catalog does not match its fixed manifest")
        self._server = server
        self._raw_names = {public: raw for raw, public in _RAW_TO_PUBLIC.items()}
        self._started = True

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        self._ensure_started()
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult:
        self._ensure_started()
        if cancellation.cancelled:
            return _result(
                invocation,
                ToolExecutionStatus.CANCELLED,
                error="Memory read cancelled.",
            )
        try:
            raw_name = self._raw_names[invocation.call.name]
            definition = self._definitions[invocation.call.name]
        except KeyError:
            return _result(
                invocation,
                ToolExecutionStatus.FAILED,
                error=f"unknown memory MCP tool: {invocation.call.name}",
                definitely_not_executed=True,
            )
        try:
            Draft202012Validator(definition.input_schema).validate(invocation.call.arguments)
        except JSONSchemaValidationError as error:
            return _result(
                invocation,
                ToolExecutionStatus.FAILED,
                error=f"Memory MCP input validation failed: {error.message}",
                definitely_not_executed=True,
            )
        context_token: Token[_MemoryCallContext | None] = _CALL_CONTEXT.set(
            _MemoryCallContext(invocation=invocation)
        )
        server = self._require_server()
        call_task = asyncio.create_task(server.call_tool(raw_name, invocation.call.arguments))
        cancel_task = asyncio.create_task(cancellation.wait())
        try:
            done, _ = await asyncio.wait(
                {call_task, cancel_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_task in done and not call_task.done():
                call_task.cancel()
                await asyncio.gather(call_task, return_exceptions=True)
                return _result(
                    invocation,
                    ToolExecutionStatus.CANCELLED,
                    error="Memory MCP read cancelled.",
                )
            _content, structured = await call_task
            envelope = _MemoryEnvelope.model_validate(structured, strict=False)
            return _result(
                invocation,
                ToolExecutionStatus.SUCCEEDED,
                data=envelope.data,
            )
        except asyncio.CancelledError:
            call_task.cancel()
            await asyncio.gather(call_task, return_exceptions=True)
            raise
        except Exception as error:
            return _result(
                invocation,
                ToolExecutionStatus.FAILED,
                error=f"Memory MCP rejected the call: {type(error).__name__}: {error}",
                definitely_not_executed=True,
            )
        finally:
            _CALL_CONTEXT.reset(context_token)
            cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)

    async def health(self) -> ProviderHealth:
        ready = self._started and not self._closed
        return ProviderHealth(
            provider=self.provider_id,
            status=ProviderHealthStatus.READY if ready else ProviderHealthStatus.UNAVAILABLE,
            checked_at=datetime.now(UTC),
            detail=(
                "4 trusted, read-only, session-scoped memory tools available."
                if ready
                else "Memory MCP provider is not running."
            ),
        )

    async def close(self) -> None:
        self._closed = True
        self._server = None
        self._raw_names.clear()

    def _require_server(self) -> FastMCP[None]:
        if self._server is None:
            raise RuntimeError("memory MCP server is unavailable")
        return self._server

    def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("memory MCP provider is closed")
        if not self._started:
            raise RuntimeError("memory MCP provider is not started")


def _definitions() -> dict[str, ToolDefinition]:
    empty_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    limit_schema = {
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
        "additionalProperties": False,
    }
    search_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 500},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            "kinds": {
                "type": "array",
                "maxItems": 6,
                "uniqueItems": True,
                "items": {"type": "string", "enum": [kind.value for kind in MemoryKind]},
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    descriptions = {
        "memory.profile.get": (
            "Read the active session user's non-secret profile. Never accepts a user identifier."
        ),
        "memory.search": (
            "Search bounded memories belonging only to the active session user. Read-only."
        ),
        "memory.behavior.successful": (
            "List confirmed successful behavior memories for the active session user."
        ),
        "memory.behavior.failed": (
            "List bounded technical failure memories for the active session user."
        ),
    }
    schemas = {
        "memory.profile.get": empty_schema,
        "memory.search": search_schema,
        "memory.behavior.successful": limit_schema,
        "memory.behavior.failed": limit_schema,
    }
    return {
        name: ToolDefinition(
            name=name,
            version="1.0.0",
            description=description,
            input_schema=schemas[name],
            output_schema={"type": "object"},
            risk=RiskLevel.READ_ONLY,
            default_timeout_seconds=2.0,
            idempotent=True,
            cancellable=True,
            confirmation_required=False,
            source=MEMORY_MCP_PROVIDER_ID,
            trust=ToolTrust.TRUSTED,
        )
        for name, description in descriptions.items()
    }


def _result(
    invocation: ToolInvocation,
    status: ToolExecutionStatus,
    *,
    data: Any = None,
    error: str | None = None,
    definitely_not_executed: bool = False,
) -> ToolExecutionResult:
    return ToolExecutionResult(
        call_id=invocation.call.call_id,
        tool_name=invocation.call.name,
        status=status,
        data=data,
        error=error,
        definitely_not_executed=definitely_not_executed,
        retry_safety=RetrySafety.SAFE,
    )
