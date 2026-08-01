"""Shared cloud-provider authentication, transport, and normalization helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .secrets import SecretStore


class CloudProviderError(RuntimeError):
    """Base class for safe cloud-provider errors."""


class CloudAuthenticationError(CloudProviderError):
    """Cloud credentials are absent, invalid, or unsupported."""


class CloudUnavailableError(CloudProviderError):
    """The provider could not be reached or rejected the request."""


class CloudProtocolError(CloudProviderError):
    """The provider returned a response that violates its documented schema."""


class CredentialSource(Protocol):
    """Resolve request headers without exposing credentials to configuration."""

    async def headers(self) -> dict[str, str]:
        """Return authentication headers for one request."""

    def status(self) -> dict[str, object]:
        """Return non-secret credential metadata."""


@dataclass(frozen=True, slots=True)
class APIKeyCredential:
    """Read an API key from the owner-private secret store or environment."""

    store: SecretStore
    environment_name: str
    header_name: str
    prefix: str = ""

    async def headers(self) -> dict[str, str]:
        try:
            value = self.store.require(self.environment_name)
        except KeyError as exc:
            raise CloudAuthenticationError(str(exc).strip("'")) from exc
        return {self.header_name: f"{self.prefix}{value}"}

    def status(self) -> dict[str, object]:
        return {
            "method": "api_key",
            "environment_name": self.environment_name,
            "configured": self.store.contains(self.environment_name),
        }


HeaderProvider = Callable[[], Awaitable[dict[str, str]]]


async def checked_json(response: httpx.Response, *, provider: str) -> dict[str, Any]:
    """Validate an HTTP response without echoing a secret-bearing response body."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if response.status_code in {401, 403}:
            raise CloudAuthenticationError(
                f"{provider} rejected the configured credentials"
            ) from exc
        if response.status_code == 429:
            raise CloudUnavailableError(
                f"{provider} rate limit or account quota was reached"
            ) from exc
        raise CloudUnavailableError(
            f"{provider} request failed with HTTP {response.status_code}"
        ) from exc
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise CloudProtocolError(f"{provider} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise CloudProtocolError(f"{provider} response must be a JSON object")
    return payload


async def iter_sse_json(
    response: httpx.Response,
    *,
    provider: str,
) -> AsyncIterator[tuple[str | None, dict[str, Any]]]:
    """Yield validated JSON objects from a Server-Sent Events response."""
    event_name: str | None = None
    data_lines: list[str] = []
    async for line in response.aiter_lines():
        if not line:
            if data_lines:
                data = "\n".join(data_lines)
                data_lines.clear()
                if data != "[DONE]":
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise CloudProtocolError(
                            f"{provider} stream returned invalid JSON"
                        ) from exc
                    if not isinstance(payload, dict):
                        raise CloudProtocolError(f"{provider} stream event must be a JSON object")
                    yield event_name, payload
            event_name = None
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        try:
            payload = json.loads("\n".join(data_lines))
        except json.JSONDecodeError as exc:
            raise CloudProtocolError(f"{provider} stream returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise CloudProtocolError(f"{provider} stream event must be a JSON object")
        yield event_name, payload


def parse_json_arguments(value: object, *, provider: str) -> dict[str, Any]:
    """Normalize provider tool arguments to one strict object."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise CloudProtocolError(f"{provider} tool arguments must be a JSON object")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CloudProtocolError(f"{provider} tool arguments contain invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise CloudProtocolError(f"{provider} tool arguments must decode to an object")
    return decoded


def tool_result_payload(content: str) -> object:
    """Preserve structured tool results when they contain valid JSON."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"text": content}


def wire_tool_name(name: str) -> str:
    """Create a provider-safe, bounded alias for one canonical tool name."""
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]
    return f"nrt_{digest}"


def wire_tool_map(names: tuple[str, ...]) -> dict[str, str]:
    """Map provider wire aliases back to canonical registry names."""
    mapping = {wire_tool_name(name): name for name in names}
    if len(mapping) != len(names):
        raise ValueError("tool wire-name collision")
    return mapping


def canonical_tool_name(
    wire_name: object,
    mapping: dict[str, str],
    *,
    provider: str,
) -> str:
    """Reject unknown provider tool names before they reach the policy engine."""
    if not isinstance(wire_name, str):
        raise CloudProtocolError(f"{provider} tool call is missing its name")
    try:
        return mapping[wire_name]
    except KeyError as exc:
        raise CloudProtocolError(f"{provider} requested an unknown tool alias") from exc
