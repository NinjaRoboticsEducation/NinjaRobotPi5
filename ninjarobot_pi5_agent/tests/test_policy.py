from __future__ import annotations

import pytest

from ninjarobot_pi5_agent import (
    MotionArmManager,
    PolicyContext,
    PolicyEngine,
    ToolDefinition,
    ToolTrust,
)
from ninjarobot_pi5_ide import RiskLevel


def tool(
    risk: RiskLevel,
    *,
    confirmation_required: bool = False,
    trust: ToolTrust = ToolTrust.TRUSTED,
) -> ToolDefinition:
    return ToolDefinition(
        name="robot.behavior.run",
        version="1.0.0",
        description="Run a behavior.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk=risk,
        default_timeout_seconds=10.0,
        idempotent=False,
        cancellable=True,
        confirmation_required=confirmation_required,
        trust=trust,
    )


def test_motion_requires_explicit_session_and_lease_arm() -> None:
    now = [100.0]
    arms = MotionArmManager(ttl_seconds=10.0, clock=lambda: now[0])
    policy = PolicyEngine(arms)
    context = PolicyContext(session_id="session-1", lease_id="lease-1")

    denied = policy.evaluate(tool(RiskLevel.MOTION), context)
    assert not denied.allowed
    assert denied.confirmation_required

    with pytest.raises(PermissionError, match="explicit confirmation"):
        arms.arm("session-1", confirmed=False, lease_id="lease-1")

    arms.arm("session-1", confirmed=True, lease_id="lease-1")
    assert policy.evaluate(tool(RiskLevel.MOTION), context).allowed
    assert not policy.evaluate(
        tool(RiskLevel.MOTION),
        PolicyContext(session_id="session-1", lease_id="other-lease"),
    ).allowed

    now[0] = 111.0
    assert not policy.evaluate(tool(RiskLevel.MOTION), context).allowed


def test_emergency_is_allowed_and_sensitive_work_requires_confirmation() -> None:
    policy = PolicyEngine(MotionArmManager())
    context = PolicyContext(session_id="session-1")

    assert policy.evaluate(tool(RiskLevel.EMERGENCY), context).allowed
    assert not policy.evaluate(tool(RiskLevel.PRIVACY), context).allowed
    assert policy.evaluate(
        tool(RiskLevel.PRIVACY),
        PolicyContext(session_id="session-1", confirmed=True),
    ).allowed


def test_external_tools_cannot_claim_physical_risk() -> None:
    policy = PolicyEngine(MotionArmManager())

    decision = policy.evaluate(
        tool(RiskLevel.MOTION, trust=ToolTrust.EXTERNAL_UNTRUSTED),
        PolicyContext(session_id="session-1"),
    )

    assert not decision.allowed
    assert "read-only" in decision.reason
