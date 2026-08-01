"""API-key-only cloud authentication configuration helpers."""

from __future__ import annotations

from pathlib import Path

from ninjarobot_pi5_ide import load_robot_config, save_robot_config


def persist_api_key_authentication(
    config_path: str | Path,
    provider_id: str,
) -> None:
    """Persist API-key mode and remove retired OAuth profile metadata."""
    config = load_robot_config(config_path)
    if provider_id not in config.providers:
        raise ValueError(f"unknown configured provider: {provider_id}")
    provider = config.providers[provider_id]
    if provider.kind == "ollama" or provider.api_key_env is None:
        raise ValueError(f"{provider.kind} does not have an API-key configuration")
    payload = config.model_dump(mode="python")
    payload["providers"][provider_id]["auth_method"] = "api_key"
    payload["providers"][provider_id].pop("oauth_profile", None)
    validated = type(config).model_validate(payload)
    save_robot_config(validated, config_path, overwrite=True)


def web_login_removed(provider_id: str) -> None:
    """Keep the legacy CLI command informative without retaining OAuth code."""
    raise ValueError(
        f"Web login for '{provider_id}' was removed; use "
        f"'ninjarobot-agent provider set-api-key {provider_id}' instead"
    )
