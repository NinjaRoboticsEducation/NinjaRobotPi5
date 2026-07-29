from __future__ import annotations

import pytest

from ninjarobot_pi5_agent import (
    CameraGrantManager,
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
    name: str = "robot.behavior.run",
    confirmation_required: bool = False,
    trust: ToolTrust = ToolTrust.TRUSTED,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
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
    arms = MotionArmManager()
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

    arms.disarm("session-1")
    assert not policy.evaluate(tool(RiskLevel.MOTION), context).allowed


def test_confirmed_motion_arm_survives_slow_local_model_reasoning() -> None:
    arms = MotionArmManager()
    policy = PolicyEngine(arms)
    context = PolicyContext(session_id="slow-model", lease_id=None)

    arms.arm("slow-model", confirmed=True)
    decision = policy.evaluate(tool(RiskLevel.MOTION), context)
    assert decision.allowed
    assert decision.reason == "Motion is armed for this active session."


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


def test_one_shot_camera_grant_survives_failure_and_is_consumed_by_success() -> None:
    grants = CameraGrantManager()
    policy = PolicyEngine(MotionArmManager(), grants)
    camera = tool(
        RiskLevel.PRIVACY,
        name="robot.camera.preview",
        confirmation_required=True,
    )
    context = PolicyContext(session_id="camera-session", lease_id="lease-1")

    assert not policy.evaluate(camera, context).allowed
    with pytest.raises(PermissionError, match="explicit confirmation"):
        grants.grant("camera-session", confirmed=False, lease_id="lease-1")

    first_sequence = grants.grant(
        "camera-session",
        confirmed=True,
        lease_id="lease-1",
    )
    assert first_sequence == 1
    assert grants.status("camera-session", lease_id="lease-1") == {
        "authorized_for_next_preview": True,
        "captures_remaining": 1,
        "capture_in_progress": False,
        "current_grant_sequence": 1,
        "last_issued_grant_sequence": 1,
        "repeatable_after_user_regrant": True,
    }
    assert policy.evaluate(camera, context).allowed
    assert not policy.evaluate(
        camera,
        PolicyContext(session_id="camera-session", lease_id="wrong-lease"),
    ).allowed

    assert grants.claim("camera-session", lease_id="lease-1")
    grants.finish("camera-session", lease_id="lease-1", succeeded=False)
    assert grants.is_granted("camera-session", lease_id="lease-1")

    assert grants.claim("camera-session", lease_id="lease-1")
    grants.finish("camera-session", lease_id="lease-1", succeeded=True)
    assert not grants.is_granted("camera-session", lease_id="lease-1")
    assert grants.status("camera-session", lease_id="lease-1") == {
        "authorized_for_next_preview": False,
        "captures_remaining": 0,
        "capture_in_progress": False,
        "current_grant_sequence": None,
        "last_issued_grant_sequence": 1,
        "repeatable_after_user_regrant": True,
    }

    second_sequence = grants.grant(
        "camera-session",
        confirmed=True,
        lease_id="lease-1",
    )
    assert second_sequence == 2
    assert grants.is_granted("camera-session", lease_id="lease-1")
    assert grants.status("camera-session", lease_id="lease-1")["current_grant_sequence"] == 2
