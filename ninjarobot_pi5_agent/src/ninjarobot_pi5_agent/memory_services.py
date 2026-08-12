"""Bounded retrieval and deterministic memory-capture policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .memory_models import BehaviorAttemptStatus, MemoryItem, UserProfile
from .memory_store import MemoryStore
from .models import MemoryKind, ToolExecutionResult, ToolExecutionStatus, ToolInvocation

BEHAVIOR_TOOLS = frozenset(
    {
        "robot.behavior.execute_expression",
        "robot.behavior.execute_movement",
        "robot.behavior.run",
        "robot.behavior.save_user",
        "robot.servo.move",
        "robot.display.show_text",
        "robot.display.clear",
        "robot.buzzer.play_tone",
    }
)
NEW_BEHAVIOR_TOOLS = frozenset(
    {
        "robot.behavior.execute_expression",
        "robot.behavior.execute_movement",
    }
)


@dataclass(frozen=True, slots=True)
class MemoryCaptureOutcome:
    confirmation_needed: bool = False
    automatically_saved_kind: MemoryKind | None = None


class MemoryCaptureService:
    """Record technical outcomes without granting models a mutation surface."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def observe_tool_result(
        self,
        user_id: str,
        invocation: ToolInvocation,
        result: ToolExecutionResult,
    ) -> MemoryCaptureOutcome:
        """Record a final behavior result and return whether confirmation is needed."""
        if invocation.call.name not in BEHAVIOR_TOOLS:
            return MemoryCaptureOutcome()
        status = _attempt_status(result.status)
        result_payload = result.model_dump(mode="json")
        attempt = await self._store.record_behavior_attempt(
            user_id,
            tool_name=invocation.call.name,
            request=invocation.call.arguments,
            result=result_payload,
            status=status,
            action_id=result.action_id,
            failure_class=_failure_class(result),
        )
        if result.status is ToolExecutionStatus.SUCCEEDED:
            if invocation.call.name in NEW_BEHAVIOR_TOOLS:
                await self._store.set_pending_behavior_confirmation(
                    user_id,
                    invocation.session_id,
                    attempt.attempt_id,
                )
                return MemoryCaptureOutcome(confirmation_needed=True)
            if invocation.call.name == "robot.behavior.run":
                content = _task_recipe_content(invocation.call.arguments)
                existing = await self._store.memories(
                    user_id,
                    kind=MemoryKind.TASK_RECIPE,
                    limit=100,
                )
                if not any(item.content == content for item in existing):
                    await self._store.add_memory(
                        user_id,
                        MemoryKind.TASK_RECIPE,
                        content,
                        payload={
                            "tool_name": invocation.call.name,
                            "request": invocation.call.arguments,
                            "action_id": result.action_id,
                            "inferred": True,
                        },
                        source_session_id=invocation.session_id,
                        source_action_id=result.action_id,
                        actor="automatic-task-recipe-capture",
                    )
                    return MemoryCaptureOutcome(automatically_saved_kind=MemoryKind.TASK_RECIPE)
            return MemoryCaptureOutcome()
        if result.status in {
            ToolExecutionStatus.FAILED,
            ToolExecutionStatus.TIMED_OUT,
            ToolExecutionStatus.CANCELLED,
        }:
            settings = await self._store.settings()
            await self._store.add_memory(
                user_id,
                MemoryKind.FAILED_BEHAVIOR,
                f"{invocation.call.name} failed technically: {result.error or result.status.value}",
                payload={
                    "tool_name": invocation.call.name,
                    "request": invocation.call.arguments,
                    "result": result_payload,
                    "attempt_id": attempt.attempt_id,
                },
                source_session_id=invocation.session_id,
                source_action_id=result.action_id,
                expires_at=datetime.now(UTC)
                + timedelta(days=settings.failed_behavior_retention_days),
                actor="automatic-failure-capture",
            )
        return MemoryCaptureOutcome()

    async def capture_inferred_preference(
        self,
        user_id: str,
        text: str,
        *,
        session_id: str,
    ) -> MemoryItem | UserProfile | None:
        """Capture only narrow, first-person preference forms with a visible notice."""
        robot_name = _robot_name_update(text)
        if robot_name is not None:
            return await self._store.update_profile(
                user_id,
                preferred_robot_name=robot_name,
                actor="explicit-chat-robot-rename",
            )
        if _is_profile_update(text.casefold()):
            return None
        content = _preference_content(text)
        if content is None:
            return None
        existing = await self._store.memories(user_id, kind=MemoryKind.PREFERENCE, limit=100)
        if any(item.content.casefold() == content.casefold() for item in existing):
            return None
        return await self._store.add_memory(
            user_id,
            MemoryKind.PREFERENCE,
            content,
            payload={"inferred": True, "source": "first-person preference statement"},
            source_session_id=session_id,
            confidence=0.8,
            actor="automatic-preference-capture",
        )


class MemoryRetrievalService:
    """Produce small, user-scoped context and read-only structured results."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def context(self, user_id: str, query: str) -> str:
        settings = await self._store.settings()
        profile = await self._store.profile(user_id)
        preferences = await self._store.memories(
            user_id,
            kind=MemoryKind.PREFERENCE,
            limit=3,
        )
        relevant = await self._store.search(
            user_id,
            query,
            kinds=(
                MemoryKind.TASK_RECIPE,
                MemoryKind.SUCCESSFUL_BEHAVIOR,
                MemoryKind.FAILED_BEHAVIOR,
                MemoryKind.EPISODIC_SUMMARY,
            ),
            limit=settings.retrieval_limit,
        )
        lines = [
            f"Active user: {profile.display_name} ({profile.role.value}).",
            f"Current robot name: {profile.preferred_robot_name or 'NinjaAgent'}.",
        ]
        lines.extend(f"Preference: {_single_line(item.content)}" for item in preferences)
        lines.extend(
            f"{item.kind.value}: {_single_line(item.content)}"
            for item in relevant
            if not item.sensitive
        )
        return _bounded_lines(lines, settings.retrieval_character_budget)

    async def profile_payload(self, user_id: str) -> dict[str, Any]:
        profile = await self._store.profile(user_id)
        return {
            "user_id": profile.user_id,
            "display_name": profile.display_name,
            "preferred_robot_name": profile.preferred_robot_name,
            "role": profile.role.value,
            "face_status": profile.face_status.value,
        }

    async def search_payload(
        self,
        user_id: str,
        query: str,
        *,
        kinds: tuple[MemoryKind, ...] = (),
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        items = await self._store.search(user_id, query, kinds=kinds, limit=limit)
        return [_public_memory(item) for item in items if not item.sensitive]

    async def list_payload(
        self,
        user_id: str,
        kind: MemoryKind,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        items = await self._store.memories(user_id, kind=kind, limit=limit)
        return [_public_memory(item) for item in items if not item.sensitive]


def _attempt_status(status: ToolExecutionStatus) -> BehaviorAttemptStatus:
    return BehaviorAttemptStatus(status.value)


def _failure_class(result: ToolExecutionResult) -> str | None:
    if result.status is ToolExecutionStatus.SUCCEEDED:
        return None
    if result.status is ToolExecutionStatus.TIMED_OUT:
        return "timeout"
    if result.status is ToolExecutionStatus.CANCELLED:
        return "cancelled"
    error = (result.error or "unknown").casefold()
    if "unavailable" in error or "driver" in error:
        return "hardware_or_driver"
    if "invalid" in error or "validation" in error:
        return "validation"
    return "execution"


def _preference_content(text: str) -> str | None:
    stripped = " ".join(text.strip().split())
    patterns = (
        r"(?i)\bI prefer\s+(.{1,160}?)[.!?]?$",
        r"(?i)\bI (?:really )?like\s+(.{1,160}?)[.!?]?$",
        r"(?i)\bmy favorite\s+(.{1,80}?)\s+is\s+(.{1,100}?)[.!?]?$",
        r"(.{1,120}?)(?:が好きです|が好きだ)[。！!]?$",
    )
    for pattern in patterns:
        match = re.search(pattern, stripped)
        if match:
            value = " ".join(part.strip() for part in match.groups() if part is not None)
            return f"User preference: {value}"
    return None


def _robot_name_update(text: str) -> str | None:
    """Extract only explicit commands that rename the assistant itself."""
    stripped = " ".join(text.strip().split())
    patterns = (
        r"(?i)(?:^|[.!?]\s+)(?:please\s+)?rename yourself to\s+(.{1,80}?)[.!?]?$",
        r"(?i)^(?:please\s+)?change your name to\s+(.{1,80}?)[.!?]?$",
        r"(?i)^from now on[,]?\s+(?:your name is|you are)\s+(.{1,80}?)[.!?]?$",
        r"^あなたの名前を(.{1,40}?)に変更してください[。！!]?$",
    )
    for pattern in patterns:
        match = re.search(pattern, stripped)
        if match:
            name = match.group(1).strip(" \"'“”‘’")
            if name and not any(character in name for character in "=;；"):
                return name
    return None


def _task_recipe_content(arguments: dict[str, Any]) -> str:
    behavior = arguments.get("behavior_id") or arguments.get("name") or "saved behavior"
    return f"Successful task recipe: run behavior {behavior}."


def _is_profile_update(normalized: str) -> bool:
    return normalized.startswith(
        ("/update profile", "please update my profile", "個人資料を更新してください")
    )


def _single_line(value: str) -> str:
    return " ".join(value.split())[:500]


def _bounded_lines(lines: list[str], budget: int) -> str:
    selected: list[str] = []
    used = 0
    for line in lines:
        addition = len(line) + (1 if selected else 0)
        if used + addition > budget:
            break
        selected.append(line)
        used += addition
    return "\n".join(selected)


def _public_memory(item: MemoryItem) -> dict[str, Any]:
    return {
        "memory_id": item.memory_id,
        "kind": item.kind.value,
        "content": _single_line(item.content),
        "confidence": item.confidence,
        "created_at": item.created_at.isoformat(),
    }
