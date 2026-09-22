"""Strict MCP server configuration and the bundled Tavily preset."""

from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

ServerID = Annotated[
    str,
    StringConstraints(min_length=1, max_length=48, pattern=r"^[a-z][a-z0-9_-]*$"),
]
EnvironmentName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Z][A-Z0-9_]*$"),
]


class MCPTransport(StrEnum):
    """Supported MCP client transports."""

    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


class MCPAuthentication(StrEnum):
    """Supported authentication modes."""

    NONE = "none"
    BEARER_ENVIRONMENT = "bearer_environment"
    OAUTH = "oauth"


class MCPServerConfig(BaseModel):
    """One approved MCP server with bounded capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: ServerID
    enabled: bool = True
    transport: MCPTransport
    url: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    environment_variables: dict[str, EnvironmentName] = Field(default_factory=dict)
    authentication: MCPAuthentication = MCPAuthentication.NONE
    token_environment: EnvironmentName | None = None
    allowed_tools: tuple[str, ...]
    read_only_tools: tuple[str, ...] = ()
    retry_safe_tools: tuple[str, ...] = ()
    max_discovery_pages: Annotated[int, Field(ge=1, le=64)] = 16
    max_discovery_tools: Annotated[int, Field(ge=1, le=1024)] = 256
    timeout_seconds: Annotated[float, Field(ge=1, le=120)] = 20.0
    max_result_bytes: Annotated[int, Field(ge=1024, le=1_048_576)] = 131_072
    default_parameters: dict[str, Any] = Field(default_factory=dict)
    preset: str | None = None

    @field_validator("allowed_tools")
    @classmethod
    def allowed_tools_are_safe_and_unique(cls, tools: tuple[str, ...]) -> tuple[str, ...]:
        """Reject empty, duplicate, or model-name-incompatible tool names."""
        if not tools:
            raise ValueError("allowed_tools must not be empty")
        if len(tools) != len(set(tools)):
            raise ValueError("allowed_tools must not contain duplicates")
        pattern = re.compile(r"^[a-z][a-z0-9_-]*$")
        if any(pattern.fullmatch(tool) is None for tool in tools):
            raise ValueError(
                "allowed MCP tool names may contain lowercase letters, digits, _ and -"
            )
        return tools

    @model_validator(mode="after")
    def transport_and_authentication_are_consistent(self) -> MCPServerConfig:
        """Require only the fields meaningful to the selected transport."""
        if not set(self.read_only_tools) <= set(self.allowed_tools):
            raise ValueError("read_only_tools must be a subset of allowed_tools")
        if not set(self.retry_safe_tools) <= set(self.read_only_tools):
            raise ValueError("retry_safe_tools must be a subset of reviewed read_only_tools")
        if self.transport is MCPTransport.STREAMABLE_HTTP:
            if self.url is None or not self.url.startswith("https://"):
                raise ValueError("Streamable HTTP MCP servers require an HTTPS URL")
            if self.command is not None or self.args or self.environment_variables:
                raise ValueError("HTTP MCP servers cannot define stdio command fields")
        else:
            if self.command is None or not self.command.strip():
                raise ValueError("stdio MCP servers require a command")
            if self.url is not None:
                raise ValueError("stdio MCP servers cannot define a URL")
        if self.authentication is MCPAuthentication.BEARER_ENVIRONMENT:
            if self.token_environment is None:
                raise ValueError("bearer authentication requires token_environment")
        elif self.authentication is MCPAuthentication.OAUTH:
            if self.transport is not MCPTransport.STREAMABLE_HTTP:
                raise ValueError("OAuth authentication requires Streamable HTTP")
        elif self.token_environment is not None:
            raise ValueError("token_environment requires bearer authentication")
        return self

    def reviewed_read_only(self, name: str) -> bool:
        """Only local policy or the existing official search preset grants read access."""
        return name in self.read_only_tools or (
            self.preset == "tavily"
            and name == "tavily_search"
            and self.transport is MCPTransport.STREAMABLE_HTTP
            and self.url == "https://mcp.tavily.com/mcp"
        )

    def redacted_dict(self) -> dict[str, Any]:
        """Return configuration metadata without resolving any secret."""
        value = self.model_dump(mode="json")
        if value["token_environment"] is not None:
            value["token_status"] = "configured-by-environment-name"
        return value


class MCPConfiguration(BaseModel):
    """Complete MCP server catalog stored outside project source."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1] = 1
    servers: tuple[MCPServerConfig, ...] = ()

    @field_validator("servers")
    @classmethod
    def server_ids_are_unique(
        cls,
        servers: tuple[MCPServerConfig, ...],
    ) -> tuple[MCPServerConfig, ...]:
        """Prevent ambiguous server ownership."""
        ids = [server.id for server in servers]
        if len(ids) != len(set(ids)):
            raise ValueError("MCP server IDs must be unique")
        return servers


def tavily_server_config(server_id: str = "tavily") -> MCPServerConfig:
    """Return the search-only official hosted Tavily preset."""
    return MCPServerConfig(
        id=server_id,
        enabled=True,
        transport=MCPTransport.STREAMABLE_HTTP,
        url="https://mcp.tavily.com/mcp",
        authentication=MCPAuthentication.BEARER_ENVIRONMENT,
        token_environment="TAVILY_API_KEY",
        allowed_tools=("tavily_search",),
        timeout_seconds=20.0,
        max_result_bytes=131_072,
        default_parameters={
            "search_depth": "basic",
            "max_results": 5,
            "include_images": False,
            "include_raw_content": False,
        },
        preset="tavily",
    )


def notion_server_config(server_id: str = "notion") -> MCPServerConfig:
    """Return the reviewed read-only subset of Notion's hosted MCP server."""
    return MCPServerConfig(
        id=server_id,
        enabled=True,
        transport=MCPTransport.STREAMABLE_HTTP,
        url="https://mcp.notion.com/mcp",
        authentication=MCPAuthentication.OAUTH,
        allowed_tools=("notion-search", "notion-fetch"),
        read_only_tools=("notion-search", "notion-fetch"),
        retry_safe_tools=("notion-search", "notion-fetch"),
        timeout_seconds=30.0,
        max_result_bytes=131_072,
        preset="notion",
    )


def google_calendar_server_config(
    command: str,
    credential_file: str,
    server_id: str = "google-calendar",
) -> MCPServerConfig:
    """Return the bundled external read-only Calendar MCP subprocess preset."""
    return MCPServerConfig(
        id=server_id,
        enabled=True,
        transport=MCPTransport.STDIO,
        command=command,
        args=(
            "-m",
            "ninjarobot_pi5_agent.external_mcp.google_calendar",
            "--credential-file",
            credential_file,
        ),
        authentication=MCPAuthentication.NONE,
        allowed_tools=("list_today_events",),
        read_only_tools=("list_today_events",),
        retry_safe_tools=("list_today_events",),
        timeout_seconds=20.0,
        max_result_bytes=65_536,
        preset="google-calendar-readonly",
    )


def load_mcp_configuration(path: str | Path) -> MCPConfiguration:
    """Load strict TOML, returning an empty catalog when the file is absent."""
    config_path = Path(path).expanduser().absolute()
    if not config_path.exists():
        return MCPConfiguration()
    if config_path.is_symlink() or config_path.parent.resolve() != config_path.parent:
        raise ValueError("MCP configuration must use a real private path")
    if config_path.stat().st_size > 1_048_576:
        raise ValueError("MCP configuration file is oversized")
    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)
    _migrate_legacy_tavily_tool_name(payload)
    return MCPConfiguration.model_validate_json(json.dumps(payload))


def _migrate_legacy_tavily_tool_name(payload: dict[str, Any]) -> None:
    """Accept the former Tavily raw tool name without rewriting a read operation."""
    servers = payload.get("servers")
    if not isinstance(servers, list):
        return
    for server in servers:
        if not isinstance(server, dict) or server.get("preset") != "tavily":
            continue
        allowed_tools = server.get("allowed_tools")
        if not isinstance(allowed_tools, list):
            continue
        server["allowed_tools"] = [
            "tavily_search" if tool == "tavily-search" else tool for tool in allowed_tools
        ]


def save_mcp_configuration(configuration: MCPConfiguration, path: str | Path) -> Path:
    """Atomically save owner-only TOML without embedding secret values."""
    config_path = Path(path).expanduser().absolute()
    config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if config_path.parent.resolve() != config_path.parent or config_path.is_symlink():
        raise ValueError("MCP configuration must use a real private path")
    config_path.parent.chmod(0o700)
    lines: list[str] = [f"schema_version = {configuration.schema_version}", ""]
    for server in configuration.servers:
        payload = server.model_dump(mode="json")
        lines.append("[[servers]]")
        for key in (
            "id",
            "enabled",
            "transport",
            "url",
            "command",
            "args",
            "environment_variables",
            "authentication",
            "token_environment",
            "allowed_tools",
            "read_only_tools",
            "retry_safe_tools",
            "max_discovery_pages",
            "max_discovery_tools",
            "timeout_seconds",
            "max_result_bytes",
            "preset",
        ):
            value = payload[key]
            if value is not None and value not in ([], {}):
                lines.append(f"{key} = {_toml_value(value)}")
        if payload["default_parameters"]:
            lines.append("[servers.default_parameters]")
            for key, value in payload["default_parameters"].items():
                lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    descriptor, name = tempfile.mkstemp(
        prefix=f".{config_path.name}-", suffix=".tmp", dir=config_path.parent, text=True
    )
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, config_path)
        config_path.chmod(0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise
    return config_path


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        pairs = (f"{json.dumps(str(key))} = {_toml_value(item)}" for key, item in value.items())
        return "{ " + ", ".join(pairs) + " }"
    raise TypeError(f"unsupported TOML value: {type(value).__name__}")
