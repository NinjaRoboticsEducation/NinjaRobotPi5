"""Bounded provider/tool loop with durable conversation and deterministic policy."""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
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
from .presentation import (
    NullPresentationController,
    PresentationController,
    StreamingPresentationFilter,
    extract_presentation_directive,
)
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
    max_output_tokens: Annotated[int, Field(ge=32, le=4096)] = 1024


class AgentReply(BaseModel):
    """Terminal user-facing response and bounded execution counts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    session_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    text: Annotated[str, StringConstraints(min_length=1, max_length=20_000)]
    model_turns: Annotated[int, Field(ge=0)]
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
        presentation: PresentationController | None = None,
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
        self._presentation = presentation or NullPresentationController()
        self._active_cancellations: dict[str, CancellationToken] = {}

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
        token = cancellation or CancellationToken()
        self._active_cancellations[session_id] = token
        try:
            async with asyncio.timeout(request_timeout):
                return await self._chat(
                    session_id=session_id,
                    text=text,
                    skill=skill,
                    lease_id=lease_id,
                    confirmed=confirmed,
                    cancellation=token,
                    on_text_delta=on_text_delta,
                )
        except TimeoutError as exc:
            raise AgentLoopError(
                f"agent request exceeded its {request_timeout:g}-second limit"
            ) from exc
        finally:
            if self._active_cancellations.get(session_id) is token:
                self._active_cancellations.pop(session_id, None)
            await asyncio.shield(
                self._present(
                    "idle",
                    self._presentation.idle,
                    session_id=session_id,
                )
            )

    def cancel_session(self, session_id: str) -> None:
        """Cancel active reasoning or tool work for one session."""
        token = self._active_cancellations.get(session_id)
        if token is not None:
            token.cancel()

    def cancel_all(self) -> None:
        """Cancel every active conversation during global revocation."""
        tokens = tuple(self._active_cancellations.values())
        self._active_cancellations.clear()
        for token in tokens:
            token.cancel()

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
        await self._present(
            "thinking",
            self._presentation.thinking,
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

        available_tool_names = {definition.name for definition in definitions}
        camera_reply = await self._handle_deterministic_camera_request(
            text=text,
            session_id=session_id,
            lease_id=lease_id,
            available_tool_names=available_tool_names,
            cancellation=token,
            on_text_delta=on_text_delta,
        )
        if camera_reply is not None:
            return camera_reply

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
                allow_provider_fallback=(model_turn_number == 1 and completed_tool_calls == 0),
            )
            turn = await self._model_turn(
                request,
                on_text_delta=on_text_delta,
                session_id=session_id,
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

            turn = turn.model_copy(
                update={
                    "tool_calls": tuple(
                        _normalize_behavior_tool_call(
                            call,
                            available_tool_names=available_tool_names,
                        )
                        for call in turn.tool_calls
                    )
                }
            )
            assistant = ModelMessage(
                role=MessageRole.ASSISTANT,
                content=turn.text,
                tool_calls=turn.tool_calls,
            )
            await self._append(session_id, assistant)
            for call in turn.tool_calls:
                if token.cancelled:
                    raise asyncio.CancelledError
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

    async def _handle_deterministic_camera_request(
        self,
        *,
        text: str,
        session_id: str,
        lease_id: str | None,
        available_tool_names: set[str],
        cancellation: CancellationToken,
        on_text_delta: TextDeltaHandler | None,
    ) -> AgentReply | None:
        """Execute a clearly requested, explicitly granted preview without an LLM."""
        if _is_camera_preview_rejection(text):
            return await self._direct_reply(
                session_id=session_id,
                text=(
                    "No photo was taken. Any current one-photo grant remains ready "
                    "until you make a clear capture request."
                ),
                tool_calls=0,
                on_text_delta=on_text_delta,
            )
        if not _is_camera_preview_request(text):
            return None

        camera_tool = "robot.camera.preview"
        if camera_tool not in available_tool_names:
            return await self._direct_reply(
                session_id=session_id,
                text=(
                    "The temporary camera preview is unavailable in the current "
                    "agent configuration."
                ),
                tool_calls=0,
                on_text_delta=on_text_delta,
            )

        grants = self._policy.camera_grants
        if not grants.is_granted(session_id, lease_id=lease_id):
            return await self._direct_reply(
                session_id=session_id,
                text=(
                    "AI camera access is not currently granted. Enter /camera or "
                    "press AI camera, then ask me to take the photo again."
                ),
                tool_calls=0,
                on_text_delta=on_text_delta,
            )

        if cancellation.cancelled:
            raise asyncio.CancelledError
        call = ToolCall(
            call_id=f"{self._id_factory()}-camera-preview",
            name=camera_tool,
            arguments={},
        )
        await self._append(
            session_id,
            ModelMessage(
                role=MessageRole.ASSISTANT,
                content="",
                tool_calls=(call,),
            ),
        )
        result = await self._execute_call(
            call,
            session_id=session_id,
            lease_id=lease_id,
            confirmed=False,
            duplicate=False,
            cancellation=cancellation,
            deterministic_camera_request=True,
        )
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

        if result.status is ToolExecutionStatus.SUCCEEDED:
            reply_text = "The temporary photo is ready."
        elif grants.is_granted(session_id, lease_id=lease_id):
            reply_text = (
                f"The camera preview failed: {result.error} "
                "Your current one-photo grant remains ready, so you can try again."
            )
        else:
            reply_text = (
                f"The camera preview did not complete: {result.error} "
                "Enter /camera or press AI camera before trying again."
            )
        await self._events.publish(
            AgentEventType.CHAT,
            "Deterministic camera request completed.",
            session_id=session_id,
            correlation_id=call.call_id,
            data={"status": result.status.value},
        )
        return await self._direct_reply(
            session_id=session_id,
            text=reply_text,
            tool_calls=1,
            on_text_delta=on_text_delta,
        )

    async def _direct_reply(
        self,
        *,
        session_id: str,
        text: str,
        tool_calls: int,
        on_text_delta: TextDeltaHandler | None,
    ) -> AgentReply:
        """Persist and stream a deterministic response without a model turn."""
        await self._present(
            "responding",
            self._presentation.responding,
            session_id=session_id,
        )
        if on_text_delta is not None:
            await on_text_delta(text)
        await self._append(
            session_id,
            ModelMessage(role=MessageRole.ASSISTANT, content=text),
        )
        return AgentReply(
            session_id=session_id,
            text=text,
            model_turns=0,
            tool_calls=tool_calls,
        )

    async def _model_turn(
        self,
        request: ModelRequest,
        *,
        on_text_delta: TextDeltaHandler | None,
        session_id: str,
    ) -> ModelTurn:
        if on_text_delta is None or not self._provider.capabilities.streaming:
            async with asyncio.timeout(request.timeout_seconds):
                turn = await self._provider.generate(request)
            face, visible = extract_presentation_directive(turn.text)
            if turn.finish_reason is not FinishReason.TOOL_CALLS:
                await self._present(
                    "responding",
                    lambda: self._presentation.responding(face),
                    session_id=session_id,
                )
            return turn.model_copy(update={"text": visible})
        stream_filter = StreamingPresentationFilter(
            on_visible_text=on_text_delta,
            on_response_started=lambda face: self._present(
                "responding",
                lambda: self._presentation.responding(face),
                session_id=session_id,
            ),
        )
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
                on_text_delta=stream_filter.feed,
            )
        if final is None:
            raise AgentLoopError("provider stream ended without a final turn")
        face, visible = extract_presentation_directive(final.text)
        if final.finish_reason is not FinishReason.TOOL_CALLS:
            await stream_filter.finish()
            if face is not None:
                await self._present(
                    "responding",
                    lambda: self._presentation.responding(face),
                    session_id=session_id,
                )
        return final.model_copy(update={"text": visible})

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
        deterministic_camera_request: bool = False,
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
        if (
            call.name == "robot.camera.preview"
            and not confirmed
            and not deterministic_camera_request
        ):
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.DENIED,
                error=(
                    "Temporary AI camera preview requires a clear user capture "
                    "request handled by the trusted service."
                ),
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
        camera_claimed = False
        if call.name == "robot.camera.preview" and not confirmed:
            camera_claimed = self._policy.camera_grants.claim(
                session_id,
                lease_id=lease_id,
            )
            if not camera_claimed:
                return ToolExecutionResult(
                    call_id=call.call_id,
                    tool_name=call.name,
                    status=ToolExecutionStatus.DENIED,
                    error="The one-shot AI camera grant is unavailable or already in use.",
                )
        invocation = ToolInvocation(
            call=call,
            session_id=session_id,
            lease_id=lease_id,
        )
        await self._present(
            "action",
            lambda: self._presentation.action_started(call.name),
            session_id=session_id,
        )
        if camera_claimed and not self._policy.camera_grants.claim_is_active(
            session_id,
            lease_id=lease_id,
        ):
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolExecutionStatus.DENIED,
                error="AI camera access was revoked before capture began.",
            )
        camera_preview_delivered = False
        try:
            result = await self._tools.call(invocation, cancellation)
            recovery = self._recovery.decide(
                definition,
                result,
                attempts_completed=1,
            )
            if recovery.action is RecoveryAction.RETRY:
                result = await self._tools.call(invocation, cancellation)
            if (
                call.name == "robot.behavior.stop"
                and result.status is ToolExecutionStatus.SUCCEEDED
            ):
                self._policy.camera_grants.revoke(session_id)
            if (
                call.name == "robot.camera.preview"
                and result.status is ToolExecutionStatus.SUCCEEDED
                and isinstance(result.data, dict)
            ):
                preview = result.data.get("jpeg_base64")
                camera_preview_delivered = (
                    result.data.get("captured") is True
                    and isinstance(preview, str)
                    and bool(preview)
                )
                if camera_preview_delivered:
                    await self._events.publish(
                        AgentEventType.MEDIA,
                        "Temporary AI camera preview is ready.",
                        session_id=session_id,
                        correlation_id=call.call_id,
                        data={
                            "kind": "camera_preview",
                            "jpeg_base64": preview,
                            "width": result.data.get("width"),
                            "height": result.data.get("height"),
                            "format": result.data.get("format"),
                        },
                        retain=False,
                    )
                safe_data = dict(result.data)
                safe_data.pop("jpeg_base64", None)
                result = result.model_copy(update={"data": safe_data})
        finally:
            if camera_claimed:
                self._policy.camera_grants.finish(
                    session_id,
                    lease_id=lease_id,
                    succeeded=camera_preview_delivered,
                )
            await self._present(
                "thinking",
                lambda: self._presentation.action_finished(call.name),
                session_id=session_id,
            )
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

    async def _present(
        self,
        state: str,
        operation: Callable[[], Awaitable[None]],
        *,
        session_id: str,
    ) -> None:
        try:
            await operation()
        except Exception as exc:
            await self._events.publish(
                AgentEventType.ERROR,
                f"Robot presentation state '{state}' was unavailable.",
                session_id=session_id,
                data={"error": f"{type(exc).__name__}: {exc}"},
            )


def _normalize_behavior_tool_call(
    call: ToolCall,
    *,
    available_tool_names: set[str],
) -> ToolCall:
    """Correct a known model routing error without weakening motion policy."""
    expression_tool = "robot.behavior.execute_expression"
    movement_tool = "robot.behavior.execute_movement"
    if (
        call.name == expression_tool
        and movement_tool in available_tool_names
        and _contains_explicit_motion(call.arguments)
    ):
        return call.model_copy(update={"name": movement_tool})
    return call


def _contains_explicit_motion(value: Any) -> bool:
    """Return whether structured arguments explicitly describe servo motion."""
    if isinstance(value, list):
        return any(_contains_explicit_motion(item) for item in value)
    if not isinstance(value, dict):
        return False

    movement = value.get("movement")
    if isinstance(movement, str) and movement.strip():
        return True
    if isinstance(value.get("drive_targets"), dict):
        return True
    if isinstance(value.get("servo_role"), str):
        return True

    kind = value.get("kind")
    if isinstance(kind, str) and kind.casefold() in {"drive", "servo"}:
        return True
    role = value.get("role")
    if isinstance(role, str) and role.casefold() in {"drive", "move", "movement", "turn"}:
        return True

    return any(_contains_explicit_motion(item) for item in value.values())


_ENGLISH_CAMERA_OBJECT = re.compile(
    r"\b(?:photo(?:graph)?s?|pictures?|snapshots?)\b",
)
_ENGLISH_CAPTURE_ACTION = re.compile(
    r"\b(?:take|capture|shoot|snap|photograph)\b",
)
_ENGLISH_NEGATED_CAPTURE = re.compile(
    r"\b(?:do\s+not|don't|dont|never|not)\s+"
    r"(?:please\s+)?(?:take|capture|shoot|snap|photograph)\b",
)
_JAPANESE_CAMERA_OBJECTS = ("写真", "撮影", "画像")
_JAPANESE_CAPTURE_ACTIONS = ("撮って", "撮る", "撮影して", "写して")
_JAPANESE_CAPTURE_NEGATIONS = (
    "撮らない",
    "撮らないで",
    "撮影しない",
    "撮影しないで",
    "写さない",
    "写さないで",
)


def _is_camera_preview_request(text: str) -> bool:
    """Recognize conservative English and Japanese requests to capture a photo."""
    normalized = unicodedata.normalize("NFKC", text).casefold().strip()
    if not normalized:
        return False
    if _is_normalized_camera_preview_rejection(normalized):
        return False
    if _ENGLISH_CAMERA_OBJECT.search(normalized) and _ENGLISH_CAPTURE_ACTION.search(normalized):
        return True
    if any(negation in normalized for negation in _JAPANESE_CAPTURE_NEGATIONS):
        return False
    return any(item in normalized for item in _JAPANESE_CAMERA_OBJECTS) and any(
        action in normalized for action in _JAPANESE_CAPTURE_ACTIONS
    )


def _is_camera_preview_rejection(text: str) -> bool:
    """Recognize explicit English and Japanese instructions not to capture."""
    normalized = unicodedata.normalize("NFKC", text).casefold().strip()
    return bool(normalized) and _is_normalized_camera_preview_rejection(normalized)


def _is_normalized_camera_preview_rejection(normalized: str) -> bool:
    english_rejection = (
        _ENGLISH_CAMERA_OBJECT.search(normalized) is not None
        and _ENGLISH_NEGATED_CAPTURE.search(normalized) is not None
    )
    japanese_rejection = any(item in normalized for item in _JAPANESE_CAMERA_OBJECTS) and any(
        negation in normalized for negation in _JAPANESE_CAPTURE_NEGATIONS
    )
    return english_rejection or japanese_rejection
