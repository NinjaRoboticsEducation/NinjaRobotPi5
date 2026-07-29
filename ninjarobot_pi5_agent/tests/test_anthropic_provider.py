from __future__ import annotations

import asyncio
import json

import httpx
from ninjarobot_pi5_agent.anthropic_provider import AnthropicConfig, AnthropicProvider
from ninjarobot_pi5_agent.cloud_common import APIKeyCredential, wire_tool_name
from ninjarobot_pi5_agent.secrets import SecretStore

from ninjarobot_pi5_agent import (
    FinishReason,
    MessageRole,
    ModelMessage,
    ModelRequest,
    StreamEventType,
    ToolDefinition,
)
from ninjarobot_pi5_ide import RiskLevel


def _request() -> ModelRequest:
    return ModelRequest(
        request_id="request-1",
        session_id="session-1",
        messages=(
            ModelMessage(
                role=MessageRole.SYSTEM,
                content=(
                    "Selected skill 'robot-behavior-generation' is subordinate workflow guidance."
                ),
            ),
            ModelMessage(role=MessageRole.USER, content="Run greeting."),
        ),
        tools=(
            ToolDefinition(
                name="robot.behavior.run",
                version="1.0.0",
                description="Run a validated robot behavior.",
                input_schema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                risk=RiskLevel.LOW,
                default_timeout_seconds=30.0,
                idempotent=False,
                cancellable=True,
                confirmation_required=False,
            ),
        ),
    )


def test_anthropic_normalizes_robot_tool_calls(tmp_path) -> None:
    async def exercise() -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["key"] = request.headers.get("x-api-key")
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "msg_1",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": wire_tool_name("robot.behavior.run"),
                            "input": {"name": "greeting"},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 18, "output_tokens": 7},
                },
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("ANTHROPIC_API_KEY", "test-anthropic-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.anthropic.com/v1",
        )
        provider = AnthropicProvider(
            AnthropicConfig(model="claude-sonnet-4-5"),
            APIKeyCredential(store, "ANTHROPIC_API_KEY", "x-api-key"),
            client=client,
        )

        turn = await provider.generate(_request())

        assert turn.finish_reason is FinishReason.TOOL_CALLS
        assert turn.tool_calls[0].name == "robot.behavior.run"
        assert turn.tool_calls[0].arguments == {"name": "greeting"}
        assert captured["key"] == "test-anthropic-key"
        payload = captured["payload"]
        assert isinstance(payload, dict)
        assert payload["tools"][0]["name"] == wire_tool_name("robot.behavior.run")
        assert "Selected skill 'robot-behavior-generation'" in payload["system"]
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())


def test_anthropic_stream_accumulates_text_without_exposing_private_events(
    tmp_path,
) -> None:
    async def exercise() -> None:
        events = (
            'event: message_start\ndata: {"type":"message_start","message":'
            '{"usage":{"input_tokens":5}}}\n\n'
            'event: content_block_start\ndata: {"type":"content_block_start",'
            '"index":0,"content_block":{"type":"text","text":""}}\n\n'
            'event: content_block_delta\ndata: {"type":"content_block_delta",'
            '"index":0,"delta":{"type":"text_delta","text":"Hello"}}\n\n'
            'event: message_delta\ndata: {"type":"message_delta","delta":'
            '{"stop_reason":"end_turn"},"usage":{"output_tokens":1}}\n\n'
            'event: message_stop\ndata: {"type":"message_stop"}\n\n'
        )

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text=events,
                headers={"content-type": "text/event-stream"},
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("ANTHROPIC_API_KEY", "test-anthropic-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.anthropic.com/v1",
        )
        provider = AnthropicProvider(
            AnthropicConfig(model="claude-sonnet-4-5"),
            APIKeyCredential(store, "ANTHROPIC_API_KEY", "x-api-key"),
            client=client,
        )

        streamed = [event async for event in provider.stream(_request())]

        assert [event.event for event in streamed] == [
            StreamEventType.ACTIVITY,
            StreamEventType.TEXT_DELTA,
            StreamEventType.DONE,
        ]
        assert streamed[-1].turn is not None
        assert streamed[-1].turn.text == "Hello"
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())
