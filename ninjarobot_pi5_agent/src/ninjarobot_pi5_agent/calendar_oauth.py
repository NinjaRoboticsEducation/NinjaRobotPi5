"""Explicit operator-only browser authorization using a private loopback callback."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from .calendar_google import READ_SCOPE, WRITE_SCOPE, bounded_request


async def authorize(client_file: Path, *, port: int = 8765, write: bool = False) -> dict[str, Any]:
    if not 1024 <= port <= 65535:
        raise ValueError("choose a local callback port from 1024 through 65535")
    with client_file.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("OAuth client file is oversized")
    client = json.loads(raw).get("installed", {})
    if not isinstance(client.get("client_id"), str) or not isinstance(
        client.get("client_secret"), str
    ):
        raise ValueError("use a Google Desktop app OAuth client JSON file")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    redirect = f"http://127.0.0.1:{port}/"
    scope = WRITE_SCOPE if write else READ_SCOPE
    future: asyncio.Future[str] = asyncio.get_running_loop().create_future()

    workers: set[asyncio.Task[Any]] = set()

    async def callback(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        worker = asyncio.current_task()
        assert worker is not None
        workers.add(worker)
        message = b"Authorization rejected."
        status = "400 Bad Request"
        try:
            async with asyncio.timeout(5):
                line = await reader.readline()
                if len(line) > 8192:
                    raise ValueError("oversized callback")
                parts = line.decode("ascii").strip().split()
                if len(parts) != 3 or parts[0] != "GET":
                    raise ValueError("invalid callback")
                target = urlsplit(parts[1])
                values = parse_qs(target.query)
                received = values.get("state", [""])[0]
                code = values.get("code", [""])[0]
                if (
                    target.path != "/"
                    or target.scheme
                    or target.netloc
                    or len(values.get("state", [])) != 1
                    or len(values.get("code", [])) != 1
                    or not secrets.compare_digest(received, state)
                    or not 1 <= len(code) <= 4096
                ):
                    raise ValueError("invalid callback state/code")
                if not future.done():
                    future.set_result(code)
                    status = "200 OK"
                    message = b"Authorization received. Return to the Pi terminal."
        except (ValueError, UnicodeError, TimeoutError):
            pass
        finally:
            try:
                async with asyncio.timeout(2):
                    writer.write(
                        (
                            f"HTTP/1.1 {status}\r\n"
                            + "Content-Type: text/plain\r\nConnection: close\r\n\r\n"
                        ).encode()
                        + message
                    )
                    await writer.drain()
            except (ConnectionError, TimeoutError):
                pass
            finally:
                writer.close()
                try:
                    async with asyncio.timeout(2):
                        await writer.wait_closed()
                except (ConnectionError, TimeoutError):
                    pass
                workers.discard(worker)

    server = await asyncio.start_server(callback, "127.0.0.1", port, limit=8192)
    try:
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": client["client_id"],
                "redirect_uri": redirect,
                "response_type": "code",
                "scope": scope,
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        print(
            f"Keep an SSH tunnel from your computer's port {port} to the Pi's loopback port {port}."
        )
        print("Open this URL in your computer's browser (not a Pi desktop):\n" + url, flush=True)
        async with asyncio.timeout(300):
            code = await future
        async with asyncio.timeout(15):
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=False, trust_env=False
            ) as http:
                _, token = await bounded_request(
                    http,
                    "POST",
                    "https://oauth2.googleapis.com/token",
                    limit=65536,
                    data={
                        "client_id": client["client_id"],
                        "client_secret": client["client_secret"],
                        "redirect_uri": redirect,
                        "code": code,
                        "code_verifier": verifier,
                        "grant_type": "authorization_code",
                    },
                )
        if (
            not isinstance(token.get("refresh_token"), str)
            or scope not in token.get("scope", "").split()
        ):
            raise ValueError("the requested offline calendar permission was not granted")
        return {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "refresh_token": token["refresh_token"],
            "scope": scope,
        }
    finally:
        server.close()
        await server.wait_closed()
        pending = tuple(workers)
        for worker in pending:
            worker.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
