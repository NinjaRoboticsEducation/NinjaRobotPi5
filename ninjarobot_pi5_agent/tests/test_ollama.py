from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from ninjarobot_pi5_agent import (
    FinishReason,
    MessageRole,
    ModelMessage,
    ModelRequest,
    OllamaConfig,
    OllamaProtocolError,
    OllamaProvider,
    ProviderHealthStatus,
    StreamEventType,
    ToolDefinition,
)
from ninjarobot_pi5_ide import RiskLevel


def tool() -> ToolDefinition:
    return ToolDefinition(
        name="robot.distance.read",
        version="1.0.0",
        description="Read forward distance.",
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={"type": "object"},
        risk=RiskLevel.READ_ONLY,
        default_timeout_seconds=2.0,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
    )


def request(*, tools: tuple[ToolDefinition, ...] = ()) -> ModelRequest:
    return ModelRequest(
        request_id="request-1",
        session_id="session-1",
        messages=(ModelMessage(role=MessageRole.USER, content="Check distance"),),
        tools=tools,
        max_output_tokens=1000,
        timeout_seconds=5.0,
    )


def test_ollama_generate_normalizes_native_tool_call_and_bounds_options() -> None:
    async def exercise() -> None:
        captured: dict[str, object] = {}

        def handler(http_request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(http_request.content))
            return httpx.Response(
                200,
                json={
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "robot.distance.read",
                                    "arguments": {},
                                }
                            }
                        ],
                    },
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 15,
                    "eval_count": 7,
                    "load_duration": 2_000_000_000,
                },
            )

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://127.0.0.1:11434",
        )
        provider = OllamaProvider(OllamaConfig(max_output_tokens=512), client=client)

        turn = await provider.generate(request(tools=(tool(),)))

        assert turn.finish_reason is FinishReason.TOOL_CALLS
        assert turn.tool_calls[0].name == "robot.distance.read"
        assert turn.tool_calls[0].call_id == "request-1-tool-1"
        assert turn.diagnostics["load_duration_seconds"] == 2.0
        assert captured["model"] == "qwen3:4b"
        assert captured["think"] is False
        assert captured["options"]["num_predict"] == 512  # type: ignore[index]
        assert captured["tools"][0]["function"]["name"] == "robot.distance.read"  # type: ignore[index]
        await client.aclose()

    asyncio.run(exercise())


def test_ollama_stream_yields_deltas_then_one_complete_turn() -> None:
    async def exercise() -> None:
        lines = [
            {
                "message": {"role": "assistant", "content": "", "thinking": "private"},
                "done": False,
            },
            {
                "message": {"role": "assistant", "content": "Hello "},
                "done": False,
            },
            {
                "message": {"role": "assistant", "content": "robot"},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 3,
                "eval_count": 2,
            },
        ]

        def handler(_request: httpx.Request) -> httpx.Response:
            body = "".join(json.dumps(line) + "\n" for line in lines)
            return httpx.Response(200, content=body)

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://127.0.0.1:11434",
        )
        provider = OllamaProvider(client=client)

        events = [event async for event in provider.stream(request())]

        assert [event.event for event in events] == [
            StreamEventType.ACTIVITY,
            StreamEventType.TEXT_DELTA,
            StreamEventType.TEXT_DELTA,
            StreamEventType.DONE,
        ]
        assert all(event.text != "private" for event in events)
        assert events[-1].turn is not None
        assert events[-1].turn.text == "Hello robot"
        await client.aclose()

    asyncio.run(exercise())


def test_ollama_health_and_malformed_output_are_safe() -> None:
    async def exercise() -> None:
        def handler(http_request: httpx.Request) -> httpx.Response:
            if http_request.url.path == "/api/tags":
                return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
            return httpx.Response(200, json={"message": {"content": 123}})

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://127.0.0.1:11434",
        )
        provider = OllamaProvider(client=client)

        health = await provider.health()
        assert health.status is ProviderHealthStatus.READY
        with pytest.raises(OllamaProtocolError, match="content must be text"):
            await provider.generate(request())
        await client.aclose()

    asyncio.run(exercise())


def test_ollama_lists_local_models_without_loading_them() -> None:
    async def exercise() -> None:
        captured_methods: list[str] = []

        def handler(http_request: httpx.Request) -> httpx.Response:
            captured_methods.append(http_request.method)
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "qwen3:4b",
                            "size": 2_600_000_000,
                            "modified_at": "2026-07-29T00:00:00Z",
                            "details": {
                                "family": "qwen3",
                                "parameter_size": "4.0B",
                                "quantization_level": "Q4_K_M",
                            },
                        },
                        {
                            "model": "gemma3:1b",
                            "size": 815_000_000,
                            "details": {},
                        },
                    ]
                },
            )

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://127.0.0.1:11434",
        )
        provider = OllamaProvider(client=client)

        models = await provider.list_models()

        assert [model.name for model in models] == ["gemma3:1b", "qwen3:4b"]
        assert models[1].parameter_size == "4.0B"
        assert models[1].quantization == "Q4_K_M"
        assert captured_methods == ["GET"]
        await client.aclose()

    asyncio.run(exercise())


def test_model_messages_preserve_assistant_tool_call_context() -> None:
    turn = asyncio.run(_tool_turn())
    message = ModelMessage(
        role=MessageRole.ASSISTANT,
        content="",
        tool_calls=turn.tool_calls,
    )
    restored = ModelMessage.model_validate_json(message.model_dump_json())
    assert restored.tool_calls[0].name == "robot.distance.read"


async def _tool_turn():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "robot.distance.read",
                                "arguments": "{}",
                            }
                        }
                    ],
                },
                "done": True,
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://127.0.0.1:11434",
    )
    provider = OllamaProvider(client=client)
    try:
        return await provider.generate(request(tools=(tool(),)))
    finally:
        await client.aclose()
