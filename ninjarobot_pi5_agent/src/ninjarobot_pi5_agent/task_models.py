"""Local task records and exact reminder time validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, StringConstraints, model_validator

from .models import AgentContractModel, Identifier


class TaskStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    MISSED = "missed"
    UNCERTAIN = "uncertain"


class TaskStep(AgentContractModel):
    description: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    status: TaskStatus = TaskStatus.QUEUED
    evidence: Annotated[str, StringConstraints(max_length=1000)] = ""


class LocalTask(AgentContractModel):
    kind: Literal["reminder", "request"] = "reminder"
    task_id: Identifier
    owner_scope: Annotated[str, StringConstraints(min_length=1, max_length=150)]
    user_id: Identifier | None = None
    source_session_id: Identifier
    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    status: TaskStatus = TaskStatus.DRAFT
    created_at: datetime
    updated_at: datetime
    due_at: datetime
    timezone: str
    repeat: Literal["none", "daily", "weekly"] = "none"
    notification: Literal["text", "display_buzzer"] = "text"
    approved_at: datetime | None = None
    recurrence_anchor: datetime | None = None
    occurrence: Annotated[int, Field(ge=0)] = 0
    steps: tuple[TaskStep, ...] = ()
    result: Annotated[str, StringConstraints(max_length=1000)] = ""
    limits: dict[str, int | float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_times(self) -> LocalTask:
        if self.notification == "display_buzzer" and len(self.title) > 160:
            raise ValueError("display reminders are limited to 160 characters")
        for value in (
            self.created_at,
            self.updated_at,
            self.due_at,
            self.approved_at,
            self.recurrence_anchor,
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError("task timestamps require a time zone")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("use an installed IANA time zone, such as Asia/Tokyo or UTC") from exc
        return self


def exact_due_time(value: str, timezone: str, now: datetime) -> datetime:
    """Require an offset and matching zone; reject nonexistent local times."""
    try:
        zone = ZoneInfo(timezone)
        supplied = datetime.fromisoformat(value)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError(
            "provide an exact ISO date/time with offset and an IANA time zone"
        ) from exc
    if supplied.tzinfo is None:
        raise ValueError("include the UTC offset to distinguish repeated daylight-saving times")
    local = supplied.astimezone(zone)
    if local.replace(tzinfo=None) != supplied.replace(tzinfo=None) or (
        local.utcoffset() != supplied.utcoffset()
    ):
        raise ValueError("the date/time and UTC offset do not match that time zone")
    due = supplied.astimezone(UTC)
    if not now < due <= now + timedelta(days=366):
        raise ValueError(
            "choose a future time within the next 366 days; past times are not shifted"
        )
    return due


def next_occurrence(task: LocalTask) -> datetime | None:
    """Keep the reviewed wall-clock time; refuse a nonexistent DST occurrence."""
    if task.repeat == "none":
        return None
    zone = ZoneInfo(task.timezone)
    local = (task.recurrence_anchor or task.due_at).astimezone(zone)
    interval = 1 if task.repeat == "daily" else 7
    elapsed_days = (task.due_at.astimezone(zone).date() - local.date()).days
    candidate = local + timedelta(days=max(1, elapsed_days // interval) * interval)
    if candidate.astimezone(UTC) <= task.due_at:
        candidate += timedelta(days=interval)
    result = candidate.astimezone(UTC)
    if result.astimezone(zone).replace(tzinfo=None) != candidate.replace(tzinfo=None):
        raise ValueError("next local time does not exist because the clock changes; review it")
    return result
