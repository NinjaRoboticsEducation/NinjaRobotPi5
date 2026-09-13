"""Fixed-host bounded Google Calendar transport; credentials never enter tool results."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from urllib.parse import quote

import httpx

from .secrets import SecretStore

READ_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"
WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.events.owned"


class CalendarHTTPError(RuntimeError):
    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"Google Calendar returned HTTP {status}; no response body is logged")


async def bounded_request(
    client: httpx.AsyncClient, method: str, url: str, *, limit: int = 1048576, **kwargs: Any
) -> tuple[int, dict[str, Any]]:
    async with client.stream(method, url, **kwargs) as response:
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError("provider response exceeds byte budget")
        if response.status_code not in {200, 201, 204}:
            raise CalendarHTTPError(response.status_code)
        decoded = json.loads(data) if data else {}
        if not isinstance(decoded, dict):
            raise ValueError("provider returned an invalid object")
        return response.status_code, decoded


class GoogleCalendarBackend:
    def __init__(
        self, secrets: SecretStore, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.secrets = secrets
        self.transport = transport
        self._lock = asyncio.Lock()
        self._cache: dict[str, tuple[float, str]] = {}

    async def _token(self, reference: str) -> str:
        async with self._lock:
            raw = self.secrets.require(reference)
            credential = json.loads(raw)
            cached = self._cache.get(reference)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            async with httpx.AsyncClient(
                timeout=8, follow_redirects=False, trust_env=False, transport=self.transport
            ) as client:
                _, result = await bounded_request(
                    client,
                    "POST",
                    "https://oauth2.googleapis.com/token",
                    limit=65536,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": credential["refresh_token"],
                        "client_id": credential["client_id"],
                        "client_secret": credential["client_secret"],
                    },
                )
            token = result.get("access_token")
            if not isinstance(token, str) or not token or len(token) > 8192:
                raise ValueError("invalid refreshed credential")
            scope = result.get("scope", credential["scope"])
            if credential["scope"] not in scope.split():
                raise ValueError("calendar permission was revoked")
            if self.secrets.get(reference) != raw:
                raise ValueError("calendar credential changed during refresh")
            self._cache[reference] = (
                time.monotonic() + min(3000, max(0, int(result.get("expires_in", 0)) - 60)),
                token,
            )
            return token

    async def request(
        self,
        connection: dict[str, Any],
        method: str,
        *,
        event_id: str = "",
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        etag: str | None = None,
        max_bytes: int = 1048576,
    ) -> dict[str, Any]:
        async with asyncio.timeout(12):
            token = await self._token(connection["secret_ref"])
            self.secrets.require(connection["secret_ref"])  # Disconnect may happen during refresh.
            url = (
                "https://www.googleapis.com/calendar/v3/calendars/"
                + quote(connection["calendar_id"], safe="")
                + "/events"
            )
            if event_id:
                url += "/" + quote(event_id, safe="")
            headers = {"Authorization": "Bearer " + token}
            if etag:
                headers["If-Match"] = etag
            async with httpx.AsyncClient(
                timeout=8, follow_redirects=False, trust_env=False, transport=self.transport
            ) as client:
                _, data = await bounded_request(
                    client, method, url, headers=headers, params=params, json=body, limit=max_bytes
                )
            return data

    def forget(self, reference: str) -> None:
        self._cache.pop(reference, None)
