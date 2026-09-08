from __future__ import annotations

import json
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
    assert preset.allowed_tools == ("tavily_search",)
    assert preset.default_parameters["include_raw_content"] is False
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert path.read_text(encoding="utf-8").startswith("schema_version = 1\n")


def test_empty_versioned_configuration_round_trips(tmp_path) -> None:
    path = tmp_path / "mcp.toml"

    save_mcp_configuration(MCPConfiguration(), path)

    assert path.read_text(encoding="utf-8") == "schema_version = 1\n"
    assert load_mcp_configuration(path) == MCPConfiguration()


def test_local_effect_and_retry_review_round_trips(tmp_path) -> None:
    preset = tavily_server_config().model_copy(
        update={"read_only_tools": ("tavily_search",), "retry_safe_tools": ("tavily_search",)}
    )
    path = tmp_path / "mcp.toml"
    save_mcp_configuration(MCPConfiguration(servers=(preset,)), path)
    assert load_mcp_configuration(path).servers == (preset,)


def test_retry_review_cannot_grant_unreviewed_effects() -> None:
    payload = tavily_server_config().model_dump(mode="json")
    payload["retry_safe_tools"] = ["tavily_search"]
    with pytest.raises(ValidationError, match="reviewed read_only_tools"):
        MCPServerConfig.model_validate_json(json.dumps(payload))


def test_legacy_configuration_without_schema_version_defaults_to_version_one(tmp_path) -> None:
    path = tmp_path / "mcp.toml"
    path.write_text("servers = []\n", encoding="utf-8")

    configuration = load_mcp_configuration(path)

    assert configuration.schema_version == 1
    assert configuration.servers == ()


def test_unsupported_mcp_schema_version_is_rejected(tmp_path) -> None:
    path = tmp_path / "mcp.toml"
    path.write_text("schema_version = 2\nservers = []\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="schema_version"):
        load_mcp_configuration(path)


def test_legacy_tavily_raw_tool_name_is_migrated_without_rewriting(tmp_path) -> None:
    path = tmp_path / "mcp.toml"
    legacy = """
[[servers]]
id = "tavily"
enabled = true
transport = "streamable_http"
url = "https://mcp.tavily.com/mcp"
authentication = "bearer_environment"
token_environment = "TAVILY_API_KEY"
allowed_tools = ["tavily-search"]
preset = "tavily"
"""
    path.write_text(legacy, encoding="utf-8")

    configuration = load_mcp_configuration(path)

    assert configuration.servers[0].allowed_tools == ("tavily_search",)
    assert path.read_text(encoding="utf-8") == legacy


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

    store.set("LEADING_EQUALS_SECRET", "=round-trip-value==")
    assert SecretStore(path).get("LEADING_EQUALS_SECRET") == "=round-trip-value=="

    monkeypatch.setenv("TAVILY_API_KEY", "environment-value")
    assert store.get("TAVILY_API_KEY") == "environment-value"

    with pytest.raises(ValueError, match="single-line"):
        store.set("BAD_SECRET", "line-1\nline-2")


def test_secret_store_redacts_environment_ngrok_token(tmp_path, monkeypatch) -> None:
    store = SecretStore(tmp_path / "secrets.env")
    monkeypatch.setenv("NGROK_AUTHTOKEN", "ngrok-private-token")

    assert store.get("NGROK_AUTHTOKEN") == "ngrok-private-token"
    assert store.redact("token=ngrok-private-token") == "token=[REDACTED]"


def test_secret_store_rejects_symbolic_link_targets(tmp_path) -> None:
    victim = tmp_path / "victim.env"
    victim.write_text("SAFE=value\n", encoding="utf-8")
    linked_file = tmp_path / "linked.env"
    linked_file.symlink_to(victim)

    with pytest.raises(ValueError, match="must not be a symbolic link"):
        SecretStore(linked_file).set("NGROK_AUTHTOKEN", "private")
    assert victim.read_text(encoding="utf-8") == "SAFE=value\n"

    real_directory = tmp_path / "real"
    real_directory.mkdir()
    linked_directory = tmp_path / "linked"
    linked_directory.symlink_to(real_directory, target_is_directory=True)
    with pytest.raises(ValueError, match="directory must not be a symbolic link"):
        SecretStore(linked_directory / "secrets.env").set(
            "NGROK_AUTHTOKEN",
            "private",
        )
