"""MCP connections normalized as isolated read-only tool providers."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from ninjarobot_pi5_ide import RetrySafety, RiskLevel

from .mcp_config import (
    MCPAuthentication,
    MCPServerConfig,
    MCPTransport,
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
from .secrets import SecretStore
from .tools import CancellationToken


class MCPProtocolError(RuntimeError):
    """Raised for malformed, disallowed, or oversized MCP responses."""


class MCPUnavailableError(RuntimeError):
    """Raised when an MCP connection cannot be initialized."""


class MCPToolDescription(Protocol):
    """Minimum discovered tool surface used by the provider."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class MCPConnection(Protocol):
    """Transport-independent normalized MCP connection."""

    async def start(self) -> None:
        """Initialize protocol negotiation."""

    async def list_tools(self) -> tuple[MCPToolDescription, ...]:
        """Return all currently discovered tools."""

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call one server tool and return JSON-compatible content."""

    async def close(self) -> None:
        """Release streams, sessions, and child processes."""


class _DiscoveredTool:
    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.output_schema = output_schema


class SDKMCPConnection:
    """Official Python SDK transport wrapper with deterministic cleanup."""

    def __init__(self, config: MCPServerConfig, secret_store: SecretStore) -> None:
        self._config = config
        self._secret_store = secret_store
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._started = False
        self._closed = False

    async def start(self) -> None:
        """Connect using direct argv or HTTPS with a protected bearer header."""
        if self._closed:
            raise RuntimeError("MCP connection is closed")
        if self._started:
            return
        await self._stack.__aenter__()
        try:
            if self._config.transport is MCPTransport.STDIO:
                environment = os.environ.copy()
                for target, source in self._config.environment_variables.items():
                    environment[target] = self._secret_store.require(source)
                parameters = StdioServerParameters(
                    command=cast(str, self._config.command),
                    args=list(self._config.args),
                    env=environment,
                )
                streams = await self._stack.enter_async_context(stdio_client(parameters))
            else:
                headers: dict[str, str] = {}
                if self._config.authentication is MCPAuthentication.BEARER_ENVIRONMENT:
                    token_name = cast(str, self._config.token_environment)
                    headers["Authorization"] = f"Bearer {self._secret_store.require(token_name)}"
                http_client = await self._stack.enter_async_context(
                    httpx.AsyncClient(
                        headers=headers,
                        timeout=self._config.timeout_seconds,
                        follow_redirects=False,
                    )
                )
                streams = await self._stack.enter_async_context(
                    streamable_http_client(
                        cast(str, self._config.url),
                        http_client=http_client,
                    )
                )
            read_stream, write_stream = streams[0], streams[1]
            session = await self._stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=self._config.timeout_seconds),
                )
            )
            await session.initialize()
            self._session = session
            self._started = True
        except BaseException as exc:
            await self._stack.aclose()
            raise MCPUnavailableError(
                f"MCP server '{self._config.id}' could not initialize: {type(exc).__name__}"
            ) from exc

    async def list_tools(self) -> tuple[MCPToolDescription, ...]:
        """Discover every page and normalize SDK models."""
        session = self._require_session()
        discovered: list[MCPToolDescription] = []
        cursor: str | None = None
        while True:
            result = await session.list_tools(cursor=cursor)
            for tool in result.tools:
                discovered.append(
                    _DiscoveredTool(
                        name=tool.name,
                        description=tool.description or f"MCP tool {tool.name}.",
                        input_schema=dict(tool.inputSchema),
                        output_schema=(
                            dict(tool.outputSchema)
                            if tool.outputSchema is not None
                            else {"type": "object"}
                        ),
                    )
                )
            cursor = result.nextCursor
            if cursor is None:
                return tuple(discovered)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call through the SDK and convert the entire result to JSON data."""
        result = await self._require_session().call_tool(name, arguments)
        payload = result.model_dump(mode="json", by_alias=True)
        if not isinstance(payload, dict):
            raise MCPProtocolError("MCP call result was not an object")
        return payload

    async def close(self) -> None:
        """Close the full async context stack once."""
        if self._closed:
            return
        self._closed = True
        await self._stack.aclose()

    def _require_session(self) -> ClientSession:
        if self._closed:
            raise RuntimeError("MCP connection is closed")
        if not self._started or self._session is None:
            raise RuntimeError("MCP connection is not started")
        return self._session


ConnectionFactory = Callable[[MCPServerConfig, SecretStore], MCPConnection]


class MCPToolProvider:
    """Expose one allowlisted MCP server through an untrusted namespace."""

    def __init__(
        self,
        config: MCPServerConfig,
        secret_store: SecretStore,
        *,
        connection_factory: ConnectionFactory = SDKMCPConnection,
    ) -> None:
        self._config = config
        self._secret_store = secret_store
        self._connection = connection_factory(config, secret_store)
        self._definitions: dict[str, ToolDefinition] = {}
        self._raw_names: dict[str, str] = {}
        self._started = False
        self._closed = False
        self._last_error: str | None = None

    @property
    def provider_id(self) -> str:
        """Return the configured ID, not self-reported server metadata."""
        return f"mcp-{self._config.id}"

    async def start(self) -> None:
        """Connect and expose only explicitly allowlisted tools."""
        if self._closed:
            raise RuntimeError("MCP provider is closed")
        if self._started:
            return
        if not self._config.enabled:
            raise MCPUnavailableError(f"MCP server '{self._config.id}' is disabled")
        try:
            await self._connection.start()
            discovered = {tool.name: tool for tool in await self._connection.list_tools()}
            missing = sorted(set(self._config.allowed_tools) - discovered.keys())
            if missing:
                raise MCPProtocolError(
                    f"MCP server '{self._config.id}' is missing allowed tools: {', '.join(missing)}"
                )
            for raw_name in self._config.allowed_tools:
                tool = discovered[raw_name]
                name = f"mcp.{self._config.id}.{self._public_tool_name(raw_name)}"
                self._definitions[name] = ToolDefinition(
                    name=name,
                    version="1.0.0",
                    description=tool.description,
                    input_schema=tool.input_schema,
                    output_schema=tool.output_schema,
                    risk=RiskLevel.READ_ONLY,
                    default_timeout_seconds=self._config.timeout_seconds,
                    idempotent=True,
                    cancellable=True,
                    confirmation_required=False,
                    source=self.provider_id,
                    trust=ToolTrust.EXTERNAL_UNTRUSTED,
                )
                self._raw_names[name] = raw_name
            self._started = True
        except BaseException as exc:
            self._last_error = type(exc).__name__
            await self._connection.close()
            raise

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        """Return the stable allowlisted catalog."""
        self._ensure_started()
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    async def refresh(self) -> tuple[ToolDefinition, ...]:
        """Rediscover tools without expanding the configured allowlist."""
        self._ensure_started()
        discovered = {tool.name: tool for tool in await self._connection.list_tools()}
        missing = sorted(set(self._config.allowed_tools) - discovered.keys())
        if missing:
            raise MCPProtocolError(f"MCP allowlisted tools disappeared: {', '.join(missing)}")
        return await self.list_tools()

    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult:
        """Call one allowlisted tool with result-size and cancellation controls."""
        self._ensure_started()
        try:
            raw_name = self._raw_names[invocation.call.name]
        except KeyError as exc:
            raise KeyError(f"unknown MCP tool: {invocation.call.name}") from exc
        arguments = self._arguments(raw_name, invocation.call.arguments)
        call_task = asyncio.create_task(self._connection.call_tool(raw_name, arguments))
        cancel_task = asyncio.create_task(cancellation.wait())
        try:
            done, _ = await asyncio.wait(
                {call_task, cancel_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_task in done and not call_task.done():
                call_task.cancel()
                await asyncio.gather(call_task, return_exceptions=True)
                return ToolExecutionResult(
                    call_id=invocation.call.call_id,
                    tool_name=invocation.call.name,
                    status=ToolExecutionStatus.CANCELLED,
                    error="The MCP tool call was cancelled.",
                    retry_safety=RetrySafety.UNKNOWN,
                )
            payload = await call_task
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if len(encoded) > self._config.max_result_bytes:
                raise MCPProtocolError(f"MCP result exceeded {self._config.max_result_bytes} bytes")
            return ToolExecutionResult(
                call_id=invocation.call.call_id,
                tool_name=invocation.call.name,
                status=ToolExecutionStatus.SUCCEEDED,
                data={"external_untrusted_content": payload},
                retry_safety=RetrySafety.SAFE,
            )
        except asyncio.CancelledError:
            call_task.cancel()
            await asyncio.gather(call_task, return_exceptions=True)
            raise
        except Exception as exc:
            self._last_error = type(exc).__name__
            return ToolExecutionResult(
                call_id=invocation.call.call_id,
                tool_name=invocation.call.name,
                status=ToolExecutionStatus.FAILED,
                error=f"MCP tool failed: {type(exc).__name__}",
                definitely_not_executed=False,
                retry_safety=RetrySafety.UNKNOWN,
            )
        finally:
            cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)

    async def health(self) -> ProviderHealth:
        """Return connection health without exposing credentials or URLs."""
        status = (
            ProviderHealthStatus.READY
            if self._started and not self._closed
            else ProviderHealthStatus.UNAVAILABLE
        )
        detail = (
            f"{len(self._definitions)} allowlisted tool(s) available."
            if status is ProviderHealthStatus.READY
            else f"Unavailable ({self._last_error or 'not started'})."
        )
        return ProviderHealth(
            provider=self.provider_id,
            status=status,
            checked_at=datetime.now(UTC),
            detail=detail,
        )

    async def close(self) -> None:
        """Close the isolated server connection once."""
        if self._closed:
            return
        self._closed = True
        await self._connection.close()

    def inspect(self) -> dict[str, Any]:
        """Return redacted configuration and catalog metadata."""
        return {
            "configuration": self._config.redacted_dict(),
            "tools": sorted(self._definitions),
            "status": "ready" if self._started and not self._closed else "unavailable",
        }

    def _arguments(self, raw_name: str, supplied: dict[str, Any]) -> dict[str, Any]:
        arguments = {**self._config.default_parameters, **supplied}
        if self._config.preset == "tavily" and raw_name == "tavily_search":
            arguments["search_depth"] = "basic"
            requested_results = arguments.get("max_results", 5)
            if not isinstance(requested_results, int) or isinstance(requested_results, bool):
                raise ValueError("Tavily max_results must be an integer")
            arguments["max_results"] = max(1, min(requested_results, 5))
            arguments["include_images"] = False
            arguments["include_raw_content"] = False
        return arguments

    def _public_tool_name(self, raw_name: str) -> str:
        """Keep the existing agent-facing Tavily name while its server name evolves."""
        if self._config.preset == "tavily" and raw_name == "tavily_search":
            return "tavily-search"
        return raw_name

    def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("MCP provider is closed")
        if not self._started:
            raise RuntimeError("MCP provider is not started")
