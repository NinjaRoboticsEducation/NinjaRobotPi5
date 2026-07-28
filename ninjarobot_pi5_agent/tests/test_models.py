from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ninjarobot_pi5_agent import (
    FinishReason,
    MessageRole,
    ModelMessage,
    ModelRequest,
    ModelTurn,
    SessionRecord,
    ToolCall,
    ToolDefinition,
)
from ninjarobot_pi5_ide import RiskLevel


def request() -> ModelRequest:
    return ModelRequest(
        request_id="request-1",
        session_id="session-1",
        messages=(ModelMessage(role=MessageRole.USER, content="Hello"),),
        max_output_tokens=256,
        timeout_seconds=10.0,
    )


def test_model_contracts_round_trip_through_json() -> None:
    original = request()

    restored = ModelRequest.model_validate_json(original.model_dump_json())

    assert restored == original
    assert ModelRequest.model_json_schema()["additionalProperties"] is False


def test_model_request_rejects_empty_messages_and_coercion() -> None:
    with pytest.raises(ValidationError, match="messages must not be empty"):
        ModelRequest(
            request_id="request-1",
            session_id="session-1",
            messages=(),
        )

    payload = request().model_dump()
    payload["max_output_tokens"] = "256"
    with pytest.raises(ValidationError):
        ModelRequest.model_validate(payload)


def test_model_turn_accepts_normalized_finish_reason() -> None:
    turn = ModelTurn(
        request_id="request-1",
        text="Hello",
        finish_reason=FinishReason.STOP,
        input_tokens=4,
        output_tokens=1,
    )

    assert turn.finish_reason is FinishReason.STOP


def test_tool_metadata_and_finish_reason_are_consistent() -> None:
    tool = ToolDefinition(
        name="distance.read",
        version="1.0.0",
        description="Read distance.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk=RiskLevel.READ_ONLY,
        default_timeout_seconds=2.0,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
    )
    call = ToolCall(call_id="call-1", name=tool.name, arguments={})

    turn = ModelTurn(
        request_id="request-1",
        tool_calls=(call,),
        finish_reason=FinishReason.TOOL_CALLS,
    )

    assert turn.tool_calls == (call,)

    with pytest.raises(ValidationError, match="requires at least one tool call"):
        ModelTurn(request_id="request-1", finish_reason=FinishReason.TOOL_CALLS)

    mcp_call = ToolCall(
        call_id="call-2",
        name="mcp.tavily.tavily-search",
        arguments={"query": "Raspberry Pi 5"},
    )
    assert mcp_call.name == "mcp.tavily.tavily-search"


def test_tool_messages_and_session_timestamps_are_validated() -> None:
    with pytest.raises(ValidationError, match="tool messages require tool_call_id"):
        ModelMessage(role=MessageRole.TOOL, content="result")

    now = datetime(2026, 7, 26, tzinfo=UTC)
    with pytest.raises(ValidationError, match="updated_at must not be before"):
        SessionRecord(
            session_id="session-1",
            user_id="user-1",
            created_at=now,
            updated_at=now - timedelta(seconds=1),
        )
