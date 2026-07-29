"""Terminal-only cloud authentication setup and removal."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from ninjarobot_pi5_ide import load_robot_config, save_robot_config

from .cloud_common import CloudAuthenticationError

GEMINI_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform,"
    "https://www.googleapis.com/auth/generative-language.retriever"
)


def persist_auth_method(
    config_path: str | Path,
    provider_id: str,
    method: str,
) -> None:
    """Persist only a validated provider authentication method."""
    if method not in {"api_key", "oauth"}:
        raise ValueError("authentication method must be api_key or oauth")
    config = load_robot_config(config_path)
    if provider_id not in config.providers:
        raise ValueError(f"unknown configured provider: {provider_id}")
    payload = config.model_dump(mode="python")
    payload["providers"][provider_id]["auth_method"] = method
    validated = type(config).model_validate(payload)
    save_robot_config(validated, config_path, overwrite=True)


async def web_login(
    config_path: str | Path,
    provider_id: str,
    *,
    client_id_file: Path | None = None,
) -> None:
    """Run the provider's official headless-friendly browser login."""
    config = load_robot_config(config_path)
    try:
        provider = config.providers[provider_id]
    except KeyError as exc:
        raise ValueError(f"unknown configured provider: {provider_id}") from exc
    if provider.kind == "openai":
        raise CloudAuthenticationError(
            "OpenAI API inference does not support ChatGPT account web login; use an API key"
        )
    if provider.kind == "gemini":
        if shutil.which("gcloud") is None:
            raise CloudAuthenticationError("Gemini web login requires the gcloud CLI")
        command = [
            "gcloud",
            "auth",
            "application-default",
            "login",
            "--no-browser",
            f"--scopes={GEMINI_SCOPES}",
        ]
        if client_id_file is not None:
            path = client_id_file.expanduser().resolve()
            if not path.is_file():
                raise ValueError(f"Google OAuth client file does not exist: {path}")
            command.append(f"--client-id-file={path}")
    elif provider.kind == "anthropic":
        if shutil.which("ant") is None:
            raise CloudAuthenticationError("Anthropic web login requires the ant CLI")
        command = [
            "ant",
            "auth",
            "login",
            "--no-browser",
            "--profile",
            provider.oauth_profile or "default",
        ]
    else:
        raise ValueError("Ollama does not require web login")
    process = await asyncio.create_subprocess_exec(*command)
    if await process.wait() != 0:
        raise CloudAuthenticationError(f"{provider.kind} web login did not complete")
    persist_auth_method(config_path, provider_id, "oauth")


async def web_logout(config_path: str | Path, provider_id: str) -> None:
    """Remove official CLI-managed OAuth credentials for one provider."""
    config = load_robot_config(config_path)
    try:
        provider = config.providers[provider_id]
    except KeyError as exc:
        raise ValueError(f"unknown configured provider: {provider_id}") from exc
    if provider.kind == "gemini":
        command = ("gcloud", "auth", "application-default", "revoke", "--quiet")
    elif provider.kind == "anthropic":
        command = (
            "ant",
            "auth",
            "logout",
            "--profile",
            provider.oauth_profile or "default",
        )
    else:
        raise ValueError(f"{provider.kind} does not have web-login credentials")
    if shutil.which(command[0]) is None:
        raise CloudAuthenticationError(f"credential CLI is not installed: {command[0]}")
    process = await asyncio.create_subprocess_exec(*command)
    if await process.wait() != 0:
        raise CloudAuthenticationError(f"{provider.kind} web logout did not complete")
