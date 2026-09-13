"""Bounded retrieval and deterministic memory-capture policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .memory_models import BehaviorAttemptStatus, MemoryItem
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


@dataclass(frozen=True, slots=True)
class PersonalizationCaptureOutcome:
    robot_name: str | None = None
    preferred_form_of_address: str | None = None
    preference_saved: bool = False


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
            if _normal_behavior_interruption(result):
                return MemoryCaptureOutcome()
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
    ) -> PersonalizationCaptureOutcome | None:
        """Capture explicit personalization plus narrow first-person preferences."""
        robot_name = _robot_name_update(text)
        form_of_address = _preferred_form_of_address(text)
        if robot_name is not None or form_of_address is not None:
            await self._store.update_personalization(
                user_id,
                preferred_robot_name=robot_name,
                preferred_form_of_address=form_of_address,
                actor="explicit-chat-personalization",
            )
            return PersonalizationCaptureOutcome(
                robot_name=robot_name,
                preferred_form_of_address=form_of_address,
            )
        if _is_profile_update(text.casefold()):
            return None
        content = _preference_content(text)
        if content is None:
            return None
        existing = await self._store.memories(user_id, kind=MemoryKind.PREFERENCE, limit=100)
        if any(item.content.casefold() == content.casefold() for item in existing):
            return None
        await self._store.add_memory(
            user_id,
            MemoryKind.PREFERENCE,
            content,
            payload={"inferred": True, "source": "first-person preference statement"},
            source_session_id=session_id,
            confidence=0.8,
            actor="automatic-preference-capture",
        )
        return PersonalizationCaptureOutcome(preference_saved=True)


class MemoryRetrievalService:
    """Produce small, user-scoped context and read-only structured results."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def context(self, user_id: str, query: str) -> str:
        settings = await self._store.settings()
        profile = await self._store.profile(user_id)
        preferred_form_of_address = await self._store.preference_value(
            user_id,
            "preferred_form_of_address",
        )
        preferences = await self._store.memories(
            user_id,
            kind=MemoryKind.PREFERENCE,
            limit=100,
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
        recent_successes = await self._store.memories(
            user_id,
            kind=MemoryKind.SUCCESSFUL_BEHAVIOR,
            limit=min(2, settings.retrieval_limit),
        )
        recent_recipes = await self._store.memories(
            user_id,
            kind=MemoryKind.TASK_RECIPE,
            limit=1,
        )
        anchored = tuple(
            item for item in (*recent_successes, *recent_recipes) if _retrievable(item)
        )
        selected = (
            *relevant,
            *(
                item
                for item in anchored
                if item.memory_id not in {match.memory_id for match in relevant}
            ),
        )[: settings.retrieval_limit]
        lines = [
            f"Active user: {profile.display_name} ({profile.role.value}).",
            f"Current robot name: {profile.preferred_robot_name or 'NinjaAgent'}.",
        ]
        if isinstance(preferred_form_of_address, str) and preferred_form_of_address:
            lines.append(f"Preferred form of address: {_single_line(preferred_form_of_address)}.")
        preferences = tuple(
            sorted(
                (item for item in preferences if _retrievable(item)),
                key=lambda item: item.payload.get("inferred") is not False,
            )
        )[:4]
        lines.extend(
            (
                "Confirmed preference: "
                if item.payload.get("inferred") is False
                else "Unconfirmed suggestion: "
            )
            + _single_line(item.content)
            for item in preferences
            if not item.sensitive
            and item.payload.get("preference_key") != "preferred_form_of_address"
        )
        lines.extend(
            f"{item.kind.value}: {_single_line(item.content)}"
            for item in selected
            if not item.sensitive
        )
        return _bounded_lines(lines, settings.retrieval_character_budget)

    async def profile_payload(self, user_id: str) -> dict[str, Any]:
        profile = await self._store.profile(user_id)
        preferred_form_of_address = await self._store.preference_value(
            user_id,
            "preferred_form_of_address",
        )
        return {
            "user_id": profile.user_id,
            "display_name": profile.display_name,
            "preferred_robot_name": profile.preferred_robot_name,
            "preferred_form_of_address": preferred_form_of_address,
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


def _retrievable(item: MemoryItem) -> bool:
    return not item.sensitive and (item.expires_at is None or item.expires_at > datetime.now(UTC))


def _attempt_status(status: ToolExecutionStatus) -> BehaviorAttemptStatus:
    return BehaviorAttemptStatus(status.value)


def _normal_behavior_interruption(result: ToolExecutionResult) -> bool:
    """Exclude an obstacle-controlled stop from success and failure learning."""
    data = result.data
    return bool(
        isinstance(data, dict)
        and data.get("interrupted") is True
        and isinstance(data.get("interruption"), dict)
        and data["interruption"].get("stop_reason") == "front_obstacle"
    )


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
        r"(?i)(?:^|[.!?]\s+)(?:please\s+)?rename yourself to\s+([^.!?]{1,80})",
        r"(?i)(?:^|[.!?]\s+)(?:please\s+)?change your name to\s+([^.!?]{1,80})",
        r"(?i)(?:^|[.!?]\s+)from now on[,]?\s+(?:your name is|you are)\s+([^.!?]{1,80})",
        r"(?i)(?:^|[.!?]\s+)(?:hi[,!]?[ ]+)?I want to call you\s+(.{1,80}?)"
        r"(?=[.!?]|\s+and\s+(?:please\s+)?call me\b|$)",
        r"(?i)(?:^|[.!?]\s+)(?:I(?:'ll| will) call you)\s+(.{1,80}?)"
        r"(?=[.!?]|\s+and\s+(?:please\s+)?call me\b|$)",
        r"^あなたの名前を(.{1,40}?)に変更してください[。！!]?$",
        r"(?:^|[。！!？?]\s*)あなたを(.{1,40}?)と呼びたい(?:です)?[。！!？?]?",
    )
    for pattern in patterns:
        match = re.search(pattern, stripped)
        if match:
            name = match.group(1).strip(" \"'“”‘’")
            if name and not any(character in name for character in "=;；"):
                return name
    return None


def _preferred_form_of_address(text: str) -> str | None:
    """Extract a direct request for how the assistant should address the user."""
    stripped = " ".join(text.strip().split())
    patterns = (
        r"(?i)(?:^|[.!?]\s+|\band\s+)(?:please\s+)?call me\s+([^.!?]{1,80})",
        r"(?i)(?:^|[.!?]\s+)I want you to call me\s+([^.!?]{1,80})",
        r"(?i)(?:^|[.!?]\s+)from now on[,]?\s+(?:please\s+)?call me\s+([^.!?]{1,80})",
        r"(?:^|[。！!？?]\s*)私を(.{1,40}?)と呼んでください[。！!？?]?",
    )
    for pattern in patterns:
        match = re.search(pattern, stripped)
        if match:
            address = match.group(1).strip(" \"'“”‘’,，")
            if address and not any(character in address for character in "=;；"):
                return address
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
        "retrieval_reason": (
            "matched current preference"
            if item.kind is MemoryKind.PREFERENCE and item.payload.get("inferred") is False
            else "matched stored content"
        ),
        "created_at": item.created_at.isoformat(),
        **memory_explanation(item),
    }


def memory_explanation(item: MemoryItem) -> dict[str, Any]:
    """Explain existing records without inventing historical source or confirmation."""
    if item.kind is MemoryKind.PREFERENCE:
        category = (
            "confirmed_preference"
            if item.payload.get("inferred") is False
            else "unconfirmed_suggestion"
        )
    elif item.kind in {MemoryKind.SUCCESSFUL_BEHAVIOR, MemoryKind.FAILED_BEHAVIOR}:
        category = "task_outcome"
    elif item.expires_at is not None:
        category = "temporary_context"
    else:
        category = "unconfirmed_suggestion" if item.payload.get("inferred") else item.kind.value
    return {
        "category": category,
        "saved_reason": item.payload.get("review_reason")
        or item.payload.get("source")
        or "Historical reason was not recorded.",
        "last_confirmed_at": item.payload.get("last_confirmed_at"),
        "source": {
            "session": item.source_session_id,
            "message": item.source_message_id,
            "action": item.source_action_id,
        },
        "updated_at": item.updated_at.isoformat(),
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
    }
