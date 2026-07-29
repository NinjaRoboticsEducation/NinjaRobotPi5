"""Bounded provider/tool loop with durable conversation and deterministic policy."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .events import AgentEventType, EventBroker
from .models import (
    FinishReason,
    MessageRole,
    ModelMessage,
    ModelRequest,
    ModelStreamEvent,
    ModelTurn,
    StreamEventType,
    ToolCall,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
)
from .persistence import ConversationStore
from .policy import PolicyContext, PolicyEngine
from .prompts import PromptComposer
from .providers import LLMProvider
from .recovery import RecoveryAction, RecoveryPolicy
from .skills import LoadedSkill
from .tools import CancellationToken, ToolRegistry

IDFactory = Callable[[], str]
RuntimeStateProvider = Callable[[str, str | None], dict[str, Any]]
TextDeltaHandler = Callable[[str], Awaitable[None]]


class AgentLoopConfig(BaseModel):
    """Hard bounds that prevent unbounded model/tool execution."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_model_turns: Annotated[int, Field(ge=1, le=20)] = 6
    max_tool_calls: Annotated[int, Field(ge=0, le=50)] = 8
    request_timeout_seconds: Annotated[float, Field(gt=0, le=600)] = 600.0
    model_inactivity_timeout_seconds: Annotated[float, Field(gt=0, le=600)] = 120.0
    max_output_tokens: Annotated[int, Field(ge=32, le=4096)] = 512


class AgentReply(BaseModel):
    """Terminal user-facing response and bounded execution counts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    session_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    text: Annotated[str, StringConstraints(min_length=1, max_length=20_000)]
    model_turns: Annotated[int, Field(ge=1)]
    tool_calls: Annotated[int, Field(ge=0)]


class AgentLoopError(RuntimeError):
    """Raised when a bounded loop cannot safely complete."""


class AgentLoop:
    """Coordinate provider turns and tools without bypassing deterministic policy."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        tools: ToolRegistry,
        policy: PolicyEngine,
        recovery: RecoveryPolicy,
        store: ConversationStore,
        prompts: PromptComposer | None = None,
        events: EventBroker | None = None,
        config: AgentLoopConfig | None = None,
        runtime_state: RuntimeStateProvider | None = None,
        id_factory: IDFactory | None = None,
    ) -> None:
        self._provider = provider
        self._tools = tools
        self._policy = policy
        self._recovery = recovery
        self._store = store
        self._prompts = prompts or PromptComposer()
        self._events = events or EventBroker()
        self._config = config or AgentLoopConfig()
        self._runtime_state = runtime_state or (
            lambda _session_id, _lease_id: {"status": "available"}
        )
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)

    async def chat(
        self,
        *,
        session_id: str,
        text: str,
        skill: LoadedSkill | None = None,
        lease_id: str | None = None,
        confirmed: bool = False,
        cancellation: CancellationToken | None = None,
        on_text_delta: TextDeltaHandler | None = None,
    ) -> AgentReply:
        """Run one bounded conversational turn and persist its messages."""
        request_timeout = self._config.request_timeout_seconds
        if skill is not None:
            request_timeout = min(request_timeout, skill.manifest.limits.timeout_seconds)
        try:
            async with asyncio.timeout(request_timeout):
                return await self._chat(
                    session_id=session_id,
                    text=text,
                    skill=skill,
                    lease_id=lease_id,
                    confirmed=confirmed,
                    cancellation=cancellation,
                    on_text_delta=on_text_delta,
                )
        except TimeoutError as exc:
            raise AgentLoopError(
                f"agent request exceeded its {request_timeout:g}-second limit"
            ) from exc

    async def _chat(
        self,
        *,
        session_id: str,
        text: str,
        skill: LoadedSkill | None = None,
        lease_id: str | None = None,
        confirmed: bool = False,
        cancellation: CancellationToken | None = None,
        on_text_delta: TextDeltaHandler | None = None,
    ) -> AgentReply:
        """Execute one request inside the complete-request deadline."""
        if not text.strip():
            raise ValueError("chat text must not be empty")
        token = cancellation or CancellationToken()
        await self._ensure_session(session_id)
        user_message = ModelMessage(role=MessageRole.USER, content=text.strip())
        await self._append(session_id, user_message)
        await self._events.publish(
            AgentEventType.CHAT,
            "User message accepted.",
            session_id=session_id,
        )

        definitions = self._tools.list_tools()
        if skill is not None:
            allowed = set(skill.manifest.allowed_tools)
            unavailable = sorted(allowed - {definition.name for definition in definitions})
            if unavailable:
                raise AgentLoopError(
                    f"skill references unavailable tools: {', '.join(unavailable)}"
                )
            definitions = tuple(
                definition for definition in definitions if definition.name in allowed
            )
            max_model_turns = min(
                self._config.max_model_turns,
                skill.manifest.limits.max_model_turns,
            )
            max_tool_calls = min(
                self._config.max_tool_calls,
                skill.manifest.limits.max_tool_calls,
            )
        else:
            max_model_turns = self._config.max_model_turns
            max_tool_calls = self._config.max_tool_calls

        completed_tool_calls = 0
        seen_call_ids: set[str] = set()
        for model_turn_number in range(1, max_model_turns + 1):
            if token.cancelled:
                raise asyncio.CancelledError
            history = tuple(stored.message for stored in await self._store.messages(session_id))
            request_id = self._id_factory()
            request = ModelRequest(
                request_id=request_id,
                session_id=session_id,
                messages=self._prompts.compose(
                    runtime_state=self._runtime_state(session_id, lease_id),
                    skill=skill,
                    conversation=history,
                ),
                tools=definitions,
                max_output_tokens=self._config.max_output_tokens,
                timeout_seconds=self._config.model_inactivity_timeout_seconds,
            )
            turn = await self._model_turn(
                request,
                on_text_delta=on_text_delta,
            )
            await self._events.publish(
                AgentEventType.CHAT,
                "Model turn completed.",
                session_id=session_id,
                correlation_id=request_id,
                data={"finish_reason": turn.finish_reason.value},
            )
            if turn.finish_reason is not FinishReason.TOOL_CALLS:
                if not turn.text.strip():
                    raise AgentLoopError("model returned an empty final response")
                assistant = ModelMessage(
                    role=MessageRole.ASSISTANT,
                    content=turn.text,
                )
                await self._append(session_id, assistant)
                return AgentReply(
                    session_id=session_id,
                    text=turn.text,
                    model_turns=model_turn_number,
                    tool_calls=completed_tool_calls,
                )

            assistant = ModelMessage(
                role=MessageRole.ASSISTANT,
                content=turn.text,
                tool_calls=turn.tool_calls,
            )
            await self._append(session_id, assistant)
            for call in turn.tool_calls:
                completed_tool_calls += 1
                if completed_tool_calls > max_tool_calls:
                    raise AgentLoopError("agent exceeded the configured tool-call limit")
                result = await self._execute_call(
                    call,
                    session_id=session_id,
                    lease_id=lease_id,
                    confirmed=confirmed,
                    duplicate=call.call_id in seen_call_ids,
                    cancellation=token,
                )
                seen_call_ids.add(call.call_id)
                await self._append(
                    session_id,
                    ModelMessage(
                        role=MessageRole.TOOL,
                        content=json.dumps(
                            result.model_dump(mode="json"),
                            sort_keys=True,
                            ensure_ascii=False,
                        ),
                        name=call.name,
                        tool_call_id=call.call_id,
                    ),
                )
        raise AgentLoopError("agent exceeded the configured model-turn limit")

    async def _model_turn(
        self,
        request: ModelRequest,
        *,
        on_text_delta: TextDeltaHandler | None,
    ) -> ModelTurn:
        if on_text_delta is None or not self._provider.capabilities.streaming:
            async with asyncio.timeout(request.timeout_seconds):
                return await self._provider.generate(request)
        final: ModelTurn | None = None
        stream = self._provider.stream(request).__aiter__()
        while True:
            try:
                async with asyncio.timeout(request.timeout_seconds):
                    event = await anext(stream)
            except StopAsyncIteration:
                break
            final = await self._consume_stream_event(
                event,
                final=final,
                on_text_delta=on_text_delta,
            )
        if final is None:
            raise AgentLoopError("provider stream ended without a final turn")
        return final

    @staticmethod
    async def _consume_stream_event(
        event: ModelStreamEvent,
        *,
        final: ModelTurn | None,
        on_text_delta: TextDeltaHandler,
    ) -> ModelTurn | None:
        if event.event is StreamEventType.ACTIVITY:
            return final
        if event.event is StreamEventType.TEXT_DELTA:
            await on_text_delta(event.text)
            return final
        if final is not None or event.turn is None:
            raise AgentLoopError("provider emitted duplicate or malformed final stream event")
        return event.turn

    async def _execute_call(
        self,
        call: ToolCall,
        *,
        session_id: str,
        lease_id: str | None,
        confirmed: bool,
        duplicate: bool,
        cancellation: CancellationToken,
    ) -> ToolExecutionResult:
        if duplicate:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.DENIED,
                error="Duplicate tool call identity was blocked.",
            )
        try:
            definition = self._tools.get(call.name)
        except KeyError:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.DENIED,
                error="The requested tool is unavailable.",
            )
        decision = self._policy.evaluate(
            definition,
            PolicyContext(
                session_id=session_id,
                lease_id=lease_id,
                confirmed=confirmed,
            ),
        )
        if not decision.allowed:
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.DENIED,
                error=decision.reason,
            )
        invocation = ToolInvocation(
            call=call,
            session_id=session_id,
            lease_id=lease_id,
        )
        result = await self._tools.call(invocation, cancellation)
        recovery = self._recovery.decide(
            definition,
            result,
            attempts_completed=1,
        )
        if recovery.action is RecoveryAction.RETRY:
            result = await self._tools.call(invocation, cancellation)
        await self._events.publish(
            AgentEventType.TOOL,
            f"Tool {result.status.value}: {call.name}",
            session_id=session_id,
            correlation_id=call.call_id,
            data={
                "tool": call.name,
                "status": result.status.value,
                "action_id": result.action_id,
            },
        )
        return result

    async def _ensure_session(self, session_id: str) -> None:
        sessions = await self._store.sessions()
        if not any(record.session_id == session_id for record in sessions):
            await self._store.create_session(session_id)

    async def _append(self, session_id: str, message: ModelMessage) -> None:
        await self._store.append_message(
            session_id,
            message,
            message_id=f"message-{self._id_factory()}",
        )
