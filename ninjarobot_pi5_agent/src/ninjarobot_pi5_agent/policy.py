"""Deterministic confirmation, trust, and motion-arming policy."""

from __future__ import annotations

import time
from collections.abc import Callable
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
    expires_at: float


class MotionArmManager:
    """Hold short-lived one-time motion consent per user session."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 1.0 <= ttl_seconds <= 3600.0:
            raise ValueError("motion arm TTL must be between 1 and 3600 seconds")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
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
        self._arms[session_id] = _MotionArm(
            lease_id=lease_id,
            expires_at=self._clock() + self._ttl_seconds,
        )

    def is_armed(self, session_id: str, *, lease_id: str | None = None) -> bool:
        """Return whether the matching session and optional lease remain armed."""
        arm = self._arms.get(session_id)
        if arm is None:
            return False
        if self._clock() >= arm.expires_at:
            self._arms.pop(session_id, None)
            return False
        if arm.lease_id is not None and arm.lease_id != lease_id:
            return False
        return True

    def disarm(self, session_id: str) -> None:
        """Revoke a session arm after stop, disconnect, or expiry."""
        self._arms.pop(session_id, None)

    def disarm_all(self) -> None:
        """Revoke all motion consent during service shutdown."""
        self._arms.clear()


class PolicyEngine:
    """Apply non-bypassable risk and external-content rules."""

    def __init__(self, motion_arms: MotionArmManager) -> None:
        self._motion_arms = motion_arms

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
