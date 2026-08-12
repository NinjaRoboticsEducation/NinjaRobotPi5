"""Strict contracts for local, user-scoped long-term memory."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import Field, StringConstraints, model_validator

from .models import AgentContractModel, Identifier, MemoryKind

DisplayName = Annotated[str, StringConstraints(min_length=1, max_length=80)]
MemoryText = Annotated[str, StringConstraints(min_length=1, max_length=20_000)]


class UserRole(StrEnum):
    """Local profile roles; exactly one owner is maintained by the store."""

    OWNER = "owner"
    MEMBER = "member"


class FaceEnrollmentStatus(StrEnum):
    """Identity enrollment state independent from chat availability."""

    PENDING = "pending"
    ENROLLED = "enrolled"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class BehaviorAttemptStatus(StrEnum):
    """Normalized technical outcome of a robot behavior attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class UserProfile(AgentContractModel):
    """One locally stored user profile."""

    user_id: Identifier
    display_name: DisplayName
    preferred_robot_name: DisplayName | None = None
    role: UserRole
    face_status: FaceEnrollmentStatus
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def timestamps_are_ordered(self) -> UserProfile:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("user profile timestamps must include timezone information")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


class FaceProfile(AgentContractModel):
    """Opaque reference to IDE-owned face recognition data."""

    user_id: Identifier
    face_index_name: Identifier
    profile_image_path: str
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    enrolled_at: datetime


class MemorySettings(AgentContractModel):
    """Deterministic retention and capacity limits."""

    conversation_retention_days: Annotated[int, Field(ge=1, le=365)] = 7
    failed_behavior_retention_days: Annotated[int, Field(ge=1, le=3650)] = 180
    failed_behavior_cap: Annotated[int, Field(ge=10, le=100_000)] = 1000
    retrieval_limit: Annotated[int, Field(ge=1, le=20)] = 6
    retrieval_character_budget: Annotated[int, Field(ge=256, le=20_000)] = 4000


class MemoryItem(AgentContractModel):
    """One durable, user-scoped memory record."""

    memory_id: Identifier
    user_id: Identifier
    kind: MemoryKind
    content: MemoryText
    payload: dict[str, Any] = Field(default_factory=dict)
    source_session_id: Identifier | None = None
    source_message_id: Identifier | None = None
    source_action_id: Identifier | None = None
    confidence: Annotated[float, Field(ge=0, le=1)] = 1.0
    sensitive: bool = False
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def timestamps_are_valid(self) -> MemoryItem:
        values = (self.created_at, self.updated_at, self.expires_at)
        if any(value is not None and value.tzinfo is None for value in values):
            raise ValueError("memory timestamps must include timezone information")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


class BehaviorAttempt(AgentContractModel):
    """Technical result linked to an authoritative IDE action when available."""

    attempt_id: Identifier
    user_id: Identifier
    action_id: Identifier | None = None
    tool_name: str
    request: dict[str, Any]
    result: dict[str, Any]
    status: BehaviorAttemptStatus
    failure_class: str | None = None
    memory_id: Identifier | None = None
    user_confirmed: bool = False
    created_at: datetime


class MemoryAuditEvent(AgentContractModel):
    """Non-secret record of a deterministic memory mutation."""

    event_id: Identifier
    operation: str
    actor: str
    target_user_id: Identifier | None = None
    target_memory_id: Identifier | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
