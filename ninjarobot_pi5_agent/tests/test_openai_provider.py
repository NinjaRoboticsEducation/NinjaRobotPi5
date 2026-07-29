from __future__ import annotations

import asyncio
import json

import httpx
from ninjarobot_pi5_agent.cloud_common import APIKeyCredential, wire_tool_name
from ninjarobot_pi5_agent.openai_provider import OpenAIConfig, OpenAIProvider
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
                content="Selected skill 'robot-check' is subordinate workflow guidance.",
            ),
            ModelMessage(role=MessageRole.USER, content="Read the distance."),
        ),
        tools=(
            ToolDefinition(
                name="robot.distance.read",
                version="1.0.0",
                description="Read the front distance sensor.",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                risk=RiskLevel.READ_ONLY,
                default_timeout_seconds=2.0,
                idempotent=True,
                cancellable=True,
                confirmation_required=False,
            ),
        ),
    )


def test_openai_normalizes_the_same_mcp_and_robot_tool_contract(tmp_path) -> None:
    async def exercise() -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["authorization"] = request.headers.get("authorization")
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "resp_1",
                    "status": "completed",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call-1",
                            "name": wire_tool_name("robot.distance.read"),
                            "arguments": "{}",
                        }
                    ],
                    "usage": {"input_tokens": 20, "output_tokens": 5},
                },
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("OPENAI_API_KEY", "test-openai-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.openai.com/v1",
        )
        provider = OpenAIProvider(
            OpenAIConfig(model="gpt-5-mini"),
            APIKeyCredential(store, "OPENAI_API_KEY", "Authorization", "Bearer "),
            client=client,
        )
        turn = await provider.generate(_request())

        assert turn.finish_reason is FinishReason.TOOL_CALLS
        assert turn.tool_calls[0].name == "robot.distance.read"
        assert turn.tool_calls[0].arguments == {}
        assert captured["authorization"] == "Bearer test-openai-key"
        payload = captured["payload"]
        assert isinstance(payload, dict)
        assert payload["store"] is False
        assert payload["include"] == ["reasoning.encrypted_content"]
        assert "Selected skill 'robot-check'" in payload["input"][0]["content"]
        assert payload["tools"][0]["name"] == wire_tool_name("robot.distance.read")
        assert payload["tools"][0]["strict"] is True
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())


def test_openai_replays_only_bounded_encrypted_reasoning_for_tool_continuation(
    tmp_path,
) -> None:
    async def exercise() -> None:
        payloads: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            payloads.append(json.loads(request.content))
            if len(payloads) == 1:
                return httpx.Response(
                    200,
                    json={
                        "id": "resp_reasoning",
                        "status": "completed",
                        "output": [
                            {
                                "type": "reasoning",
                                "encrypted_content": "opaque-encrypted-state",
                            },
                            {
                                "type": "function_call",
                                "call_id": "call-1",
                                "name": wire_tool_name("robot.distance.read"),
                                "arguments": "{}",
                            },
                        ],
                    },
                )
            return httpx.Response(
                200,
                json={
                    "id": "resp_final",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "123 mm"}],
                        }
                    ],
                },
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("OPENAI_API_KEY", "test-openai-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.openai.com/v1",
        )
        provider = OpenAIProvider(
            OpenAIConfig(model="gpt-5-mini"),
            APIKeyCredential(store, "OPENAI_API_KEY", "Authorization", "Bearer "),
            client=client,
        )
        first = await provider.generate(_request())
        continuation = _request().model_copy(
            update={
                "messages": (
                    *_request().messages,
                    ModelMessage(
                        role=MessageRole.ASSISTANT,
                        content="",
                        tool_calls=first.tool_calls,
                    ),
                    ModelMessage(
                        role=MessageRole.TOOL,
                        content='{"distance_mm": 123}',
                        name="robot.distance.read",
                        tool_call_id="call-1",
                    ),
                )
            }
        )

        final = await provider.generate(continuation)

        assert final.text == "123 mm"
        second_input = payloads[1]["input"]
        assert isinstance(second_input, list)
        assert any(
            isinstance(item, dict) and item.get("encrypted_content") == "opaque-encrypted-state"
            for item in second_input
        )
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())


def test_openai_streams_text_and_returns_normalized_terminal_turn(tmp_path) -> None:
    async def exercise() -> None:
        completed = {
            "id": "resp_2",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Hello"}],
                }
            ],
            "usage": {"input_tokens": 4, "output_tokens": 1},
        }
        body = (
            'event: response.output_text.delta\ndata: {"type":'
            '"response.output_text.delta","delta":"Hello"}\n\n'
            "event: response.completed\ndata: "
            + json.dumps({"type": "response.completed", "response": completed})
            + "\n\n"
        )

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

        store = SecretStore(tmp_path / "secrets.env")
        store.set("OPENAI_API_KEY", "test-openai-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.openai.com/v1",
        )
        provider = OpenAIProvider(
            OpenAIConfig(model="gpt-5-mini"),
            APIKeyCredential(store, "OPENAI_API_KEY", "Authorization", "Bearer "),
            client=client,
        )

        events = [event async for event in provider.stream(_request())]

        assert [event.event for event in events] == [
            StreamEventType.ACTIVITY,
            StreamEventType.TEXT_DELTA,
            StreamEventType.DONE,
        ]
        assert events[-1].turn is not None
        assert events[-1].turn.text == "Hello"
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())
