from __future__ import annotations

from ninjarobot_pi5_agent import (
    RecoveryAction,
    RecoveryPolicy,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from ninjarobot_pi5_ide import RetrySafety, RiskLevel


def definition(*, idempotent: bool = True) -> ToolDefinition:
    return ToolDefinition(
        name="robot.distance.read",
        version="1.0.0",
        description="Read distance.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk=RiskLevel.READ_ONLY,
        default_timeout_seconds=2.0,
        idempotent=idempotent,
        cancellable=True,
        confirmation_required=False,
    )


def failed_result(
    *,
    definitely_not_executed: bool,
    retry_safety: RetrySafety,
    status: ToolExecutionStatus = ToolExecutionStatus.FAILED,
) -> ToolExecutionResult:
    return ToolExecutionResult(
        call_id="call-1",
        tool_name="robot.distance.read",
        status=status,
        error="test failure",
        definitely_not_executed=definitely_not_executed,
        retry_safety=retry_safety,
    )


def test_recovery_retries_only_proven_safe_nonexecuted_idempotent_calls() -> None:
    policy = RecoveryPolicy(max_safe_retries=1)

    safe = policy.decide(
        definition(),
        failed_result(
            definitely_not_executed=True,
            retry_safety=RetrySafety.SAFE,
        ),
        attempts_completed=1,
    )
    uncertain = policy.decide(
        definition(),
        failed_result(
            definitely_not_executed=False,
            retry_safety=RetrySafety.UNKNOWN,
        ),
        attempts_completed=1,
    )
    physical = policy.decide(
        definition(idempotent=False),
        failed_result(
            definitely_not_executed=True,
            retry_safety=RetrySafety.SAFE,
        ),
        attempts_completed=1,
    )

    assert safe.action is RecoveryAction.RETRY
    assert uncertain.action is RecoveryAction.REQUIRE_OPERATOR
    assert physical.action is RecoveryAction.REQUIRE_OPERATOR


def test_recovery_never_retries_timeout_cancel_or_exhausted_budget() -> None:
    policy = RecoveryPolicy(max_safe_retries=1)

    timed_out = policy.decide(
        definition(),
        failed_result(
            definitely_not_executed=False,
            retry_safety=RetrySafety.UNKNOWN,
            status=ToolExecutionStatus.TIMED_OUT,
        ),
        attempts_completed=1,
    )
    cancelled = policy.decide(
        definition(),
        failed_result(
            definitely_not_executed=True,
            retry_safety=RetrySafety.SAFE,
            status=ToolExecutionStatus.CANCELLED,
        ),
        attempts_completed=1,
    )
    exhausted = policy.decide(
        definition(),
        failed_result(
            definitely_not_executed=True,
            retry_safety=RetrySafety.SAFE,
        ),
        attempts_completed=2,
    )

    assert timed_out.action is RecoveryAction.REQUIRE_OPERATOR
    assert cancelled.action is RecoveryAction.NONE
    assert exhausted.action is RecoveryAction.REQUIRE_OPERATOR
