"""Anthropic Messages API adapter for the provider-neutral agent boundary."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .cloud_common import (
    CloudProtocolError,
    CloudUnavailableError,
    CredentialSource,
    canonical_tool_name,
    checked_json,
    iter_sse_json,
    tool_result_payload,
    wire_tool_map,
    wire_tool_name,
)
from .model_selection import ModelCatalogEntry
from .models import (
    FinishReason,
    MessageRole,
    ModelMessage,
    ModelRequest,
    ModelStreamEvent,
    ModelTurn,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthStatus,
    StreamEventType,
    ToolCall,
    ToolDefinition,
)


class AnthropicConfig(BaseModel):
    """Validated Anthropic adapter configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model: str = "claude-sonnet-4-5"
    base_url: HttpUrl = HttpUrl("https://api.anthropic.com/v1")
    max_output_tokens: int = Field(default=2048, ge=1, le=32768)

    @field_validator("base_url")
    @classmethod
    def cloud_endpoint_must_use_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("Anthropic cloud endpoints must use HTTPS")
        if value.host != "api.anthropic.com":
            raise ValueError("Anthropic credentials may be sent only to api.anthropic.com")
        return value


class AnthropicProvider:
    """Translate provider-neutral requests to Anthropic Messages."""

    def __init__(
        self,
        config: AnthropicConfig,
        credentials: CredentialSource,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._credentials = credentials
        self._client = client or httpx.AsyncClient(base_url=str(config.base_url).rstrip("/"))
        self._owns_client = client is None
        self._closed = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tools=True,
            streaming=True,
            images=False,
            audio=False,
            structured_output=True,
            usage_reporting=True,
            provider_conversation_state=False,
        )

    async def generate(self, request: ModelRequest) -> ModelTurn:
        self._ensure_open()
        try:
            response = await self._client.post(
                "/messages",
                headers=await self._headers(),
                json=self._payload(request, stream=False),
                timeout=request.timeout_seconds,
            )
            payload = await checked_json(response, provider="Anthropic")
        except httpx.HTTPError as exc:
            raise CloudUnavailableError(f"Anthropic request failed: {type(exc).__name__}") from exc
        return _normalize_response(
            request.request_id,
            payload,
            wire_tool_map(tuple(tool.name for tool in request.tools)),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        self._ensure_open()
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.ACTIVITY,
        )
        text: list[str] = []
        blocks: dict[int, dict[str, Any]] = {}
        calls: list[ToolCall] = []
        input_tokens: int | None = None
        output_tokens: int | None = None
        stop_reason: str | None = None
        tool_names = wire_tool_map(tuple(tool.name for tool in request.tools))
        try:
            async with self._client.stream(
                "POST",
                "/messages",
                headers=await self._headers(),
                json=self._payload(request, stream=True),
                timeout=request.timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    await checked_json(response, provider="Anthropic")
                async for event_name, payload in iter_sse_json(
                    response,
                    provider="Anthropic",
                ):
                    event_type = str(payload.get("type") or event_name or "")
                    if event_type == "message_start":
                        message = payload.get("message", {})
                        if isinstance(message, dict):
                            usage = message.get("usage", {})
                            if isinstance(usage, dict):
                                input_tokens = _nonnegative_int(usage.get("input_tokens"))
                    elif event_type == "content_block_start":
                        index = payload.get("index")
                        block = payload.get("content_block")
                        if isinstance(index, int) and isinstance(block, dict):
                            blocks[index] = dict(block)
                            blocks[index]["partial_json"] = ""
                    elif event_type == "content_block_delta":
                        index = payload.get("index")
                        delta = payload.get("delta")
                        if not isinstance(index, int) or not isinstance(delta, dict):
                            continue
                        delta_type = delta.get("type")
                        if delta_type == "text_delta":
                            value = delta.get("text")
                            if isinstance(value, str) and value:
                                text.append(value)
                                yield ModelStreamEvent(
                                    request_id=request.request_id,
                                    event=StreamEventType.TEXT_DELTA,
                                    text=value,
                                )
                        elif delta_type == "input_json_delta":
                            partial = delta.get("partial_json")
                            block = blocks.get(index)
                            if isinstance(partial, str) and block is not None:
                                block["partial_json"] = str(block.get("partial_json", "")) + partial
                    elif event_type == "content_block_stop":
                        index = payload.get("index")
                        block = blocks.get(index) if isinstance(index, int) else None
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            calls.append(_stream_tool_call(block, tool_names))
                    elif event_type == "message_delta":
                        delta = payload.get("delta", {})
                        if isinstance(delta, dict) and isinstance(delta.get("stop_reason"), str):
                            stop_reason = delta["stop_reason"]
                        usage = payload.get("usage", {})
                        if isinstance(usage, dict):
                            output_tokens = _nonnegative_int(usage.get("output_tokens"))
                    elif event_type == "error":
                        raise CloudUnavailableError("Anthropic stream returned an error")
        except httpx.HTTPError as exc:
            raise CloudUnavailableError(f"Anthropic stream failed: {type(exc).__name__}") from exc
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.DONE,
            turn=_turn(
                request.request_id,
                "".join(text),
                tuple(calls),
                stop_reason,
                input_tokens,
                output_tokens,
            ),
        )

    async def health(self) -> ProviderHealth:
        self._ensure_open()
        try:
            entries = await self.list_models()
            available = {entry.name for entry in entries}
            if self.config.model in available:
                status = ProviderHealthStatus.READY
                detail = f"Anthropic model '{self.config.model}' is available."
            else:
                status = ProviderHealthStatus.DEGRADED
                detail = f"Anthropic model '{self.config.model}' is not available to this account."
        except Exception as exc:
            status = ProviderHealthStatus.UNAVAILABLE
            detail = f"Anthropic is unavailable: {type(exc).__name__}"
        return ProviderHealth(
            provider="anthropic",
            status=status,
            checked_at=datetime.now(UTC),
            detail=detail,
        )

    async def list_models(self) -> tuple[ModelCatalogEntry, ...]:
        self._ensure_open()
        entries: list[ModelCatalogEntry] = []
        after_id: str | None = None
        for _page in range(20):
            params: dict[str, str] = {"limit": "1000"}
            if after_id:
                params["after_id"] = after_id
            try:
                response = await self._client.get(
                    "/models",
                    headers=await self._headers(),
                    params=params,
                    timeout=10.0,
                )
                payload = await checked_json(response, provider="Anthropic")
            except httpx.HTTPError as exc:
                raise CloudUnavailableError(
                    f"Anthropic model catalog failed: {type(exc).__name__}"
                ) from exc
            raw_models = payload.get("data")
            if not isinstance(raw_models, list):
                raise CloudProtocolError("Anthropic model catalog is missing data")
            for item in raw_models:
                if not isinstance(item, dict):
                    continue
                model_id = item.get("id")
                if isinstance(model_id, str):
                    display_name = item.get("display_name")
                    entries.append(
                        ModelCatalogEntry(
                            provider="anthropic",
                            name=model_id,
                            family=(display_name if isinstance(display_name, str) else "Claude"),
                        )
                    )
            if payload.get("has_more") is not True or not raw_models:
                break
            last = raw_models[-1]
            after_id = last.get("id") if isinstance(last, dict) else None
            if not isinstance(after_id, str):
                break
        return tuple(sorted(entries, key=lambda entry: entry.name.casefold()))

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._client.aclose()

    async def _headers(self) -> dict[str, str]:
        return {
            **await self._credentials.headers(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        systems = [
            message.content for message in request.messages if message.role is MessageRole.SYSTEM
        ]
        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": min(
                request.max_output_tokens,
                self.config.max_output_tokens,
            ),
            "messages": _messages(request.messages),
            "stream": stream,
        }
        if systems:
            payload["system"] = "\n\n".join(systems)
        if request.tools:
            payload["tools"] = [_tool_payload(tool) for tool in request.tools]
            payload["tool_choice"] = {"type": "auto"}
        return payload

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Anthropic provider is closed")


def _messages(messages: tuple[ModelMessage, ...]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in messages:
        if message.role is MessageRole.SYSTEM:
            continue
        role = "assistant" if message.role is MessageRole.ASSISTANT else "user"
        content: list[dict[str, Any]] = []
        if message.role is MessageRole.TOOL:
            content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": json.dumps(
                        tool_result_payload(message.content),
                        sort_keys=True,
                        ensure_ascii=False,
                    ),
                }
            )
        else:
            if message.content:
                content.append({"type": "text", "text": message.content})
            content.extend(
                {
                    "type": "tool_use",
                    "id": call.call_id,
                    "name": wire_tool_name(call.name),
                    "input": call.arguments,
                }
                for call in message.tool_calls
            )
        if content:
            result.append({"role": role, "content": content})
    return result


def _tool_payload(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "name": wire_tool_name(tool.name),
        "description": tool.description,
        "input_schema": tool.input_schema,
    }


def _normalize_response(
    request_id: str,
    payload: dict[str, Any],
    tool_names: dict[str, str],
) -> ModelTurn:
    content = payload.get("content", [])
    if not isinstance(content, list):
        raise CloudProtocolError("Anthropic content must be a list")
    text: list[str] = []
    calls: list[ToolCall] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            value = block.get("text")
            if isinstance(value, str):
                text.append(value)
        elif block.get("type") == "tool_use":
            call_id = block.get("id")
            arguments = block.get("input")
            if not isinstance(call_id, str) or not isinstance(arguments, dict):
                raise CloudProtocolError("Anthropic tool use is missing id or input")
            calls.append(
                ToolCall(
                    call_id=call_id,
                    name=canonical_tool_name(
                        block.get("name"),
                        tool_names,
                        provider="Anthropic",
                    ),
                    arguments=arguments,
                )
            )
    usage = payload.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    stop_reason = payload.get("stop_reason")
    return _turn(
        request_id,
        "".join(text),
        tuple(calls),
        stop_reason if isinstance(stop_reason, str) else None,
        _nonnegative_int(usage.get("input_tokens")),
        _nonnegative_int(usage.get("output_tokens")),
    )


def _stream_tool_call(
    block: dict[str, Any],
    tool_names: dict[str, str],
) -> ToolCall:
    call_id = block.get("id")
    if not isinstance(call_id, str):
        raise CloudProtocolError("Anthropic streamed tool use is missing id")
    raw_arguments = block.get("partial_json")
    if isinstance(raw_arguments, str) and raw_arguments:
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise CloudProtocolError(
                "Anthropic streamed tool arguments contain invalid JSON"
            ) from exc
    else:
        arguments = block.get("input", {})
    if not isinstance(arguments, dict):
        raise CloudProtocolError("Anthropic streamed tool arguments must be an object")
    return ToolCall(
        call_id=call_id,
        name=canonical_tool_name(block.get("name"), tool_names, provider="Anthropic"),
        arguments=arguments,
    )


def _turn(
    request_id: str,
    text: str,
    calls: tuple[ToolCall, ...],
    provider_finish: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
) -> ModelTurn:
    finish_reason = (
        FinishReason.TOOL_CALLS
        if calls
        else FinishReason.LENGTH
        if provider_finish == "max_tokens"
        else FinishReason.STOP
    )
    return ModelTurn(
        request_id=request_id,
        text=text,
        tool_calls=calls,
        finish_reason=finish_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
