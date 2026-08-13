"""Phase 8 configuration-independent lifecycle foundation tests."""

from __future__ import annotations

import pytest
from ninjarobot_pi5_agent.events import AgentEventType
from ninjarobot_pi5_agent.release_foundations import (
    ReleaseComponentStatus,
    ReleaseFeatureState,
    ReleaseStatusRegistry,
)
from pydantic import ValidationError


def test_disabled_release_status_preserves_phase_7_behavior() -> None:
    status = ReleaseStatusRegistry.disabled().status()

    assert set(status) == {
        "voice",
        "remote_access",
        "pairing",
        "onboarding",
        "shutdown",
    }
    assert all(component["state"] == "disabled" for component in status.values())
    assert all(component["enabled"] is False for component in status.values())


def test_enabled_features_report_missing_optional_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(
        "ninjarobot_pi5_agent.release_foundations._module_available",
        lambda _name: False,
    )
    registry = ReleaseStatusRegistry(
        voice_enabled=True,
        remote_access_enabled=True,
        onboarding_enabled=True,
        shutdown_enabled=True,
    )
    status = registry.status()

    assert status["voice"]["state"] == "unavailable"
    assert status["remote_access"]["detail"] == "optional_dependencies_missing"
    assert status["onboarding"]["state"] == "unavailable"
    assert status["pairing"]["state"] == "idle"
    assert status["shutdown"]["state"] == "idle"


def test_release_status_updates_are_bounded_and_disabled_features_cannot_start() -> None:
    disabled = ReleaseStatusRegistry.disabled()
    with pytest.raises(ValueError, match="cannot update disabled"):
        disabled.update("voice", ReleaseFeatureState.LISTENING)

    enabled = ReleaseStatusRegistry(
        voice_enabled=True,
        remote_access_enabled=False,
        onboarding_enabled=False,
        shutdown_enabled=False,
    )
    updated = enabled.update(
        "voice",
        ReleaseFeatureState.DEGRADED,
        detail="microphone_unavailable",
    )
    assert updated.state is ReleaseFeatureState.DEGRADED
    assert enabled.status()["voice"]["detail"] == "microphone_unavailable"

    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        enabled.update("voice", ReleaseFeatureState.FAILED, detail="token=do-not-log")


def test_release_event_categories_are_stable() -> None:
    assert {
        AgentEventType.VOICE.value,
        AgentEventType.REMOTE_ACCESS.value,
        AgentEventType.PAIRING.value,
        AgentEventType.ONBOARDING.value,
        AgentEventType.SHUTDOWN.value,
    } == {"voice", "remote_access", "pairing", "onboarding", "shutdown"}


def test_release_component_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ReleaseComponentStatus.model_validate(
            {
                "enabled": False,
                "state": "disabled",
                "secret": "must-not-serialize",
            }
        )
