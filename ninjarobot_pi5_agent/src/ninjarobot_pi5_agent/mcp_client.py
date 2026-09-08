"""MCP connections normalized as isolated read-only tool providers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

import httpx
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client
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


def _validate_schema(schema: dict[str, Any]) -> None:
    """Validate locally; server schema references must never trigger network reads."""
    pending: list[tuple[Any, int]] = [(schema, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise MCPProtocolError("MCP schema nesting exceeds the supported limit")
        if isinstance(item, dict):
            for key, value in item.items():
                if key in {"$ref", "$dynamicRef"} and (
                    not isinstance(value, str) or not value.startswith("#")
                ):
                    raise MCPProtocolError("MCP schemas must use only local references")
                pending.append((value, depth + 1))
        elif isinstance(item, list):
            pending.extend((value, depth + 1) for value in item)
    Draft202012Validator.check_schema(schema)


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
                environment = get_default_environment()
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
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise MCPUnavailableError(
                f"MCP server '{self._config.id}' could not initialize: {type(exc).__name__}"
            ) from exc

    async def list_tools(self) -> tuple[MCPToolDescription, ...]:
        """Discover every page and normalize SDK models."""
        session = self._require_session()
        discovered: list[MCPToolDescription] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        names: set[str] = set()
        size = 0
        for _ in range(self._config.max_discovery_pages):
            result = await session.list_tools(cursor=cursor)
            for tool in result.tools:
                size += len(tool.model_dump_json().encode())
                if size > 1_048_576 or len(discovered) >= self._config.max_discovery_tools:
                    raise MCPProtocolError("MCP discovery exceeded its catalog limit")
                if tool.name in names:
                    raise MCPProtocolError("MCP discovery returned duplicate tool names")
                names.add(tool.name)
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
            if cursor in seen_cursors:
                raise MCPProtocolError("MCP discovery repeated a pagination cursor")
            seen_cursors.add(cursor)
        raise MCPProtocolError("MCP discovery exceeded its page limit")

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
        self._catalog_valid = False

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
            async with asyncio.timeout(self._config.timeout_seconds):
                await self._connection.start()
                await self._refresh_catalog()
            self._started = True
        except BaseException as exc:
            self._last_error = type(exc).__name__
            await self._connection.close()
            raise

    async def _refresh_catalog(self) -> None:
        """Build the full reviewed catalog before replacing the active schema set."""
        self._catalog_valid = False
        try:
            discovered: dict[str, MCPToolDescription] = {}
            total_bytes = 0
            async with asyncio.timeout(self._config.timeout_seconds):
                catalog = await self._connection.list_tools()
            for tool in catalog:
                if tool.name in discovered or len(discovered) >= self._config.max_discovery_tools:
                    raise MCPProtocolError("MCP catalog contains duplicates or too many tools")
                total_bytes += len(
                    json.dumps(
                        [tool.name, tool.description, tool.input_schema, tool.output_schema]
                    ).encode()
                )
                if total_bytes > 1_048_576:
                    raise MCPProtocolError("MCP catalog is too large")
                discovered[tool.name] = tool
            missing = sorted(set(self._config.allowed_tools) - discovered.keys())
            if missing:
                raise MCPProtocolError(
                    f"MCP server '{self._config.id}' is missing allowed tools: {', '.join(missing)}"
                )
            definitions: dict[str, ToolDefinition] = {}
            raw_names: dict[str, str] = {}
            for raw_name in self._config.allowed_tools:
                if not self._config.reviewed_read_only(raw_name):
                    continue
                tool = discovered[raw_name]
                for schema in (tool.input_schema, tool.output_schema):
                    _validate_schema(schema)
                name = f"mcp.{self._config.id}.{self._public_tool_name(raw_name)}"
                if name in definitions:
                    raise MCPProtocolError("MCP public tool names collide")
                definitions[name] = ToolDefinition(
                    name=name,
                    version="1.0.0",
                    description=tool.description[:1000] or "External tool.",
                    input_schema=tool.input_schema,
                    output_schema=tool.output_schema,
                    risk=RiskLevel.READ_ONLY,
                    default_timeout_seconds=self._config.timeout_seconds,
                    idempotent=raw_name in self._config.retry_safe_tools,
                    cancellable=True,
                    confirmation_required=False,
                    source=self.provider_id,
                    trust=ToolTrust.EXTERNAL_UNTRUSTED,
                )
                raw_names[name] = raw_name
            self._definitions, self._raw_names = definitions, raw_names
            self._catalog_valid = True
        except BaseException:
            self._definitions.clear()
            self._raw_names.clear()
            raise

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        """Return the stable allowlisted catalog."""
        self._ensure_started()
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    async def refresh(self) -> tuple[ToolDefinition, ...]:
        """Rediscover tools without expanding the configured allowlist."""
        self._ensure_started()
        await self._refresh_catalog()
        return await self.list_tools()

    async def call(
        self,
        invocation: ToolInvocation,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult:
        """Call one allowlisted tool with result-size and cancellation controls."""
        self._ensure_started()
        if not self._catalog_valid:
            raise MCPProtocolError("MCP catalog requires a successful refresh")
        try:
            raw_name = self._raw_names[invocation.call.name]
            definition = self._definitions[invocation.call.name]
        except KeyError as exc:
            raise KeyError(f"unknown MCP tool: {invocation.call.name}") from exc
        try:
            arguments = self._arguments(raw_name, invocation.call.arguments)
            Draft202012Validator(definition.input_schema).validate(arguments)
        except Exception:
            return ToolExecutionResult(
                call_id=invocation.call.call_id,
                tool_name=invocation.call.name,
                status=ToolExecutionStatus.DENIED,
                error="MCP arguments do not match the current reviewed tool schema.",
                definitely_not_executed=True,
                retry_safety=RetrySafety.SAFE,
            )
        if cancellation.cancelled:
            return ToolExecutionResult(
                call_id=invocation.call.call_id,
                tool_name=invocation.call.name,
                status=ToolExecutionStatus.CANCELLED,
                error="The MCP tool call was cancelled.",
                definitely_not_executed=True,
                retry_safety=RetrySafety.SAFE,
            )
        call_task = asyncio.create_task(self._connection.call_tool(raw_name, arguments))
        cancel_task = asyncio.create_task(cancellation.wait())
        try:
            done, _ = await asyncio.wait(
                {call_task, cancel_task},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=self._config.timeout_seconds,
            )
            if not done:
                call_task.cancel()
                await asyncio.gather(call_task, return_exceptions=True)
                raise TimeoutError("MCP tool deadline exceeded")
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
            error_flag = payload.get("isError", False)
            if not isinstance(error_flag, bool):
                raise MCPProtocolError("MCP isError must be a boolean")
            if error_flag:
                self._last_error = "ToolExecutionError"
                return ToolExecutionResult(
                    call_id=invocation.call.call_id,
                    tool_name=invocation.call.name,
                    status=ToolExecutionStatus.FAILED,
                    error="The external MCP tool reported an execution error.",
                    data={"external_untrusted_content": payload},
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.UNKNOWN,
                )
            structured = payload.get("structuredContent")
            if structured is not None:
                Draft202012Validator(definition.output_schema).validate(structured)
            return ToolExecutionResult(
                call_id=invocation.call.call_id,
                tool_name=invocation.call.name,
                status=ToolExecutionStatus.SUCCEEDED,
                data={"external_untrusted_content": payload},
                retry_safety=(
                    RetrySafety.SAFE
                    if raw_name in self._config.retry_safe_tools
                    else RetrySafety.UNKNOWN
                ),
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
                status=(
                    ToolExecutionStatus.TIMED_OUT
                    if isinstance(exc, TimeoutError)
                    else ToolExecutionStatus.FAILED
                ),
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
            if self._started and not self._closed and self._catalog_valid
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
            "unreviewed_tools": [
                name
                for name in self._config.allowed_tools
                if not self._config.reviewed_read_only(name)
            ],
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
