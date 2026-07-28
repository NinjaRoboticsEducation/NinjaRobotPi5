"""Conservative recovery decisions for failed tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ninjarobot_pi5_ide import RetrySafety

from .models import ToolDefinition, ToolExecutionResult, ToolExecutionStatus


class RecoveryAction(StrEnum):
    """Allowed outcomes of the deterministic recovery matrix."""

    NONE = "none"
    RETRY = "retry"
    REQUIRE_OPERATOR = "require_operator"


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    """One recovery choice and its audit-friendly reason."""

    action: RecoveryAction
    reason: str


class RecoveryPolicy:
    """Permit only bounded retries proven safe before physical execution."""

    def __init__(self, *, max_safe_retries: int = 1) -> None:
        if not 0 <= max_safe_retries <= 3:
            raise ValueError("max_safe_retries must be between 0 and 3")
        self._max_safe_retries = max_safe_retries

    def decide(
        self,
        definition: ToolDefinition,
        result: ToolExecutionResult,
        *,
        attempts_completed: int,
    ) -> RecoveryDecision:
        """Return a decision without executing or retrying the tool."""
        if result.status is ToolExecutionStatus.SUCCEEDED:
            return RecoveryDecision(RecoveryAction.NONE, "The tool succeeded.")
        if result.status in {
            ToolExecutionStatus.CANCELLED,
            ToolExecutionStatus.DENIED,
        }:
            return RecoveryDecision(
                RecoveryAction.NONE,
                "Cancellation and policy denials are never retried automatically.",
            )
        safely_retryable = (
            definition.idempotent
            and result.definitely_not_executed
            and result.retry_safety is RetrySafety.SAFE
        )
        if safely_retryable and attempts_completed <= self._max_safe_retries:
            return RecoveryDecision(
                RecoveryAction.RETRY,
                "The IDE proved the idempotent action did not execute.",
            )
        return RecoveryDecision(
            RecoveryAction.REQUIRE_OPERATOR,
            "Execution is uncertain or retry safety is not proven.",
        )
