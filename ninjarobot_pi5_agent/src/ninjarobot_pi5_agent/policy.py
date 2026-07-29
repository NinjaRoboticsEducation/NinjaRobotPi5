"""Deterministic confirmation, trust, and motion-arming policy."""

from __future__ import annotations

from dataclasses import dataclass

from ninjarobot_pi5_ide import RiskLevel

from .models import ToolDefinition, ToolTrust


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """User/session evidence evaluated before one tool call."""

    session_id: str
    lease_id: str | None = None
    confirmed: bool = False


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Machine-readable allow/deny decision."""

    allowed: bool
    reason: str
    confirmation_required: bool = False


@dataclass(frozen=True, slots=True)
class _MotionArm:
    lease_id: str | None


@dataclass(slots=True)
class _CameraGrant:
    lease_id: str | None
    claimed: bool = False


class CameraGrantManager:
    """Hold one-shot consent for a temporary AI camera preview."""

    def __init__(self) -> None:
        self._grants: dict[str, _CameraGrant] = {}

    def grant(
        self,
        session_id: str,
        *,
        confirmed: bool,
        lease_id: str | None = None,
    ) -> None:
        """Grant one preview only after an explicit user action."""
        if not confirmed:
            raise PermissionError("explicit confirmation is required for AI camera access")
        self._grants[session_id] = _CameraGrant(lease_id=lease_id)

    def is_granted(self, session_id: str, *, lease_id: str | None = None) -> bool:
        """Return whether an unused matching grant is available."""
        grant = self._grants.get(session_id)
        if grant is None or grant.claimed:
            return False
        if grant.lease_id is not None and grant.lease_id != lease_id:
            return False
        return True

    def claim(self, session_id: str, *, lease_id: str | None = None) -> bool:
        """Reserve the grant while one preview attempt is in progress."""
        if not self.is_granted(session_id, lease_id=lease_id):
            return False
        self._grants[session_id].claimed = True
        return True

    def claim_is_active(self, session_id: str, *, lease_id: str | None = None) -> bool:
        """Return whether the same session still owns the in-flight claim."""
        grant = self._grants.get(session_id)
        if grant is None or not grant.claimed:
            return False
        if grant.lease_id is not None and grant.lease_id != lease_id:
            return False
        return True

    def finish(
        self,
        session_id: str,
        *,
        succeeded: bool,
        lease_id: str | None = None,
    ) -> None:
        """Consume a successful preview; release a failed attempt for retry."""
        if not self.claim_is_active(session_id, lease_id=lease_id):
            return
        if succeeded:
            self._grants.pop(session_id, None)
        else:
            self._grants[session_id].claimed = False

    def revoke(self, session_id: str) -> None:
        """Revoke one session's unused or in-flight grant."""
        self._grants.pop(session_id, None)

    def revoke_all(self) -> None:
        """Revoke all grants during shutdown or model replacement."""
        self._grants.clear()


class MotionArmManager:
    """Hold explicit motion consent until a deterministic revocation event."""

    def __init__(self) -> None:
        self._arms: dict[str, _MotionArm] = {}

    def arm(
        self,
        session_id: str,
        *,
        confirmed: bool,
        lease_id: str | None = None,
    ) -> None:
        """Arm motion only after explicit user confirmation."""
        if not confirmed:
            raise PermissionError("explicit confirmation is required to arm motion")
        self._arms[session_id] = _MotionArm(lease_id=lease_id)

    def is_armed(self, session_id: str, *, lease_id: str | None = None) -> bool:
        """Return whether the matching session and optional lease remain armed."""
        arm = self._arms.get(session_id)
        if arm is None:
            return False
        if arm.lease_id is not None and arm.lease_id != lease_id:
            return False
        return True

    def disarm(self, session_id: str) -> None:
        """Revoke a session arm after stop or disconnect."""
        self._arms.pop(session_id, None)

    def disarm_all(self) -> None:
        """Revoke all motion consent during shutdown or model replacement."""
        self._arms.clear()


class PolicyEngine:
    """Apply non-bypassable risk and external-content rules."""

    def __init__(
        self,
        motion_arms: MotionArmManager,
        camera_grants: CameraGrantManager | None = None,
    ) -> None:
        self._motion_arms = motion_arms
        self._camera_grants = camera_grants or CameraGrantManager()

    @property
    def camera_grants(self) -> CameraGrantManager:
        """Return the service-owned camera consent manager."""
        return self._camera_grants

    def evaluate(
        self,
        definition: ToolDefinition,
        context: PolicyContext,
    ) -> PolicyDecision:
        """Evaluate one tool using catalog risk, never model-provided risk."""
        if (
            definition.trust is ToolTrust.EXTERNAL_UNTRUSTED
            and definition.risk is not RiskLevel.READ_ONLY
        ):
            return PolicyDecision(
                allowed=False,
                reason="Untrusted external tools may only perform read-only work.",
            )
        if definition.risk is RiskLevel.EMERGENCY:
            return PolicyDecision(allowed=True, reason="Emergency stops are always allowed.")
        if definition.risk is RiskLevel.MOTION:
            if self._motion_arms.is_armed(
                context.session_id,
                lease_id=context.lease_id,
            ):
                return PolicyDecision(
                    allowed=True,
                    reason="Motion is armed for this active session.",
                )
            return PolicyDecision(
                allowed=False,
                reason="Motion is not armed for this session.",
                confirmation_required=True,
            )
        if definition.name == "robot.camera.preview" and self._camera_grants.is_granted(
            context.session_id,
            lease_id=context.lease_id,
        ):
            return PolicyDecision(
                allowed=True,
                reason="One temporary AI camera preview is granted for this session.",
            )
        requires_confirmation = definition.confirmation_required or definition.risk in {
            RiskLevel.PRIVACY,
            RiskLevel.MAINTENANCE,
        }
        if requires_confirmation and not context.confirmed:
            return PolicyDecision(
                allowed=False,
                reason="This operation requires explicit user confirmation.",
                confirmation_required=True,
            )
        return PolicyDecision(allowed=True, reason="Tool policy requirements are satisfied.")
