"""Private OAuth storage and loopback authorization for reviewed MCP presets."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlsplit

from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from pydantic import AnyUrl

from .mcp_config import MCPServerConfig

NOTION_URL = "https://mcp.notion.com/mcp"


class PrivateOAuthStorage:
    """Store one server's OAuth tokens and dynamic client data atomically."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().absolute()
        self._lock = asyncio.Lock()

    async def get_tokens(self) -> OAuthToken | None:
        payload = await self._read()
        raw = payload.get("tokens")
        return OAuthToken.model_validate(raw) if isinstance(raw, dict) else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        async with self._lock:
            payload = self._read_sync()
            payload["tokens"] = tokens.model_dump(mode="json")
            self._write_sync(payload)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        payload = await self._read()
        raw = payload.get("client")
        return OAuthClientInformationFull.model_validate(raw) if isinstance(raw, dict) else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        async with self._lock:
            payload = self._read_sync()
            payload["client"] = client_info.model_dump(mode="json")
            self._write_sync(payload)

    async def _read(self) -> dict[str, object]:
        async with self._lock:
            return self._read_sync()

    def _read_sync(self) -> dict[str, object]:
        if not self.path.exists():
            return {"schema_version": 1}
        if self.path.is_symlink() or self.path.parent.resolve() != self.path.parent:
            raise ValueError("MCP OAuth storage must use a real private path")
        if self.path.stat().st_mode & 0o077:
            raise PermissionError("MCP OAuth storage must be owner-only (mode 0600)")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("invalid MCP OAuth storage")
        if raw.get("schema_version") != 1:
            raise ValueError("unsupported MCP OAuth storage version")
        return cast(dict[str, object], raw)

    def _write_sync(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.parent.resolve() != self.path.parent or self.path.is_symlink():
            raise ValueError("MCP OAuth storage must use a real private path")
        self.path.parent.chmod(0o700)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{self.path.name}-", suffix=".tmp", dir=self.path.parent, text=True
        )
        temporary = Path(name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
            raise


def oauth_provider_for(
    server: MCPServerConfig, *, port: int = 8766, interactive: bool = False
) -> OAuthClientProvider:
    """Build OAuth only for the exact reviewed hosted Notion preset."""
    if server.preset != "notion" or server.url != NOTION_URL:
        raise ValueError("OAuth is allowed only for the reviewed Notion MCP endpoint")
    if not 1024 <= port <= 65535:
        raise ValueError("OAuth callback port must be between 1024 and 65535")
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    storage = PrivateOAuthStorage(Path(f"~/.config/ninjarobot_pi5/mcp-oauth/{server.id}.json"))

    async def redirect(url: str) -> None:
        if not interactive:
            raise RuntimeError(
                "Notion authorization requires `ninjarobot onboard --step mcp`; "
                "the Agent service will not start a browser login"
            )
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("MCP authorization URL must use HTTPS")
        print("Open this authorization URL in your browser:")
        print(url)
        print(f"From another computer, first use: ssh -L {port}:127.0.0.1:{port} USER@ROBOT")

    async def callback() -> tuple[str, str | None]:
        future: asyncio.Future[tuple[str, str | None]] = asyncio.get_running_loop().create_future()
        workers: set[asyncio.Task[None]] = set()

        async def receive(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            worker = asyncio.current_task()
            assert worker is not None
            workers.add(worker)
            status = "400 Bad Request"
            message = b"Authorization rejected."
            try:
                async with asyncio.timeout(5):
                    line = await reader.readline()
                    if len(line) > 8192:
                        raise ValueError("oversized OAuth callback request")
                    parts = line.decode("ascii").strip().split()
                    if len(parts) != 3 or parts[0] != "GET":
                        raise ValueError("invalid OAuth callback request")
                    target = urlsplit(parts[1])
                    query = parse_qs(target.query)
                    codes = query.get("code", [])
                    states = query.get("state", [])
                    if (
                        target.path != "/callback"
                        or target.scheme
                        or target.netloc
                        or len(codes) != 1
                        or len(states) > 1
                        or not 1 <= len(codes[0]) <= 4096
                    ):
                        raise ValueError("invalid OAuth callback code or state")
                    state = states[0] if states else None
                    if not future.done():
                        future.set_result((codes[0], state))
                    status = "200 OK"
                    message = b"Authorization received. Return to the NinjaRobot terminal."
            except (TimeoutError, UnicodeError, ValueError) as exc:
                if not future.done():
                    future.set_exception(exc)
            finally:
                try:
                    async with asyncio.timeout(2):
                        writer.write(
                            (
                                f"HTTP/1.1 {status}\r\n"
                                "Content-Type: text/plain\r\nConnection: close\r\n\r\n"
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

        server_handle = await asyncio.start_server(receive, "127.0.0.1", port, limit=8192)
        try:
            async with asyncio.timeout(300):
                return await future
        finally:
            server_handle.close()
            await server_handle.wait_closed()
            pending = tuple(workers)
            for worker in pending:
                worker.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    metadata = OAuthClientMetadata(
        redirect_uris=[AnyUrl(redirect_uri)],
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        client_name="NinjaRobotPi5",
    )
    return OAuthClientProvider(
        NOTION_URL,
        metadata,
        storage,
        redirect_handler=redirect,
        callback_handler=callback,
        timeout=300,
    )
