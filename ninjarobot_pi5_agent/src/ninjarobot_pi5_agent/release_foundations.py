"""Strict, redaction-safe Phase 8 feature state and dependency reporting."""

from __future__ import annotations

import importlib.util
import threading
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from .models import AgentContractModel

ReleaseComponentName = Literal[
    "voice",
    "remote_access",
    "pairing",
    "onboarding",
    "shutdown",
]
StatusDetail = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$"),
]


class ReleaseFeatureState(StrEnum):
    """Stable lifecycle values shared by status, IPC, and interfaces."""

    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    IDLE = "idle"
    STARTING = "starting"
    READY = "ready"
    LISTENING = "listening"
    DETECTED = "detected"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    DISPATCHING = "dispatching"
    COOLDOWN = "cooldown"
    CONNECTING = "connecting"
    WAITING_FOR_CONNECTION = "waiting_for_connection"
    CONNECTED = "connected"
    LOCAL_FALLBACK = "local_fallback"
    PAIRING = "pairing"
    AUTHENTICATED = "authenticated"
    SHUTTING_DOWN = "shutting_down"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DEGRADED = "degraded"
    FAILED = "failed"


class ReleaseComponentStatus(AgentContractModel):
    """One feature status without URLs, credentials, cookies, or private paths."""

    enabled: bool
    state: ReleaseFeatureState
    detail: StatusDetail | None = None
    dependencies: dict[str, bool] = Field(default_factory=dict)


class ReleaseStatusSnapshot(AgentContractModel):
    """Normalized Phase 8 state embedded in the existing runtime status."""

    voice: ReleaseComponentStatus
    remote_access: ReleaseComponentStatus
    pairing: ReleaseComponentStatus
    onboarding: ReleaseComponentStatus
    shutdown: ReleaseComponentStatus


class ReleaseStatusRegistry:
    """Synchronously expose current feature states without active health probes."""

    def __init__(
        self,
        *,
        voice_enabled: bool,
        remote_access_enabled: bool,
        onboarding_enabled: bool,
        shutdown_enabled: bool,
    ) -> None:
        voice_dependencies = _dependency_status(("openwakeword", "onnxruntime"))
        remote_dependencies = _dependency_status(("pyngrok",))
        onboarding_dependencies = _dependency_status(("qrcode",))
        pairing_enabled = remote_access_enabled or onboarding_enabled
        self._lock = threading.RLock()
        self._components: dict[ReleaseComponentName, ReleaseComponentStatus] = {
            "voice": _initial_component(voice_enabled, voice_dependencies),
            "remote_access": _initial_component(remote_access_enabled, remote_dependencies),
            "pairing": _initial_component(pairing_enabled, {}),
            "onboarding": _initial_component(onboarding_enabled, onboarding_dependencies),
            "shutdown": _initial_component(shutdown_enabled, {}),
        }

    @classmethod
    def disabled(cls) -> ReleaseStatusRegistry:
        """Return the backwards-compatible state for an existing Phase 7 runtime."""
        return cls(
            voice_enabled=False,
            remote_access_enabled=False,
            onboarding_enabled=False,
            shutdown_enabled=False,
        )

    def update(
        self,
        component: ReleaseComponentName,
        state: ReleaseFeatureState,
        *,
        detail: str | None = None,
    ) -> ReleaseComponentStatus:
        """Atomically update one known component with a sanitized detail code."""
        with self._lock:
            current = self._components[component]
            if not current.enabled and state is not ReleaseFeatureState.DISABLED:
                raise ValueError(f"cannot update disabled release component: {component}")
            validated = ReleaseComponentStatus.model_validate(
                {
                    **current.model_dump(mode="python"),
                    "state": state,
                    "detail": detail,
                }
            )
            self._components[component] = validated
            return validated

    def set_enabled(
        self,
        component: ReleaseComponentName,
        enabled: bool,
    ) -> ReleaseComponentStatus:
        """Apply an explicit operator enable/disable action to one component."""
        with self._lock:
            current = self._components[component]
            if not enabled:
                updated = ReleaseComponentStatus(
                    enabled=False,
                    state=ReleaseFeatureState.DISABLED,
                    dependencies=current.dependencies,
                )
            else:
                missing = any(not value for value in current.dependencies.values())
                updated = ReleaseComponentStatus(
                    enabled=True,
                    state=(
                        ReleaseFeatureState.UNAVAILABLE if missing else ReleaseFeatureState.IDLE
                    ),
                    detail="optional_dependencies_missing" if missing else None,
                    dependencies=current.dependencies,
                )
            self._components[component] = updated
            return updated

    def status(self) -> dict[str, object]:
        """Return a stable snapshot containing no active dependency or network probes."""
        with self._lock:
            snapshot = ReleaseStatusSnapshot(
                voice=self._components["voice"],
                remote_access=self._components["remote_access"],
                pairing=self._components["pairing"],
                onboarding=self._components["onboarding"],
                shutdown=self._components["shutdown"],
            )
        return snapshot.model_dump(mode="json")


def _dependency_status(module_names: tuple[str, ...]) -> dict[str, bool]:
    return {name: _module_available(name) for name in module_names}


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _initial_component(
    enabled: bool,
    dependencies: dict[str, bool],
) -> ReleaseComponentStatus:
    if not enabled:
        return ReleaseComponentStatus(
            enabled=False,
            state=ReleaseFeatureState.DISABLED,
            dependencies=dependencies,
        )
    missing = any(not available for available in dependencies.values())
    return ReleaseComponentStatus(
        enabled=True,
        state=(ReleaseFeatureState.UNAVAILABLE if missing else ReleaseFeatureState.IDLE),
        detail="optional_dependencies_missing" if missing else None,
        dependencies=dependencies,
    )
