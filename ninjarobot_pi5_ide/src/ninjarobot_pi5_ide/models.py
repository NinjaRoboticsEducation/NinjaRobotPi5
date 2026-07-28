"""Strict, serializable contracts shared across the V4 control boundary."""

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

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    ),
]
CapabilityName = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
    ),
]
ErrorCode = Annotated[
    str,
    StringConstraints(min_length=3, max_length=96, pattern=r"^[A-Z][A-Z0-9_]+$"),
]


class ContractModel(BaseModel):
    """Base model that rejects unknown fields and unsafe implicit coercion."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RiskLevel(StrEnum):
    """Deterministic safety class attached to every capability."""

    READ_ONLY = "read_only"
    LOW = "low"
    MOTION = "motion"
    PRIVACY = "privacy"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


class ActionStatus(StrEnum):
    """Stable lifecycle states returned by the IDE."""

    ACCEPTED = "accepted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class LifecycleState(StrEnum):
    """Explicit lifecycle shared by registries, schedulers, and the IDE."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class RetrySafety(StrEnum):
    """Whether repeating an operation is known to be safe."""

    SAFE = "safe"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


class ResourceHealth(StrEnum):
    """Non-moving health state for one IDE resource."""

    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


class CapabilityDescriptor(ContractModel):
    """Machine-readable description of one IDE capability."""

    name: CapabilityName
    version: Identifier
    description: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk: RiskLevel
    resources: tuple[Identifier, ...]
    default_timeout_seconds: Annotated[float, Field(gt=0, le=3600)]
    idempotent: bool
    cancellable: bool
    confirmation_required: bool
    persist_result_data: bool = True

    @field_validator("resources")
    @classmethod
    def resources_must_be_unique(cls, resources: tuple[str, ...]) -> tuple[str, ...]:
        """Prevent ambiguous double-lock declarations."""
        if len(resources) != len(set(resources)):
            raise ValueError("resources must not contain duplicates")
        return resources


class ActionRequest(ContractModel):
    """Validated request entering the deterministic IDE control plane."""

    action_id: Identifier
    capability: CapabilityName
    arguments: dict[str, Any]
    requested_by: Identifier
    session_id: Identifier
    deadline: datetime | None = None
    idempotency_key: Identifier

    @field_validator("deadline")
    @classmethod
    def deadline_must_include_timezone(cls, deadline: datetime | None) -> datetime | None:
        """Reject local-time deadlines whose meaning changes across machines."""
        if deadline is not None and deadline.tzinfo is None:
            raise ValueError("deadline must include a timezone")
        return deadline


class ErrorDetails(ContractModel):
    """Serializable error information suitable for users, logs, and providers."""

    code: ErrorCode
    message: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    technical_detail: Annotated[str, StringConstraints(max_length=2000)] | None = None
    definitely_not_executed: bool
    retry_safety: RetrySafety
    capability: CapabilityName | None = None
    action_id: Identifier | None = None


class ActionResult(ContractModel):
    """Normalized IDE result with explicit timing and retry semantics."""

    action_id: Identifier
    status: ActionStatus
    data: dict[str, Any] | None = None
    error: ErrorDetails | None = None
    started_at: datetime
    finished_at: datetime
    retry_safety: RetrySafety

    @model_validator(mode="after")
    def result_is_consistent(self) -> ActionResult:
        """Keep status, error, and timestamps internally consistent."""
        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None:
            raise ValueError("result timestamps must include a timezone")
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not be before started_at")
        failed = self.status in {
            ActionStatus.FAILED,
            ActionStatus.CANCELLED,
            ActionStatus.REJECTED,
        }
        if failed and self.error is None:
            raise ValueError("failed, cancelled, or rejected results require error details")
        if self.status is ActionStatus.SUCCEEDED and self.error is not None:
            raise ValueError("successful results must not include error details")
        if self.error is not None and self.error.retry_safety is not self.retry_safety:
            raise ValueError("result and error retry_safety must agree")
        return self


class ActionRecord(ContractModel):
    """Durable snapshot of one accepted action and its latest known state."""

    request: ActionRequest
    status: ActionStatus
    result: ActionResult | None = None
    accepted_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def record_is_consistent(self) -> ActionRecord:
        """Reject time travel and mismatched terminal records."""
        if self.accepted_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("record timestamps must include a timezone")
        if self.updated_at < self.accepted_at:
            raise ValueError("updated_at must not be before accepted_at")
        if self.result is not None:
            if self.result.action_id != self.request.action_id:
                raise ValueError("record request and result action IDs must agree")
            if self.status is not self.result.status:
                raise ValueError("record and result statuses must agree")
        if (
            self.status
            in {
                ActionStatus.SUCCEEDED,
                ActionStatus.FAILED,
                ActionStatus.CANCELLED,
                ActionStatus.REJECTED,
            }
            and self.result is None
        ):
            raise ValueError("terminal action records require a result")
        if self.status in {ActionStatus.ACCEPTED, ActionStatus.RUNNING} and self.result is not None:
            raise ValueError("non-terminal action records must not contain a result")
        return self


class HealthReport(ContractModel):
    """Safe health snapshot that does not invoke device actions."""

    status: ResourceHealth
    components: dict[Identifier, ResourceHealth]
    checked_at: datetime
    detail: Annotated[str, StringConstraints(max_length=1000)] | None = None

    @field_validator("checked_at")
    @classmethod
    def checked_at_must_include_timezone(cls, checked_at: datetime) -> datetime:
        """Require portable, unambiguous health timestamps."""
        if checked_at.tzinfo is None:
            raise ValueError("checked_at must include a timezone")
        return checked_at
