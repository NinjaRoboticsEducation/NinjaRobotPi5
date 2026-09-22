"""Exercise browser callback handling without opening sockets or Google accounts."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from ninjarobot_pi5_agent import calendar_oauth


@pytest.mark.parametrize("declined", [False, True])
def test_browser_callback_reports_result_and_closes_listener(monkeypatch, tmp_path, declined):
    client = tmp_path / "client.json"
    client.write_text(
        json.dumps({"installed": {"client_id": "fixture", "client_secret": "fixture"}})
    )
    server = Mock()
    server.wait_closed = AsyncMock()
    callback = None
    tasks = []
    messages = []

    async def start_server(handler, host, port, **kwargs):
        nonlocal callback
        assert host == "127.0.0.1"
        callback = handler
        return server

    def output(message):
        messages.append(message)
        if "https://accounts.google.com/" not in message:
            return
        url = message.split("\n")[-1]
        query = parse_qs(urlsplit(url).query)
        values = {"state": query["state"][0]}
        values.update({"error": "access_denied"} if declined else {"code": "fixture-code"})
        reader = asyncio.StreamReader()
        reader.feed_data(("GET /?" + urlencode(values) + " HTTP/1.1\r\n").encode())
        reader.feed_eof()
        writer = Mock()
        writer.drain = AsyncMock()
        writer.wait_closed = AsyncMock()
        tasks.append(asyncio.create_task(callback(reader, writer)))

    monkeypatch.setattr(calendar_oauth.asyncio, "start_server", start_server)
    request = AsyncMock(
        return_value=(200, {"refresh_token": "fixture", "scope": calendar_oauth.READ_SCOPE})
    )
    monkeypatch.setattr(calendar_oauth, "bounded_request", request)

    async def run():
        try:
            return await calendar_oauth.authorize(client, output=output)
        finally:
            await asyncio.gather(*tasks)

    if declined:
        with pytest.raises(ValueError, match="declined"):
            asyncio.run(run())
        request.assert_not_awaited()
    else:
        credential = asyncio.run(run())
        assert credential["refresh_token"] == "fixture"
        assert any("Authorization received" in message for message in messages)
        request.assert_awaited_once()
    server.close.assert_called_once()
    server.wait_closed.assert_awaited_once()
