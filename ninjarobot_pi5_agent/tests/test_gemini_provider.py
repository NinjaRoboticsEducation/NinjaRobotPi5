from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from ninjarobot_pi5_agent.cloud_common import (
    APIKeyCredential,
    CloudUnavailableError,
    wire_tool_name,
)
from ninjarobot_pi5_agent.gemini_provider import GeminiConfig, GeminiProvider
from ninjarobot_pi5_agent.secrets import SecretStore

from ninjarobot_pi5_agent import (
    FinishReason,
    MessageRole,
    ModelMessage,
    ModelRequest,
    ToolCall,
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
                content="Selected skill 'web-research' is subordinate workflow guidance.",
            ),
            ModelMessage(role=MessageRole.USER, content="Search for Pi news."),
        ),
        tools=(
            ToolDefinition(
                name="mcp.tavily.tavily-search",
                version="1.0.0",
                description="Search the public web.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                risk=RiskLevel.READ_ONLY,
                default_timeout_seconds=20.0,
                idempotent=True,
                cancellable=True,
                confirmation_required=False,
                source="mcp.tavily",
            ),
        ),
    )


def test_gemini_preserves_mcp_tool_identity_and_disables_sdk_auto_execution(
    tmp_path,
) -> None:
    async def exercise() -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["key"] = request.headers.get("x-goog-api-key")
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": wire_tool_name("mcp.tavily.tavily-search"),
                                            "args": {"query": "Raspberry Pi news"},
                                        }
                                    }
                                ],
                            },
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 20,
                        "candidatesTokenCount": 4,
                    },
                },
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("GEMINI_API_KEY", "test-gemini-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
        provider = GeminiProvider(
            GeminiConfig(model="gemini-2.5-flash"),
            APIKeyCredential(store, "GEMINI_API_KEY", "x-goog-api-key"),
            client=client,
        )

        turn = await provider.generate(_request())

        assert turn.finish_reason is FinishReason.TOOL_CALLS
        assert turn.tool_calls[0].name == "mcp.tavily.tavily-search"
        assert turn.tool_calls[0].arguments == {"query": "Raspberry Pi news"}
        assert turn.tool_calls[0].provider_metadata == {"provider": "gemini"}
        assert captured["key"] == "test-gemini-key"
        payload = captured["payload"]
        assert isinstance(payload, dict)
        assert payload["tools"][0]["functionDeclarations"][0]["name"] == wire_tool_name(
            "mcp.tavily.tavily-search"
        )
        assert "Selected skill 'web-research'" in payload["systemInstruction"]["parts"][0]["text"]
        assert payload["toolConfig"]["functionCallingConfig"]["mode"] == "AUTO"
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())


def test_gemini_replays_native_function_call_ids_and_thought_signatures(tmp_path) -> None:
    async def exercise() -> None:
        payloads: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            payloads.append(json.loads(request.content))
            if len(payloads) == 1:
                return httpx.Response(
                    200,
                    json={
                        "candidates": [
                            {
                                "content": {
                                    "role": "model",
                                    "parts": [
                                        {
                                            "thoughtSignature": "opaque-signature",
                                            "functionCall": {
                                                "id": "gemini-call-1",
                                                "name": wire_tool_name("mcp.tavily.tavily-search"),
                                                "args": {"query": "Raspberry Pi news"},
                                            },
                                        }
                                    ],
                                },
                                "finishReason": "STOP",
                            }
                        ]
                    },
                )
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {"role": "model", "parts": [{"text": "Done."}]},
                            "finishReason": "STOP",
                        }
                    ]
                },
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("GEMINI_API_KEY", "test-gemini-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
        provider = GeminiProvider(
            GeminiConfig(model="gemini-3.6-flash"),
            APIKeyCredential(store, "GEMINI_API_KEY", "x-goog-api-key"),
            client=client,
        )
        first_request = _request()
        initial = await provider.generate(first_request)
        assert initial.tool_calls[0].provider_metadata == {
            "provider": "gemini",
            "thought_signature": "opaque-signature",
        }

        continuation = first_request.model_copy(
            update={
                "request_id": "request-2",
                "messages": (
                    *first_request.messages,
                    ModelMessage(
                        role=MessageRole.ASSISTANT,
                        content="",
                        tool_calls=initial.tool_calls,
                    ),
                    ModelMessage(
                        role=MessageRole.TOOL,
                        name="mcp.tavily.tavily-search",
                        tool_call_id="gemini-call-1",
                        content='{"answer":"Pi news"}',
                    ),
                ),
            }
        )
        final = await provider.generate(continuation)
        assert final.text == "Done."

        contents = payloads[1]["contents"]
        assert isinstance(contents, list)
        function_call = contents[-2]["parts"][0]["functionCall"]
        function_response = contents[-1]["parts"][0]["functionResponse"]
        assert function_call["id"] == "gemini-call-1"
        assert contents[-2]["parts"][0]["thoughtSignature"] == "opaque-signature"
        assert function_response["id"] == "gemini-call-1"
        assert function_response["name"] == function_call["name"]
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())


def test_gemini_flattens_foreign_tool_history_to_reference_text(tmp_path) -> None:
    async def exercise() -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {"role": "model", "parts": [{"text": "Recovered."}]},
                            "finishReason": "STOP",
                        }
                    ]
                },
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("GEMINI_API_KEY", "test-gemini-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
        provider = GeminiProvider(
            GeminiConfig(model="gemini-3.6-flash"),
            APIKeyCredential(store, "GEMINI_API_KEY", "x-goog-api-key"),
            client=client,
        )
        request = _request().model_copy(
            update={
                "messages": (
                    ModelMessage(role=MessageRole.USER, content="Move."),
                    ModelMessage(
                        role=MessageRole.ASSISTANT,
                        content="",
                        tool_calls=(
                            ToolCall(
                                call_id="ollama-call-1",
                                name="robot.display.clear",
                                arguments={},
                            ),
                        ),
                    ),
                    ModelMessage(
                        role=MessageRole.TOOL,
                        name="robot.display.clear",
                        tool_call_id="ollama-call-1",
                        content='{"status":"succeeded"}',
                    ),
                    ModelMessage(role=MessageRole.USER, content="What happened?"),
                )
            }
        )
        final = await provider.generate(request)
        assert final.text == "Recovered."
        payload = captured["payload"]
        assert isinstance(payload, dict)
        serialized = json.dumps(payload["contents"])
        assert "functionCall" not in serialized
        assert "functionResponse" not in serialized
        assert "Trusted historical tool result" in serialized
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())


def test_gemini_retries_a_rate_limited_non_streaming_request(tmp_path) -> None:
    async def exercise() -> None:
        attempts = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"error": {"status": "RESOURCE_EXHAUSTED"}},
                )
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {"role": "model", "parts": [{"text": "Retried."}]},
                            "finishReason": "STOP",
                        }
                    ]
                },
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("GEMINI_API_KEY", "test-gemini-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
        provider = GeminiProvider(
            GeminiConfig(model="gemini-3.6-flash", max_rate_limit_retries=1),
            APIKeyCredential(store, "GEMINI_API_KEY", "x-goog-api-key"),
            client=client,
        )
        assert (await provider.generate(_request())).text == "Retried."
        assert attempts == 2
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())


def test_gemini_retries_a_rate_limited_stream_before_public_output(tmp_path) -> None:
    async def exercise() -> None:
        attempts = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"error": {"status": "RESOURCE_EXHAUSTED"}},
                )
            payload = {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "Stream retried."}]},
                        "finishReason": "STOP",
                    }
                ]
            }
            return httpx.Response(200, content=f"data: {json.dumps(payload)}\n\n")

        store = SecretStore(tmp_path / "secrets.env")
        store.set("GEMINI_API_KEY", "test-gemini-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
        provider = GeminiProvider(
            GeminiConfig(model="gemini-3.6-flash", max_rate_limit_retries=1),
            APIKeyCredential(store, "GEMINI_API_KEY", "x-goog-api-key"),
            client=client,
        )
        events = [event async for event in provider.stream(_request())]
        assert attempts == 2
        assert events[-1].turn is not None
        assert events[-1].turn.text == "Stream retried."
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())


def test_gemini_400_reports_only_a_safe_provider_error_category(tmp_path) -> None:
    async def exercise() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "status": "INVALID_ARGUMENT",
                        "message": "This must not be returned to the user.",
                    }
                },
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("GEMINI_API_KEY", "test-gemini-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
        provider = GeminiProvider(
            GeminiConfig(model="gemini-3.6-flash", max_rate_limit_retries=0),
            APIKeyCredential(store, "GEMINI_API_KEY", "x-goog-api-key"),
            client=client,
        )
        with pytest.raises(
            CloudUnavailableError,
            match=r"Gemini rejected the request \(INVALID_ARGUMENT\)",
        ):
            await provider.generate(_request())
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())


def test_gemini_catalog_filters_models_without_generate_content(tmp_path) -> None:
    async def exercise() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-2.5-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {
                            "name": "models/text-embedding",
                            "supportedGenerationMethods": ["embedContent"],
                        },
                    ]
                },
            )

        store = SecretStore(tmp_path / "secrets.env")
        store.set("GEMINI_API_KEY", "test-gemini-key")
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
        provider = GeminiProvider(
            GeminiConfig(model="gemini-2.5-flash"),
            APIKeyCredential(store, "GEMINI_API_KEY", "x-goog-api-key"),
            client=client,
        )

        models = await provider.list_models()

        assert [model.name for model in models] == ["gemini-2.5-flash"]
        await provider.close()
        await client.aclose()

    asyncio.run(exercise())
