"""Bounded local Ollama provider adapter for Raspberry Pi 5."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from .models import (
    FinishReason,
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


class OllamaError(RuntimeError):
    """Base error for local provider failures."""


class OllamaUnavailableError(OllamaError):
    """Raised when the local Ollama service or model is unavailable."""


class OllamaProtocolError(OllamaError):
    """Raised when Ollama returns malformed provider data."""


class OllamaConfig(BaseModel):
    """Pi-oriented local model settings with bounded memory and output."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    base_url: str = "http://127.0.0.1:11434"
    model: Annotated[str, StringConstraints(min_length=1, max_length=100)] = "qwen3:4b"
    context_window: Annotated[int, Field(ge=1024, le=16_384)] = 4096
    max_output_tokens: Annotated[int, Field(ge=32, le=4096)] = 512
    temperature: Annotated[float, Field(ge=0, le=1)] = 0.1
    keep_alive: Annotated[str, StringConstraints(min_length=1, max_length=20)] = "30m"
    think: bool = False
    seed: int = 42

    @field_validator("base_url")
    @classmethod
    def base_url_must_be_local_http(cls, value: str) -> str:
        """Keep the default provider local to the Raspberry Pi."""
        parsed = urlparse(value)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Ollama base_url must be a local HTTP address")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Ollama base_url must not contain credentials")
        return value.rstrip("/")


class OllamaProvider:
    """Normalize Ollama chat, native tools, streaming, usage, and health."""

    def __init__(
        self,
        config: OllamaConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or OllamaConfig()
        self._client = client or httpx.AsyncClient(base_url=self.config.base_url)
        self._owns_client = client is None
        self._closed = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Describe the tested Ollama adapter surface."""
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
        """Generate one complete turn under the request timeout."""
        self._ensure_open()
        try:
            response = await self._client.post(
                "/api/chat",
                json=self._payload(request, stream=False),
                timeout=request.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise OllamaUnavailableError(f"Ollama request failed: {type(exc).__name__}") from exc
        if not isinstance(payload, dict):
            raise OllamaProtocolError("Ollama response must be a JSON object")
        return self._normalize_turn(request.request_id, payload)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        """Yield private activity, text deltas, then one normalized turn."""
        self._ensure_open()
        accumulated_text: list[str] = []
        accumulated_calls: list[dict[str, Any]] = []
        final_payload: dict[str, Any] | None = None
        try:
            async with self._client.stream(
                "POST",
                "/api/chat",
                json=self._payload(request, stream=True),
                timeout=request.timeout_seconds,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    decoded = json.loads(line)
                    if not isinstance(decoded, dict):
                        raise OllamaProtocolError("Ollama stream item must be an object")
                    message = decoded.get("message", {})
                    if not isinstance(message, dict):
                        raise OllamaProtocolError("Ollama stream message must be an object")
                    content = message.get("content", "")
                    if not isinstance(content, str):
                        raise OllamaProtocolError("Ollama stream content must be text")
                    thinking = message.get("thinking", "")
                    if not isinstance(thinking, str):
                        raise OllamaProtocolError("Ollama stream thinking must be text")
                    if thinking:
                        yield ModelStreamEvent(
                            request_id=request.request_id,
                            event=StreamEventType.ACTIVITY,
                        )
                    if content:
                        accumulated_text.append(content)
                        yield ModelStreamEvent(
                            request_id=request.request_id,
                            event=StreamEventType.TEXT_DELTA,
                            text=content,
                        )
                    raw_calls = message.get("tool_calls", [])
                    if raw_calls:
                        if not isinstance(raw_calls, list):
                            raise OllamaProtocolError("Ollama tool_calls must be a list")
                        accumulated_calls.extend(raw_calls)
                        if not content:
                            yield ModelStreamEvent(
                                request_id=request.request_id,
                                event=StreamEventType.ACTIVITY,
                            )
                    if decoded.get("done") is True:
                        final_payload = decoded
                        break
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise OllamaUnavailableError(f"Ollama stream failed: {type(exc).__name__}") from exc
        if final_payload is None:
            raise OllamaProtocolError("Ollama stream ended without a done event")
        final_payload["message"] = {
            "role": "assistant",
            "content": "".join(accumulated_text),
            "tool_calls": accumulated_calls,
        }
        turn = self._normalize_turn(request.request_id, final_payload)
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.DONE,
            turn=turn,
        )

    async def health(self) -> ProviderHealth:
        """Check service reachability and whether the configured model is installed."""
        self._ensure_open()
        try:
            response = await self._client.get("/api/tags", timeout=5.0)
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models", []) if isinstance(payload, dict) else []
            installed = {
                item.get("name") or item.get("model") for item in models if isinstance(item, dict)
            }
            if self.config.model in installed:
                status = ProviderHealthStatus.READY
                detail = f"Local model '{self.config.model}' is installed."
            else:
                status = ProviderHealthStatus.DEGRADED
                detail = f"Local model '{self.config.model}' is not installed."
        except (httpx.HTTPError, json.JSONDecodeError):
            status = ProviderHealthStatus.UNAVAILABLE
            detail = "The local Ollama service is unavailable."
        return ProviderHealth(
            provider="ollama",
            status=status,
            checked_at=datetime.now(UTC),
            detail=detail,
        )

    async def close(self) -> None:
        """Release the owned HTTP client once."""
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._client.aclose()

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        max_output = min(request.max_output_tokens, self.config.max_output_tokens)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [_message_payload(message) for message in request.messages],
            "stream": stream,
            "think": self.config.think,
            "keep_alive": self.config.keep_alive,
            "options": {
                "num_ctx": self.config.context_window,
                "num_predict": max_output,
                "temperature": self.config.temperature,
                "seed": self.config.seed,
            },
        }
        if request.tools:
            payload["tools"] = [_tool_payload(tool) for tool in request.tools]
        return payload

    @staticmethod
    def _normalize_turn(request_id: str, payload: dict[str, Any]) -> ModelTurn:
        message = payload.get("message")
        if not isinstance(message, dict):
            raise OllamaProtocolError("Ollama response is missing message")
        content = message.get("content", "")
        if not isinstance(content, str):
            raise OllamaProtocolError("Ollama response content must be text")
        calls = _normalize_tool_calls(request_id, message.get("tool_calls", []))
        done_reason = payload.get("done_reason")
        if calls:
            finish_reason = FinishReason.TOOL_CALLS
        elif done_reason == "length":
            finish_reason = FinishReason.LENGTH
        else:
            finish_reason = FinishReason.STOP
        diagnostics: dict[str, Any] = {}
        for field in (
            "total_duration",
            "load_duration",
            "prompt_eval_duration",
            "eval_duration",
        ):
            value = payload.get(field)
            if isinstance(value, int) and not isinstance(value, bool):
                diagnostics[f"{field}_seconds"] = value / 1_000_000_000
        return ModelTurn(
            request_id=request_id,
            text=content,
            tool_calls=calls,
            finish_reason=finish_reason,
            input_tokens=_optional_nonnegative_int(payload.get("prompt_eval_count")),
            output_tokens=_optional_nonnegative_int(payload.get("eval_count")),
            diagnostics=diagnostics,
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Ollama provider is closed")


def _message_payload(message: ModelMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": message.role.value,
        "content": message.content,
    }
    if message.name is not None:
        payload["tool_name"] = message.name
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": call.arguments,
                },
            }
            for call in message.tool_calls
        ]
    return payload


def _tool_payload(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


def _normalize_tool_calls(request_id: str, raw_calls: Any) -> tuple[ToolCall, ...]:
    if raw_calls in (None, []):
        return ()
    if not isinstance(raw_calls, list):
        raise OllamaProtocolError("Ollama tool_calls must be a list")
    normalized: list[ToolCall] = []
    for index, raw_call in enumerate(raw_calls, start=1):
        if not isinstance(raw_call, dict) or not isinstance(raw_call.get("function"), dict):
            raise OllamaProtocolError("Ollama tool call is malformed")
        function = raw_call["function"]
        name = function.get("name")
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise OllamaProtocolError("Ollama tool arguments are invalid JSON") from exc
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise OllamaProtocolError("Ollama tool call name or arguments are malformed")
        normalized.append(
            ToolCall(
                call_id=f"{request_id}-tool-{index}",
                name=name,
                arguments=arguments,
            )
        )
    return tuple(normalized)


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None
