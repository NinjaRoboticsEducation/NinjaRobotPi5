"""Single-owner in-process agent application used by CLI and web interfaces."""

from __future__ import annotations

import asyncio
import re
import unicodedata
import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from ninjarobot_pi5_ide import RiskLevel

from .agent_loop import AgentLoop, AgentReply, TextDeltaHandler
from .events import AgentEventType, EventBroker
from .memory_models import MemorySettings, UserProfile
from .memory_services import (
    MemoryCaptureService,
    MemoryRetrievalService,
    PersonalizationCaptureOutcome,
)
from .memory_store import MemoryStore, ProfileConflictError, ProfileDeletionError
from .model_selection import ModelCatalogEntry, ModelManager
from .models import (
    MemoryKind,
    MessageRole,
    ModelMessage,
    ProviderHealth,
    ToolCall,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolInvocation,
)
from .persistence import ConversationStore
from .policy import CameraGrantManager, MotionArmManager, PolicyContext, PolicyEngine
from .providers import LLMProvider
from .skills import SkillRepository
from .tools import CancellationToken, ToolRegistry

IdentityEnrollment = Callable[[str], Awaitable[dict[str, Any]]]
IdentityRecognition = Callable[[], Awaitable[dict[str, Any]]]
IdentityDeletion = Callable[[str], Awaitable[bool]]
IdentityResetPreparation = Callable[[], Awaitable[str]]
IdentityResetCommit = Callable[[str], Awaitable[bool]]
IdentityResetRollback = Callable[[str], Awaitable[None]]


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
        robot_status: Callable[[], Mapping[str, Any]] | None = None,
        memory: MemoryStore | None = None,
        enroll_identity: IdentityEnrollment | None = None,
        recognize_identity: IdentityRecognition | None = None,
        delete_identity: IdentityDeletion | None = None,
        prepare_identity_reset: IdentityResetPreparation | None = None,
        commit_identity_reset: IdentityResetCommit | None = None,
        rollback_identity_reset: IdentityResetRollback | None = None,
        initial_memory_settings: MemorySettings | None = None,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.store = store
        self.loop = loop
        self.policy = policy
        self.motion_arms = motion_arms
        self.camera_grants: CameraGrantManager = policy.camera_grants
        self.skills = skills
        self.events = events
        self.models = model_manager
        self.memory = memory
        self._memory_capture = MemoryCaptureService(memory) if memory is not None else None
        self._memory_retrieval = MemoryRetrievalService(memory) if memory is not None else None
        self._robot_status = robot_status
        self._enroll_identity = enroll_identity
        self._recognize_identity = recognize_identity
        self._delete_identity = delete_identity
        self._prepare_identity_reset = prepare_identity_reset
        self._commit_identity_reset = commit_identity_reset
        self._rollback_identity_reset = rollback_identity_reset
        self._initial_memory_settings = initial_memory_settings
        self._startup: dict[str, Any] = {
            "phase": "runtime_ready",
            "complete": True,
            "liveliness": "not_managed",
            "detail": None,
        }
        self._started = False
        self._closed = False
        self._active_operations = 0
        self._switching_model = False
        self._chat_lock = asyncio.Lock()
        self._motion_cancellations: dict[str, set[CancellationToken]] = {}
        self._active_users: dict[str, str] = {}
        self._identity_states: dict[str, str] = {}
        self._pending_confirmation_prompts: set[str] = set()
        self._automatic_memory_notices: dict[str, set[str]] = {}
        self.loop.set_active_user_provider(self._active_users.get)
        self.loop.set_memory_context_provider(
            self._memory_context_for_session if memory is not None else None
        )
        self.loop.set_tool_result_observer(self._record_tool_result if memory is not None else None)

    def begin_startup_liveliness(self) -> None:
        """Mark Greeting/Idle startup as pending before the IPC socket is bound."""
        self._startup = {
            "phase": "starting",
            "complete": False,
            "liveliness": "pending",
            "detail": "Waiting for the startup Greeting and Idle supervisor.",
        }

    def complete_startup_liveliness(self) -> None:
        """Mark the startup Greeting and Idle handoff as successful."""
        self._startup = {
            "phase": "ready",
            "complete": True,
            "liveliness": "ready",
            "detail": "Startup Greeting completed; silent Idle is supervised by the IDE.",
        }

    def fail_startup_liveliness(self, error: BaseException) -> None:
        """Record a bounded startup failure while leaving recovery operator-controlled."""
        detail = f"{type(error).__name__}: {error}"
        self._startup = {
            "phase": "degraded",
            "complete": True,
            "liveliness": "failed",
            "detail": detail[:1000],
        }

    def complete_startup_recovery(self) -> None:
        """Mark the service ready after an explicitly confirmed system resume."""
        if self._startup["liveliness"] != "failed":
            return
        self._startup = {
            "phase": "ready",
            "complete": True,
            "liveliness": "recovered",
            "detail": (
                "Confirmed health checks cleared the system latch; silent Idle was restored."
            ),
        }

    async def start(self) -> None:
        """Start persistence and all tool providers transactionally."""
        if self._closed:
            raise RuntimeError("agent runtime is closed")
        if self._started:
            return
        await self.store.start()
        try:
            if self.memory is not None:
                await self.memory.start()
                if self._initial_memory_settings is not None:
                    await self.memory.initialize_settings(self._initial_memory_settings)
                settings = await self.memory.settings()
                self.store.set_retention_days(settings.conversation_retention_days)
                await self.memory.prune()
            await self.store.prune()
            await self.tools.start()
        except BaseException:
            if self.memory is not None:
                await self.memory.close()
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
                identity_reply = await self._handle_identity_chat(
                    session_id,
                    text,
                    on_text_delta=on_text_delta,
                )
                if identity_reply is not None:
                    return identity_reply
                confirmation_reply = await self._handle_behavior_confirmation(
                    session_id,
                    text,
                    on_text_delta=on_text_delta,
                )
                if confirmation_reply is not None:
                    return confirmation_reply
                preference = (
                    await self._capture_preference_safe(session_id, text)
                    if self._memory_capture is not None
                    else None
                )
                skill = (
                    self.skills.get(
                        skill_id,
                        available_tools={tool.name for tool in self.tools.list_tools()},
                    )
                    if skill_id is not None
                    else None
                )
                reply = await self.loop.chat(
                    session_id=session_id,
                    text=text,
                    skill=skill,
                    lease_id=lease_id,
                    confirmed=confirmed,
                    cancellation=cancellation,
                    on_text_delta=on_text_delta,
                )
                notices: list[str] = []
                if isinstance(preference, PersonalizationCaptureOutcome):
                    if preference.robot_name is not None:
                        notices.append(f"Memory saved: robot name is {preference.robot_name}.")
                    if preference.preferred_form_of_address is not None:
                        notices.append(
                            "Memory saved: preferred form of address is "
                            f"{preference.preferred_form_of_address}."
                        )
                    if preference.preference_saved:
                        notices.append("Memory saved: preference.")
                for kind in sorted(self._automatic_memory_notices.pop(session_id, set())):
                    notices.append(f"Memory saved: {kind.replace('_', ' ')}.")
                if session_id in self._pending_confirmation_prompts:
                    self._pending_confirmation_prompts.discard(session_id)
                    notices.append(
                        "Do you want to record this new behavior in long-term memory and the "
                        'IDE catalog? Reply `Yes`, `No`, or `Yes, name it "my behavior"`.'
                    )
                if notices:
                    suffix = "\n\n" + " ".join(notices)
                    await self._append_memory_notice(
                        session_id,
                        " ".join(notices),
                        on_text_delta=on_text_delta,
                    )
                    reply = reply.model_copy(update={"text": reply.text + suffix})
                return reply
        finally:
            self._end_operation()

    async def status(self) -> dict[str, Any]:
        """Return service, model, tool, startup, and persistent robot status."""
        self._ensure_started()
        self._begin_operation()
        try:
            provider = await self.provider.health()
            tool_health = await self.tools.health()
            sessions = await self.store.sessions()
            profiles = await self.memory.profiles() if self.memory is not None else ()
            owner = await self.memory.owner() if self.memory is not None else None
            return {
                **self.startup_status(),
                "provider": provider.model_dump(mode="json"),
                "model_selection": self.models.selection() if self.models else None,
                "tool_providers": [report.model_dump(mode="json") for report in tool_health],
                "tools": [tool.name for tool in self.tools.list_tools()],
                "session_count": len(sessions),
                "memory": {
                    "enabled": self.memory is not None,
                    "profile_count": len(profiles),
                    "owner_user_id": owner.user_id if owner is not None else None,
                },
            }
        finally:
            self._end_operation()

    def startup_status(self) -> dict[str, Any]:
        """Return readiness without model, database, MCP, or hardware health probes."""
        self._ensure_started()
        robot, robot_status_error = self._read_robot_status()
        safety = robot.get("safety") if robot is not None else None
        system_latched = bool(isinstance(safety, Mapping) and safety.get("system_latched") is True)
        motion_latched = bool(isinstance(safety, Mapping) and safety.get("motion_latched") is True)
        liveliness = robot.get("liveliness") if robot is not None else None
        liveliness_degraded = bool(
            isinstance(liveliness, Mapping) and liveliness.get("state") == "degraded"
        )
        startup_complete = self._startup["complete"] is True
        startup_failed = self._startup["liveliness"] == "failed"
        ready = (
            startup_complete
            and not startup_failed
            and not system_latched
            and not liveliness_degraded
        )
        if not startup_complete:
            operational_state = "starting"
        elif system_latched:
            operational_state = "recovery_required"
        elif robot_status_error is not None:
            operational_state = "status_degraded"
            ready = False
        elif startup_failed:
            operational_state = "degraded"
        elif liveliness_degraded:
            operational_state = "liveliness_degraded"
        elif motion_latched:
            operational_state = "motion_latched"
        else:
            operational_state = "ready"
        return {
            "started": True,
            "ready": ready,
            "operational_state": operational_state,
            "startup": dict(self._startup),
            "robot": robot,
            "robot_status_error": robot_status_error,
            "recovery": self._recovery_status(safety, system_latched=system_latched),
        }

    def _read_robot_status(self) -> tuple[dict[str, Any] | None, str | None]:
        if self._robot_status is None:
            return None, None
        try:
            return dict(self._robot_status()), None
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            return None, detail[:1000]

    @staticmethod
    def _recovery_status(
        safety: object,
        *,
        system_latched: bool,
    ) -> dict[str, Any]:
        snapshot = safety if isinstance(safety, Mapping) else {}
        return {
            "required": system_latched,
            "reason": snapshot.get("reason") if system_latched else None,
            "detail": snapshot.get("fault_detail") if system_latched else None,
            "instructions": (
                "Open `ninjarobot-agent chat`, enter `/resume`, and explicitly confirm "
                "the non-moving health checks. Do not delete the safety state file."
                if system_latched
                else None
            ),
        }

    async def history(self, session_id: str) -> list[dict[str, Any]]:
        """Return one ordered transcript."""
        self._ensure_started()
        user_id = await self._user_for_existing_session(session_id)
        return [
            message.model_dump(mode="json")
            for message in await self.store.messages(session_id, user_id=user_id)
        ]

    async def sessions(self) -> list[dict[str, Any]]:
        """Return recent session metadata."""
        self._ensure_started()
        return [session.model_dump(mode="json") for session in await self.store.sessions()]

    async def clear(self, session_id: str) -> int:
        """Clear one transcript without deleting its session identity."""
        self._ensure_started()
        user_id = await self._user_for_existing_session(session_id)
        return await self.store.clear_session(session_id, user_id=user_id)

    async def memory_profiles(self) -> list[dict[str, Any]]:
        """List non-secret profile metadata for the deterministic management UI."""
        self._ensure_started()
        memory = self._require_memory()
        return [profile.model_dump(mode="json") for profile in await memory.profiles()]

    async def memory_items(
        self,
        user_id: str,
        *,
        kind: MemoryKind,
        limit: int,
    ) -> list[dict[str, Any]]:
        """List one selected user's behavioral memory for local administration."""
        self._ensure_started()
        if kind not in {
            MemoryKind.SUCCESSFUL_BEHAVIOR,
            MemoryKind.FAILED_BEHAVIOR,
            MemoryKind.TASK_RECIPE,
        }:
            raise ValueError("only behavioral memory categories can be managed here")
        memory = self._require_memory()
        await memory.profile(user_id)
        return [
            item.model_dump(mode="json")
            for item in await memory.memories(user_id, kind=kind, limit=limit)
        ]

    async def memory_settings(self) -> dict[str, Any]:
        self._ensure_started()
        return (await self._require_memory().settings()).model_dump(mode="json")

    async def update_memory_settings(
        self,
        *,
        conversation_retention_days: int | None = None,
        failed_behavior_retention_days: int | None = None,
        failed_behavior_cap: int | None = None,
    ) -> dict[str, Any]:
        """Update validated retention settings and enforce them immediately."""
        self._ensure_started()
        async with self._chat_lock:
            memory = self._require_memory()
            settings = await memory.update_settings(
                conversation_retention_days=conversation_retention_days,
                failed_behavior_retention_days=failed_behavior_retention_days,
                failed_behavior_cap=failed_behavior_cap,
            )
            self.store.set_retention_days(settings.conversation_retention_days)
            pruned_messages = await self.store.prune()
            pruned_memory = await memory.prune()
        return {
            "settings": settings.model_dump(mode="json"),
            "pruned_messages": pruned_messages,
            "pruned_memory": pruned_memory,
        }

    async def transfer_memory_owner(self, user_id: str) -> None:
        self._ensure_started()
        async with self._chat_lock:
            await self._require_memory().transfer_owner(user_id)

    async def delete_memory_profile(self, user_id: str) -> None:
        """Delete a non-active member after IDE-owned face data is removed."""
        self._ensure_started()
        async with self._chat_lock:
            memory = self._require_memory()
            profile = await memory.profile(user_id)
            if user_id in set(self._active_users.values()):
                raise ProfileDeletionError("the active user profile cannot be deleted")
            if profile.role.value == "owner":
                raise ProfileDeletionError("transfer ownership before deleting the owner profile")
            face = await memory.face_profile(user_id)
            if face is not None:
                if self._delete_identity is None:
                    raise RuntimeError(
                        "IDE face deletion is unavailable; the profile was not deleted"
                    )
                await self._delete_identity(user_id)
            try:
                await memory.delete_profile(
                    user_id,
                    active_user_ids=set(self._active_users.values()),
                )
            except Exception:
                if face is not None:
                    await memory.clear_face_profile(user_id)
                raise

    async def register_memory_profile_face(self, user_id: str) -> dict[str, Any]:
        """Register or replace one selected profile face without switching users."""
        self._ensure_started()
        async with self._chat_lock:
            memory = self._require_memory()
            profile = await memory.profile(user_id)
            message = await self._enroll_profile_face(profile)
            face = await memory.face_profile(user_id)
            return {
                "user_id": user_id,
                "display_name": profile.display_name,
                "face_registered": face is not None,
                "detail": message,
            }

    async def reset_all_memory(self) -> dict[str, Any]:
        """Erase all robot memory after coordinated IDE identity quarantine."""
        self._ensure_started()
        if self._initial_memory_settings is None:
            raise RuntimeError("configured memory defaults are unavailable; reset was not started")
        if (
            self._prepare_identity_reset is None
            or self._commit_identity_reset is None
            or self._rollback_identity_reset is None
        ):
            raise RuntimeError("IDE identity reset is unavailable; robot memory was not changed")
        async with self._chat_lock:
            self._disarm_all_motion()
            self.camera_grants.revoke_all()
            token = await self._prepare_identity_reset()
            database_reset = False
            try:
                deleted = await self._require_memory().reset_all(self._initial_memory_settings)
                database_reset = True
            except BaseException as error:
                try:
                    await self._rollback_identity_reset(token)
                except BaseException as rollback_error:
                    error.add_note(
                        "The IDE could not restore quarantined face data: "
                        f"{type(rollback_error).__name__}: {rollback_error}"
                    )
                raise

            self._active_users.clear()
            self._identity_states.clear()
            self._pending_confirmation_prompts.clear()
            self._automatic_memory_notices.clear()
            self.store.set_retention_days(self._initial_memory_settings.conversation_retention_days)
            try:
                face_data_removed = await self._commit_identity_reset(token)
            except BaseException as error:
                if database_reset:
                    error.add_note(
                        "The memory database was reset, but quarantined face data cleanup failed."
                    )
                raise
            return {
                "reset": True,
                "owner": None,
                "deleted": deleted,
                "face_data_removed": face_data_removed,
                "settings": self._initial_memory_settings.model_dump(mode="json"),
                "next_step": "Start chat to register the new default owner.",
            }

    async def delete_behavior_memory(self, user_id: str, memory_id: str) -> bool:
        """Delete one explicitly selected behavior memory, never a profile or preference."""
        self._ensure_started()
        async with self._chat_lock:
            memory = self._require_memory()
            item = await memory.memory(user_id, memory_id)
            if item.kind not in {
                MemoryKind.SUCCESSFUL_BEHAVIOR,
                MemoryKind.FAILED_BEHAVIOR,
                MemoryKind.TASK_RECIPE,
            }:
                raise ValueError("the selected item is not behavioral memory")
            return await memory.delete_memory(user_id, memory_id)

    async def _handle_identity_chat(
        self,
        session_id: str,
        text: str,
        *,
        on_text_delta: TextDeltaHandler | None,
    ) -> AgentReply | None:
        """Handle explicit profile workflows without delegating mutations to a model."""
        if self.memory is None:
            return None
        stripped = text.strip()
        normalized = stripped.casefold()
        owner = await self.memory.owner()
        state = self._identity_states.get(session_id)

        if owner is None:
            if state != "owner_name":
                self._identity_states[session_id] = "owner_name"
                return await self._identity_reply(
                    session_id,
                    "Welcome! Before we chat, what is your name? The first profile becomes "
                    "the robot owner and default user.",
                    on_text_delta=on_text_delta,
                    persist=False,
                )
            return await self._register_user(
                session_id,
                stripped,
                on_text_delta=on_text_delta,
            )

        await self._ensure_active_user(session_id, owner)
        if normalized == "/cancel":
            self._identity_states.pop(session_id, None)
            return await self._identity_reply(
                session_id,
                "The profile workflow was cancelled.",
                on_text_delta=on_text_delta,
                user_text=stripped,
            )
        if state == "new_user_name":
            return await self._register_user(
                session_id,
                stripped,
                on_text_delta=on_text_delta,
            )
        if state == "switch_user":
            return await self._switch_user(
                session_id,
                stripped,
                on_text_delta=on_text_delta,
            )
        if state == "profile_update":
            return await self._update_active_profile(
                session_id,
                stripped,
                on_text_delta=on_text_delta,
            )

        if normalized == "/new user":
            self._identity_states[session_id] = "new_user_name"
            return await self._identity_reply(
                session_id,
                "What is the new user's name? Enter /cancel to stop registration.",
                on_text_delta=on_text_delta,
                user_text=stripped,
            )
        if normalized.startswith("/new user "):
            return await self._register_user(
                session_id,
                stripped[len("/new user ") :].strip(),
                on_text_delta=on_text_delta,
            )
        if normalized == "/switch user":
            self._identity_states[session_id] = "switch_user"
            profiles = await self.memory.profiles()
            choices = ", ".join(profile.display_name for profile in profiles)
            return await self._identity_reply(
                session_id,
                f"Which user should I switch to? Available profiles: {choices}. "
                "Enter /cancel to keep the current user.",
                on_text_delta=on_text_delta,
                user_text=stripped,
            )
        if normalized.startswith("/switch user "):
            return await self._switch_user(
                session_id,
                stripped[len("/switch user ") :].strip(),
                on_text_delta=on_text_delta,
            )
        if normalized == "/identify":
            return await self._identify_user(
                session_id,
                on_text_delta=on_text_delta,
                user_text=stripped,
            )
        if _is_profile_update_request(normalized):
            details = _profile_update_details(stripped)
            if details:
                return await self._update_active_profile(
                    session_id,
                    details,
                    on_text_delta=on_text_delta,
                    original_text=stripped,
                )
            self._identity_states[session_id] = "profile_update"
            profile = await self.memory.profile(self._active_users[session_id])
            face_state = (
                "registered"
                if profile.face_status.value == "enrolled"
                else f"unregistered ({profile.face_status.value})"
            )
            return await self._identity_reply(
                session_id,
                f"Current profile:\n- Name: {profile.display_name}\n- Face: {face_state}\n"
                "To change the name, enter name=<new name>. To register or update the "
                "profile face, enter register user face. Enter /cancel to stop.",
                on_text_delta=on_text_delta,
                user_text=stripped,
            )
        return None

    async def _handle_behavior_confirmation(
        self,
        session_id: str,
        text: str,
        *,
        on_text_delta: TextDeltaHandler | None,
    ) -> AgentReply | None:
        if self.memory is None or session_id not in self._active_users:
            return None
        confirmation = _parse_behavior_confirmation(text)
        if confirmation is None:
            return None
        accepted, requested_name = confirmation
        attempt = await self.memory.take_pending_behavior_confirmation(
            self._active_users[session_id],
            session_id,
        )
        if attempt is None:
            return None
        if not accepted:
            return await self._identity_reply(
                session_id,
                "The successful behavior was not saved to long-term memory or the IDE catalog.",
                on_text_delta=on_text_delta,
                user_text=text.strip(),
            )
        behavior_name = requested_name or str(
            attempt.request.get("name") or f"saved behavior {attempt.attempt_id[-8:]}"
        )
        catalog_name = _catalog_behavior_name(behavior_name, attempt.attempt_id)
        definition = _executed_behavior_definition(attempt.result, attempt.request)
        definition["name"] = catalog_name
        definition.setdefault("schema_version", 1)
        definition.setdefault(
            "category",
            "movement" if attempt.tool_name.endswith("execute_movement") else "expression",
        )
        definition.setdefault("description", f"User-confirmed behavior: {behavior_name}.")
        memory_item = None
        try:
            memory_item = await self.memory.add_memory(
                attempt.user_id,
                MemoryKind.SUCCESSFUL_BEHAVIOR,
                f'Confirmed successful behavior: "{behavior_name}" (catalog: {catalog_name}).',
                payload={
                    "tool_name": attempt.tool_name,
                    "request": attempt.request,
                    "result": attempt.result,
                    "attempt_id": attempt.attempt_id,
                    "display_name": behavior_name,
                    "catalog_name": catalog_name,
                },
                source_session_id=session_id,
                source_action_id=attempt.action_id,
                actor="confirmed-success-capture",
            )
            saved = await self._execute_tool(
                tool_name="robot.behavior.save_user",
                arguments=definition,
                session_id=session_id,
                lease_id=None,
                confirmed=True,
                requested_by="confirmed-success-capture",
                cancellation=None,
            )
            if saved.status is not ToolExecutionStatus.SUCCEEDED:
                raise RuntimeError(saved.error or "the IDE catalog save failed")
        except Exception as error:
            recovery_errors: list[str] = []
            if memory_item is not None:
                try:
                    await self.memory.delete_memory(
                        attempt.user_id,
                        memory_item.memory_id,
                        actor="confirmed-success-rollback",
                    )
                except Exception as rollback_error:
                    recovery_errors.append(
                        f"memory rollback: {type(rollback_error).__name__}: {rollback_error}"
                    )
            try:
                await self.memory.set_pending_behavior_confirmation(
                    attempt.user_id,
                    session_id,
                    attempt.attempt_id,
                )
            except Exception as pending_error:
                recovery_errors.append(
                    f"confirmation restore: {type(pending_error).__name__}: {pending_error}"
                )
            if recovery_errors:
                await self.events.publish(
                    AgentEventType.ERROR,
                    "Behavior-save recovery was incomplete.",
                    session_id=session_id,
                    data={"errors": recovery_errors},
                )
            return await self._identity_reply(
                session_id,
                (
                    f'Could not save "{behavior_name}" to both memory and the IDE catalog '
                    f"({type(error).__name__}: {error}). The successful behavior was not "
                    "recorded in both destinations. "
                    "Reply Yes again, optionally with a different name such as "
                    '`Yes, name it "my behavior"`.'
                )[:900],
                on_text_delta=on_text_delta,
                user_text=text.strip(),
            )
        if memory_item is None:  # pragma: no cover - guarded by the successful try block
            raise RuntimeError("successful behavior memory was not created")
        try:
            await self.memory.link_behavior_memory(attempt.attempt_id, memory_item.memory_id)
        except Exception as error:
            await self.events.publish(
                AgentEventType.ERROR,
                "Behavior and catalog were saved, but audit linkage failed.",
                session_id=session_id,
                data={"error": f"{type(error).__name__}: {error}"[:500]},
            )
        return await self._identity_reply(
            session_id,
            (
                f'Memory saved: successful behavior "{behavior_name}". '
                f'IDE catalog entry saved as "{catalog_name}".'
            ),
            on_text_delta=on_text_delta,
            user_text=text.strip(),
        )

    async def _memory_context_for_session(self, session_id: str, query: str) -> str:
        if self._memory_retrieval is None:
            return ""
        user_id = self._active_users.get(session_id)
        if user_id is None:
            return ""
        try:
            return await self._memory_retrieval.context(user_id, query)
        except Exception as error:
            await self.events.publish(
                AgentEventType.ERROR,
                "Bounded memory retrieval failed; continuing without memory context.",
                session_id=session_id,
                data={"error": f"{type(error).__name__}: {error}"[:500]},
            )
            return ""

    async def _capture_preference_safe(
        self,
        session_id: str,
        text: str,
    ) -> object | None:
        assert self._memory_capture is not None
        try:
            return await self._memory_capture.capture_inferred_preference(
                self._active_users[session_id],
                text,
                session_id=session_id,
            )
        except Exception as error:
            await self.events.publish(
                AgentEventType.ERROR,
                "Automatic preference capture failed; chat will continue.",
                session_id=session_id,
                data={"error": f"{type(error).__name__}: {error}"[:500]},
            )
            return None

    async def _record_tool_result(
        self,
        invocation: ToolInvocation,
        result: ToolExecutionResult,
    ) -> None:
        if self._memory_capture is None:
            return
        user_id = self._active_users.get(invocation.session_id)
        if user_id is None:
            user_id = await self._user_for_existing_session(invocation.session_id)
        if user_id is None:
            return
        try:
            outcome = await self._memory_capture.observe_tool_result(user_id, invocation, result)
        except Exception as error:
            await self.events.publish(
                AgentEventType.ERROR,
                "Behavior memory capture failed; robot execution remains authoritative.",
                session_id=invocation.session_id,
                data={"error": f"{type(error).__name__}: {error}"[:500]},
            )
            return
        if outcome.confirmation_needed:
            self._pending_confirmation_prompts.add(invocation.session_id)
        if outcome.automatically_saved_kind is not None:
            kind = outcome.automatically_saved_kind.value
            self._automatic_memory_notices.setdefault(invocation.session_id, set()).add(kind)
            await self.events.publish(
                AgentEventType.SERVICE,
                f"Memory saved: {kind}.",
                session_id=invocation.session_id,
                data={"kind": kind},
            )

    async def _append_memory_notice(
        self,
        session_id: str,
        notice: str,
        *,
        on_text_delta: TextDeltaHandler | None,
    ) -> None:
        await self.store.append_message(
            session_id,
            ModelMessage(role=MessageRole.ASSISTANT, content=notice),
            message_id=f"message-{uuid.uuid4().hex}",
            user_id=self._active_users[session_id],
            metadata={"workflow": "memory-notice"},
        )
        if on_text_delta is not None:
            await on_text_delta("\n\n" + notice)

    async def _register_user(
        self,
        session_id: str,
        display_name: str,
        *,
        on_text_delta: TextDeltaHandler | None,
    ) -> AgentReply:
        assert self.memory is not None
        try:
            profile = await self.memory.create_profile(display_name)
        except (ValueError, ProfileConflictError) as error:
            return await self._identity_reply(
                session_id,
                f"I could not create that profile: {error}. Please enter another name or /cancel.",
                on_text_delta=on_text_delta,
                persist=session_id in self._active_users,
                user_text=display_name if session_id in self._active_users else None,
            )
        self._identity_states.pop(session_id, None)
        await self._set_active_user(session_id, profile)
        enrollment = await self._enroll_profile_face(profile)
        return await self._identity_reply(
            session_id,
            f"Profile created for {profile.display_name}. {enrollment}",
            on_text_delta=on_text_delta,
            user_text=display_name,
        )

    async def _enroll_profile_face(self, profile: UserProfile) -> str:
        assert self.memory is not None
        if self._enroll_identity is None:
            return (
                "Camera enrollment is unavailable, so the face profile remains pending. "
                "The profile is still usable. After camera service is restored, run "
                "/update profile and enter register user face."
            )
        try:
            result = await self._enroll_identity(profile.user_id)
        except Exception as error:
            return (
                "Camera enrollment could not complete, so the face profile remains pending "
                f"({type(error).__name__}: {error}). The profile is still usable. Run "
                "'uv sync --frozen --extra hardware', restart the agent service, then run "
                "/update profile and enter register user face."
            )
        if result.get("status") != "enrolled":
            status = str(result.get("status", "failed")).replace("_", " ")
            advice = {
                "no_face": "Center one face in front of the camera with even lighting.",
                "multiple_faces": "Keep only the intended user in the camera frame.",
                "already_known": "That face belongs to another registered profile.",
            }.get(str(result.get("status")), "Check the camera and recognition backend.")
            return (
                f"Face enrollment reported {status}; the face profile remains pending. "
                f"{advice} Run /update profile and enter register user face to retry."
            )
        identity = result.get("identity")
        image_path = result.get("profile_image_path")
        if not isinstance(identity, str) or not isinstance(image_path, str):
            return "Face enrollment returned incomplete data; the face profile remains pending."
        await self.memory.set_face_profile(
            profile.user_id,
            face_index_name=identity,
            profile_image_path=image_path,
            model_metadata={
                "backend": result.get("backend", "pi5camera"),
                "raw_photo_retained": result.get("raw_photo_retained", False),
            },
        )
        action = "updated" if result.get("refreshed") else "completed"
        return (
            f"Face enrollment {action} and only cropped profile images were retained. "
            "The display has returned to Idle."
        )

    async def _switch_user(
        self,
        session_id: str,
        selector: str,
        *,
        on_text_delta: TextDeltaHandler | None,
    ) -> AgentReply:
        assert self.memory is not None
        profiles = await self.memory.profiles()
        matches = [
            profile
            for profile in profiles
            if selector.casefold() in {profile.user_id.casefold(), profile.display_name.casefold()}
        ]
        if len(matches) != 1:
            return await self._identity_reply(
                session_id,
                "No unique profile matched that name. Please enter one listed profile "
                "name or /cancel.",
                on_text_delta=on_text_delta,
                user_text=selector,
            )
        original_user_id = self._active_users[session_id]
        target = matches[0]
        self._identity_states.pop(session_id, None)
        self.disarm_motion(session_id)
        self.revoke_camera(session_id)
        face = await self.memory.face_profile(target.user_id)
        if face is None or target.face_status.value != "enrolled":
            return await self._identity_reply(
                session_id,
                f"{target.display_name} does not have a registered face, so the active user "
                "was not changed. Use Manage Memory > Register or Replace User Face, then retry.",
                on_text_delta=on_text_delta,
                user_text=selector,
                persist_user_id=original_user_id,
            )
        if self._recognize_identity is None:
            return await self._identity_reply(
                session_id,
                "Face recognition is unavailable, so the active user was not changed. Restore "
                "the camera service and recognition backend, then retry.",
                on_text_delta=on_text_delta,
                user_text=selector,
                persist_user_id=original_user_id,
            )
        try:
            result = await self._recognize_identity()
        except Exception as error:
            return await self._identity_reply(
                session_id,
                "Face recognition could not complete, so the active user was not changed "
                f"({type(error).__name__}: {error}). Check the camera service and retry.",
                on_text_delta=on_text_delta,
                user_text=selector,
                persist_user_id=original_user_id,
            )
        status = str(result.get("status", "failed"))
        identity = result.get("identity")
        if status != "recognized" or identity != face.face_index_name:
            advice = {
                "no_face": "Center the selected user's face in front of the camera and retry.",
                "multiple_faces": "Keep only the selected user in the camera frame and retry.",
                "unknown": "The face was not recognized. Check its registration and retry.",
                "recognized": "The face did not match the selected user.",
            }.get(status, "Check the camera and recognition backend, then retry.")
            return await self._identity_reply(
                session_id,
                f"Face verification for {target.display_name} failed; the active user was not "
                f"changed. {advice}",
                on_text_delta=on_text_delta,
                user_text=selector,
                persist_user_id=original_user_id,
            )
        await self._set_active_user(session_id, target)
        return await self._identity_reply(
            session_id,
            f"Face verified. Switched to {target.display_name}. This session now uses only that "
            "user's profile, conversation history, and memory.",
            on_text_delta=on_text_delta,
            user_text=selector,
            persist_user_id=original_user_id,
        )

    async def _identify_user(
        self,
        session_id: str,
        *,
        on_text_delta: TextDeltaHandler | None,
        user_text: str,
    ) -> AgentReply:
        assert self.memory is not None
        message = "Face recognition failed; the active user was not changed."
        if self._recognize_identity is None:
            message = "Face recognition is unavailable; the active user was not changed."
        else:
            try:
                result = await self._recognize_identity()
            except Exception as error:
                result = {"status": "failed"}
                message = (
                    "Face recognition could not complete; the active user was not changed "
                    f"({type(error).__name__}: {error})."
                )
            if result.get("status") == "recognized":
                identity = result.get("identity")
                profiles = await self.memory.profiles()
                matches = []
                for profile in profiles:
                    face = await self.memory.face_profile(profile.user_id)
                    if face is not None and face.face_index_name == identity:
                        matches.append(profile)
                if len(matches) == 1:
                    await self._set_active_user(session_id, matches[0])
                    message = f"Recognized and switched to {matches[0].display_name}."
                else:
                    message = (
                        "The recognized face did not map to one unique profile; no switch occurred."
                    )
            elif result.get("status") in {"no_face", "unknown", "multiple_faces"}:
                status = str(result["status"]).replace("_", " ")
                message = f"Recognition reported {status}; the active user was not changed."
        return await self._identity_reply(
            session_id,
            message,
            on_text_delta=on_text_delta,
            user_text=user_text,
        )

    async def _update_active_profile(
        self,
        session_id: str,
        details: str,
        *,
        on_text_delta: TextDeltaHandler | None,
        original_text: str | None = None,
    ) -> AgentReply:
        assert self.memory is not None
        if details.strip().casefold() == "register user face":
            user_id = self._active_users[session_id]
            profile = await self.memory.profile(user_id)
            self._identity_states.pop(session_id, None)
            enrollment = await self._enroll_profile_face(profile)
            return await self._identity_reply(
                session_id,
                f"Profile face workflow for {profile.display_name}: {enrollment}",
                on_text_delta=on_text_delta,
                user_text=original_text or details,
            )
        updates = _parse_profile_update(details)
        if not updates:
            return await self._identity_reply(
                session_id,
                "I could not parse that update. Enter name=<new name>, "
                "register user face, or /cancel. To rename NinjaAgent, ask it directly "
                "in ordinary chat.",
                on_text_delta=on_text_delta,
                user_text=original_text or details,
            )
        user_id = self._active_users[session_id]
        try:
            profile = await self.memory.update_profile(
                user_id,
                display_name=updates.get("display_name"),
            )
        except (ValueError, ProfileConflictError) as error:
            return await self._identity_reply(
                session_id,
                f"The profile was not changed: {error}.",
                on_text_delta=on_text_delta,
                user_text=original_text or details,
            )
        self._identity_states.pop(session_id, None)
        return await self._identity_reply(
            session_id,
            f"Profile updated for {profile.display_name}.",
            on_text_delta=on_text_delta,
            user_text=original_text or details,
        )

    async def _ensure_active_user(self, session_id: str, owner: UserProfile) -> str:
        if session_id not in self._active_users:
            await self._set_active_user(session_id, owner)
        return self._active_users[session_id]

    async def _set_active_user(self, session_id: str, profile: UserProfile) -> None:
        sessions = await self.store.sessions()
        if any(session.session_id == session_id for session in sessions):
            await self.store.set_session_user(session_id, profile.user_id)
        else:
            await self.store.create_session(session_id, user_id=profile.user_id)
        previous = self._active_users.get(session_id)
        self._active_users[session_id] = profile.user_id
        if previous is not None and previous != profile.user_id:
            self.disarm_motion(session_id)
            self.revoke_camera(session_id)

    async def _user_for_existing_session(self, session_id: str) -> str | None:
        if session_id in self._active_users:
            return self._active_users[session_id]
        if self.memory is None:
            return None
        owner = await self.memory.owner()
        if owner is None:
            return None
        await self._ensure_active_user(session_id, owner)
        return owner.user_id

    async def _identity_reply(
        self,
        session_id: str,
        text: str,
        *,
        on_text_delta: TextDeltaHandler | None,
        persist: bool = True,
        user_text: str | None = None,
        persist_user_id: str | None = None,
    ) -> AgentReply:
        if persist and session_id in self._active_users:
            workflow_user_id = persist_user_id or self._active_users[session_id]
            if user_text:
                await self.store.append_message(
                    session_id,
                    ModelMessage(role=MessageRole.USER, content=user_text),
                    message_id=f"message-{uuid.uuid4().hex}",
                    user_id=workflow_user_id,
                    metadata={"workflow": "profile"},
                )
            await self.store.append_message(
                session_id,
                ModelMessage(role=MessageRole.ASSISTANT, content=text),
                message_id=f"message-{uuid.uuid4().hex}",
                user_id=workflow_user_id,
                metadata={"workflow": "profile"},
            )
        if on_text_delta is not None:
            await on_text_delta(text)
        return AgentReply(session_id=session_id, text=text, model_turns=0, tool_calls=0)

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

    def grant_camera(
        self,
        session_id: str,
        *,
        confirmed: bool,
        lease_id: str | None = None,
    ) -> dict[str, bool | int | None]:
        """Grant the model one fresh temporary, non-retained camera preview."""
        self._ensure_started()
        sequence = self.camera_grants.grant(
            session_id,
            confirmed=confirmed,
            lease_id=lease_id,
        )
        return {
            "ai_camera_granted": True,
            "authorized_for_next_preview": True,
            "captures_remaining": 1,
            "grant_sequence": sequence,
        }

    def revoke_camera(self, session_id: str) -> None:
        """Revoke one session's pending or active camera grant."""
        self.camera_grants.revoke(session_id)

    def camera_granted(
        self,
        session_id: str,
        *,
        lease_id: str | None = None,
    ) -> bool:
        """Return whether one unused camera preview is authorized."""
        return self.camera_grants.is_granted(session_id, lease_id=lease_id)

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

    async def resume_system(
        self,
        session_id: str,
        *,
        confirmed: bool,
        lease_id: str | None = None,
        requested_by: str = "local-controller",
    ) -> ToolExecutionResult:
        """Health-check and clear the system latch without re-arming AI motion."""
        self._ensure_started()
        if not confirmed:
            raise PermissionError("system resume requires explicit confirmation")
        self.disarm_motion(session_id)
        result = await self.execute_tool(
            tool_name="robot.system.resume",
            arguments={"confirmed": True},
            session_id=session_id,
            lease_id=lease_id,
            confirmed=True,
            requested_by=requested_by,
        )
        if result.status is not ToolExecutionStatus.SUCCEEDED:
            detail = result.error or "a required robot health check failed"
            raise RuntimeError(f"system resume failed: {detail}")
        self.complete_startup_recovery()
        return result

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
        await self._record_tool_result(
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
            result,
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
        self.camera_grants.revoke_all()
        await self.tools.close()
        await self.provider.close()
        if self.memory is not None:
            await self.memory.close()
        await self.store.close()
        self._started = False

    async def provider_health(self) -> ProviderHealth:
        """Return model health for lightweight UI checks."""
        self._begin_operation()
        try:
            return await self.provider.health()
        finally:
            self._end_operation()

    async def list_models(
        self,
        provider_id: str | None = None,
    ) -> tuple[ModelCatalogEntry, ...]:
        """Return available models from every registered provider."""
        self._ensure_started()
        if self.models is None:
            raise RuntimeError("runtime model selection is not configured")
        return await self.models.catalog(provider_id)

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
            self.camera_grants.revoke_all()
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

    def _require_memory(self) -> MemoryStore:
        if self.memory is None:
            raise RuntimeError("persistent memory is disabled")
        return self.memory


def _is_profile_update_request(normalized: str) -> bool:
    return normalized.startswith(
        (
            "/update profile",
            "please update my profile",
            "個人資料を更新してください",
        )
    )


def _profile_update_details(text: str) -> str:
    normalized = text.casefold()
    for prefix in (
        "/update profile",
        "please update my profile",
        "個人資料を更新してください",
    ):
        if normalized.startswith(prefix.casefold()):
            return text[len(prefix) :].lstrip(" :：,-")
    return ""


def _parse_profile_update(details: str) -> dict[str, str]:
    updates: dict[str, str] = {}
    for part in re.split(r"[;,；]", details):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        normalized_key = key.strip().casefold().replace(" ", "_")
        normalized_value = " ".join(value.split())
        if not normalized_value:
            continue
        if normalized_key in {"name", "display_name", "名前"}:
            updates["display_name"] = normalized_value
    return updates


def _parse_behavior_confirmation(text: str) -> tuple[bool, str | None] | None:
    """Parse a bounded affirmative or negative reply without consulting the model."""
    stripped = text.strip()
    normalized = stripped.casefold()
    accepted = bool(
        re.match(r"^(?:yes|y)(?=$|[\s,.!?:;])", normalized)
        or re.match(r"^(?:はい|保存する)(?=$|[\s、。,.!！?？:：;；])", normalized)
    )
    declined = bool(
        re.match(r"^(?:no|n)(?=$|[\s,.!?:;])", normalized)
        or re.match(r"^(?:いいえ|保存しない)(?=$|[\s、。,.!！?？:：;；])", normalized)
    )
    if not accepted and not declined:
        return None
    if declined:
        return False, None

    name_patterns = (
        r"(?:name(?:\s+(?:this\s+behavior|it))?|named)\s*(?:as\s*)?[\"“']([^\"”']{1,120})[\"”']",
        r"(?:名前|行動名)(?:を)?[^「]{0,20}「([^」]{1,120})」",
    )
    for pattern in name_patterns:
        match = re.search(pattern, stripped, flags=re.IGNORECASE)
        if match is not None:
            name = " ".join(match.group(1).split())
            if name:
                return True, name
    quoted_names = [
        *re.findall(r'"([^"\n]{1,120})"', stripped),
        *re.findall(r"“([^”\n]{1,120})”", stripped),
        *re.findall(r"「([^」\n]{1,120})」", stripped),
    ]
    if len(quoted_names) == 1:
        name = " ".join(quoted_names[0].split())
        if name:
            return True, name
    return True, None


def _catalog_behavior_name(display_name: str, attempt_id: str) -> str:
    """Convert a user-facing name into the IDE's stable ASCII identifier."""
    ascii_name = (
        unicodedata.normalize("NFKD", display_name).encode("ascii", "ignore").decode("ascii")
    )
    candidate = re.sub(r"[^a-z0-9]+", "_", ascii_name.casefold()).strip("_")
    if candidate and not candidate[0].isalpha():
        candidate = f"behavior_{candidate}"
    if not candidate:
        suffix = re.sub(r"[^a-z0-9]", "", attempt_id.casefold())[-12:] or "saved"
        candidate = f"saved_behavior_{suffix}"
    return candidate[:64].rstrip("_")


def _executed_behavior_definition(
    result: Mapping[str, Any],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the authoritative IDE-compiled definition, with a legacy fallback."""
    data = result.get("data")
    if isinstance(data, Mapping):
        compiled = data.get("compiled_definition")
        if isinstance(compiled, Mapping):
            return dict(compiled)
    return dict(request)
