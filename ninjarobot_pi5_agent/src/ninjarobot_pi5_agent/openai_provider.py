"""OpenAI Responses API adapter for the provider-neutral agent boundary."""

from __future__ import annotations

from collections import OrderedDict
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
    parse_json_arguments,
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


class OpenAIConfig(BaseModel):
    """Validated OpenAI adapter configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model: str = "gpt-5-mini"
    base_url: HttpUrl = HttpUrl("https://api.openai.com/v1")
    max_output_tokens: int = Field(default=2048, ge=1, le=32768)

    @field_validator("base_url")
    @classmethod
    def official_endpoint_must_use_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("OpenAI cloud endpoints must use HTTPS")
        if value.host != "api.openai.com":
            raise ValueError("OpenAI credentials may be sent only to api.openai.com")
        return value


class OpenAIProvider:
    """Translate provider-neutral requests to the OpenAI Responses API."""

    def __init__(
        self,
        config: OpenAIConfig,
        credentials: CredentialSource,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._credentials = credentials
        self._client = client or httpx.AsyncClient(base_url=str(config.base_url).rstrip("/"))
        self._owns_client = client is None
        self._reasoning_by_session: OrderedDict[str, tuple[dict[str, Any], ...]] = OrderedDict()
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
                "/responses",
                headers=await self._headers(),
                json=self._payload(request, stream=False),
                timeout=request.timeout_seconds,
            )
            payload = await checked_json(response, provider="OpenAI")
        except httpx.HTTPError as exc:
            raise CloudUnavailableError(f"OpenAI request failed: {type(exc).__name__}") from exc
        self._remember_reasoning(request.session_id, payload)
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
        completed: dict[str, Any] | None = None
        tool_names = wire_tool_map(tuple(tool.name for tool in request.tools))
        try:
            async with self._client.stream(
                "POST",
                "/responses",
                headers=await self._headers(),
                json=self._payload(request, stream=True),
                timeout=request.timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    await checked_json(response, provider="OpenAI")
                async for event_name, payload in iter_sse_json(
                    response,
                    provider="OpenAI",
                ):
                    event_type = str(payload.get("type") or event_name or "")
                    if event_type == "response.output_text.delta":
                        delta = payload.get("delta")
                        if isinstance(delta, str) and delta:
                            yield ModelStreamEvent(
                                request_id=request.request_id,
                                event=StreamEventType.TEXT_DELTA,
                                text=delta,
                            )
                    elif event_type == "response.completed":
                        raw_response = payload.get("response")
                        if isinstance(raw_response, dict):
                            completed = raw_response
                    elif event_type in {"error", "response.failed", "response.incomplete"}:
                        raise CloudUnavailableError(f"OpenAI stream ended with {event_type}")
        except httpx.HTTPError as exc:
            raise CloudUnavailableError(f"OpenAI stream failed: {type(exc).__name__}") from exc
        if completed is None:
            raise CloudProtocolError("OpenAI stream ended without response.completed")
        self._remember_reasoning(request.session_id, completed)
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.DONE,
            turn=_normalize_response(request.request_id, completed, tool_names),
        )

    async def health(self) -> ProviderHealth:
        self._ensure_open()
        try:
            entries = await self.list_models()
            available = {entry.name for entry in entries}
            if self.config.model in available:
                status = ProviderHealthStatus.READY
                detail = f"OpenAI model '{self.config.model}' is available."
            else:
                status = ProviderHealthStatus.DEGRADED
                detail = f"OpenAI model '{self.config.model}' is not available to this account."
        except Exception as exc:
            status = ProviderHealthStatus.UNAVAILABLE
            detail = f"OpenAI is unavailable: {type(exc).__name__}"
        return ProviderHealth(
            provider="openai",
            status=status,
            checked_at=datetime.now(UTC),
            detail=detail,
        )

    async def list_models(self) -> tuple[ModelCatalogEntry, ...]:
        self._ensure_open()
        try:
            response = await self._client.get(
                "/models",
                headers=await self._headers(),
                timeout=10.0,
            )
            payload = await checked_json(response, provider="OpenAI")
        except httpx.HTTPError as exc:
            raise CloudUnavailableError(
                f"OpenAI model catalog failed: {type(exc).__name__}"
            ) from exc
        raw_models = payload.get("data")
        if not isinstance(raw_models, list):
            raise CloudProtocolError("OpenAI model catalog is missing data")
        entries = [
            ModelCatalogEntry(
                provider="openai",
                name=model_id,
                family="OpenAI",
            )
            for item in raw_models
            if isinstance(item, dict)
            and isinstance((model_id := item.get("id")), str)
            and _is_chat_model(model_id)
        ]
        return tuple(sorted(entries, key=lambda entry: entry.name.casefold()))

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._client.aclose()
        self._reasoning_by_session.clear()

    async def _headers(self) -> dict[str, str]:
        return {
            **await self._credentials.headers(),
            "Content-Type": "application/json",
        }

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "input": _input_items(
                request.messages,
                reasoning_items=self._reasoning_by_session.get(request.session_id, ()),
            ),
            "max_output_tokens": min(
                request.max_output_tokens,
                self.config.max_output_tokens,
            ),
            "store": False,
            "stream": stream,
            "parallel_tool_calls": False,
            "include": ["reasoning.encrypted_content"],
        }
        if request.tools:
            payload["tools"] = [_tool_payload(tool) for tool in request.tools]
        return payload

    def _remember_reasoning(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        output = payload.get("output", [])
        if not isinstance(output, list):
            return
        has_function_call = any(
            isinstance(item, dict) and item.get("type") == "function_call" for item in output
        )
        reasoning = tuple(
            dict(item)
            for item in output
            if isinstance(item, dict)
            and item.get("type") == "reasoning"
            and isinstance(item.get("encrypted_content"), str)
        )
        if not has_function_call or not reasoning:
            self._reasoning_by_session.pop(session_id, None)
            return
        self._reasoning_by_session[session_id] = reasoning
        self._reasoning_by_session.move_to_end(session_id)
        while len(self._reasoning_by_session) > 64:
            self._reasoning_by_session.popitem(last=False)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("OpenAI provider is closed")


def _input_items(
    messages: tuple[ModelMessage, ...],
    *,
    reasoning_items: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    inserted_reasoning = False
    for message in messages:
        if message.role is MessageRole.TOOL:
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": message.tool_call_id,
                    "output": message.content,
                }
            )
            continue
        if message.content:
            items.append(
                {
                    "role": message.role.value,
                    "content": message.content,
                }
            )
        if message.tool_calls and reasoning_items and not inserted_reasoning:
            items.extend(dict(item) for item in reasoning_items)
            inserted_reasoning = True
        for call in message.tool_calls:
            items.append(
                {
                    "type": "function_call",
                    "call_id": call.call_id,
                    "name": wire_tool_name(call.name),
                    "arguments": _json_dumps(call.arguments),
                }
            )
    return items


def _tool_payload(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "name": wire_tool_name(tool.name),
        "description": tool.description,
        "parameters": tool.input_schema,
        "strict": _strict_schema_compatible(tool.input_schema),
    }


def _normalize_response(
    request_id: str,
    payload: dict[str, Any],
    tool_names: dict[str, str],
) -> ModelTurn:
    output = payload.get("output", [])
    if not isinstance(output, list):
        raise CloudProtocolError("OpenAI response output must be a list")
    text: list[str] = []
    calls: list[ToolCall] = []
    for index, item in enumerate(output):
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "message":
            content = item.get("content", [])
            if not isinstance(content, list):
                raise CloudProtocolError("OpenAI message content must be a list")
            for part in content:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    value = part.get("text")
                    if isinstance(value, str):
                        text.append(value)
        elif item_type == "function_call":
            call_id = item.get("call_id")
            if not isinstance(call_id, str):
                raise CloudProtocolError("OpenAI function call is missing name or call_id")
            calls.append(
                ToolCall(
                    call_id=call_id,
                    name=canonical_tool_name(
                        item.get("name"),
                        tool_names,
                        provider="OpenAI",
                    ),
                    arguments=parse_json_arguments(item.get("arguments"), provider="OpenAI"),
                )
            )
    status = payload.get("status")
    finish_reason = (
        FinishReason.TOOL_CALLS
        if calls
        else FinishReason.LENGTH
        if status == "incomplete"
        else FinishReason.STOP
    )
    usage = payload.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    diagnostics: dict[str, Any] = {}
    response_id = payload.get("id")
    if isinstance(response_id, str):
        diagnostics["response_id"] = response_id
    return ModelTurn(
        request_id=request_id,
        text="".join(text),
        tool_calls=tuple(calls),
        finish_reason=finish_reason,
        input_tokens=_nonnegative_int(usage.get("input_tokens")),
        output_tokens=_nonnegative_int(usage.get("output_tokens")),
        diagnostics=diagnostics,
    )


def _is_chat_model(model_id: str) -> bool:
    excluded = (
        "audio",
        "embedding",
        "image",
        "moderation",
        "realtime",
        "search",
        "transcribe",
        "tts",
    )
    lowered = model_id.casefold()
    return model_id.startswith(("gpt-", "o1", "o3", "o4", "o5")) and not any(
        marker in lowered for marker in excluded
    )


def _strict_schema_compatible(schema: object) -> bool:
    if not isinstance(schema, dict):
        return False
    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if (
            not isinstance(properties, dict)
            or not isinstance(required, list)
            or schema.get("additionalProperties") is not False
            or set(properties) != set(required)
        ):
            return False
        return all(_strict_schema_compatible(value) for value in properties.values())
    if schema_type == "array":
        return _strict_schema_compatible(schema.get("items"))
    alternatives = schema.get("anyOf")
    if isinstance(alternatives, list):
        return all(_strict_schema_compatible(value) for value in alternatives)
    return isinstance(schema_type, str)


def _nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _json_dumps(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True, ensure_ascii=False)
