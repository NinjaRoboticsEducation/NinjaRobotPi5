from __future__ import annotations

import asyncio
import json

import httpx
from ninjarobot_pi5_agent.cloud_common import APIKeyCredential, wire_tool_name
from ninjarobot_pi5_agent.gemini_provider import GeminiConfig, GeminiProvider
from ninjarobot_pi5_agent.secrets import SecretStore

from ninjarobot_pi5_agent import (
    FinishReason,
    MessageRole,
    ModelMessage,
    ModelRequest,
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
