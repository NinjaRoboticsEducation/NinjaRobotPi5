from __future__ import annotations

import stat

import pytest
from pydantic import ValidationError

from ninjarobot_pi5_agent import (
    MCPAuthentication,
    MCPConfiguration,
    MCPServerConfig,
    MCPTransport,
    SecretStore,
    load_mcp_configuration,
    save_mcp_configuration,
    tavily_server_config,
)


def test_tavily_preset_is_search_only_https_and_round_trips(tmp_path) -> None:
    preset = tavily_server_config()
    path = tmp_path / "private" / "mcp.toml"

    save_mcp_configuration(MCPConfiguration(servers=(preset,)), path)
    restored = load_mcp_configuration(path)

    assert restored == MCPConfiguration(servers=(preset,))
    assert preset.url == "https://mcp.tavily.com/mcp"
    assert preset.allowed_tools == ("tavily-search",)
    assert preset.default_parameters["include_raw_content"] is False
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_mcp_config_rejects_insecure_remote_and_missing_stdio_command() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        MCPServerConfig(
            id="unsafe",
            transport=MCPTransport.STREAMABLE_HTTP,
            url="http://example.test/mcp",
            allowed_tools=("search",),
        )

    with pytest.raises(ValidationError, match="require a command"):
        MCPServerConfig(
            id="local",
            transport=MCPTransport.STDIO,
            allowed_tools=("search",),
        )

    with pytest.raises(ValidationError, match="token_environment"):
        MCPServerConfig(
            id="remote",
            transport=MCPTransport.STREAMABLE_HTTP,
            url="https://example.test/mcp",
            authentication=MCPAuthentication.BEARER_ENVIRONMENT,
            allowed_tools=("search",),
        )


def test_secret_store_permissions_environment_override_and_redaction(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "private" / "secrets.env"
    store = SecretStore(path)
    store.set("TAVILY_API_KEY", "stored-secret-value")

    assert store.get("TAVILY_API_KEY") == "stored-secret-value"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert store.redact({"message": "token=stored-secret-value"}) == {"message": "token=[REDACTED]"}

    monkeypatch.setenv("TAVILY_API_KEY", "environment-value")
    assert store.get("TAVILY_API_KEY") == "environment-value"

    with pytest.raises(ValueError, match="single-line"):
        store.set("BAD_SECRET", "line-1\nline-2")
