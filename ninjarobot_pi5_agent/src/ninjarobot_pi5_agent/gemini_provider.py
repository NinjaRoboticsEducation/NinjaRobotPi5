"""Google Gemini generateContent adapter for the provider-neutral agent boundary."""

from __future__ import annotations

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


class GeminiConfig(BaseModel):
    """Validated Gemini adapter configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model: str = "gemini-2.5-flash"
    base_url: HttpUrl = HttpUrl("https://generativelanguage.googleapis.com/v1beta")
    project_id: str | None = None
    max_output_tokens: int = Field(default=2048, ge=1, le=32768)

    @field_validator("base_url")
    @classmethod
    def cloud_endpoint_must_use_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("Gemini cloud endpoints must use HTTPS")
        if value.host != "generativelanguage.googleapis.com":
            raise ValueError(
                "Gemini credentials may be sent only to generativelanguage.googleapis.com"
            )
        return value


class GeminiProvider:
    """Translate provider-neutral requests to Gemini generateContent."""

    def __init__(
        self,
        config: GeminiConfig,
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
                self._model_path("generateContent"),
                headers=await self._headers(),
                json=self._payload(request),
                timeout=request.timeout_seconds,
            )
            payload = await checked_json(response, provider="Gemini")
        except httpx.HTTPError as exc:
            raise CloudUnavailableError(f"Gemini request failed: {type(exc).__name__}") from exc
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
        calls: list[ToolCall] = []
        usage: dict[str, Any] = {}
        finish_reason: str | None = None
        tool_names = wire_tool_map(tuple(tool.name for tool in request.tools))
        try:
            async with self._client.stream(
                "POST",
                self._model_path("streamGenerateContent"),
                params={"alt": "sse"},
                headers=await self._headers(),
                json=self._payload(request),
                timeout=request.timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    await checked_json(response, provider="Gemini")
                async for _event_name, payload in iter_sse_json(
                    response,
                    provider="Gemini",
                ):
                    chunk_text, chunk_calls, chunk_finish, chunk_usage = _response_parts(
                        request.request_id,
                        payload,
                        tool_names,
                        call_offset=len(calls),
                    )
                    if chunk_text:
                        text.append(chunk_text)
                        yield ModelStreamEvent(
                            request_id=request.request_id,
                            event=StreamEventType.TEXT_DELTA,
                            text=chunk_text,
                        )
                    calls.extend(chunk_calls)
                    finish_reason = chunk_finish or finish_reason
                    if chunk_usage:
                        usage = chunk_usage
        except httpx.HTTPError as exc:
            raise CloudUnavailableError(f"Gemini stream failed: {type(exc).__name__}") from exc
        turn = _turn(
            request.request_id,
            "".join(text),
            tuple(calls),
            finish_reason,
            usage,
        )
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.DONE,
            turn=turn,
        )

    async def health(self) -> ProviderHealth:
        self._ensure_open()
        try:
            entries = await self.list_models()
            available = {entry.name for entry in entries}
            if self.config.model.removeprefix("models/") in available:
                status = ProviderHealthStatus.READY
                detail = f"Gemini model '{self.config.model}' is available."
            else:
                status = ProviderHealthStatus.DEGRADED
                detail = f"Gemini model '{self.config.model}' is not available to this account."
        except Exception as exc:
            status = ProviderHealthStatus.UNAVAILABLE
            detail = f"Gemini is unavailable: {type(exc).__name__}"
        return ProviderHealth(
            provider="gemini",
            status=status,
            checked_at=datetime.now(UTC),
            detail=detail,
        )

    async def list_models(self) -> tuple[ModelCatalogEntry, ...]:
        self._ensure_open()
        entries: list[ModelCatalogEntry] = []
        page_token: str | None = None
        for _page in range(20):
            params = {"pageSize": "1000"}
            if page_token:
                params["pageToken"] = page_token
            try:
                response = await self._client.get(
                    "/models",
                    headers=await self._headers(),
                    params=params,
                    timeout=10.0,
                )
                payload = await checked_json(response, provider="Gemini")
            except httpx.HTTPError as exc:
                raise CloudUnavailableError(
                    f"Gemini model catalog failed: {type(exc).__name__}"
                ) from exc
            raw_models = payload.get("models")
            if not isinstance(raw_models, list):
                raise CloudProtocolError("Gemini model catalog is missing models")
            for item in raw_models:
                if not isinstance(item, dict):
                    continue
                methods = item.get("supportedGenerationMethods", [])
                name = item.get("name")
                if (
                    isinstance(name, str)
                    and isinstance(methods, list)
                    and "generateContent" in methods
                ):
                    entries.append(
                        ModelCatalogEntry(
                            provider="gemini",
                            name=name.removeprefix("models/"),
                            family="Gemini",
                        )
                    )
            next_token = payload.get("nextPageToken")
            if not isinstance(next_token, str) or not next_token:
                break
            page_token = next_token
        return tuple(sorted(entries, key=lambda entry: entry.name.casefold()))

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._client.aclose()

    async def _headers(self) -> dict[str, str]:
        headers = {
            **await self._credentials.headers(),
            "Content-Type": "application/json",
        }
        if self.config.project_id:
            headers["x-goog-user-project"] = self.config.project_id
        return headers

    def _payload(self, request: ModelRequest) -> dict[str, Any]:
        system_parts = [
            {"text": message.content}
            for message in request.messages
            if message.role is MessageRole.SYSTEM
        ]
        payload: dict[str, Any] = {
            "contents": _contents(request.messages),
            "generationConfig": {
                "maxOutputTokens": min(
                    request.max_output_tokens,
                    self.config.max_output_tokens,
                )
            },
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        if request.tools:
            payload["tools"] = [
                {"functionDeclarations": [_tool_payload(tool) for tool in request.tools]}
            ]
            payload["toolConfig"] = {
                "functionCallingConfig": {"mode": "AUTO"},
            }
        return payload

    def _model_path(self, action: str) -> str:
        model = self.config.model.removeprefix("models/")
        return f"/models/{model}:{action}"

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Gemini provider is closed")


def _contents(messages: tuple[ModelMessage, ...]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for message in messages:
        if message.role is MessageRole.SYSTEM:
            continue
        role = "model" if message.role is MessageRole.ASSISTANT else "user"
        parts: list[dict[str, Any]] = []
        if message.role is MessageRole.TOOL:
            parts.append(
                {
                    "functionResponse": {
                        "name": wire_tool_name(message.name or "unknown.tool"),
                        "response": tool_result_payload(message.content),
                    }
                }
            )
        else:
            if message.content:
                parts.append({"text": message.content})
            parts.extend(
                {
                    "functionCall": {
                        "name": wire_tool_name(call.name),
                        "args": call.arguments,
                    }
                }
                for call in message.tool_calls
            )
        if parts:
            contents.append({"role": role, "parts": parts})
    return contents


def _tool_payload(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "name": wire_tool_name(tool.name),
        "description": tool.description,
        "parametersJsonSchema": tool.input_schema,
    }


def _normalize_response(
    request_id: str,
    payload: dict[str, Any],
    tool_names: dict[str, str],
) -> ModelTurn:
    text, calls, finish_reason, usage = _response_parts(
        request_id,
        payload,
        tool_names,
        call_offset=0,
    )
    return _turn(request_id, text, calls, finish_reason, usage)


def _response_parts(
    request_id: str,
    payload: dict[str, Any],
    tool_names: dict[str, str],
    *,
    call_offset: int,
) -> tuple[str, tuple[ToolCall, ...], str | None, dict[str, Any]]:
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        raise CloudProtocolError("Gemini candidates must be a list")
    text: list[str] = []
    calls: list[ToolCall] = []
    finish_reason: str | None = None
    if candidates:
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise CloudProtocolError("Gemini candidate must be an object")
        raw_finish = candidate.get("finishReason")
        finish_reason = raw_finish if isinstance(raw_finish, str) else None
        content = candidate.get("content", {})
        if not isinstance(content, dict):
            raise CloudProtocolError("Gemini candidate content must be an object")
        parts = content.get("parts", [])
        if not isinstance(parts, list):
            raise CloudProtocolError("Gemini content parts must be a list")
        for part in parts:
            if not isinstance(part, dict):
                continue
            value = part.get("text")
            if isinstance(value, str):
                text.append(value)
            function_call = part.get("functionCall")
            if isinstance(function_call, dict):
                arguments = function_call.get("args", {})
                if not isinstance(arguments, dict):
                    raise CloudProtocolError("Gemini function arguments must be an object")
                call_id = function_call.get("id")
                if not isinstance(call_id, str) or not call_id:
                    call_id = f"gemini-{request_id}-{call_offset + len(calls)}"
                calls.append(
                    ToolCall(
                        call_id=call_id,
                        name=canonical_tool_name(
                            function_call.get("name"),
                            tool_names,
                            provider="Gemini",
                        ),
                        arguments=arguments,
                    )
                )
    raw_usage = payload.get("usageMetadata", {})
    usage = raw_usage if isinstance(raw_usage, dict) else {}
    return "".join(text), tuple(calls), finish_reason, usage


def _turn(
    request_id: str,
    text: str,
    calls: tuple[ToolCall, ...],
    provider_finish: str | None,
    usage: dict[str, Any],
) -> ModelTurn:
    finish_reason = (
        FinishReason.TOOL_CALLS
        if calls
        else FinishReason.LENGTH
        if provider_finish == "MAX_TOKENS"
        else FinishReason.STOP
    )
    return ModelTurn(
        request_id=request_id,
        text=text,
        tool_calls=calls,
        finish_reason=finish_reason,
        input_tokens=_nonnegative_int(usage.get("promptTokenCount")),
        output_tokens=_nonnegative_int(usage.get("candidatesTokenCount")),
    )


def _nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
