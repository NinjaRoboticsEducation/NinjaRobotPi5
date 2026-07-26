from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ninjarobot_pi5_ide import (
    ActionRequest,
    ActionResult,
    ActionStatus,
    CapabilityDescriptor,
    ErrorDetails,
    RetrySafety,
    RiskLevel,
)


def capability() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name="distance.read",
        version="1.0.0",
        description="Read a simulated distance.",
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={"type": "object"},
        risk=RiskLevel.READ_ONLY,
        resources=("distance_sensor",),
        default_timeout_seconds=2.0,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
    )


def test_contracts_generate_json_schema_and_round_trip() -> None:
    descriptor = capability()

    restored = CapabilityDescriptor.model_validate_json(descriptor.model_dump_json())

    assert restored == descriptor
    assert CapabilityDescriptor.model_json_schema()["additionalProperties"] is False


def test_contracts_reject_unknown_fields_and_duplicate_resources() -> None:
    payload = capability().model_dump()
    payload["unexpected"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CapabilityDescriptor.model_validate(payload)

    payload = capability().model_dump()
    payload["resources"] = ("distance_sensor", "distance_sensor")
    with pytest.raises(ValidationError, match="resources must not contain duplicates"):
        CapabilityDescriptor.model_validate(payload)


def test_action_request_requires_timezone_aware_deadline() -> None:
    with pytest.raises(ValidationError, match="deadline must include a timezone"):
        ActionRequest(
            action_id="action-1",
            capability="distance.read",
            arguments={},
            requested_by="tester",
            session_id="session-1",
            deadline=datetime(2026, 1, 1),
            idempotency_key="request-1",
        )


def test_action_result_enforces_status_error_and_time_order() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    error = ErrorDetails(
        code="DEVICE_UNAVAILABLE",
        message="The device is unavailable.",
        definitely_not_executed=True,
        retry_safety=RetrySafety.SAFE,
        capability="distance.read",
        action_id="action-1",
    )

    with pytest.raises(ValidationError, match="successful results must not include"):
        ActionResult(
            action_id="action-1",
            status=ActionStatus.SUCCEEDED,
            error=error,
            started_at=now,
            finished_at=now,
            retry_safety=RetrySafety.SAFE,
        )

    with pytest.raises(ValidationError, match="finished_at must not be before"):
        ActionResult(
            action_id="action-1",
            status=ActionStatus.FAILED,
            error=error,
            started_at=now,
            finished_at=now - timedelta(seconds=1),
            retry_safety=RetrySafety.SAFE,
        )

    with pytest.raises(ValidationError, match="result and error retry_safety must agree"):
        ActionResult(
            action_id="action-1",
            status=ActionStatus.FAILED,
            error=error,
            started_at=now,
            finished_at=now,
            retry_safety=RetrySafety.UNSAFE,
        )
