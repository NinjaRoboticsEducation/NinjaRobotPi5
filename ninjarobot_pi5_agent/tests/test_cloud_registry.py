from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from ninjarobot_pi5_agent.provider_auth import persist_auth_method
from ninjarobot_pi5_agent.secrets import SecretStore
from ninjarobot_pi5_ide.config_import import save_robot_config
from pydantic import ValidationError

from ninjarobot_pi5_agent import (
    AnthropicConfig,
    AnthropicProvider,
    ConfiguredProviderRegistry,
    GeminiConfig,
    GeminiProvider,
    OllamaProvider,
    OpenAIConfig,
    OpenAIProvider,
)
from ninjarobot_pi5_ide import load_robot_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"


def test_configured_registry_builds_every_provider_without_resolving_secrets(
    tmp_path,
) -> None:
    registry = ConfiguredProviderRegistry(
        EXAMPLE,
        SecretStore(tmp_path / "secrets.env"),
    )
    adapters = {
        "ollama": registry.create("ollama", "qwen3:4b"),
        "openai": registry.create("openai", "gpt-5-mini"),
        "gemini": registry.create("gemini", "gemini-2.5-flash"),
        "anthropic": registry.create("anthropic", "claude-sonnet-4-5"),
    }

    assert isinstance(adapters["ollama"], OllamaProvider)
    assert isinstance(adapters["openai"], OpenAIProvider)
    assert isinstance(adapters["gemini"], GeminiProvider)
    assert isinstance(adapters["anthropic"], AnthropicProvider)
    assert all(adapter.capabilities.native_tools for adapter in adapters.values())
    assert all(adapter.capabilities.streaming for adapter in adapters.values())

    async def close() -> None:
        for adapter in adapters.values():
            await adapter.close()

    asyncio.run(close())


def test_registry_credential_status_never_contains_secret_values(tmp_path) -> None:
    secret_path = tmp_path / "secrets.env"
    store = SecretStore(secret_path)
    store.set("OPENAI_API_KEY", "never-show-this-value")
    registry = ConfiguredProviderRegistry(EXAMPLE, store)

    status = registry.credential_status("openai")

    assert status == {
        "method": "api_key",
        "environment_name": "OPENAI_API_KEY",
        "configured": True,
    }
    assert "never-show-this-value" not in repr(status)


def test_auth_method_persistence_revalidates_the_complete_configuration(
    tmp_path,
) -> None:
    config_path = tmp_path / "config.toml"
    save_robot_config(load_robot_config(EXAMPLE), config_path, overwrite=False)

    with pytest.raises(ValidationError, match="does not support ChatGPT web login"):
        persist_auth_method(config_path, "openai", "oauth")
    with pytest.raises(ValidationError, match="requires project_id"):
        persist_auth_method(config_path, "gemini", "oauth")

    persist_auth_method(config_path, "anthropic", "oauth")
    assert load_robot_config(config_path).providers["anthropic"].auth_method == "oauth"


@pytest.mark.parametrize(
    "factory",
    (
        lambda: OpenAIConfig(base_url="https://example.com/v1"),
        lambda: GeminiConfig(base_url="https://example.com/v1beta"),
        lambda: AnthropicConfig(base_url="https://example.com/v1"),
    ),
)
def test_cloud_credentials_cannot_be_redirected_to_an_unapproved_host(factory) -> None:
    with pytest.raises(ValidationError, match="credentials may be sent only"):
        factory()
