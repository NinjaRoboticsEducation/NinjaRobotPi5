from __future__ import annotations

import asyncio
import stat

import pytest
from mcp.shared.auth import OAuthToken
from ninjarobot_pi5_agent.mcp_config import notion_server_config, tavily_server_config
from ninjarobot_pi5_agent.mcp_oauth import PrivateOAuthStorage, oauth_provider_for


def test_oauth_tokens_round_trip_in_owner_only_storage(tmp_path) -> None:
    async def exercise() -> None:
        path = tmp_path / "private" / "notion.json"
        storage = PrivateOAuthStorage(path)
        token = OAuthToken(access_token="private-access", refresh_token="private-refresh")

        await storage.set_tokens(token)

        assert await storage.get_tokens() == token
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

    asyncio.run(exercise())


def test_oauth_provider_is_restricted_to_exact_notion_preset() -> None:
    provider = oauth_provider_for(notion_server_config(), port=18766)

    assert provider is not None
    with pytest.raises(ValueError, match="only for the reviewed Notion"):
        oauth_provider_for(tavily_server_config(), port=18766)


def test_service_oauth_provider_never_starts_interactive_login() -> None:
    provider = oauth_provider_for(notion_server_config(), port=18766)

    async def exercise() -> None:
        with pytest.raises(RuntimeError, match="will not start a browser login"):
            await provider.context.redirect_handler("https://www.notion.so/oauth")

    asyncio.run(exercise())
