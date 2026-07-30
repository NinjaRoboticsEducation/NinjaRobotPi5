"""Terminal-only cloud authentication setup and removal."""

from __future__ import annotations

import asyncio
import getpass
import json
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.auth.exceptions import GoogleAuthError
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from oauthlib.oauth2 import OAuth2Error  # type: ignore[import-untyped]
from requests import RequestException

from ninjarobot_pi5_ide import load_robot_config, save_robot_config

from .cloud_common import CloudAuthenticationError
from .google_oauth import (
    GEMINI_SCOPES,
    gemini_credential_path,
    save_google_credentials,
)

GEMINI_REDIRECT_URI = "http://localhost:8080/"


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
    secret_file: str | Path,
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
        if client_id_file is None:
            raise ValueError("Gemini web login requires a Google Desktop OAuth client JSON file")
        if provider.project_id is None:
            raise ValueError("Gemini web login requires project_id in the provider configuration")
        await asyncio.to_thread(
            _gemini_web_login,
            client_id_file,
            gemini_credential_path(secret_file, provider_id),
        )
        persist_auth_method(config_path, provider_id, "oauth")
        return
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


def _gemini_web_login(client_id_file: Path, credential_file: Path) -> None:
    """Complete Google's loopback OAuth flow without requiring a Pi desktop."""
    expanded_client_path = client_id_file.expanduser()
    if expanded_client_path.is_symlink():
        raise CloudAuthenticationError("refusing to read a symbolic-link Google OAuth client file")
    client_path = expanded_client_path.resolve()
    if not client_path.is_file():
        raise ValueError(f"Google OAuth client file does not exist: {client_path}")
    _validate_google_client_file(client_path)
    try:
        flow = InstalledAppFlow.from_client_secrets_file(client_path, GEMINI_SCOPES)
    except (OSError, ValueError) as exc:
        raise CloudAuthenticationError(
            "Google OAuth client JSON is unreadable or is not a Desktop app credential"
        ) from exc
    flow.redirect_uri = GEMINI_REDIRECT_URI
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    print(
        "\nGemini Web Login\n"
        "1. Open this URL in a browser on your phone or computer:\n"
        f"{authorization_url}\n\n"
        "2. Sign in and approve access.\n"
        "3. Google will redirect to a localhost page that may show a connection error.\n"
        "4. Copy the complete localhost URL from the browser address bar."
    )
    authorization_response = getpass.getpass(
        "Paste the complete localhost URL here (input is hidden): "
    ).strip()
    _validate_google_redirect(authorization_response, state)
    try:
        flow.fetch_token(authorization_response=authorization_response)
    except (ValueError, GoogleAuthError, OAuth2Error, RequestException) as exc:
        raise CloudAuthenticationError("Google OAuth authorization could not be completed") from exc
    save_google_credentials(credential_file, flow.credentials)


def _validate_google_client_file(client_path: Path) -> None:
    """Accept only a bounded Google Desktop OAuth client document."""
    if client_path.stat().st_size > 64 * 1024:
        raise CloudAuthenticationError("Google OAuth client JSON is unexpectedly large")
    try:
        payload = json.loads(client_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CloudAuthenticationError("Google OAuth client JSON is unreadable or invalid") from exc
    installed = payload.get("installed") if isinstance(payload, dict) else None
    required = {"client_id", "client_secret", "auth_uri", "token_uri", "redirect_uris"}
    if not isinstance(installed, dict) or not required.issubset(installed):
        raise CloudAuthenticationError("Google OAuth client JSON must be a Desktop app credential")


def _validate_google_redirect(authorization_response: str, expected_state: str) -> None:
    """Reject pasted responses that are not the exact local OAuth callback."""
    try:
        parsed = urlparse(authorization_response)
        port = parsed.port
    except ValueError as exc:
        raise CloudAuthenticationError("Google OAuth redirect URL is invalid") from exc
    query = parse_qs(parsed.query)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or port != 8080
        or parsed.path != "/"
        or query.get("state") != [expected_state]
        or len(query.get("code", [])) != 1
    ):
        raise CloudAuthenticationError(
            "Google OAuth redirect URL does not match this login request"
        )


async def web_logout(
    config_path: str | Path,
    provider_id: str,
    *,
    secret_file: str | Path,
) -> bool:
    """Remove the selected provider's managed OAuth credentials."""
    config = load_robot_config(config_path)
    try:
        provider = config.providers[provider_id]
    except KeyError as exc:
        raise ValueError(f"unknown configured provider: {provider_id}") from exc
    if provider.kind == "gemini":
        credential_file = gemini_credential_path(secret_file, provider_id)
        if credential_file.is_symlink():
            raise CloudAuthenticationError(
                "refusing to remove a symbolic-link OAuth credential file"
            )
        existed = credential_file.is_file()
        credential_file.unlink(missing_ok=True)
        return existed
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
    return True
