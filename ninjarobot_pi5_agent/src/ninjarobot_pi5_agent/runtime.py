"""Single-owner in-process agent application used by CLI and web interfaces."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from ninjarobot_pi5_ide import RiskLevel

from .agent_loop import AgentLoop, AgentReply, TextDeltaHandler
from .events import AgentEventType, EventBroker
from .model_selection import ModelCatalogEntry, ModelManager
from .models import ProviderHealth, ToolCall, ToolExecutionResult, ToolInvocation
from .persistence import ConversationStore
from .policy import MotionArmManager, PolicyContext, PolicyEngine
from .providers import LLMProvider
from .skills import SkillRepository
from .tools import CancellationToken, ToolRegistry


class AgentRuntime:
    """Own model, tools, transcript, motion arms, and shared events exactly once."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        tools: ToolRegistry,
        store: ConversationStore,
        loop: AgentLoop,
        policy: PolicyEngine,
        motion_arms: MotionArmManager,
        skills: SkillRepository,
        events: EventBroker,
        model_manager: ModelManager | None = None,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.store = store
        self.loop = loop
        self.policy = policy
        self.motion_arms = motion_arms
        self.skills = skills
        self.events = events
        self.models = model_manager
        self._started = False
        self._closed = False
        self._active_operations = 0
        self._switching_model = False
        self._chat_lock = asyncio.Lock()
        self._motion_cancellations: dict[str, set[CancellationToken]] = {}

    async def start(self) -> None:
        """Start persistence and all tool providers transactionally."""
        if self._closed:
            raise RuntimeError("agent runtime is closed")
        if self._started:
            return
        await self.store.start()
        try:
            await self.tools.start()
        except BaseException:
            await self.store.close()
            raise
        self._started = True

    async def chat(
        self,
        *,
        session_id: str,
        text: str,
        skill_id: str | None = None,
        lease_id: str | None = None,
        confirmed: bool = False,
        cancellation: CancellationToken | None = None,
        on_text_delta: TextDeltaHandler | None = None,
    ) -> AgentReply:
        """Run one chat through the bounded loop."""
        self._ensure_started()
        self._begin_operation()
        try:
            async with self._chat_lock:
                skill = (
                    self.skills.get(
                        skill_id,
                        available_tools={tool.name for tool in self.tools.list_tools()},
                    )
                    if skill_id is not None
                    else None
                )
                return await self.loop.chat(
                    session_id=session_id,
                    text=text,
                    skill=skill,
                    lease_id=lease_id,
                    confirmed=confirmed,
                    cancellation=cancellation,
                    on_text_delta=on_text_delta,
                )
        finally:
            self._end_operation()

    async def status(self) -> dict[str, Any]:
        """Return provider, tool-provider, session, and motion-arm status."""
        self._ensure_started()
        self._begin_operation()
        try:
            provider = await self.provider.health()
            tool_health = await self.tools.health()
            sessions = await self.store.sessions()
            return {
                "started": True,
                "provider": provider.model_dump(mode="json"),
                "model_selection": self.models.selection() if self.models else None,
                "tool_providers": [report.model_dump(mode="json") for report in tool_health],
                "tools": [tool.name for tool in self.tools.list_tools()],
                "session_count": len(sessions),
            }
        finally:
            self._end_operation()

    async def history(self, session_id: str) -> list[dict[str, Any]]:
        """Return one ordered transcript."""
        self._ensure_started()
        return [
            message.model_dump(mode="json") for message in await self.store.messages(session_id)
        ]

    async def sessions(self) -> list[dict[str, Any]]:
        """Return recent session metadata."""
        self._ensure_started()
        return [session.model_dump(mode="json") for session in await self.store.sessions()]

    async def clear(self, session_id: str) -> int:
        """Clear one transcript without deleting its session identity."""
        self._ensure_started()
        return await self.store.clear_session(session_id)

    def arm_motion(
        self,
        session_id: str,
        *,
        confirmed: bool,
        lease_id: str | None = None,
    ) -> None:
        """Arm physical motion for one bounded session."""
        self._ensure_started()
        self.motion_arms.arm(
            session_id,
            confirmed=confirmed,
            lease_id=lease_id,
        )

    def disarm_motion(self, session_id: str) -> None:
        """Revoke one session's consent and cancel its active motion tools."""
        self.motion_arms.disarm(session_id)
        self.loop.cancel_session(session_id)
        for token in self._motion_cancellations.pop(session_id, set()):
            token.cancel()

    async def stop_and_disarm_motion(
        self,
        session_id: str,
        *,
        lease_id: str | None = None,
        requested_by: str = "local-controller",
    ) -> ToolExecutionResult:
        """Revoke consent, cancel motion work, and request an immediate servo stop."""
        self.disarm_motion(session_id)
        return await self.execute_tool(
            tool_name="robot.servo.stop",
            arguments={},
            session_id=session_id,
            lease_id=lease_id,
            requested_by=requested_by,
        )

    async def execute_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str,
        lease_id: str | None = None,
        confirmed: bool = False,
        requested_by: str = "local-controller",
        cancellation: CancellationToken | None = None,
    ) -> ToolExecutionResult:
        """Execute one catalog tool through the same non-bypassable policy boundary."""
        self._ensure_started()
        self._begin_operation()
        try:
            return await self._execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                session_id=session_id,
                lease_id=lease_id,
                confirmed=confirmed,
                requested_by=requested_by,
                cancellation=cancellation,
            )
        finally:
            self._end_operation()

    async def _execute_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str,
        lease_id: str | None,
        confirmed: bool,
        requested_by: str,
        cancellation: CancellationToken | None,
    ) -> ToolExecutionResult:
        definition = self.tools.get(tool_name)
        decision = self.policy.evaluate(
            definition,
            PolicyContext(
                session_id=session_id,
                lease_id=lease_id,
                confirmed=confirmed,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)
        call_id = f"control-{uuid.uuid4().hex}"
        await self.events.publish(
            AgentEventType.TOOL,
            f"Starting {tool_name}.",
            session_id=session_id,
            correlation_id=call_id,
            data={"tool": tool_name},
        )
        effective_cancellation = cancellation
        if definition.risk is RiskLevel.MOTION:
            effective_cancellation = cancellation or CancellationToken()
            self._motion_cancellations.setdefault(session_id, set()).add(effective_cancellation)
        try:
            result = await self.tools.call(
                ToolInvocation(
                    call=ToolCall(
                        call_id=call_id,
                        name=tool_name,
                        arguments=arguments,
                    ),
                    session_id=session_id,
                    requested_by=requested_by,
                    lease_id=lease_id,
                ),
                effective_cancellation,
            )
        finally:
            if definition.risk is RiskLevel.MOTION and effective_cancellation is not None:
                active = self._motion_cancellations.get(session_id)
                if active is not None:
                    active.discard(effective_cancellation)
                    if not active:
                        self._motion_cancellations.pop(session_id, None)
        event_type = (
            AgentEventType.TOOL if result.status.value == "succeeded" else AgentEventType.ERROR
        )
        await self.events.publish(
            event_type,
            f"{tool_name} {result.status.value}.",
            session_id=session_id,
            correlation_id=call_id,
            data={
                "tool": tool_name,
                "status": result.status.value,
                "error": result.error,
            },
        )
        return result

    async def close(self) -> None:
        """Disarm and close tools, provider, and persistence once."""
        if self._closed:
            return
        self._closed = True
        self._disarm_all_motion()
        await self.tools.close()
        await self.provider.close()
        await self.store.close()
        self._started = False

    async def provider_health(self) -> ProviderHealth:
        """Return model health for lightweight UI checks."""
        self._begin_operation()
        try:
            return await self.provider.health()
        finally:
            self._end_operation()

    async def list_models(self) -> tuple[ModelCatalogEntry, ...]:
        """Return available models from every registered provider."""
        self._ensure_started()
        if self.models is None:
            raise RuntimeError("runtime model selection is not configured")
        return await self.models.catalog()

    def current_model(self) -> dict[str, object]:
        """Return the active provider/model and benchmark acceptance."""
        self._ensure_started()
        if self.models is None:
            raise RuntimeError("runtime model selection is not configured")
        return self.models.selection()

    async def select_model(self, provider_id: str, model: str) -> ModelCatalogEntry:
        """Switch only while the service has no active chat or robot action."""
        self._ensure_started()
        if self.models is None:
            raise RuntimeError("runtime model selection is not configured")
        if self._switching_model or self._active_operations:
            raise RuntimeError(
                "the agent is busy; wait for the current response or robot action to finish"
            )
        self._switching_model = True
        try:
            selected = await self.models.select(provider_id, model)
            self._disarm_all_motion()
            await self.events.publish(
                AgentEventType.SERVICE,
                f"Agent model changed to {provider_id}/{model}.",
                data={
                    "provider": provider_id,
                    "model": model,
                    "accepted": selected.accepted,
                },
            )
            return selected
        finally:
            self._switching_model = False

    def _disarm_all_motion(self) -> None:
        """Revoke all arms and cancel every active motion tool."""
        self.motion_arms.disarm_all()
        self.loop.cancel_all()
        tokens = tuple(
            token
            for session_tokens in self._motion_cancellations.values()
            for token in session_tokens
        )
        self._motion_cancellations.clear()
        for token in tokens:
            token.cancel()

    def _begin_operation(self) -> None:
        if self._switching_model:
            raise RuntimeError("the agent model is currently changing")
        self._active_operations += 1

    def _end_operation(self) -> None:
        self._active_operations -= 1
        if self._active_operations < 0:
            raise RuntimeError("agent operation accounting underflow")

    def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("agent runtime is closed")
        if not self._started:
            raise RuntimeError("agent runtime is not started")
