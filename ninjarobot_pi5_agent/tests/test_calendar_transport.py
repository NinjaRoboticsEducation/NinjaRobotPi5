"""Fake HTTP and loopback callbacks only; never authorize a real account."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from ninjarobot_pi5_agent.calendar_google import (
    READ_SCOPE,
    CalendarHTTPError,
    GoogleCalendarBackend,
    bounded_request,
)
from ninjarobot_pi5_agent.secrets import SecretStore


def test_transport_fixed_hosts_scope_revocation_and_response_budget(tmp_path):
    async def run():
        secrets = SecretStore(tmp_path / "secrets.env")
        secrets.set(
            "NINJA_CAL_TEST",
            json.dumps(
                {
                    "client_id": "fake-client",
                    "client_secret": "fake-client-secret",
                    "refresh_token": "fake-refresh",
                    "scope": READ_SCOPE,
                }
            ),
        )
        requests = []

        def respond(request):
            requests.append(request)
            if request.url.host == "oauth2.googleapis.com":
                return httpx.Response(
                    200,
                    json={"access_token": "fake-access", "scope": READ_SCOPE, "expires_in": 3600},
                )
            assert request.url.host == "www.googleapis.com"
            assert request.headers["Authorization"] == "Bearer fake-access"
            return httpx.Response(200, json={"items": []})

        backend = GoogleCalendarBackend(secrets, transport=httpx.MockTransport(respond))
        conn = {"secret_ref": "NINJA_CAL_TEST", "calendar_id": "someone@example.org/../../other"}
        assert await backend.request(conn, "GET") == {"items": []}
        assert b"%2F..%2F..%2F" in requests[-1].url.raw_path
        assert secrets.path.stat().st_mode & 0o777 == 0o600
        secrets.delete("NINJA_CAL_TEST")
        with pytest.raises(KeyError):
            await backend.request(conn, "GET")
        assert len(requests) == 2
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"x": "large"}))
        ) as client:
            with pytest.raises(ValueError, match="byte budget"):
                await bounded_request(client, "GET", "https://example.org/", limit=4)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(401, text="sensitive provider text")
            )
        ) as client:
            with pytest.raises(CalendarHTTPError) as caught:
                await bounded_request(client, "GET", "https://example.org/")
            assert "sensitive" not in str(caught.value)

    asyncio.run(run())


def test_oauth_pkce_state_loopback_and_cleanup_without_live_network(tmp_path, monkeypatch):
    from ninjarobot_pi5_agent import calendar_oauth

    async def run():
        client_file = tmp_path / "desktop.json"
        client_file.write_text(
            json.dumps({"installed": {"client_id": "fake-client", "client_secret": "fake-secret"}})
        )
        callback = None
        authorization = {}
        responses = []
        spawned = []

        class Server:
            closed = False

            def close(self):
                self.closed = True

            async def wait_closed(self):
                pass

        server = Server()

        async def start_server(handler, host, port, **kwargs):
            nonlocal callback
            assert host == "127.0.0.1" and port == 8765
            callback = handler
            return server

        class Writer:
            def write(self, value):
                responses.append(value)

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def send():
            for state in ("wrong", authorization["state"][0]):
                reader = asyncio.StreamReader()
                reader.feed_data(f"GET /?state={state}&code=fake-code HTTP/1.1\r\n".encode())
                reader.feed_eof()
                await callback(reader, Writer())

        def capture(message, **kwargs):
            if "https://accounts.google.com/" in message:
                authorization.update(parse_qs(urlsplit(message.split("\n")[-1]).query))
                spawned.append(asyncio.create_task(send()))

        def respond(request):
            assert request.url.host == "oauth2.googleapis.com"
            values = parse_qs(request.content.decode())
            challenge = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(values["code_verifier"][0].encode()).digest()
                )
                .decode()
                .rstrip("=")
            )
            assert challenge == authorization["code_challenge"][0]
            assert values["redirect_uri"] == ["http://127.0.0.1:8765/"]
            return httpx.Response(200, json={"refresh_token": "fake-refresh", "scope": READ_SCOPE})

        original_client = httpx.AsyncClient
        monkeypatch.setattr(calendar_oauth.asyncio, "start_server", start_server)
        monkeypatch.setattr("builtins.print", capture)
        monkeypatch.setattr(
            calendar_oauth.httpx,
            "AsyncClient",
            lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(respond)),
        )
        result = await calendar_oauth.authorize(client_file)
        await asyncio.gather(*spawned)
        assert result["refresh_token"] == "fake-refresh"
        assert responses[0].startswith(b"HTTP/1.1 400")
        assert responses[1].startswith(b"HTTP/1.1 200")
        assert server.closed

    asyncio.run(run())
