"""Strict provider, tool, session, and memory contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ninjarobot_pi5_ide import RetrySafety, RiskLevel

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    ),
]
ToolName = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$",
    ),
]
NonEmptyText = Annotated[str, StringConstraints(min_length=1, max_length=20_000)]


class AgentContractModel(BaseModel):
    """Base that rejects extra fields and implicit type coercion."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class MessageRole(StrEnum):
    """Provider-neutral message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(StrEnum):
    """Normalized reason a provider stopped generating."""

    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    CANCELLED = "cancelled"
    ERROR = "error"


class ProviderHealthStatus(StrEnum):
    """Non-secret provider readiness state."""

    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class MemoryKind(StrEnum):
    """Initial provider-neutral memory categories."""

    USER_PROFILE = "user_profile"
    PREFERENCE = "preference"
    TASK_RECIPE = "task_recipe"
    EPISODIC_SUMMARY = "episodic_summary"


class ToolTrust(StrEnum):
    """Whether tool output originates inside or outside the robot boundary."""

    TRUSTED = "trusted"
    EXTERNAL_UNTRUSTED = "external_untrusted"


class ToolExecutionStatus(StrEnum):
    """Normalized terminal state for one agent tool invocation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"
    TIMED_OUT = "timed_out"


class StreamEventType(StrEnum):
    """Provider-neutral streaming event kinds."""

    ACTIVITY = "activity"
    TEXT_DELTA = "text_delta"
    DONE = "done"


class ToolCall(AgentContractModel):
    """Normalized model-proposed tool call."""

    call_id: Identifier
    name: ToolName
    arguments: dict[str, Any]


class ModelMessage(AgentContractModel):
    """One provider-neutral conversation message."""

    role: MessageRole
    content: Annotated[str, StringConstraints(max_length=20_000)]
    name: Identifier | None = None
    tool_call_id: Identifier | None = None
    tool_calls: tuple[ToolCall, ...] = ()

    @model_validator(mode="after")
    def tool_messages_require_call_identity(self) -> ModelMessage:
        """Keep provider tool-result messages tied to a requested call."""
        if self.role is MessageRole.TOOL and self.tool_call_id is None:
            raise ValueError("tool messages require tool_call_id")
        if self.role is not MessageRole.TOOL and self.tool_call_id is not None:
            raise ValueError("tool_call_id is valid only for tool messages")
        if self.role is not MessageRole.ASSISTANT and self.tool_calls:
            raise ValueError("tool_calls are valid only for assistant messages")
        if not self.content and not (self.role is MessageRole.ASSISTANT and self.tool_calls):
            raise ValueError("message content must not be empty")
        return self


class ToolDefinition(AgentContractModel):
    """Agent-facing view of one IDE or external capability."""

    name: ToolName
    version: Identifier
    description: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk: RiskLevel
    default_timeout_seconds: Annotated[float, Field(gt=0, le=3600)]
    idempotent: bool
    cancellable: bool
    confirmation_required: bool
    source: Identifier = "ide"
    trust: ToolTrust = ToolTrust.TRUSTED


class ToolInvocation(AgentContractModel):
    """One tool call bound to its user session and request identity."""

    call: ToolCall
    session_id: Identifier
    requested_by: Identifier = "agent"
    lease_id: Identifier | None = None


class ToolExecutionResult(AgentContractModel):
    """Provider-neutral result with conservative retry evidence."""

    call_id: Identifier
    tool_name: ToolName
    status: ToolExecutionStatus
    data: dict[str, Any] | None = None
    error: Annotated[str, StringConstraints(min_length=1, max_length=2000)] | None = None
    definitely_not_executed: bool = False
    retry_safety: RetrySafety = RetrySafety.UNKNOWN
    action_id: Identifier | None = None

    @model_validator(mode="after")
    def status_and_error_are_consistent(self) -> ToolExecutionResult:
        """Require errors for every non-success terminal state."""
        if self.status is ToolExecutionStatus.SUCCEEDED and self.error is not None:
            raise ValueError("successful tool results must not include an error")
        if self.status is not ToolExecutionStatus.SUCCEEDED and self.error is None:
            raise ValueError("non-successful tool results require an error")
        return self


class ProviderCapabilities(AgentContractModel):
    """Features supported by one provider adapter."""

    native_tools: bool
    streaming: bool
    images: bool
    audio: bool
    structured_output: bool
    usage_reporting: bool
    provider_conversation_state: bool


class ModelRequest(AgentContractModel):
    """Bounded provider-neutral generation request."""

    request_id: Identifier
    session_id: Identifier
    messages: tuple[ModelMessage, ...]
    tools: tuple[ToolDefinition, ...] = ()
    max_output_tokens: Annotated[int, Field(ge=1, le=32_768)] = 1024
    timeout_seconds: Annotated[float, Field(gt=0, le=600)] = 60.0

    @field_validator("messages")
    @classmethod
    def messages_must_not_be_empty(
        cls, messages: tuple[ModelMessage, ...]
    ) -> tuple[ModelMessage, ...]:
        """A generation request without context is always a caller error."""
        if not messages:
            raise ValueError("messages must not be empty")
        return messages

    @field_validator("tools")
    @classmethod
    def tool_names_must_be_unique(
        cls, tools: tuple[ToolDefinition, ...]
    ) -> tuple[ToolDefinition, ...]:
        """Prevent two schemas from competing for one model-visible name."""
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise ValueError("tool names must not contain duplicates")
        return tools


class ModelTurn(AgentContractModel):
    """Normalized provider response."""

    request_id: Identifier
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: FinishReason
    input_tokens: Annotated[int, Field(ge=0)] | None = None
    output_tokens: Annotated[int, Field(ge=0)] | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def finish_reason_must_match_tool_calls(self) -> ModelTurn:
        """Reject contradictory provider normalization."""
        if self.finish_reason is FinishReason.TOOL_CALLS and not self.tool_calls:
            raise ValueError("tool_calls finish reason requires at least one tool call")
        if self.finish_reason is not FinishReason.TOOL_CALLS and self.tool_calls:
            raise ValueError("tool calls require the tool_calls finish reason")
        return self


class ModelStreamEvent(AgentContractModel):
    """One private activity signal, text delta, or final provider turn."""

    request_id: Identifier
    event: StreamEventType
    text: str = ""
    turn: ModelTurn | None = None

    @model_validator(mode="after")
    def event_payload_is_consistent(self) -> ModelStreamEvent:
        """Keep partial text separate from the terminal turn."""
        if self.event is StreamEventType.ACTIVITY:
            if self.text or self.turn is not None:
                raise ValueError("activity events do not expose provider content")
        elif self.event is StreamEventType.TEXT_DELTA:
            if not self.text or self.turn is not None:
                raise ValueError("text delta events require text and no turn")
        elif self.turn is None or self.text:
            raise ValueError("done events require a turn and no delta text")
        return self


class ProviderHealth(AgentContractModel):
    """Safe provider health response without credentials."""

    provider: Identifier
    status: ProviderHealthStatus
    checked_at: datetime
    detail: Annotated[str, StringConstraints(max_length=1000)] | None = None

    @field_validator("checked_at")
    @classmethod
    def checked_at_must_include_timezone(cls, checked_at: datetime) -> datetime:
        """Require portable health timestamps."""
        if checked_at.tzinfo is None:
            raise ValueError("checked_at must include a timezone")
        return checked_at


class SessionRecord(AgentContractModel):
    """Provider-neutral session identity and lifecycle timestamps."""

    session_id: Identifier
    user_id: Identifier
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def session_times_must_include_timezone(cls, value: datetime) -> datetime:
        """Reject ambiguous local timestamps."""
        if value.tzinfo is None:
            raise ValueError("session timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def updated_at_must_not_precede_creation(self) -> SessionRecord:
        """Keep session lifecycle order valid."""
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be before created_at")
        return self


class MemoryCandidate(AgentContractModel):
    """Model-suggested memory that still requires deterministic approval."""

    candidate_id: Identifier
    session_id: Identifier
    kind: MemoryKind
    content: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    source: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    confidence: Annotated[float, Field(ge=0, le=1)]
    sensitive: bool
